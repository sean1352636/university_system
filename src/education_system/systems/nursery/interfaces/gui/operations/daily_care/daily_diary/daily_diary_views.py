"""Tkinter views for Daily Diary (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Lists diary entries with a tree + toolbar and an add/edit form
dialog — the GUI counterpart of ``daily_diary_cli.py``.
"""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.operations.daily_care.daily_diary import (
    daily_diary as data,
)
from education_system.systems.nursery.domain.operations.daily_care.daily_diary.daily_diary import (
    MOODS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent)
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _pupil_choices() -> list[tuple[str, str]]:
    try:
        return data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return []


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: daily_diary open_manager")
    root = _clear(host)
    _header(root, "Daily Diary")

    date_var = tk.StringVar()

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Date (YYYY-MM-DD):").pack(side="left", padx=(0, 4))
    ttk.Entry(bar, textvariable=date_var, width=14).pack(side="left", padx=2)
    ttk.Button(bar, text="Load",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Add",
               command=lambda: open_add(host)).pack(side="left", padx=(12, 2))
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=2)

    cols = ("date", "child", "mood", "highlights")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("date", "Date", 110), ("child", "Child", 200),
        ("mood", "Mood", 110), ("highlights", "Highlights", 320),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, date_var.get())
    host.status_var.set("Daily diary loaded")


def _refresh(tree: ttk.Treeview, date_filter: str) -> None:
    for i in tree.get_children():
        tree.delete(i)
    df = (date_filter or "").strip() or None
    try:
        rows = data.list_records(entry_date=df)
    except Exception:
        logger.exception("Could not refresh daily diary")
        try:
            messagebox.showerror("Daily diary", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        tree.insert("", "end", iid=r.entry_id, values=(
            r.entry_date, r.child_name or "-", r.mood or "-",
            r.highlights or "-"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Daily diary", f"Select an entry to {verb}.",
                            parent=host.root)
        return None
    return sel


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "edit")
    if sel:
        open_edit(host, sel)


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    r = data.get_record(sel)
    if r is None:
        return
    if not messagebox.askyesno(
            "Delete entry",
            f"Delete diary entry {sel} for {r.child_name}?",
            parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete daily-diary %s", sel)
        messagebox.showerror("Delete entry", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted diary entry {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None,
                 staff_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("500x560")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    row = 0

    # Child picker only when adding a new entry.
    pid_id_by_label: dict[str, str] = {}
    pvar: tk.StringVar | None = None
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar,
                     values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=38).grid(
            row=row, column=1, sticky="ew", pady=2)
        row += 1

    # Date.
    ttk.Label(frm, text="Date (YYYY-MM-DD):").grid(
        row=row, column=0, sticky="nw", pady=2)
    date_var = tk.StringVar(
        value=str(initial.get("entry_date") or _dt.date.today().isoformat()))
    ttk.Entry(frm, textvariable=date_var, width=40).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    # Mood (editable combobox).
    ttk.Label(frm, text="Mood:").grid(row=row, column=0, sticky="nw", pady=2)
    mood_var = tk.StringVar(value=str(initial.get("mood") or ""))
    ttk.Combobox(frm, textvariable=mood_var, values=list(MOODS),
                 state="normal", width=38).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    # Multi-line text areas.
    texts: dict[str, tk.Text] = {}
    for key, label in (("activities", "Activities"),
                       ("highlights", "Highlights"),
                       ("notes", "Notes")):
        ttk.Label(frm, text=f"{label}:").grid(
            row=row, column=0, sticky="nw", pady=2)
        txt = tk.Text(frm, width=40, height=3, wrap="word")
        txt.grid(row=row, column=1, sticky="ew", pady=2)
        txt.insert("1.0", str(initial.get(key) or ""))
        texts[key] = txt
        row += 1

    # Staff picker (optional).
    ttk.Label(frm, text="Staff:").grid(row=row, column=0, sticky="nw", pady=2)
    schoices = staff_choices or []
    sid_id_by_label = {lbl: sid for sid, lbl in schoices}
    sid_label_by_id = {sid: lbl for sid, lbl in schoices}
    svar = tk.StringVar(value=sid_label_by_id.get(initial.get("staff_id"), ""))
    ttk.Combobox(frm, textvariable=svar,
                 values=[""] + [lbl for _i, lbl in schoices],
                 state="readonly" if schoices else "normal", width=38).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {
            "entry_date": (date_var.get() or "").strip(),
            "mood": (mood_var.get() or "").strip(),
            "staff_id": sid_id_by_label.get((svar.get() or "").strip(), ""),
        }
        for key, txt in texts.items():
            out[key] = txt.get("1.0", "end").strip()
        if pvar is not None:
            out["pupil_id"] = pid_id_by_label.get((pvar.get() or "").strip(), "")
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    logger.debug("GUI: daily_diary open_add")
    fields = _form_dialog(host, "Add Diary Entry",
                          pupil_choices=_pupil_choices(),
                          staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add diary entry cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add entry", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        r = data.create_record(fields)
    except ValidationError as e:
        messagebox.showerror("Add entry", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Entry added",
        f"{r.child_name} — {r.entry_date}\nMood: {r.mood or '-'}",
        parent=host.root)
    host.status_var.set(f"Added diary entry {r.entry_id}")
    open_manager(host)


@_safe_view
def open_edit(host, entry_id: str) -> None:
    logger.debug("GUI: daily_diary open_edit(%s)", entry_id)
    r = data.get_record(entry_id)
    if r is None:
        messagebox.showerror("Edit entry", f"No entry with id {entry_id}",
                             parent=host.root)
        return
    initial = {
        "entry_date": r.entry_date, "mood": r.mood, "activities": r.activities,
        "highlights": r.highlights, "notes": r.notes, "staff_id": r.staff_id,
    }
    fields = _form_dialog(host, f"Edit {r.child_name} — diary entry",
                          initial=initial, is_edit=True,
                          staff_choices=_staff_choices())
    if not fields:
        return
    try:
        data.update_record(entry_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit entry", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated diary entry {entry_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Daily Diary",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Daily Diary from the navigation menu."
              ).pack(anchor="w")
    return frame
