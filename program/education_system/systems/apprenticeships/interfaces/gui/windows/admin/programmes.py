"""The standards catalogue, and the KSBs and duties that make each one up."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    programme_service,
)

logger = logging.getLogger(__name__)

_SUBTITLE = (
    "Everything else is judged against these. Portfolio evidence maps to a "
    "standard's KSBs and the EPAO assesses against its named methods, so a "
    "standard is only publishable once both are in place."
)

_COLUMNS = (
    ("reference", "Reference", 100),
    ("title", "Title", 240),
    ("level", "Level", 60, "e"),
    ("band", "Band", 60, "e"),
    ("duration", "Months", 70, "e"),
    ("epa", "EPA methods", 260),
    ("status", "Status", 90),
    ("count", "Apprentices", 90, "e"),
)


def render(gui) -> None:
    """The standards catalogue, with the actions that publish and close one."""
    frame = gui.clear()
    widgets.heading(frame, "Programmes & KSBs", subtitle=_SUBTITLE)

    filters = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.PROGRAMME_STATUSES),
            ("level", "Level", "combo", config.PROGRAMME_LEVELS),
            ("search", "Search", "entry"),
            ("active_only", "Active only", "check"),
        ),
        lambda: reload(),
    )
    table = widgets.DataTable(frame, _COLUMNS)
    hint = widgets.empty_state(frame, "")

    def reload() -> None:
        chosen = filters.values()
        if "level" in chosen:
            chosen["level"] = int(chosen["level"])
        _, rows = widgets.guard(
            lambda: programme_service.list_programmes(gui.actor, **chosen)
        )
        rows = rows or []
        enrolled = _enrolment_counts(gui)
        table.populate(
            rows,
            lambda p: (
                p.reference, p.title, p.level, p.funding_band, p.duration_months,
                ", ".join(p.epa_methods), p.status,
                enrolled.get(p.programme_id, 0),
            ),
            identity=lambda p: p.programme_id,
            noun="standard",
        )
        hint.config(
            text="" if rows else
            "No standard matches these filters. Clear them to see the whole "
            "catalogue, or use New to add one.",
        )

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("programme.manage"):
        buttons.append(("New", lambda: _create(gui)))
        buttons.append(("Edit", lambda: _edit(gui, table)))
        buttons.append(("Activate", lambda: _activate(gui, table)))
        buttons.append(("Withdraw", lambda: _withdraw(gui, table)))
    buttons.append(("KSBs…", lambda: _open_sub(gui, table, _ksbs)))
    buttons.append(("Duties…", lambda: _open_sub(gui, table, _duties)))
    if gui.actor.is_admin:
        buttons.append(("Delete", lambda: _delete(gui, table)))
    widgets.button_bar(frame, buttons)

    reload()


def _enrolment_counts(gui) -> dict[int, int]:
    """How many apprentices sit on each standard.

    Tallied from the cohort the actor may already see rather than asked of
    the repository, so the count obeys the same scoping as every other read
    on this screen.
    """
    _, cohort = widgets.guard(lambda: apprentice_service.list_apprentices(gui.actor))
    counts: dict[int, int] = {}
    for summary in cohort or []:
        key = summary.apprentice.programme_id
        if key is not None:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _open_sub(gui, table: widgets.DataTable, screen) -> None:
    programme_id = table.require_selection_int("open that")
    if programme_id is not None:
        screen(gui, programme_id)


def _back(gui, parent) -> None:
    widgets.button_bar(parent, [("← Back to catalogue", lambda: render(gui))])


def _load(gui, programme_id: int):
    ok, programme = widgets.guard(
        lambda: programme_service.get_programme(gui.actor, programme_id)
    )
    return programme if ok else None


# ═════════════════════════════════════════════════════════════════════
# The standard
# ═════════════════════════════════════════════════════════════════════

def _create(gui) -> None:
    def save(values: dict[str, Any]) -> None:
        programme_service.create_programme(gui.actor, _payload(values))

    dialog = widgets.FormDialog(
        gui.root, "Add standard", _fields(None), save,
        intro="New standards start as a draft. Add the KSBs and at least one EPA "
              "method, then activate it to open it for enrolment. EPA methods: "
              + ", ".join(config.EPA_METHODS) + ".",
    )
    if dialog.saved:
        gui.refresh()


def _edit(gui, table: widgets.DataTable) -> None:
    programme_id = table.require_selection_int("edit a standard")
    if programme_id is None:
        return
    programme = _load(gui, programme_id)
    if programme is None:
        return

    def save(values: dict[str, Any]) -> None:
        programme_service.update_programme(gui.actor, programme_id, _payload(values))

    dialog = widgets.FormDialog(
        gui.root, f"Edit {programme.reference}", _fields(programme), save,
        intro="Status moves through Activate and Withdraw, which check the "
              "conditions each transition depends on. EPA methods: "
              + ", ".join(config.EPA_METHODS) + ".",
    )
    if dialog.saved:
        gui.refresh()


def _fields(programme: Any) -> list[dict[str, Any]]:
    return [
        {"key": "reference", "label": "Reference", "required": True,
         "value": getattr(programme, "reference", ""), "help": "For example ST0119."},
        {"key": "title", "label": "Title", "required": True,
         "value": getattr(programme, "title", "")},
        {"key": "level", "label": "Level", "kind": "combo", "required": True,
         "options": config.PROGRAMME_LEVELS,
         "value": getattr(programme, "level", "")},
        {"key": "funding_band", "label": "Funding band", "kind": "combo",
         "required": True, "options": sorted(config.FUNDING_BANDS),
         "value": getattr(programme, "funding_band", ""),
         "help": "The band caps what may be negotiated for this standard."},
        {"key": "duration_months", "label": "Duration (months)", "required": True,
         "value": getattr(programme, "duration_months", "")},
        {"key": "epa_methods", "label": "EPA methods", "kind": "text",
         "value": ", ".join(getattr(programme, "epa_methods", []) or []),
         "help": "Comma-separated, from the published methods listed above."},
        {"key": "sector", "label": "Sector", "value": getattr(programme, "sector", "")},
        {"key": "description", "label": "Description", "kind": "text",
         "value": getattr(programme, "description", "")},
    ]


def _payload(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: values.get(key, "")
        for key in (
            "reference", "title", "level", "funding_band", "duration_months",
            "epa_methods", "sector", "description",
        )
    }


def _activate(gui, table: widgets.DataTable) -> None:
    programme_id = table.require_selection_int("activate a standard")
    if programme_id is None:
        return
    ok, _ = widgets.guard(
        lambda: programme_service.activate_programme(gui.actor, programme_id)
    )
    if ok:
        gui.refresh()


def _withdraw(gui, table: widgets.DataTable) -> None:
    programme_id = table.require_selection_int("withdraw a standard")
    if programme_id is None:
        return
    if not widgets.confirm(
        "Close this standard to new enrolments?",
        title="Withdraw standard",
    ):
        return
    reason = widgets.ask_reason("Why is this standard being withdrawn?")
    if reason is None:
        return
    ok, _ = widgets.guard(
        lambda: programme_service.withdraw_programme(gui.actor, programme_id, reason=reason)
    )
    if ok:
        gui.refresh()


def _delete(gui, table: widgets.DataTable) -> None:
    programme_id = table.require_selection_int("delete a standard")
    if programme_id is None:
        return
    if not widgets.confirm(
        "Delete this standard along with its KSBs and duties?\n\n"
        "One the provider has stopped delivering should be withdrawn instead — "
        "that keeps the record the funding audit reads.",
        title="Delete standard",
    ):
        return
    reason = widgets.ask_reason("Why is this standard being deleted?")
    if reason is None:
        return
    ok, _ = widgets.guard(
        lambda: programme_service.delete_programme(gui.actor, programme_id, reason=reason)
    )
    if ok:
        gui.refresh()


# ═════════════════════════════════════════════════════════════════════
# KSBs
# ═════════════════════════════════════════════════════════════════════

def _ksbs(gui, programme_id: int) -> None:
    """The knowledge, skill and behaviour statements within one standard."""
    frame = gui.clear()
    programme = _load(gui, programme_id)
    title = f"{programme.reference} — {programme.title}" if programme else "Standard"
    widgets.heading(
        frame, f"{title}: KSBs",
        subtitle="Portfolio evidence maps to these, and gateway requires every one "
                 "of them covered.",
    )
    _back(gui, frame)

    _, breakdown = widgets.guard(
        lambda: programme_service.ksb_breakdown(gui.actor, programme_id)
    )
    if breakdown:
        widgets.field_grid(
            frame,
            [(ksb_type, count) for ksb_type, count in breakdown.items()],
            columns=3,
        )

    table = widgets.DataTable(
        frame,
        (
            ("code", "Code", 80),
            ("type", "Type", 110),
            ("description", "Statement", 520),
            ("duty", "Duty", 90),
        ),
        height=14,
    )
    _, rows = widgets.guard(lambda: programme_service.list_ksbs(gui.actor, programme_id))
    rows = sorted(rows or [], key=lambda k: k.sort_key)
    table.populate(
        rows,
        lambda k: (k.code, k.ksb_type, k.description, k.duty_ref),
        identity=lambda k: k.ksb_id,
        noun="statement",
    )
    if not rows:
        widgets.empty_state(
            frame,
            "This standard has no KSBs yet, so it cannot be activated — there would "
            "be nothing for portfolio evidence to map to.",
        )

    if not gui.actor.can("programme.manage"):
        return

    _, duties = widgets.guard(lambda: programme_service.list_duties(gui.actor, programme_id))
    duty_codes = ("", *[d.code for d in (duties or [])])

    def add() -> None:
        def save(values: dict[str, Any]) -> None:
            programme_service.add_ksb(gui.actor, programme_id, _ksb_payload(values))

        if widgets.FormDialog(
            gui.root, "Add KSB", _ksb_fields(None, duty_codes), save
        ).saved:
            _ksbs(gui, programme_id)

    def edit() -> None:
        ksb_id = table.require_selection_int("edit a statement")
        if ksb_id is None:
            return
        existing = next((k for k in rows if k.ksb_id == ksb_id), None)

        def save(values: dict[str, Any]) -> None:
            programme_service.update_ksb(gui.actor, ksb_id, _ksb_payload(values))

        if widgets.FormDialog(
            gui.root, "Edit KSB", _ksb_fields(existing, duty_codes), save
        ).saved:
            _ksbs(gui, programme_id)

    def remove() -> None:
        ksb_id = table.require_selection_int("delete a statement")
        if ksb_id is None:
            return
        if not widgets.confirm(
            "Delete this KSB?\n\nEvidence already mapped to it survives, having "
            "simply lost one of the things it covered.",
            title="Delete KSB",
        ):
            return
        reason = widgets.ask_reason("Why is this KSB being removed?")
        if reason is None:
            return
        ok, _ = widgets.guard(
            lambda: programme_service.delete_ksb(gui.actor, ksb_id, reason=reason)
        )
        if ok:
            _ksbs(gui, programme_id)

    widgets.button_bar(frame, [("Add", add), ("Edit", edit), ("Delete", remove)])


def _ksb_fields(ksb: Any, duty_codes: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {"key": "code", "label": "Code", "required": True,
         "value": getattr(ksb, "code", ""),
         "help": "K, S or B followed by a number. The letter decides the type."},
        {"key": "description", "label": "Statement", "kind": "text", "required": True,
         "value": getattr(ksb, "description", "")},
        {"key": "duty_ref", "label": "Duty", "kind": "combo", "options": duty_codes,
         "value": getattr(ksb, "duty_ref", "") or ""},
    ]


def _ksb_payload(values: dict[str, Any]) -> dict[str, Any]:
    return {key: values.get(key, "") for key in ("code", "description", "duty_ref")}


# ═════════════════════════════════════════════════════════════════════
# Occupational duties
# ═════════════════════════════════════════════════════════════════════

def _duties(gui, programme_id: int) -> None:
    """The occupational duties a standard's KSBs are grouped under."""
    frame = gui.clear()
    programme = _load(gui, programme_id)
    title = f"{programme.reference} — {programme.title}" if programme else "Standard"
    widgets.heading(
        frame, f"{title}: occupational duties",
        subtitle="Duties are what the job actually involves; each KSB is filed "
                 "under one of them.",
    )
    _back(gui, frame)

    table = widgets.DataTable(
        frame,
        (("code", "Code", 90), ("description", "Duty", 640)),
        height=14,
    )
    _, rows = widgets.guard(lambda: programme_service.list_duties(gui.actor, programme_id))
    rows = rows or []
    table.populate(
        rows,
        lambda d: (d.code, d.description),
        identity=lambda d: d.duty_id,
        noun="duty",
    )
    if not rows:
        widgets.empty_state(
            frame,
            "No duties are recorded. They are optional, but without them a KSB "
            "cannot be filed under the part of the job it belongs to.",
        )

    if not gui.actor.can("programme.manage"):
        return

    def add() -> None:
        def save(values: dict[str, Any]) -> None:
            programme_service.add_duty(gui.actor, programme_id, _duty_payload(values))

        if widgets.FormDialog(gui.root, "Add duty", _duty_fields(None), save).saved:
            _duties(gui, programme_id)

    def edit() -> None:
        duty_id = table.require_selection_int("edit a duty")
        if duty_id is None:
            return
        existing = next((d for d in rows if d.duty_id == duty_id), None)

        def save(values: dict[str, Any]) -> None:
            programme_service.update_duty(gui.actor, duty_id, _duty_payload(values))

        if widgets.FormDialog(gui.root, "Edit duty", _duty_fields(existing), save).saved:
            _duties(gui, programme_id)

    def remove() -> None:
        duty_id = table.require_selection_int("delete a duty")
        if duty_id is None:
            return
        if not widgets.confirm(
            "Delete this duty?\n\nKSBs that reference it keep the text they were "
            "given — the reference is a label, not a foreign key.",
            title="Delete duty",
        ):
            return
        ok, _ = widgets.guard(lambda: programme_service.delete_duty(gui.actor, duty_id))
        if ok:
            _duties(gui, programme_id)

    widgets.button_bar(frame, [("Add", add), ("Edit", edit), ("Delete", remove)])


def _duty_fields(duty: Any) -> list[dict[str, Any]]:
    return [
        {"key": "code", "label": "Code", "required": True,
         "value": getattr(duty, "code", ""), "help": "For example D1."},
        {"key": "description", "label": "Duty", "kind": "text", "required": True,
         "value": getattr(duty, "description", "")},
    ]


def _duty_payload(values: dict[str, Any]) -> dict[str, Any]:
    return {key: values.get(key, "") for key in ("code", "description")}
