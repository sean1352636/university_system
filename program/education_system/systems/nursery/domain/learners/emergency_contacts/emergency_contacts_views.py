"""Tkinter views for Emergency Contacts (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Shows the emergency contact list with a tree + toolbar and an
add/edit form dialog — the GUI counterpart of ``emergency_contacts_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.learners.emergency_contacts import (
    emergency_contacts as data,
)
from education_system.systems.nursery.domain.learners.emergency_contacts.emergency_contacts import (
    RELATIONSHIPS,
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


# (key, label, kind) — kind one of entry/rel/bool
_FIELDS: list[tuple[str, str, str]] = [
    ("full_name",    "Contact name",          "entry"),
    ("relationship", "Relationship",          "rel"),
    ("phone_primary", "Phone (primary)",      "entry"),
    ("phone_alt",    "Phone (alt)",           "entry"),
    ("priority",     "Priority",              "entry"),
    ("can_collect",  "Authorised to collect", "bool"),
    ("notes",        "Notes",                 "entry"),
]


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


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: emergency_contacts open_manager")
    root = _clear(host)
    _header(root, "Emergency Contacts")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Contact",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    cols = ("id", "child", "name", "rel", "phone", "priority", "collect")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 170), ("name", "Name", 170),
        ("rel", "Relationship", 110), ("phone", "Phone (primary)", 130),
        ("priority", "Priority", 70), ("collect", "Collect", 70),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Emergency contacts loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_contacts()
    except Exception:
        logger.exception("Could not refresh emergency contacts")
        return
    for c in rows:
        tree.insert("", "end", iid=c.contact_id, values=(
            c.contact_id, c.child_name or "-", c.full_name,
            c.relationship or "-", c.phone_primary or "-",
            c.priority, "Yes" if c.can_collect else ""))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Emergency contacts", f"Select a contact to {verb}.",
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
    if not messagebox.askyesno("Delete contact", f"Delete contact {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_contact(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete emergency contact %s", sel)
        messagebox.showerror("Delete contact", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted contact {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x420")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    pid_id_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar, values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    for key, label, kind in _FIELDS:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "rel":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(RELATIONSHIPS),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "bool":
            v = tk.BooleanVar(value=bool(cur))
            ttk.Checkbutton(frm, variable=v).grid(
                row=row, column=1, sticky="w", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif isinstance(v, tk.BooleanVar):
                out[k] = bool(v.get())
            else:
                out[k] = (v.get() or "").strip()
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
    fields = _form_dialog(host, "Add Emergency Contact",
                          pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add contact cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add contact", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        c = data.create_contact(fields)
    except ValidationError as e:
        messagebox.showerror("Add contact", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added emergency contact {c.contact_id}")
    open_manager(host)


@_safe_view
def open_edit(host, contact_id: str) -> None:
    c = data.get_contact(contact_id)
    if c is None:
        messagebox.showerror("Edit contact", f"No contact with id {contact_id}",
                             parent=host.root)
        return
    initial = {key: getattr(c, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit contact — {c.full_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_contact(contact_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit contact", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated contact {contact_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Emergency Contacts", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Emergency Contacts from the navigation menu.").pack(
        anchor="w")
    return frame
