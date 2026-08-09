"""Tkinter views for Child Directory (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Provides a directory with a tree + toolbar, an add/edit form
dialog, a search screen and a profile screen — the GUI counterparts of the
flows in ``children_cli.py``.

Every entry point is wrapped by :func:`_safe_view`: domain/DB errors are
logged and surfaced in a dialog rather than crashing the GUI. A legacy
:func:`build` is kept so the old placeholder call site still works.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.learners.children import children as data
from education_system.systems.nursery.domain.learners.children import primary_transfer
from education_system.systems.nursery.domain.learners.children.children import (
    FUNDED_HOURS_OPTIONS,
    ROOMS,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    """Catch unexpected errors in a Tk view; log and show an error dialog."""
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
        except Exception as e:  # noqa: BLE001 - last-resort GUI guard
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent,
                )
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


# (field key, label, widget kind). Widget kind drives the form dialog.
_FIELDS: list[tuple[str, str, str]] = [
    ("first_name",    "First name",                 "entry"),
    ("last_name",     "Last name",                  "entry"),
    ("date_of_birth", "Date of birth (YYYY-MM-DD)", "entry"),
    ("room",          "Room",                       "room"),
    ("key_person",    "Key person",                 "key_person"),
    ("funded_hours",  "Funded hours",               "funded"),
    ("start_date",    "Start date (YYYY-MM-DD)",    "entry"),
    ("parent_name",   "Parent / carer name",        "entry"),
    ("parent_phone",  "Parent phone",               "entry"),
    ("parent_email",  "Parent email",               "entry"),
    ("allergies",     "Allergies",                  "entry"),
    ("medical_notes", "Medical notes",              "entry"),
    ("status",        "Status",                     "status"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _key_person_choices() -> list[tuple[str, str]]:
    try:
        return data.list_key_person_choices()
    except Exception:
        logger.exception("Could not load key-person choices")
        return []


# ── Directory ────────────────────────────────────────────────────────────────

@_safe_view
def open_directory(host) -> None:
    logger.debug("GUI: open_directory")
    root = _clear(host)
    _header(root, "Child Directory")

    show_left = tk.BooleanVar(value=False)

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Child",
               command=lambda: open_add_child(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit Selected",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete Selected",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Move to Primary School",
               command=lambda: _move_selected_to_primary(tree, host)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, show_left.get())).pack(
        side="left", padx=2)
    ttk.Checkbutton(
        bar, text="Show leavers", variable=show_left,
        command=lambda: _refresh(tree, show_left.get()),
    ).pack(side="left", padx=(12, 2))

    cols = ("id", "name", "room", "funded", "key_person", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=20)
    for c, label, w in [
        ("id", "ID", 80), ("name", "Name", 200), ("room", "Room", 130),
        ("funded", "Funded hours", 150), ("key_person", "Key person", 180),
        ("status", "Status", 70),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, show_left.get())
    host.status_var.set("Child directory loaded")


def _refresh(tree: ttk.Treeview, include_left: bool = False) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_children(include_left=include_left)
    except Exception:
        logger.exception("Could not refresh child directory")
        try:
            messagebox.showerror(
                "Child directory",
                "Could not load the child list — see logs for details.",
            )
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for c in rows:
        tree.insert("", "end", iid=c.pupil_id, values=(
            c.pupil_id, c.full_name, c.room or "-",
            c.funded_hours or "-", c.key_person_name or "-", c.status,
        ))


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Edit child", "Select a child first.",
                            parent=host.root)
        return
    open_edit_child(host, sel, on_done=lambda: _refresh(tree))


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Delete child", "Select a child first.",
                            parent=host.root)
        return
    try:
        c = data.get_child(sel)
    except Exception:
        logger.exception("Lookup failed before delete for id=%s", sel)
        messagebox.showerror("Delete child", "Could not look up child.",
                             parent=host.root)
        return
    if c is None:
        return
    if not messagebox.askyesno(
            "Delete child",
            f"Permanently delete {c.full_name} ({c.pupil_id})?\n\n"
            "To keep the record but take the child off roll, edit and set "
            "status to 'left' instead.",
            parent=host.root):
        return
    try:
        data.delete_child(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete child id=%s", sel)
        messagebox.showerror("Delete child",
                             f"Could not delete child:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Deleted child {sel}")
    logger.info("GUI deleted child %s", sel)


# ── Move to Primary School ───────────────────────────────────────────────────

def _open_move_dialog(host, c: data.Child, *, on_success: Callable[[], None]) -> None:
    """Confirm year group / class, run the move, and report the new pupil."""
    dlg = tk.Toplevel(host.root)
    dlg.title("Move to Primary School")
    dlg.transient(host.root)
    dlg.geometry("440x240")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(
        frm,
        text=f"Move {c.full_name} ({c.pupil_id}) into the primary school system?",
        wraplength=400,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))

    year_group = tk.StringVar(value=primary_transfer.DEFAULT_YEAR_GROUP)
    class_name = tk.StringVar()

    grid = ttk.Frame(frm)
    grid.pack(fill="x", expand=True)
    ttk.Label(grid, text="Year group:").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Combobox(grid, textvariable=year_group,
                 values=list(primary_transfer.primary_year_groups()),
                 state="readonly", width=29).grid(row=0, column=1, sticky="ew", pady=3)
    ttk.Label(grid, text="Class (optional):").grid(row=1, column=0, sticky="w",
                                                    pady=3)
    ttk.Entry(grid, textvariable=class_name, width=32).grid(
        row=1, column=1, sticky="ew", pady=3)
    grid.columnconfigure(1, weight=1)

    def _go() -> None:
        if not messagebox.askyesno(
                "Move to Primary School",
                "This will create a primary school pupil record and take the "
                "child off the nursery roll (status set to 'left'). Continue?",
                parent=dlg):
            return
        try:
            result = primary_transfer.move_to_primary_school(
                c.pupil_id,
                year_group=year_group.get().strip() or None,
                class_name=class_name.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Move to Primary School", str(e), parent=dlg)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Primary transfer failed for %s", c.pupil_id)
            messagebox.showerror(
                "Move to Primary School",
                f"Could not move child:\n\n{e}\n\nSee logs for details.",
                parent=dlg,
            )
            return
        host.status_var.set(
            f"Moved {c.pupil_id} to primary as {result.primary_pupil_id}")
        messagebox.showinfo(
            "Moved to Primary School",
            "Primary pupil created.\n\n"
            f"Primary ID: {result.primary_pupil_id}\n"
            f"Year group: {result.year_group}\n"
            f"School email: {result.primary_email}",
            parent=dlg,
        )
        dlg.destroy()
        try:
            on_success()
        except Exception:
            logger.exception("on_success callback failed after primary transfer")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Move", command=_go).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _lookup_movable(host, child_id: str) -> data.Child | None:
    """Fetch a child and verify they can still be moved; else show why."""
    try:
        c = data.get_child(child_id)
    except Exception:
        logger.exception("Lookup failed before primary transfer for id=%s",
                         child_id)
        messagebox.showerror("Move to Primary School", "Could not look up child.",
                             parent=host.root)
        return None
    if c is None:
        messagebox.showerror("Move to Primary School",
                             f"No child with id {child_id}", parent=host.root)
        return None
    if c.status == "left":
        messagebox.showinfo(
            "Move to Primary School",
            f"{c.full_name} ({c.pupil_id}) has already left the nursery.",
            parent=host.root)
        return None
    return c


def _move_selected_to_primary(tree: ttk.Treeview, host) -> None:
    """Directory toolbar flow — move the child selected in the tree."""
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Move to Primary School", "Select a child first.",
                            parent=host.root)
        return
    c = _lookup_movable(host, sel)
    if c is not None:
        _open_move_dialog(host, c, on_success=lambda: _refresh(tree))


@_safe_view
def open_move_to_primary(host) -> None:
    """Menu-driven screen — look up a child by ID and move them to primary."""
    logger.debug("GUI: open_move_to_primary")
    root = _clear(host)
    _header(root, "Move to Primary School")

    ttk.Label(
        root,
        text="Move a child onto the primary school roll (Reception by "
             "default). The nursery record is kept and marked as 'left'.",
        foreground="#555", wraplength=600, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Child ID:").pack(side="left", padx=(0, 6))
    pidvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=pidvar, width=20)
    entry.pack(side="left")
    entry.focus_set()

    def _go() -> None:
        pid = pidvar.get().strip()
        if not pid:
            messagebox.showinfo("Move to Primary School", "Enter a child ID.",
                                parent=host.root)
            return
        c = _lookup_movable(host, pid)
        if c is not None:
            _open_move_dialog(host, c, on_success=lambda: open_move_to_primary(host))

    ttk.Button(bar, text="Move…", command=_go).pack(side="left", padx=4)
    entry.bind("<Return>", lambda _e: _go())


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, initial: dict[str, Any] | None = None,
                 *, is_edit: bool = False) -> dict[str, str] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    kp_choices = _key_person_choices()
    # Map "Name (id)" -> id and id -> label for the key-person combobox.
    kp_label_by_id = {sid: label for sid, label in kp_choices}
    kp_id_by_label = {label: sid for sid, label in kp_choices}

    vars_: dict[str, tk.Variable] = {}

    row = 0
    for key, label, kind in _FIELDS:
        if key == "status" and not is_edit:
            continue  # new children are always 'active'
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                               pady=2)
        cur = initial.get(key)
        if kind == "room":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=list(ROOMS),
                         width=30).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "funded":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=list(FUNDED_HOURS_OPTIONS),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "active"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "key_person":
            display = kp_label_by_id.get(str(cur or ""), "")
            v = tk.StringVar(value=display)
            state = "readonly" if kp_choices else "normal"
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _id, lbl in kp_choices],
                         state=state, width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value=str(cur or ""))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, str] = {}
        for k, v in vars_.items():
            val = (v.get() or "").strip()
            if k == "key_person":
                # Translate the "Name (id)" label back to the staff id.
                val = kp_id_by_label.get(val, val)
            out[k] = val
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_add_child(host) -> None:
    logger.debug("GUI: open_add_child")
    root = _clear(host)
    _header(root, "Add Child")
    ttk.Label(root, text="Opening add-child form…", foreground="#666").pack(
        anchor="w")
    fields = _form_dialog(host, "Add Child")
    if not fields:
        host.status_var.set("Add child cancelled")
        open_directory(host)
        return
    try:
        c = data.create_child(fields)
    except ValidationError as e:
        messagebox.showerror("Add child", str(e), parent=host.root)
        open_directory(host)
        return
    messagebox.showinfo(
        "Child added",
        f"Created {c.full_name}\nID: {c.pupil_id}\nRoom: {c.room or '-'}",
        parent=host.root,
    )
    host.status_var.set(f"Added child {c.pupil_id}")
    open_directory(host)


@_safe_view
def open_edit_child(host, pupil_id: str, *, on_done=None) -> None:
    logger.debug("GUI: open_edit_child(%s)", pupil_id)
    c = data.get_child(pupil_id)
    if c is None:
        messagebox.showerror("Edit child", f"No child with id {pupil_id}",
                             parent=host.root)
        return
    initial = {key: getattr(c, key) for key, _label, _kind in _FIELDS}
    fields = _form_dialog(host, f"Edit {c.full_name}", initial=initial,
                          is_edit=True)
    if not fields:
        return
    try:
        data.update_child(pupil_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit child", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated child {pupil_id}")
    if on_done:
        try:
            on_done()
        except Exception:
            logger.exception("on_done callback failed after edit")


# ── Search ───────────────────────────────────────────────────────────────────

@_safe_view
def open_search(host) -> None:
    logger.debug("GUI: open_search")
    root = _clear(host)
    _header(root, "Search Children")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Query:").pack(side="left", padx=(0, 6))
    qvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=qvar, width=40)
    entry.pack(side="left")
    entry.focus_set()

    cols = ("id", "name", "room", "funded", "parent")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=20)
    for c, label, w in [
        ("id", "ID", 80), ("name", "Name", 200), ("room", "Room", 130),
        ("funded", "Funded hours", 150), ("parent", "Parent", 200),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(8, 0))
    tree.bind("<Double-1>",
              lambda _e: _open_profile_for(host, tree.focus()) if tree.focus()
              else None)

    status = ttk.Label(root, text="", foreground="#666")
    status.pack(anchor="w", pady=(6, 0))

    def _do_search(*_a) -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.search_children(qvar.get())
        except Exception:
            logger.exception("Search failed")
            status.config(text="Search failed — see logs", foreground="#a00")
            return
        for c in rows:
            tree.insert("", "end", iid=c.pupil_id, values=(
                c.pupil_id, c.full_name, c.room or "-",
                c.funded_hours or "-", c.parent_name or "-",
            ))
        status.config(text=f"{len(rows)} match(es)", foreground="#666")

    ttk.Button(bar, text="Search", command=_do_search).pack(side="left", padx=4)
    entry.bind("<Return>", _do_search)
    _do_search()


# ── Profile ──────────────────────────────────────────────────────────────────

def _open_profile_for(host, pupil_id: str) -> None:
    open_profile(host, preset_id=pupil_id)


@_safe_view
def open_profile(host, preset_id: str | None = None) -> None:
    logger.debug("GUI: open_profile")
    root = _clear(host)
    _header(root, "Child Profile")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Child ID:").pack(side="left", padx=(0, 6))
    pidvar = tk.StringVar(value=preset_id or "")
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
            ttk.Label(body, text="Enter a child ID and press Load.",
                      foreground="#666").pack(anchor="w")
            return
        try:
            c = data.get_child(pid)
        except Exception:
            logger.exception("Profile lookup failed for id=%s", pid)
            ttk.Label(body, text="Lookup failed — see logs.",
                      foreground="#a00").pack(anchor="w")
            return
        if c is None:
            ttk.Label(body, text="No child with that ID.",
                      foreground="#a00").pack(anchor="w")
            return
        rows = [
            ("Name", c.full_name),
            ("Date of birth", c.date_of_birth or "-"),
            ("Room", c.room or "-"),
            ("Key person", c.key_person_name or c.key_person or "-"),
            ("Funded hours", c.funded_hours or "-"),
            ("Start date", c.start_date or "-"),
            ("Status", c.status),
            ("Parent / carer", c.parent_name or "-"),
            ("Parent phone", c.parent_phone or "-"),
            ("Parent email", c.parent_email or "-"),
            ("Allergies", c.allergies or "-"),
            ("Medical notes", c.medical_notes or "-"),
        ]
        for i, (lbl, val) in enumerate(rows):
            ttk.Label(body, text=f"{lbl}:", foreground="#555").grid(
                row=i, column=0, sticky="nw", padx=(0, 12), pady=2)
            ttk.Label(body, text=val, wraplength=480, justify="left").grid(
                row=i, column=1, sticky="w", pady=2)
        ttk.Button(body, text="Edit",
                   command=lambda: open_edit_child(host, c.pupil_id)).grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(10, 0))

    ttk.Button(bar, text="Load", command=_load).pack(side="left", padx=4)
    entry.bind("<Return>", lambda _e: _load())
    if preset_id:
        _load()


# ── Legacy placeholder entry point ───────────────────────────────────────────

def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    """Standalone frame fallback (kept for the old placeholder call site)."""
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Child Directory",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(
        frame,
        text="Open the Child Directory from the navigation menu.",
    ).pack(anchor="w")
    return frame
