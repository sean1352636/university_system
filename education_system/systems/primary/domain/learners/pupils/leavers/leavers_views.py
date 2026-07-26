"""Tk views for leavers in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.learners.pupils.leavers import (
    leavers as data,
)
from education_system.systems.primary.domain.learners.pupils.leavers.leavers import (
    Leaver, STATUSES,
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
                messagebox.showerror("Leavers", str(e),
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


FORM_FIELDS: list[tuple[str, str]] = [
    ("first_name", "First name *"),
    ("last_name", "Last name *"),
    ("year_left", "Year left *"),
    ("date_of_birth", "Date of birth (YYYY-MM-DD)"),
    ("leaving_date", "Leaving date (YYYY-MM-DD)"),
    ("destination_school", "Destination school"),
    ("current_email", "Current email"),
    ("parent_phone", "Parent phone"),
    ("reason", "Reason"),
    ("status", "Status"),
    ("notes", "Notes"),
    ("pupil_id", "Source pupil ID (optional)"),
]


@_safe_view
def open_leavers(host) -> None:
    logger.debug("GUI: open_leavers")

    win = tk.Toplevel(host.root)
    win.title("Leavers")
    win.transient(host.root)
    win.geometry("960x560")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")

    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Status:").pack(side="left")
    status_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["All"] + list(STATUSES),
                 state="readonly", width=10).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Year left:").pack(side="left")
    year_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=year_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Search:").pack(side="left")
    search_var = tk.StringVar()
    ttk.Entry(filt, textvariable=search_var, width=22).pack(side="left", padx=(4, 0))

    cols = ("leaver_id", "pupil_id", "name", "year", "leaving_date",
            "destination", "status")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("leaver_id", "Leaver ID", 90, "w"),
        ("pupil_id", "Pupil ID", 80, "w"),
        ("name", "Name", 200, "w"),
        ("year", "Year", 60, "center"),
        ("leaving_date", "Leaving date", 100, "center"),
        ("destination", "Destination", 220, "w"),
        ("status", "Status", 80, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            q = search_var.get().strip()
            if q:
                rows = data.search_leavers(q)
            else:
                s = None if status_var.get() == "All" else status_var.get()
                y = None if year_var.get() == "All" else year_var.get()
                rows = data.list_leavers(status=s, year_left=y)
        except ValidationError as e:
            messagebox.showerror("Leavers", str(e), parent=win)
            return
        except Exception:
            logger.exception("leavers refresh failed")
            messagebox.showerror("Error",
                                 "Could not load leavers — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for r in rows:
            tree.insert("", "end", iid=r.leaver_id, values=(
                r.leaver_id, r.pupil_id or "", r.full_name, r.year_left,
                r.leaving_date or "", r.destination_school or "", r.status,
            ))
        try:
            counts = data.status_counts()
        except Exception:
            counts = {s: 0 for s in STATUSES}
        total = sum(counts.values())
        summary_var.set(
            f"Total: {total}   " + "   ".join(
                f"{s.title()}: {counts[s]}" for s in STATUSES
            )
        )

    def _selected_id() -> str | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Leavers", "Select a leaver first.", parent=win)
            return None
        return sel[0]

    def _add() -> None:
        _open_form_dialog(win, leaver_id=None, on_saved=_refresh)

    def _edit() -> None:
        lid = _selected_id()
        if lid is None:
            return
        _open_form_dialog(win, leaver_id=lid, on_saved=_refresh)

    def _promote() -> None:
        _open_promote_dialog(win, on_saved=_refresh)

    def _toggle_status() -> None:
        lid = _selected_id()
        if lid is None:
            return
        rec = data.get_leaver(lid)
        if rec is None:
            messagebox.showerror("Leavers", f"No leaver with id {lid}", parent=win)
            return
        new_status = "inactive" if rec.status == "active" else "active"
        try:
            data.set_status(lid, new_status)
        except ValidationError as e:
            messagebox.showerror("Leavers", str(e), parent=win)
            return
        except Exception:
            logger.exception("set_status failed for %s", lid)
            messagebox.showerror("Error", "Could not change status — see logs.",
                                 parent=win)
            return
        _refresh()

    def _delete() -> None:
        lid = _selected_id()
        if lid is None:
            return
        if not messagebox.askyesno("Delete leaver",
                                   f"Delete leaver {lid}?",
                                   parent=win):
            return
        try:
            data.delete_leaver(lid)
        except Exception:
            logger.exception("delete_leaver failed for %s", lid)
            messagebox.showerror("Error",
                                 "Could not delete leaver — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btns, text="Add leaver", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Promote pupil...", command=_promote).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Toggle status", command=_toggle_status).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _edit())
    status_var.trace_add("write", lambda *_: _refresh())
    year_var.trace_add("write", lambda *_: _refresh())
    search_var.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_form_dialog(parent, *, leaver_id: str | None,
                      on_saved: Callable[[], None]) -> None:
    existing: Leaver | None = None
    if leaver_id is not None:
        try:
            existing = data.get_leaver(leaver_id)
        except Exception:
            logger.exception("get_leaver(%s) failed", leaver_id)
            messagebox.showerror("Error",
                                 "Could not load leaver — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Leavers",
                                 f"No leaver with id {leaver_id}",
                                 parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Leaver" if existing else "New leaver")
    dlg.transient(parent)
    dlg.geometry("520x560")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    vars_: dict[str, tk.StringVar] = {}
    for i, (key, label) in enumerate(FORM_FIELDS):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
        v = tk.StringVar()
        if existing is not None:
            v.set(getattr(existing, key, "") or "")
        elif key == "status":
            v.set("active")
        vars_[key] = v
        if key == "year_left":
            ttk.Combobox(frm, textvariable=v, values=list(YEAR_GROUPS),
                         state="readonly", width=28).grid(
                row=i, column=1, sticky="ew", pady=2)
        elif key == "status":
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=28).grid(
                row=i, column=1, sticky="ew", pady=2)
        elif key == "notes":
            ttk.Entry(frm, textvariable=v, width=30).grid(
                row=i, column=1, sticky="ew", pady=2)
        else:
            ttk.Entry(frm, textvariable=v, width=30).grid(
                row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    def _save() -> None:
        payload = {k: v.get() for k, v in vars_.items()}
        try:
            if existing is None:
                rec = data.create_leaver(payload)
                logger.info("GUI created leaver %s", rec.leaver_id)
            else:
                data.update_leaver(existing.leaver_id, payload)
        except ValidationError as e:
            messagebox.showerror("Leavers", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save leaver failed")
            messagebox.showerror("Error",
                                 "Could not save leaver — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(FORM_FIELDS), column=0, columnspan=2,
              sticky="ew", pady=(12, 0))
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_promote_dialog(parent, *, on_saved: Callable[[], None]) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("Promote pupil to leaver")
    dlg.transient(parent)
    dlg.geometry("440x340")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text="Create a leaver record from an existing pupil "
                   "and remove the pupil.",
              foreground="#555", wraplength=400, justify="left").pack(
        anchor="w", pady=(0, 10))

    fields = {
        "pupil_id": tk.StringVar(),
        "destination_school": tk.StringVar(),
        "current_email": tk.StringVar(),
        "reason": tk.StringVar(),
        "leaving_date": tk.StringVar(),
        "notes": tk.StringVar(),
    }
    labels = {
        "pupil_id": "Pupil ID *",
        "destination_school": "Destination school",
        "current_email": "Current email",
        "reason": "Reason",
        "leaving_date": "Leaving date (YYYY-MM-DD)",
        "notes": "Notes",
    }
    grid = ttk.Frame(frm)
    grid.pack(fill="both", expand=True)
    for i, key in enumerate(fields):
        ttk.Label(grid, text=labels[key]).grid(row=i, column=0, sticky="w", pady=3)
        ttk.Entry(grid, textvariable=fields[key], width=30).grid(
            row=i, column=1, sticky="ew", pady=3)
    grid.columnconfigure(1, weight=1)

    def _go() -> None:
        pid = fields["pupil_id"].get().strip()
        if not pid:
            messagebox.showerror("Promote", "Pupil ID is required.", parent=dlg)
            return
        if not messagebox.askyesno(
                "Promote pupil",
                f"Create leaver record for pupil {pid} and delete the pupil?",
                parent=dlg):
            return
        extras = {k: v.get() for k, v in fields.items() if k != "pupil_id"}
        try:
            data.promote_from_pupil(pid, extras=extras)
        except ValidationError as e:
            messagebox.showerror("Promote", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("promote_from_pupil failed for %s", pid)
            messagebox.showerror("Error",
                                 "Could not promote pupil — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Promote", command=_go).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
