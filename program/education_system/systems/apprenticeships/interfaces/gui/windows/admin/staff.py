"""Provider staff and the pressure on their caseloads."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.staff.assessors import (
    validate_staff_role,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets

logger = logging.getLogger(__name__)

_SUBTITLE = (
    "Caseload size is the best early warning there is: a tutor over the threshold "
    "stops seeing people long before the missed reviews show up as a compliance "
    "problem."
)

_COLUMNS = (
    ("name", "Staff", 200),
    ("role", "Role", 140),
    ("total", "Caseload", 90, "e"),
    ("active", "Active", 80, "e"),
    ("gateway", "At gateway", 90, "e"),
    ("overdue", "Reviews overdue", 120, "e"),
    ("behind", "Behind on OTJ", 110, "e"),
    ("evidence", "Evidence to assess", 130, "e"),
    ("rag", "RAG", 70),
)


def render(gui) -> None:
    """Every tutor's caseload, with the staff record behind it."""
    frame = gui.clear()
    widgets.heading(frame, "Staff & Caseloads", subtitle=_SUBTITLE)

    # There is no staff service, so this screen talks to the repository —
    # which means the permission check the service layer would have done
    # has to happen here instead.
    if not gui.actor.can("staff.view"):
        widgets.empty_state(
            frame, "Your role may not see the provider's staff records."
        )
        return

    table = widgets.DataTable(frame, _COLUMNS)
    _, rows = widgets.guard(staff_repository.list_caseloads)
    rows = rows or []
    table.populate(
        rows,
        lambda c: (
            c.name, c.staff.staff_role, c.total, c.active, c.at_gateway,
            c.reviews_overdue, c.otj_behind, c.evidence_awaiting_assessment,
            c.rag_rating,
        ),
        identity=lambda c: c.staff.staff_id,
        tag=lambda c: c.rag_rating,
        noun="caseload",
    )
    if not rows:
        widgets.empty_state(
            frame,
            "No active staff are recorded. Add a tutor here before assigning "
            "apprentices to a caseload.",
        )

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("staff.manage"):
        buttons.append(("New", lambda: _create(gui)))
        buttons.append(("Edit", lambda: _edit(gui, table)))
        buttons.append(("Deactivate", lambda: _deactivate(gui, table)))
    buttons.append(("View Caseload", lambda: _open_caseload(gui, table)))
    widgets.button_bar(frame, buttons)


# ═════════════════════════════════════════════════════════════════════
# One caseload
# ═════════════════════════════════════════════════════════════════════

def _open_caseload(gui, table: widgets.DataTable) -> None:
    staff_id = table.require_selection_int("view a caseload")
    if staff_id is not None:
        _caseload(gui, staff_id)


def _caseload(gui, staff_id: int) -> None:
    """Who one member of staff is actually responsible for."""
    frame = gui.clear()
    _, caseload = widgets.guard(
        lambda: staff_repository.build_caseload(staff_id, with_members=True)
    )
    if caseload is None:
        widgets.heading(frame, "Caseload")
        widgets.button_bar(frame, [("← Back to staff", lambda: render(gui))])
        widgets.empty_state(frame, "That staff record could not be opened.")
        return

    member = caseload.staff
    widgets.heading(
        frame, f"{member.full_name} — caseload",
        subtitle=f"{member.staff_role} · {caseload.rag_rating} · "
                 f"{caseload.headroom} more apprentice(s) before capacity",
    )
    widgets.button_bar(frame, [("← Back to staff", lambda: render(gui))])

    widgets.field_grid(
        frame,
        (
            ("Email", member.email),
            ("Phone", member.phone),
            ("Login", member.username),
            ("Specialisms", member.specialisms),
            ("Active apprentices", caseload.active),
            ("At gateway", caseload.at_gateway),
            ("Reviews overdue", caseload.reviews_overdue),
            ("Behind on off-the-job", caseload.otj_behind),
            ("Evidence to assess", caseload.evidence_awaiting_assessment),
        ),
        columns=3,
    )

    members = list(caseload.members)
    if not members:
        widgets.empty_state(
            frame,
            "Nobody is currently assigned to this caseload. Assign apprentices from "
            "the Apprentices screen.",
        )
        return

    table = widgets.DataTable(
        frame,
        (
            ("name", "Apprentice", 200),
            ("programme", "Programme", 220),
            ("employer", "Employer", 170),
            ("status", "Status", 120),
            ("otj", "Off-the-job", 90, "e"),
            ("elapsed", "Elapsed", 80, "e"),
            ("gateway", "Gateway", 100),
        ),
        height=16,
    )
    table.populate(
        members,
        lambda s: (
            s.full_name, s.programme_title, s.employer_name, s.apprentice.status,
            widgets.percent(s.otj_percent), widgets.percent(s.progress_percent),
            s.gateway_status,
        ),
        identity=lambda s: s.apprentice.apprentice_id,
        tag=lambda s: s.apprentice.status,
        noun="apprentice",
    )


