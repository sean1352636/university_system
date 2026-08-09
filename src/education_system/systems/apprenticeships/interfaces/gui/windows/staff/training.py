"""Training sessions the tutor delivers, and their registers."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.training import sessions as session_rules
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    programme_service,
    training_service,
)

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your login is not linked to a staff record. You can still see the timetable, but "
    "\"Mine only\" and new sessions cannot be attributed to you until an administrator "
    "links your account to your staff profile."
)

COLUMNS = (
    ("when", "Date and time", 180),
    ("title", "Session", 220),
    ("programme", "Programme", 190),
    ("mode", "Mode", 130),
    ("location", "Location", 150),
    ("hours", "Off-the-job", 90, "e"),
    ("attendees", "Marked", 70, "e"),
    ("capacity", "Capacity", 80, "e"),
    ("status", "Status", 100),
)

REGISTER_COLUMNS = (
    ("apprentice", "Apprentice", 220),
    ("mark", "Mark", 110),
    ("hours", "Off-the-job hours", 130, "e"),
    ("notes", "Notes", 380),
)


def render(gui) -> None:
    """The training timetable, with scheduling and register marking."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "Training Sessions",
        subtitle="Scheduled delivery. Marking a register is also how attendance "
                 "becomes off-the-job hours.",
    )
    if gui.actor.staff_id is None:
        widgets.empty_state(frame, UNLINKED)

    can_manage = gui.actor.can("training.manage")
    body = ttk.Frame(frame)

    def reload() -> None:
        for child in body.winfo_children():
            child.destroy()
        filters = bar.values()
        # A check box cannot carry an id, so "Mine only" is translated
        # into the trainer filter the service actually takes.
        if filters.pop("mine_only", False):
            filters["trainer_id"] = gui.actor.staff_id
        rows = training_service.list_sessions(gui.actor, **filters)

        new_button = [("New Session…", lambda: _session_form(gui, None))] if can_manage else []
        if not rows:
            widgets.empty_state(
                body,
                "No sessions match these filters. Clear them to see the whole "
                "timetable, or schedule one.",
            )
            widgets.button_bar(body, new_button)
            return

        table = widgets.DataTable(
            body, COLUMNS,
            on_activate=lambda ident: _register(gui, int(ident)),
        )
        table.populate(
            rows,
            lambda s: (
                s.when, s.title, s.programme_title, s.delivery_mode, s.location,
                s.otj_hours, s.attendee_count, s.capacity, s.status,
            ),
            identity=lambda s: s.session_id,
            noun="session",
        )
        _actions(gui, body, table, new_button, can_manage=can_manage)

    bar = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", session_rules.SESSION_STATUSES),
            ("upcoming_only", "Upcoming only", "check"),
            ("mine_only", "Mine only", "check"),
        ),
        reload,
    )
    body.pack(fill="both", expand=True)
    reload()


def _actions(gui, parent, table: widgets.DataTable, new_button, *, can_manage: bool) -> None:
    """The buttons under the timetable."""

    def edit() -> None:
        chosen = table.require_selection_int("edit a session")
        if chosen is not None:
            _session_form(gui, chosen)

    def cancel() -> None:
        chosen = table.require_selection_int("cancel a session")
        if chosen is None:
            return
        reason = widgets.ask_reason(
            "Why is this session being called off?", title="Cancel session"
        )
        if reason is None:
            return
        ok, _ = widgets.guard(
            lambda: training_service.cancel_session(gui.actor, chosen, reason=reason)
        )
        if ok:
            gui.refresh()

    def delete() -> None:
        chosen = table.require_selection_int("delete a session")
        if chosen is None:
            return
        if not widgets.confirm(
            "Delete this session and its register?\n\nA session that ran and was called "
            "off should be cancelled instead — that keeps the record. Hours the register "
            "already generated survive either way.",
            title="Delete session",
        ):
            return
        reason = widgets.ask_reason("Why is it being deleted?", title="Delete session")
        if reason is None:
            return
        ok, _ = widgets.guard(
            lambda: training_service.delete_session(gui.actor, chosen, reason=reason)
        )
        if ok:
            gui.refresh()

    def register() -> None:
        chosen = table.require_selection_int("open a register")
        if chosen is not None:
            _register(gui, chosen)

    buttons = [*new_button]
    if can_manage:
        buttons += [("Edit…", edit), ("Cancel…", cancel), ("Delete", delete)]
    buttons.append(("Register…", register))
    widgets.button_bar(parent, buttons)


# ═════════════════════════════════════════════════════════════════════
# Sessions
# ═════════════════════════════════════════════════════════════════════

