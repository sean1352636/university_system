"""One window for a learner's whole route to university.

This replaces six menu entries — University Progression, UCAS
Applications, UCAS Workflow, Personal Statements, References and
University Offers — that between them described one thing from six
angles, and made a member of staff working a single application visit
six screens to do it.

Four tabs, and the ordering is the workflow rather than the alphabet:

**Overview**     the progression board — the cohort question, "who is on
                 the way out and what is stopping them", which is what
                 somebody opens on results day.
**Application**  one learner, everything: the application, its choices,
                 the personal statement, the reference and the workflow
                 position, on one page. This is the tab that exists
                 because the same facts used to be entered twice.
**Offers**       offers across the cohort, and the comparison view.
**Workflow**     the tracked pipeline, cohort-wide.

The area screens are *embedded*, not reimplemented: each one already
exposed ``_build_*_tab(gui, parent)`` and those are called directly, so
this module is a composition and the behaviour of each area is
unchanged. What is new here is the Learner panel, which is the one
screen that never existed — the place where an application, its
statement and its reference are visible together.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import logging
import re
import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.assessment.gradebook.gradebook import (
    LETTER_GRADES as _LETTER_GRADES,
)

from education_system.systems.sixth_form.domain.progression.university import (
    references as reference_data,
    statements as statement_data,
    ucas as ucas_data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.gui.progression.university import (
    admissions_tests as admissions_test_views,
    board as board_views,
    deadlines as deadline_views,
    offers as offer_views,
    post_offer as post_offer_views,
    student_finance as student_finance_views,
    structured_references as structured_reference_views,
    references as reference_views,
    statements as statement_views,
    ucas as ucas_views,
    workflow as workflow_views,
)

logger = logging.getLogger(__name__)

#: Status colours shared by the summary strips, so "Submitted" is the
#: same colour whether it is a statement, a reference or an application.
_GOOD = "#0d6b2a"
_WORKING = "#7a5800"
_MISSING = "#a33"
_MUTED = "#777"


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def open_window(gui) -> None:
    """Entry point used by the sixth-form GUI navigation."""
    frame = _clear(gui)
    ttk.Label(frame, text="University & UCAS",
              font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        text=("Everything on a learner's route to university in one "
              "place — the application and its choices, the personal "
              "statement, the reference, the offers and where they have "
              "got to."),
        foreground="#555", wraplength=900, justify="left",
    ).pack(anchor="w", pady=(2, 8))

    nb = SidebarBook(frame)
    nb.pack(fill="both", expand=True)

    overview_tab = ttk.Frame(nb, padding=8)
    application_tab = ttk.Frame(nb, padding=8)
    offers_tab = ttk.Frame(nb, padding=8)
    workflow_tab = ttk.Frame(nb, padding=8)
    nb.add(overview_tab,    text="Overview")
    nb.add(application_tab, text="Application")
    nb.add(offers_tab,      text="Offers")
    nb.add(workflow_tab,    text="Workflow")
    # Added after the original four, in workflow order: the deadlines that
    # drive the pipeline, the tests some courses need, life after offers,
    # and the funding application that has to happen alongside.
    deadlines_tab = ttk.Frame(nb, padding=8)
    tests_tab = ttk.Frame(nb, padding=8)
    post_offer_tab = ttk.Frame(nb, padding=8)
    finance_tab = ttk.Frame(nb, padding=8)
    nb.add(deadlines_tab,  text="Deadlines")
    nb.add(tests_tab,      text="Admissions tests")
    nb.add(post_offer_tab, text="Extra & Clearing")
    nb.add(finance_tab,    text="Student finance")

    # Built eagerly. Every one of these was a screen somebody opened
    # directly a moment ago, and making three of them lazy would trade a
    # cost nobody noticed for a stutter on every tab change.
    _safe(overview_tab, "Overview",
          lambda: board_views._Dashboard(gui, overview_tab))
    _safe(application_tab, "Application",
          lambda: _build_application_tab(gui, application_tab))
    _safe(offers_tab, "Offers",
          lambda: _build_offers_tab(gui, offers_tab))
    _safe(workflow_tab, "Workflow",
          lambda: _build_workflow_tab(gui, workflow_tab))
    _safe(deadlines_tab, "Deadlines",
          lambda: deadline_views.build_tab(gui, deadlines_tab))
    _safe(tests_tab, "Admissions tests",
          lambda: admissions_test_views.build_tab(gui, tests_tab))
    _safe(post_offer_tab, "Extra & Clearing",
          lambda: post_offer_views.build_tab(gui, post_offer_tab))
    _safe(finance_tab, "Student finance",
          lambda: student_finance_views.build_tab(gui, finance_tab))

    gui.status_var.set("University & UCAS")


def _safe(parent: ttk.Frame, label: str, build) -> None:
    """Build one tab, and let the other three survive it failing.

    Four independent areas share this window now. An exception out of one
    of them used to take down only itself, because it *was* the screen;
    here it would leave the whole window blank, including the three tabs
    that are fine.
    """
    try:
        build()
    except Exception as exc:
        logger.exception("Could not build the %s tab", label)
        ttk.Label(parent,
                  text=f"This tab could not be loaded: {exc}",
                  foreground=_MISSING, wraplength=700,
                  justify="left").pack(anchor="w", pady=8)


# ─── Offers / Workflow: the area screens, embedded ──────────────────

def _build_offers_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    for label, build in (
        ("Offers",   offer_views._build_directory_tab),
        ("Compare",  offer_views._build_compare_tab),
        ("Summary",  offer_views._build_summary_tab),
    ):
        tab = ttk.Frame(inner, padding=6)
        inner.add(tab, text=label)
        _safe(tab, label, lambda b=build, t=tab: b(gui, t))


def _build_workflow_tab(gui, parent: ttk.Frame) -> None:
    """The workflow screen's own two tabs, without its page chrome.

    Built here rather than by calling ``open_directory``, which clears
    the whole content frame — inside a notebook that would take this
    window down with it. The two tab builders share a ``state`` dict and
    the cohort tab needs a handle on the notebook so double-clicking a
    learner can switch to their pipeline, so both are passed through.
    """
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    cohort = ttk.Frame(inner, padding=6)
    pipeline = ttk.Frame(inner, padding=6)
    inner.add(cohort, text="Cohort")
    inner.add(pipeline, text="Student pipeline")

    state = {"year": workflow_data.default_cycle_year(),
             "sid": tk.StringVar()}
    workflow_views._build_pipeline_tab(gui, pipeline, state)
    workflow_views._build_cohort_tab(gui, cohort, state, inner, pipeline)


# ─── Application: one learner, everything ───────────────────────────

def _build_application_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)

    learner_tab = ttk.Frame(inner, padding=6)
    all_tab = ttk.Frame(inner, padding=6)
    statements_tab = ttk.Frame(inner, padding=6)
    references_tab = ttk.Frame(inner, padding=6)
    inner.add(learner_tab,    text="Learner")
    inner.add(all_tab,        text="All applications")
    inner.add(statements_tab, text="Statements")
    inner.add(references_tab, text="References")
    structured_tab = ttk.Frame(inner, padding=6)
    inner.add(structured_tab, text="Structured references")

    _safe(learner_tab, "Learner",
          lambda: _build_learner_panel(gui, learner_tab))
    _safe(all_tab, "All applications",
          lambda: ucas_views._build_directory_tab(gui, all_tab))
    _safe(statements_tab, "Statements",
          lambda: statement_views._build_directory_tab(gui, statements_tab))
    _safe(references_tab, "References",
          lambda: reference_views._build_directory_tab(gui, references_tab))
    _safe(structured_tab, "Structured references",
          lambda: structured_reference_views.build_tab(gui, structured_tab))


def _build_learner_panel(gui, parent: ttk.Frame) -> None:
    """Pick a learner; see their whole application on one page."""
    picker = ttk.Frame(parent)
    picker.pack(anchor="w", fill="x", pady=(0, 8))

    rows = ucas_data.list_applications_with_detail()
    labels = [
        f"{r.application.student_id} — {r.student_name}  "
        f"(cycle {r.application.cycle_year}, {r.application.status})"
        for r in rows
    ]
    by_label = {label: r.application.application_id
                for label, r in zip(labels, rows)}

    app_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(picker, text="Learner:").pack(side="left")
    chooser = ttk.Combobox(picker, textvariable=app_var, values=labels,
                           state="readonly", width=58)
    chooser.pack(side="left", padx=(4, 8))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        application_id = by_label.get(app_var.get())
        if application_id is None:
            ttk.Label(holder, text="Pick a learner above.",
                      foreground=_MUTED).pack(anchor="w")
            return
        application = ucas_data.get_application(application_id)
        if application is None:
            ttk.Label(holder, text="That application no longer exists.",
                      foreground=_MISSING).pack(anchor="w")
            return

        # The application, its choices and their action bar — the same
        # renderer the UCAS screen uses, so there is one implementation
        # of "what does an application look like".
        ucas_views._render_application_detail(
            gui, holder, application_id, on_changed=render)

        _render_predicted_strip(gui, holder, application)
        _render_results_strip(gui, holder, application, on_changed=render)
        _render_statement_strip(gui, holder, application, on_changed=render)
        _render_reference_strip(gui, holder, application, on_changed=render)
        _render_workflow_strip(gui, holder, application)

    chooser.bind("<<ComboboxSelected>>", lambda _e: render())
    ttk.Button(picker, text="Refresh",
               command=lambda: _build_learner_panel_refresh(gui, parent)
               ).pack(side="left")

    if labels:
        render()
    else:
        ttk.Label(holder,
                  text="No UCAS applications yet. Use All applications → "
                       "New to start one.",
                  foreground=_MUTED).pack(anchor="w")


def _build_learner_panel_refresh(gui, parent: ttk.Frame) -> None:
    """Rebuild the panel, so a new application appears in the picker."""
    for w in parent.winfo_children():
        w.destroy()
    _build_learner_panel(gui, parent)


def _section(parent: ttk.Frame, title: str) -> ttk.Frame:
    frame = ttk.LabelFrame(parent, text=title, padding=8)
    frame.pack(fill="x", pady=(8, 0))
    return frame


def _predicted_grades(student_id: str):
    """``(subject, grade_or_None)`` per A-level, or ``None`` if unknown.

    Reaches out of this package into assessment, read-only and lazily,
    the way :mod:`..board` already reaches into the students table.
    Predicted grades are assessment data used well beyond UCAS and do
    not belong in here — but the UCAS workflow has a stage that turns on
    them, so the learner page has to be able to say where they stand.

    ``None`` means the question could not be answered (no student row, no
    module) rather than "no grades", which is a different thing to show.
    """
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
            predicted_grades as _predicted,
        )
        student = _students.get_student(student_id)
        if student is None:
            return None
        subjects = [s for s in (student.subject_1, student.subject_2,
                                student.subject_3) if s]
        # Keyed on the subject string, because that is exactly what the
        # workflow stage matches on — a prediction filed against a
        # subject the student is not down for counts for nothing, and
        # this strip should show the same answer the stage reaches.
        by_subject = {p.subject: p
                      for p in _predicted.predictions_for_student(student_id)}
        return [(subject, by_subject.get(subject)) for subject in subjects]
    except Exception:
        logger.debug("Could not read predicted grades for %s", student_id,
                     exc_info=True)
        return None


def _render_predicted_strip(gui, parent: ttk.Frame, application) -> None:
    """Predicted grades — the one UCAS workflow input filed elsewhere.

    The stage named "Predicted grades entered" is satisfied by a screen
    in Assessment, which is a reasonable place for it to live and a
    hopeless place to find it from here. So the position is shown on the
    page that cares, with a way through to the screen that owns it.
    """
    frame = _section(parent, "Predicted grades")
    rows = _predicted_grades(application.student_id)

    if rows is None:
        ttk.Label(frame, text="Could not be read.",
                  foreground=_MUTED).pack(anchor="w")
    elif not rows:
        ttk.Label(frame,
                  text="No A-level subjects on this student's record, so "
                       "there is nothing to predict.",
                  foreground=_MUTED, wraplength=760,
                  justify="left").pack(anchor="w")
    else:
        have = sum(1 for _subject, prediction in rows if prediction)
        ttk.Label(
            frame,
            text=f"{have}/{len(rows)} subjects predicted",
            foreground=(_GOOD if have == len(rows)
                        else _WORKING if have else _MISSING),
            font=("", 10, "bold"),
        ).pack(anchor="w")
        grid = ttk.Frame(frame)
        grid.pack(anchor="w", pady=(4, 0))
        for row, (subject, prediction) in enumerate(rows):
            ttk.Label(grid, text=subject, width=26, anchor="w").grid(
                row=row, column=0, sticky="w")
            ttk.Label(
                grid,
                text=(f"{prediction.grade}"
                      + (f"  ({prediction.confidence} confidence)"
                         if prediction.confidence else "")
                      if prediction else "— not predicted"),
                foreground=(_GOOD if prediction else _MISSING),
            ).grid(row=row, column=1, sticky="w", padx=(8, 0))

    ttk.Button(frame, text="Open predicted grades",
               command=lambda: _open_predicted_grades(gui)
               ).pack(anchor="w", pady=(6, 0))


def _open_predicted_grades(gui) -> None:
    """Hand over to the Assessment screen that owns these."""
    try:
        from education_system.systems.sixth_form.interfaces.gui.assessment.predicted_grades import (
            predicted_grades_views,
        )
    except Exception as exc:
        logger.exception("Could not load the predicted-grades screen")
        messagebox.showerror(
            "Predicted grades",
            f"Could not open the predicted-grades screen: {exc}",
            parent=gui.root)
        return
    predicted_grades_views.open_directory(gui)


def _released_results(student_id: str):
    """``(subject, grade_or_None)`` per A-level from *released* results.

    Released is the whole point: an unreleased grade is a mark somebody
    has keyed in, not a fact about the learner, and the handover's
    ``Results confirmed`` check says so explicitly. ``None`` means the
    question could not be answered rather than "no results".
    """
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        from education_system.systems.sixth_form.domain.assessment.exam_results import (
            exam_results as _results,
        )
        student = _students.get_student(student_id)
        if student is None:
            return None
        subjects = [s for s in (student.subject_1, student.subject_2,
                                student.subject_3) if s]
        released = {row.subject: row.result
                    for row in _results.results_for_student(student_id)
                    if row.result and row.result.released_at}
        return [(subject, released.get(subject)) for subject in subjects]
    except Exception:
        logger.debug("Could not read exam results for %s", student_id,
                     exc_info=True)
        return None


def _render_results_strip(gui, parent: ttk.Frame, application,
                          *, on_changed) -> None:
    """Released exam results — the last thing the handover waits on."""
    frame = _section(parent, "Exam results")
    rows = _released_results(application.student_id)

    if rows is None:
        ttk.Label(frame, text="Could not be read.",
                  foreground=_MUTED).pack(anchor="w")
        return
    if not rows:
        ttk.Label(frame,
                  text="No A-level subjects on this learner's record.",
                  foreground=_MUTED).pack(anchor="w")
        return

    have = sum(1 for _subject, result in rows if result)
    ttk.Label(frame, text=f"{have}/{len(rows)} subjects released",
              foreground=(_GOOD if have == len(rows)
                          else _WORKING if have else _MISSING),
              font=("", 10, "bold")).pack(anchor="w")
    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(4, 0))
    for row, (subject, result) in enumerate(rows):
        ttk.Label(grid, text=subject, width=26, anchor="w").grid(
            row=row, column=0, sticky="w")
        ttk.Label(grid,
                  text=(f"{result.grade}   released {result.released_at}"
                        if result else "— no released result"),
                  foreground=(_GOOD if result else _MISSING)).grid(
            row=row, column=1, sticky="w", padx=(8, 0))

    ttk.Button(frame, text="Enter results",
               command=lambda: _enter_results_dialog(
                   gui, application, on_saved=on_changed)
               ).pack(anchor="w", pady=(6, 0))


def _result_only_paper_code(subject: str) -> str:
    """A paper code for an entry created just to carry a result.

    Exam entries are UNIQUE on ``(student_id, paper_code, season, year)``,
    so one fixed placeholder code would collide on a learner's second
    subject — the first result would save and the rest would fail. It is
    derived from the subject instead, which is unique per learner by the
    same logic that makes the three A-level slots distinct.

    Kept obviously artificial. A code that looked like a real one would
    eventually be read as a real one; ``RO-`` says what it is.
    """
    slug = re.sub(r"[^A-Z0-9]+", "-", subject.upper()).strip("-")
    return f"RO-{slug}"[:24].rstrip("-") or "RO-SUBJECT"


def _enter_results_dialog(gui, application, *, on_saved) -> None:
    """Enter and release a grade per subject, in one dialog.

    A result hangs off an exam *entry*, and a learner with no entries —
    which is most of them until somebody does the entry run — has nothing
    for a result to attach to. So this creates the entry when it is
    missing, rather than sending the user to a different screen to make
    one before they can record a grade they already have in front of
    them.

    The entry it creates is deliberately minimal and marked as such in
    its notes: the fields that matter here are the subject and the grade,
    and inventing a paper code that looks real would be worse than one
    that admits what it is. A college running proper entry runs will
    already have the real entry, and this reuses it.
    """
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )

    student = _students.get_student(application.student_id)
    subjects = [s for s in (student.subject_1, student.subject_2,
                            student.subject_3) if s] if student else []
    if not subjects:
        messagebox.showinfo(
            "No subjects",
            "This learner has no A-level subjects on their record, so "
            "there is nothing to record results for.",
            parent=gui.root)
        return

    existing_entries = {e.subject: e
                        for e in _entries.entries_for_student(
                            application.student_id)}
    existing_results = {row.subject: row.result
                        for row in _results.results_for_student(
                            application.student_id) if row.result}

    win = tk.Toplevel(gui.root)
    win.title(f"Exam results — {application.student_id}")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=f"{application.student_id} — "
                        f"{student.full_name if student else '?'}",
              font=("", 11, "bold")).grid(row=0, column=0, columnspan=4,
                                          sticky="w", pady=(0, 8))
    for column, text in enumerate(("Subject", "Grade", "Released", "")):
        ttk.Label(frm, text=text, font=("", 9, "bold")).grid(
            row=1, column=column, sticky="w", padx=(0, 8))

    fields = []
    for index, subject in enumerate(subjects):
        result = existing_results.get(subject)
        grade_var = tk.StringVar(value=result.grade if result else "")
        release_var = tk.BooleanVar(
            value=bool(result and result.released_at) or not result)
        box = ttk.Entry(frm, width=26)
        box.insert(0, subject)
        box.configure(state="readonly")
        box.grid(row=2 + index, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Combobox(frm, textvariable=grade_var,
                     values=["", *_LETTER_GRADES], state="readonly",
                     width=6).grid(row=2 + index, column=1, sticky="w",
                                   padx=(0, 8), pady=2)
        ttk.Checkbutton(frm, variable=release_var).grid(
            row=2 + index, column=2, sticky="w", padx=(0, 8))
        ttk.Label(frm,
                  text=("entry on file" if subject in existing_entries
                        else "entry will be created"),
                  foreground=_MUTED).grid(row=2 + index, column=3,
                                          sticky="w")
        fields.append((subject, grade_var, release_var))

    next_row = 2 + len(subjects)
    ttk.Label(frm,
              text=("Releasing is what makes a grade count: the handover "
                    "treats an unreleased result as no result."),
              foreground=_MUTED, wraplength=460, justify="left").grid(
        row=next_row, column=0, columnspan=4, sticky="w", pady=(8, 0))

    year_var = tk.StringVar(value=str(application.cycle_year))
    board_var = tk.StringVar(value=_entries.EXAM_BOARDS[0])
    meta = ttk.Frame(frm)
    meta.grid(row=next_row + 1, column=0, columnspan=4, sticky="w",
              pady=(8, 0))
    ttk.Label(meta, text="Series year:").pack(side="left")
    ttk.Entry(meta, textvariable=year_var, width=6).pack(side="left",
                                                          padx=(4, 12))
    ttk.Label(meta, text="Board (new entries):").pack(side="left")
    ttk.Combobox(meta, textvariable=board_var,
                 values=list(_entries.EXAM_BOARDS), state="readonly",
                 width=12).pack(side="left", padx=(4, 0))

    def save() -> None:
        filled = [(s, g.get().strip(), r.get()) for s, g, r in fields
                  if g.get().strip()]
        if not filled:
            messagebox.showinfo(
                "Nothing to save",
                "Pick a grade for at least one subject.", parent=win)
            return
        try:
            year = int(year_var.get().strip())
        except ValueError:
            messagebox.showwarning("Series year",
                                   "Year must be a 4-digit number.",
                                   parent=win)
            return

        today = _date.today().isoformat()
        saved, failed = 0, []
        for subject, grade, release in filled:
            try:
                entry = existing_entries.get(subject)
                if entry is None:
                    entry = _entries.create_entry({
                        "student_id": application.student_id,
                        "subject": subject,
                        "exam_board": board_var.get(),
                        "paper_code": _result_only_paper_code(subject),
                        "season": "Summer",
                        "year": year,
                        "status": "Sat",
                        "notes": "Created to record a result entered from "
                                 "the University & UCAS screen.",
                    })
                    existing_entries[subject] = entry
                _results.save_result({
                    "entry_id": entry.entry_id,
                    "grade": grade,
                    "released_at": today if release else None,
                })
                saved += 1
            except Exception as e:
                logger.exception("Saving the result for %s failed", subject)
                failed.append(f"{subject}: {e}")

        if failed:
            messagebox.showerror(
                "Some results were not saved",
                f"Saved {saved} of {len(filled)}.\n\n" + "\n".join(failed),
                parent=win)
        else:
            gui.status_var.set(
                f"Saved {saved} exam result(s) for "
                f"{application.student_id}")
            win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=next_row + 2, column=0, columnspan=4, sticky="e",
             pady=(12, 0))
    ttk.Button(bar, text="Save results",
               command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel",
               command=win.destroy).pack(side="left")


def _render_statement_strip(gui, parent: ttk.Frame, application,
                            *, on_changed) -> None:
    """The personal statement, as a line rather than a separate screen."""
    frame = _section(parent, "Personal statement")
    drafts = statement_data.statements_for_student(application.student_id)
    latest = drafts[0] if drafts else None

    if latest is not None:
        over = (latest.char_count > statement_data.MAX_CHARS
                or latest.line_count > statement_data.MAX_LINES)
        text = (f"{latest.status}  ·  {latest.char_count}/"
                f"{statement_data.MAX_CHARS} chars  ·  "
                f"{latest.line_count}/{statement_data.MAX_LINES} lines"
                + (f"  ·  reviewed by {latest.reviewer}"
                   if latest.reviewer else "")
                + (f"  ·  {len(drafts)} drafts" if len(drafts) > 1 else ""))
        colour = (_MISSING if over
                  else _GOOD if latest.status in ("Approved", "Submitted")
                  else _WORKING)
    elif application.personal_statement:
        # On the application and never drafted here. Naming that state is
        # the whole reason the import exists.
        text = ("On the UCAS application only — no draft here, so it has "
                "no review history or feedback.")
        colour = _WORKING
    else:
        text = "Not written yet."
        colour = _MISSING

    ttk.Label(frame, text=text, foreground=colour,
              wraplength=760, justify="left").pack(anchor="w")

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(6, 0))
    if latest is not None:
        ttk.Button(bar, text="Open statement",
                   command=lambda: statement_views.open_editor(
                       gui, statement_id=latest.statement_id)
                   ).pack(side="left", padx=(0, 6))
    elif application.personal_statement:
        ttk.Button(bar, text="Import as draft",
                   command=lambda: statement_views._import_ucas_statement(
                       gui, application.application_id, on_changed=on_changed)
                   ).pack(side="left", padx=(0, 6))
    else:
        ttk.Button(bar, text="Start a draft",
                   command=lambda: statement_views.open_editor(
                       gui, statement_id=None)
                   ).pack(side="left", padx=(0, 6))


def _render_reference_strip(gui, parent: ttk.Frame, application,
                            *, on_changed) -> None:
    """The academic reference, same treatment."""
    frame = _section(parent, "Academic reference")
    refs = reference_data.references_for_student(application.student_id)
    # The submitted one is the one that counts; otherwise the latest.
    latest = next((r for r in refs if r.status == "Submitted"),
                  refs[0] if refs else None)

    if latest is None:
        ttk.Label(frame, text="No reference requested yet.",
                  foreground=_MISSING).pack(anchor="w")
    else:
        ttk.Label(
            frame,
            text=(f"{latest.status}"
                  + (f"  ·  {latest.referee}" if latest.referee else "")
                  + (f" ({latest.referee_role})"
                     if latest.referee_role else "")
                  + (f"  ·  {len(refs)} on file" if len(refs) > 1 else "")),
            foreground=(_GOOD if latest.status == "Submitted" else _WORKING),
        ).pack(anchor="w")

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(6, 0))
    ttk.Button(
        bar,
        text="Open reference" if latest is not None else "Request one",
        command=lambda: reference_views.open_editor(
            gui, reference_id=(latest.reference_id
                               if latest is not None else None)),
    ).pack(side="left", padx=(0, 6))


def _render_workflow_strip(gui, parent: ttk.Frame, application) -> None:
    """Where this application has got to, as the stage list."""
    frame = _section(parent, "Workflow")
    try:
        pipeline = workflow_data.get_pipeline(
            application.student_id, application.cycle_year)
    except Exception as exc:
        logger.debug("Could not read the workflow pipeline", exc_info=True)
        ttk.Label(frame, text=f"Pipeline unavailable: {exc}",
                  foreground=_MUTED, wraplength=760,
                  justify="left").pack(anchor="w")
        return

    ttk.Label(frame,
              text=f"{pipeline['complete']}/{pipeline['total']} stages "
                   f"complete  ({pipeline['percent']}%)",
              font=("", 10, "bold")).pack(anchor="w")
    strip = ttk.Frame(frame)
    strip.pack(anchor="w", pady=(4, 0))
    for column, stage in enumerate(pipeline["stages"]):
        status = stage["status"]
        colour = (_GOOD if status == "Complete"
                  else _MUTED if status == "N/A"
                  else _WORKING if status == "In Progress"
                  else _MISSING)
        mark = {"Complete": "✓", "N/A": "–",
                "In Progress": "…"}.get(status, "·")
        ttk.Label(strip, text=f"{mark} {stage['label']}",
                  foreground=colour).grid(
            row=column // 4, column=column % 4, sticky="w", padx=(0, 16))

    ttk.Button(frame, text="Open workflow",
               command=lambda: workflow_views.open_directory(gui)
               ).pack(anchor="w", pady=(6, 0))


__all__ = ["open_window"]