# ═════════════════════════════════════════════════════════════════════
# Staff records
# ═════════════════════════════════════════════════════════════════════

def _create(gui) -> None:
    def save(values: dict[str, Any]) -> None:
        staff_repository.create({**_payload(values), "active": 1})

    if widgets.FormDialog(gui.root, "Add staff member", _fields(None), save).saved:
        gui.refresh()


def _edit(gui, table: widgets.DataTable) -> None:
    staff_id = table.require_selection_int("edit a staff record")
    if staff_id is None:
        return
    _, member = widgets.guard(lambda: staff_repository.get(staff_id))
    if member is None:
        return

    def save(values: dict[str, Any]) -> None:
        staff_repository.update(staff_id, _payload(values))

    if widgets.FormDialog(
        gui.root, f"Edit {member.full_name}", _fields(member), save
    ).saved:
        gui.refresh()


def _deactivate(gui, table: widgets.DataTable) -> None:
    staff_id = table.require_selection_int("deactivate a staff record")
    if staff_id is None:
        return
    if not widgets.confirm(
        "Deactivate this member of staff?\n\nTheir apprentices keep the record and "
        "surface as unassigned, so the reassignment is visible rather than silent.",
        title="Deactivate staff",
    ):
        return
    ok, _ = widgets.guard(lambda: staff_repository.update(staff_id, {"active": 0}))
    if ok:
        gui.refresh()


def _fields(member: Any) -> list[dict[str, Any]]:
    return [
        {"key": "full_name", "label": "Name", "required": True,
         "value": getattr(member, "full_name", "")},
        {"key": "staff_role", "label": "Role", "kind": "combo", "required": True,
         "options": config.STAFF_ROLES,
         "value": getattr(member, "staff_role", "Tutor")},
        {"key": "email", "label": "Email", "value": getattr(member, "email", "")},
        {"key": "phone", "label": "Phone", "value": getattr(member, "phone", "")},
        {"key": "username", "label": "Login username",
         "value": getattr(member, "username", ""),
         "help": "Links this record to a staff login and scopes their caseload."},
        {"key": "specialisms", "label": "Specialisms",
         "value": getattr(member, "specialisms", ""),
         "help": "Comma-separated."},
    ]


def _payload(values: dict[str, Any]) -> dict[str, Any]:
    """Check a staff payload the way a service would, then hand it on.

    Raising from here keeps the dialog open with the message inline, which
    is the whole reason the repository call happens inside ``on_save``.
    """
    from education_system.systems.apprenticeships.domain.apprentices.models import (
        ValidationError,
    )

    name = str(values.get("full_name") or "").strip()
    if not name:
        raise ValidationError("Name is required")
    email = str(values.get("email") or "").strip()
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        raise ValidationError(f"{email!r} is not a valid email address")

    return {
        "full_name": name,
        "staff_role": validate_staff_role(values.get("staff_role")),
        "email": email or None,
        "phone": str(values.get("phone") or "").strip() or None,
        "username": str(values.get("username") or "").strip() or None,
        "specialisms": str(values.get("specialisms") or "").strip() or None,
    }
