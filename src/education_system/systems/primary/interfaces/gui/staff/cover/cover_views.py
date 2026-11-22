"""Tk views for cover arrangements."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.staff.cover import (
    cover as data,
)
from education_system.systems.primary.domain.staff.cover.cover import (
    STATUSES, MIN_PERIOD, MAX_PERIOD,
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
                messagebox.showerror("Cover", str(e),
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


class _Owner:
    """The host as the cover helpers see it, but with ``root`` = the
    window the page is drawn in (the main window, or its pop-out), so
    dialogs and messages open over the right window."""

    def __init__(self, host, parent: tk.Misc) -> None:
        self._host = host
        self.root = parent.winfo_toplevel()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._host, name)


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("600x560")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm, footer = kit.scrolled_form(dlg)

    date_var    = tk.StringVar(value=str(initial.get("date") or _today()))
    period_var  = tk.StringVar(value=str(initial.get("period") or
                                           MIN_PERIOD))
    absent_var  = tk.StringVar(value=str(initial.get("absent_teacher") or ""))
    cover_var   = tk.StringVar(value=str(initial.get("cover_teacher") or ""))
    year_var    = tk.StringVar(value=str(initial.get("year_group") or ""))
    form_var    = tk.StringVar(value=str(initial.get("form_group") or ""))
    room_var    = tk.StringVar(value=str(initial.get("room") or ""))
    status_var  = tk.StringVar(value=str(initial.get("status") or "Pending"))
    reason_var  = tk.StringVar(value=str(initial.get("reason") or ""))

    initial_sid = initial.get("subject_id")
    subject_var = tk.StringVar(value="" if initial_sid is None else str(initial_sid))

    rows: list[tuple[str, tk.Widget]] = [
        ("Date:",    kit.DateField(frm, date_var)),
        ("Period:",  kit.NumberField(frm, period_var, from_=MIN_PERIOD, to=MAX_PERIOD,
                                     width=6)),
        ("Absent teacher:", kit.StaffPicker(frm, absent_var, by="name")),
        ("Cover teacher:",  kit.StaffPicker(frm, cover_var, by="name")),
        ("Year:",   kit.YearGroupPicker(frm, year_var, blank=True)),
        ("Form:",   kit.ClassPicker(frm, form_var)),
        ("Subject:", kit.SubjectPicker(frm, subject_var, by="id", width=36)),
        ("Room:",   ttk.Entry(frm, textvariable=room_var, width=12)),
        ("Status:", kit.ChoiceField(frm, status_var, choices=STATUSES, width=14)),
        ("Reason:", ttk.Entry(frm, textvariable=reason_var, width=36)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
        widget.grid(row=i, column=1, sticky="w", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0, sticky="nw",
                                        pady=2)
    notes_widget = tk.Text(frm, width=40, height=4, wrap="word")
    notes_widget.insert("1.0", str(initial.get("notes") or ""))
    notes_widget.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "date":           date_var.get().strip(),
            "period":         period_var.get().strip(),
            "absent_teacher": absent_var.get().strip(),
            "cover_teacher":  cover_var.get().strip(),
            "year_group":     year_var.get().strip(),
            "form_group":     form_var.get().strip(),
            "subject_id":     subject_var.get().strip(),
            "room":           room_var.get().strip(),
            "status":         status_var.get().strip(),
            "reason":         reason_var.get().strip(),
            "notes":          notes_widget.get("1.0", "end").strip(),
        }
        dlg.destroy()

    ttk.Button(footer, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(footer, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_cover(host) -> None:
    logger.debug("GUI: open_cover")
    kit.show_page(host, "Cover", lambda parent: _draw_cover(parent, host))


def _draw_cover(parent, main_host) -> None:
    host = _Owner(main_host, parent)
    root = parent
    kit.page_heading(root, "Cover",
                     "Cover for absent teachers: who is covering which class and "
                     "period, and the day's cover load.")

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Date:").pack(side="left", padx=(0, 4))
    date_var = tk.StringVar(value=_today())
    kit.DateField(bar, date_var).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    kit.ChoiceField(bar, status_var, choices=STATUSES, blank=True,
                    width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Absent:").pack(side="left", padx=(0, 4))
    absent_var = tk.StringVar(value="")
    kit.StaffPicker(bar, absent_var, by="name", active_only=False,
                    width=24).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Filter",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)).pack(side="left",
                                                                   padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Assign",
               command=lambda: _assign_selected(host, tree,
                                                  on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Set status",
               command=lambda: _status_selected(host, tree,
                                                  on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(host, tree,
                                                  on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Daily load",
               command=lambda: _daily_load(host, date_var.get())
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "p", "yr", "form", "subj", "absent",
            "cover", "room", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 90), ("p", "P", 40),
        ("yr", "Yr", 50), ("form", "Form", 60),
        ("subj", "Subj", 70),
        ("absent", "Absent", 150), ("cover", "Cover", 150),
        ("room", "Room", 70), ("status", "Status", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_arrangements(
                date=date_var.get().strip() or None,
                teacher=absent_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Cover", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("cover refresh failed")
            messagebox.showerror("Cover",
                                 f"Could not load cover list:\n\n{e}",
                                 parent=host.root)
            return
        for c in rows:
            tree.insert("", "end", iid=str(c.cover_id), values=(
                c.cover_id, c.date, c.period,
                c.year_group or "-", c.form_group or "-",
                c.subject_code or "-",
                c.absent_teacher,
                c.cover_teacher or "-",
                c.room or "-", c.status,
            ))
        try:
            counts = data.status_counts()
            total = sum(counts.values())
            summary_var.set(
                f"Total: {total}    " +
                "    ".join(f"{s}: {counts[s]}" for s in STATUSES))
        except Exception:
            logger.exception("status_counts failed")
            summary_var.set("(counts unavailable)")
        status_bar = getattr(main_host, "status_var", None)
        if status_bar is not None:
            status_bar.set(f"Cover: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit_selected(host, tree,
                                                       on_done=_refresh))
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Cover", "Select a row first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _form_dialog(host, "New cover arrangement")
    if not fields:
        return
    c = data.create(fields)
    messagebox.showinfo(
        "Cover",
        f"Created cover #{c.cover_id}: {c.date} P{c.period} "
        f"absent={c.absent_teacher} status={c.status}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        return
    initial = {
        "date": existing.date, "period": existing.period,
        "absent_teacher": existing.absent_teacher,
        "cover_teacher": existing.cover_teacher,
        "year_group": existing.year_group,
        "form_group": existing.form_group,
        "subject_id": existing.subject_id, "room": existing.room,
        "status": existing.status, "reason": existing.reason,
        "notes": existing.notes,
    }
    fields = _form_dialog(host, f"Edit cover #{cid}", initial=initial)
    if not fields:
        return
    data.update(cid, fields)
    if on_done:
        on_done()


@_safe_view
def _assign_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        return
    teacher = _pick_cover_teacher(host, existing)
    if teacher is None:
        return
    teacher = teacher.strip()
    if not teacher:
        return
    data.assign(cid, teacher)
    if on_done:
        on_done()


def _pick_cover_teacher(host, existing) -> str | None:
    """Modal: choose the cover teacher from the staff list (was a typed
    name). Returns the full name, or None if cancelled."""
    dlg, frm = kit.dialog(host.root, "Assign cover")
    dlg.transient(host.root)
    ttk.Label(frm, text=f"Cover teacher for {existing.date} P{existing.period} "
                        f"(absent: {existing.absent_teacher}):").pack(anchor="w")
    var = tk.StringVar(value=existing.cover_teacher or "")
    kit.StaffPicker(frm, var, by="name").pack(fill="x", pady=(6, 0))
    result: list[str | None] = [None]

    def _ok() -> None:
        result[0] = var.get()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="OK", command=_ok).pack(side="right")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    dlg.wait_window()
    return result[0]


@_safe_view
def _status_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — cover #{cid}")
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
    ttk.Label(frm,
              text=f"{existing.date} P{existing.period} — "
                   f"{existing.absent_teacher}").pack(anchor="w")
    ttk.Label(frm, text=f"Current status: {existing.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=existing.status)
    kit.ChoiceField(frm, new_var, choices=STATUSES).pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(cid, new_var.get())
        except ValidationError as e:
            messagebox.showerror("Cover", str(e), parent=dlg)
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
def _delete_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete cover",
            f"Delete cover #{cid}: {existing.date} P{existing.period} "
            f"absent={existing.absent_teacher}?",
            parent=host.root):
        return
    data.delete(cid)
    if on_done:
        on_done()


@_safe_view
def _daily_load(host, date_iso: str) -> None:
    try:
        load = data.daily_load(date_iso.strip())
    except ValidationError as e:
        messagebox.showerror("Cover", str(e), parent=host.root)
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Cover load — {load['date']}")
    dlg.transient(host.root)
    dlg.geometry("620x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"Date: {load['date']}",
              font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
    ttk.Label(frm,
              text=(f"Total: {load['total']}    "
                    f"Unassigned: {load['unassigned']}    "
                    + "    ".join(f"{s}: {load['by_status'][s]}"
                                   for s in STATUSES)),
              foreground="#444").pack(anchor="w", pady=(0, 10))

    by_cover = load["by_cover"]
    if by_cover:
        block = ttk.LabelFrame(frm, text="By cover teacher", padding=6)
        block.pack(fill="x", pady=(0, 8))
        t = ttk.Treeview(block, columns=("teacher", "n"),
                         show="headings", height=min(6, len(by_cover)))
        t.heading("teacher", text="Teacher")
        t.heading("n", text="Slots")
        t.column("teacher", width=300)
        t.column("n", width=80, anchor="e")
        t.pack(fill="x")
        for teacher, n in sorted(by_cover.items(), key=lambda kv: -kv[1]):
            t.insert("", "end", values=(teacher, n))

    detail = ttk.LabelFrame(frm, text="Arrangements", padding=6)
    detail.pack(fill="both", expand=True)
    t2 = ttk.Treeview(detail, columns=("p", "absent", "cover", "yr",
                                         "status"),
                      show="headings", height=12)
    for c, label, w in [
        ("p", "P", 40), ("absent", "Absent", 160), ("cover", "Cover", 160),
        ("yr", "Yr/Form", 80), ("status", "Status", 90),
    ]:
        t2.heading(c, text=label)
        t2.column(c, width=w, anchor="w")
    t2.pack(fill="both", expand=True)
    for r in load["records"]:
        yrform = (r.year_group or "-") + (("/" + r.form_group)
                                            if r.form_group else "")
        t2.insert("", "end", values=(
            r.period, r.absent_teacher, r.cover_teacher or "-",
            yrform, r.status))

    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))
