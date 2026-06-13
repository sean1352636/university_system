"""Tk views for mock exams."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.assessment.mock_exams import (
    mock_exams as data,
)
from education_system.secondarysch_system.modules.domain.assessment.mock_exams.mock_exams import (
    SERIES_STATUSES, PAPER_TIERS,
)
from education_system.secondarysch_system.modules.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Mock Exams", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


def _series_dialog(host, title: str,
                   initial: dict[str, Any] | None = None
                   ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("440x380")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    name_var   = tk.StringVar(value=str(initial.get("name") or ""))
    year_var   = tk.StringVar(value=str(initial.get("year_group") or "11"))
    start_var  = tk.StringVar(value=str(initial.get("start_date") or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Planned"))

    rows: list[tuple[str, tk.Widget]] = [
        ("Name:",       ttk.Entry(frm, textvariable=name_var, width=40)),
        ("Year:",       ttk.Combobox(frm, textvariable=year_var,
                                      values=list(YEAR_GROUPS),
                                      state="readonly", width=8)),
        ("Start date:", ttk.Entry(frm, textvariable=start_var, width=14)),
        ("End date:",   ttk.Entry(frm, textvariable=end_var, width=14)),
        ("Status:",     ttk.Combobox(frm, textvariable=status_var,
                                      values=list(SERIES_STATUSES),
                                      state="readonly", width=12)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=40, height=4, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "name":       name_var.get().strip(),
            "year_group": year_var.get().strip(),
            "start_date": start_var.get().strip(),
            "end_date":   end_var.get().strip(),
            "status":     status_var.get().strip(),
            "notes":      notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _paper_dialog(host, title: str, series_id: int,
                  initial: dict[str, Any] | None = None
                  ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x440")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    name_var  = tk.StringVar(value=str(initial.get("paper_name") or ""))
    date_var  = tk.StringVar(value=str(initial.get("paper_date") or ""))
    max_var   = tk.StringVar(value=str(initial.get("max_marks") or ""))
    tier_var  = tk.StringVar(value=str(initial.get("tier") or "N/A"))
    gb_var    = tk.StringVar(value=str(initial.get("grade_boundaries")
                                         or ""))

    try:
        subjects = subjects_data.list_all(active_only=True)
    except Exception:
        subjects = []
    subject_labels = [f"#{s.subject_id} {s.code} — {s.name}"
                      for s in subjects]
    subject_var = tk.StringVar(value="")
    initial_sid = initial.get("subject_id")
    if initial_sid is not None:
        for s in subjects:
            if s.subject_id == int(initial_sid):
                subject_var.set(f"#{s.subject_id} {s.code} — {s.name}")
                break

    rows: list[tuple[str, tk.Widget]] = [
        ("Subject:",       ttk.Combobox(frm, textvariable=subject_var,
                                         values=subject_labels,
                                         state="readonly", width=42)),
        ("Paper name:",    ttk.Entry(frm, textvariable=name_var,
                                      width=24)),
        ("Paper date:",    ttk.Entry(frm, textvariable=date_var,
                                      width=14)),
        ("Max marks:",     ttk.Entry(frm, textvariable=max_var, width=8)),
        ("Tier:",          ttk.Combobox(frm, textvariable=tier_var,
                                         values=list(PAPER_TIERS),
                                         state="readonly", width=12)),
        ("Grade boundaries:", ttk.Entry(frm, textvariable=gb_var,
                                         width=30)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=40, height=4, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "series_id":        series_id,
            "subject_id":       _parse_subject(subject_var.get()),
            "paper_name":       name_var.get().strip(),
            "paper_date":       date_var.get().strip(),
            "max_marks":        max_var.get().strip(),
            "tier":             tier_var.get().strip(),
            "grade_boundaries": gb_var.get().strip(),
            "notes":            notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _result_dialog(host, paper: data.MockPaper,
                    existing: data.MockResult | None,
                    initial_pupil: str | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Mock result — {paper.paper_name}")
    dlg.transient(host.root)
    dlg.geometry("420x340")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{paper.subject_code} — {paper.paper_name}    "
                   f"max {paper.max_marks:g}",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))

    pupil_var = tk.StringVar(value=str(
        (existing.pupil_id if existing else initial_pupil) or ""))
    marks_var = tk.StringVar(value=str(
        existing.marks_awarded if existing
        and existing.marks_awarded is not None else ""))
    grade_var = tk.StringVar(value=str(
        existing.grade if existing else ""))
    absent_var = tk.BooleanVar(value=bool(existing and existing.absent))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:", ttk.Entry(frm, textvariable=pupil_var, width=14,
                                  state=("readonly" if existing
                                          else "normal"))),
        ("Marks:",    ttk.Entry(frm, textvariable=marks_var, width=8)),
        ("Grade:",    ttk.Entry(frm, textvariable=grade_var, width=6)),
        ("Absent:",   ttk.Checkbutton(frm, variable=absent_var)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    ttk.Label(frm, text="Notes:").pack(anchor="w", pady=(8, 0))
    notes_w = tk.Text(frm, width=44, height=4, wrap="word")
    notes_w.insert("1.0", str(existing.notes if existing else ""))
    notes_w.pack(fill="x", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":      pupil_var.get().strip(),
            "marks_awarded": marks_var.get().strip(),
            "grade":         grade_var.get().strip(),
            "absent":        bool(absent_var.get()),
            "notes":         notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_mock_exams(host) -> None:
    logger.debug("GUI: open_mock_exams")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Mock Exams",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly",
                 width=5).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *SERIES_STATUSES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="New series",
               command=lambda: _new_series(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_series(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Set status",
               command=lambda: _status_series(host, tree,
                                                on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Papers",
               command=lambda: _open_papers(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_series(host, tree,
                                                on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "year", "start", "end", "status", "name")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("year", "Yr", 50),
        ("start", "Start", 100), ("end", "End", 100),
        ("status", "Status", 100), ("name", "Name", 340),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_series(
                year_group=year_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Mock Exams", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("mock series refresh failed")
            messagebox.showerror("Mock Exams",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for s in rows:
            tree.insert("", "end", iid=str(s.series_id), values=(
                s.series_id, s.year_group, s.start_date, s.end_date,
                s.status, s.name,
            ))
        summary_var.set(f"{len(rows)} series listed")
        host.status_var.set(f"Mock Exams: {len(rows)} series")

    tree.bind("<Double-1>", lambda _e: _open_papers(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host, label: str) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Mock Exams",
                            f"Select a {label} first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new_series(host, *, on_done=None) -> None:
    fields = _series_dialog(host, "New mock series")
    if not fields:
        return
    s = data.create_series(fields)
    messagebox.showinfo("Mock Exams", f"Created '{s.name}'",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_series(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host, "series")
    if sid is None:
        return
    existing = data.get_series(sid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "name", "year_group", "start_date", "end_date",
        "status", "notes")}
    fields = _series_dialog(host, f"Edit series #{sid}",
                              initial=initial)
    if not fields:
        return
    data.update_series(sid, fields)
    if on_done:
        on_done()


@_safe_view
def _status_series(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host, "series")
    if sid is None:
        return
    s = data.get_series(sid)
    if s is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{sid}")
    dlg.transient(host.root)
    dlg.geometry("320x140")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=s.name[:40]).pack(anchor="w")
    ttk.Label(frm, text=f"Current: {s.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=s.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(SERIES_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_series_status(sid, new_var.get())
        except ValidationError as e:
            messagebox.showerror("Mock Exams", str(e), parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _delete_series(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host, "series")
    if sid is None:
        return
    s = data.get_series(sid)
    if s is None:
        return
    if not messagebox.askyesno(
            "Delete series",
            f"Delete '{s.name}' and ALL its papers + results?",
            parent=host.root):
        return
    data.delete_series(sid)
    if on_done:
        on_done()


@_safe_view
def _open_papers(host, tree: ttk.Treeview) -> None:
    sid = _selected_id(tree, host, "series")
    if sid is None:
        return
    s = data.get_series(sid)
    if s is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Papers — {s.name}")
    dlg.transient(host.root)
    dlg.geometry("820x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{s.name}    Yr {s.year_group}    "
                   f"{s.start_date}..{s.end_date}    {s.status}",
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Add paper",
               command=lambda: _new_paper()).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit paper",
               command=lambda: _edit_paper()).pack(side="left", padx=2)
    ttk.Button(bar, text="Results",
               command=lambda: _open_results()).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _paper_summary()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete paper",
               command=lambda: _delete_paper()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    paper_tree = ttk.Treeview(frm,
                                columns=("id", "date", "subj", "name",
                                          "tier", "max"),
                                show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("subj", "Subj", 90), ("name", "Paper", 300),
        ("tier", "Tier", 100), ("max", "Max", 80),
    ]:
        paper_tree.heading(c, text=label)
        paper_tree.column(c, width=w, anchor="w")
    paper_tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in paper_tree.get_children():
            paper_tree.delete(i)
        try:
            rows = data.list_papers(sid)
        except Exception as e:
            logger.exception("paper list failed")
            messagebox.showerror("Mock Exams",
                                 f"Could not load papers:\n\n{e}",
                                 parent=dlg)
            return
        for p in rows:
            paper_tree.insert("", "end", iid=str(p.paper_id), values=(
                p.paper_id, p.paper_date, p.subject_code or "?",
                p.paper_name, p.tier, p.max_marks,
            ))

    def _selected_paper() -> data.MockPaper | None:
        sel = paper_tree.focus()
        if not sel:
            messagebox.showinfo("Mock Exams",
                                "Select a paper first.", parent=dlg)
            return None
        try:
            return data.get_paper(int(sel))
        except Exception:
            return None

    def _new_paper() -> None:
        fields = _paper_dialog(host, "New paper", sid)
        if not fields:
            return
        try:
            data.create_paper(fields)
        except ValidationError as e:
            messagebox.showerror("Mock Exams", str(e), parent=dlg)
            return
        _refresh()

    def _edit_paper() -> None:
        p = _selected_paper()
        if p is None:
            return
        initial = {
            "paper_name": p.paper_name, "paper_date": p.paper_date,
            "subject_id": p.subject_id, "max_marks": p.max_marks,
            "tier": p.tier, "grade_boundaries": p.grade_boundaries,
            "notes": p.notes,
        }
        fields = _paper_dialog(host, f"Edit paper #{p.paper_id}",
                                sid, initial=initial)
        if not fields:
            return
        try:
            data.update_paper(p.paper_id, fields)
        except ValidationError as e:
            messagebox.showerror("Mock Exams", str(e), parent=dlg)
            return
        _refresh()

    def _delete_paper() -> None:
        p = _selected_paper()
        if p is None:
            return
        if not messagebox.askyesno(
                "Delete paper",
                f"Delete '{p.paper_name}' and ALL its results?",
                parent=dlg):
            return
        data.delete_paper(p.paper_id)
        _refresh()

    def _paper_summary() -> None:
        p = _selected_paper()
        if p is None:
            return
        s2 = data.paper_summary(p.paper_id)
        lines = [
            f"{p.subject_code} — {p.paper_name}",
            f"Date: {p.paper_date}    Max: {p.max_marks:g}    "
            f"Tier: {p.tier}",
            "",
            f"Results: {s2['count']}    Absent: {s2['absent']}",
            f"Avg %: {s2['avg_pct'] if s2['avg_pct'] is not None else '-'}    "
            f"Min %: {s2['min_pct'] if s2['min_pct'] is not None else '-'}    "
            f"Max %: {s2['max_pct'] if s2['max_pct'] is not None else '-'}",
        ]
        if s2["grades"]:
            lines.append("")
            lines.append("Grades:")
            for k, v in sorted(s2["grades"].items()):
                lines.append(f"   {k}: {v}")
        messagebox.showinfo("Paper summary", "\n".join(lines),
                            parent=dlg)

    def _open_results() -> None:
        p = _selected_paper()
        if p is None:
            return
        _show_results(host, p)

    paper_tree.bind("<Double-1>", lambda _e: _open_results())
    _refresh()


def _show_results(host, paper: data.MockPaper) -> None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Results — {paper.paper_name}")
    dlg.transient(host.root)
    dlg.geometry("700x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{paper.subject_code} — {paper.paper_name}    "
                   f"max {paper.max_marks:g}",
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Add result",
               command=lambda: _do_upsert(None)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit selected",
               command=lambda: _do_upsert("selected")
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    res_tree = ttk.Treeview(frm,
                              columns=("id", "pupil", "marks", "pct",
                                        "grade", "abs"),
                              show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 100),
        ("marks", "Marks", 100), ("pct", "%", 60),
        ("grade", "Grade", 60), ("abs", "Abs", 50),
    ]:
        res_tree.heading(c, text=label)
        res_tree.column(c, width=w, anchor="w")
    res_tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in res_tree.get_children():
            res_tree.delete(i)
        try:
            rows = data.list_results(paper.paper_id)
        except Exception as e:
            logger.exception("mock results list failed")
            messagebox.showerror("Mock Exams",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        for r in rows:
            marks = ("ABS" if r.absent
                     else ("-" if r.marks_awarded is None
                            else f"{r.marks_awarded:g}/{paper.max_marks:g}"))
            res_tree.insert("", "end", iid=str(r.result_id), values=(
                r.result_id, r.pupil_id, marks,
                f"{r.mark_pct:.0f}" if r.mark_pct is not None else "-",
                r.grade or "-",
                "Y" if r.absent else "N",
            ))

    def _do_upsert(mode: str | None) -> None:
        existing: data.MockResult | None = None
        initial_pupil: str | None = None
        if mode == "selected":
            sel = res_tree.focus()
            if not sel:
                messagebox.showinfo("Mock Exams",
                                    "Select a result first.",
                                    parent=dlg)
                return
            try:
                existing = data.get_result(int(sel))
            except Exception:
                logger.exception("get_result failed")
                return
        else:
            initial_pupil = simpledialog.askstring(
                "Pupil ID", "Pupil ID:", parent=dlg)
            if not initial_pupil:
                return
        fields = _result_dialog(host, paper, existing,
                                  initial_pupil=initial_pupil)
        if not fields:
            return
        try:
            data.upsert_result(paper.paper_id, fields)
        except ValidationError as e:
            messagebox.showerror("Mock Exams", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = res_tree.focus()
        if not sel:
            messagebox.showinfo("Mock Exams",
                                "Select a result first.", parent=dlg)
            return
        try:
            rid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete result",
                f"Delete result #{rid}?", parent=dlg):
            return
        data.delete_result(rid)
        _refresh()

    res_tree.bind("<Double-1>", lambda _e: _do_upsert("selected"))
    _refresh()
