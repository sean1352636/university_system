"""Assignments: work set by the provider, submitted, marked and moderated.

One screen, two shapes. The apprentice sees their own assignments and
hands work in. Provider staff open on the two piles that need them —
work waiting to be marked, and marked work waiting for a second opinion —
with the full list behind them. The moderation pile leaves out anything
the signed-in user marked themselves, because nobody moderates their own
marking; the service refuses it anyway.

Not to be confused with ``staff.assessments``, which is the off-the-job
hours approval queue.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.progress.assignments import Assignment
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.assessments import portfolio_service
from education_system.systems.apprenticeships.application.learning import assignment_service

logger = logging.getLogger(__name__)

TITLE = "Assignments"
SUBTITLE = (
    "Work set by the provider. A Refer goes back for another attempt, up to the limit "
    "the assignment allows; late work is accepted and flagged."
)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there are no assignments "
    "to show. Ask your training provider's administrator to link your account."
)

OWN_COLUMNS = (
    ("title", "Assignment", 280),
    ("type", "Type", 170),
    ("due", "Due", 100),
    ("status", "Status", 110),
    ("attempt", "Attempt", 80),
    ("grade", "Grade", 100),
    ("late", "Late", 60),
)

PROVIDER_COLUMNS = (
    ("apprentice", "Apprentice", 170),
    ("title", "Assignment", 250),
    ("type", "Type", 160),
    ("due", "Due", 100),
    ("status", "Status", 110),
    ("attempt", "Attempt", 80),
    ("grade", "Grade", 90),
    ("marker", "Marked by", 120),
    ("late", "Late", 60),
)

SUBMISSION_COLUMNS = (
    ("attempt", "Attempt", 70, "e"),
    ("when", "Submitted", 150),
    ("late", "Late", 60),
    ("evidence", "Portfolio evidence", 200),
    ("grade", "Grade", 90),
    ("marker", "Marked by", 120),
    ("feedback", "Feedback", 360),
)

MODERATION_COLUMNS = (
    ("attempt", "Attempt", 70, "e"),
    ("when", "Moderated", 150),
    ("moderator", "Moderator", 130),
    ("outcome", "Outcome", 90),
    ("grades", "Grade", 160),
    ("notes", "Notes", 380),
)


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)
    if not gui.actor.can("assignment.view"):
        widgets.empty_state(
            frame,
            "Assignments are the training provider's own assessments, and your role "
            "does not see them.",
        )
        return
    if gui.actor.role == config.APPRENTICE:
        if gui.actor.apprentice_id is None:
            widgets.empty_state(frame, UNLINKED)
            return
        _own(gui, frame)
        return
    _provider(gui, frame)


# ═════════════════════════════════════════════════════════════════════
# The apprentice's view
# ═════════════════════════════════════════════════════════════════════

def _own(gui: Any, frame: Any) -> None:
    ok, rows = widgets.guard(
        lambda: assignment_service.list_assignments(gui.actor, with_children=True)
    )
    if not ok:
        return
    rows = rows or []
    today = date.today()
    widgets.kpi_row(frame, [
        ("To do", sum(1 for a in rows if a.is_with_apprentice)),
        ("Overdue", sum(1 for a in rows if a.is_overdue(today))),
        ("Waiting to be marked", sum(1 for a in rows if a.status == "Submitted")),
        ("Passed", sum(1 for a in rows if a.is_passed)),
    ])
    by_id = {a.assignment_id: a for a in rows}

    def chosen(action: str) -> Assignment | None:
        ident = table.require_selection_int(action)
        return by_id.get(ident) if ident is not None else None

    def open_one() -> None:
        item = chosen("open an assignment")
        if item is not None:
            _detail(gui, item.assignment_id)

    def submit() -> None:
        item = chosen("hand in work")
        if item is not None:
            _submit_form(gui, item, lambda: render(gui))

    buttons: list[tuple[str, Callable[[], None]]] = [("Open", open_one)]
    if gui.actor.can("assignment.submit"):
        buttons.append(("Submit work…", submit))
    widgets.button_bar(frame, buttons)
    table = widgets.DataTable(
        frame, OWN_COLUMNS, on_activate=lambda ident: _detail(gui, int(ident))
    )
    table.populate(
        rows,
        lambda a: (a.title, a.assignment_type, a.due_date, a.status, _attempt(a), a.grade,
                   a.is_late),
        identity=lambda a: a.assignment_id,
        tag=lambda a: a.rag(today),
        noun="assignment",
    )
    if not rows:
        widgets.empty_state(frame, "Nothing has been set for you yet.")


# ═════════════════════════════════════════════════════════════════════
# The provider's view
# ═════════════════════════════════════════════════════════════════════

def _provider(gui: Any, frame: Any) -> None:
    actor = gui.actor
    ok, summary = widgets.guard(lambda: assignment_service.assignment_summary(actor))
    if ok and summary is not None:
        widgets.kpi_row(frame, [
            ("With apprentices", summary["with_apprentice"]),
            ("Overdue", summary["overdue"]),
            ("To mark", summary["to_mark"]),
            ("To moderate", summary["to_moderate"]),
            ("Passed", summary["passed"]),
        ])

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)
    if actor.can("assignment.set"):
        _, to_mark = widgets.guard(lambda: assignment_service.marking_queue(actor))
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text=f"To mark ({len(to_mark or [])})")
        _queue(gui, tab, to_mark or [], "Submitted work waiting on a marker.")
    if actor.can("assignment.moderate"):
        _, to_moderate = widgets.guard(lambda: assignment_service.moderation_queue(actor))
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text=f"To moderate ({len(to_moderate or [])})")
        _queue(gui, tab, to_moderate or [],
               "Marked work not yet second-marked. Work you marked yourself is not "
               "listed: moderation needs a second person.")
    tab = ttk.Frame(notebook, padding=8)
    notebook.add(tab, text="All assignments")
    _all(gui, tab)


def _queue(gui: Any, parent: Any, rows: list[Assignment], blurb: str) -> None:
    ttk.Label(parent, text=blurb, foreground=config.MUTED_FG, wraplength=900,
              justify="left").pack(anchor="w", pady=(0, 8))
    table = _provider_table(gui, parent)
    _fill(table, rows)


def _all(gui: Any, parent: Any) -> None:
    filters = widgets.FilterBar(
        parent,
        (
            ("status", "Status", "combo", config.ASSIGNMENT_STATUSES),
            ("assignment_type", "Type", "combo", config.ASSIGNMENT_TYPES),
            ("overdue_only", "Overdue only", "check"),
            ("due_soon", f"Due within {config.ASSIGNMENT_DUE_SOON_DAYS} days", "check"),
        ),
        lambda: reload(),
    )
    table = _provider_table(gui, parent)

    def reload() -> None:
        values = filters.values()
        kwargs: dict[str, Any] = {
            "status": values.get("status"),
            "assignment_type": values.get("assignment_type"),
            "overdue_only": bool(values.get("overdue_only")),
        }
        if values.get("due_soon"):
            kwargs["due_within_days"] = config.ASSIGNMENT_DUE_SOON_DAYS
        ok, rows = widgets.guard(
            lambda: assignment_service.list_assignments(gui.actor, with_children=True, **kwargs)
        )
        _fill(table, (rows or []) if ok else [])

    reload()


def _provider_table(gui: Any, parent: Any) -> widgets.DataTable:
    """A provider list with its action bar, packed before the table expands."""
    holder: dict[str, widgets.DataTable] = {}

    def chosen(action: str) -> int | None:
        return holder["table"].require_selection_int(action)

    def run(action: str, handler: Callable[[int], None]) -> Callable[[], None]:
        def go() -> None:
            ident = chosen(action)
            if ident is not None:
                handler(ident)
        return go

    actor = gui.actor
    buttons: list[tuple[str, Callable[[], None]]] = [
        ("Open", run("open an assignment", lambda i: _detail(gui, i))),
    ]
    if actor.can("assignment.set"):
        buttons += [
            ("Set assignment…", lambda: _set_form(gui)),
            ("Mark…", run("mark an assignment", lambda i: _with(gui, i, _mark_form))),
        ]
    if actor.can("assignment.moderate"):
        buttons.append(
            ("Moderate…", run("moderate an assignment", lambda i: _with(gui, i, _moderate_form)))
        )
    widgets.button_bar(parent, buttons)
    table = widgets.DataTable(
        parent, PROVIDER_COLUMNS, on_activate=lambda ident: _detail(gui, int(ident))
    )
    holder["table"] = table
    return table


def _fill(table: widgets.DataTable, rows: list[Assignment]) -> None:
    today = date.today()
    table.populate(
        rows,
        lambda a: (a.apprentice_name, a.title, a.assignment_type, a.due_date, a.status,
                   _attempt(a), a.grade, a.marked_by, a.is_late),
        identity=lambda a: a.assignment_id,
        tag=lambda a: a.rag(today),
        noun="assignment",
    )


# ═════════════════════════════════════════════════════════════════════
# One assignment
# ═════════════════════════════════════════════════════════════════════

def _detail(gui: Any, assignment_id: int) -> None:
    frame = gui.clear()
    back = ("← All assignments", lambda: render(gui))
    ok, item = widgets.guard(lambda: assignment_service.get_assignment(gui.actor, assignment_id))
    if not ok or item is None:
        widgets.button_bar(frame, [back])
        return

    def reopen() -> None:
        _detail(gui, assignment_id)

    widgets.heading(
        frame, f"{item.title} — {item.apprentice_name}",
        subtitle=f"{item.assignment_type} · {item.status} · set by {item.set_by or '—'}",
    )
    actor = gui.actor
    buttons: list[tuple[str, Callable[[], None]]] = []
    if actor.can("assignment.submit") and item.is_with_apprentice:
        buttons.append(("Submit work…", lambda: _submit_form(gui, item, reopen)))
    if actor.can("assignment.set") and item.status == "Submitted":
        buttons.append(("Mark…", lambda: _mark_form(gui, item, reopen)))
    if (actor.can("assignment.moderate") and item.awaiting_moderation
            and (item.marked_by or "").casefold() != actor.username.casefold()):
        buttons.append(("Moderate…", lambda: _moderate_form(gui, item, reopen)))
    if actor.can("assignment.set") and item.is_with_apprentice:
        buttons += [
            ("Edit…", lambda: _edit_form(gui, item, reopen)),
            ("Withdraw…", lambda: _withdraw(gui, item, reopen)),
        ]
    buttons.append(back)
    widgets.button_bar(frame, buttons)

    body = widgets.scrollable(frame)
    widgets.field_grid(body, [
        ("Due", item.due_date),
        ("Status", item.status),
        ("Attempt", _attempt(item)),
        ("Attempts left", item.attempts_left),
        ("Grade", item.grade),
        ("Marked by", item.marked_by),
        ("KSBs", item.ksb_codes),
        ("Set", item.set_at),
    ], columns=4)
    box = widgets.section(body, "Brief")
    ttk.Label(box, text=item.brief or widgets.EMPTY, wraplength=900,
              justify="left").pack(anchor="w")
    if item.feedback:
        box = widgets.section(body, "Latest feedback")
        ttk.Label(box, text=item.feedback, wraplength=900, justify="left").pack(anchor="w")

    box = widgets.section(body, "Attempts")
    if item.submissions:
        table = widgets.DataTable(box, SUBMISSION_COLUMNS, height=min(6, len(item.submissions)))
        table.populate(
            item.submissions,
            lambda s: (s.attempt, s.submitted_at, s.is_late, s.evidence_title, s.grade,
                       s.marked_by, s.feedback),
            identity=lambda s: s.submission_id,
            tag=lambda s: "Red" if s.is_late else None,
            noun="attempt",
        )
        latest = item.submissions[-1]
        if latest.body:
            ttk.Label(box, text=f"Attempt {latest.attempt}:", font=("", 9, "bold")).pack(
                anchor="w", pady=(6, 0))
            ttk.Label(box, text=latest.body, wraplength=900, justify="left").pack(anchor="w")
    else:
        widgets.empty_state(box, "Nothing has been handed in yet.")

    box = widgets.section(body, "Moderation")
    if item.moderations:
        table = widgets.DataTable(box, MODERATION_COLUMNS, height=min(4, len(item.moderations)))
        table.populate(
            item.moderations,
            lambda m: (m.attempt, m.moderated_at, m.moderator, m.outcome,
                       f"{m.original_grade} → {m.adjusted_grade}" if m.adjusted_grade
                       else m.original_grade, m.notes),
            identity=lambda m: m.moderation_id,
            noun="moderation",
        )
    else:
        widgets.empty_state(box, "Not moderated.")


def _with(gui: Any, assignment_id: int,
          form: Callable[[Any, Assignment, Callable[[], None]], None]) -> None:
    """Load an assignment fresh, then open *form* on it."""
    ok, item = widgets.guard(lambda: assignment_service.get_assignment(gui.actor, assignment_id))
    if ok and item is not None:
        form(gui, item, gui.refresh)


# ═════════════════════════════════════════════════════════════════════
# Forms
# ═════════════════════════════════════════════════════════════════════

def _set_form(gui: Any) -> None:
    ok, people = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor, active_only=True)
    )
    if not ok or not people:
        widgets.warn("There is nobody on programme to set work for.", title="Nobody to set for")
        return
    labels = {s.full_name: s.apprentice.apprentice_id for s in people}
    fields = [
        {"key": "apprentice", "label": "Apprentice", "kind": "combo", "required": True,
         "options": list(labels)},
        *_assignment_fields(None),
    ]

    def save(values: dict[str, Any]) -> object:
        apprentice_id = labels.get(values.get("apprentice") or "")
        if apprentice_id is None:
            raise ValueError("Choose the apprentice the work is for")
        payload = {k: v for k, v in values.items() if k != "apprentice"}
        return assignment_service.set_assignment(gui.actor, apprentice_id, payload)

    if widgets.FormDialog(gui.root, "Set an assignment", fields, save).saved:
        gui.refresh()


def _edit_form(gui: Any, item: Assignment, done: Callable[[], None]) -> None:
    fields = _assignment_fields(item)
    intro = None
    if item.attempts_used:
        # Work was done against the brief; only the deadline may move.
        fields = [f for f in fields if f["key"] == "due_date"]
        intro = "Work has been handed in against this brief, so only the due date may change."

    def save(values: dict[str, Any]) -> object:
        return assignment_service.update_assignment(gui.actor, item.assignment_id, values)

    if widgets.FormDialog(gui.root, "Edit assignment", fields, save, intro=intro).saved:
        done()


def _assignment_fields(item: Assignment | None) -> list[dict[str, Any]]:
    def current(attr: str, default: Any = "") -> Any:
        value = getattr(item, attr, None) if item is not None else None
        return default if value is None else value

    return [
        {"key": "title", "label": "Title", "required": True, "value": current("title")},
        {"key": "assignment_type", "label": "Type", "kind": "combo", "required": True,
         "options": config.ASSIGNMENT_TYPES,
         "value": current("assignment_type", config.ASSIGNMENT_TYPES[0])},
        {"key": "brief", "label": "Brief", "kind": "text", "value": current("brief")},
        {"key": "ksb_codes", "label": "KSBs", "value": current("ksb_codes"),
         "help": "Comma-separated codes from the apprentice's standard, e.g. K1, S3."},
        {"key": "due_date", "label": "Due", "value": current("due_date"), "help": "YYYY-MM-DD."},
        {"key": "max_attempts", "label": "Attempts allowed",
         "value": str(current("max_attempts", config.ASSIGNMENT_MAX_ATTEMPTS)),
         "help": f"1 to {config.ASSIGNMENT_MAX_ATTEMPTS}, the first attempt included."},
    ]


def _submit_form(gui: Any, item: Assignment, done: Callable[[], None]) -> None:
    if not item.is_with_apprentice:
        widgets.warn(f"This assignment is {item.status.lower()} and is not waiting for work.",
                     title="Not open")
        return
    _, evidence = widgets.guard(
        lambda: portfolio_service.list_evidence(gui.actor, apprentice_id=item.apprentice_id)
    )
    choices = {f"{e.evidence_id} — {e.title} ({e.status})": e.evidence_id
               for e in (evidence or [])}
    fields = [
        {"key": "body", "label": "Your work", "kind": "text",
         "help": "Write it here, attach a piece of portfolio evidence, or both."},
        {"key": "evidence", "label": "Portfolio evidence", "kind": "combo",
         "options": ["", *choices]},
    ]
    late = item.is_overdue(date.today())

    def save(values: dict[str, Any]) -> object:
        return assignment_service.submit(
            gui.actor, item.assignment_id, body=values.get("body"),
            evidence_id=choices.get(values.get("evidence") or ""),
        )

    dialog = widgets.FormDialog(
        gui.root, f"Submit — {item.title}", fields, save, save_label="Submit",
        intro=f"Attempt {item.next_attempt} of {item.max_attempts}."
              + (f" It was due {item.due_date}: it will be accepted, and marked as late."
                 if late else ""),
    )
    if dialog.saved:
        done()


def _mark_form(gui: Any, item: Assignment, done: Callable[[], None]) -> None:
    if item.status != "Submitted":
        widgets.warn(f"There is nothing to mark — this assignment is {item.status.lower()}.",
                     title="Nothing to mark")
        return
    fields = [
        {"key": "grade", "label": "Grade", "kind": "combo", "required": True,
         "options": config.ASSIGNMENT_GRADES, "value": "Pass"},
        {"key": "feedback", "label": "Feedback", "kind": "text",
         "help": "Required for a Refer."},
        {"key": "resubmit_by", "label": "Resubmit by",
         "help": "YYYY-MM-DD. Used only for a Refer with attempts left."},
    ]

    def save(values: dict[str, Any]) -> object:
        return assignment_service.mark(
            gui.actor, item.assignment_id, grade=values.get("grade", ""),
            feedback=values.get("feedback"), resubmit_by=values.get("resubmit_by"),
        )

    left = item.max_attempts - item.attempt
    dialog = widgets.FormDialog(
        gui.root, f"Mark — {item.title}", fields, save,
        intro=f"{item.apprentice_name}, attempt {item.attempt} of {item.max_attempts}"
              + (" (handed in late)." if item.is_late else ".")
              + (f" A Refer sends it back; {left} more attempt(s) allowed."
                 if left > 0 else " This is the final attempt: a Refer stands."),
    )
    if dialog.saved:
        done()


def _moderate_form(gui: Any, item: Assignment, done: Callable[[], None]) -> None:
    if not item.awaiting_moderation:
        widgets.warn("This attempt is not waiting for moderation.", title="Nothing to moderate")
        return
    fields = [
        {"key": "outcome", "label": "Outcome", "kind": "combo", "required": True,
         "options": config.ASSIGNMENT_MODERATION_OUTCOMES, "value": "Agreed"},
        {"key": "adjusted_grade", "label": "Adjusted grade", "kind": "combo",
         "options": ["", *config.ASSIGNMENT_GRADES], "help": "Only for an adjustment."},
        {"key": "notes", "label": "Notes", "kind": "text",
         "help": "Required for an adjustment."},
    ]

    def save(values: dict[str, Any]) -> object:
        return assignment_service.moderate(
            gui.actor, item.assignment_id, outcome=values.get("outcome", ""),
            adjusted_grade=values.get("adjusted_grade") or None, notes=values.get("notes"),
        )

    dialog = widgets.FormDialog(
        gui.root, f"Moderate — {item.title}", fields, save,
        intro=f"Attempt {item.attempt}, marked {item.grade} by {item.marked_by}.",
    )
    if dialog.saved:
        done()


def _withdraw(gui: Any, item: Assignment, done: Callable[[], None]) -> None:
    reason = widgets.ask_reason(
        f"Why is “{item.title}” being withdrawn? It is kept on the record, not deleted.",
        title="Withdraw assignment",
    )
    if not reason:
        return
    ok, _ = widgets.guard(
        lambda: assignment_service.withdraw_assignment(gui.actor, item.assignment_id,
                                                       reason=reason)
    )
    if ok:
        done()


def _attempt(item: Assignment) -> str:
    return f"{item.attempt} of {item.max_attempts}"
