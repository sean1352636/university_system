"""Tk views for peer mentoring."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pastoral.peer_mentoring import (
    peer_mentoring as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.peer_mentoring.peer_mentoring import (
    PAIRING_STATUSES, FOCUS_AREAS, FREQUENCIES, SESSION_OUTCOMES,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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
                messagebox.showerror("Peer Mentoring", str(e),
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


def _pairing_dialog(host, title: str,
                     initial: dict[str, Any] | None = None
                     ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("500x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    mentor_var = tk.StringVar(value=str(initial.get("mentor_id") or ""))
    mentee_var = tk.StringVar(value=str(initial.get("mentee_id") or ""))
    ay_var     = tk.StringVar(value=str(initial.get("academic_year")
                                          or ""))
    focus_var  = tk.StringVar(value=str(initial.get("focus")
                                          or "Academic"))
    freq_var   = tk.StringVar(value=str(initial.get("frequency")
                                          or "Weekly"))
    coord_var  = tk.StringVar(value=str(initial.get("coordinator")
                                          or ""))
    start_var  = tk.StringVar(value=str(initial.get("start_date")
                                          or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status")
                                          or "Proposed"))

    rows: list[tuple[str, tk.Widget]] = [
        ("Mentor ID:",     ttk.Entry(frm, textvariable=mentor_var,
                                        width=14)),
        ("Mentee ID:",     ttk.Entry(frm, textvariable=mentee_var,
                                        width=14)),
        ("Academic year:", ttk.Entry(frm, textvariable=ay_var,
                                        width=10)),
        ("Focus:",         ttk.Combobox(frm, textvariable=focus_var,
                                          values=list(FOCUS_AREAS),
                                          state="readonly", width=18)),
        ("Frequency:",     ttk.Combobox(frm, textvariable=freq_var,
                                          values=list(FREQUENCIES),
                                          state="readonly", width=14)),
        ("Coordinator:",   ttk.Entry(frm, textvariable=coord_var,
                                        width=28)),
        ("Start date:",    ttk.Entry(frm, textvariable=start_var,
                                        width=14)),
        ("End date:",      ttk.Entry(frm, textvariable=end_var,
                                        width=14)),
        ("Status:",        ttk.Combobox(frm, textvariable=status_var,
                                          values=list(PAIRING_STATUSES),
                                          state="readonly", width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Goals:", "goals", 3),
                   ("Notes:", "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(rows)):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                         pady=2)
        t = tk.Text(frm, width=44, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.grid(row=i, column=1, sticky="ew", pady=2)
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "mentor_id":     mentor_var.get().strip(),
            "mentee_id":     mentee_var.get().strip(),
            "academic_year": ay_var.get().strip(),
            "focus":         focus_var.get().strip(),
            "frequency":     freq_var.get().strip(),
            "coordinator":   coord_var.get().strip(),
            "start_date":    start_var.get().strip(),
            "end_date":      end_var.get().strip(),
            "status":        status_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + len(text_fields), column=0,
              columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _session_dialog(host, pairing_id: int,
                     initial: dict[str, Any] | None = None
                     ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Session — pairing #{pairing_id}")
    dlg.transient(host.root)
    dlg.geometry("520x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    date_var = tk.StringVar(value=str(initial.get("session_date") or ""))
    time_var = tk.StringVar(value=str(initial.get("session_time") or ""))
    dur_var  = tk.StringVar(value=str(initial.get("duration_min") or ""))
    loc_var  = tk.StringVar(value=str(initial.get("location") or ""))
    outcome_var = tk.StringVar(value=str(initial.get("outcome")
                                            or "Attended"))
    concerns_var = tk.BooleanVar(value=bool(initial.get("concerns_flag")))

    rows: list[tuple[str, tk.Widget]] = [
        ("Date:",    ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Time:",    ttk.Entry(frm, textvariable=time_var, width=8)),
        ("Duration (min):", ttk.Entry(frm, textvariable=dur_var,
                                        width=6)),
        ("Location:", ttk.Entry(frm, textvariable=loc_var, width=22)),
        ("Outcome:", ttk.Combobox(frm, textvariable=outcome_var,
                                    values=list(SESSION_OUTCOMES),
                                    state="readonly", width=18)),
        ("Concerns:", ttk.Checkbutton(frm, variable=concerns_var)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    text_fields = [("Agenda:", "agenda", 3),
                   ("Follow-up:", "follow_up", 2),
                   ("Notes:", "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for label, key, lines in text_fields:
        ttk.Label(frm, text=label).pack(anchor="w", pady=(8, 0))
        t = tk.Text(frm, width=54, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.pack(fill="x")
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pairing_id":    pairing_id,
            "session_date":  date_var.get().strip(),
            "session_time":  time_var.get().strip(),
            "duration_min":  dur_var.get().strip(),
            "location":      loc_var.get().strip(),
            "outcome":       outcome_var.get().strip(),
            "concerns_flag": bool(concerns_var.get()),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_peer_mentoring(host) -> None:
    logger.debug("GUI: open_peer_mentoring")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Peer Mentoring",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Academic year:").pack(side="left", padx=(0, 4))
    ay_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=ay_var, width=10).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *PAIRING_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Focus:").pack(side="left", padx=(0, 4))
    focus_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=focus_var,
                 values=["", *FOCUS_AREAS], state="readonly",
                 width=14).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Sessions",
               command=lambda: _open_sessions(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="End",
               command=lambda: _end(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "ay", "mentor", "mentee", "focus", "freq",
            "status", "start")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("ay", "Academic yr", 100),
        ("mentor", "Mentor", 200), ("mentee", "Mentee", 200),
        ("focus", "Focus", 110), ("freq", "Frequency", 100),
        ("status", "Status", 100), ("start", "Start", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_pairings(
                academic_year=ay_var.get().strip() or None,
                status=status_var.get().strip() or None,
                focus=focus_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Peer Mentoring", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("peer_mentoring refresh failed")
            messagebox.showerror("Peer Mentoring",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for p in rows:
            mentor = (f"{p.mentor_id} ({p.mentor_name or '-'}, "
                      f"Yr {p.mentor_year or '-'})")
            mentee = (f"{p.mentee_id} ({p.mentee_name or '-'}, "
                      f"Yr {p.mentee_year or '-'})")
            tree.insert("", "end", iid=str(p.pairing_id), values=(
                p.pairing_id, p.academic_year, mentor, mentee,
                p.focus, p.frequency, p.status, p.start_date,
            ))
        try:
            s = data.cohort_summary(
                academic_year=ay_var.get().strip() or None)
            summary_var.set(
                f"Pairings: {s['total']}    Active: {s['active']}    "
                f"Mentors: {s['mentors']}    "
                f"Mentees: {s['mentees']}")
        except Exception:
            summary_var.set(f"{len(rows)} pairing(s)")
        host.status_var.set(f"Peer Mentoring: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_sessions(host, tree))
    status_var.trace_add("write", lambda *_: _refresh())
    focus_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Peer Mentoring",
                            "Select a pairing first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _pairing_dialog(host, "New pairing")
    if not fields:
        return
    p = data.create_pairing(fields)
    messagebox.showinfo(
        "Peer Mentoring",
        f"Created pairing #{p.pairing_id}: "
        f"{p.mentor_id} → {p.mentee_id} ({p.focus})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    pid = _selected_id(tree, host)
    if pid is None:
        return
    existing = data.get_pairing(pid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "mentor_id", "mentee_id", "academic_year", "focus",
        "frequency", "coordinator", "start_date", "end_date",
        "status", "goals", "notes")}
    fields = _pairing_dialog(host, f"Edit pairing #{pid}",
                                initial=initial)
    if not fields:
        return
    data.update_pairing(pid, fields)
    if on_done:
        on_done()


@_safe_view
def _end(host, tree: ttk.Treeview, *, on_done=None) -> None:
    pid = _selected_id(tree, host)
    if pid is None:
        return
    end = simpledialog.askstring(
        "End pairing",
        "End date (YYYY-MM-DD, blank = today):",
        parent=host.root)
    if end is None:
        return
    data.end_pairing(pid, end_date=end.strip() or None)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    pid = _selected_id(tree, host)
    if pid is None:
        return
    existing = data.get_pairing(pid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete pairing",
            f"Delete {existing.mentor_id} → {existing.mentee_id} "
            f"and ALL sessions?",
            parent=host.root):
        return
    data.delete_pairing(pid)
    if on_done:
        on_done()


@_safe_view
def _open_sessions(host, tree: ttk.Treeview) -> None:
    pid = _selected_id(tree, host)
    if pid is None:
        return
    rec = data.get_pairing(pid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Sessions — pairing #{pid}")
    dlg.transient(host.root)
    dlg.geometry("780x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    header_var = tk.StringVar()
    ttk.Label(frm, textvariable=header_var,
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Log session",
               command=lambda: _do_add()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "date", "time", "dur",
                                 "outcome", "concerns", "agenda"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("time", "Time", 60), ("dur", "Min", 50),
        ("outcome", "Outcome", 140), ("concerns", "Concerns", 80),
        ("agenda", "Agenda", 300),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    t.tag_configure("concerns", background="#fde7e7")

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.pairing_summary(pid)
        except Exception as e:
            logger.exception("pairing_summary failed")
            messagebox.showerror("Peer Mentoring",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        p = s["pairing"]
        header_var.set(
            f"#{p.pairing_id} {p.mentor_id} → {p.mentee_id} "
            f"({p.focus}, {p.frequency}, {p.status})    "
            f"Sessions: {s['session_count']}    "
            f"Attended: {s['attended']}    "
            f"Missed: {s['missed']}    "
            f"Concerns: {s['concerns']}")
        for sess in s["sessions"]:
            tags = ("concerns",) if sess.concerns_flag else ()
            t.insert("", "end", iid=str(sess.session_id), values=(
                sess.session_id, sess.session_date,
                sess.session_time or "-",
                sess.duration_min if sess.duration_min else "-",
                sess.outcome,
                "Yes" if sess.concerns_flag else "No",
                (sess.agenda or "-")[:100],
            ), tags=tags)

    def _do_add() -> None:
        fields = _session_dialog(host, pid)
        if not fields:
            return
        try:
            data.log_session(fields)
        except ValidationError as e:
            messagebox.showerror("Peer Mentoring", str(e),
                                 parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Peer Mentoring",
                                "Select a session first.", parent=dlg)
            return
        try:
            sid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete session",
                f"Delete session #{sid}?", parent=dlg):
            return
        data.delete_session(sid)
        _refresh()

    _refresh()
