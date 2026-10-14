"""Tk views for year-group configuration."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.academics.year_groups import (
    year_groups as data,
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
                messagebox.showerror("Year Groups", str(e),
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


def _edit_dialog(host, year_group: str,
                 existing: data.YearGroup | None) -> dict[str, str] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Year {year_group}")
    dlg.transient(host.root)
    dlg.geometry("420x260")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=f"Year group: {year_group}",
              font=("", 11, "bold")).grid(row=0, column=0, columnspan=2,
                                          sticky="w", pady=(0, 8))

    head_var = tk.StringVar(value=(existing.head_of_year if existing else "")
                            or "")
    cap_var = tk.StringVar(value=str(existing.capacity) if (
        existing and existing.capacity is not None) else "")
    notes_var = tk.StringVar(value=(existing.notes if existing else "") or "")

    ttk.Label(frm, text="Head of year:").grid(row=1, column=0, sticky="w",
                                               pady=2)
    ttk.Entry(frm, textvariable=head_var, width=32).grid(
        row=1, column=1, sticky="ew", pady=2)
    ttk.Label(frm, text="Capacity:").grid(row=2, column=0, sticky="w", pady=2)
    ttk.Entry(frm, textvariable=cap_var, width=10).grid(
        row=2, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Notes:").grid(row=3, column=0, sticky="nw", pady=2)
    ttk.Entry(frm, textvariable=notes_var, width=32).grid(
        row=3, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "year_group":   year_group,
            "head_of_year": head_var.get().strip(),
            "capacity":     cap_var.get().strip(),
            "notes":        notes_var.get().strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_year_groups(host) -> None:
    logger.debug("GUI: open_year_groups")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Year Groups", font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Clear",
               command=lambda: _clear_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("year", "head", "capacity", "pupils", "notes")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=10)
    for c, label, w in [
        ("year", "Year", 70), ("head", "Head of Year", 200),
        ("capacity", "Capacity", 90), ("pupils", "Pupils", 90),
        ("notes", "Notes", 320),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_all()
            counts = data.pupil_counts()
        except Exception as e:
            logger.exception("year_groups refresh failed")
            messagebox.showerror("Year Groups",
                                 f"Could not load year groups:\n\n{e}",
                                 parent=host.root)
            return
        for y in rows:
            tree.insert("", "end", iid=y.year_group, values=(
                y.year_group,
                y.head_of_year or "-",
                y.capacity if y.capacity is not None else "-",
                counts.get(y.year_group, 0),
                y.notes or "-",
            ))
        host.status_var.set(f"Year Groups: {len(rows)} year(s)")

    tree.bind("<Double-1>", lambda _e: _edit_selected(host, tree,
                                                       on_done=_refresh))
    _refresh()


@_safe_view
def _edit_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Year Groups", "Select a year first.",
                            parent=host.root)
        return
    existing = data.get(sel)
    fields = _edit_dialog(host, sel, existing)
    if not fields:
        return
    rec = data.upsert(fields)
    messagebox.showinfo("Year Groups",
                        f"Saved Year {rec.year_group}",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _clear_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Year Groups", "Select a year first.",
                            parent=host.root)
        return
    if not messagebox.askyesno(
            "Clear configuration",
            f"Clear stored config for Year {sel}? "
            f"(pupils are not affected)",
            parent=host.root):
        return
    data.delete(sel)
    if on_done:
        on_done()
