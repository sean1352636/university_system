"""Tkinter views for Collections & Late Pickup (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Two tabs — the authorised-collector list (with a door check that
verifies name and collection password) and the late-collection log with its
fees and escalation trail — the GUI counterpart of ``collections_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.operations.daily_care.collections import (
    collections as data,
)
from education_system.systems.nursery.domain.operations.daily_care.collections.collections import (
    COLLECTOR_STATUSES,
    ESCALATION_STAGES,
    FEE_STATUSES,
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


def _tree(parent: ttk.Frame, spec: list[tuple[str, str, int]],
          height: int = 14) -> ttk.Treeview:
    cols = tuple(c for c, _l, _w in spec)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c, label, w in spec:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("alert", foreground="#c0392b")
    tree.tag_configure("warn", foreground="#b9770e")
    tree.tag_configure("muted", foreground="#7f8c8d")
    tree.pack(fill="both", expand=True)
    return tree


def _selected(tree: ttk.Treeview, host, what: str, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Collections", f"Select {what} to {verb}.",
                            parent=host.root)
        return None
    return sel


# ── Generic form dialog ──────────────────────────────────────────────────────
# Fields are (key, label, kind, choices); ``password`` renders a masked entry
# and ``pupil`` the child picker.

def _form_dialog(host, title: str, fields: list[tuple[str, str, str, Any]], *,
                 initial: dict[str, Any] | None = None,
                 geometry: str = "480x560") -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry(geometry)
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    pupil_by_label: dict[str, str] = {}
    row = 0

    for key, label, kind, choices in fields:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                              pady=2)
        cur = initial.get(key)
        if kind == "pupil":
            pupil_by_label = {lbl: pid for pid, lbl in (choices or [])}
            v = tk.StringVar()
            ttk.Combobox(frm, textvariable=v,
                         values=[lbl for _p, lbl in (choices or [])],
                         state="readonly" if choices else "normal",
                         width=34).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "choice":
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Combobox(frm, textvariable=v, values=list(choices or []),
                         width=32).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "bool":
            v = tk.BooleanVar(value=bool(cur))
            ttk.Checkbutton(frm, variable=v).grid(row=row, column=1, sticky="w",
                                                  pady=2)
        elif kind == "password":
            v = tk.StringVar()
            ttk.Entry(frm, textvariable=v, width=34, show="•").grid(
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
        for (key, _l, kind, _c) in fields:
            v = vars_[key]
            if kind == "pupil":
                out["pupil_id"] = pupil_by_label.get(
                    (str(v.get()) or "").strip(), "")
            elif isinstance(v, tk.BooleanVar):
                out[key] = bool(v.get())
            else:
                out[key] = (str(v.get()) or "").strip()
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: collections open_manager")
    root = _clear(host)
    _header(root, "Collections & Late Pickup")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Button(bar, text="Verify Someone At The Door",
               command=lambda: open_verify(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 2))
    warn = ttk.Label(root, foreground="#a00")
    warn.pack(anchor="w", pady=(0, 6))
    _refresh_summary(summary, warn)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    collector_tab = ttk.Frame(nb, padding=8)
    late_tab = ttk.Frame(nb, padding=8)
    nb.add(collector_tab, text="Authorised Collectors")
    nb.add(late_tab, text="Late Collection Log")

    _build_collector_tab(host, collector_tab)
    _build_late_tab(host, late_tab)

    host.status_var.set("Collections loaded")


def _refresh_summary(summary: ttk.Label, warn: ttk.Label) -> None:
    try:
        s = data.summary()
    except Exception:
        logger.exception("Could not load collections summary")
        summary.config(text="Could not load summary — see logs.",
                       foreground="#a00")
        return
    summary.config(
        text=f"Collectors: {s['collectors']} ({s['active_collectors']} in date, "
             f"{s['revoked_collectors']} revoked, {s['with_password']} with a "
             f"password)   Late today: {s['late_today']}   This month: "
             f"{s['late_this_month']}   Fees outstanding: "
             f"£{s['fees_outstanding']:.2f}")
    problems = []
    if s["children_without_collectors"]:
        problems.append(f"{s['children_without_collectors']} child(ren) have "
                        "nobody authorised to collect them")
    if s["id_unchecked"]:
        problems.append(f"{s['id_unchecked']} collector(s) have no photo ID "
                        "check recorded")
    if s["open_late"]:
        problems.append(f"{s['open_late']} child(ren) logged late today and not "
                        "yet marked collected")
    warn.config(text=("⚠ " + "; ".join(problems)) if problems else "")


# ── Door check ───────────────────────────────────────────────────────────────

@_safe_view
def open_verify(host) -> None:
    choices = _pupil_choices()
    dlg = tk.Toplevel(host.root)
    dlg.title("Verify Collector")
    dlg.transient(host.root)
    dlg.geometry("520x420")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Who is collecting?", font=("", 13, "bold")).pack(
        anchor="w", pady=(0, 8))

    pupil_by_label = {lbl: pid for pid, lbl in choices}
    ttk.Label(frm, text="Child:").pack(anchor="w")
    child_var = tk.StringVar()
    child_box = ttk.Combobox(frm, textvariable=child_var,
                             values=[lbl for _p, lbl in choices],
                             state="readonly" if choices else "normal", width=44)
    child_box.pack(anchor="w", pady=(2, 6))

    ttk.Label(frm, text="Authorised for this child:").pack(anchor="w")
    listed = tk.Text(frm, height=5, width=56, state="disabled", wrap="word")
    listed.pack(anchor="w", pady=(2, 6))

    ttk.Label(frm, text="Name of the person collecting:").pack(anchor="w")
    name_var = tk.StringVar()
    ttk.Entry(frm, textvariable=name_var, width=44).pack(anchor="w", pady=(2, 6))

    ttk.Label(frm, text="Collection password (if they have one):").pack(anchor="w")
    pw_var = tk.StringVar()
    ttk.Entry(frm, textvariable=pw_var, width=44, show="•").pack(
        anchor="w", pady=(2, 8))

    verdict = ttk.Label(frm, wraplength=470, font=("", 11, "bold"))
    verdict.pack(anchor="w", pady=(4, 8))

    def _show_listed(*_a) -> None:
        pid = pupil_by_label.get(child_var.get().strip(), "")
        lines = []
        if pid:
            for c in data.list_collectors(pupil_id=pid):
                marks = []
                if c.has_password:
                    marks.append("password")
                if c.status == "revoked":
                    marks.append("REVOKED")
                if not c.id_checked:
                    marks.append("ID not checked")
                suffix = f"  [{', '.join(marks)}]" if marks else ""
                lines.append(f"• {c.full_name} ({c.relationship or '-'}){suffix}")
            for name in data.emergency_contact_collectors(pid):
                lines.append(f"• {name}  [emergency contact]")
        listed.config(state="normal")
        listed.delete("1.0", "end")
        listed.insert("1.0", "\n".join(lines) or "(nobody on the list)")
        listed.config(state="disabled")

    child_box.bind("<<ComboboxSelected>>", _show_listed)

    def _check() -> None:
        pid = pupil_by_label.get(child_var.get().strip(), "")
        if not pid:
            verdict.config(text="Choose a child first.", foreground="#a00")
            return
        try:
            result = data.verify_collector(pid, name_var.get(),
                                           pw_var.get() or None)
        except Exception as e:  # noqa: BLE001
            logger.exception("Collector verification failed")
            verdict.config(text=f"Could not check — {e}", foreground="#a00")
            return
        if result.allowed:
            verdict.config(text=f"✔ ALLOWED — {result.reason}",
                           foreground="#1e7e34")
        else:
            verdict.config(
                text=f"✘ DO NOT RELEASE THE CHILD — {result.reason}",
                foreground="#c0392b")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(4, 0))
    ttk.Button(btns, text="Close", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Check", command=_check).pack(side="right")
    dlg.wait_window()


# ── Authorised collectors tab ────────────────────────────────────────────────

_COLLECTOR_FIELDS: list[tuple[str, str, str, Any]] = [
    ("full_name",    "Full name",                  "entry",    None),
    ("relationship", "Relationship",               "choice",   RELATIONSHIPS),
    ("phone",        "Phone",                      "entry",    None),
    ("password",     "Collection password",        "password", None),
    ("clear_password", "Remove existing password", "bool",     None),
    ("photo_on_file", "Photo on file",             "bool",     None),
    ("id_checked",   "Photo ID checked",           "bool",     None),
    ("is_escalation_contact", "Escalation contact", "bool",    None),
    ("valid_from",   "Authorised from (YYYY-MM-DD)", "entry",  None),
    ("valid_until",  "Authorised until",           "entry",    None),
    ("status",       "Status",                     "choice", COLLECTOR_STATUSES),
    ("notes",        "Notes",                      "entry",    None),
]


def _collector_fields(*, with_pupil: bool) -> list[tuple[str, str, str, Any]]:
    fields = list(_COLLECTOR_FIELDS)
    if with_pupil:
        fields = [f for f in fields if f[0] != "clear_password"]
        fields.insert(0, ("pupil_id", "Child", "pupil", _pupil_choices()))
    return fields


def _build_collector_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Collector",
               command=lambda: _add_collector(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_collector(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Revoke",
               command=lambda: _revoke_collector(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_collector(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_collectors(tree)).pack(side="left", padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("child", "Child", 170), ("name", "Name", 170),
        ("rel", "Relationship", 120), ("phone", "Phone", 120),
        ("pwd", "Password", 80), ("idchk", "ID checked", 90),
        ("esc", "Escalation", 90), ("valid", "Valid", 150),
        ("status", "Status", 80),
    ])
    tree.bind("<Double-1>", lambda _e: _edit_collector(host, tree))
    _refresh_collectors(tree)


def _refresh_collectors(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_collectors()
    except Exception:
        logger.exception("Could not refresh collectors")
        return
    for c in rows:
        if c.status == "revoked":
            tag = "muted"
        elif not c.id_checked:
            tag = "warn"
        else:
            tag = ""
        window = " to ".join(x for x in (c.valid_from, c.valid_until) if x) or "-"
        tree.insert("", "end", iid=c.collector_id, tags=(tag,) if tag else (),
                    values=(c.collector_id, c.child_name or c.pupil_id,
                            c.full_name, c.relationship or "-", c.phone or "-",
                            "Yes" if c.has_password else "No",
                            "Yes" if c.id_checked else "No",
                            "Yes" if c.is_escalation_contact else "",
                            window, c.status))


@_safe_view
def _add_collector(host) -> None:
    fields = _form_dialog(host, "Add Authorised Collector",
                          _collector_fields(with_pupil=True),
                          initial={"status": "active"})
    if not fields:
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add collector", "Please choose a child.",
                             parent=host.root)
        return
    try:
        c = data.create_collector(fields)
    except ValidationError as e:
        messagebox.showerror("Add collector", str(e), parent=host.root)
        return
    host.status_var.set(f"Added authorised collector {c.collector_id}")
    open_manager(host)


@_safe_view
def _edit_collector(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a collector", "edit")
    if not sel:
        return
    c = data.get_collector(sel)
    if c is None:
        return
    initial = {k: getattr(c, k, None) for k, _l, _kd, _ch in _COLLECTOR_FIELDS}
    initial["password"] = ""
    initial["clear_password"] = False
    title = f"Edit collector — {c.full_name}"
    if c.has_password:
        title += " (leave password blank to keep the current one)"
    fields = _form_dialog(host, title, _collector_fields(with_pupil=False),
                          initial=initial)
    if not fields:
        return
    try:
        data.update_collector(sel, fields)
    except ValidationError as e:
        messagebox.showerror("Edit collector", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated collector {sel}")
    open_manager(host)


@_safe_view
def _revoke_collector(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a collector", "revoke")
    if not sel:
        return
    if not messagebox.askyesno(
            "Revoke authorisation",
            f"Revoke {sel}? They will no longer be allowed to collect the "
            "child, but the record is kept.", parent=host.root):
        return
    data.revoke_collector(sel, "Revoked from the GUI")
    host.status_var.set(f"Revoked collector {sel}")
    open_manager(host)


@_safe_view
def _delete_collector(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a collector", "delete")
    if not sel:
        return
    if not messagebox.askyesno(
            "Delete collector",
            f"Delete {sel} outright? Revoking keeps the audit trail; deleting "
            "does not.", parent=host.root):
        return
    data.delete_collector(sel)
    host.status_var.set(f"Deleted collector {sel}")
    open_manager(host)


# ── Late collection tab ──────────────────────────────────────────────────────

_LATE_FIELDS: list[tuple[str, str, str, Any]] = [
    ("event_date",     "Date (YYYY-MM-DD)",        "entry",  None),
    ("due_time",       "Booked collection (HH:MM)", "entry", None),
    ("collected_time", "Actually collected (HH:MM)", "entry", None),
    ("collected_by",   "Collected by",             "entry",  None),
    ("fee_amount",     "Fee (blank = policy)",     "entry",  None),
    ("fee_status",     "Fee status",               "choice", FEE_STATUSES),
    ("escalation_stage", "Escalation stage",       "choice", ESCALATION_STAGES),
    ("escalated_to",   "Escalated to",             "entry",  None),
    ("parent_contacted", "Parent contacted",       "bool",   None),
    ("safeguarding_referral", "Safeguarding referral made", "bool", None),
    ("recorded_by",    "Recorded by (staff ID)",   "entry",  None),
    ("notes",          "Notes",                    "entry",  None),
]


def _late_fields(*, with_pupil: bool) -> list[tuple[str, str, str, Any]]:
    fields = list(_LATE_FIELDS)
    if with_pupil:
        fields.insert(0, ("pupil_id", "Child", "pupil", _pupil_choices()))
    return fields


def _build_late_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Log Late Collection",
               command=lambda: _add_late(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Mark Collected",
               command=lambda: _close_late(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_late(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Waive Fee",
               command=lambda: _waive_late(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_late(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_late(tree)).pack(side="left", padx=2)

    ttk.Label(parent, foreground="#555",
              text=f"Policy: {data.LATE_FEE_GRACE_MINUTES} minutes' grace, then "
                   f"£{data.LATE_FEE_PER_BLOCK:.2f} per started "
                   f"{data.LATE_FEE_BLOCK_MINUTES} minutes.").pack(
        anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("id", "ID", 70), ("child", "Child", 170), ("date", "Date", 100),
        ("due", "Due", 70), ("got", "Collected", 90), ("late", "Late", 70),
        ("fee", "Fee", 80), ("feestatus", "Fee status", 90),
        ("esc", "Escalation", 170), ("by", "Collected by", 140),
    ])
    tree.bind("<Double-1>", lambda _e: _edit_late(host, tree))
    _refresh_late(tree)


def _refresh_late(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_late_collections()
    except Exception:
        logger.exception("Could not refresh late collections")
        return
    for r in rows:
        if r.safeguarding_referral or r.minutes_late >= 60:
            tag = "alert"
        elif not r.collected_time:
            tag = "warn"
        else:
            tag = ""
        tree.insert("", "end", iid=r.record_id, tags=(tag,) if tag else (),
                    values=(r.record_id, r.child_name or r.pupil_id,
                            r.event_date, r.due_time, r.collected_time or "-",
                            f"{r.minutes_late}m", f"£{r.fee_amount:.2f}",
                            r.fee_status, r.escalation_stage,
                            r.collected_by or "-"))


@_safe_view
def _add_late(host) -> None:
    fields = _form_dialog(host, "Log Late Collection",
                          _late_fields(with_pupil=True),
                          initial={"event_date": data._today(),
                                   "fee_status": "due"})
    if not fields:
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Log late collection", "Please choose a child.",
                             parent=host.root)
        return
    try:
        r = data.log_late_collection(fields)
    except ValidationError as e:
        messagebox.showerror("Log late collection", str(e), parent=host.root)
        return
    host.status_var.set(
        f"Logged {r.record_id} — {r.minutes_late} min late, £{r.fee_amount:.2f}")
    if r.minutes_late >= 60:
        messagebox.showwarning(
            "Uncollected child",
            f"{r.child_name or r.pupil_id} was {r.minutes_late} minutes late.\n\n"
            "Check the uncollected-child procedure has been followed and the "
            "DSL informed.", parent=host.root)
    open_manager(host)


@_safe_view
def _close_late(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a record", "mark collected")
    if not sel:
        return
    fields = _form_dialog(host, "Mark As Collected", [
        ("collected_time", "Collected at (HH:MM, blank = now)", "entry", None),
        ("collected_by", "Collected by", "entry", None),
    ], geometry="420x180")
    if fields is None:
        return
    try:
        r = data.close_late_collection(sel, fields.get("collected_time") or None,
                                       fields.get("collected_by") or None)
    except ValidationError as e:
        messagebox.showerror("Mark collected", str(e), parent=host.root)
        return
    host.status_var.set(
        f"{r.record_id}: collected at {r.collected_time}, "
        f"{r.minutes_late} min late, fee £{r.fee_amount:.2f}")
    open_manager(host)


@_safe_view
def _edit_late(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a record", "edit")
    if not sel:
        return
    r = data.get_late_collection(sel)
    if r is None:
        return
    initial = {k: getattr(r, k) for k, _l, _kd, _ch in _LATE_FIELDS}
    fields = _form_dialog(host, f"Edit — {r.child_name or r.pupil_id}",
                          _late_fields(with_pupil=False), initial=initial)
    if not fields:
        return
    try:
        data.update_late_collection(sel, fields)
    except ValidationError as e:
        messagebox.showerror("Edit late collection", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated late collection {sel}")
    open_manager(host)


@_safe_view
def _waive_late(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a record", "waive the fee on")
    if not sel:
        return
    if not messagebox.askyesno("Waive fee", f"Waive the late fee on {sel}?",
                               parent=host.root):
        return
    data.waive_fee(sel, "Waived from the GUI")
    host.status_var.set(f"Waived fee on {sel}")
    open_manager(host)


@_safe_view
def _delete_late(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a record", "delete")
    if not sel:
        return
    if not messagebox.askyesno(
            "Delete record",
            f"Delete {sel}? Late-collection records are part of the "
            "safeguarding audit trail.", parent=host.root):
        return
    data.delete_late_collection(sel)
    host.status_var.set(f"Deleted late collection {sel}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Collections & Late Pickup",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Collections & Late Pickup from the navigation "
              "menu.").pack(anchor="w")
    return frame
