"""Employers: the organisations that employ the apprentices, and their sites."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import employer_service

logger = logging.getLogger(__name__)

_SUBTITLE = (
    "Every employing organisation the provider has a contract with. Size and pay "
    "bill decide the funding route, so they are worth keeping current."
)

_COLUMNS = (
    ("name", "Employer", 220),
    ("sector", "Sector", 150),
    ("size", "Size", 90),
    ("status", "Status", 100),
    ("active", "Active apprentices", 130, "e"),
    ("retention", "Retention", 90, "e"),
    ("pending", "Pending approvals", 130, "e"),
)


def render(gui) -> None:
    """The employer list, with workplaces, contacts and the levy position."""
    frame = gui.clear()
    widgets.heading(frame, "Employers", subtitle=_SUBTITLE)

    filters = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.EMPLOYER_STATUSES),
            ("search", "Search", "entry"),
            ("active_only", "Active only", "check"),
        ),
        lambda: reload(),
    )
    table = widgets.DataTable(frame, _COLUMNS)
    hint = widgets.empty_state(frame, "")

    def reload() -> None:
        _, rows = widgets.guard(
            lambda: employer_service.list_employers(gui.actor, **filters.values())
        )
        rows = rows or []
        table.populate(
            rows,
            lambda e: (
                e.name, e.employer.sector, e.employer.size, e.employer.status,
                e.active_apprentices, widgets.percent(e.retention_rate),
                e.pending_otj_approvals,
            ),
            identity=lambda e: e.employer.employer_id,
            noun="employer",
        )
        hint.config(
            text="" if rows else
            "No employer matches these filters. Clear them to see everyone, or use "
            "New to add an organisation.",
        )

    buttons: list[tuple[str, Any]] = []
    can_manage = gui.actor.can("employer.manage")
    if can_manage:
        buttons.append(("New", lambda: _create(gui)))
        buttons.append(("Edit", lambda: _edit(gui, table)))
    if gui.actor.is_admin:
        buttons.append(("Delete", lambda: _delete(gui, table)))
    buttons.append(("Workplaces…", lambda: _open_sub(gui, table, _workplaces)))
    buttons.append(("Managers…", lambda: _open_sub(gui, table, _managers)))
    if gui.actor.can("employer.contact"):
        buttons.append(("Contacts & commitments…",
                        lambda: _open_sub(gui, table, _contacts_and_commitments)))
    if gui.actor.can("funding.view") or can_manage:
        buttons.append(("Levy position", lambda: _open_sub(gui, table, _levy)))
    widgets.button_bar(frame, buttons)

    reload()


def _open_sub(gui, table: widgets.DataTable, screen) -> None:
    employer_id = table.require_selection_int("open that")
    if employer_id is not None:
        screen(gui, employer_id)


def _back(gui, parent) -> None:
    widgets.button_bar(parent, [("← Back to employers", lambda: render(gui))])


def _contacts_and_commitments(gui, employer_id: int) -> None:
    """The shared contacts screen: contact log and commitments for this employer."""
    from education_system.systems.apprenticeships.interfaces.gui.windows.shared import (
        employer_contacts,
    )
    employer_contacts.open_employer(gui, employer_id)


def _load(gui, employer_id: int):
    ok, summary = widgets.guard(
        lambda: employer_service.get_employer(gui.actor, employer_id)
    )
    return summary if ok else None


# ═════════════════════════════════════════════════════════════════════
# The employer record
# ═════════════════════════════════════════════════════════════════════

def _create(gui) -> None:
    def save(values: dict[str, Any]) -> None:
        employer_service.create_employer(gui.actor, _payload(values))

    dialog = widgets.FormDialog(
        gui.root, "Add employer", _fields(None), save,
        intro="Pay bill decides levy status and headcount decides the small-employer "
              "exemption, so both change what an apprenticeship costs.",
    )
    if dialog.saved:
        gui.refresh()


def _edit(gui, table: widgets.DataTable) -> None:
    employer_id = table.require_selection_int("edit an employer")
    if employer_id is None:
        return
    summary = _load(gui, employer_id)
    if summary is None:
        return

    def save(values: dict[str, Any]) -> None:
        employer_service.update_employer(gui.actor, employer_id, _payload(values))

    dialog = widgets.FormDialog(
        gui.root, f"Edit {summary.name}", _fields(summary.employer), save
    )
    if dialog.saved:
        gui.refresh()


def _fields(employer: Any) -> list[dict[str, Any]]:
    return [
        {"key": "name", "label": "Employer name", "required": True,
         "value": getattr(employer, "name", "")},
        {"key": "company_number", "label": "Company number",
         "value": getattr(employer, "company_number", "")},
        {"key": "sector", "label": "Sector", "value": getattr(employer, "sector", "")},
        {"key": "size", "label": "Size band", "kind": "combo",
         "options": ("", *config.EMPLOYER_SIZES),
         "value": getattr(employer, "size", ""),
         "help": "Left blank, it is derived from the headcount."},
        {"key": "headcount", "label": "Headcount",
         "value": getattr(employer, "headcount", "")},
        {"key": "paybill", "label": "Annual pay bill",
         "value": getattr(employer, "paybill", ""),
         "help": f"Above {config.CURRENCY_SYMBOL}{config.LEVY_THRESHOLD_PAYBILL:,.0f} "
                 "the employer pays the levy."},
        {"key": "address", "label": "Address", "kind": "text",
         "value": getattr(employer, "address", "")},
        {"key": "postcode", "label": "Postcode",
         "value": getattr(employer, "postcode", "")},
        {"key": "status", "label": "Status", "kind": "combo",
         "options": config.EMPLOYER_STATUSES,
         "value": getattr(employer, "status", "Prospect")},
        {"key": "contract_start", "label": "Contract start",
         "value": getattr(employer, "contract_start", ""), "help": "YYYY-MM-DD"},
        {"key": "contract_end", "label": "Contract end",
         "value": getattr(employer, "contract_end", "")},
        {"key": "notes", "label": "Notes", "kind": "text",
         "value": getattr(employer, "notes", "")},
    ]


def _payload(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: values.get(key, "")
        for key in (
            "name", "company_number", "sector", "size", "headcount", "paybill",
            "address", "postcode", "status", "contract_start", "contract_end", "notes",
        )
    }


def _delete(gui, table: widgets.DataTable) -> None:
    employer_id = table.require_selection_int("delete an employer")
    if employer_id is None:
        return
    if not widgets.confirm(
        "Delete this employer, its sites and its contacts?\n\n"
        "An organisation the provider has stopped working with should be set to "
        "'Ended' instead — that keeps the contract history the funding audit reads.",
        title="Delete employer",
    ):
        return
    reason = widgets.ask_reason("Why is this employer being deleted?")
    if reason is None:
        return
    ok, _ = widgets.guard(
        lambda: employer_service.delete_employer(gui.actor, employer_id, reason=reason)
    )
    if ok:
        gui.refresh()


# ═════════════════════════════════════════════════════════════════════
# Workplaces
# ═════════════════════════════════════════════════════════════════════

def _workplaces(gui, employer_id: int) -> None:
    """The sites this employer may place apprentices at."""
    frame = gui.clear()
    summary = _load(gui, employer_id)
    name = summary.name if summary else f"Employer {employer_id}"
    widgets.heading(
        frame, f"{name} — workplaces",
        subtitle="Health and safety vetting is per site: only a site with a current "
                 "check may host an apprentice.",
    )
    _back(gui, frame)

    table = widgets.DataTable(
        frame,
        (
            ("name", "Site", 200),
            ("address", "Address", 240),
            ("postcode", "Postcode", 100),
            ("checked", "H&S checked", 110),
            ("expires", "Expires", 110),
            ("current", "Can host", 90),
            ("active", "Active", 80),
        ),
        height=14,
    )
    _, rows = widgets.guard(
        lambda: employer_service.list_workplaces(gui.actor, employer_id)
    )
    rows = rows or []
    table.populate(
        rows,
        lambda w: (
            w.name, w.address, w.postcode, w.hs_checked_date, w.hs_expiry_date,
            w.can_host_apprentices, w.active,
        ),
        identity=lambda w: w.workplace_id,
        noun="site",
    )
    if not rows:
        widgets.empty_state(
            frame,
            "No sites are recorded. Add the address an apprentice actually works at — "
            "the health and safety check is against the site, not the organisation.",
        )

    if not gui.actor.can("employer.manage"):
        return

    def add() -> None:
        def save(values: dict[str, Any]) -> None:
            employer_service.add_workplace(gui.actor, employer_id, _workplace_payload(values))

        if widgets.FormDialog(
            gui.root, "Add workplace", _workplace_fields(None), save
        ).saved:
            _workplaces(gui, employer_id)

    def edit() -> None:
        workplace_id = table.require_selection_int("edit a site")
        if workplace_id is None:
            return
        existing = next((w for w in rows if w.workplace_id == workplace_id), None)

        def save(values: dict[str, Any]) -> None:
            employer_service.update_workplace(gui.actor, workplace_id, _workplace_payload(values))

        if widgets.FormDialog(
            gui.root, "Edit workplace", _workplace_fields(existing), save
        ).saved:
            _workplaces(gui, employer_id)

    def deactivate() -> None:
        workplace_id = table.require_selection_int("deactivate a site")
        if workplace_id is None:
            return
        if not widgets.confirm(
            "Stop new placements at this site?\n\n"
            "Apprentices already placed there keep it on their record, so the health "
            "and safety evidence for that period survives.",
            title="Deactivate workplace",
        ):
            return
        ok_off, _ = widgets.guard(
            lambda: employer_service.deactivate_workplace(gui.actor, workplace_id)
        )
        if ok_off:
            _workplaces(gui, employer_id)

    widgets.button_bar(frame, [("Add", add), ("Edit", edit), ("Deactivate", deactivate)])


def _workplace_fields(workplace: Any) -> list[dict[str, Any]]:
    return [
        {"key": "name", "label": "Site name", "required": True,
         "value": getattr(workplace, "name", "")},
        {"key": "address", "label": "Address", "kind": "text",
         "value": getattr(workplace, "address", "")},
        {"key": "postcode", "label": "Postcode",
         "value": getattr(workplace, "postcode", "")},
        {"key": "hs_checked_date", "label": "H&S checked",
         "value": getattr(workplace, "hs_checked_date", ""), "help": "YYYY-MM-DD"},
        {"key": "hs_expiry_date", "label": "H&S expires",
         "value": getattr(workplace, "hs_expiry_date", ""),
         "help": "Blank means the check does not lapse."},
    ]


def _workplace_payload(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: values.get(key, "")
        for key in ("name", "address", "postcode", "hs_checked_date", "hs_expiry_date")
    }


# ═════════════════════════════════════════════════════════════════════
# Managers
# ═════════════════════════════════════════════════════════════════════

def _managers(gui, employer_id: int) -> None:
    """The named contacts who sign for this employer."""
    frame = gui.clear()
    summary = _load(gui, employer_id)
    name = summary.name if summary else f"Employer {employer_id}"
    widgets.heading(
        frame, f"{name} — contacts",
        subtitle="A contact's username is what links an employer login to this "
                 "organisation, and deactivating them revokes that access.",
    )
    _back(gui, frame)

    table = widgets.DataTable(
        frame,
        (
            ("name", "Contact", 200),
            ("role", "Role", 160),
            ("title", "Job title", 180),
            ("email", "Email", 220),
            ("phone", "Phone", 120),
            ("username", "Login", 120),
            ("primary", "Signatory", 90),
            ("active", "Active", 80),
        ),
        height=14,
    )
    _, rows = widgets.guard(lambda: employer_service.list_managers(gui.actor, employer_id))
    rows = rows or []
    table.populate(
        rows,
        lambda m: (
            m.full_name, m.contact_role, m.job_title, m.email, m.phone, m.username,
            m.is_primary, m.active,
        ),
        identity=lambda m: m.manager_id,
        noun="contact",
    )
    if not rows:
        widgets.empty_state(
            frame,
            "No contacts are recorded. Without one there is nobody to sign the "
            "commitment statement or the progress reviews.",
        )

    if not gui.actor.can("employer.manage"):
        return

    def add() -> None:
        def save(values: dict[str, Any]) -> None:
            employer_service.add_manager(gui.actor, employer_id, _manager_payload(values))

        if widgets.FormDialog(gui.root, "Add contact", _manager_fields(None), save).saved:
            _managers(gui, employer_id)

    def edit() -> None:
        manager_id = table.require_selection_int("edit a contact")
        if manager_id is None:
            return
        existing = next((m for m in rows if m.manager_id == manager_id), None)

        def save(values: dict[str, Any]) -> None:
            employer_service.update_manager(gui.actor, manager_id, _manager_payload(values))

        if widgets.FormDialog(gui.root, "Edit contact", _manager_fields(existing), save).saved:
            _managers(gui, employer_id)

    def deactivate() -> None:
        manager_id = table.require_selection_int("deactivate a contact")
        if manager_id is None:
            return
        if not widgets.confirm(
            "Retire this contact?\n\nTheir login will stop resolving to this "
            "employer, so this is also how employer portal access is revoked.",
            title="Deactivate contact",
        ):
            return
        ok_off, _ = widgets.guard(
            lambda: employer_service.deactivate_manager(gui.actor, manager_id)
        )
        if ok_off:
            _managers(gui, employer_id)

    widgets.button_bar(frame, [("Add", add), ("Edit", edit), ("Deactivate", deactivate)])


def _manager_fields(manager: Any) -> list[dict[str, Any]]:
    return [
        {"key": "full_name", "label": "Contact name", "required": True,
         "value": getattr(manager, "full_name", "")},
        {"key": "contact_role", "label": "Role", "kind": "combo",
         "options": ("", *config.EMPLOYER_CONTACT_ROLES),
         "value": getattr(manager, "contact_role", "") or ""},
        {"key": "job_title", "label": "Job title",
         "value": getattr(manager, "job_title", "")},
        {"key": "email", "label": "Email", "value": getattr(manager, "email", "")},
        {"key": "phone", "label": "Phone", "value": getattr(manager, "phone", "")},
        {"key": "username", "label": "Login username",
         "value": getattr(manager, "username", ""),
         "help": "Links this contact to an employer portal login."},
    ]


def _manager_payload(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: values.get(key, "")
        for key in ("full_name", "contact_role", "job_title", "email", "phone", "username")
    }


# ═════════════════════════════════════════════════════════════════════
# Levy
# ═════════════════════════════════════════════════════════════════════

def _levy(gui, employer_id: int) -> None:
    """What the apprenticeship levy costs this employer for the year."""
    frame = gui.clear()
    summary = _load(gui, employer_id)
    name = summary.name if summary else f"Employer {employer_id}"
    widgets.heading(
        frame, f"{name} — levy position",
        subtitle="Half a percent of the pay bill, less the annual allowance. The "
                 "allowance is why the levy only bites above the threshold.",
    )
    _back(gui, frame)

    ok, position = widgets.guard(
        lambda: employer_service.funding_position(gui.actor, employer_id)
    )
    if not ok or position is None:
        widgets.empty_state(frame, "The levy position could not be worked out.")
        return

    widgets.field_grid(
        frame,
        (
            ("Annual pay bill", widgets.money(position.paybill)),
            ("Levy due for the year", widgets.money(position.levy_due)),
            ("Per month", widgets.money(position.monthly_levy)),
            ("Allowance used", widgets.money(position.allowance_used)),
            ("Levy payer", position.is_levy_payer),
            ("Funding route", "Levy" if position.is_levy_payer else "Co-investment"),
        ),
        columns=3,
    )
    if not position.is_levy_payer:
        widgets.empty_state(
            frame,
            "Below the threshold, so this employer co-invests: the government pays "
            f"{config.CO_INVESTMENT_GOVERNMENT_SHARE:.0%} of each negotiated price and "
            "the employer is invoiced the rest.",
        )
