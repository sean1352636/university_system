"""End-Point Assessment — apprentice screen.

Your bookings, results and overall grade.

Read-only. Booking is the provider's job and grading is the assessment
organisation's, so the only thing this screen owes the apprentice is a
straight answer to "when am I being assessed, how did it go, and what am
I coming out with?".

The overall grade is the *lowest* of the per-method grades, not an
average, and that surprises people — so the screen says so where the
grade appears rather than leaving it to be discovered.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import epa_service

logger = logging.getLogger(__name__)

TITLE = "End-Point Assessment"
SUBTITLE = "Your bookings, results and overall grade."

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is nothing to "
    "show here. Ask your training provider's administrator to link your account."
)

_BOOKING_COLUMNS = (
    ("method", "Method", 240),
    ("when", "When", 170),
    ("location", "Where", 200),
    ("assessor", "Assessor", 200),
    ("status", "Status", 130),
    ("resit", "Resit", 80),
)

_RESULT_COLUMNS = (
    ("assessed", "Assessed", 120),
    ("method", "Method", 240),
    ("grade", "Grade", 110),
    ("attempt", "Attempt", 90, "e"),
    ("assessor", "Assessor", 180),
    ("feedback", "Feedback", 420),
)

_RESIT_COLUMNS = (
    ("requested", "Requested", 170),
    ("type", "Type", 100),
    ("status", "Status", 120),
    ("reason", "Reason", 340),
    ("plan", "Training plan", 340),
)

_BOOKING_TAGS = {
    "Assessed": "Green", "Scheduled": "Green", "In Progress": "Amber",
    "Requested": "Amber", "Cancelled": "Red",
}


def render(gui) -> None:
    """Draw the end-point assessment screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    apprentice_id = gui.actor.apprentice_id
    if apprentice_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    ok, progress = widgets.guard(
        lambda: epa_service.epa_progress(gui.actor, apprentice_id)
    )
    if not ok or progress is None:
        return

    required = progress.required_methods
    if not required:
        widgets.empty_state(
            frame,
            "The standard on your record does not list its assessment methods yet, so "
            "there is nothing to show. Your provider sets those on the programme.",
        )
        return

    passed = len(progress.methods_passed)
    widgets.kpi_row(frame, [
        ("Methods required", len(required)),
        ("Passed", passed),
        ("Still to pass", len(progress.methods_outstanding)),
        ("Bookings", len(progress.bookings)),
        ("Results", len(progress.results)),
        ("Overall grade", progress.overall or widgets.EMPTY),
    ])
    widgets.progress_row(
        frame, "End-point assessment", (passed / len(required) * 100),
        detail=f"{passed} of {len(required)} methods passed",
        rag="Green" if progress.is_complete else "Amber",
    )

    if progress.is_complete:
        ttk.Label(
            frame,
            text=f"Every required method is passed — your apprenticeship is complete "
                 f"at {progress.overall}. The overall grade is the lowest of your "
                 "per-method grades rather than an average, so a strong showing in "
                 "one does not lift a weaker one in another.",
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(8, 0))
    elif progress.methods_outstanding:
        ttk.Label(
            frame,
            text="Still to pass: " + ", ".join(progress.methods_outstanding),
            foreground=config.MUTED_FG, wraplength=900, justify="left",
        ).pack(anchor="w", pady=(8, 0))

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True, pady=(10, 0))

    bookings = ttk.Frame(notebook, padding=8)
    notebook.add(bookings, text=f"Bookings ({len(progress.bookings)})")
    _bookings(bookings, progress)

    results = ttk.Frame(notebook, padding=8)
    notebook.add(results, text=f"Results ({len(progress.results)})")
    _results(results, progress)

    resits = ttk.Frame(notebook, padding=8)
    notebook.add(resits, text=f"Resits ({len(progress.resits)})")
    _resits(resits, progress)

    widgets.button_bar(frame, [("Refresh", lambda: render(gui))])


def _bookings(parent: Any, progress: Any) -> None:
    if not progress.bookings:
        widgets.empty_state(
            parent,
            "Nothing is booked yet. Your provider books each method once the "
            "assessment organisation has approved you through gateway.",
        )
        return
    table = widgets.DataTable(parent, _BOOKING_COLUMNS, height=min(10, len(progress.bookings)))
    table.populate(
        progress.bookings,
        lambda b: (b.method, b.when, b.location, b.assessor_name, b.status, b.is_resit),
        identity=lambda b: b.booking_id,
        tag=lambda b: _BOOKING_TAGS.get(b.status),
        noun="booking",
    )


def _results(parent: Any, progress: Any) -> None:
    if not progress.results:
        widgets.empty_state(parent, "Nothing has been graded yet.")
        return

    best = {r.result_id for r in progress.best_results.values()}
    table = widgets.DataTable(parent, _RESULT_COLUMNS, height=min(10, len(progress.results)))
    table.populate(
        progress.results,
        lambda r: (r.assessed_date, r.method, r.grade, r.attempt, r.assessor_name,
                   r.feedback),
        identity=lambda r: r.result_id,
        tag=lambda r: "Green" if r.is_pass else "Red",
        noun="result",
    )
    ttk.Label(
        parent,
        text="Where a method was sat more than once, the best grade is the one that "
             f"counts ({len(best)} counting towards your overall grade).",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(6, 0))


def _resits(parent: Any, progress: Any) -> None:
    if not progress.resits:
        ttk.Label(
            parent,
            text="No resit has been requested. If a method is failed, you may normally "
                 f"sit it {config.MAX_RESITS} more times — a resit goes straight back "
                 "to assessment, a retake means more training first.",
            foreground=config.MUTED_FG, wraplength=900, justify="left",
        ).pack(anchor="w")
        return

    table = widgets.DataTable(parent, _RESIT_COLUMNS, height=min(8, len(progress.resits)))
    table.populate(
        progress.resits,
        lambda r: (r.requested_at, r.resit_type, r.status, r.reason, r.training_plan),
        identity=lambda r: r.resit_id,
        tag=lambda r: "Green" if r.booking_id else "Amber",
        noun="resit",
    )

    remaining = {
        method: progress.resits_remaining(method)
        for method in progress.methods_outstanding
    }
    if remaining:
        ttk.Label(
            parent,
            text="Attempts left: " + ", ".join(
                f"{method} — {count}" for method, count in remaining.items()
            ),
            foreground=config.MUTED_FG, wraplength=900, justify="left",
        ).pack(anchor="w", pady=(6, 0))
