"""The standards catalogue, and the KSBs and duties that make each one up."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.programmes import versions
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.programmes import programme_service

# Apprentices whose plan is closed; the curriculum is not applied to them.
_FINISHED = ("Completed", "Withdrawn", "Transferred")

logger = logging.getLogger(__name__)

_SUBTITLE = (
    "Everything else is judged against these. Portfolio evidence maps to a "
    "standard's KSBs and the EPAO assesses against its named methods, so a "
    "standard is only publishable once both are in place."
)

_COLUMNS = (
    ("reference", "Reference", 100),
    ("version", "Version", 60),
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
                p.reference, p.version, p.title, p.level, p.funding_band, p.duration_months,
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
        buttons.append(("New version…", lambda: _new_version(gui, table)))
    buttons.append(("KSBs…", lambda: _open_sub(gui, table, _ksbs)))
    buttons.append(("Duties…", lambda: _open_sub(gui, table, _duties)))
    buttons.append(("Curriculum…", lambda: _open_sub(gui, table, _curriculum)))
    buttons.append(("Versions…", lambda: _open_sub(gui, table, _versions)))
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


# ═════════════════════════════════════════════════════════════════════
# Versions
# ═════════════════════════════════════════════════════════════════════

def _new_version(gui, table: widgets.DataTable) -> None:
    programme_id = table.require_selection_int("revise a standard")
    if programme_id is None:
        return
    programme = _load(gui, programme_id)
    if programme is None:
        return

    def save(values: dict[str, Any]) -> object:
        return programme_service.new_version(
            gui.actor, programme_id,
            version=values.get("version") or None, reason=values.get("reason") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, f"New version of {programme.reference}",
        [
            {"key": "version", "label": "New version", "required": True,
             "value": versions.next_version(programme.version),
             "help": f"Must come after {programme.version}."},
            {"key": "reason", "label": "What changed", "kind": "text"},
        ],
        save,
        intro=f"The KSBs, duties and curriculum of v{programme.version} are copied to the "
              f"new version. v{programme.version} becomes Superseded: apprentices already "
              "on it stay on it, and new starts go onto the new version.",
        save_label="Create version",
    )
    if dialog.saved:
        _versions(gui, dialog.result.programme_id)


def _versions(gui, programme_id: int) -> None:
    """Every version of one standard, with how many apprentices are on each."""
    frame = gui.clear()
    programme = _load(gui, programme_id)
    reference = programme.reference if programme else "Standard"
    widgets.heading(
        frame, f"{reference}: version history",
        subtitle="Each version is its own record. Apprentices finish on the version they "
                 "started; only the active one takes new starts.",
    )
    _back(gui, frame)
    ok, history = widgets.guard(lambda: programme_service.version_history(gui.actor, programme_id))
    if not ok:
        return
    table = widgets.DataTable(
        frame,
        (
            ("version", "Version", 80),
            ("title", "Title", 280),
            ("status", "Status", 110),
            ("apprentices", "Apprentices", 100, "e"),
            ("created", "Created", 160),
            ("updated", "Last changed", 160),
        ),
        height=10,
    )
    table.populate(
        history,
        lambda h: (h.programme.version, h.programme.title, h.programme.status,
                   h.apprentices, h.programme.created_at, h.programme.updated_at),
        identity=lambda h: h.programme.programme_id,
        tag=lambda h: "Green" if h.is_current else None,
        noun="version",
    )


# ═════════════════════════════════════════════════════════════════════
# Curriculum
# ═════════════════════════════════════════════════════════════════════

def _curriculum(gui, programme_id: int) -> None:
    """The modules a standard is delivered through, stage by stage."""
    frame = gui.clear()
    programme = _load(gui, programme_id)
    title = (f"{programme.reference} v{programme.version} — {programme.title}"
             if programme else "Standard")
    widgets.heading(
        frame, f"{title}: curriculum",
        subtitle="Applying the curriculum puts one objective per module on an apprentice's "
                 "learning plan, and an activity for any module with planned hours. It only "
                 "ever adds what is not there yet.",
    )
    _back(gui, frame)

    _, modules = widgets.guard(lambda: programme_service.list_modules(gui.actor, programme_id))
    rows = modules or []
    table = widgets.DataTable(
        frame,
        (
            ("stage", "Stage", 100),
            ("position", "#", 40, "e"),
            ("title", "Module", 280),
            ("ksbs", "KSBs", 150),
            ("hours", "Planned hours", 100, "e"),
            ("description", "Description", 320),
        ),
        height=14,
    )

    def reload() -> None:
        _curriculum(gui, programme_id)

    def selected(action: str):
        ident = table.require_selection_int(action)
        return next((m for m in rows if m.module_id == ident), None)

    def add() -> None:
        def save(values: dict[str, Any]) -> object:
            return programme_service.add_module(gui.actor, programme_id, _module_payload(values))

        if widgets.FormDialog(gui.root, "Add module", _module_fields(None), save).saved:
            reload()

    def edit() -> None:
        module = selected("edit a module")
        if module is None:
            return

        def save(values: dict[str, Any]) -> object:
            return programme_service.update_module(
                gui.actor, module.module_id, _module_payload(values)
            )

        if widgets.FormDialog(gui.root, "Edit module", _module_fields(module), save).saved:
            reload()

    def remove() -> None:
        module = selected("delete a module")
        if module is None or not widgets.confirm(
            f"Delete “{module.title}”?\n\nPlans it was already applied to keep their "
            "objective.", title="Delete module",
        ):
            return
        ok, _ = widgets.guard(lambda: programme_service.delete_module(gui.actor, module.module_id))
        if ok:
            reload()

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("programme.manage"):
        buttons += [("Add", add), ("Edit", edit), ("Delete", remove)]
    if gui.actor.can("training.manage"):
        buttons += [
            ("Apply to an apprentice…", lambda: _apply_to_one(gui, programme_id)),
            ("Apply to everyone on it", lambda: _apply_to_all(gui, programme_id)),
        ]
    if buttons:
        widgets.button_bar(frame, buttons)

    table.populate(
        rows,
        lambda m: (m.stage, m.position, m.title, m.ksb_codes, m.planned_hours, m.description),
        identity=lambda m: m.module_id,
        noun="module",
    )
    if not rows:
        widgets.empty_state(
            frame,
            "No modules yet. Add the modules the standard is taught through, stage by stage, "
            "so each apprentice's plan can start from them.",
        )


def _module_fields(module: Any) -> list[dict[str, Any]]:
    def current(attr: str, default: Any = "") -> Any:
        value = getattr(module, attr, None) if module is not None else None
        return default if value is None else value

    return [
        {"key": "title", "label": "Module", "required": True, "value": current("title")},
        {"key": "stage", "label": "Stage", "required": True,
         "value": current("stage", "Year 1"), "help": "For example Year 1, or Foundation."},
        {"key": "position", "label": "Position", "value": current("position"),
         "help": "Order within the curriculum. Blank puts it last."},
        {"key": "ksb_codes", "label": "KSBs", "value": current("ksb_codes"),
         "help": "Codes from this standard, e.g. K1, S3, B2."},
        {"key": "planned_hours", "label": "Planned off-the-job hours",
         "value": str(current("planned_hours", 0))},
        {"key": "description", "label": "Description", "kind": "text",
         "value": current("description")},
    ]


def _module_payload(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: values.get(key, "")
        for key in ("title", "stage", "position", "ksb_codes", "planned_hours", "description")
    }


def _apply_to_one(gui, programme_id: int) -> None:
    ok, people = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor, programme_id=programme_id)
    )
    choices = {
        f"{s.full_name} ({s.apprentice.status})": s.apprentice.apprentice_id
        for s in (people or []) if s.apprentice.status not in _FINISHED
    } if ok else {}
    if not choices:
        widgets.inform("Nobody you can plan for is on this programme.", title="No apprentices")
        return

    def save(values: dict[str, Any]) -> object:
        apprentice_id = choices.get(values.get("apprentice") or "")
        if apprentice_id is None:
            from education_system.systems.apprenticeships.domain.apprentices.models import (
                ValidationError,
            )
            raise ValidationError("Choose an apprentice")
        return programme_service.apply_curriculum(gui.actor, apprentice_id)

    dialog = widgets.FormDialog(
        gui.root, "Apply curriculum",
        [{"key": "apprentice", "label": "Apprentice", "kind": "combo", "required": True,
          "options": tuple(choices)}],
        save, save_label="Apply",
    )
    if dialog.saved:
        widgets.inform(f"Learning plan updated: {dialog.result.summary}.")


def _apply_to_all(gui, programme_id: int) -> None:
    if not widgets.confirm(
        "Apply the curriculum to every apprentice on this programme that you plan for?\n\n"
        "Modules already on a plan are left alone, so this only adds what is new."
    ):
        return
    ok, results = widgets.guard(
        lambda: programme_service.apply_curriculum_to_cohort(gui.actor, programme_id)
    )
    if ok:
        added = sum(len(r.created) for r in results)
        widgets.inform(
            f"{len(results)} learning plan(s) checked; {added} objective(s) added."
        )
