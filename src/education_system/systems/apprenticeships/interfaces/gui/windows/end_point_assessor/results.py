"""Results — end point assessor screen.

Grade a sitting. Grading is final and exclusive to this role.

``epa.grade`` is held by the end-point assessor and by nobody else — the
provider administrator deliberately included, because a training
provider grading the apprentices it is paid for completing is what
independent assessment exists to prevent. So this screen is where the
capability lives, and it says out loud that the decision cannot be
edited afterwards: a correction is another sitting, not a rewrite.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    epa_service,
)

logger = logging.getLogger(__name__)

TITLE = "Results"
SUBTITLE = "Grade a sitting. Grading is final and exclusive to this role."

# Only these two can legally move to Assessed, so a Requested booking
# with no date is not offered and then refused.
GRADABLE = ("Scheduled", "In Progress")

_QUEUE_COLUMNS = (
    ("apprentice", "Apprentice", 200),
    ("method", "Method", 220),
    ("when", "When", 160),
    ("location", "Where", 180),
    ("standard", "Standard", 110),
    ("status", "Status", 120),
)

_RESULT_COLUMNS = (
    ("assessed", "Assessed", 120),
    ("method", "Method", 240),
    ("grade", "Grade", 110),
    ("attempt", "Attempt", 90, "e"),
    ("assessor", "Assessor", 190),
    ("feedback", "Feedback", 400),
)

_PROGRESS_COLUMNS = (
    ("method", "Method", 240),
    ("grade", "Best grade", 120),
    ("attempts", "Attempts", 90, "e"),
    ("remaining", "Attempts left", 110, "e"),
    ("passed", "Passed", 80),
)


def render(gui) -> None:
    """Draw the results screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("epa.view"):
        widgets.empty_state(frame, "Your role may not see assessment results.")
        return

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)

    grading = ttk.Frame(notebook, padding=8)
    notebook.add(grading, text="To grade")
    _to_grade(gui, grading)

    recent = ttk.Frame(notebook, padding=8)
    notebook.add(recent, text="Recorded")
    _recorded(gui, recent)

    progress = ttk.Frame(notebook, padding=8)
    notebook.add(progress, text="One apprentice")
    _progress_tab(gui, progress)


# ═════════════════════════════════════════════════════════════════════
# The grading queue
# ═════════════════════════════════════════════════════════════════════

def _to_grade(gui, parent: Any) -> None:
    if not gui.actor.can("epa.grade"):
        ttk.Label(
            parent,
            text="Only the independent end-point assessor may grade a sitting. "
                 "End-Point Assessment is independent by design: the organisation "
                 "that delivered the training does not decide that its own "
                 "apprentice has passed.",
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(0, 8))

    ok, rows = widgets.guard(
        lambda: epa_service.list_bookings(gui.actor, open_only=True)
    )
    if not ok:
        return
    rows = [r for r in (rows or []) if r.get("status") in GRADABLE]

    table = widgets.DataTable(parent, _QUEUE_COLUMNS)
    table.populate(
        rows,
        lambda r: (
            r.get("apprentice_name"), r.get("method"),
            f"{r.get('scheduled_date') or widgets.EMPTY} "
            f"{r.get('scheduled_time') or ''}".strip(),
            r.get("location"), r.get("programme_reference"), r.get("status"),
        ),
        identity=lambda r: r["booking_id"],
        tag=lambda r: "Amber" if r.get("status") == "In Progress" else None,
        noun="sitting",
    )
    if not rows:
        widgets.empty_state(
            parent,
            "Nothing is at a point where it can be graded. A booking has to be "
            "scheduled or in progress first.",
        )
        return

    by_id = {int(r["booking_id"]): r for r in rows}

    def grade() -> None:
        booking_id = table.require_selection_int("record a result")
        if booking_id is not None:
            _grade(gui, by_id[booking_id])

    if gui.actor.can("epa.grade"):
        widgets.button_bar(parent, [("Record Result…", grade)])


def _grade(gui, row: dict) -> None:
    """Grade one sitting."""
    fields = [
        {"key": "grade", "label": "Grade", "kind": "combo", "required": True,
         "options": config.EPA_GRADES, "value": "Pass"},
        {"key": "assessed_date", "label": "Assessed on",
         "value": row.get("scheduled_date") or date.today().isoformat(),
         "help": "YYYY-MM-DD"},
        {"key": "feedback", "label": "Feedback", "kind": "text",
         "help": "Read by the apprentice and their provider. On a fail it is what "
                 "the retake is planned around."},
    ]

    def save(values: dict[str, Any]) -> Any:
        return epa_service.record_result(
            gui.actor, int(row["booking_id"]),
            grade=values["grade"], assessed_date=values["assessed_date"],
            feedback=values["feedback"],
        )

    dialog = widgets.FormDialog(
        gui.root,
        f"Grade — {row.get('apprentice_name')}, {row.get('method')}",
        fields, save,
        intro="Grading is final. A correction is another sitting, not an edit, so "
              "check the grade before you save.",
        save_label="Record",
    )
    if not dialog.saved or dialog.result is None:
        return

    result = dialog.result
    ok, progress = widgets.guard(
        lambda: epa_service.epa_progress(gui.actor, result.apprentice_id)
    )
    message = f"{result.method}: {result.grade} (attempt {result.attempt})."
    if ok and progress is not None:
        if progress.is_complete:
            message += (
                f"\n\nEvery required method is passed — the apprenticeship is "
                f"complete at {progress.overall}, and the provider's withheld "
                "completion payment is released."
            )
        elif not result.is_pass:
            message += (
                f"\n\n{progress.resits_remaining(result.method)} further attempt(s) "
                f"at {result.method} are permitted."
            )
        elif progress.methods_outstanding:
            message += "\n\nStill to pass: " + ", ".join(progress.methods_outstanding)
    widgets.inform(message, title="Result recorded")
    gui.refresh()


