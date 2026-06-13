"""Tkinter views for Key Person Assignment (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Shows every active child with their key person, lets you assign /
change / clear it, surfaces unassigned children, and offers a per-practitioner
caseload view — the GUI counterpart of ``key_persons_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.nursery_system.modules.domain.key_persons import (
    key_persons as data,
)
from education_system.nursery_system.modules.domain.key_persons.key_persons import (
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


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: key_persons open_manager")
    root = _clear(host)
    _header(root, "Key Person Assignment")

    unassigned_only = tk.BooleanVar(value=False)
    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Assign / Change",
               command=lambda: _assign_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Clear Key Person",
               command=lambda: _clear_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Caseloads",
               command=lambda: open_caseloads(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary, unassigned_only.get())).pack(
        side="left", padx=2)
    ttk.Checkbutton(bar, text="Unassigned only", variable=unassigned_only,
                    command=lambda: _refresh(tree, summary, unassigned_only.get())
                    ).pack(side="left", padx=(12, 2))

    cols = ("pupil", "name", "room", "key_person")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("pupil", "Pupil", 80), ("name", "Name", 220), ("room", "Room", 150),
        ("key_person", "Key person", 220),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _assign_selected(tree, host))

    _refresh(tree, summary, unassigned_only.get())
    host.status_var.set("Key person assignment loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label, unassigned_only: bool) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_assignments(unassigned_only=unassigned_only)
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh key-person list")
        try:
            messagebox.showerror("Key persons", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for a in rows:
        kp = a.key_person_name or "— UNASSIGNED —"
        tree.insert("", "end", iid=a.pupil_id, values=(
            a.pupil_id, a.child_name, a.room or "-", kp))
    summary.config(
        text=f"Active children: {s['total']}   Assigned: {s['assigned']}   "
             f"Unassigned: {s['unassigned']}",
        foreground="#a00" if s["unassigned"] else "#555")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Key persons", f"Select a child to {verb}.",
                            parent=host.root)
        return None
    return sel


def _assign_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "assign")
    if not sel:
        return
    a = data.get_assignment(sel)
    if a is None:
        return
    choices = _staff_choices()
    label_by_id = {sid: lbl for sid, lbl in choices}
    id_by_label = {lbl: sid for sid, lbl in choices}

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Key person — {a.child_name}")
    dlg.transient(host.root)
    dlg.geometry("420x170")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{a.child_name} — room {a.room or '-'}",
              font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(frm, text="Key person:").pack(anchor="w")
    var = tk.StringVar(value=label_by_id.get(a.key_person or "", ""))
    ttk.Combobox(frm, textvariable=var, values=[""] + [lbl for _i, lbl in choices],
                 state="readonly" if choices else "normal", width=44).pack(
        fill="x", pady=(2, 10))

    def _save() -> None:
        sid = id_by_label.get(var.get().strip(), "")
        try:
            data.assign(sel, sid or None)
        except ValidationError as e:
            messagebox.showerror("Key persons", str(e), parent=dlg)
            return
        dlg.destroy()
        # Rebuild the whole screen so the summary + table refresh.
        open_manager(host)
        host.status_var.set(f"Updated key person for {sel}")

    btns = ttk.Frame(frm)
    btns.pack(fill="x")
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()


def _clear_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "clear")
    if not sel:
        return
    a = data.get_assignment(sel)
    if a is None or not a.key_person:
        return
    if not messagebox.askyesno(
            "Clear key person",
            f"Remove {a.key_person_name or a.key_person} as {a.child_name}'s "
            "key person?", parent=host.root):
        return
    try:
        data.assign(sel, None)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to clear key person for %s", sel)
        messagebox.showerror("Key persons", f"Could not clear:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Cleared key person for {sel}")


@_safe_view
def open_caseloads(host) -> None:
    logger.debug("GUI: key_persons open_caseloads")
    root = _clear(host)
    _header(root, "Key Person Caseloads")
    ttk.Button(root, text="← Back to assignments",
               command=lambda: open_manager(host)).pack(anchor="w", pady=(0, 8))

    tree = ttk.Treeview(root, columns=("info",), show="tree", height=22)
    tree.column("#0", width=320)
    tree.column("info", width=240)
    tree.pack(fill="both", expand=True)
    for cl in data.list_caseloads():
        room = f" ({cl.room})" if cl.room else ""
        parent = tree.insert("", "end",
                             text=f"{cl.staff_name}{room} — {cl.count} child(ren)",
                             open=True)
        for a in cl.children:
            tree.insert(parent, "end", text=f"   {a.child_name}",
                        values=(f"{a.pupil_id} · {a.room or '-'}",))
    host.status_var.set("Caseloads loaded")


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Key Person Assignment",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Key Person Assignment from the navigation menu."
              ).pack(anchor="w")
    return frame
