"""Tkinter views for Registration & Enrolment (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Provides an enrolment manager with a tree + toolbar, a "register
new child" dialog (child details + registration/consents), an edit dialog and
a hand-off used by the Admissions screen to convert an accepted application —
the GUI counterpart of the flow in ``enrolment_cli.py``.

Every entry point is wrapped by :func:`_safe_view`. A legacy :func:`build` is
kept so the old placeholder call site still works.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
from education_system.systems.nursery.domain.admissions.enrolment.enrolment import (
    CONSENT_FIELDS,
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
        logger.exception("Could not load room choices for enrolment")
        return []


def _funded_options() -> list[str]:
    from education_system.systems.nursery.domain.learners.children.children import (
        FUNDED_HOURS_OPTIONS,
    )
    return list(FUNDED_HOURS_OPTIONS)


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: enrolment open_manager")
    root = _clear(host)
    _header(root, "Registration & Enrolment")

    show_withdrawn = tk.BooleanVar(value=True)

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Register New Child",
               command=lambda: open_register_new(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Withdraw",
               command=lambda: _withdraw_selected(tree, host)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, show_withdrawn.get())).pack(
        side="left", padx=2)
    ttk.Checkbutton(
        bar, text="Show withdrawn", variable=show_withdrawn,
        command=lambda: _refresh(tree, show_withdrawn.get()),
    ).pack(side="left", padx=(12, 2))

    cols = ("id", "child", "pupil", "room", "start", "consents", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 180), ("pupil", "Pupil", 70),
        ("room", "Room", 140), ("start", "Start", 100),
        ("consents", "Consents", 110), ("status", "Status", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, show_withdrawn.get())
    host.status_var.set("Enrolments loaded")


def _consent_summary(e: data.Enrolment) -> str:
    given = sum(1 for key, _ in CONSENT_FIELDS if getattr(e, key))
    return f"{given}/{len(CONSENT_FIELDS)}"


def _refresh(tree: ttk.Treeview, include_withdrawn: bool = True) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_enrolments(include_withdrawn=include_withdrawn)
    except Exception:
        logger.exception("Could not refresh enrolments")
        try:
            messagebox.showerror(
                "Enrolment", "Could not load enrolments — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for e in rows:
        tree.insert("", "end", iid=e.enrolment_id, values=(
            e.enrolment_id, e.child_name or "-", e.pupil_id, e.room or "-",
            e.start_date or "-", _consent_summary(e), e.status,
        ))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Enrolment", f"Select an enrolment to {verb}.",
                            parent=host.root)
        return None
    return sel


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "edit")
    if sel:
        open_edit(host, sel, on_done=lambda: _refresh(tree))


def _withdraw_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "withdraw")
    if not sel:
        return
    e = data.get_enrolment(sel)
    if e is None:
        return
    off = messagebox.askyesnocancel(
        "Withdraw enrolment",
        f"Withdraw the enrolment for {e.child_name or e.pupil_id}?\n\n"
        "Yes = also take the child off roll (status 'left')\n"
        "No  = withdraw the enrolment only\n"
        "Cancel = do nothing",
        parent=host.root)
    if off is None:
        return
    try:
        data.withdraw(sel, take_off_roll=bool(off))
    except Exception as e2:  # noqa: BLE001
        logger.exception("Failed to withdraw enrolment id=%s", sel)
        messagebox.showerror("Withdraw enrolment", f"Could not withdraw:\n\n{e2}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Withdrew enrolment {sel}")


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    if not messagebox.askyesno(
            "Delete enrolment",
            f"Permanently delete enrolment {sel}?\n\n"
            "This removes the registration record only, not the child.",
            parent=host.root):
        return
    try:
        data.delete_enrolment(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete enrolment id=%s", sel)
        messagebox.showerror("Delete enrolment", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Deleted enrolment {sel}")


# ── Generic form dialog ──────────────────────────────────────────────────────
# Field spec entries are (key, label, kind). Kinds: entry, room, funded, status,
# check (boolean), section (a non-input heading row).

def _build_form(host, title: str, spec: list[tuple[str, str, str]],
                initial: dict[str, Any] | None = None, *,
                height: int = 640) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry(f"480x{height}")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    outer = ttk.Frame(dlg, padding=12)
    outer.pack(fill="both", expand=True)
    frm = ttk.Frame(outer)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    rooms = _room_choices()
    vars_: dict[str, tk.Variable] = {}

    row = 0
    for key, label, kind in spec:
        if kind == "section":
            ttk.Label(frm, text=label, font=("", 10, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(8, 2))
            row += 1
            continue
        cur = initial.get(key)
        if kind == "check":
            v = tk.BooleanVar(value=bool(cur))
            ttk.Checkbutton(frm, text=label, variable=v).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=1)
            vars_[key] = v
            row += 1
            continue
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                              pady=2)
        if kind == "room":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + rooms,
                         width=30).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "funded":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=_funded_options(),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "enrolled"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if isinstance(v, tk.BooleanVar):
                out[k] = 1 if v.get() else 0
            else:
                out[k] = (v.get() or "").strip()
        result = out
        dlg.destroy()

    btns = ttk.Frame(outer)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


def _registration_spec(*, with_room: bool = True) -> list[tuple[str, str, str]]:
    spec: list[tuple[str, str, str]] = [("", "Registration", "section")]
    if with_room:
        spec += [
            ("room", "Room", "room"),
            ("funded_hours", "Funded hours", "funded"),
            ("start_date", "Start date (YYYY-MM-DD)", "entry"),
        ]
    spec += [
        ("weekly_sessions", "Weekly sessions (e.g. Mon,Tue,Wed)", "entry"),
        ("registration_date", "Registration date (YYYY-MM-DD)", "entry"),
        ("contract_signed", "Contract signed", "check"),
        ("", "Consents", "section"),
    ]
    spec += [(key, label, "check") for key, label in CONSENT_FIELDS]
    spec += [
        ("", "Emergency contact", "section"),
        ("emergency_contact_name", "Contact name", "entry"),
        ("emergency_contact_phone", "Contact phone", "entry"),
        ("notes", "Notes", "entry"),
    ]
    return spec


# ── Register new child ───────────────────────────────────────────────────────

@_safe_view
def open_register_new(host) -> None:
    logger.debug("GUI: enrolment open_register_new")
    spec: list[tuple[str, str, str]] = [
        ("", "Child details", "section"),
        ("first_name", "First name", "entry"),
        ("last_name", "Last name", "entry"),
        ("date_of_birth", "Date of birth (YYYY-MM-DD)", "entry"),
        ("parent_name", "Parent / carer name", "entry"),
        ("parent_phone", "Parent phone", "entry"),
        ("parent_email", "Parent email", "entry"),
    ] + _registration_spec(with_room=True)

    fields = _build_form(host, "Register New Child", spec, height=720)
    if not fields:
        host.status_var.set("Registration cancelled")
        open_manager(host)
        return

    child = {k: fields.get(k, "") for k in (
        "first_name", "last_name", "date_of_birth",
        "parent_name", "parent_phone", "parent_email")}
    child["room"] = fields.get("room", "")
    child["funded_hours"] = fields.get("funded_hours", "")
    child["start_date"] = fields.get("start_date", "")
    reg = {k: v for k, v in fields.items() if k not in (
        "first_name", "last_name", "parent_name", "parent_phone",
        "parent_email")}

    try:
        enr = data.enrol_child(child, reg)
    except ValidationError as e:
        messagebox.showerror("Register child", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Child registered",
        f"Registered {enr.child_name}\nChild ID: {enr.pupil_id}\n"
        f"Enrolment: {enr.enrolment_id}",
        parent=host.root,
    )
    host.status_var.set(f"Registered child {enr.pupil_id}")
    open_manager(host)


@_safe_view
def open_enrol_from_application(host, application_id: str) -> None:
    """Convert an accepted admission — invoked from the Admissions screen."""
    logger.debug("GUI: enrolment open_enrol_from_application(%s)", application_id)
    from education_system.systems.nursery.domain.admissions import admissions
    app = admissions.get_application(application_id)
    if app is None:
        messagebox.showerror("Enrol", f"No application with id {application_id}",
                             parent=host.root)
        return
    initial = {
        "room": app.requested_room or "",
        "funded_hours": app.funded_hours or "",
        "start_date": app.requested_start or "",
        "weekly_sessions": app.days_required or "",
    }
    fields = _build_form(
        host, f"Enrol {app.child_name}", _registration_spec(with_room=True),
        initial=initial, height=640)
    if not fields:
        host.status_var.set("Enrolment cancelled")
        return
    overrides = {k: v for k, v in fields.items() if v not in ("", 0)}
    try:
        enr = data.enrol_from_application(application_id, overrides)
    except ValidationError as e:
        messagebox.showerror("Enrol", str(e), parent=host.root)
        return
    messagebox.showinfo(
        "Child enrolled",
        f"Enrolled {enr.child_name}\nChild ID: {enr.pupil_id}\n"
        f"Enrolment: {enr.enrolment_id}\nApplication marked enrolled.",
        parent=host.root,
    )
    host.status_var.set(f"Enrolled application {application_id}")
    open_manager(host)


@_safe_view
def open_edit(host, enrolment_id: str, *, on_done=None) -> None:
    logger.debug("GUI: enrolment open_edit(%s)", enrolment_id)
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Edit enrolment",
                             f"No enrolment with id {enrolment_id}",
                             parent=host.root)
        return
    spec = _registration_spec(with_room=True) + [
        ("", "Record", "section"),
        ("status", "Status", "status"),
    ]
    initial = {key: getattr(e, key) for key, _label, _kind in spec
               if key and hasattr(e, key)}
    fields = _build_form(host, f"Edit enrolment {enrolment_id}", spec,
                         initial=initial, height=700)
    if not fields:
        return
    try:
        data.update_enrolment(enrolment_id, fields)
    except ValidationError as e2:
        messagebox.showerror("Edit enrolment", str(e2), parent=host.root)
        return
    host.status_var.set(f"Updated enrolment {enrolment_id}")
    if on_done:
        try:
            on_done()
        except Exception:
            logger.exception("on_done callback failed after edit")


# ── Legacy placeholder entry point ───────────────────────────────────────────

def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    """Standalone frame fallback (kept for the old placeholder call site)."""
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Registration & Enrolment",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(
        frame,
        text="Open Registration & Enrolment from the navigation menu.",
    ).pack(anchor="w")
    return frame
