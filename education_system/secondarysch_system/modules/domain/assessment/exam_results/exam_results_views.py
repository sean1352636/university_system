"""Tk views for Results Day."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.assessment.exam_results import (
    exam_results as data,
)
from education_system.secondarysch_system.modules.domain.assessment.exam_results.exam_results import (
    RESULT_STATUSES,
)
from education_system.secondarysch_system.modules.domain.assessment.exam_entries import (
    exam_entries as entries_data,
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
                messagebox.showerror("Results Day", str(e),
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


def _result_dialog(host, entry: Any, existing: data.ExamResult | None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Result — entry #{entry.entry_id}")
    dlg.transient(host.root)
    dlg.geometry("440x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{entry.pupil_id} / {entry.subject_code or '?'}    "
                   f"{entry.exam_board} {entry.tier}",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))

    grade_var  = tk.StringVar(value=str(
        existing.final_grade if existing else ""))
    marks_var  = tk.StringVar(value=str(
        existing.marks_awarded if existing
        and existing.marks_awarded is not None else ""))
    ums_var    = tk.StringVar(value=str(
        existing.ums if existing and existing.ums is not None else ""))
    date_var   = tk.StringVar(value=str(
        existing.result_date if existing else ""))
    status_var = tk.StringVar(value=str(
        existing.status if existing else "Pending"))
    remark_var = tk.StringVar(value=str(
        existing.remark_outcome if existing else ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Final grade:",     ttk.Entry(frm, textvariable=grade_var,
                                         width=6)),
        ("Marks awarded:",   ttk.Entry(frm, textvariable=marks_var,
                                         width=8)),
        ("UMS:",             ttk.Entry(frm, textvariable=ums_var,
                                         width=8)),
        ("Result date:",     ttk.Entry(frm, textvariable=date_var,
                                         width=14)),
        ("Status:",          ttk.Combobox(frm, textvariable=status_var,
                                            values=list(RESULT_STATUSES),
                                            state="readonly", width=14)),
        ("Remark outcome:",  ttk.Entry(frm, textvariable=remark_var,
                                         width=30)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=16).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    ttk.Label(frm, text="Notes:").pack(anchor="w", pady=(8, 0))
    notes_w = tk.Text(frm, width=44, height=4, wrap="word")
    notes_w.insert("1.0", str(existing.notes if existing else ""))
    notes_w.pack(fill="x", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "entry_id":       entry.entry_id,
            "final_grade":    grade_var.get().strip(),
            "marks_awarded":  marks_var.get().strip(),
            "ums":            ums_var.get().strip(),
            "result_date":    date_var.get().strip(),
            "status":         status_var.get().strip(),
            "remark_outcome": remark_var.get().strip(),
            "notes":          notes_w.get("1.0", "end").strip(),
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
def open_results_day(host) -> None:
    logger.debug("GUI: open_results_day")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Results Day",
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
                 values=["", *RESULT_STATUSES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="Record for entry",
               command=lambda: _record(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Pupil sheet",
               command=lambda: _pupil_sheet(host)).pack(side="left",
                                                        padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host,
                                          year_var.get().strip() or None)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Pending",
               command=lambda: _pending(host,
                                          year_var.get().strip() or None)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "entry", "pupil", "year", "subj", "board", "tier",
            "grade", "marks", "ums", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("entry", "Entry", 60),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("subj", "Subj", 80), ("board", "Board", 80),
        ("tier", "Tier", 90),
        ("grade", "Grade", 60), ("marks", "Marks", 70),
        ("ums", "UMS", 60), ("status", "Status", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_results(
                year_group=year_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Results Day", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("exam_results refresh failed")
            messagebox.showerror("Results Day",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for r in rows:
            tree.insert("", "end", iid=str(r.result_id), values=(
                r.result_id, r.entry_id, r.pupil_id,
                r.pupil_year or "-", r.subject_code or "?",
                r.exam_board or "-", r.tier or "-",
                r.final_grade or "-",
                r.marks_awarded if r.marks_awarded is not None else "-",
                r.ums if r.ums is not None else "-",
                r.status,
            ))
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Total: {s['total']}    Graded: {s['graded']}    "
                f"Pass (4+): "
                f"{s['pass_rate_pct'] if s['pass_rate_pct'] is not None else '-'}%    "
                f"Strong (5+): "
                f"{s['strong_pass_pct'] if s['strong_pass_pct'] is not None else '-'}%")
        except Exception:
            summary_var.set(f"{len(rows)} result(s) listed")
        host.status_var.set(f"Results Day: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Results Day",
                            "Select a result first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _record(host, *, on_done=None) -> None:
    raw = simpledialog.askstring("Entry ID", "Entry ID:",
                                  parent=host.root)
    if not raw:
        return
    try:
        eid = int(raw.strip())
    except ValueError:
        messagebox.showerror("Results Day",
                             "Entry ID must be a number.",
                             parent=host.root)
        return
    entry = entries_data.get(eid)
    if entry is None:
        messagebox.showerror("Results Day",
                             f"No entry #{eid}.",
                             parent=host.root)
        return
    existing = data.get_for_entry(eid)
    fields = _result_dialog(host, entry, existing)
    if not fields:
        return
    r = data.upsert(fields)
    messagebox.showinfo(
        "Results Day",
        f"Saved result for entry #{r.entry_id}: "
        f"grade {r.final_grade or '-'} ({r.status})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        return
    entry = entries_data.get(existing.entry_id)
    if entry is None:
        messagebox.showerror("Results Day",
                             f"Linked entry #{existing.entry_id} "
                             f"no longer exists.",
                             parent=host.root)
        return
    fields = _result_dialog(host, entry, existing)
    if not fields:
        return
    data.upsert(fields)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete result",
            f"Delete result for {existing.pupil_id} / "
            f"{existing.subject_code}?",
            parent=host.root):
        return
    data.delete(rid)
    if on_done:
        on_done()


@_safe_view
def _pupil_sheet(host) -> None:
    pid = simpledialog.askstring("Pupil sheet", "Pupil ID:",
                                  parent=host.root)
    if not pid:
        return
    s = data.pupil_results(pid.strip())
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Results — {pid}")
    dlg.transient(host.root)
    dlg.geometry("760x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"Pupil {pid}    Graded: {s['graded']}    "
                   f"Passes (4+): {s['passes']}    "
                   f"Strong (5+): {s['strong_passes']}",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))
    t = ttk.Treeview(frm, columns=("subj", "board", "tier", "grade",
                                     "marks", "ums", "status"),
                       show="headings", height=16)
    for c, label, w in [
        ("subj", "Subject", 100), ("board", "Board", 80),
        ("tier", "Tier", 90), ("grade", "Grade", 70),
        ("marks", "Marks", 70), ("ums", "UMS", 60),
        ("status", "Status", 90),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    for r in s["results"]:
        t.insert("", "end", values=(
            r.subject_code or "?", r.exam_board or "-",
            r.tier or "-", r.final_grade or "-",
            r.marks_awarded if r.marks_awarded is not None else "-",
            r.ums if r.ums is not None else "-",
            r.status,
        ))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))


@_safe_view
def _summary(host, year_group: str | None) -> None:
    s = data.cohort_summary(year_group=year_group)
    lines = [
        f"Total: {s['total']}    Graded: {s['graded']}",
        f"Pass rate (4+): "
        f"{s['pass_rate_pct'] if s['pass_rate_pct'] is not None else '-'}%",
        f"Strong pass (5+): "
        f"{s['strong_pass_pct'] if s['strong_pass_pct'] is not None else '-'}%",
    ]
    if s["by_status"]:
        lines.append("")
        lines.append("By status:")
        for k, v in s["by_status"].items():
            lines.append(f"  {k:<12} {v}")
    if s["by_grade"]:
        lines.append("")
        lines.append("By grade:")
        for g in sorted(s["by_grade"].keys(),
                          key=lambda x: (-int(x) if x.isdigit() else 0,
                                          x)):
            lines.append(f"  {g:<4} {s['by_grade'][g]}")
    messagebox.showinfo("Results — summary", "\n".join(lines),
                        parent=host.root)


@_safe_view
def _pending(host, year_group: str | None) -> None:
    pending = data.list_pending_for_entries(year_group=year_group)
    dlg = tk.Toplevel(host.root)
    dlg.title("Pending results")
    dlg.transient(host.root)
    dlg.geometry("640x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{len(pending)} Final entry(ies) without a result",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))
    t = ttk.Treeview(frm, columns=("entry", "pupil", "year", "subj",
                                     "board", "tier"),
                       show="headings", height=14)
    for c, label, w in [
        ("entry", "Entry", 60), ("pupil", "Pupil", 100),
        ("year", "Yr", 50), ("subj", "Subj", 80),
        ("board", "Board", 80), ("tier", "Tier", 100),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    for e in pending:
        t.insert("", "end", values=(
            e.entry_id, e.pupil_id, e.pupil_year or "-",
            e.subject_code or "?", e.exam_board, e.tier,
        ))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))