# ═════════════════════════════════════════════════════════════════════
# What has been recorded
# ═════════════════════════════════════════════════════════════════════

def _recorded(gui, parent: Any) -> None:
    ok, rows = widgets.guard(
        lambda: epa_service.list_bookings(gui.actor, status="Assessed")
    )
    if not ok:
        return
    rows = rows or []
    if not rows:
        widgets.empty_state(parent, "Nothing has been graded yet.")
        return

    ttk.Label(
        parent,
        text="Graded sittings, newest date first. A booking cannot leave this state — "
             "a correction is a resit.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    table = widgets.DataTable(parent, _QUEUE_COLUMNS)
    table.populate(
        rows,
        lambda r: (
            r.get("apprentice_name"), r.get("method"),
            f"{r.get('scheduled_date') or widgets.EMPTY} "
            f"{r.get('scheduled_time') or ''}".strip(),
            r.get("location"), r.get("programme_reference"), r.get("status"),
        ),
        identity=lambda r: r["booking_id"],
        tag=lambda _r: "Green",
        noun="sitting",
    )


# ═════════════════════════════════════════════════════════════════════
# One apprentice's whole EPA
# ═════════════════════════════════════════════════════════════════════

def _progress_tab(gui, parent: Any) -> None:
    ok, summaries = widgets.guard(lambda: apprentice_service.list_apprentices(gui.actor))
    if not ok or not summaries:
        widgets.empty_state(parent, "There are no apprentices in scope.")
        return

    labels = {s.full_name: s.apprentice.apprentice_id for s in summaries}
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 8))
    ttk.Label(row, text="Apprentice:").pack(side="left", padx=(0, 6))
    picker = ttk.Combobox(row, values=list(labels), state="readonly", width=34)
    picker.set(next(iter(labels)))
    picker.pack(side="left")

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)

    def show(_event: Any = None) -> None:
        for child in body.winfo_children():
            child.destroy()
        _progress(gui, body, labels[picker.get()])

    picker.bind("<<ComboboxSelected>>", show)
    ttk.Button(row, text="Refresh", command=show).pack(side="left", padx=(8, 0))
    show()


def _progress(gui, parent: Any, apprentice_id: int) -> None:
    ok, progress = widgets.guard(
        lambda: epa_service.epa_progress(gui.actor, apprentice_id)
    )
    if not ok or progress is None:
        return
    if not progress.required_methods:
        widgets.empty_state(
            parent,
            "The standard on this record does not list its assessment methods, so "
            "there is nothing to grade against.",
        )
        return

    best = progress.best_results
    widgets.kpi_row(parent, [
        ("Methods required", len(progress.required_methods)),
        ("Passed", len(progress.methods_passed)),
        ("Outstanding", len(progress.methods_outstanding)),
        ("Complete", "Yes" if progress.is_complete else "No"),
        ("Overall grade", progress.overall or widgets.EMPTY),
    ])

    box = widgets.section(parent, "Method by method")
    rows = [
        {
            "method": method,
            "result": best.get(method),
            "attempts": progress.attempts_by_method.get(method, 0),
            "remaining": progress.resits_remaining(method),
        }
        for method in progress.required_methods
    ]
    table = widgets.DataTable(box, _PROGRESS_COLUMNS, height=max(3, len(rows)))
    table.populate(
        rows,
        lambda r: (r["method"],
                   r["result"].grade if r["result"] else widgets.EMPTY,
                   r["attempts"], r["remaining"],
                   bool(r["result"] and r["result"].is_pass)),
        identity=lambda r: r["method"],
        tag=lambda r: "Green" if r["result"] and r["result"].is_pass else (
            "Red" if r["result"] else "Amber"
        ),
        noun="method",
    )
    ttk.Label(
        box,
        text="Where a method was sat more than once the best grade counts, not the "
             "latest — so an administrative re-entry cannot downgrade anyone. The "
             "overall grade is the lowest across the methods rather than an average.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(6, 0))

    box = widgets.section(parent, "Every result")
    if progress.results:
        results = widgets.DataTable(
            box, _RESULT_COLUMNS, height=min(8, len(progress.results))
        )
        results.populate(
            progress.results,
            lambda r: (r.assessed_date, r.method, r.grade, r.attempt,
                       r.assessor_name, r.feedback),
            identity=lambda r: r.result_id,
            tag=lambda r: "Green" if r.is_pass else "Red",
            noun="result",
        )
    else:
        widgets.empty_state(box, "Nothing graded yet.")
