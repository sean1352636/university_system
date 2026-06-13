"""Tkinter views for Newsletters (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Shows the newsletter list with a tree + toolbar and an add/edit
form dialog — the GUI counterpart of ``newsletters_cli.py``.

Newsletters are setting-wide bulletins and are NOT attached to any child.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.newsletters import (
    newsletters as data,
)
from education_system.nursery_system.modules.domain.newsletters.newsletters import (
    AUDIENCES,
    STATUSES,
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


# (key, label, kind) — kind: entry | audience | status | staff
_FIELDS: list[tuple[str, str, str]] = [
    ("title",          "Title",                        "entry"),
    ("issue_date",     "Issue date (YYYY-MM-DD)",      "entry"),
    ("body",           "Body",                         "entry"),
    ("audience",       "Audience",                     "audience"),
    ("status",         "Status",                       "status"),
    ("author",         "Author (staff)",               "staff"),
    ("published_date", "Published date (YYYY-MM-DD)",  "entry"),
]


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
    logger.debug("GUI: newsletters open_manager")
    root = _clear(host)
    _header(root, "Newsletters")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Newsletter",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Publish",
               command=lambda: _publish_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    cols = ("id", "title", "issue_date", "audience", "status", "author")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id",         "ID",         80),
        ("title",      "Title",      240),
        ("issue_date", "Issue date", 100),
        ("audience",   "Audience",   140),
        ("status",     "Status",     80),
        ("author",     "Author",     160),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Newsletters loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_newsletters()
    except Exception:
        logger.exception("Could not refresh newsletters")
        return
    for n in rows:
        tree.insert("", "end", iid=n.newsletter_id, values=(
            n.newsletter_id,
            n.title,
            n.issue_date or "-",
            n.audience or "-",
            n.status,
            n.author_name or n.author or "-",
        ))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Newsletters", f"Select a newsletter to {verb}.",
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
    if not messagebox.askyesno("Delete newsletter",
                               f"Delete newsletter {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_newsletter(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete newsletter %s", sel)
        messagebox.showerror("Delete newsletter", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted newsletter {sel}")


def _publish_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "publish")
    if not sel:
        return
    try:
        n = data.publish_newsletter(sel)
    except ValidationError as e:
        messagebox.showerror("Publish newsletter", str(e), parent=host.root)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to publish newsletter %s", sel)
        messagebox.showerror("Publish newsletter", f"Could not publish:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Published newsletter {n.newsletter_id}")


def _form_dialog(host, title: str, *,
                 initial: dict[str, Any] | None = None,
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x420")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    staff = _staff_choices()
    staff_label_by_id = {sid: lbl for sid, lbl in staff}
    staff_id_by_label = {lbl: sid for sid, lbl in staff}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    for key, label, kind in _FIELDS:
        ttk.Label(frm, text=f"{label}:").grid(
            row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "audience":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + list(AUDIENCES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "draft"))
            ttk.Combobox(frm, textvariable=v,
                         values=list(STATUSES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "staff":
            v = tk.StringVar(value=staff_label_by_id.get(str(cur or ""), ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _i, lbl in staff],
                         state="readonly" if staff else "normal",
                         width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
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
            val = (v.get() or "").strip()
            if k == "author":
                out[k] = staff_id_by_label.get(val, val)
            else:
                out[k] = val
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(
        side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    fields = _form_dialog(host, "Add Newsletter")
    if not fields:
        host.status_var.set("Add newsletter cancelled")
        open_manager(host)
        return
    try:
        n = data.create_newsletter(fields)
    except ValidationError as e:
        messagebox.showerror("Add newsletter", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added newsletter {n.newsletter_id}")
    open_manager(host)


@_safe_view
def open_edit(host, newsletter_id: str) -> None:
    n = data.get_newsletter(newsletter_id)
    if n is None:
        messagebox.showerror("Edit newsletter",
                             f"No newsletter with id {newsletter_id}",
                             parent=host.root)
        return
    initial = {key: getattr(n, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit newsletter — {n.title}",
                          initial=initial)
    if not fields:
        return
    try:
        data.update_newsletter(newsletter_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit newsletter", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated newsletter {newsletter_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Newsletters", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Newsletters from the navigation menu.").pack(
        anchor="w")
    return frame
