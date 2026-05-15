"""Tk views for pupil reports."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.pupil_reports import (
    pupil_reports as data,
)
from education_system.primarysch_system.modules.domain.pupil_reports.pupil_reports import (
    Report, STATUSES, TERMS,
)
from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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
                messagebox.showerror("Pupil Reports", str(e),
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


@_safe_view
def open_pupil_reports(host) -> None:
    logger.debug("GUI: open_pupil_reports")

    win = tk.Toplevel(host.root)
    win.title("Pupil Reports")
    win.transient(host.root)
    win.geometry("1140x620")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    year_box = ttk.Combobox(filt, textvariable=year_var,
                            values=["All"], state="readonly", width=10)
    year_box.pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Term:").pack(side="left")
    term_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=term_var,
                 values=["All"] + list(TERMS),
                 state="readonly", width=8).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Status:").pack(side="left")
    status_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["All"] + list(STATUSES),
                 state="readonly", width=10).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Pupil year:").pack(side="left")
    py_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=py_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))

    cols = ("report_id", "pupil_id", "name", "year", "academic_year",
            "term", "status", "attendance", "published_on", "authored_by")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("report_id", "#", 50, "center"),
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 180, "w"),
        ("year", "Yr", 40, "center"),
        ("academic_year", "AcYr", 80, "center"),
        ("term", "Term", 70, "center"),
        ("status", "Status", 90, "w"),
        ("attendance", "Att %", 60, "center"),
        ("published_on", "Published", 100, "center"),
        ("authored_by", "Author", 150, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            ay = None if year_var.get() == "All" else year_var.get()
            term = None if term_var.get() == "All" else term_var.get()
            st = None if status_var.get() == "All" else status_var.get()
            py = None if py_var.get() == "All" else py_var.get()
            rows = data.list_reports(academic_year=ay, term=term,
                                     status=st, year_group=py)
        except ValidationError as e:
            messagebox.showerror("Pupil Reports", str(e), parent=win)
            return
        except Exception:
            logger.exception("pupil_reports refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for rec, p in rows:
            tree.insert("", "end", iid=str(rec.report_id), values=(
                rec.report_id, rec.pupil_id,
                p.full_name if p else "(unknown)",
                p.year_group if p else "-",
                rec.academic_year, rec.term, rec.status,
                "" if rec.attendance_pct is None else f"{rec.attendance_pct:.1f}",
                rec.published_on or "", rec.authored_by or "",
            ))
        try:
            year_box["values"] = ["All"] + data.known_years()
        except Exception:
            pass
        try:
            s = data.summary(academic_year=ay, term=term)
        except Exception:
            s = {"total": 0, "draft": 0, "published": 0,
                 "published_pct": 0.0, "average_attendance": None,
                 "attendance_count": 0}
        parts = [
            f"Total: {s['total']}",
            f"Draft: {s['draft']}",
            f"Published: {s['published']} ({s['published_pct']:.1f}%)",
        ]
        if s['average_attendance'] is not None:
            parts.append(f"Avg attendance: {s['average_attendance']:.1f}%")
        summary_var.set("   ".join(parts))

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Pupil Reports", "Select a report first.",
                                parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, report_id=None, on_saved=_refresh)

    def _edit() -> None:
        rid = _selected_id()
        if rid is None:
            return
        _open_form_dialog(win, report_id=rid, on_saved=_refresh)

    def _view() -> None:
        rid = _selected_id()
        if rid is None:
            return
        _open_view_dialog(win, rid, on_changed=_refresh)

    def _publish() -> None:
        rid = _selected_id()
        if rid is None:
            return
        try:
            data.publish(rid)
        except ValidationError as e:
            messagebox.showerror("Pupil Reports", str(e), parent=win)
            return
        except Exception:
            logger.exception("publish(%s) failed", rid)
            messagebox.showerror("Error", "Could not publish — see logs.",
                                 parent=win)
            return
        _refresh()

    def _revert() -> None:
        rid = _selected_id()
        if rid is None:
            return
        if not messagebox.askyesno("Revert to draft",
                                   f"Revert report #{rid} to draft?",
                                   parent=win):
            return
        try:
            data.revert_to_draft(rid)
        except Exception:
            logger.exception("revert_to_draft(%s) failed", rid)
            messagebox.showerror("Error", "Could not revert — see logs.",
                                 parent=win)
            return
        _refresh()

    def _delete() -> None:
        rid = _selected_id()
        if rid is None:
            return
        if not messagebox.askyesno("Delete report",
                                   f"Delete report #{rid}?", parent=win):
            return
        try:
            data.delete(rid)
        except Exception:
            logger.exception("delete(%s) failed", rid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btns, text="New draft", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit draft", command=_edit).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="View...", command=_view).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Publish", command=_publish).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Revert to draft", command=_revert).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _view())
    for v in (year_var, term_var, status_var, py_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()


def _set_text(text: tk.Text, value: str | None) -> None:
    text.delete("1.0", "end")
    if value:
        text.insert("1.0", value)


def _get_text(text: tk.Text) -> str:
    return text.get("1.0", "end").strip()


def _open_form_dialog(parent, *, report_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: Report | None = None
    if report_id is not None:
        try:
            existing = data.get(report_id)
        except Exception:
            logger.exception("get(%s) failed", report_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Pupil Reports",
                                 f"No report #{report_id}", parent=parent)
            return
        if existing.is_published:
            messagebox.showinfo(
                "Pupil Reports",
                "This report is published. Revert it to draft to edit.",
                parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Report" if existing else "New report")
    dlg.transient(parent)
    dlg.geometry("680x680")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var = tk.StringVar(value=existing.pupil_id if existing else "")
    pupil_label = tk.StringVar(value="")
    ttk.Label(frm, text="Pupil ID *").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Entry(frm, textvariable=pupil_var, width=14).grid(
        row=0, column=1, sticky="w", pady=3)
    ttk.Label(frm, textvariable=pupil_label, foreground="#666").grid(
        row=0, column=2, sticky="w", padx=(8, 0))

    def _lookup_pupil(*_a) -> None:
        pid = pupil_var.get().strip()
        if not pid:
            pupil_label.set("")
            return
        try:
            p = pupils_data.get_pupil(pid)
        except Exception:
            pupil_label.set("(error)")
            return
        pupil_label.set(
            f"{p.full_name} (year {p.year_group})" if p else "(unknown)")
    pupil_var.trace_add("write", _lookup_pupil)
    _lookup_pupil()

    ttk.Label(frm, text="Academic year *").grid(
        row=1, column=0, sticky="w", pady=3)
    ay_var = tk.StringVar(value=existing.academic_year if existing else "")
    ttk.Entry(frm, textvariable=ay_var, width=14).grid(
        row=1, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="e.g. 2025-26", foreground="#888").grid(
        row=1, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Term *").grid(row=2, column=0, sticky="w", pady=3)
    term_var = tk.StringVar(value=existing.term if existing else TERMS[0])
    ttk.Combobox(frm, textvariable=term_var, values=list(TERMS),
                 state="readonly", width=10).grid(
        row=2, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Headline").grid(row=3, column=0, sticky="w", pady=3)
    headline_var = tk.StringVar(value=existing.headline or "" if existing else "")
    ttk.Entry(frm, textvariable=headline_var, width=46).grid(
        row=3, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Authored by").grid(
        row=4, column=0, sticky="w", pady=3)
    author_var = tk.StringVar(
        value=existing.authored_by or "" if existing else "")
    ttk.Entry(frm, textvariable=author_var, width=30).grid(
        row=4, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Attendance %").grid(
        row=5, column=0, sticky="w", pady=3)
    att_var = tk.StringVar(
        value="" if not existing or existing.attendance_pct is None
        else f"{existing.attendance_pct:g}")
    ttk.Entry(frm, textvariable=att_var, width=8).grid(
        row=5, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Behaviour").grid(row=6, column=0, sticky="w", pady=3)
    behav_var = tk.StringVar(
        value=existing.behaviour or "" if existing else "")
    ttk.Entry(frm, textvariable=behav_var, width=30).grid(
        row=6, column=1, sticky="w", pady=3)

    def _section(row: int, label: str, value: str | None) -> tk.Text:
        ttk.Label(frm, text=label).grid(row=row, column=0, sticky="nw", pady=(8, 0))
        text = tk.Text(frm, height=4, width=58, wrap="word")
        text.grid(row=row, column=1, columnspan=2, sticky="nsew", pady=(8, 0))
        _set_text(text, value)
        frm.rowconfigure(row, weight=1)
        return text

    summary_text = _section(7, "Summary",
                            existing.summary if existing else None)
    strengths_text = _section(8, "Strengths",
                              existing.strengths if existing else None)
    next_steps_text = _section(9, "Next steps",
                               existing.next_steps if existing else None)

    ttk.Label(frm, text="Notes").grid(row=10, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=46).grid(
        row=10, column=1, columnspan=2, sticky="ew", pady=3)

    frm.columnconfigure(1, weight=1)
    frm.columnconfigure(2, weight=1)

    def _save(*, then_publish: bool = False) -> None:
        payload = {
            "pupil_id": pupil_var.get(),
            "academic_year": ay_var.get(),
            "term": term_var.get(),
            "headline": headline_var.get(),
            "summary": _get_text(summary_text),
            "strengths": _get_text(strengths_text),
            "next_steps": _get_text(next_steps_text),
            "attendance_pct": att_var.get(),
            "behaviour": behav_var.get(),
            "status": existing.status if existing else "draft",
            "authored_by": author_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                rec = data.create(payload)
            else:
                rec = data.update(existing.report_id, payload)
            if then_publish:
                rec = data.publish(rec.report_id)
        except ValidationError as e:
            messagebox.showerror("Pupil Reports", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save report failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(12, 0))
    ttk.Button(btn_row, text="Save draft", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Save & publish",
               command=lambda: _save(then_publish=True)).pack(
        side="right", padx=(0, 8))
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_view_dialog(parent, report_id: int,
                      on_changed: Callable[[], None]) -> None:
    try:
        rec = data.get(report_id)
    except Exception:
        logger.exception("get(%s) failed", report_id)
        messagebox.showerror("Error", "Could not load — see logs.",
                             parent=parent)
        return
    if rec is None:
        messagebox.showerror("Pupil Reports",
                             f"No report #{report_id}", parent=parent)
        return

    dlg = tk.Toplevel(parent)
    dlg.title(f"Report #{rec.report_id}")
    dlg.transient(parent)
    dlg.geometry("680x620")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text=f"Pupil {rec.pupil_id}  —  {rec.academic_year}  {rec.term}",
              font=("Segoe UI", 12, "bold")).pack(anchor="w")
    att = ("-" if rec.attendance_pct is None
           else f"{rec.attendance_pct:.1f}%")
    ttk.Label(frm,
              text=f"Status: {rec.status}   "
                   f"Author: {rec.authored_by or '-'}   "
                   f"Published: {rec.published_on or '-'}   "
                   f"Attendance: {att}   Behaviour: {rec.behaviour or '-'}",
              foreground="#444").pack(anchor="w", pady=(2, 6))

    if rec.headline:
        ttk.Label(frm, text=rec.headline,
                  font=("Segoe UI", 10, "italic"),
                  wraplength=620).pack(anchor="w", pady=(0, 8))

    text = tk.Text(frm, wrap="word", height=20)
    text.pack(fill="both", expand=True)

    def _add_section(title: str, body: str | None) -> None:
        text.insert("end", f"{title}\n", "h")
        text.insert("end", (body or "—") + "\n\n")

    text.tag_configure("h", font=("Segoe UI", 10, "bold"),
                       spacing1=4, spacing3=2)
    _add_section("Summary", rec.summary)
    _add_section("Strengths", rec.strengths)
    _add_section("Next steps", rec.next_steps)
    if rec.notes:
        _add_section("Notes", rec.notes)
    text.config(state="disabled")

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill="x", pady=(10, 0))

    def _do_publish() -> None:
        try:
            data.publish(rec.report_id)
        except ValidationError as e:
            messagebox.showerror("Pupil Reports", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("publish failed for %s", rec.report_id)
            messagebox.showerror("Error", "Could not publish — see logs.",
                                 parent=dlg)
            return
        on_changed()
        dlg.destroy()

    def _do_revert() -> None:
        try:
            data.revert_to_draft(rec.report_id)
        except Exception:
            logger.exception("revert failed for %s", rec.report_id)
            messagebox.showerror("Error", "Could not revert — see logs.",
                                 parent=dlg)
            return
        on_changed()
        dlg.destroy()

    if rec.is_draft:
        ttk.Button(btn_row, text="Publish", command=_do_publish).pack(side="left")
    else:
        ttk.Button(btn_row, text="Revert to draft",
                   command=_do_revert).pack(side="left")
    ttk.Button(btn_row, text="Close",
               command=dlg.destroy).pack(side="right")
