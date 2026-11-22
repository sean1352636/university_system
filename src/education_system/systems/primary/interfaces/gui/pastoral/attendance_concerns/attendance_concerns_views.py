"""Tk views for attendance concerns."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.pastoral.attendance_concerns import (
    attendance_concerns as data,
)
from education_system.systems.primary.domain.pastoral.attendance_concerns.attendance_concerns import (
    CONCERN_STATUSES, CONCERN_LEVELS, CONCERN_TYPES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError,
)
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Attendance Concerns", str(e),
                                       parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\n"
                    f"See logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


def _owner(host, owner=None):
    """The window a pop-up belongs to: the page's own window when the page
    was popped out, else the main window."""
    return owner if owner is not None else host.root


def _ay_choices() -> list[str]:
    """Academic years in the "2026/27" form this domain stores (the kit's
    years are "2026-27")."""
    return [y.replace("-", "/") for y in kit.academic_years()]


def _current_ay() -> str:
    years = kit.academic_years(back=0, ahead=0)
    return years[0].replace("-", "/") if years else ""


def _ask_date(owner, title: str, prompt: str) -> str | None:
    """A date picked from drop-downs ("" = left blank); None if cancelled."""
    dlg = tk.Toplevel(owner)
    dlg.title(title)
    dlg.transient(owner)
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=prompt).pack(anchor="w", pady=(0, 6))
    var = tk.StringVar()
    kit.DateField(frm, var).pack(anchor="w")
    result: str | None = None

    def _ok() -> None:
        nonlocal result
        result = var.get().strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(btns, text="OK", command=_ok).pack(side="right")
    dlg.wait_window()
    return result


def _concern_dialog(host, title: str,
                      initial: dict[str, Any] | None = None, *,
                      owner=None) -> dict[str, Any] | None:
    master = _owner(host, owner)
    dlg = tk.Toplevel(master)
    dlg.title(title)
    dlg.transient(master)
    dlg.geometry("600x620")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    initial = initial or {}
    frm, footer = kit.scrolled_form(dlg)

    pupil_var  = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    ay_var     = tk.StringVar(value=str(initial.get("academic_year")
                                           or _current_ay()))
    type_var   = tk.StringVar(value=str(initial.get("concern_type")
                                           or "Persistent absence"))
    level_var  = tk.StringVar(value=str(initial.get("level")
                                           or "PA threshold (<90%)"))
    att_var    = tk.StringVar(value=str(initial.get("attendance_pct") or ""))
    thr_var    = tk.StringVar(value=str(initial.get("threshold_pct") or 90.0))
    open_var   = tk.StringVar(value=str(initial.get("opened_date") or ""))
    review_var = tk.StringVar(value=str(initial.get("next_review_date") or ""))
    close_var  = tk.StringVar(value=str(initial.get("closed_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Open"))
    worker_var = tk.StringVar(value=str(initial.get("key_worker") or ""))
    parent_var = tk.StringVar(value=str(initial.get("parent_contact") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil:",        kit.PupilPicker(frm, pupil_var)),
        ("Academic year:", kit.ChoiceField(frm, ay_var, choices=_ay_choices(),
                                           editable=True, width=10)),
        ("Concern type:", kit.ChoiceField(frm, type_var,
                                          choices=CONCERN_TYPES, width=22)),
        ("Level:",        kit.ChoiceField(frm, level_var,
                                          choices=CONCERN_LEVELS, width=22)),
        ("Attendance %:", kit.NumberField(frm, att_var, from_=0, to=100,
                                          increment=0.1)),
        ("Threshold %:",  kit.NumberField(frm, thr_var, from_=0, to=100,
                                          increment=0.1)),
        ("Opened:",       kit.DateField(frm, open_var)),
        ("Next review:",  kit.DateField(frm, review_var)),
        ("Closed:",       kit.DateField(frm, close_var)),
        ("Status:",       kit.ChoiceField(frm, status_var,
                                          choices=CONCERN_STATUSES,
                                          width=14)),
        ("Key worker:",   kit.StaffPicker(frm, worker_var, by="name")),
        ("Parent ctc:",   ttk.Entry(frm, textvariable=parent_var, width=24)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                          pady=2)
        widget.grid(row=i, column=1, sticky="w", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Intervention:", "intervention", 3),
                    ("Notes:",        "notes", 3)]
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
            "pupil_id":         pupil_var.get().strip(),
            "academic_year":    ay_var.get().strip(),
            "concern_type":     type_var.get().strip(),
            "level":            level_var.get().strip(),
            "attendance_pct":   att_var.get().strip(),
            "threshold_pct":    thr_var.get().strip(),
            "opened_date":      open_var.get().strip(),
            "next_review_date": review_var.get().strip(),
            "closed_date":      close_var.get().strip(),
            "status":           status_var.get().strip(),
            "key_worker":       worker_var.get().strip(),
            "parent_contact":   parent_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    ttk.Button(footer, text="Cancel",
                  command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(footer, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_attendance_concerns(host) -> None:
    logger.debug("GUI: open_attendance_concerns")
    kit.show_page(host, "Attendance Concerns",
                  lambda parent: _draw_attendance_concerns(parent, host))


def _draw_attendance_concerns(parent, host) -> None:
    root = parent
    win = parent.winfo_toplevel()
    kit.page_heading(root, "Attendance Concerns",
                     "Persistent-absence cases: levels, reviews and "
                     "interventions.")

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var,
                foreground="#666").pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Academic year:").pack(side="left", padx=(0, 4))
    ay_var = tk.StringVar(value="")
    kit.ChoiceField(bar, ay_var, choices=_ay_choices(), blank=True,
                    width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    kit.ChoiceField(bar, status_var, choices=CONCERN_STATUSES, blank=True,
                    width=12).pack(side="left", padx=(0, 6))
    open_only_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Open only",
                       variable=open_only_var).pack(side="left", padx=4)
    ttk.Button(bar, text="Apply",
                  command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
                  command=lambda: _new(host, on_done=_refresh,
                                        owner=win)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
                  command=lambda: _edit(host, tree, on_done=_refresh,
                                        owner=win)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Close",
                  command=lambda: _close(host, tree, on_done=_refresh,
                                        owner=win)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
                  command=lambda: _delete(host, tree, on_done=_refresh,
                                        owner=win)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
                  command=lambda: _refresh()).pack(side="left", padx=2)

    tree = kit.tree(root, [
        ("id", "ID", 50), ("pupil", "Pupil", 200),
        ("year", "Yr", 50), ("ay", "AY", 80),
        ("type", "Type", 160), ("level", "Level", 150),
        ("att", "Att%", 60), ("status", "Status", 100),
        ("opened", "Opened", 90), ("review", "Review", 90),
    ], height=18, tags={"severe": "#fde7e7", "closed": {"foreground": "#888"},
                        "escalated": "#ffe4b3"})

    def _refresh() -> None:
        if not tree.winfo_exists():
            return
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_concerns(
                academic_year=ay_var.get().strip() or None,
                status=status_var.get().strip() or None,
                open_only=open_only_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Attendance Concerns", str(e),
                                   parent=win)
            return
        except Exception as e:
            logger.exception("attendance_concerns refresh failed")
            messagebox.showerror("Attendance Concerns",
                                   f"Could not load:\n\n{e}",
                                   parent=win)
            return
        for c in rows:
            pupil = f"{c.pupil_id} ({c.pupil_name or '-'})"
            att = (f"{c.attendance_pct:.1f}"
                    if c.attendance_pct is not None else "-")
            tags = []
            if c.status == "Closed":
                tags.append("closed")
            elif c.status == "Escalated":
                tags.append("escalated")
            elif c.attendance_pct is not None and c.attendance_pct < 80:
                tags.append("severe")
            tree.insert("", "end", iid=str(c.concern_id), values=(
                c.concern_id, pupil, c.pupil_year or "-",
                c.academic_year, c.concern_type, c.level, att,
                c.status, c.opened_date,
                c.next_review_date or "-",
            ), tags=tuple(tags))
        try:
            s = data.cohort_summary(
                academic_year=ay_var.get().strip() or None)
            avg = (f"{s['avg_attendance']:.2f}%"
                    if s["avg_attendance"] is not None else "-")
            summary_var.set(
                f"Concerns: {s['total']}    Open: {s['open']}    "
                f"Pupils: {s['pupils']}    Avg attendance: {avg}")
        except Exception:
            summary_var.set(f"{len(rows)} concern(s)")
        status_bar = getattr(host, "status_var", None)
        if status_bar is not None:
            status_bar.set(f"Attendance Concerns: {len(rows)} record(s)")

    tree.bind("<Double-1>",
                lambda _e: _edit(host, tree, on_done=_refresh, owner=win))
    ay_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    open_only_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host, owner=None) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Attendance Concerns",
                              "Select a concern first.",
                              parent=_owner(host, owner))
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None, owner=None) -> None:
    fields = _concern_dialog(host, "New attendance concern", owner=owner)
    if not fields:
        return
    c = data.create(fields)
    messagebox.showinfo(
        "Attendance Concerns",
        f"Created concern #{c.concern_id}: {c.pupil_id} — "
        f"{c.concern_type} ({c.status})",
        parent=_owner(host, owner),
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    cid = _selected_id(tree, host, owner)
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "academic_year", "concern_type", "level",
        "attendance_pct", "threshold_pct", "opened_date",
        "next_review_date", "closed_date", "status",
        "key_worker", "intervention", "parent_contact", "notes")}
    fields = _concern_dialog(host, f"Edit concern #{cid}",
                                initial=initial, owner=owner)
    if not fields:
        return
    data.update(cid, fields)
    if on_done:
        on_done()


@_safe_view
def _close(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    cid = _selected_id(tree, host, owner)
    if cid is None:
        return
    end = _ask_date(_owner(host, owner), "Close concern",
                    "Closed date (blank = today):")
    if end is None:
        return
    data.close(cid, closed_date=end.strip() or None)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    cid = _selected_id(tree, host, owner)
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete concern",
            f"Delete concern #{cid} ({existing.pupil_id} / "
            f"{existing.concern_type})?",
            parent=_owner(host, owner)):
        return
    data.delete(cid)
    if on_done:
        on_done()
