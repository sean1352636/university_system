"""GUI panels for Sixth Form Predicted Grades.

Three-tab Notebook:

* Directory — filterable list of every prediction.
* Per-student — pick a student, see all their predictions, edit
  inline.
* Group sheet — pick a class group, render its roster, set predictions
  for the group's subject in one go.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups
from education_system.sixthform_system.modules.domain.academics.courses import courses
from education_system.sixthform_system.modules.domain.assessment.predicted_grades import predicted_grades
from education_system.sixthform_system.modules.domain.students.students import students
from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups as cg_data
from education_system.sixthform_system.modules.domain.academics.courses import courses as course_data
from education_system.sixthform_system.modules.domain.assessment.predicted_grades import predicted_grades as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.sixthform_system.modules.domain.assessment.gradebook.gradebook import LETTER_GRADES
from education_system.sixthform_system.modules.domain.assessment.predicted_grades.predicted_grades import (
    CONFIDENCE_LEVELS,
    DEFAULT_CONFIDENCE,
    Prediction,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students.students import A_LEVEL_SUBJECTS

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


def _group_label(g, course=None) -> str:
    if course is None:
        course = course_data.get_course(g.course_id)
    code = course.course_code if course else f"#{g.course_id}"
    return f"#{g.group_id} {g.group_name} ({code})"


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Predicted Grades")

    nb = ttk.Notebook(frame)
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
                 values=["", *LETTER_GRADES], state="readonly", width=6
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
    win.after_idle(win.grab_set)

    frm = ttk.Frame(win, padding=12)
    frm.grid()

    student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                        for s in students}
    student_var = tk.StringVar(value=student_labels[0])
    subject_var = tk.StringVar(value=_active_subjects()[0] if _active_subjects() else "")
    grade_var = tk.StringVar(value=LETTER_GRADES[0])
    confidence_var = tk.StringVar(value=DEFAULT_CONFIDENCE)
    by_var = tk.StringVar(
        value=(gui.auth.current_user or {}).get("display_name", "")
              if hasattr(gui, "auth") and gui.auth else "")
    notes_var = tk.StringVar()

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Student:", ttk.Combobox(frm, textvariable=student_var,
                                     values=student_labels,
                                     state="readonly", width=40))
    row(1, "Subject:", ttk.Combobox(frm, textvariable=subject_var,
                                     values=_active_subjects(),
                                     state="readonly", width=22))
    row(2, "Grade:", ttk.Combobox(frm, textvariable=grade_var,
                                   values=list(LETTER_GRADES),
                                   state="readonly", width=6))
    row(3, "Confidence:", ttk.Combobox(frm, textvariable=confidence_var,
                                        values=list(CONFIDENCE_LEVELS),
                                        state="readonly", width=10))
    row(4, "Predicted by:", ttk.Entry(frm, textvariable=by_var, width=32))
    row(5, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

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
    bar.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")
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
    win.after_idle(win.grab_set)

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
                                   values=list(LETTER_GRADES),
                                   state="readonly", width=6))
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

        if not rows:
            ttk.Label(holder, text="(no predictions yet)",
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
            tree = ttk.Treeview(holder, columns=cols, show="headings", height=10)
            for col in cols:
                text, width = headings[col]
                tree.heading(col, text=text)
                tree.column(col, width=width, anchor="w")
            vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
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
