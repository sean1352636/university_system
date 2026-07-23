"""GUI panels for Sixth Form Exam Entries.

Tabbed Notebook:

* Directory  — filterable list with single CRUD.
* Bulk sheet — pick a paper (subject + board + code + season + year),
  render its subject roster, fill in candidate numbers / status / fee
  per row in one go.
* Per-student — pick a student, see all their entries.
* Series     — counts and total fees for a board/season/year.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.assessment.exam_entries import exam_entries
from education_system.post_16.sixthform_system.modules.domain.assessment.exam_entries import exam_entries as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.post_16.sixthform_system.modules.domain.assessment.exam_entries.exam_entries import (
    DEFAULT_SEASON,
    DEFAULT_STATUS,
    EntryView,
    ExamEntry,
    SEASONS,
    STATUSES,
    TIERS,
    ValidationError,
)
from education_system.post_16.sixthform_system.modules.domain.students.students.students import A_LEVEL_SUBJECTS
from education_system.post_16.sixthform_system.modules.domain.academics.subjects.subjects import EXAM_BOARDS

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
    # Default to the academic year that ends this summer if we're before
    # June; otherwise next summer.
    return today.year if today.month < 9 else today.year + 1


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Exam Entries")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    bulk_tab = ttk.Frame(nb, padding=8)
    student_tab = ttk.Frame(nb, padding=8)
    series_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(bulk_tab,    text="Bulk sheet")
    nb.add(student_tab, text="Per-student")
    nb.add(series_tab,  text="Series")

    _build_directory_tab(gui, dir_tab)
    _build_bulk_tab(gui, bulk_tab)
    _build_student_tab(gui, student_tab)
    _build_series_tab(gui, series_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    subject_var = tk.StringVar()
    board_var = tk.StringVar()
    season_var = tk.StringVar()
    year_var = tk.StringVar()
    status_var = tk.StringVar()

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
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=10
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
            rows = data.list_entries(
                student_id=sid_var.get().strip() or None,
                subject=subject_var.get().strip() or None,
                exam_board=board_var.get().strip() or None,
                season=season_var.get().strip() or None,
                year=yr,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_entries failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("entry_id", "student", "subject", "board",
                "paper", "season", "year",
                "candidate", "status", "fee")
        headings = {
            "entry_id":  ("#",        50),
            "student":   ("Student", 100),
            "subject":   ("Subject", 140),
            "board":     ("Board",    90),
            "paper":     ("Paper",   100),
            "season":    ("Season",   80),
            "year":      ("Year",     50),
            "candidate": ("Cand. #",  90),
            "status":    ("Status",   90),
            "fee":       ("Fee",      60),
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

        for e in rows:
            tree.insert("", "end", iid=str(e.entry_id), values=(
                e.entry_id, e.student_id, e.subject, e.exam_board,
                e.paper_code, e.season, e.year,
                e.candidate_no or "—", e.status,
                f"£{e.fee:.2f}" if e.fee is not None else "—",
            ))
        summary.configure(text=f"{len(rows)} entry/entries.")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            eid = _selected()
            if eid is None:
                messagebox.showinfo("No selection",
                                    "Pick an entry first.", parent=gui.root)
            return eid

        def _delete() -> None:
            eid = _require()
            if eid is None:
                return
            e = data.get_entry(eid)
            if e is None:
                return
            if not messagebox.askyesno(
                "Delete entry",
                f"Delete entry #{eid} "
                f"({e.student_id} on {e.paper_code}, {e.season} {e.year})?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_entry(eid)
            except Exception as exc:
                logger.exception("delete_entry crashed")
                messagebox.showerror("Error", f"Could not delete: {exc}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Edit",
                   command=lambda: (_require() and
                                    open_edit_entry(gui, _selected(),
                                                    on_saved=refresh))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_new_entry(gui, on_saved=refresh)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>",
                  lambda _e: (_selected() and
                              open_edit_entry(gui, _selected(),
                                              on_saved=refresh)))
        gui.status_var.set(f"Exam entries: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), subject_var.set(""),
                                board_var.set(""), season_var.set(""),
                                year_var.set(""), status_var.set(""),
                                refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def open_new_entry(gui, on_saved=None) -> None:
    _entry_dialog(gui, title="New Exam Entry", existing=None,
                  on_saved=on_saved)


def open_edit_entry(gui, entry_id: int, on_saved=None) -> None:
    e = data.get_entry(entry_id)
    if e is None:
        messagebox.showerror("Not found", f"No entry #{entry_id}",
                             parent=gui.root)
        return
    _entry_dialog(gui, title=f"Edit Entry #{entry_id}",
                  existing=e, on_saved=on_saved)


def _entry_dialog(gui, *, title: str,
                   existing: ExamEntry | None,
                   on_saved=None) -> None:
    is_edit = existing is not None
    win = tk.Toplevel(gui.root)
    win.title(title)
    win.transient(gui.root)
    win.after_idle(win.grab_set)

    frm = ttk.Frame(win, padding=12)
    frm.grid()

    # Pre-fill
    if is_edit:
        student_disp = existing.student_id
    else:
        student_disp = ""
    subject_var = tk.StringVar(value=existing.subject if is_edit
                                else _active_subjects()[0]
                                if _active_subjects() else "")
    board_var = tk.StringVar(value=existing.exam_board if is_edit
                              else (EXAM_BOARDS[0]))
    paper_var = tk.StringVar(value=existing.paper_code if is_edit else "")
    title_var = tk.StringVar(
        value=(existing.paper_title or "") if is_edit else "")
    season_var = tk.StringVar(value=existing.season if is_edit
                                else DEFAULT_SEASON)
    year_var = tk.StringVar(value=str(existing.year) if is_edit
                              else str(_default_year()))
    candidate_var = tk.StringVar(
        value=(existing.candidate_no or "") if is_edit else "")
    tier_var = tk.StringVar(value=(existing.tier or "") if is_edit else "")
    status_var = tk.StringVar(value=existing.status if is_edit
                                else DEFAULT_STATUS)
    fee_var = tk.StringVar(
        value=(f"{existing.fee:.2f}" if (is_edit and existing.fee is not None)
               else ""))
    notes_var = tk.StringVar(value=(existing.notes or "") if is_edit else "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    if not is_edit:
        students = student_data.list_students()
        student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
        student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                            for s in students}
        student_var = tk.StringVar(
            value=student_labels[0] if student_labels else "")
        row(0, "Student:", ttk.Combobox(frm, textvariable=student_var,
                                         values=student_labels,
                                         state="readonly", width=42))
    else:
        student_var = tk.StringVar(value=existing.student_id)
        ttk.Label(frm, text="Student:").grid(row=0, column=0, sticky="e",
                                              padx=(0, 6), pady=2)
        ttk.Label(frm, text=f"{existing.student_id}",
                  foreground="#555").grid(row=0, column=1, sticky="w", pady=2)

    row(1, "Subject:", ttk.Combobox(frm, textvariable=subject_var,
                                     values=_active_subjects(),
                                     state="readonly", width=22))
    row(2, "Exam board:", ttk.Combobox(frm, textvariable=board_var,
                                        values=list(EXAM_BOARDS),
                                        state="readonly", width=14))
    row(3, "Paper code:", ttk.Entry(frm, textvariable=paper_var, width=18))
    row(4, "Paper title:", ttk.Entry(frm, textvariable=title_var, width=42))
    row(5, "Season:", ttk.Combobox(frm, textvariable=season_var,
                                    values=list(SEASONS),
                                    state="readonly", width=10))
    row(6, "Year:", ttk.Entry(frm, textvariable=year_var, width=8))
    row(7, "Candidate #:", ttk.Entry(frm, textvariable=candidate_var, width=14))
    row(8, "Tier:", ttk.Combobox(frm, textvariable=tier_var,
                                  values=["", *TIERS],
                                  state="readonly", width=12))
    row(9, "Status:", ttk.Combobox(frm, textvariable=status_var,
                                    values=list(STATUSES),
                                    state="readonly", width=12))
    row(10, "Fee (£):", ttk.Entry(frm, textvariable=fee_var, width=10))
    row(11, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        if is_edit:
            sid = existing.student_id
        else:
            sid = student_by_label.get(student_var.get())
            if not sid:
                messagebox.showerror("Cannot save",
                                     "Pick a student.", parent=win)
                return
        payload = {
            "student_id":   sid,
            "subject":      subject_var.get(),
            "exam_board":   board_var.get(),
            "paper_code":   paper_var.get(),
            "paper_title":  title_var.get(),
            "season":       season_var.get(),
            "year":         year_var.get(),
            "candidate_no": candidate_var.get(),
            "tier":         tier_var.get(),
            "status":       status_var.get(),
            "fee":          fee_var.get(),
            "notes":        notes_var.get(),
        }
        try:
            if is_edit:
                data.update_entry(existing.entry_id, payload)
            else:
                data.create_entry(payload)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("entry save crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        if on_saved:
            on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=12, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Bulk-sheet tab ─────────────────────────────────────────────────

def _build_bulk_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    subject_var = tk.StringVar(
        value=_active_subjects()[0] if _active_subjects() else "")
    board_var = tk.StringVar(value=EXAM_BOARDS[0])
    paper_var = tk.StringVar()
    title_var = tk.StringVar()
    season_var = tk.StringVar(value=DEFAULT_SEASON)
    year_var = tk.StringVar(value=str(_default_year()))
    tier_var = tk.StringVar()

    ttk.Label(bar, text="Subject:").pack(side="left")
    ttk.Combobox(bar, textvariable=subject_var, values=_active_subjects(),
                 state="readonly", width=20
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Board:").pack(side="left")
    ttk.Combobox(bar, textvariable=board_var, values=list(EXAM_BOARDS),
                 state="readonly", width=14
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Paper code:").pack(side="left")
    ttk.Entry(bar, textvariable=paper_var, width=14
              ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Season:").pack(side="left")
    ttk.Combobox(bar, textvariable=season_var, values=list(SEASONS),
                 state="readonly", width=10
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Year:").pack(side="left")
    ttk.Entry(bar, textvariable=year_var, width=6
              ).pack(side="left", padx=(4, 4))

    extras = ttk.Frame(parent)
    extras.pack(anchor="w", fill="x", pady=(0, 8))
    ttk.Label(extras, text="Paper title:").pack(side="left")
    ttk.Entry(extras, textvariable=title_var, width=40
              ).pack(side="left", padx=(4, 12))
    ttk.Label(extras, text="Tier:").pack(side="left")
    ttk.Combobox(extras, textvariable=tier_var,
                 values=["", *TIERS], state="readonly", width=12
                 ).pack(side="left", padx=(4, 4))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, pady=(0, 8))

    row_state: dict[str, dict[str, Any]] = {}

    def load() -> None:
        for w in holder.winfo_children():
            w.destroy()
        row_state.clear()

        subject = subject_var.get().strip()
        paper = paper_var.get().strip().upper()
        season = season_var.get().strip()
        try:
            year = int(year_var.get())
        except ValueError:
            messagebox.showerror("Bad input",
                                 "Year must be a number.", parent=gui.root)
            return
        if not subject or not paper:
            ttk.Label(holder,
                      text="Pick a subject and enter a paper code.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            view = data.bulk_view(subject, paper, season, year)
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
                text=(f"No students take {subject}."),
                foreground="#a33",
            ).pack(anchor="w")
            return

        ttk.Label(
            holder,
            text=(f"{paper}  ·  {subject}  ·  {season} {year}  ·  "
                  f"{len(view)} candidate(s)"),
            font=("", 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        header = ttk.Frame(holder)
        header.pack(fill="x")
        for text, width in [
            ("Student ID",  12), ("Name", 26),
            ("Candidate #", 14), ("Status", 14),
            ("Fee", 8), ("Notes", 24),
        ]:
            ttk.Label(header, text=text, font=("", 10, "bold"),
                      width=width, anchor="w").pack(side="left", padx=2)

        for v in view:
            row = ttk.Frame(holder)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=v.student_id, width=12, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=v.full_name, width=26, anchor="w"
                      ).pack(side="left", padx=2)

            candidate_var = tk.StringVar(
                value=(v.entry.candidate_no or "") if v.entry else "")
            status_var = tk.StringVar(
                value=v.entry.status if v.entry else DEFAULT_STATUS)
            fee_var = tk.StringVar(
                value=(f"{v.entry.fee:.2f}"
                       if (v.entry and v.entry.fee is not None) else ""))
            notes_var = tk.StringVar(
                value=(v.entry.notes or "") if v.entry else "")

            ttk.Entry(row, textvariable=candidate_var, width=14
                      ).pack(side="left", padx=2)
            ttk.Combobox(row, textvariable=status_var,
                         values=list(STATUSES), state="readonly", width=12
                         ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=fee_var, width=8
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=notes_var, width=24
                      ).pack(side="left", padx=2)
            row_state[v.student_id] = {
                "candidate_no": candidate_var,
                "status":       status_var,
                "fee":          fee_var,
                "notes":        notes_var,
            }
        gui.status_var.set(
            f"Bulk sheet loaded: {paper} ({len(view)} candidate(s))")

    def submit() -> None:
        subject = subject_var.get().strip()
        board = board_var.get().strip()
        paper = paper_var.get().strip().upper()
        season = season_var.get().strip()
        title = title_var.get().strip() or None
        tier = tier_var.get().strip() or None
        try:
            year = int(year_var.get())
        except ValueError:
            messagebox.showerror("Bad input",
                                 "Year must be a number.", parent=gui.root)
            return
        if not row_state:
            messagebox.showinfo("Nothing to save",
                                "Load the sheet first.", parent=gui.root)
            return
        payload = {sid: {k: v.get() for k, v in vs.items()}
                   for sid, vs in row_state.items()}
        try:
            n = data.save_bulk(
                subject=subject, exam_board=board, paper_code=paper,
                paper_title=title, season=season, year=year, tier=tier,
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
        messagebox.showinfo("Saved", f"Saved {n} entry/entries.",
                            parent=gui.root)
        gui.status_var.set(f"Saved {n} entries")
        load()

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))
    ttk.Button(actions, text="Load", command=load
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save bulk", command=submit
               ).pack(side="left", padx=(0, 6))


# ─── Per-student tab ────────────────────────────────────────────────

def _build_student_tab(gui, parent: ttk.Frame) -> None:
    students = student_data.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in students]
    by_label = {lbl: s.student_id for lbl, s in zip(labels, students)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    student_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Combobox(bar, textvariable=student_var, values=labels,
                 state="readonly", width=42
                 ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, pady=(0, 8))

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        sid = by_label.get(student_var.get())
        if not sid:
            ttk.Label(holder, text="Pick a student.",
                      foreground="#a33").pack(anchor="w")
            return
        student = student_data.get_student(sid)
        ttk.Label(
            holder,
            text=f"{student.student_id}  {student.full_name}"
                 if student else f"{sid} (deleted)",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        try:
            rows = data.entries_for_student(sid)
        except Exception as e:
            logger.exception("entries_for_student failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        if not rows:
            ttk.Label(holder, text="(no entries)",
                      foreground="#555").pack(anchor="w")
            return

        cols = ("entry_id", "subject", "board", "paper",
                "season", "year", "candidate", "status", "fee")
        headings = {
            "entry_id":  ("#",        50),
            "subject":   ("Subject", 140),
            "board":     ("Board",    90),
            "paper":     ("Paper",   110),
            "season":    ("Season",   80),
            "year":      ("Year",     60),
            "candidate": ("Cand. #", 100),
            "status":    ("Status",   90),
            "fee":       ("Fee",      80),
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
        for e in rows:
            tree.insert("", "end", iid=str(e.entry_id), values=(
                e.entry_id, e.subject, e.exam_board, e.paper_code,
                e.season, e.year, e.candidate_no or "—", e.status,
                f"£{e.fee:.2f}" if e.fee is not None else "—",
            ))

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _edit() -> None:
            eid = _selected()
            if eid is None:
                messagebox.showinfo("No selection",
                                    "Pick an entry.", parent=gui.root)
                return
            open_edit_entry(gui, eid, on_saved=render)

        def _delete() -> None:
            eid = _selected()
            if eid is None:
                messagebox.showinfo("No selection",
                                    "Pick an entry.", parent=gui.root)
                return
            if not messagebox.askyesno("Delete entry",
                                       f"Delete entry #{eid}?",
                                       parent=gui.root):
                return
            try:
                data.delete_entry(eid)
            except Exception as exc:
                logger.exception("delete_entry crashed")
                messagebox.showerror("Error", f"Could not delete: {exc}",
                                     parent=gui.root)
                return
            render()

        actions = ttk.Frame(parent)
        actions.pack(anchor="w", pady=(0, 4))
        ttk.Button(actions, text="Edit",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="New",
                   command=lambda: open_new_entry(gui, on_saved=render)
                   ).pack(side="left", padx=(12, 6))
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"Entries for {sid}: {len(rows)} row(s)")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if labels:
        render()
    else:
        ttk.Label(holder, text="No students yet.",
                  foreground="#a33").pack(anchor="w")


# ─── Series tab ────────────────────────────────────────────────────

def _build_series_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    board_var = tk.StringVar()
    season_var = tk.StringVar()
    year_var = tk.StringVar(value=str(_default_year()))

    ttk.Label(bar, text="Board:").pack(side="left")
    ttk.Combobox(bar, textvariable=board_var,
                 values=["", *EXAM_BOARDS], state="readonly", width=14
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
    info = ttk.Label(parent, text="", foreground="#333")
    info.pack(anchor="w", pady=(8, 0))

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            yr = int(year_var.get()) if year_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Bad input",
                                 "Year must be a number.", parent=gui.root)
            return
        try:
            summ = data.series_summary(
                exam_board=board_var.get().strip() or None,
                season=season_var.get().strip() or None,
                year=yr,
            )
        except ValidationError as e:
            ttk.Label(holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        ttk.Label(holder, text=f"Entries: {summ.total}",
                  font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))
        if not summ.total:
            return

        # Status breakdown
        ttk.Label(holder, text="By status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for st in STATUSES:
            n = summ.by_status.get(st, 0)
            ttk.Label(holder, text=f"   {st:<12}: {n}",
                      foreground="#444").pack(anchor="w")

        # Subject breakdown
        ttk.Label(holder, text="By subject:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for subj, n in sorted(summ.by_subject.items()):
            ttk.Label(holder, text=f"   {subj:<22}: {n}",
                      foreground="#444").pack(anchor="w")

        info.configure(
            text=f"Total fees recorded: £{summ.total_fee:.2f}")
        gui.status_var.set("Series summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
