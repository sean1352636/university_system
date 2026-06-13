"""Tk GUI views for pupil CRUD in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.pupils import pupils as data
from education_system.primarysch_system.modules.domain.pupils import secondary_transfer
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)
from education_system.primarysch_system.modules.domain.enrolment.enrolment import (
    _bump_class,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    """Catch unexpected errors in a Tk view; log and show an error dialog."""
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


_FIELDS = [
    ("first_name",    "First name"),
    ("last_name",     "Last name"),
    ("year_group",    "Year group"),
    ("class_name",    "Class"),
    ("date_of_birth", "Date of birth (YYYY-MM-DD)"),
    ("parent_name",   "Parent name"),
    ("parent_phone",  "Parent phone"),
    ("medical_notes", "Medical notes"),
    ("send_status",   "SEND (yes/no)"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


@_safe_view
def open_directory(host) -> None:
    logger.debug("GUI: open_directory")
    root = _clear(host)
    _header(root, "Pupil Directory")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Pupil",
               command=lambda: open_add_pupil(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit Selected",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete Selected",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Move to Secondary",
               command=lambda: _move_selected_to_secondary(tree, host)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree)).pack(side="left", padx=2)

    cols = ("id", "year", "klass", "name", "parent", "send")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=20)
    for c, label, w in [
        ("id", "ID", 90), ("year", "Year", 50), ("klass", "Class", 80),
        ("name", "Name", 220), ("parent", "Parent", 180), ("send", "SEND", 60),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Pupil directory loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_pupils()
    except Exception:
        logger.exception("Could not refresh pupil directory")
        try:
            messagebox.showerror(
                "Pupil directory",
                "Could not load the pupil list — see logs for details.",
            )
        except Exception:
            pass
        return
    for p in rows:
        tree.insert("", "end", iid=p.pupil_id, values=(
            p.pupil_id, p.year_group, p.class_name or "-",
            p.full_name, p.parent_name or "-", p.send_status or "-",
        ))


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Edit pupil", "Select a pupil first.",
                            parent=host.root)
        return
    open_edit_pupil(host, sel, on_done=lambda: _refresh(tree))


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Delete pupil", "Select a pupil first.",
                            parent=host.root)
        return
    try:
        p = data.get_pupil(sel)
    except Exception:
        logger.exception("Lookup failed before delete for id=%s", sel)
        messagebox.showerror("Delete pupil", "Could not look up pupil.",
                             parent=host.root)
        return
    if p is None:
        return
    if not messagebox.askyesno(
            "Delete pupil",
            f"Delete {p.full_name} ({p.pupil_id})? This cannot be undone.",
            parent=host.root):
        return
    try:
        data.delete_pupil(sel)
    except Exception as e:
        logger.exception("Failed to delete pupil id=%s", sel)
        messagebox.showerror("Delete pupil",
                             f"Could not delete pupil:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Deleted pupil {sel}")
    logger.info("GUI deleted pupil %s", sel)


def _move_selected_to_secondary(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Move to secondary", "Select a pupil first.",
                            parent=host.root)
        return
    try:
        p = data.get_pupil(sel)
    except Exception:
        logger.exception("Lookup failed before secondary transfer for id=%s", sel)
        messagebox.showerror("Move to secondary", "Could not look up pupil.",
                             parent=host.root)
        return
    if p is None:
        messagebox.showerror("Move to secondary", f"No pupil with id {sel}",
                             parent=host.root)
        return

    dlg = tk.Toplevel(host.root)
    dlg.title("Move to Secondary School")
    dlg.transient(host.root)
    dlg.geometry("440x260")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(
        frm,
        text=f"Move {p.full_name} ({p.pupil_id}) into the secondary system?",
        wraplength=400,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))
    if p.year_group != "6":
        ttk.Label(
            frm,
            text=f"Current primary year group is {p.year_group}.",
            foreground="#a45",
        ).pack(anchor="w", pady=(0, 10))

    form_group = tk.StringVar()
    destination = tk.StringVar(value=secondary_transfer.DEFAULT_DESTINATION)
    notes = tk.StringVar()

    grid = ttk.Frame(frm)
    grid.pack(fill="x", expand=True)
    for row, (label, var) in enumerate((
        ("Form group", form_group),
        ("Destination", destination),
        ("Notes", notes),
    )):
        ttk.Label(grid, text=f"{label}:").grid(row=row, column=0, sticky="w",
                                                pady=3)
        ttk.Entry(grid, textvariable=var, width=32).grid(
            row=row, column=1, sticky="ew", pady=3)
    grid.columnconfigure(1, weight=1)

    def _go() -> None:
        if not messagebox.askyesno(
                "Move to secondary",
                "This will create a secondary pupil record, create a login, "
                "record a leaver, and remove the primary pupil. Continue?",
                parent=dlg):
            return
        try:
            result = secondary_transfer.move_to_secondary_school(
                p.pupil_id,
                form_group=form_group.get().strip() or None,
                destination_school=destination.get().strip() or None,
                notes=notes.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Move to secondary", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("Secondary transfer failed for %s", p.pupil_id)
            messagebox.showerror(
                "Move to secondary",
                f"Could not move pupil:\n\n{e}\n\nSee logs for details.",
                parent=dlg,
            )
            return

        _refresh(tree)
        host.status_var.set(
            f"Moved {p.pupil_id} to secondary as {result.secondary_pupil_id}")
        messagebox.showinfo(
            "Moved to secondary",
            "Secondary pupil created.\n\n"
            f"Secondary ID: {result.secondary_pupil_id}\n"
            f"Login email: {result.secondary_email}\n"
            f"Password: {result.password}\n"
            f"Leaver record: {result.leaver_id}",
            parent=dlg,
        )
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Move", command=_go).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, str] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("440x440")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}

    for i, (key, label) in enumerate(_FIELDS):
        ttk.Label(frm, text=f"{label}:").grid(row=i, column=0, sticky="nw",
                                               pady=2)
        if key == "year_group":
            v = tk.StringVar(value=str(initial.get(key, YEAR_GROUPS[0])))
            ttk.Combobox(frm, textvariable=v, values=list(YEAR_GROUPS),
                         state="readonly", width=10).grid(
                row=i, column=1, sticky="w", pady=2)
        elif key == "send_status":
            v = tk.StringVar(value=str(initial.get(key) or ""))
            ttk.Combobox(frm, textvariable=v, values=["", "yes", "no"],
                         width=10).grid(row=i, column=1, sticky="w", pady=2)
        elif key == "medical_notes":
            v = tk.StringVar(value=str(initial.get(key) or ""))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=i, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value=str(initial.get(key) or ""))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=i, column=1, sticky="ew", pady=2)
        vars_[key] = v
    frm.columnconfigure(1, weight=1)

    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        result = {k: (v.get() or "").strip() for k, v in vars_.items()}
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(_FIELDS), column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_add_pupil(host) -> None:
    logger.debug("GUI: open_add_pupil")
    root = _clear(host)
    _header(root, "Add Pupil")
    ttk.Label(root, text="Opening add-pupil form…", foreground="#666").pack(
        anchor="w")
    fields = _form_dialog(host, "Add Pupil")
    if not fields:
        host.status_var.set("Add pupil cancelled")
        return
    try:
        p = data.create_pupil(fields)
    except ValidationError as e:
        messagebox.showerror("Add pupil", str(e), parent=host.root)
        return
    messagebox.showinfo(
        "Pupil added",
        f"Created {p.full_name}\nID: {p.pupil_id}\nEmail: {p.email}",
        parent=host.root,
    )
    open_directory(host)


@_safe_view
def open_edit_pupil(host, pupil_id: str, *, on_done=None) -> None:
    logger.debug("GUI: open_edit_pupil(%s)", pupil_id)
    p = data.get_pupil(pupil_id)
    if p is None:
        messagebox.showerror("Edit pupil", f"No pupil with id {pupil_id}",
                             parent=host.root)
        return
    initial = {key: getattr(p, key) for key, _ in _FIELDS}
    fields = _form_dialog(host, f"Edit {p.full_name}", initial=initial)
    if not fields:
        return
    # If the year changed but the class field wasn't touched, bump the
    # class prefix (e.g. 3A -> 4A) so it follows the pupil up.
    if (fields.get("year_group") != p.year_group
            and fields.get("class_name") == (p.class_name or "")):
        bumped = _bump_class(
            p.year_group, fields["year_group"], p.class_name)
        if bumped is not None:
            fields["class_name"] = bumped
    try:
        data.update_pupil(pupil_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit pupil", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated pupil {pupil_id}")
    if on_done:
        try:
            on_done()
        except Exception:
            logger.exception("on_done callback failed after edit")


@_safe_view
def open_search(host) -> None:
    logger.debug("GUI: open_search")
    root = _clear(host)
    _header(root, "Search Pupils")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Query:").pack(side="left", padx=(0, 6))
    qvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=qvar, width=40)
    entry.pack(side="left")
    entry.focus_set()

    cols = ("id", "year", "klass", "name", "parent")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=20)
    for c, label, w in [
        ("id", "ID", 90), ("year", "Year", 50), ("klass", "Class", 80),
        ("name", "Name", 220), ("parent", "Parent", 200),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(8, 0))

    status = ttk.Label(root, text="", foreground="#666")
    status.pack(anchor="w", pady=(6, 0))

    def _do_search(*_a) -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.search_pupils(qvar.get())
        except Exception:
            logger.exception("Search failed")
            status.config(text="Search failed — see logs", foreground="#a00")
            return
        for p in rows:
            tree.insert("", "end", iid=p.pupil_id, values=(
                p.pupil_id, p.year_group, p.class_name or "-",
                p.full_name, p.parent_name or "-",
            ))
        status.config(text=f"{len(rows)} match(es)", foreground="#666")

    ttk.Button(bar, text="Search", command=_do_search).pack(side="left", padx=4)
    entry.bind("<Return>", _do_search)
    _do_search()


@_safe_view
def open_profile(host) -> None:
    logger.debug("GUI: open_profile")
    root = _clear(host)
    _header(root, "Pupil Profile")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Pupil ID:").pack(side="left", padx=(0, 6))
    pidvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=pidvar, width=20)
    entry.pack(side="left")
    entry.focus_set()

    body = ttk.Frame(root, padding=(0, 8))
    body.pack(fill="both", expand=True)

    def _load() -> None:
        for w in body.winfo_children():
            w.destroy()
        pid = pidvar.get().strip()
        if not pid:
            ttk.Label(body, text="Enter a pupil ID and press Load.",
                      foreground="#666").pack(anchor="w")
            return
        try:
            p = data.get_pupil(pid)
        except Exception:
            logger.exception("Profile lookup failed for id=%s", pid)
            ttk.Label(body, text="Lookup failed — see logs.",
                      foreground="#a00").pack(anchor="w")
            return
        if p is None:
            ttk.Label(body, text="No pupil with that ID.",
                      foreground="#a00").pack(anchor="w")
            return
        rows = [
            ("Name", p.full_name),
            ("Year group", p.year_group),
            ("Class", p.class_name or "-"),
            ("Date of birth", p.date_of_birth or "-"),
            ("Email", p.email),
            ("Parent", p.parent_name or "-"),
            ("Parent phone", p.parent_phone or "-"),
            ("Medical notes", p.medical_notes or "-"),
            ("SEND", p.send_status or "-"),
        ]
        for i, (lbl, val) in enumerate(rows):
            ttk.Label(body, text=f"{lbl}:", foreground="#555").grid(
                row=i, column=0, sticky="w", padx=(0, 12), pady=2)
            ttk.Label(body, text=val).grid(row=i, column=1, sticky="w", pady=2)
        ttk.Button(body, text="Edit",
                   command=lambda: open_edit_pupil(host, p.pupil_id)).grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(10, 0))

    ttk.Button(bar, text="Load", command=_load).pack(side="left", padx=4)
    entry.bind("<Return>", lambda _e: _load())
