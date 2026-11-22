"""Tk views for year-group enrolment in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.admissions.enrolment import (
    enrolment as data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
    kit.show_page(host, "Year Group Enrolment", lambda parent: _draw_enrolment(parent, host))


def _owner(host, widget: tk.Misc | None = None) -> tk.Misc:
    """The page's own window (main window or pop-out), else the main window."""
    if widget is not None:
        try:
            return widget.winfo_toplevel()
        except tk.TclError:
            pass
    return getattr(host, "root", host)


def _draw_enrolment(root: ttk.Frame, host) -> None:
    kit.page_heading(root, "Year Group Enrolment",
                     "Who is on roll in each year group; move or promote pupils.")

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
                                                     on_done=_refresh,
                                                     owner=root)).pack(
        fill="x", pady=2)
    ttk.Button(left, text="View leavers",
               command=lambda: _show_leavers(host, owner=root)).pack(fill="x", pady=2)
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
                                 parent=_owner(host, root))
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
        if getattr(host, "status_var", None) is not None:
            host.status_var.set(f"Year-group enrolment: {total} on roll")

    selected_year.trace_add("write", lambda *_: _refresh())
    _refresh()


def _move_selected_dialog(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Move pupil",
                            "Select a pupil first.", parent=_owner(host, tree))
        return

    owner = _owner(host, tree)
    dlg = tk.Toplevel(owner)
    dlg.title(f"Move pupil {sel}")
    dlg.transient(owner)
    dlg.geometry("460x200")
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
    kit.YearGroupPicker(row1, yvar).pack(side="left")
    row2 = ttk.Frame(frm)
    row2.pack(fill="x", pady=2)
    ttk.Label(row2, text="New class (blank = auto, e.g. 3A → 4A):").pack(
        side="left", padx=(0, 6))
    class_picker = kit.ClassPicker(row2, cvar, year_group=yvar.get())
    class_picker.pack(side="left")
    # Offer the classes of the year being moved to; blank still means auto.
    yvar.trace_add("write", lambda *_a: (cvar.set(""),
                                         class_picker.for_year(yvar.get() or None)))

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


def _promote_year_dialog(host, year: str, *, on_done=None,
                         owner: tk.Misc | None = None) -> None:
    win = _owner(host, owner)
    try:
        preview = data.promote_year(year, dry_run=True)
    except ValidationError as e:
        messagebox.showerror("Promote year", str(e), parent=win)
        return
    to_y = preview["to_year"]
    label = "Reception" if year == "R" else f"Year {year}"
    if to_y is None:
        leavers = preview["leavers"]
        if not leavers:
            messagebox.showinfo("Promote year",
                                f"{label} is empty — nothing to do.",
                                parent=win)
            return
        messagebox.showinfo(
            "Promote year",
            f"{label} is the final year. "
            f"{len(leavers)} pupil(s) would become leavers.\n\n"
            "Leavers must be removed manually from the pupil directory.",
            parent=win,
        )
        return
    count = preview["count"]
    if count == 0:
        messagebox.showinfo("Promote year",
                            f"No pupils in {label} — nothing to do.",
                            parent=win)
        return
    to_label = "Reception" if to_y == "R" else f"Year {to_y}"
    if not messagebox.askyesno(
            "Promote year",
            f"Move all {count} pupil(s) from {label} to {to_label}?\n"
            f"Classes will be bumped accordingly (e.g. {year}A → {to_y}A).",
            parent=win):
        return
    result = data.promote_year(year)
    messagebox.showinfo(
        "Promote year",
        f"Promoted {result['count']} pupil(s) from {label} to {to_label}.",
        parent=win,
    )
    if on_done:
        on_done()


def _show_leavers(host, *, owner: tk.Misc | None = None) -> None:
    win = _owner(host, owner)
    try:
        rows = data.leavers()
    except Exception as e:
        logger.exception("leavers lookup failed")
        messagebox.showerror("Leavers", f"Could not load leavers:\n\n{e}",
                             parent=win)
        return
    dlg = tk.Toplevel(win)
    dlg.title(f"Leavers (Year {data.FINAL_YEAR})")
    dlg.transient(win)
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
