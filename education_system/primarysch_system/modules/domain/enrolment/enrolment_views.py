"""Tk views for year-group enrolment in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.enrolment import (
    enrolment as data,
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
                messagebox.showerror("Year-group enrolment", str(e),
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
def open_enrolment(host) -> None:
    logger.debug("GUI: open_enrolment")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Year Group Enrolment",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    body = ttk.Frame(root)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=0)
    body.columnconfigure(1, weight=1)
    body.rowconfigure(0, weight=1)

    left = ttk.LabelFrame(body, text="Year groups", padding=8)
    left.grid(row=0, column=0, sticky="ns", padx=(0, 8))
    right = ttk.LabelFrame(body, text="Roll", padding=8)
    right.grid(row=0, column=1, sticky="nsew")

    selected_year = tk.StringVar(value=YEAR_GROUPS[0])
    total_var = tk.StringVar(value="Total: —")
    ttk.Label(left, textvariable=total_var, foreground="#555").pack(
        anchor="w", pady=(0, 6))

    year_count_vars: dict[str, tk.StringVar] = {y: tk.StringVar() for y in YEAR_GROUPS}
    for y in YEAR_GROUPS:
        row = ttk.Frame(left)
        row.pack(fill="x", pady=1)
        label = "Reception" if y == "R" else f"Year {y}"
        ttk.Radiobutton(row, text=label, variable=selected_year,
                        value=y).pack(side="left")
        ttk.Label(row, textvariable=year_count_vars[y],
                  foreground="#666").pack(side="right")

    ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)
    ttk.Button(left, text="Promote this year",
               command=lambda: _promote_year_dialog(host, selected_year.get(),
                                                     on_done=_refresh)).pack(
        fill="x", pady=2)
    ttk.Button(left, text="View leavers",
               command=lambda: _show_leavers(host)).pack(fill="x", pady=2)
    ttk.Button(left, text="Refresh",
               command=lambda: _refresh()).pack(fill="x", pady=(8, 0))

    summary_var = tk.StringVar(value="")
    ttk.Label(right, textvariable=summary_var, foreground="#555").pack(
        anchor="w", pady=(0, 6))
    cols = ("id", "klass", "name", "dob", "send")
    tree = ttk.Treeview(right, columns=cols, show="headings", height=18)
    for c, lbl, w in [
        ("id", "ID", 90), ("klass", "Class", 80),
        ("name", "Name", 220), ("dob", "DOB", 100), ("send", "SEND", 60),
    ]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    act = ttk.Frame(right)
    act.pack(fill="x", pady=(8, 0))
    ttk.Button(act, text="Move selected pupil…",
               command=lambda: _move_selected_dialog(host, tree,
                                                      on_done=_refresh)).pack(
        side="left", padx=2)

    def _refresh() -> None:
        try:
            roll = data.roll_by_year()
        except Exception as e:
            logger.exception("roll_by_year failed")
            messagebox.showerror("Year-group enrolment",
                                 f"Could not load roll:\n\n{e}",
                                 parent=host.root)
            return
        total = sum(len(v) for v in roll.values())
        total_var.set(f"Total on roll: {total}")
        for y in YEAR_GROUPS:
            year_count_vars[y].set(f"{len(roll[y])} pupil(s)")
        y = selected_year.get()
        for i in tree.get_children():
            tree.delete(i)
        for p in roll.get(y, []):
            tree.insert("", "end", iid=p.pupil_id, values=(
                p.pupil_id, p.class_name or "-", p.full_name,
                p.date_of_birth or "-", p.send_status or "-",
            ))
        label = "Reception" if y == "R" else f"Year {y}"
        summary_var.set(f"{label}: {len(roll.get(y, []))} pupil(s)")
        host.status_var.set(f"Year-group enrolment: {total} on roll")

    selected_year.trace_add("write", lambda *_: _refresh())
    _refresh()


def _move_selected_dialog(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Move pupil",
                            "Select a pupil first.", parent=host.root)
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Move pupil {sel}")
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

    ttk.Label(frm, text=f"Pupil ID: {sel}").pack(anchor="w")
    yvar = tk.StringVar(value=YEAR_GROUPS[0])
    cvar = tk.StringVar()
    row1 = ttk.Frame(frm)
    row1.pack(fill="x", pady=(8, 2))
    ttk.Label(row1, text="New year:").pack(side="left", padx=(0, 6))
    ttk.Combobox(row1, textvariable=yvar, values=list(YEAR_GROUPS),
                 state="readonly", width=8).pack(side="left")
    row2 = ttk.Frame(frm)
    row2.pack(fill="x", pady=2)
    ttk.Label(row2, text="New class (blank = keep):").pack(side="left",
                                                            padx=(0, 6))
    ttk.Entry(row2, textvariable=cvar, width=10).pack(side="left")

    def _save() -> None:
        try:
            new_class = cvar.get().strip() or None
            data.move_pupil(sel, yvar.get(), new_class=new_class)
        except ValidationError as e:
            messagebox.showerror("Move pupil", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("move_pupil failed for %s", sel)
            messagebox.showerror("Move pupil",
                                 f"Move failed:\n\n{e}", parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Move", command=_save).pack(side="right")


def _promote_year_dialog(host, year: str, *, on_done=None) -> None:
    try:
        preview = data.promote_year(year, dry_run=True)
    except ValidationError as e:
        messagebox.showerror("Promote year", str(e), parent=host.root)
        return
    to_y = preview["to_year"]
    label = "Reception" if year == "R" else f"Year {year}"
    if to_y is None:
        leavers = preview["leavers"]
        if not leavers:
            messagebox.showinfo("Promote year",
                                f"{label} is empty — nothing to do.",
                                parent=host.root)
            return
        messagebox.showinfo(
            "Promote year",
            f"{label} is the final year. "
            f"{len(leavers)} pupil(s) would become leavers.\n\n"
            "Leavers must be removed manually from the pupil directory.",
            parent=host.root,
        )
        return
    count = preview["count"]
    if count == 0:
        messagebox.showinfo("Promote year",
                            f"No pupils in {label} — nothing to do.",
                            parent=host.root)
        return
    to_label = "Reception" if to_y == "R" else f"Year {to_y}"
    if not messagebox.askyesno(
            "Promote year",
            f"Move all {count} pupil(s) from {label} to {to_label}?",
            parent=host.root):
        return
    result = data.promote_year(year)
    messagebox.showinfo(
        "Promote year",
        f"Promoted {result['count']} pupil(s) from {label} to {to_label}.",
        parent=host.root,
    )
    if on_done:
        on_done()


def _show_leavers(host) -> None:
    try:
        rows = data.leavers()
    except Exception as e:
        logger.exception("leavers lookup failed")
        messagebox.showerror("Leavers", f"Could not load leavers:\n\n{e}",
                             parent=host.root)
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Leavers (Year {data.FINAL_YEAR})")
    dlg.transient(host.root)
    dlg.geometry("520x360")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{len(rows)} pupil(s) in final year",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    cols = ("id", "klass", "name", "dob")
    tree = ttk.Treeview(frm, columns=cols, show="headings")
    for c, label, w in [("id", "ID", 90), ("klass", "Class", 70),
                        ("name", "Name", 220), ("dob", "DOB", 100)]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    for p in rows:
        tree.insert("", "end", values=(p.pupil_id, p.class_name or "-",
                                        p.full_name, p.date_of_birth or "-"))
    ttk.Button(frm, text="Close", command=dlg.destroy).pack(pady=(8, 0),
                                                              anchor="e")
