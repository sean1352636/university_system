"""GUI panels for Sixth Form Mock Exams.

Three-tab Notebook:

  * Mocks — filterable directory + CRUD on mock-exam papers.
  * Results — pick a mock, render its subject roster, enter marks +
    optional letter override + notes in one go.
  * Summary — per-student summary for a chosen subject + date range.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.systems.sixth_form.domain.assessment.mock_exams import mock_exams
from education_system.systems.sixth_form.domain.learners.students import students
from education_system.systems.sixth_form.domain.assessment.mock_exams import mock_exams as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.academics.subjects import subjects as subjects_data
from education_system.systems.sixth_form.domain.assessment.gradebook.gradebook import LETTER_GRADES
from education_system.systems.sixth_form.domain.assessment.mock_exams.mock_exams import (
    MockExam,
    ResultView,
    StudentMockSummary,
    ValidationError,
    derived_pct,
    effective_grade,
)
from education_system.systems.sixth_form.domain.learners.students.students import A_LEVEL_SUBJECTS
from education_system.systems.sixth_form.domain.academics.subjects.subjects import EXAM_BOARDS

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


def _today() -> str:
    return _date.today().isoformat()


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Mock Exams")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    mocks_tab = ttk.Frame(nb, padding=8)
    results_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(mocks_tab,   text="Mocks")
    nb.add(results_tab, text="Results")
    nb.add(summary_tab, text="Summary")

    _build_mocks_tab(gui, mocks_tab)
    _build_results_tab(gui, results_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Mocks tab ──────────────────────────────────────────────────────

def _build_mocks_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    subject_var = tk.StringVar()
    board_var = tk.StringVar()
    from_var = tk.StringVar()
    to_var = tk.StringVar()
    search_var = tk.StringVar()

    ttk.Label(filt, text="Subject:").pack(side="left")
    ttk.Combobox(filt, textvariable=subject_var,
                 values=["", *_active_subjects()],
                 state="readonly", width=22
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Exam board:").pack(side="left")
    ttk.Combobox(filt, textvariable=board_var,
                 values=["", *EXAM_BOARDS], state="readonly", width=14
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="From:").pack(side="left")
    ttk.Entry(filt, textvariable=from_var, width=12
              ).pack(side="left", padx=(4, 8))
    ttk.Label(filt, text="to:").pack(side="left")
    ttk.Entry(filt, textvariable=to_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=search_var, width=14
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
            rows = data.list_mocks(
                subject=subject_var.get().strip() or None,
                exam_board=board_var.get().strip() or None,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
                search=search_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_mocks failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("mock_id", "title", "subject", "board",
                "paper", "date_sat", "max")
        headings = {
            "mock_id":  ("#",     50),
            "title":    ("Title", 280),
            "subject":  ("Subject", 180),
            "board":    ("Board",  100),
            "paper":    ("Paper",   60),
            "date_sat": ("Date sat", 100),
            "max":      ("Max",     60),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings",
                            height=12)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for m in rows:
            tree.insert("", "end", iid=str(m.mock_id), values=(
                m.mock_id, m.title, m.subject,
                m.exam_board or "—",
                m.paper_number if m.paper_number is not None else "—",
                m.date_sat, m.max_marks,
            ))
        summary.configure(text=f"{len(rows)} mock exam(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            mid = _selected()
            if mid is None:
                messagebox.showinfo("No selection",
                                    "Pick a mock first.", parent=gui.root)
            return mid

        ttk.Button(actions_holder, text="View",
                   command=lambda: (_require() and open_profile(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Edit",
                   command=lambda: (_require() and
                                    open_edit_mock(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Results",
                   command=lambda: (_require() and
                                    open_results_sheet(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=lambda: (_require() and
                                    _delete_with_confirm(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_add_mock(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>",
                  lambda _e: (_selected() and open_profile(gui, _selected())))
        gui.status_var.set(f"Mocks: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (subject_var.set(""), board_var.set(""),
                                from_var.set(""), to_var.set(""),
                                search_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Add / edit form ────────────────────────────────────────────────

def _mock_form(
    gui,
    *,
    title: str,
    existing: MockExam | None,
    on_save: Callable[[dict[str, Any]], MockExam],
) -> None:
    frame = _clear(gui)
    _heading(frame, title)

    is_edit = existing is not None

    title_var = tk.StringVar(value=existing.title if is_edit else "")
    subject_var = tk.StringVar(
        value=existing.subject if is_edit else (
            _active_subjects()[0] if _active_subjects() else ""))
    board_var = tk.StringVar(
        value=(existing.exam_board or "") if is_edit else "")
    paper_var = tk.StringVar(
        value=str(existing.paper_number)
        if (is_edit and existing.paper_number is not None) else "")
    date_var = tk.StringVar(value=existing.date_sat if is_edit else _today())
    dur_var = tk.StringVar(
        value=str(existing.duration_minutes)
        if (is_edit and existing.duration_minutes is not None) else "")
    max_var = tk.StringVar(
        value=str(existing.max_marks) if is_edit else "100")

    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    form.columnconfigure(1, weight=1, minsize=320)

    notes_text = tk.Text(form, height=4, width=60)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    row(0, "Title *", ttk.Entry(form, textvariable=title_var))
    row(1, "Subject *", ttk.Combobox(
        form, textvariable=subject_var, values=_active_subjects(),
        state="readonly", width=28))
    row(2, "Exam board", ttk.Combobox(
        form, textvariable=board_var, values=["", *EXAM_BOARDS],
        state="readonly", width=18))
    row(3, "Paper number", ttk.Entry(form, textvariable=paper_var, width=8))
    row(4, "Date sat * (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=date_var, width=14))
    row(5, "Duration (mins)",
        ttk.Entry(form, textvariable=dur_var, width=8))
    row(6, "Max marks *",
        ttk.Entry(form, textvariable=max_var, width=10))
    ttk.Label(form, text="Notes").grid(
        row=7, column=0, sticky="ne", padx=(0, 8), pady=4)
    notes_text.grid(row=7, column=1, sticky="ew", pady=4)
    if is_edit and existing.notes:
        notes_text.insert("1.0", existing.notes)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    def submit() -> None:
        payload = {
            "title":            title_var.get(),
            "subject":          subject_var.get(),
            "exam_board":       board_var.get(),
            "paper_number":     paper_var.get(),
            "date_sat":         date_var.get(),
            "duration_minutes": dur_var.get(),
            "max_marks":        max_var.get(),
            "notes":            notes_text.get("1.0", "end").strip(),
        }
        try:
            saved = on_save(payload)
        except ValidationError as e:
            logger.warning("mock form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save mock crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        logger.info("GUI saved mock #%d via %s", saved.mock_id, title)
        gui.status_var.set(f"Saved mock #{saved.mock_id}")
        open_profile(gui, saved.mock_id)

    ttk.Button(bar, text="Save", command=submit
               ).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")


def open_add_mock(gui) -> None:
    def on_save(p):
        return data.create_mock(p)
    _mock_form(gui, title="New Mock Exam", existing=None, on_save=on_save)


def open_edit_mock(gui, mock_id: int) -> None:
    m = data.get_mock(mock_id)
    if m is None:
        messagebox.showerror("Not found", f"No mock #{mock_id}",
                             parent=gui.root)
        return
    def on_save(p):
        return data.update_mock(mock_id, p)
    _mock_form(gui, title=f"Edit Mock — {m.title}",
               existing=m, on_save=on_save)


# ─── Profile ────────────────────────────────────────────────────────

def open_profile(gui, mock_id: int) -> None:
    frame = _clear(gui)
    _heading(frame, f"Mock Exam #{mock_id}")
    m = data.get_mock(mock_id)
    if m is None:
        ttk.Label(frame, text="No such mock.",
                  foreground="#a33").pack(anchor="w")
        return

    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(8, 0))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(grid, text=label + ":", foreground="#555",
                  width=18, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(grid, text=value or "—").grid(
            row=row, column=1, sticky="w", pady=2)

    field(0, "Title", m.title)
    field(1, "Subject", m.subject)
    field(2, "Exam board", m.exam_board or "—")
    field(3, "Paper number",
          str(m.paper_number) if m.paper_number is not None else "—")
    field(4, "Date sat", m.date_sat)
    field(5, "Duration",
          f"{m.duration_minutes} mins" if m.duration_minutes else "—")
    field(6, "Max marks", str(m.max_marks))
    field(7, "Created", m.created_at)
    if m.notes:
        ttk.Separator(grid, orient="horizontal").grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(grid, text="Notes:", foreground="#555",
                  width=18, anchor="e").grid(row=9, column=0, sticky="ne",
                                              padx=(0, 8))
        ttk.Label(grid, text=m.notes, wraplength=520,
                  justify="left").grid(row=9, column=1, sticky="w")

    # Quick stats
    results = data.list_results(mock_id=mock_id)
    marked = [r for r in results if r.marks is not None]
    pcts = [data.derived_pct(r.marks, m.max_marks) for r in marked]
    pcts = [p for p in pcts if p is not None]
    stats = ttk.Frame(frame)
    stats.pack(anchor="w", pady=(12, 0))
    ttk.Label(stats, text=(
        f"Results recorded: {len(results)}  ·  "
        f"Marked: {len(marked)}  ·  "
        f"Avg: {round(sum(pcts)/len(pcts), 1)}%"
        if pcts else
        f"Results recorded: {len(results)}  ·  Marked: 0"
    ), foreground="#555").pack(anchor="w")

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Results sheet",
               command=lambda: open_results_sheet(gui, m.mock_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Edit",
               command=lambda: open_edit_mock(gui, m.mock_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete",
               command=lambda: _delete_with_confirm(gui, m.mock_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Viewing mock #{mock_id}")


def _delete_with_confirm(gui, mock_id: int) -> None:
    m = data.get_mock(mock_id)
    if m is None:
        messagebox.showerror("Not found", f"No mock #{mock_id}",
                             parent=gui.root)
        return
    n = len(data.list_results(mock_id=mock_id))
    msg = f"Delete mock '{m.title}'?"
    if n:
        msg += f"\n\n{n} result row(s) will be removed."
    if not messagebox.askyesno("Delete mock", msg, parent=gui.root):
        return
    try:
        data.delete_mock(mock_id)
    except Exception as e:
        logger.exception("delete_mock crashed")
        messagebox.showerror("Error", f"Could not delete: {e}",
                             parent=gui.root)
        return
    gui.status_var.set(f"Deleted mock #{mock_id}")
    open_directory(gui)


# ─── Results sheet tab (and standalone) ─────────────────────────────

def _build_results_tab(gui, parent: ttk.Frame) -> None:
    mocks = data.list_mocks()
    labels = [f"#{m.mock_id}  {m.title}  ({m.subject}, {m.date_sat})"
              for m in mocks]
    by_label = {lbl: m.mock_id for lbl, m in zip(labels, mocks)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    mock_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Mock:").pack(side="left")
    ttk.Combobox(bar, textvariable=mock_var, values=labels,
                 state="readonly", width=58
                 ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, pady=(0, 8))

    row_state: dict[str, dict[str, Any]] = {}
    current_mock: dict[str, Any] = {"mock": None}

    def load() -> None:
        for w in holder.winfo_children():
            w.destroy()
        row_state.clear()
        mid = by_label.get(mock_var.get())
        if mid is None:
            ttk.Label(holder, text="Pick a mock.",
                      foreground="#a33").pack(anchor="w")
            current_mock["mock"] = None
            return
        m = data.get_mock(mid)
        current_mock["mock"] = m
        try:
            view = data.result_view(mid)
        except ValidationError as e:
            ttk.Label(holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("result_view failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        if not view:
            ttk.Label(
                holder,
                text=(f"No students take {m.subject}. "
                      "Update student records or save results manually."),
                foreground="#a33",
            ).pack(anchor="w")
            return

        ttk.Label(
            holder,
            text=(f"{m.title}  ·  Max marks: {m.max_marks}  ·  "
                  f"Boundaries: A*≥90% A≥80% B≥70% C≥60% D≥50% E≥40%"),
            foreground="#555",
        ).pack(anchor="w", pady=(0, 6))

        header = ttk.Frame(holder)
        header.pack(fill="x")
        for text, width in [
            ("Student ID",  12), ("Name",  28),
            ("Marks",        7), ("%",      6),
            ("Letter (auto)", 10),
            ("Grade override", 12), ("Notes", 26),
        ]:
            ttk.Label(header, text=text, font=("", 10, "bold"),
                      width=width, anchor="w").pack(side="left", padx=2)

        for v in view:
            row = ttk.Frame(holder)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=v.student_id, width=12, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=v.full_name, width=28, anchor="w"
                      ).pack(side="left", padx=2)

            marks_var = tk.StringVar(
                value=str(v.result.marks)
                if v.result and v.result.marks is not None else "")
            grade_var = tk.StringVar(
                value=(v.result.grade or "") if v.result else "")
            notes_var = tk.StringVar(
                value=(v.result.notes or "") if v.result else "")

            ttk.Entry(row, textvariable=marks_var, width=7
                      ).pack(side="left", padx=2)

            pct_label = ttk.Label(row, text="—", width=6, anchor="w")
            pct_label.pack(side="left", padx=2)
            auto_label = ttk.Label(row, text="—", width=10, anchor="w")
            auto_label.pack(side="left", padx=2)

            def _refresh_derived(*_a, mv=marks_var,
                                  plabel=pct_label, alabel=auto_label,
                                  mm=m.max_marks):
                try:
                    val = int(mv.get())
                except ValueError:
                    plabel.configure(text="—")
                    alabel.configure(text="—")
                    return
                pct = data.derived_pct(val, mm)
                plabel.configure(text=f"{pct}%" if pct is not None else "—")
                from education_system.systems.sixth_form.domain.assessment.gradebook.gradebook import pct_to_letter
                alabel.configure(text=pct_to_letter(pct) or "—")

            marks_var.trace_add("write", _refresh_derived)
            _refresh_derived()

            ttk.Combobox(row, textvariable=grade_var,
                         values=["", *LETTER_GRADES],
                         state="readonly", width=10
                         ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=notes_var, width=26
                      ).pack(side="left", padx=2)

            row_state[v.student_id] = {
                "marks": marks_var, "grade": grade_var, "notes": notes_var,
            }

        gui.status_var.set(
            f"Mock results loaded: #{mid} ({len(view)} student(s))")

    def submit() -> None:
        m = current_mock["mock"]
        if m is None:
            messagebox.showerror("Cannot save",
                                 "Pick a mock.", parent=gui.root)
            return
        if not row_state:
            messagebox.showinfo("Nothing to save",
                                "Load a mock first.", parent=gui.root)
            return
        payload = {sid: {k: v.get() for k, v in vs.items()}
                   for sid, vs in row_state.items()}
        try:
            n = data.save_results(m.mock_id, payload)
        except ValidationError as e:
            logger.warning("save_results rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_results crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        messagebox.showinfo("Results saved",
                            f"Saved {n} result row(s).", parent=gui.root)
        gui.status_var.set(f"Saved {n} result(s)")

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))
    ttk.Button(actions, text="Load", command=load
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save results", command=submit
               ).pack(side="left", padx=(0, 6))

    if labels:
        load()
    else:
        ttk.Label(holder,
                  text="No mocks yet — create one in the Mocks tab.",
                  foreground="#a33").pack(anchor="w")


def open_results_sheet(gui, mock_id: int) -> None:
    """Standalone view for a single mock's results sheet."""
    frame = _clear(gui)
    _heading(frame, f"Mock #{mock_id} — Results Sheet")
    m = data.get_mock(mock_id)
    if m is None:
        ttk.Label(frame, text="No such mock.",
                  foreground="#a33").pack(anchor="w")
        return
    ttk.Label(
        frame,
        text=(f"{m.title}  ·  {m.subject}  ·  sat {m.date_sat}  ·  "
              f"max {m.max_marks}"),
        foreground="#555",
    ).pack(anchor="w", pady=(0, 8))

    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)
    try:
        view = data.result_view(mock_id)
    except Exception as e:
        logger.exception("result_view crashed")
        ttk.Label(holder, text=f"Error: {e}",
                  foreground="#a33").pack(anchor="w")
        return
    if not view:
        ttk.Label(
            holder,
            text=(f"No students take {m.subject}."),
            foreground="#a33",
        ).pack(anchor="w")
        ttk.Button(frame, text="Back",
                   command=lambda: open_directory(gui)
                   ).pack(anchor="w", pady=(12, 0))
        return

    row_state: dict[str, dict[str, Any]] = {}

    header = ttk.Frame(holder)
    header.pack(fill="x")
    for text, width in [
        ("Student ID", 12), ("Name", 28), ("Marks", 7),
        ("%", 6), ("Letter (auto)", 10), ("Grade override", 12),
        ("Notes", 26),
    ]:
        ttk.Label(header, text=text, font=("", 10, "bold"),
                  width=width, anchor="w").pack(side="left", padx=2)

    for v in view:
        row = ttk.Frame(holder)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=v.student_id, width=12, anchor="w").pack(side="left", padx=2)
        ttk.Label(row, text=v.full_name, width=28, anchor="w").pack(side="left", padx=2)
        marks_var = tk.StringVar(
            value=str(v.result.marks)
            if v.result and v.result.marks is not None else "")
        grade_var = tk.StringVar(
            value=(v.result.grade or "") if v.result else "")
        notes_var = tk.StringVar(
            value=(v.result.notes or "") if v.result else "")
        ttk.Entry(row, textvariable=marks_var, width=7).pack(side="left", padx=2)
        pct_label = ttk.Label(row, text="—", width=6, anchor="w")
        pct_label.pack(side="left", padx=2)
        auto_label = ttk.Label(row, text="—", width=10, anchor="w")
        auto_label.pack(side="left", padx=2)
        def _refresh(*_a, mv=marks_var, plabel=pct_label,
                     alabel=auto_label, mm=m.max_marks):
            try:
                val = int(mv.get())
            except ValueError:
                plabel.configure(text="—")
                alabel.configure(text="—")
                return
            pct = data.derived_pct(val, mm)
            plabel.configure(text=f"{pct}%" if pct is not None else "—")
            from education_system.systems.sixth_form.domain.assessment.gradebook.gradebook import pct_to_letter
            alabel.configure(text=pct_to_letter(pct) or "—")
        marks_var.trace_add("write", _refresh)
        _refresh()
        ttk.Combobox(row, textvariable=grade_var,
                     values=["", *LETTER_GRADES],
                     state="readonly", width=10
                     ).pack(side="left", padx=2)
        ttk.Entry(row, textvariable=notes_var, width=26
                  ).pack(side="left", padx=2)
        row_state[v.student_id] = {
            "marks": marks_var, "grade": grade_var, "notes": notes_var,
        }

    def save() -> None:
        payload = {sid: {k: v.get() for k, v in vs.items()}
                   for sid, vs in row_state.items()}
        try:
            n = data.save_results(mock_id, payload)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_results crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        gui.status_var.set(f"Saved {n} result(s)")
        messagebox.showinfo("Saved", f"Saved {n} row(s).", parent=gui.root)

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Save", command=save
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back",
               command=lambda: open_directory(gui)
               ).pack(side="left")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    subject_var = tk.StringVar(
        value=_active_subjects()[0] if _active_subjects() else "")
    from_var = tk.StringVar()
    to_var = tk.StringVar()

    ttk.Label(bar, text="Subject:").pack(side="left")
    ttk.Combobox(bar, textvariable=subject_var,
                 values=_active_subjects(),
                 state="readonly", width=22
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12
              ).pack(side="left", padx=(4, 8))
    ttk.Label(bar, text="to:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        subject = subject_var.get().strip()
        if not subject:
            ttk.Label(holder, text="Pick a subject.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            per = data.per_student_summary_for_subject(
                subject,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("summary failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        students_index = {s.student_id: s for s in student_data.list_students()}
        cols = ("student_id", "name", "sat", "total",
                "avg", "best", "worst")
        headings = {
            "student_id": ("Student ID", 110),
            "name":       ("Name",       220),
            "sat":        ("Sat",         50),
            "total":      ("Total",       60),
            "avg":        ("Avg %",       70),
            "best":       ("Best",        60),
            "worst":      ("Worst",       60),
        }
        tree = ttk.Treeview(holder, columns=cols, show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for sid, s in sorted(per.items()):
            student = students_index.get(sid)
            name = student.full_name if student else "(deleted)"
            tree.insert("", "end", iid=sid, values=(
                sid, name, s.mocks_sat, s.mocks_total,
                f"{s.avg_pct}%" if s.avg_pct is not None else "—",
                s.best_letter or "—", s.worst_letter or "—",
            ))
        gui.status_var.set(f"Mock summary loaded ({subject})")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if subject_var.get():
        render()
