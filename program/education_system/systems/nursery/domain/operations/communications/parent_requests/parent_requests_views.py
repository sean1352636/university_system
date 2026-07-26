"""Tkinter views for Parent Self-Service Requests (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). The request inbox: pending items first, a plain-English preview of
what approving each one will do, and Approve / Decline buttons that write the
change through to the real record — the GUI counterpart of
``parent_requests_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.operations.communications.parent_requests import (
    parent_requests as data,
)
from education_system.systems.nursery.domain.operations.communications.parent_requests.parent_requests import (
    CONTACT_FIELDS,
    REQUEST_TYPES,
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


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Parent requests", f"Select a request to {verb}.",
                            parent=host.root)
        return None
    return sel


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: parent_requests open_manager")
    root = _clear(host)
    _header(root, "Parent Self-Service Requests")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Approve & Apply",
               command=lambda: _approve(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Decline",
               command=lambda: _decline(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="View",
               command=lambda: _view(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Log a Request",
               command=lambda: _submit(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Account & Invoices",
               command=lambda: _statement(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 2))
    warn = ttk.Label(root, foreground="#a00")
    warn.pack(anchor="w", pady=(0, 6))

    cols = ("id", "child", "type", "submitted", "by", "status", "what")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 160), ("type", "Type", 120),
        ("submitted", "Submitted", 150), ("by", "By", 130),
        ("status", "Status", 90), ("what", "What was asked for", 320),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("pending", foreground="#b9770e")
    tree.tag_configure("declined", foreground="#7f8c8d")
    tree.tag_configure("approved", foreground="#1e7e34")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _view(host, tree))

    preview = ttk.Label(root, foreground="#2c3e50", wraplength=900,
                        font=("", 10, "italic"))
    preview.pack(anchor="w", pady=(8, 0))
    tree.bind("<<TreeviewSelect>>",
              lambda _e: _update_preview(tree, preview))

    _refresh(tree, summary, warn)
    host.status_var.set("Parent requests loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label, warn: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_requests()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh parent requests")
        summary.config(text="Could not load — see logs.", foreground="#a00")
        return
    for r in rows:
        tree.insert("", "end", iid=r.request_id, tags=(r.status,), values=(
            r.request_id, r.child_name or r.pupil_id, r.request_type,
            (r.submitted_at or "")[:19], r.submitted_by or "-", r.status,
            r.summary_line))
    by_type = ", ".join(f"{t}: {n}" for t, n in s["pending_by_type"].items()
                        if n)
    summary.config(
        text=f"Pending: {s['pending']}   Approved: {s['approved']}   "
             f"Declined: {s['declined']}   Submitted today: "
             f"{s['submitted_today']}"
             + (f"   ({by_type})" if by_type else ""),
        foreground="#b9770e" if s["pending"] else "#555")
    warn.config(text=(
        f"⚠ {s['overdue']} pending request(s) are for dates that have already "
        "passed." if s["overdue"] else ""))


def _update_preview(tree: ttk.Treeview, preview: ttk.Label) -> None:
    sel = tree.focus()
    if not sel:
        preview.config(text="")
        return
    try:
        r = data.get_request(sel)
        preview.config(
            text=(f"If approved: {data.preview(sel)}" if r and r.is_open
                  else (f"Applied as {r.applied_ref}"
                        if r and r.applied_ref else "")))
    except Exception:
        logger.debug("Could not build request preview", exc_info=True)
        preview.config(text="")


@_safe_view
def _view(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "view")
    if not sel:
        return
    r = data.get_request(sel)
    if r is None:
        return
    lines = [
        f"Child:        {r.child_name or '-'} ({r.pupil_id})",
        f"Type:         {r.request_type}",
        f"Submitted by: {r.submitted_by or '-'} at {r.submitted_at}",
        f"Status:       {r.status}",
        "",
        "Details:",
    ]
    lines += [f"  {k}: {v}" for k, v in r.payload.items()]
    if r.decided_at:
        lines += ["", f"Decided by {r.decided_by_name or r.decided_by or '-'} "
                      f"at {r.decided_at}",
                  f"Note: {r.decision_note or '-'}"]
    if r.applied_ref:
        lines.append(f"Applied as: {r.applied_ref}")
    if r.is_open:
        lines += ["", f"If approved: {data.preview(sel)}"]
    messagebox.showinfo(f"Request {r.request_id}", "\n".join(lines),
                        parent=host.root)


@_safe_view
def _approve(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "approve")
    if not sel:
        return
    r = data.get_request(sel)
    if r is None:
        return
    if not r.is_open:
        messagebox.showinfo("Approve", f"Request {sel} is already {r.status}.",
                            parent=host.root)
        return
    if not messagebox.askyesno("Approve & apply",
                               f"{data.preview(sel)}\n\nApply it now?",
                               parent=host.root):
        return
    fields = _form_dialog(host, "Approve", [
        ("decided_by", "Your staff ID", "entry", None),
        ("note", "Note (optional)", "entry", None),
    ], geometry="420x180")
    if fields is None:
        return
    try:
        out = data.approve(sel, fields.get("decided_by") or None,
                           fields.get("note") or None)
    except ValidationError as e:
        messagebox.showerror("Approve", str(e), parent=host.root)
        return
    host.status_var.set(
        f"Approved {out.request_id} — applied as {out.applied_ref}")
    open_manager(host)


@_safe_view
def _decline(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "decline")
    if not sel:
        return
    fields = _form_dialog(host, "Decline Request", [
        ("decided_by", "Your staff ID", "entry", None),
        ("note", "Reason for the parent", "entry", None),
    ], geometry="460x180")
    if fields is None:
        return
    try:
        data.decline(sel, fields.get("decided_by") or None,
                     fields.get("note") or None)
    except ValidationError as e:
        messagebox.showerror("Decline", str(e), parent=host.root)
        return
    host.status_var.set(f"Declined {sel}")
    open_manager(host)


# ── Logging a request on a parent's behalf ───────────────────────────────────

def _payload_fields(request_type: str) -> list[tuple[str, str, str, Any]]:
    if request_type == "session":
        return [
            ("session_date", "Session date (YYYY-MM-DD)", "entry", None),
            ("session_type", "Session", "choice", ("am", "pm", "all-day")),
            ("kind", "Kind", "choice", ("extra", "cancellation")),
            ("room", "Room (optional)", "entry", None),
            ("reason", "Reason", "entry", None),
        ]
    if request_type == "absence":
        return [
            ("absence_date", "Absence date (YYYY-MM-DD)", "entry", None),
            ("status", "Status", "choice", ("absent", "sick", "holiday")),
            ("reason", "Reason", "entry", None),
            ("expected_return", "Expected back (optional)", "entry", None),
        ]
    if request_type == "contact-update":
        return [(f, f.replace("_", " ").title(), "entry", None)
                for f in CONTACT_FIELDS]
    if request_type == "consent":
        from education_system.systems.nursery.domain.governance.consents import (
            consents as _consents,
        )
        return [
            ("consent_type", "Consent type", "choice", _consents.CONSENT_TYPES),
            ("consent_status", "Answer", "choice", ("granted", "refused")),
            ("expiry_date", "Expiry (optional)", "entry", None),
        ]
    return [("message", "Message", "entry", None)]


@_safe_view
def _submit(host) -> None:
    first = _form_dialog(host, "Log a Parent Request", [
        ("pupil_id", "Child", "pupil", _pupil_choices()),
        ("request_type", "Request type", "choice", REQUEST_TYPES),
        ("submitted_by", "Parent name", "entry", None),
    ], geometry="460x230")
    if not first:
        return
    if not first.get("pupil_id"):
        messagebox.showerror("Log request", "Please choose a child.",
                             parent=host.root)
        return
    request_type = first.get("request_type") or ""
    if request_type not in REQUEST_TYPES:
        messagebox.showerror("Log request", "Please choose a request type.",
                             parent=host.root)
        return

    payload = _form_dialog(host, f"{request_type.title()} details",
                           _payload_fields(request_type), geometry="460x330")
    if payload is None:
        return
    try:
        r = data.submit({
            "pupil_id": first["pupil_id"], "request_type": request_type,
            "submitted_by": first.get("submitted_by") or None,
            "payload": {k: v for k, v in payload.items() if v},
        })
    except ValidationError as e:
        messagebox.showerror("Log request", str(e), parent=host.root)
        return
    host.status_var.set(f"Logged request {r.request_id}")
    open_manager(host)


@_safe_view
def _statement(host) -> None:
    fields = _form_dialog(host, "Account & Invoices", [
        ("pupil_id", "Child", "pupil", _pupil_choices()),
    ], geometry="460x150")
    if not fields or not fields.get("pupil_id"):
        return
    st = data.statement(fields["pupil_id"])
    lines = [f"{i['invoice_id']}  {i.get('period') or '-'}  "
             f"issued {i.get('issue_date') or '-'}  "
             f"£{float(i.get('total_amount') or 0):.2f}  {i.get('status')}"
             for i in st["invoices"]] or ["(no invoices)"]
    lines += ["",
              f"Invoiced: £{st['total_invoiced']:.2f}",
              f"Paid:     £{st['total_paid']:.2f}",
              f"Balance:  £{st['balance']:.2f}"]
    messagebox.showinfo(f"Account — {fields['pupil_id']}", "\n".join(lines),
                        parent=host.root)


# ── Generic form dialog ──────────────────────────────────────────────────────

def _form_dialog(host, title: str, fields: list[tuple[str, str, str, Any]], *,
                 initial: dict[str, Any] | None = None,
                 geometry: str = "460x400") -> dict[str, Any] | None:
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
        for key, _l, kind, _c in fields:
            value = (str(vars_[key].get()) or "").strip()
            out[key] = (pupil_by_label.get(value, "") if kind == "pupil"
                        else value)
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Parent Self-Service Requests",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Parent Self-Service Requests from the "
              "navigation menu.").pack(anchor="w")
    return frame