def _session_form(gui, session_id: int | None) -> None:
    """Create or edit a session in a modal form."""
    existing = None
    if session_id is not None:
        ok, existing = widgets.guard(lambda: training_service.get_session(gui.actor, session_id))
        if not ok or existing is None:
            return

    programmes = programme_service.list_programmes(gui.actor, active_only=True)
    labels = {f"{p.programme_id} — {p.title}": p.programme_id for p in programmes}
    current = next(
        (
            label for label, pid in labels.items()
            if existing is not None and pid == existing.programme_id
        ),
        "",
    )

    fields = [
        {"key": "title", "label": "Session title", "required": True,
         "value": existing.title if existing else ""},
        {"key": "session_date", "label": "Date", "required": True, "kind": "date",
         "value": existing.session_date if existing else "",
         "help": "YYYY-MM-DD"},
        {"key": "start_time", "label": "Start time",
         "value": existing.start_time if existing else "", "help": "HH:MM"},
        {"key": "end_time", "label": "End time",
         "value": existing.end_time if existing else "", "help": "HH:MM"},
        {"key": "delivery_mode", "label": "Delivery mode", "kind": "combo",
         "options": session_rules.DELIVERY_MODES,
         "value": existing.delivery_mode if existing else "Classroom"},
        {"key": "location", "label": "Location",
         "value": existing.location if existing else ""},
        {"key": "programme", "label": "Programme", "kind": "combo",
         "options": ["", *labels], "value": current},
        {"key": "capacity", "label": "Capacity",
         "value": existing.capacity if existing else ""},
        {"key": "otj_hours", "label": "Off-the-job hours", "kind": "entry",
         "value": existing.otj_hours if existing else "",
         "help": "What a present apprentice earns from attending. Blank for none."},
        {"key": "ksb_codes", "label": "KSBs covered",
         "value": existing.ksb_codes if existing else "", "help": "e.g. K1, S4, B2"},
        {"key": "notes", "label": "Notes", "kind": "text",
         "value": existing.notes if existing else ""},
    ]

    def save(values: dict) -> object:
        payload = {k: v for k, v in values.items() if k != "programme"}
        payload["programme_id"] = labels.get(values["programme"])
        if session_id is None:
            # A tutor scheduling a session is almost always delivering it,
            # and there is no staff picker on this screen, so it is stamped
            # with their own record.
            payload["trainer_id"] = gui.actor.staff_id
            return training_service.create_session(gui.actor, payload)
        return training_service.update_session(gui.actor, session_id, payload)

    dialog = widgets.FormDialog(
        gui.root,
        "Edit session" if session_id is not None else "New training session",
        fields,
        save,
    )
    if dialog.saved:
        gui.refresh()


# ═════════════════════════════════════════════════════════════════════
# Registers
# ═════════════════════════════════════════════════════════════════════

def _register(gui, session_id: int) -> None:
    """One session's register, in place of the timetable."""
    frame = gui.clear()
    ok, session = widgets.guard(lambda: training_service.get_session(gui.actor, session_id))
    if not ok or session is None:
        widgets.button_bar(frame, [("← Back to sessions", lambda: render(gui))])
        return

    widgets.heading(
        frame, f"Register — {session.title}",
        subtitle=f"{session.when} · {session.delivery_mode} · worth "
                 f"{session.otj_hours:,.1f} off-the-job hours",
    )
    ok, marks = widgets.guard(lambda: training_service.get_register(gui.actor, session_id))
    marks = marks or []

    table: widgets.DataTable | None = None
    if marks:
        table = widgets.DataTable(frame, REGISTER_COLUMNS, height=16)
        table.populate(
            marks,
            lambda m: (m.apprentice_name, m.status, m.otj_hours, m.notes),
            identity=lambda m: m.apprentice_id,
            tag=lambda m: "Green" if m.earned_hours else None,
            noun="mark",
        )
    else:
        widgets.empty_state(
            frame,
            "Nobody has been marked yet. Marking an apprentice is also how they join "
            "this register.",
        )

    def mark() -> None:
        selected = table.selected_int() if table is not None else None
        _mark_form(gui, session, selected)

    buttons = [("← Back to sessions", lambda: render(gui))]
    if gui.actor.can("training.manage"):
        buttons.insert(0, ("Mark…", mark))
    widgets.button_bar(frame, buttons)


def _mark_form(gui, session, apprentice_id: int | None) -> None:
    """Mark one apprentice on a register.

    A Present or Late mark writes the hours it earned into the off-the-job
    log as already approved — the tutor marking the register is the same
    person who would sign the entry off — and re-marking corrects that
    entry rather than adding a second one.
    """
    people = apprentice_service.list_apprentices(gui.actor, active_only=True)
    if not people:
        widgets.warn(
            "There are no active apprentices on your caseload to mark.",
            title="Nothing to mark",
        )
        return

    labels = {f"{s.apprentice.apprentice_id} — {s.full_name}": s.apprentice.apprentice_id
              for s in people}
    current = next((label for label, aid in labels.items() if aid == apprentice_id), "")

    fields = [
        {"key": "apprentice", "label": "Apprentice", "kind": "combo", "required": True,
         "options": list(labels), "value": current},
        {"key": "status", "label": "Mark", "kind": "combo", "required": True,
         "options": session_rules.ATTENDANCE_STATUSES, "value": "Present"},
        {"key": "otj_hours", "label": "Off-the-job hours",
         "help": f"Blank uses the session default ({session.otj_hours:,.1f}h present, "
                 f"half that for late). An absence earns nothing either way."},
        {"key": "notes", "label": "Notes", "kind": "text"},
    ]

    def save(values: dict) -> object:
        chosen = labels.get(values["apprentice"])
        if chosen is None:
            raise ValueError("Choose an apprentice to mark")
        return training_service.mark_attendance(
            gui.actor, session.session_id, chosen,
            status=values["status"],
            otj_hours=_hours_or_none(values["otj_hours"]),
            notes=values["notes"],
        )

    dialog = widgets.FormDialog(gui.root, "Mark register", fields, save)
    if dialog.saved:
        # Not gui.refresh(): that re-renders the timetable and drops the
        # tutor out of the register they are part-way through marking.
        _register(gui, session.session_id)


def _hours_or_none(text: str) -> float | None:
    """An hours override, or None to take the session's default."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError("Off-the-job hours must be a number") from exc
