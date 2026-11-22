"""GUI panels for Sixth Form Predicted Grades.

Three-tab Notebook:

* Directory — filterable list of every prediction.
* Per-student — pick a student, see all their predictions, edit
  inline.
* Group sheet — pick a class group, render its roster, set predictions
  for the group's subject in one go.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable
from education_system.systems.sixth_form.domain.academics.class_groups import class_groups
from education_system.systems.sixth_form.domain.academics.courses import courses
from education_system.systems.sixth_form.domain.assessment.predicted_grades import predicted_grades
from education_system.systems.sixth_form.domain.academics.class_groups import class_groups as cg_data
from education_system.systems.sixth_form.domain.academics.courses import courses as course_data
from education_system.systems.sixth_form.domain.assessment.predicted_grades import predicted_grades as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.academics.subjects import subjects as subjects_data
from education_system.systems.sixth_form.domain.assessment.gradebook.gradebook import LETTER_GRADES
from education_system.systems.sixth_form.domain.assessment.predicted_grades.predicted_grades import (
    CONFIDENCE_LEVELS,
    DEFAULT_CONFIDENCE,
    Prediction,
    ValidationError,
)
from education_system.systems.sixth_form.domain.learners.students.students import A_LEVEL_SUBJECTS

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _active_subjects() -> list[str]:
    try:
        return subjects_data.get_active_names() or list(A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to seed subject list")
        return list(A_LEVEL_SUBJECTS)


def _student_subjects(student) -> list[str]:
    """The A-levels this learner is actually taking.

    A prediction is filed against a subject *string*, and everything that
    reads predictions back — the UCAS workflow stage, the university
    handover — matches on the learner's own three subjects. So a
    prediction against anything else counts for nothing anywhere, which
    is what made a picker listing every subject in the college a way to
    enter data that silently did not register.
    """
    if student is None:
        return []
    out = [s for s in (student.subject_1, student.subject_2,
                       student.subject_3) if s]
    # Plus every other active learning aim (4th A level, EPQ, BTEC,
    # T Level, GCSE resit) — UCAS takes predictions for those too.
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        for a in learning_aims.active_aims(student.student_id):
            if a.subject not in out:
                out.append(a.subject)
    except Exception:
        logger.exception("Could not read learning aims for %s",
                         student.student_id)
    return out


def _grades_for(student_id: str | None, subject: str | None) -> list[str]:
    """Grade scale for the learner's aim in ``subject`` (A*-U default)."""
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        return list(learning_aims.grade_options(student_id, subject))
    except Exception:
        return list(LETTER_GRADES)


def _all_grades() -> list[str]:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    return list(grade_scales.ALL_GRADES)


def _current_user(gui) -> str:
    """Who is entering these, for the ``predicted_by`` column."""
    auth = getattr(gui, "auth", None)
    cu = getattr(auth, "current_user", None) if auth is not None else None
    if isinstance(cu, dict):
        for key in ("display_name", "username"):
            value = cu.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _ucas_requirement(student_id: str) -> tuple[str, str] | None:
    """``(message, colour)`` describing what UCAS still needs, or None.

    Predicted grades are assessment data, and this module has no business
    depending on UCAS — so the read is lazy, guarded, and its absence is
    silent. But a predicted grade is one of the things a UCAS application
    is *waiting on*, and the person filling this screen in is usually
    filling it in for that reason. Saying so here is the difference
    between a form and a task.
    """
    try:
        from education_system.systems.sixth_form.domain.progression.university import (
            ucas as _ucas,
            workflow as _workflow,
        )
        application = _ucas.get_application_for_student(student_id)
        if application is None:
            return ("No UCAS application on file, so nothing is waiting on "
                    "these yet.", "#777")
        pipeline = _workflow.get_pipeline(student_id, application.cycle_year)
        stage = next((s for s in pipeline["stages"]
                      if s["key"] == "predicted_grades"), None)
        status = stage["status"] if stage else "Unknown"
        colour = {"Complete": "#0d6b2a", "In Progress": "#7a5800"}.get(
            status, "#a33")
        return (f"UCAS application #{application.application_id} "
                f"(cycle {application.cycle_year}, {application.status}) — "
                f"predicted-grades stage: {status}. The stage completes "
                f"when every subject below has a grade.", colour)
    except Exception:
        logger.debug("Could not read the UCAS requirement for %s",
                     student_id, exc_info=True)
        return None


