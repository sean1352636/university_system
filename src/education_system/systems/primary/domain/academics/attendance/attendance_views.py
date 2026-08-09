"""Tk views for daily attendance."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.academics.attendance import (
    attendance as data,
)
from education_system.systems.primary.domain.academics.attendance.attendance import (
    MARK_CODES, SESSIONS,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("Attendance", str(e),
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


def _today() -> str:
    return _dt.date.today().isoformat()


def _mark_choices() -> list[str]:
    return [f"{code}  {label}" for code, (label, _cat) in MARK_CODES.items()]


def _parse_mark(s: str) -> str:
    return (s or "").strip().split()[0] if s else ""


@_safe_view
def open_attendance(host) -> None:
    logger.debug("GUI: open_attendance")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Attendance",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Date:").pack(side="left", padx=(0, 4))
    date_var = tk.StringVar(value=_today())
    ttk.Entry(bar, textvariable=date_var, width=12).pack(side="left",
                                                         padx=(0, 8))
    ttk.Label(bar, text="Session:").pack(side="left", padx=(0, 4))
    session_var = tk.StringVar(value="AM")
    ttk.Combobox(bar, textvariable=session_var,
                 values=list(SESSIONS), state="readonly", width=5).pack(
        side="left", padx=(0, 8))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly", width=5).pack(
        side="left", padx=(0, 8))
    ttk.Button(bar, text="Load register",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="Save",
               command=lambda: _save_register()).pack(side="left", padx=2)
    ttk.Button(bar, text="Single mark",
               command=lambda: _single_mark(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Pupil history",
               command=lambda: _pupil_history(host)).pack(side="left",
                                                          padx=2)
    ttk.Button(bar, text="Daily summary",
               command=lambda: _daily_summary(host, date_var.get())
               ).pack(side="left", padx=2)

    summary_var = tk.StringVar(value="")
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    cols = ("pupil", "name", "year", "form", "mark", "label", "notes")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("pupil", "Pupil ID", 90), ("name", "Name", 180),
        ("year", "Year", 50), ("form", "Form", 60),
        ("mark", "Mark", 60), ("label", "Status", 160),
        ("notes", "Notes", 200),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    # Per-row editable state held outside the tree.
    state: dict[str, dict[str, str]] = {}

    def _load_pupils() -> list[Any]:
        from education_system.systems.primary.domain.learners.pupils import (
            pupils as pupils_data,
        )
        yg = year_var.get().strip() or None
        all_pupils = pupils_data.list_pupils()
        if yg:
            all_pupils = [p for p in all_pupils if p.year_group == yg]
        return all_pupils

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        state.clear()
        try:
            pupils = _load_pupils()
            existing_records = data.list_for_date(
                date_var.get().strip(),
                session=session_var.get().strip() or None)
        except ValidationError as e:
            messagebox.showerror("Attendance", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("attendance refresh failed")
            messagebox.showerror("Attendance",
                                 f"Could not load register:\n\n{e}",
                                 parent=host.root)
            return
        by_pupil = {r.pupil_id: r for r in existing_records}
        for p in pupils:
            rec = by_pupil.get(p.pupil_id)
            mark = rec.mark if rec else ""
            label = MARK_CODES.get(mark, ("", ""))[0] if mark else "-"
            notes = (rec.notes or "") if rec else ""
            state[p.pupil_id] = {"mark": mark, "notes": notes}
            tree.insert("", "end", iid=p.pupil_id, values=(
                p.pupil_id, p.full_name, p.year_group,
                p.form_group or "-",
                mark or "-", label, notes or "-",
            ))
        present = sum(1 for v in state.values()
                      if MARK_CODES.get(v["mark"], (None, None))[1]
                      in {"present", "late"})
        unmarked = sum(1 for v in state.values() if not v["mark"])
        summary_var.set(
            f"Register loaded: {len(pupils)} pupil(s)    "
            f"present={present}    unmarked={unmarked}")
        host.status_var.set(
            f"Attendance: {date_var.get()} {session_var.get()} "
            f"— {len(pupils)} pupil(s)")

    def _set_mark_for(pupil_id: str) -> None:
        cur = state.get(pupil_id, {"mark": "", "notes": ""})
        dlg = tk.Toplevel(host.root)
        dlg.title(f"Mark — {pupil_id}")
        dlg.transient(host.root)
        dlg.geometry("360x180")
        dlg.update_idletasks()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except tk.TclError:
            pass
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Pupil: {pupil_id}").pack(anchor="w")
        ttk.Label(frm, text=f"{date_var.get()} {session_var.get()}",
                  foreground="#666").pack(anchor="w", pady=(0, 8))
        mark_var = tk.StringVar(
            value=(f"{cur['mark']}  "
                   f"{MARK_CODES.get(cur['mark'], ('', ''))[0]}"
                   if cur["mark"] else ""))
        ttk.Combobox(frm, textvariable=mark_var, values=_mark_choices(),
                     state="readonly", width=36).pack(fill="x")
        notes_var = tk.StringVar(value=cur["notes"])
        ttk.Label(frm, text="Notes:").pack(anchor="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=notes_var, width=40).pack(fill="x")

        def _ok() -> None:
            state[pupil_id] = {
                "mark": _parse_mark(mark_var.get()),
                "notes": notes_var.get().strip(),
            }
            mark = state[pupil_id]["mark"]
            label = MARK_CODES.get(mark, ("", ""))[0] if mark else "-"
            vals = list(tree.item(pupil_id, "values"))
            vals[4] = mark or "-"
            vals[5] = label
            vals[6] = state[pupil_id]["notes"] or "-"
            tree.item(pupil_id, values=tuple(vals))
            dlg.destroy()

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Cancel",
                   command=dlg.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="OK", command=_ok).pack(side="right")

    def _save_register() -> None:
        marks = {pid: s["mark"] for pid, s in state.items() if s["mark"]}
        if not marks:
            messagebox.showinfo("Attendance",
                                "No marks to save.",
                                parent=host.root)
            return
        try:
            results = data.bulk_record(date_var.get().strip(),
                                        session_var.get().strip(), marks)
        except ValidationError as e:
            messagebox.showerror("Attendance", str(e), parent=host.root)
            return
        # Apply notes (bulk_record doesn't take notes)
        for pid, payload in state.items():
            if payload["mark"] and payload["notes"]:
                try:
                    data.record_mark(pid, date_var.get().strip(),
                                     session_var.get().strip(),
                                     payload["mark"], payload["notes"])
                except Exception:
                    logger.exception("note update failed for %s", pid)
        ok = sum(1 for v in results.values()
                 if not isinstance(v, str))
        bad = {k: v for k, v in results.items() if isinstance(v, str)}
        msg = f"Saved {ok} mark(s)."
        if bad:
            msg += "\n\nFailures:\n" + "\n".join(
                f"• {pid}: {err}" for pid, err in bad.items())
            messagebox.showwarning("Attendance", msg, parent=host.root)
        else:
            messagebox.showinfo("Attendance", msg, parent=host.root)
        _refresh()

    tree.bind("<Double-1>",
              lambda _e: (tree.focus()
                          and _set_mark_for(tree.focus())))
    year_var.trace_add("write", lambda *_: _refresh())
    session_var.trace_add("write", lambda *_: _refresh())
    _refresh()


@_safe_view
def _single_mark(host, *, on_done=None) -> None:
    pid = simpledialog.askstring("Single mark", "Pupil ID:",
                                  parent=host.root)
    if not pid:
        return
    pid = pid.strip()
    if not pid:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Mark — {pid}")
    dlg.transient(host.root)
    dlg.geometry("380x220")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    date_var = tk.StringVar(value=_today())
    sess_var = tk.StringVar(value="AM")
    mark_var = tk.StringVar(value="")
    notes_var = tk.StringVar(value="")

    ttk.Label(frm, text=f"Pupil: {pid}",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))
    row = ttk.Frame(frm); row.pack(fill="x", pady=2)
    ttk.Label(row, text="Date:", width=8).pack(side="left")
    ttk.Entry(row, textvariable=date_var, width=14).pack(side="left",
                                                         padx=4)
    row = ttk.Frame(frm); row.pack(fill="x", pady=2)
    ttk.Label(row, text="Session:", width=8).pack(side="left")
    ttk.Combobox(row, textvariable=sess_var, values=list(SESSIONS),
                 state="readonly", width=6).pack(side="left", padx=4)
    row = ttk.Frame(frm); row.pack(fill="x", pady=2)
    ttk.Label(row, text="Mark:", width=8).pack(side="left")
    ttk.Combobox(row, textvariable=mark_var, values=_mark_choices(),
                 state="readonly", width=30).pack(side="left", padx=4)
    row = ttk.Frame(frm); row.pack(fill="x", pady=2)
    ttk.Label(row, text="Notes:", width=8).pack(side="left")
    ttk.Entry(row, textvariable=notes_var, width=30).pack(side="left",
                                                          padx=4)

    def _save() -> None:
        try:
            rec = data.record_mark(
                pid, date_var.get().strip(),
                sess_var.get().strip(),
                _parse_mark(mark_var.get()),
                notes_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Attendance", str(e), parent=dlg)
            return
        messagebox.showinfo(
            "Attendance",
            f"Saved {rec.pupil_id} {rec.date}/{rec.session} = "
            f"{rec.mark} ({rec.label})",
            parent=dlg,
        )
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm); btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _pupil_history(host) -> None:
    pid = simpledialog.askstring("Pupil history", "Pupil ID:",
                                  parent=host.root)
    if not pid:
        return
    pid = pid.strip()
    if not pid:
        return
    try:
        summary = data.pupil_summary(pid)
    except ValidationError as e:
        messagebox.showerror("Attendance", str(e), parent=host.root)
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Attendance — {pid}")
    dlg.transient(host.root)
    dlg.geometry("640x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Pupil {pid}",
              font=("", 11, "bold")).pack(anchor="w")
    ttk.Label(frm,
              text=(f"Total: {summary['total_sessions']}    "
                    f"Present: {summary['present']}    "
                    f"Auth absent: {summary['authorised_absent']}    "
                    f"Unauth absent: {summary['unauthorised_absent']}    "
                    f"Attendance %: {summary['attendance_pct']}"),
              foreground="#444").pack(anchor="w", pady=(2, 8))
    tree = ttk.Treeview(frm, columns=("date", "sess", "mark", "label",
                                       "notes"),
                        show="headings", height=18)
    for c, label, w in [
        ("date", "Date", 100), ("sess", "Sess", 60),
        ("mark", "Mark", 60), ("label", "Status", 160),
        ("notes", "Notes", 200),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    for r in summary["records"]:
        tree.insert("", "end", iid=str(r.record_id), values=(
            r.date, r.session, r.mark, r.label, r.notes or "-"))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))


@_safe_view
def _daily_summary(host, date_iso: str) -> None:
    try:
        summary = data.daily_summary(date_iso.strip())
    except ValidationError as e:
        messagebox.showerror("Attendance", str(e), parent=host.root)
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Daily summary — {summary['date']}")
    dlg.transient(host.root)
    dlg.geometry("520x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Date: {summary['date']}",
              font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))
    for sess, vals in summary["sessions"].items():
        block = ttk.LabelFrame(frm, text=sess, padding=8)
        block.pack(fill="x", pady=4)
        ttk.Label(block,
                  text=(f"Total: {vals['total']}    "
                        f"Present: {vals['present']}    "
                        f"Auth absent: {vals['authorised_absent']}    "
                        f"Unauth absent: {vals['unauthorised_absent']}    "
                        f"Other: {vals['other']}")
                  ).pack(anchor="w")
        if vals["marks"]:
            t = ttk.Treeview(block, columns=("code", "label", "count"),
                             show="headings", height=5)
            t.heading("code", text="Code")
            t.heading("label", text="Status")
            t.heading("count", text="Count")
            t.column("code", width=60)
            t.column("label", width=240)
            t.column("count", width=80, anchor="e")
            t.pack(fill="x", pady=(4, 0))
            for code, n in sorted(vals["marks"].items()):
                label = MARK_CODES.get(code, (code, ""))[0]
                t.insert("", "end", values=(code, label, n))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))
