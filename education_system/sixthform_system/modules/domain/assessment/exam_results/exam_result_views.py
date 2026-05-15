"""GUI panels for Sixth Form Results Day.

Four-tab Notebook:

  * Directory  — filterable list of every recorded result.
  * Bulk sheet — pick a paper (code/season/year), enter grades + marks
    + UMS for every entered candidate in one go.
  * Per-student — pick a student, see all their results.
  * Distribution — grade-distribution table for a series filter.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.assessment.exam_entries import exam_entries
from education_system.sixthform_system.modules.domain.assessment.exam_results import exam_results
from education_system.sixthform_system.modules.domain.students.students import students
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as entries_data
from education_system.sixthform_system.modules.domain.assessment.exam_results import exam_results as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.sixthform_system.modules.domain.assessment.exam_entries.exam_entries import SEASONS
from education_system.sixthform_system.modules.domain.assessment.exam_results.exam_results import (
    GradeDistribution,
    ResultEntryView,
    ResultRow,
    StudentResultsSummary,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.assessment.gradebook.gradebook import LETTER_GRADES
from education_system.sixthform_system.modules.domain.students.students.students import A_LEVEL_SUBJECTS
from education_system.sixthform_system.modules.domain.academics.subjects.subjects import EXAM_BOARDS

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


def _default_year() -> int:
    today = _date.today()
    return today.year if today.month < 9 else today.year + 1


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Results Day")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    bulk_tab = ttk.Frame(nb, padding=8)
    student_tab = ttk.Frame(nb, padding=8)
    dist_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(bulk_tab,    text="Bulk sheet")
    nb.add(student_tab, text="Per-student")
    nb.add(dist_tab,    text="Distribution")

    _build_directory_tab(gui, dir_tab)
    _build_bulk_tab(gui, bulk_tab)
    _build_student_tab(gui, student_tab)
    _build_distribution_tab(gui, dist_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    subject_var = tk.StringVar()
    board_var = tk.StringVar()
    season_var = tk.StringVar()
    year_var = tk.StringVar()
    grade_var = tk.StringVar()

    ttk.Label(filt, text="Student:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Subject:").pack(side="left")
    ttk.Combobox(filt, textvariable=subject_var,
                 values=["", *_active_subjects()],
                 state="readonly", width=18
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Board:").pack(side="left")
    ttk.Combobox(filt, textvariable=board_var,
                 values=["", *EXAM_BOARDS], state="readonly", width=12
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Season:").pack(side="left")
    ttk.Combobox(filt, textvariable=season_var,
                 values=["", *SEASONS], state="readonly", width=10
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Year:").pack(side="left")
    ttk.Entry(filt, textvariable=year_var, width=6
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Grade:").pack(side="left")
    ttk.Combobox(filt, textvariable=grade_var,
                 values=["", *LETTER_GRADES], state="readonly", width=6
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
            yr = int(year_var.get()) if year_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Bad filter",
                                 "Year must be a number.", parent=gui.root)
            return
        try:
            rows = data.list_results(
                student_id=sid_var.get().strip() or None,
                subject=subject_var.get().strip() or None,
                exam_board=board_var.get().strip() or None,
                season=season_var.get().strip() or None,
                year=yr,
                grade=grade_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_results failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("result_id", "student", "subject", "board",
                "paper", "season", "year",
                "grade", "marks", "ums", "released")
        headings = {
            "result_id": ("#",        50),
            "student":   ("Student", 100),
            "subject":   ("Subject", 140),
            "board":     ("Board",    90),
            "paper":     ("Paper",   100),
            "season":    ("Season",   80),
            "year":      ("Year",     50),
            "grade":     ("Grade",    60),
            "marks":     ("Marks",    60),
            "ums":       ("UMS",      60),
            "released":  ("Released", 100),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for r in rows:
            tree.insert("", "end", iid=str(r.result.result_id), values=(
                r.result.result_id, r.student_id, r.subject,
                r.exam_board, r.paper_code, r.season, r.year,
                r.result.grade,
                r.result.marks if r.result.marks is not None else "—",
                r.result.ums if r.result.ums is not None else "—",
                r.result.released_at or "—",
            ))
        summary.configure(text=f"{len(rows)} result(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection",
                                    "Pick a result first.", parent=gui.root)
            return rid

        def _edit() -> None:
            rid = _require()
            if rid is None:
                return
            _edit_dialog(gui, rid, on_saved=refresh)

        def _delete() -> None:
            rid = _require()
            if rid is None:
                return
            r = data.get_result(rid)
            if r is None:
                return
            if not messagebox.askyesno(
                "Delete result",
                f"Delete result #{rid}?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_result(rid)
            except Exception as e:
                logger.exception("delete_result crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Edit",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: _new_dialog(gui, on_saved=refresh)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"Results: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), subject_var.set(""),
                                board_var.set(""), season_var.set(""),
                                year_var.set(""), grade_var.set(""),
                                refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def _new_dialog(gui, on_saved) -> None:
    entries = entries_data.list_entries()
    if not entries:
        messagebox.showinfo("No entries",
                            "Create an exam entry first.", parent=gui.root)
        return
    win = tk.Toplevel(gui.root)
    win.title("New Result")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    entry_labels = [
        f"#{e.entry_id}  {e.student_id}  {e.paper_code}  "
        f"({e.season} {e.year})" for e in entries
    ]
    entry_by_label = {lbl: e.entry_id for lbl, e in zip(entry_labels, entries)}

    entry_var = tk.StringVar(value=entry_labels[0])
    grade_var = tk.StringVar(value=LETTER_GRADES[0])
    marks_var = tk.StringVar()
    ums_var = tk.StringVar()
    released_var = tk.StringVar()
    notes_var = tk.StringVar()

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Entry:", ttk.Combobox(frm, textvariable=entry_var,
                                   values=entry_labels,
                                   state="readonly", width=44))
    row(1, "Grade:", ttk.Combobox(frm, textvariable=grade_var,
                                   values=list(LETTER_GRADES),
                                   state="readonly", width=6))
    row(2, "Marks:", ttk.Entry(frm, textvariable=marks_var, width=8))
    row(3, "UMS:", ttk.Entry(frm, textvariable=ums_var, width=8))
    row(4, "Released at:",
        ttk.Entry(frm, textvariable=released_var, width=14))
    row(5, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        eid = entry_by_label.get(entry_var.get())
        if eid is None:
            messagebox.showerror("Cannot save",
                                 "Pick an entry.", parent=win)
            return
        try:
            data.save_result({
                "entry_id":   eid,
                "grade":      grade_var.get(),
                "marks":      marks_var.get(),
                "ums":        ums_var.get(),
                "released_at": released_var.get(),
                "notes":      notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("save_result crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _edit_dialog(gui, result_id: int, on_saved) -> None:
    r = data.get_result(result_id)
    if r is None:
        messagebox.showerror("Not found", f"No result #{result_id}",
                             parent=gui.root)
        return
    entry = entries_data.get_entry(r.entry_id)

    win = tk.Toplevel(gui.root)
    win.title(f"Edit result #{result_id}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()
    ttk.Label(
        frm,
        text=(f"Entry #{r.entry_id}  ·  "
              + (f"{entry.student_id} on {entry.paper_code} "
                 f"({entry.season} {entry.year})" if entry else "(deleted)")),
        foreground="#555",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    grade_var = tk.StringVar(value=r.grade)
    marks_var = tk.StringVar(
        value=str(r.marks) if r.marks is not None else "")
    ums_var = tk.StringVar(
        value=str(r.ums) if r.ums is not None else "")
    released_var = tk.StringVar(value=r.released_at or "")
    notes_var = tk.StringVar(value=r.notes or "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Grade:", ttk.Combobox(frm, textvariable=grade_var,
                                   values=list(LETTER_GRADES),
                                   state="readonly", width=6))
    row(2, "Marks:", ttk.Entry(frm, textvariable=marks_var, width=8))
    row(3, "UMS:", ttk.Entry(frm, textvariable=ums_var, width=8))
    row(4, "Released at:",
        ttk.Entry(frm, textvariable=released_var, width=14))
    row(5, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        try:
            data.update_result(result_id, {
                "grade":      grade_var.get(),
                "marks":      marks_var.get(),
                "ums":        ums_var.get(),
                "released_at": released_var.get(),
                "notes":      notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_result crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Bulk sheet tab ─────────────────────────────────────────────────

def _build_bulk_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    paper_var = tk.StringVar()
    season_var = tk.StringVar(value=SEASONS[0])
    year_var = tk.StringVar(value=str(_default_year()))
    released_var = tk.StringVar()

    ttk.Label(bar, text="Paper code:").pack(side="left")
    ttk.Entry(bar, textvariable=paper_var, width=14
              ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Season:").pack(side="left")
    ttk.Combobox(bar, textvariable=season_var, values=list(SEASONS),
                 state="readonly", width=10
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Year:").pack(side="left")
    ttk.Entry(bar, textvariable=year_var, width=6
              ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Released at:").pack(side="left")
    ttk.Entry(bar, textvariable=released_var, width=14
              ).pack(side="left", padx=(4, 4))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, pady=(0, 8))

    row_state: dict[int, dict[str, Any]] = {}

    def load() -> None:
        for w in holder.winfo_children():
            w.destroy()
        row_state.clear()
        paper = paper_var.get().strip().upper()
        season = season_var.get().strip()
        try:
            year = int(year_var.get())
        except ValueError:
            messagebox.showerror("Bad input",
                                 "Year must be a number.", parent=gui.root)
            return
        if not paper:
            ttk.Label(holder, text="Enter a paper code.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            view = data.bulk_view(paper, season, year)
        except ValidationError as e:
            ttk.Label(holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("bulk_view failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        if not view:
            ttk.Label(
                holder,
                text=(f"No candidates entered for {paper} ({season} {year})."),
                foreground="#a33",
            ).pack(anchor="w")
            return

        ttk.Label(
            holder,
            text=(f"{paper}  ·  {season} {year}  ·  "
                  f"{len(view)} candidate(s)"),
            font=("", 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        header = ttk.Frame(holder)
        header.pack(fill="x")
        for text, width in [
            ("Entry #",  8), ("Student",  12), ("Name",  26),
            ("Cand #",   8), ("Status",  10),
            ("Grade",    7), ("Marks",    7), ("UMS",  6), ("Notes", 22),
        ]:
            ttk.Label(header, text=text, font=("", 10, "bold"),
                      width=width, anchor="w").pack(side="left", padx=2)

        for v in view:
            row = ttk.Frame(holder)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=str(v.entry_id), width=8, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=v.student_id, width=12, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=v.full_name, width=26, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=(v.candidate_no or "—"), width=8, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=v.status, width=10, anchor="w",
                      foreground=("#a33" if v.status == "Withdrawn" else "#000")
                      ).pack(side="left", padx=2)

            grade_var = tk.StringVar(
                value=v.result.grade if v.result else "")
            marks_var = tk.StringVar(
                value=str(v.result.marks)
                if v.result and v.result.marks is not None else "")
            ums_var = tk.StringVar(
                value=str(v.result.ums)
                if v.result and v.result.ums is not None else "")
            notes_var = tk.StringVar(
                value=(v.result.notes or "") if v.result else "")

            ttk.Combobox(row, textvariable=grade_var,
                         values=["", *LETTER_GRADES],
                         state="readonly", width=5
                         ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=marks_var, width=7
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=ums_var, width=6
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=notes_var, width=22
                      ).pack(side="left", padx=2)
            row_state[v.entry_id] = {
                "grade": grade_var, "marks": marks_var,
                "ums": ums_var, "notes": notes_var,
            }
        gui.status_var.set(
            f"Results sheet loaded: {paper} ({len(view)} candidate(s))")

    def submit() -> None:
        if not row_state:
            messagebox.showinfo("Nothing to save",
                                "Load a paper first.", parent=gui.root)
            return
        paper = paper_var.get().strip().upper()
        season = season_var.get().strip()
        try:
            year = int(year_var.get())
        except ValueError:
            messagebox.showerror("Bad input",
                                 "Year must be a number.", parent=gui.root)
            return
        payload = {eid: {k: v.get() for k, v in vs.items()}
                   for eid, vs in row_state.items()}
        try:
            n = data.save_bulk(
                paper_code=paper, season=season, year=year,
                released_at=released_var.get() or None,
                entries=payload,
            )
        except ValidationError as e:
            logger.warning("save_bulk rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_bulk crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        messagebox.showinfo("Saved", f"Saved {n} result(s).",
                            parent=gui.root)
        gui.status_var.set(f"Saved {n} results")
        load()

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))
    ttk.Button(actions, text="Load", command=load
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save results", command=submit
               ).pack(side="left", padx=(0, 6))


# ─── Per-student tab ────────────────────────────────────────────────

def _build_student_tab(gui, parent: ttk.Frame) -> None:
    students = student_data.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in students]
    by_label = {lbl: s.student_id for lbl, s in zip(labels, students)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    student_var = tk.StringVar(value=labels[0] if labels else "")
    year_var = tk.StringVar()
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Combobox(bar, textvariable=student_var, values=labels,
                 state="readonly", width=42
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Year (optional):").pack(side="left")
    ttk.Entry(bar, textvariable=year_var, width=6
              ).pack(side="left", padx=(4, 4))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, pady=(0, 8))
    summary_label = ttk.Label(parent, text="", foreground="#333")
    summary_label.pack(anchor="w", pady=(8, 0))

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        sid = by_label.get(student_var.get())
        if not sid:
            ttk.Label(holder, text="Pick a student.",
                      foreground="#a33").pack(anchor="w")
            summary_label.configure(text="")
            return
        try:
            yr = int(year_var.get()) if year_var.get().strip() else None
        except ValueError:
            ttk.Label(holder, text="Year must be a number.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            rows = data.results_for_student(sid, year=yr)
            summ = data.per_student_summary(sid, year=yr)
        except ValidationError as e:
            ttk.Label(holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        student = student_data.get_student(sid)
        ttk.Label(
            holder,
            text=f"{student.student_id}  {student.full_name}"
                 if student else f"{sid} (deleted)",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        if not rows:
            ttk.Label(holder, text="(no results)",
                      foreground="#555").pack(anchor="w")
            summary_label.configure(text="")
            return

        cols = ("result_id", "subject", "board", "paper",
                "season", "year", "grade", "marks", "ums")
        headings = {
            "result_id": ("#",       50),
            "subject":   ("Subject", 160),
            "board":     ("Board",    90),
            "paper":     ("Paper",   100),
            "season":    ("Season",   80),
            "year":      ("Year",     60),
            "grade":     ("Grade",    60),
            "marks":     ("Marks",    60),
            "ums":       ("UMS",      60),
        }
        tree = ttk.Treeview(holder, columns=cols,
                            show="headings", height=12)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for r in rows:
            tree.insert("", "end", iid=str(r.result.result_id), values=(
                r.result.result_id, r.subject, r.exam_board, r.paper_code,
                r.season, r.year, r.result.grade,
                r.result.marks if r.result.marks is not None else "—",
                r.result.ums if r.result.ums is not None else "—",
            ))

        # Per-letter counts
        parts = [f"{g}={summ.by_grade.get(g, 0)}"
                 for g in LETTER_GRADES if summ.by_grade.get(g)]
        summary_label.configure(text=(
            f"Total results: {summ.total}  ·  "
            f"Best: {summ.best or '—'}  ·  Worst: {summ.worst or '—'}"
            + (f"  ·  Breakdown: {' '.join(parts)}" if parts else "")
        ))
        gui.status_var.set(f"Results for {sid}: {len(rows)} row(s)")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if labels:
        render()
    else:
        ttk.Label(holder, text="No students yet.",
                  foreground="#a33").pack(anchor="w")


# ─── Distribution tab ───────────────────────────────────────────────

def _build_distribution_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    subject_var = tk.StringVar()
    board_var = tk.StringVar()
    season_var = tk.StringVar()
    year_var = tk.StringVar(value=str(_default_year()))

    ttk.Label(bar, text="Subject:").pack(side="left")
    ttk.Combobox(bar, textvariable=subject_var,
                 values=["", *_active_subjects()],
                 state="readonly", width=20
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Board:").pack(side="left")
    ttk.Combobox(bar, textvariable=board_var,
                 values=["", *EXAM_BOARDS], state="readonly", width=12
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Season:").pack(side="left")
    ttk.Combobox(bar, textvariable=season_var,
                 values=["", *SEASONS], state="readonly", width=10
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Year:").pack(side="left")
    ttk.Entry(bar, textvariable=year_var, width=6
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    summary_label = ttk.Label(parent, text="", foreground="#333")
    summary_label.pack(anchor="w", pady=(8, 0))

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            yr = int(year_var.get()) if year_var.get().strip() else None
        except ValueError:
            ttk.Label(holder, text="Year must be a number.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            dist = data.grade_distribution(
                subject=subject_var.get().strip() or None,
                exam_board=board_var.get().strip() or None,
                season=season_var.get().strip() or None,
                year=yr,
            )
        except ValidationError as e:
            ttk.Label(holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        ttk.Label(holder, text=f"Total results: {dist.total}",
                  font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))
        if not dist.total:
            summary_label.configure(text="")
            return

        # Render an ascii bar chart for visual punch
        max_count = max(dist.counts.get(g, 0) for g in LETTER_GRADES)
        chart = ttk.Frame(holder)
        chart.pack(anchor="w", pady=(4, 4))
        for g in LETTER_GRADES:
            n = dist.counts.get(g, 0)
            pct = round(100.0 * n / dist.total, 1) if dist.total else 0.0
            bar_len = int((n / max_count) * 40) if max_count else 0
            row = ttk.Frame(chart)
            row.pack(anchor="w", pady=1)
            ttk.Label(row, text=f"{g:<2}", width=3, anchor="w",
                      font=("", 10, "bold")).pack(side="left")
            ttk.Label(row, text="█" * bar_len, foreground="#258"
                      ).pack(side="left")
            ttk.Label(row, text=f"  {n}  ({pct}%)",
                      foreground="#555").pack(side="left")

        summary_label.configure(text=(
            f"Pass (A*-E): {dist.pass_count}  ·  "
            f"Pass rate: {dist.pass_rate}%  ·  "
            f"A*-A: {dist.top_rate}%"
        ))
        gui.status_var.set("Distribution loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