def _group_label(g, course=None) -> str:
    if course is None:
        course = course_data.get_course(g.course_id)
    code = course.course_code if course else f"#{g.course_id}"
    return f"#{g.group_id} {g.group_name} ({code})"


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Predicted Grades")

    nb = SidebarBook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    student_tab = ttk.Frame(nb, padding=8)
    group_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(student_tab, text="Per-student")
    nb.add(group_tab,   text="Group sheet")

    _build_directory_tab(gui, dir_tab)
    _build_student_tab(gui, student_tab)
    _build_group_tab(gui, group_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    subject_var = tk.StringVar()
    grade_var = tk.StringVar()
    confidence_var = tk.StringVar()

    ttk.Label(filt, text="Student ID:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Subject:").pack(side="left")
    ttk.Combobox(filt, textvariable=subject_var,
                 values=["", *_active_subjects()], state="readonly", width=22
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Grade:").pack(side="left")
    ttk.Combobox(filt, textvariable=grade_var,
                 values=["", *_all_grades()], state="readonly", width=12
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Confidence:").pack(side="left")
    ttk.Combobox(filt, textvariable=confidence_var,
                 values=["", *CONFIDENCE_LEVELS], state="readonly", width=10
                 ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(parent)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        try:
            rows = data.list_predictions(
                student_id=sid_var.get().strip() or None,
                subject=subject_var.get().strip() or None,
                grade=grade_var.get().strip() or None,
                confidence=confidence_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_predictions failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("prediction_id", "student", "subject", "grade",
                "confidence", "predicted_by", "updated_at")
        headings = {
            "prediction_id": ("#",          50),
            "student":       ("Student",   110),
            "subject":       ("Subject",   180),
            "grade":         ("Grade",      60),
            "confidence":    ("Confidence", 90),
            "predicted_by":  ("By",         140),
            "updated_at":    ("Updated",   140),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings",
                            height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for p in rows:
            tree.insert("", "end", iid=str(p.prediction_id), values=(
                p.prediction_id, p.student_id, p.subject, p.grade,
                p.confidence, p.predicted_by or "—",
                p.updated_at,
            ))
        summary.configure(text=f"{len(rows)} prediction(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            pid = _selected()
            if pid is None:
                messagebox.showinfo("No selection",
                                    "Pick a prediction first.",
                                    parent=gui.root)
            return pid

        def _edit() -> None:
            pid = _require()
            if pid is None:
                return
            _edit_dialog(gui, pid, on_saved=refresh)

        def _delete() -> None:
            pid = _require()
            if pid is None:
                return
            p = data.get_prediction(pid)
            if p is None:
                return
            if not messagebox.askyesno(
                "Delete prediction",
                f"Delete prediction #{pid} ({p.student_id} / {p.subject})?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_prediction(pid)
            except Exception as e:
                logger.exception("delete_prediction crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Edit",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New / Update",
                   command=lambda: _new_dialog(gui, on_saved=refresh)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"Predictions: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), subject_var.set(""),
                                grade_var.set(""), confidence_var.set(""),
                                refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def _new_dialog(gui, on_saved) -> None:
    students = student_data.list_students()
    if not students:
        messagebox.showinfo("No students",
                            "Add a student first.", parent=gui.root)
        return

    win = tk.Toplevel(gui.root)
    win.title("New / Update Prediction")
    win.transient(gui.root)
    grab_when_viewable(win)

    frm = ttk.Frame(win, padding=12)
    frm.grid()

    student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                        for s in students}
    student_var = tk.StringVar(value=student_labels[0])
    subject_var = tk.StringVar()
    grade_var = tk.StringVar(value=LETTER_GRADES[0])
    confidence_var = tk.StringVar(value=DEFAULT_CONFIDENCE)
    by_var = tk.StringVar(value=_current_user(gui))
    notes_var = tk.StringVar()

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Student:", ttk.Combobox(frm, textvariable=student_var,
                                     values=student_labels,
                                     state="readonly", width=40))
    subject_box = ttk.Combobox(frm, textvariable=subject_var,
                                state="readonly", width=22)
    row(1, "Subject:", subject_box)
    subject_note = ttk.Label(frm, text="", foreground="#777",
                              wraplength=320, justify="left")
    subject_note.grid(row=2, column=1, sticky="w")

    def _sync_subjects(*_args) -> None:
        """Offer the picked learner's own subjects, and nothing else.

        A prediction is matched back by subject name, so one filed
        against a subject this learner does not take satisfies nothing
        and shows up nowhere. Listing the whole college made that the
        easiest mistake on the screen.

        A learner with no subjects on record falls back to the full list
        rather than an empty picker — otherwise the dialog would refuse
        to do anything, and the fix for that lives on another screen.
        """
        sid = student_by_label.get(student_var.get())
        student = student_data.get_student(sid) if sid else None
        subjects = _student_subjects(student)
        if subjects:
            subject_note.configure(text="")
        else:
            subjects = _active_subjects()
            subject_note.configure(
                text="This learner has no A-level subjects on their "
                     "record, so every subject is offered. Set their "
                     "subjects on the student record.")
        subject_box.configure(values=subjects)
        if subject_var.get() not in subjects:
            subject_var.set(subjects[0] if subjects else "")

    student_var.trace_add("write", _sync_subjects)
    _sync_subjects()
    grade_box = ttk.Combobox(frm, textvariable=grade_var,
                             values=list(LETTER_GRADES),
                             state="readonly", width=14)
    row(3, "Grade:", grade_box)

    def _sync_grades(*_args) -> None:
        # The grade list follows the qualification of the learner's aim.
        grades = _grades_for(student_by_label.get(student_var.get()),
                             subject_var.get())
        grade_box.configure(values=grades)
        if grade_var.get() not in grades:
            grade_var.set(grades[0] if grades else "")

    subject_var.trace_add("write", _sync_grades)
    _sync_grades()
    row(4, "Confidence:", ttk.Combobox(frm, textvariable=confidence_var,
                                        values=list(CONFIDENCE_LEVELS),
                                        state="readonly", width=10))
    row(5, "Predicted by:", ttk.Entry(frm, textvariable=by_var, width=32))
    row(6, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        sid = student_by_label.get(student_var.get())
        if sid is None:
            messagebox.showerror("Cannot save",
                                 "Pick a student.", parent=win)
            return
        try:
            data.save_prediction({
                "student_id": sid,
                "subject":     subject_var.get(),
                "grade":       grade_var.get(),
                "confidence":  confidence_var.get(),
                "predicted_by": by_var.get(),
                "notes":       notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("save_prediction crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=7, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _edit_dialog(gui, prediction_id: int, on_saved) -> None:
    pred = data.get_prediction(prediction_id)
    if pred is None:
        messagebox.showerror("Not found",
                             f"No prediction #{prediction_id}",
                             parent=gui.root)
        return

    win = tk.Toplevel(gui.root)
    win.title(f"Edit prediction #{prediction_id}")
    win.transient(gui.root)
    grab_when_viewable(win)

    frm = ttk.Frame(win, padding=12)
    frm.grid()
    ttk.Label(frm,
              text=f"{pred.student_id}  ·  {pred.subject}",
              foreground="#555").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 8))

    grade_var = tk.StringVar(value=pred.grade)
    confidence_var = tk.StringVar(value=pred.confidence)
    by_var = tk.StringVar(value=pred.predicted_by or "")
    notes_var = tk.StringVar(value=pred.notes or "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Grade:", ttk.Combobox(frm, textvariable=grade_var,
                                   values=_grades_for(pred.student_id,
                                                      pred.subject),
                                   state="readonly", width=14))
    row(2, "Confidence:", ttk.Combobox(frm, textvariable=confidence_var,
                                        values=list(CONFIDENCE_LEVELS),
                                        state="readonly", width=10))
    row(3, "Predicted by:", ttk.Entry(frm, textvariable=by_var, width=32))
    row(4, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        try:
            data.update_prediction(prediction_id, {
                "grade":        grade_var.get(),
                "confidence":   confidence_var.get(),
                "predicted_by": by_var.get(),
                "notes":        notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_prediction crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Per-student tab ────────────────────────────────────────────────

def _build_entry_grid(gui, parent: ttk.Frame, student, rows,
                      *, on_saved: Callable[[], None]) -> None:
    """One row per subject the learner takes: the subject, and a grade.

    This is the whole screen for most people. A learner has three
    A-levels and needs three predictions, so the form is three lines —
    not a dialog opened three times, each one asking again which student
    and offering every subject in the college.

    Subjects are read-only: they come from the learner's record and are
    changed there. Grades default to whatever is already predicted, so
    re-opening this shows what is on file rather than an empty form.
    """
    frame = ttk.LabelFrame(parent, text="Predicted grades", padding=10)
    frame.pack(fill="x")

    subjects = _student_subjects(student)
    if not subjects:
        ttk.Label(
            frame,
            text=("No A-level subjects on this learner's record, so there "
                  "is nothing to predict. Set their subjects on the "
                  "student record first."),
            foreground="#a33", wraplength=620, justify="left",
        ).pack(anchor="w")
        return

    existing = {p.subject: p for p in rows}

    header = ttk.Frame(frame)
    header.pack(anchor="w", fill="x")
    for column, (text, width) in enumerate(
            (("Subject", 30), ("Grade", 8), ("Confidence", 12))):
        ttk.Label(header, text=text, width=width,
                  font=("", 9, "bold")).grid(row=0, column=column,
                                             sticky="w", padx=(0, 8))

    fields: list[tuple[str, tk.StringVar, tk.StringVar]] = []
    for row_index, subject in enumerate(subjects, start=1):
        current = existing.get(subject)
        grade_var = tk.StringVar(value=current.grade if current else "")
        confidence_var = tk.StringVar(
            value=(current.confidence if current else DEFAULT_CONFIDENCE))

        subject_box = ttk.Entry(header, width=30)
        subject_box.insert(0, subject)
        subject_box.configure(state="readonly")
        subject_box.grid(row=row_index, column=0, sticky="w",
                         padx=(0, 8), pady=2)
        # Blank is a real option: it means "not predicted yet", which is
        # what an empty row has to be able to stay.
        ttk.Combobox(header, textvariable=grade_var,
                     values=["", *_grades_for(student.student_id, subject)],
                     state="readonly",
                     width=12).grid(row=row_index, column=1, sticky="w",
                                    padx=(0, 8), pady=2)
        ttk.Combobox(header, textvariable=confidence_var,
                     values=list(CONFIDENCE_LEVELS), state="readonly",
                     width=10).grid(row=row_index, column=2, sticky="w",
                                    padx=(0, 8), pady=2)
        ttk.Label(header,
                  text=(f"last set by {current.predicted_by or '—'} on "
                        f"{current.updated_at}" if current else "not set"),
                  foreground="#777").grid(row=row_index, column=3,
                                          sticky="w", padx=(8, 0))
        fields.append((subject, grade_var, confidence_var))

    by_row = ttk.Frame(frame)
    by_row.pack(anchor="w", pady=(8, 0))
    by_var = tk.StringVar(value=_current_user(gui))
    ttk.Label(by_row, text="Predicted by:").pack(side="left")
    ttk.Entry(by_row, textvariable=by_var, width=28).pack(
        side="left", padx=(4, 0))

    def save() -> None:
        wanted = [(subject, grade.get().strip(), confidence.get())
                  for subject, grade, confidence in fields]
        filled = [(s, g, c) for s, g, c in wanted if g]
        if not filled:
            messagebox.showinfo(
                "Nothing to save",
                "Pick a grade for at least one subject. Leaving a grade "
                "blank leaves that subject unpredicted.",
                parent=gui.root)
            return
        saved, failed = 0, []
        for subject, grade, confidence in filled:
            try:
                data.save_prediction({
                    "student_id":   student.student_id,
                    "subject":      subject,
                    "grade":        grade,
                    "confidence":   confidence,
                    "predicted_by": by_var.get().strip(),
                })
                saved += 1
            except ValidationError as e:
                failed.append(f"{subject}: {e}")
            except Exception as e:
                logger.exception("save_prediction crashed for %s", subject)
                failed.append(f"{subject}: {e}")
        # Reported per subject rather than as one verdict: three saves
        # can half-succeed, and "it failed" would be a lie about the two
        # that went in.
        if failed:
            messagebox.showerror(
                "Some grades were not saved",
                f"Saved {saved} of {len(filled)}.\n\n" + "\n".join(failed),
                parent=gui.root)
        else:
            gui.status_var.set(
                f"Saved {saved} predicted grade(s) for "
                f"{student.student_id}")
        on_saved()

    ttk.Button(frame, text="Save predicted grades",
               command=save).pack(anchor="w", pady=(8, 0))

    requirement = _ucas_requirement(student.student_id)
    if requirement is not None:
        message, colour = requirement
        ttk.Label(frame, text=message, foreground=colour,
                  wraplength=620, justify="left").pack(anchor="w",
                                                       pady=(8, 0))
        ttk.Button(frame, text="Open University & UCAS",
                   command=lambda: _open_university_ucas(gui)
                   ).pack(anchor="w", pady=(4, 0))


def _open_university_ucas(gui) -> None:
    """Through to the screen these are needed by."""
    try:
        from education_system.systems.sixth_form.interfaces.gui.progression.university import (
            window as university_window,
        )
    except Exception as exc:
        logger.exception("Could not load the University & UCAS window")
        messagebox.showerror(
            "University & UCAS",
            f"Could not open it: {exc}", parent=gui.root)
        return
    university_window.open_window(gui)


def _build_student_tab(gui, parent: ttk.Frame) -> None:
    students = student_data.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {lbl: s.student_id for lbl, s in zip(labels, students)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    student_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Combobox(bar, textvariable=student_var, values=labels,
                 state="readonly", width=42
                 ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, pady=(0, 8))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        for w in actions.winfo_children():
            w.destroy()
        sid = student_by_label.get(student_var.get())
        if sid is None:
            ttk.Label(holder, text="Pick a student.",
                      foreground="#a33").pack(anchor="w")
            return
        student = student_data.get_student(sid)
        ttk.Label(holder,
                  text=f"{student.student_id}  {student.full_name}"
                  if student else f"{sid} (deleted)",
                  font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))

        try:
            rows = data.predictions_for_student(sid)
        except Exception as e:
            logger.exception("predictions_for_student failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        _build_entry_grid(gui, holder, student, rows, on_saved=render)

        # A distinct name, not a rebinding of ``holder``: assigning to it
        # here would make it local to ``render`` and unbind the closure
        # the function opens with.
        history = ttk.LabelFrame(holder, text="All predictions on file",
                                 padding=8)
        history.pack(fill="both", expand=True, pady=(10, 0))

        if not rows:
            ttk.Label(history, text="(no predictions yet)",
                      foreground="#555").pack(anchor="w")
        else:
            cols = ("prediction_id", "subject", "grade", "confidence",
                    "predicted_by", "updated_at")
            headings = {
                "prediction_id": ("#",          50),
                "subject":       ("Subject",   200),
                "grade":         ("Grade",      60),
                "confidence":    ("Confidence", 90),
                "predicted_by":  ("By",         140),
                "updated_at":    ("Updated",   140),
            }
            tree = ttk.Treeview(history, columns=cols, show="headings", height=10)
            for col in cols:
                text, width = headings[col]
                tree.heading(col, text=text)
                tree.column(col, width=width, anchor="w")
            vs = ttk.Scrollbar(history, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vs.set)
            tree.pack(side="left", fill="both", expand=True)
            vs.pack(side="right", fill="y")
            for p in rows:
                tree.insert("", "end", iid=str(p.prediction_id), values=(
                    p.prediction_id, p.subject, p.grade, p.confidence,
                    p.predicted_by or "—", p.updated_at,
                ))

            def _selected() -> int | None:
                sel = tree.selection()
                return int(sel[0]) if sel else None

            def _edit() -> None:
                pid = _selected()
                if pid is None:
                    messagebox.showinfo("No selection",
                                        "Pick a prediction.", parent=gui.root)
                    return
                _edit_dialog(gui, pid, on_saved=render)

            def _delete() -> None:
                pid = _selected()
                if pid is None:
                    messagebox.showinfo("No selection",
                                        "Pick a prediction.", parent=gui.root)
                    return
                if not messagebox.askyesno(
                    "Delete prediction",
                    f"Delete prediction #{pid}?",
                    parent=gui.root,
                ):
                    return
                try:
                    data.delete_prediction(pid)
                except Exception as e:
                    logger.exception("delete_prediction crashed")
                    messagebox.showerror("Error", f"Could not delete: {e}",
                                         parent=gui.root)
                    return
                render()

            ttk.Button(actions, text="Edit",
                       command=_edit).pack(side="left", padx=(0, 6))
            ttk.Button(actions, text="Delete",
                       command=_delete).pack(side="left", padx=(0, 6))
            tree.bind("<Double-1>", lambda _e: _edit())

        ttk.Button(actions, text="New / Update",
                   command=lambda: _new_dialog(gui, on_saved=render)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions, text="Refresh",
                   command=render).pack(side="left")
        gui.status_var.set(f"Predictions for {sid}: {len(rows)} row(s)")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if labels:
        render()
    else:
        ttk.Label(holder, text="No students yet.",
                  foreground="#a33").pack(anchor="w")


# ─── Group sheet tab ────────────────────────────────────────────────

def _build_group_tab(gui, parent: ttk.Frame) -> None:
    groups = cg_data.list_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    labels = [_group_label(g, courses_by_id.get(g.course_id)) for g in groups]
    group_by_label = {lbl: g.group_id for lbl, g in zip(labels, groups)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    group_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Group:").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var, values=labels,
                 state="readonly", width=42
                 ).pack(side="left", padx=(4, 12))

    by_var = tk.StringVar(
        value=(gui.auth.current_user or {}).get("display_name", "")
              if hasattr(gui, "auth") and gui.auth else "")
    ttk.Label(bar, text="Predicted by:").pack(side="left")
    ttk.Entry(bar, textvariable=by_var, width=22).pack(side="left", padx=(4, 8))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, pady=(0, 8))

    row_state: dict[str, dict[str, Any]] = {}

    def load() -> None:
        nonlocal row_state
        for w in holder.winfo_children():
            w.destroy()
        row_state = {}
        gid = group_by_label.get(group_var.get())
        if gid is None:
            ttk.Label(holder, text="Pick a group.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            subject, view = data.group_prediction_view(gid)
        except Exception as e:
            logger.exception("group_prediction_view failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        if subject is None:
            ttk.Label(
                holder,
                text=("Group has no parent course/subject — "
                      "predictions can't be auto-targeted."),
                foreground="#a33",
            ).pack(anchor="w")
            return
        if not view:
            ttk.Label(holder, text="Group has no members.",
                      foreground="#a33").pack(anchor="w")
            return

        ttk.Label(holder, text=f"Subject: {subject}",
                  font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))

        header = ttk.Frame(holder)
        header.pack(fill="x")
        for text, width in [
            ("Student ID",  12), ("Name", 30),
            ("Grade", 8), ("Confidence", 14), ("Notes", 30),
        ]:
            ttk.Label(header, text=text, font=("", 10, "bold"),
                      width=width, anchor="w").pack(side="left", padx=2)

        for v in view:
            row = ttk.Frame(holder)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=v.student_id, width=12, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=v.full_name, width=30, anchor="w"
                      ).pack(side="left", padx=2)

            grade_var = tk.StringVar(
                value=v.prediction.grade if v.prediction else "")
            conf_var = tk.StringVar(
                value=v.prediction.confidence if v.prediction else DEFAULT_CONFIDENCE)
            notes_var = tk.StringVar(
                value=(v.prediction.notes or "") if v.prediction else "")

            ttk.Combobox(row, textvariable=grade_var,
                         values=["", *LETTER_GRADES],
                         state="readonly", width=6
                         ).pack(side="left", padx=2)
            ttk.Combobox(row, textvariable=conf_var,
                         values=list(CONFIDENCE_LEVELS),
                         state="readonly", width=12
                         ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=notes_var, width=30
                      ).pack(side="left", padx=2)

            row_state[v.student_id] = {
                "grade": grade_var,
                "confidence": conf_var,
                "notes": notes_var,
            }
        gui.status_var.set(
            f"Group sheet: {len(view)} student(s), subject {subject}")

    def submit() -> None:
        gid = group_by_label.get(group_var.get())
        if gid is None:
            messagebox.showerror("Cannot save",
                                 "Pick a group.", parent=gui.root)
            return
        if not row_state:
            messagebox.showinfo("Nothing to save",
                                "Load the sheet first.", parent=gui.root)
            return
        payload = {}
        for sid, vs in row_state.items():
            grade = vs["grade"].get().strip()
            if not grade:
                continue
            payload[sid] = {
                "grade":       grade,
                "confidence":  vs["confidence"].get(),
                "notes":       vs["notes"].get(),
                "predicted_by": by_var.get(),
            }
        if not payload:
            messagebox.showinfo("Nothing to save",
                                "No grades filled in.", parent=gui.root)
            return
        try:
            n = data.save_group_predictions(gid, payload)
        except ValidationError as e:
            logger.warning("save_group_predictions rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_group_predictions crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        messagebox.showinfo("Saved",
                            f"Saved {n} prediction(s).",
                            parent=gui.root)
        gui.status_var.set(f"Saved {n} prediction(s)")
        load()

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))
    ttk.Button(actions, text="Load", command=load).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save predictions", command=submit
               ).pack(side="left", padx=(0, 6))
    if labels:
        load()
    else:
        ttk.Label(holder, text="No class groups yet.",
                  foreground="#a33").pack(anchor="w")
