"""Tkinter views for Admissions & Waiting List (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Provides a waiting-list manager with a priority-ordered tree +
toolbar, an application form dialog, and the offer/accept/decline/withdraw
transitions plus an "Enrol" hand-off to Registration & Enrolment — the GUI
counterpart of the flow in ``admissions_cli.py``.

Every entry point is wrapped by :func:`_safe_view`. A legacy :func:`build` is
kept so the old placeholder call site still works.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.admissions import admissions as data
from education_system.systems.nursery.domain.admissions.admissions import (
    FUNDED_HOURS_OPTIONS,
    PRIORITIES,
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
    ("child_first_name", "Child first name",            "entry"),
    ("child_last_name",  "Child last name",             "entry"),
    ("date_of_birth",    "Date of birth (YYYY-MM-DD)",  "entry"),
    ("parent_name",      "Parent / carer name",         "entry"),
    ("parent_phone",     "Parent phone",                "entry"),
    ("parent_email",     "Parent email",                "entry"),
    ("requested_room",   "Requested room",              "room"),
    ("requested_start",  "Requested start (YYYY-MM-DD)", "entry"),
    ("funded_hours",     "Funded hours",                "funded"),
    ("days_required",    "Days required",               "entry"),
    ("date_applied",     "Application date (YYYY-MM-DD)", "entry"),
    ("priority",         "Priority",                    "priority"),
    ("notes",            "Notes",                       "entry"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _room_choices() -> list[str]:
    try:
        from education_system.systems.nursery.domain.operations.rooms import rooms
        return rooms.list_room_choices()
    except Exception:
        logger.exception("Could not load room choices for admissions")
        return []


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: admissions open_manager")
    root = _clear(host)
    _header(root, "Admissions & Waiting List")

    show_all = tk.BooleanVar(value=False)

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Button(bar, text="New Application",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, show_all.get())).pack(
        side="left", padx=2)
    ttk.Checkbutton(
        bar, text="Show all (incl. closed)", variable=show_all,
        command=lambda: _refresh(tree, show_all.get()),
    ).pack(side="left", padx=(12, 2))

    bar2 = ttk.Frame(root)
    bar2.pack(fill="x", pady=(0, 8))
    ttk.Label(bar2, text="Selected:").pack(side="left", padx=(0, 4))
    ttk.Button(bar2, text="Offer Place",
               command=lambda: _act(tree, host, data.offer_place, "offered")).pack(
        side="left", padx=2)
    ttk.Button(bar2, text="Accept Offer",
               command=lambda: _act(tree, host, data.accept_offer, "accepted")).pack(
        side="left", padx=2)
    ttk.Button(bar2, text="Decline",
               command=lambda: _act(tree, host, data.decline, "declined")).pack(
        side="left", padx=2)
    ttk.Button(bar2, text="Withdraw",
               command=lambda: _act(tree, host, data.withdraw, "withdrawn")).pack(
        side="left", padx=2)
    ttk.Button(bar2, text="Enrol →",
               command=lambda: _enrol_selected(tree, host)).pack(
        side="left", padx=(12, 2))

    cols = ("id", "child", "room", "priority", "applied", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
    for c, label, w in [
        ("id", "ID", 80), ("child", "Child", 200), ("room", "Requested room", 150),
        ("priority", "Priority", 110), ("applied", "Applied", 100),
        ("status", "Status", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    summary = ttk.Label(root, text="", foreground="#666")
    summary.pack(anchor="w", pady=(6, 0))
    tree._summary = summary  # type: ignore[attr-defined]

    _refresh(tree, show_all.get())
    host.status_var.set("Admissions loaded")


def _refresh(tree: ttk.Treeview, show_all: bool = False) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_applications() if show_all else data.list_waiting_list()
        counts = data.counts_by_status()
    except Exception:
        logger.exception("Could not refresh admissions")
        try:
            messagebox.showerror(
                "Admissions", "Could not load applications — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for a in rows:
        tree.insert("", "end", iid=a.application_id, values=(
            a.application_id, a.child_name, a.requested_room or "-",
            a.priority, a.date_applied or "-", a.status,
        ))
    summary = getattr(tree, "_summary", None)
    if summary is not None:
        summary.config(text="Totals: " + "  ".join(
            f"{k}={v}" for k, v in sorted(counts.items())) if counts else "")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Admissions", f"Select an application to {verb}.",
                            parent=host.root)
        return None
    return sel


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "edit")
    if sel:
        open_edit(host, sel, on_done=lambda: _refresh(tree))


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    a = data.get_application(sel)
    if a is None:
        return
    if not messagebox.askyesno(
            "Delete application",
            f"Permanently delete the application for {a.child_name} ({sel})?",
            parent=host.root):
        return
    try:
        data.delete_application(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete application id=%s", sel)
        messagebox.showerror("Delete application", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Deleted application {sel}")


def _act(tree: ttk.Treeview, host, action: Callable[[str], Any], verb: str) -> None:
    sel = _selected(tree, host, verb)
    if not sel:
        return
    try:
        action(sel)
    except ValidationError as e:
        messagebox.showerror("Admissions", str(e), parent=host.root)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("Status action %s failed for id=%s", verb, sel)
        messagebox.showerror("Admissions", f"Could not update:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Application {sel} → {verb}")


def _enrol_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "enrol")
    if not sel:
        return
    a = data.get_application(sel)
    if a is None:
        return
    if a.pupil_id:
        messagebox.showinfo("Enrol", f"Already enrolled as {a.pupil_id}.",
                            parent=host.root)
        return
    if a.status != "accepted" and not messagebox.askyesno(
            "Enrol",
            f"Offer for {a.child_name} is '{a.status}', not accepted.\n"
            "Enrol anyway?",
            parent=host.root):
        return
    from education_system.systems.nursery.domain.admissions.enrolment import (
        enrolment_views,
    )
    enrolment_views.open_enrol_from_application(host, sel)


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, str] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x560")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    rooms = _room_choices()
    vars_: dict[str, tk.Variable] = {}

    row = 0
    for key, label, kind in _FIELDS:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                              pady=2)
        cur = initial.get(key)
        if kind == "room":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + rooms,
                         width=30).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "funded":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=list(FUNDED_HOURS_OPTIONS),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "priority":
            v = tk.StringVar(value=str(cur or "standard"))
            ttk.Combobox(frm, textvariable=v, values=list(PRIORITIES),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        result = {k: (v.get() or "").strip() for k, v in vars_.items()}
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    logger.debug("GUI: admissions open_add")
    fields = _form_dialog(host, "New Application")
    if not fields:
        host.status_var.set("New application cancelled")
        open_manager(host)
        return
    try:
        a = data.create_application(fields)
    except ValidationError as e:
        messagebox.showerror("New application", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Application added",
        f"Created application {a.application_id} for {a.child_name}.",
        parent=host.root,
    )
    host.status_var.set(f"Added application {a.application_id}")
    open_manager(host)


@_safe_view
def open_edit(host, application_id: str, *, on_done=None) -> None:
    logger.debug("GUI: admissions open_edit(%s)", application_id)
    a = data.get_application(application_id)
    if a is None:
        messagebox.showerror("Edit application",
                             f"No application with id {application_id}",
                             parent=host.root)
        return
    initial = {key: getattr(a, key) for key, _label, _kind in _FIELDS}
    fields = _form_dialog(host, f"Edit {a.child_name}", initial=initial)
    if not fields:
        return
    try:
        data.update_application(application_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit application", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated application {application_id}")
    if on_done:
        try:
            on_done()
        except Exception:
            logger.exception("on_done callback failed after edit")


# ── Legacy placeholder entry point ───────────────────────────────────────────

def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    """Standalone frame fallback (kept for the old placeholder call site)."""
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Admissions & Waiting List",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(
        frame,
        text="Open Admissions & Waiting List from the navigation menu.",
    ).pack(anchor="w")
    return frame
