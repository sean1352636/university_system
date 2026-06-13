"""Tk views for onboarding in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.pupils.onboarding import (
    onboarding as data,
)
from education_system.primarysch_system.modules.domain.pupils.onboarding.onboarding import (
    STEPS, STEP_KEYS,
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
                messagebox.showerror("Onboarding", str(e),
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


def _status_text(record) -> str:
    if record.complete:
        return "complete"
    if record.done_count > 0:
        return "started"
    return "pending"


@_safe_view
def open_onboarding(host) -> None:
    logger.debug("GUI: open_onboarding")

    win = tk.Toplevel(host.root)
    win.title("Onboarding")
    win.transient(host.root)
    win.geometry("820x520")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")

    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filter_frame = ttk.Frame(win, padding=(10, 0, 10, 6))
    filter_frame.pack(fill="x")
    ttk.Label(filter_frame, text="Year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    year_choices = ["All"] + list(YEAR_GROUPS)
    ttk.Combobox(filter_frame, textvariable=year_var, values=year_choices,
                 state="readonly", width=6).pack(side="left", padx=(4, 12))
    pending_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(filter_frame, text="Pending only",
                    variable=pending_var).pack(side="left")

    cols = ("pupil_id", "name", "year", "progress", "status")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
    for col, label, width, anchor in [
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 240, "w"),
        ("year", "Year", 60, "center"),
        ("progress", "Progress", 90, "center"),
        ("status", "Status", 100, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btn_frame = ttk.Frame(win, padding=10)
    btn_frame.pack(fill="x")

    def _refresh() -> None:
        yg_choice = year_var.get()
        yg = None if yg_choice == "All" else yg_choice
        try:
            rows = data.list_records(
                pending_only=pending_var.get(), year_group=yg,
            )
        except Exception:
            logger.exception("onboarding refresh failed")
            messagebox.showerror(
                "Error", "Could not load onboarding records — see logs.",
                parent=win,
            )
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for pupil, rec in rows:
            tree.insert(
                "", "end", iid=pupil.pupil_id,
                values=(
                    pupil.pupil_id, pupil.full_name, pupil.year_group,
                    f"{rec.done_count}/{rec.total}", _status_text(rec),
                ),
            )
        summary = data.progress_summary()
        summary_var.set(
            f"Total: {summary['total']}   "
            f"Complete: {summary['complete']}   "
            f"Started: {summary['started']}   "
            f"Pending: {summary['pending']}"
        )

    def _selected_pupil_id() -> str | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Onboarding", "Select a pupil first.",
                                parent=win)
            return None
        return sel[0]

    def _edit() -> None:
        pid = _selected_pupil_id()
        if pid is None:
            return
        _open_checklist_dialog(win, pid, _refresh)

    def _mark_done() -> None:
        pid = _selected_pupil_id()
        if pid is None:
            return
        try:
            data.mark_all(pid, True)
        except ValidationError as e:
            messagebox.showerror("Onboarding", str(e), parent=win)
            return
        except Exception:
            logger.exception("mark_all failed for %s", pid)
            messagebox.showerror("Error",
                                 "Could not update onboarding — see logs.",
                                 parent=win)
            return
        _refresh()

    def _reset() -> None:
        pid = _selected_pupil_id()
        if pid is None:
            return
        if not messagebox.askyesno(
                "Reset onboarding",
                f"Reset every onboarding step for pupil {pid}?",
                parent=win):
            return
        try:
            data.mark_all(pid, False)
        except ValidationError as e:
            messagebox.showerror("Onboarding", str(e), parent=win)
            return
        except Exception:
            logger.exception("reset failed for %s", pid)
            messagebox.showerror("Error",
                                 "Could not reset onboarding — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btn_frame, text="Edit checklist", command=_edit).pack(
        side="left")
    ttk.Button(btn_frame, text="Mark all done",
               command=_mark_done).pack(side="left", padx=(8, 0))
    ttk.Button(btn_frame, text="Reset",
               command=_reset).pack(side="left", padx=(8, 0))
    ttk.Button(btn_frame, text="Refresh",
               command=_refresh).pack(side="left", padx=(8, 0))
    ttk.Button(btn_frame, text="Close",
               command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _edit())
    year_var.trace_add("write", lambda *_: _refresh())
    pending_var.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_checklist_dialog(parent, pupil_id: str, on_changed: Callable[[], None]) -> None:
    try:
        record = data.get_record(pupil_id)
    except ValidationError as e:
        messagebox.showerror("Onboarding", str(e), parent=parent)
        return
    except Exception:
        logger.exception("get_record(%s) failed", pupil_id)
        messagebox.showerror("Error",
                             "Could not load record — see logs.",
                             parent=parent)
        return
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        messagebox.showerror("Onboarding",
                             f"No pupil with id {pupil_id}",
                             parent=parent)
        return

    dlg = tk.Toplevel(parent)
    dlg.title(f"Onboarding — {pupil.full_name}")
    dlg.transient(parent)
    dlg.geometry("460x380")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text=f"{pupil.full_name}  ({pupil.pupil_id}, year {pupil.year_group})",
              font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))

    updated_var = tk.StringVar(value=f"Updated: {record.updated_at or '-'}")
    ttk.Label(frm, textvariable=updated_var,
              foreground="#666").pack(anchor="w")

    progress_var = tk.StringVar()

    def _format_progress(r) -> str:
        return f"Progress: {r.done_count}/{r.total} ({_status_text(r)})"

    progress_var.set(_format_progress(record))
    ttk.Label(frm, textvariable=progress_var).pack(anchor="w", pady=(0, 10))

    vars_: dict[str, tk.BooleanVar] = {}
    for key, label in STEPS:
        v = tk.BooleanVar(value=record.steps[key])
        vars_[key] = v
        cb = ttk.Checkbutton(frm, text=label, variable=v)
        cb.pack(anchor="w", pady=2)

    def _apply() -> None:
        try:
            current = data.get_record(pupil_id)
        except ValidationError as e:
            messagebox.showerror("Onboarding", str(e), parent=dlg)
            return
        for key in STEP_KEYS:
            desired = vars_[key].get()
            if desired != current.steps[key]:
                try:
                    data.set_step(pupil_id, key, desired)
                except ValidationError as e:
                    messagebox.showerror("Onboarding", str(e), parent=dlg)
                    return
                except Exception:
                    logger.exception("set_step(%s, %s) failed", pupil_id, key)
                    messagebox.showerror(
                        "Error",
                        "Could not update step — see logs.",
                        parent=dlg,
                    )
                    return
        on_changed()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(14, 0))
    ttk.Button(btns, text="Save", command=_apply).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
