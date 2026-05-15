"""Tk views for wraparound care."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.wraparound import (
    wraparound as data,
)
from education_system.primarysch_system.modules.domain.wraparound.wraparound import (
    ATTENDANCE_LABELS, ATTENDANCE_STATUSES, DAYS_OF_WEEK,
    Session, SESSION_TYPE_LABELS, SESSION_TYPES,
)
from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError,
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
                messagebox.showerror("Wraparound", str(e),
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


def _session_choices() -> tuple[list[str], dict[str, int]]:
    try:
        sessions = data.list_sessions()
    except Exception:
        logger.exception("list_sessions failed")
        return [], {}
    labels: list[str] = []
    mapping: dict[str, int] = {}
    for s in sessions:
        lbl = (f"#{s.session_id}  {s.name}  "
               f"({SESSION_TYPE_LABELS.get(s.session_type, s.session_type)})"
               + ("" if s.is_active else "  (inactive)"))
        labels.append(lbl)
        mapping[lbl] = s.session_id
    return labels, mapping


@_safe_view
def open_wraparound(host) -> None:
    logger.debug("GUI: open_wraparound")

    win = tk.Toplevel(host.root)
    win.title("Breakfast / After-School Club")
    win.transient(host.root)
    win.geometry("1140x640")

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    sessions_tab = ttk.Frame(nb, padding=10)
    register_tab = ttk.Frame(nb, padding=10)
    attendance_tab = ttk.Frame(nb, padding=10)
    nb.add(sessions_tab, text="Sessions")
    nb.add(register_tab, text="Daily Register")
    nb.add(attendance_tab, text="All Attendance")

    # --- Sessions tab ---------------------------------------------------
    s_filt = ttk.Frame(sessions_tab)
    s_filt.pack(fill="x", pady=(0, 6))
    ttk.Label(s_filt, text="Type:").pack(side="left")
    type_filter = tk.StringVar(value="All")
    ttk.Combobox(s_filt, textvariable=type_filter,
                 values=["All"] + list(SESSION_TYPES),
                 state="readonly", width=14).pack(side="left", padx=(4, 10))
    active_filter = tk.BooleanVar(value=False)
    ttk.Checkbutton(s_filt, text="Active only",
                    variable=active_filter).pack(side="left")

    s_cols = ("session_id", "name", "type", "days", "time", "capacity",
              "fee", "active")
    stree = ttk.Treeview(sessions_tab, columns=s_cols, show="headings",
                         height=14)
    for col, label, width, anchor in [
        ("session_id", "ID", 50, "center"),
        ("name", "Name", 180, "w"),
        ("type", "Type", 140, "w"),
        ("days", "Days", 200, "w"),
        ("time", "Time", 110, "center"),
        ("capacity", "Cap", 60, "center"),
        ("fee", "Fee", 80, "center"),
        ("active", "Active", 70, "center"),
    ]:
        stree.heading(col, text=label)
        stree.column(col, width=width, anchor=anchor)
    stree.pack(fill="both", expand=True, pady=(0, 6))

    s_btns = ttk.Frame(sessions_tab)
    s_btns.pack(fill="x")

    def _refresh_sessions() -> None:
        try:
            st = None if type_filter.get() == "All" else type_filter.get()
            rows = data.list_sessions(session_type=st,
                                      active_only=active_filter.get())
        except ValidationError as e:
            messagebox.showerror("Wraparound", str(e), parent=win)
            return
        except Exception:
            logger.exception("list_sessions failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in stree.get_children():
            stree.delete(iid)
        for s in rows:
            time = ""
            if s.start_time or s.end_time:
                time = f"{s.start_time or '?'}–{s.end_time or '?'}"
            stree.insert("", "end", iid=str(s.session_id), values=(
                s.session_id, s.name,
                SESSION_TYPE_LABELS.get(s.session_type, s.session_type),
                s.days_of_week or "", time,
                s.capacity if s.capacity is not None else "",
                s.fee_display,
                "yes" if s.is_active else "no",
            ))

    def _s_selected() -> int | None:
        sel = stree.selection()
        if not sel:
            messagebox.showinfo("Wraparound", "Select a session first.",
                                parent=win)
            return None
        return int(sel[0])

    def _s_add() -> None:
        _open_session_dialog(win, session_id=None, on_saved=_refresh_all)

    def _s_edit() -> None:
        sid = _s_selected()
        if sid is None:
            return
        _open_session_dialog(win, session_id=sid, on_saved=_refresh_all)

    def _s_toggle() -> None:
        sid = _s_selected()
        if sid is None:
            return
        try:
            data.toggle_session_active(sid)
        except Exception:
            logger.exception("toggle_session(%s) failed", sid)
            messagebox.showerror("Error", "Could not toggle — see logs.",
                                 parent=win)
            return
        _refresh_all()

    def _s_delete() -> None:
        sid = _s_selected()
        if sid is None:
            return
        if not messagebox.askyesno(
                "Delete session",
                f"Delete session #{sid}? "
                f"All attendance rows for this session will be removed.",
                parent=win):
            return
        try:
            data.delete_session(sid)
        except Exception:
            logger.exception("delete_session(%s) failed", sid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh_all()

    ttk.Button(s_btns, text="New session", command=_s_add).pack(side="left")
    ttk.Button(s_btns, text="Edit", command=_s_edit).pack(
        side="left", padx=(8, 0))
    ttk.Button(s_btns, text="Toggle active", command=_s_toggle).pack(
        side="left", padx=(8, 0))
    ttk.Button(s_btns, text="Delete", command=_s_delete).pack(
        side="left", padx=(8, 0))
    stree.bind("<Double-Button-1>", lambda _e: _s_edit())

    # --- Register tab ---------------------------------------------------
    r_top = ttk.Frame(register_tab)
    r_top.pack(fill="x", pady=(0, 6))
    ttk.Label(r_top, text="Session:").pack(side="left")
    reg_session_var = tk.StringVar()
    reg_session_box = ttk.Combobox(r_top, textvariable=reg_session_var,
                                   values=[], state="readonly", width=42)
    reg_session_box.pack(side="left", padx=(4, 10))
    ttk.Label(r_top, text="Date:").pack(side="left")
    today = _dt.date.today().isoformat()
    reg_date_var = tk.StringVar(value=today)
    ttk.Entry(r_top, textvariable=reg_date_var, width=14).pack(
        side="left", padx=(4, 10))

    reg_summary = tk.StringVar()
    ttk.Label(register_tab, textvariable=reg_summary,
              foreground="#444").pack(anchor="w")

    add_row = ttk.LabelFrame(register_tab, text="Add booking", padding=8)
    add_row.pack(fill="x", pady=(8, 6))
    ttk.Label(add_row, text="Pupil ID:").grid(row=0, column=0, sticky="w")
    add_pid_var = tk.StringVar()
    ttk.Entry(add_row, textvariable=add_pid_var, width=14).grid(
        row=0, column=1, padx=(4, 10))
    ttk.Label(add_row, text="Status:").grid(row=0, column=2, sticky="w")
    add_status_var = tk.StringVar(value="booked")
    ttk.Combobox(add_row, textvariable=add_status_var,
                 values=list(ATTENDANCE_STATUSES),
                 state="readonly", width=12).grid(row=0, column=3, padx=(4, 10))

    r_cols = ("attendance_id", "pupil_id", "name", "year", "status")
    rtree = ttk.Treeview(register_tab, columns=r_cols,
                         show="headings", height=16)
    for col, label, width, anchor in [
        ("attendance_id", "#", 60, "center"),
        ("pupil_id", "Pupil ID", 100, "w"),
        ("name", "Name", 260, "w"),
        ("year", "Year", 60, "center"),
        ("status", "Status", 110, "center"),
    ]:
        rtree.heading(col, text=label)
        rtree.column(col, width=width, anchor=anchor)
    rtree.pack(fill="both", expand=True, pady=(0, 6))

    r_btns = ttk.Frame(register_tab)
    r_btns.pack(fill="x")

    def _ssn_id_from_reg() -> int | None:
        labels, mapping = _session_choices()
        if not labels:
            return None
        sel = reg_session_var.get()
        if sel not in mapping:
            return None
        return mapping[sel]

    def _refresh_register() -> None:
        labels, _ = _session_choices()
        reg_session_box["values"] = labels
        sid = _ssn_id_from_reg()
        date = reg_date_var.get().strip()
        for iid in rtree.get_children():
            rtree.delete(iid)
        if sid is None or not date:
            reg_summary.set("Choose a session and date.")
            return
        try:
            rows = data.day_register(sid, date)
        except ValidationError as e:
            messagebox.showerror("Wraparound", str(e), parent=win)
            return
        except Exception:
            logger.exception("day_register(%s, %s) failed", sid, date)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        attended = 0
        for a, p in rows:
            if a.status in ("attended", "late"):
                attended += 1
            rtree.insert("", "end", iid=str(a.attendance_id), values=(
                a.attendance_id, a.pupil_id,
                p.full_name if p else "(unknown)",
                p.year_group if p else "-",
                a.status,
            ))
        sess = data.get_session(sid)
        cap = (f"   capacity {sess.capacity}"
               if sess and sess.capacity is not None else "")
        reg_summary.set(
            f"{date} — {len(rows)} on register, "
            f"{attended} present{cap}")

    def _r_add_booking() -> None:
        sid = _ssn_id_from_reg()
        date = reg_date_var.get().strip()
        if sid is None or not date:
            messagebox.showinfo("Wraparound", "Choose a session and date.",
                                parent=win)
            return
        pid = add_pid_var.get().strip()
        if not pid:
            messagebox.showinfo("Wraparound", "Enter a pupil ID.", parent=win)
            return
        try:
            data.book({
                "session_id": sid, "pupil_id": pid, "date": date,
                "status": add_status_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Wraparound", str(e), parent=win)
            return
        except Exception:
            logger.exception("book failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=win)
            return
        add_pid_var.set("")
        _refresh_register()

    ttk.Button(add_row, text="Book", command=_r_add_booking).grid(
        row=0, column=4)
    add_row.columnconfigure(5, weight=1)

    def _r_selected_id() -> int | None:
        sel = rtree.selection()
        if not sel:
            messagebox.showinfo("Wraparound", "Select a row first.",
                                parent=win)
            return None
        return int(sel[0])

    def _r_mark(status: str) -> None:
        aid = _r_selected_id()
        if aid is None:
            return
        try:
            data.set_attendance_status(aid, status)
        except ValidationError as e:
            messagebox.showerror("Wraparound", str(e), parent=win)
            return
        except Exception:
            logger.exception("set_attendance_status(%s, %s) failed",
                             aid, status)
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=win)
            return
        _refresh_register()

    def _r_delete() -> None:
        aid = _r_selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Delete row",
                                   f"Remove attendance #{aid}?", parent=win):
            return
        try:
            data.delete_attendance(aid)
        except Exception:
            logger.exception("delete_attendance(%s) failed", aid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh_register()

    ttk.Button(r_btns, text="Mark attended",
               command=lambda: _r_mark("attended")).pack(side="left")
    ttk.Button(r_btns, text="Mark late",
               command=lambda: _r_mark("late")).pack(side="left", padx=(8, 0))
    ttk.Button(r_btns, text="Mark absent",
               command=lambda: _r_mark("absent")).pack(side="left", padx=(8, 0))
    ttk.Button(r_btns, text="Mark booked",
               command=lambda: _r_mark("booked")).pack(side="left", padx=(8, 0))
    ttk.Button(r_btns, text="Remove row",
               command=_r_delete).pack(side="left", padx=(8, 0))
    ttk.Button(r_btns, text="Refresh",
               command=_refresh_register).pack(side="left", padx=(8, 0))

    # --- Attendance (all) tab ------------------------------------------
    a_filt = ttk.Frame(attendance_tab)
    a_filt.pack(fill="x", pady=(0, 6))
    ttk.Label(a_filt, text="Session:").pack(side="left")
    att_session_var = tk.StringVar(value="All")
    att_session_box = ttk.Combobox(a_filt, textvariable=att_session_var,
                                   values=["All"], state="readonly", width=36)
    att_session_box.pack(side="left", padx=(4, 10))
    ttk.Label(a_filt, text="Pupil ID:").pack(side="left")
    att_pupil_var = tk.StringVar()
    ttk.Entry(a_filt, textvariable=att_pupil_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(a_filt, text="From:").pack(side="left")
    att_from_var = tk.StringVar()
    ttk.Entry(a_filt, textvariable=att_from_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(a_filt, text="To:").pack(side="left")
    att_to_var = tk.StringVar()
    ttk.Entry(a_filt, textvariable=att_to_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(a_filt, text="Status:").pack(side="left")
    att_status_var = tk.StringVar(value="All")
    ttk.Combobox(a_filt, textvariable=att_status_var,
                 values=["All"] + list(ATTENDANCE_STATUSES),
                 state="readonly", width=10).pack(side="left", padx=(4, 10))

    a_cols = ("attendance_id", "date", "session", "pupil", "name",
              "year", "status")
    atree = ttk.Treeview(attendance_tab, columns=a_cols,
                         show="headings", height=16)
    for col, label, width, anchor in [
        ("attendance_id", "#", 60, "center"),
        ("date", "Date", 100, "center"),
        ("session", "Session", 200, "w"),
        ("pupil", "Pupil ID", 90, "w"),
        ("name", "Name", 220, "w"),
        ("year", "Yr", 50, "center"),
        ("status", "Status", 100, "center"),
    ]:
        atree.heading(col, text=label)
        atree.column(col, width=width, anchor=anchor)
    atree.pack(fill="both", expand=True, pady=(0, 6))

    a_btns = ttk.Frame(attendance_tab)
    a_btns.pack(fill="x")

    def _att_session_map() -> tuple[dict[str, int], list[str]]:
        try:
            sessions = data.list_sessions()
        except Exception:
            return {}, ["All"]
        labels = ["All"]
        mapping: dict[str, int] = {}
        for s in sessions:
            lbl = f"#{s.session_id} {s.name}"
            labels.append(lbl)
            mapping[lbl] = s.session_id
        return mapping, labels

    def _refresh_attendance() -> None:
        mapping, labels = _att_session_map()
        att_session_box["values"] = labels
        sel = att_session_var.get()
        sid: int | None = None
        if sel != "All" and sel in mapping:
            sid = mapping[sel]
        try:
            rows = data.list_attendance(
                session_id=sid,
                pupil_id=att_pupil_var.get().strip() or None,
                from_date=att_from_var.get().strip() or None,
                to_date=att_to_var.get().strip() or None,
                status=None if att_status_var.get() == "All"
                else att_status_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Wraparound", str(e), parent=win)
            return
        except Exception:
            logger.exception("list_attendance failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in atree.get_children():
            atree.delete(iid)
        for a, sess, p in rows[:500]:
            atree.insert("", "end", iid=str(a.attendance_id), values=(
                a.attendance_id, a.date,
                sess.name if sess else f"#{a.session_id}",
                a.pupil_id, p.full_name if p else "(unknown)",
                p.year_group if p else "-", a.status,
            ))

    def _a_selected_id() -> int | None:
        sel = atree.selection()
        if not sel:
            messagebox.showinfo("Wraparound", "Select a row first.",
                                parent=win)
            return None
        return int(sel[0])

    def _a_change_status() -> None:
        aid = _a_selected_id()
        if aid is None:
            return
        new = att_status_var.get()
        if new == "All":
            messagebox.showinfo(
                "Wraparound",
                "Pick a specific status in the filter, then click again.",
                parent=win)
            return
        try:
            data.set_attendance_status(aid, new)
        except Exception:
            logger.exception("set_attendance_status(%s, %s) failed", aid, new)
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=win)
            return
        _refresh_attendance()

    def _a_delete() -> None:
        aid = _a_selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Delete row",
                                   f"Delete attendance #{aid}?", parent=win):
            return
        try:
            data.delete_attendance(aid)
        except Exception:
            logger.exception("delete_attendance(%s) failed", aid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh_attendance()

    ttk.Button(a_btns, text="Apply status from filter",
               command=_a_change_status).pack(side="left")
    ttk.Button(a_btns, text="Delete",
               command=_a_delete).pack(side="left", padx=(8, 0))
    ttk.Button(a_btns, text="Refresh",
               command=_refresh_attendance).pack(side="left", padx=(8, 0))

    ttk.Button(win, text="Close", command=win.destroy).pack(
        anchor="e", padx=12, pady=(0, 10))

    def _refresh_all() -> None:
        _refresh_sessions()
        _refresh_register()
        _refresh_attendance()

    type_filter.trace_add("write", lambda *_: _refresh_sessions())
    active_filter.trace_add("write", lambda *_: _refresh_sessions())
    reg_session_var.trace_add("write", lambda *_: _refresh_register())
    reg_date_var.trace_add("write", lambda *_: _refresh_register())
    for v in (att_session_var, att_pupil_var, att_from_var,
              att_to_var, att_status_var):
        v.trace_add("write", lambda *_: _refresh_attendance())

    _refresh_all()


def _open_session_dialog(parent, *, session_id: int | None,
                         on_saved: Callable[[], None]) -> None:
    existing: Session | None = None
    if session_id is not None:
        try:
            existing = data.get_session(session_id)
        except Exception:
            logger.exception("get_session(%s) failed", session_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Wraparound",
                                 f"No session #{session_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Session" if existing else "New session")
    dlg.transient(parent)
    dlg.geometry("480x520")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Name *").grid(row=0, column=0, sticky="w", pady=3)
    name_var = tk.StringVar(value=existing.name if existing else "")
    ttk.Entry(frm, textvariable=name_var, width=30).grid(
        row=0, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Type *").grid(row=1, column=0, sticky="w", pady=3)
    type_var = tk.StringVar(
        value=existing.session_type if existing else SESSION_TYPES[0])
    ttk.Combobox(frm, textvariable=type_var, values=list(SESSION_TYPES),
                 state="readonly", width=20).grid(
        row=1, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Days (comma-sep)").grid(
        row=2, column=0, sticky="w", pady=3)
    days_var = tk.StringVar(
        value=existing.days_of_week or "" if existing else "")
    ttk.Entry(frm, textvariable=days_var, width=30).grid(
        row=2, column=1, columnspan=2, sticky="ew", pady=3)
    ttk.Label(frm, text=f"({', '.join(DAYS_OF_WEEK)})",
              foreground="#888").grid(
        row=3, column=1, columnspan=2, sticky="w")

    ttk.Label(frm, text="Start (HH:MM)").grid(
        row=4, column=0, sticky="w", pady=3)
    start_var = tk.StringVar(value=existing.start_time or "" if existing else "")
    ttk.Entry(frm, textvariable=start_var, width=10).grid(
        row=4, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="End (HH:MM)").grid(
        row=5, column=0, sticky="w", pady=3)
    end_var = tk.StringVar(value=existing.end_time or "" if existing else "")
    ttk.Entry(frm, textvariable=end_var, width=10).grid(
        row=5, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Capacity").grid(row=6, column=0, sticky="w", pady=3)
    cap_var = tk.StringVar(
        value="" if not existing or existing.capacity is None
        else str(existing.capacity))
    ttk.Entry(frm, textvariable=cap_var, width=8).grid(
        row=6, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Fee (£)").grid(row=7, column=0, sticky="w", pady=3)
    fee_default = ""
    if existing and existing.fee_pence:
        fee_default = f"{existing.fee_pence/100:.2f}"
    fee_var = tk.StringVar(value=fee_default)
    ttk.Entry(frm, textvariable=fee_var, width=10).grid(
        row=7, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="(0 or blank = free)",
              foreground="#888").grid(row=7, column=2, sticky="w", padx=(8, 0))

    active_var = tk.BooleanVar(value=existing.is_active if existing else True)
    ttk.Checkbutton(frm, text="Active",
                    variable=active_var).grid(
        row=8, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Notes").grid(row=9, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=30).grid(
        row=9, column=1, columnspan=2, sticky="ew", pady=3)
    frm.columnconfigure(1, weight=1)
    frm.columnconfigure(2, weight=1)

    def _save() -> None:
        payload = {
            "name": name_var.get(),
            "session_type": type_var.get(),
            "days_of_week": days_var.get(),
            "start_time": start_var.get(),
            "end_time": end_var.get(),
            "capacity": cap_var.get(),
            "fee_pounds": fee_var.get(),
            "is_active": active_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.create_session(payload)
            else:
                data.update_session(existing.session_id, payload)
        except ValidationError as e:
            messagebox.showerror("Wraparound", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save session failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
