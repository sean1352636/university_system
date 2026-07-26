"""Tkinter views for Funded Hours Claims (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists local-authority funding claims with a tree + toolbar and an
add/edit form dialog — the GUI counterpart of ``funding_claims_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.finance.funding_claims import (
    funding_claims as data,
)
from education_system.systems.nursery.domain.finance.funding_claims.funding_claims import (
    ENTITLEMENTS,
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
    logger.debug("GUI: funding_claims open_manager")
    root = _clear(host)
    _header(root, "Funded Hours Claims")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Claim",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "period", "child", "entitlement", "amount", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w, anc in [
        ("id", "ID", 80, "w"), ("period", "Period", 120, "w"),
        ("child", "Child", 160, "w"), ("entitlement", "Entitlement", 150, "w"),
        ("amount", "Amount £", 100, "e"), ("status", "Status", 90, "w"),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor=anc)
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Funding claims loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_claims()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh funding claims")
        try:
            messagebox.showerror("Funding claims", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for c in rows:
        tree.insert("", "end", iid=c.claim_id, values=(
            c.claim_id, c.funding_period or "-", c.child_name or "(whole setting)",
            c.entitlement or "-", f"{c.claim_amount:.2f}", c.status))
    summary.config(text=f"Claims: {int(s['count'])}    Total: £{s['total']:.2f}    "
                        f"Submitted: £{s['submitted']:.2f}    Paid: £{s['paid']:.2f}")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Funding claims", f"Select a claim to {verb}.",
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
    if not messagebox.askyesno("Delete claim", f"Delete claim {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_claim(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete claim %s", sel)
        messagebox.showerror("Delete claim", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted claim {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x460")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    choices = _pupil_choices()
    pid_label_by_id = {sid: lbl for sid, lbl in choices}
    pid_id_by_label = {lbl: sid for sid, lbl in choices}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
    pvar = tk.StringVar(value=pid_label_by_id.get(str(initial.get("pupil_id") or ""),
                                                  ""))
    ttk.Combobox(frm, textvariable=pvar,
                 values=["(whole setting)"] + [lbl for _i, lbl in choices],
                 width=34).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["__pupil_label"] = pvar
    row += 1

    spec = [
        ("funding_period", "Funding period", "entry"),
        ("entitlement", "Entitlement", "entitlement"),
        ("funded_hours", "Funded hours / week", "entry"),
        ("weeks", "Weeks in period", "entry"),
        ("hourly_rate", "LA hourly rate (£)", "entry"),
        ("headcount_date", "Headcount date (YYYY-MM-DD)", "entry"),
        ("status", "Status", "status"),
        ("submitted_date", "Submitted date (YYYY-MM-DD)", "entry"),
        ("notes", "Notes", "entry"),
    ]
    for key, label, kind in spec:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "entitlement":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(ENTITLEMENTS),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "draft"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)
    ttk.Label(frm, text="(Amount = funded hours × weeks × rate, computed on save)",
              foreground="#888").grid(row=row, column=0, columnspan=2, sticky="w",
                                      pady=(4, 0))
    row += 1

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            val = (v.get() or "").strip()
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get(val, "")
            else:
                out[k] = val
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    fields = _form_dialog(host, "Add Funding Claim")
    if not fields:
        host.status_var.set("Add claim cancelled")
        open_manager(host)
        return
    try:
        c = data.create_claim(fields)
    except ValidationError as e:
        messagebox.showerror("Add claim", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo("Claim created",
                        f"{c.funding_period or '-'} — £{c.claim_amount:.2f}",
                        parent=host.root)
    host.status_var.set(f"Created claim {c.claim_id}")
    open_manager(host)


@_safe_view
def open_edit(host, claim_id: str) -> None:
    c = data.get_claim(claim_id)
    if c is None:
        messagebox.showerror("Edit claim", f"No claim with id {claim_id}",
                             parent=host.root)
        return
    initial = {"pupil_id": c.pupil_id, "funding_period": c.funding_period,
               "entitlement": c.entitlement, "funded_hours": c.funded_hours,
               "weeks": c.weeks, "hourly_rate": c.hourly_rate,
               "headcount_date": c.headcount_date, "status": c.status,
               "submitted_date": c.submitted_date, "notes": c.notes}
    fields = _form_dialog(host, f"Edit claim {claim_id}", initial=initial)
    if not fields:
        return
    try:
        data.update_claim(claim_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit claim", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated claim {claim_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Funded Hours Claims",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Funded Hours Claims from the navigation menu."
              ).pack(anchor="w")
    return frame
