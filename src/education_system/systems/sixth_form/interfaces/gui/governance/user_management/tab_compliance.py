"""Compliance tab of Sixth Form User Management.

Split out of ``user_management_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.governance.user_management import compliance
from education_system.systems.sixth_form.domain.governance.user_management.user_accounts import (
    UserAccountError,
)


# ── Compliance tab (39-43) ─────────────────────────────────────────

def _build_compliance_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    consent_p = ttk.Frame(nb, padding=8)
    sar_p = ttk.Frame(nb, padding=8)
    retention_p = ttk.Frame(nb, padding=8)
    safeguard_p = ttk.Frame(nb, padding=8)
    erasure_p = ttk.Frame(nb, padding=8)
    nb.add(consent_p, text="GDPR consents")
    nb.add(sar_p, text="SAR bundler")
    nb.add(retention_p, text="Retention sweep")
    nb.add(safeguard_p, text="Safeguarding")
    nb.add(erasure_p, text="Right to erasure")

    _build_consents_pane(gui, consent_p)
    _build_sar_pane(gui, sar_p)
    _build_retention_pane(gui, retention_p, refresh_all)
    _build_safeguard_pane(gui, safeguard_p)
    _build_erasure_pane(gui, erasure_p, refresh_all)


def _build_consents_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid = tk.StringVar()
    ttk.Entry(bar, textvariable=uid, width=8).pack(side="left",
                                                       padx=(0, 8))
    ttk.Label(bar, text="Consent type:").pack(side="left", padx=(0, 4))
    ct = tk.StringVar()
    ttk.Entry(bar, textvariable=ct, width=22).pack(side="left",
                                                       padx=(0, 8))
    granted = tk.BooleanVar(value=True)
    ttk.Checkbutton(bar, text="Granted",
                    variable=granted).pack(side="left", padx=(0, 8))

    cols = ("ts", "type", "granted", "source", "version")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("ts", "Updated", 160),
                       ("type", "Type", 220),
                       ("granted", "Granted", 80),
                       ("source", "Source", 120),
                       ("version", "Version", 80)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        if not uid.get().strip().isdigit():
            return
        for r in compliance.list_consents(gui.auth, int(uid.get())):
            tree.insert("", "end", values=(
                r.get("updated_at"), r.get("consent_type"),
                "yes" if r.get("granted") else "no",
                r.get("source"), r.get("version")))

    def _record():
        if not uid.get().strip().isdigit() or not ct.get().strip():
            return
        try:
            compliance.record_consent(
                gui.auth, user_id=int(uid.get()),
                consent_type=ct.get().strip(),
                granted=granted.get())
        except UserAccountError as e:
            messagebox.showerror("Consent", str(e), parent=gui.root)
            return
        _refresh()

    ttk.Button(bar, text="Record",
               command=_record).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Load",
               command=_refresh).pack(side="left")


def _build_sar_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Bundle every row attached to a user-id across "
                    "auth, audit, and lifecycle tables into a single "
                    "zip — what GDPR calls a Subject Access Request."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))
    bar = ttk.Frame(parent)
    bar.pack(anchor="w")
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid = tk.StringVar()
    ttk.Entry(bar, textvariable=uid, width=8).pack(side="left",
                                                       padx=(0, 8))
    out_var = tk.StringVar()
    ttk.Label(parent, textvariable=out_var,
              foreground="#444").pack(anchor="w", pady=(8, 0))

    def _go():
        if not uid.get().strip().isdigit():
            return
        try:
            path = compliance.bundle_sar(gui.auth, int(uid.get()))
        except UserAccountError as e:
            messagebox.showerror("SAR", str(e), parent=gui.root)
            return
        out_var.set(f"Bundle written to: {path}")
        messagebox.showinfo("SAR", f"Bundle written:\n{path}",
                              parent=gui.root)

    ttk.Button(bar, text="Bundle",
               command=_go).pack(side="left")


def _build_retention_pane(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Sweep archived users whose retention window has "
                    "passed. ‘Preview’ lists them; ‘Execute’ runs the "
                    "permanent-delete on each."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    out = tk.Text(parent, height=20, wrap="word")
    out.pack(fill="both", expand=True, pady=(6, 6))
    out.configure(state="disabled")

    def _run(execute: bool):
        result = compliance.execute_retention_policy(
            gui.auth, purge_expired=execute)
        out.configure(state="normal")
        out.delete("1.0", "end")
        out.insert("1.0",
                    f"Candidates: {len(result['candidates'])}\n"
                    f"Purged: {len(result['purged'])}\n"
                    f"Errors: {len(result['errors'])}\n\n")
        for c in result["candidates"]:
            out.insert("end", f"  archive {c['archive_id']} "
                               f"user {c['user_id']} "
                               f"retention until "
                               f"{c['retention_until']}\n")
        for e in result["errors"]:
            out.insert("end", f"\nERROR user {e[0]}: {e[1]}")
        out.configure(state="disabled")
        if execute:
            refresh_all()

    bar = ttk.Frame(parent)
    bar.pack(fill="x")
    ttk.Button(bar, text="Preview",
               command=lambda: _run(False)).pack(side="left")
    ttk.Button(bar, text="Execute permanent delete",
               command=lambda: _run(True)).pack(side="left",
                                                  padx=(6, 0))


def _build_safeguard_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 6))
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid = tk.StringVar()
    ttk.Entry(bar, textvariable=uid, width=8).pack(side="left",
                                                       padx=(0, 8))
    ttk.Label(bar, text="Reason:").pack(side="left", padx=(0, 4))
    reason = tk.StringVar()
    ttk.Entry(bar, textvariable=reason, width=30).pack(side="left",
                                                           padx=(0, 8))

    cols = ("uid", "reason", "set_by", "set_at")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("uid", "User #", 70),
                       ("reason", "Reason", 320),
                       ("set_by", "Set by", 140),
                       ("set_at", "Set at", 170)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in compliance.list_safeguarded(gui.auth):
            tree.insert("", "end", values=(
                r.get("user_id"), r.get("reason") or "",
                r.get("set_by") or "", r.get("set_at")))

    def _set():
        if not uid.get().strip().isdigit():
            return
        try:
            compliance.set_safeguarding(
                gui.auth, int(uid.get()),
                reason=reason.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Safeguarding", str(e), parent=gui.root)
            return
        _refresh()

    def _clear():
        if not uid.get().strip().isdigit():
            return
        compliance.clear_safeguarding(gui.auth, int(uid.get()))
        _refresh()

    ttk.Button(bar, text="Set flag",
               command=_set).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Clear flag",
               command=_clear).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()


def _build_erasure_pane(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Open an erasure request; a *different* admin (DPO) "
                    "executes it. The request closes by running the "
                    "permanent-delete flow."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 6))

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid = tk.StringVar()
    ttk.Entry(bar, textvariable=uid, width=8).pack(side="left",
                                                       padx=(0, 8))
    ttk.Label(bar, text="Reason:").pack(side="left", padx=(0, 4))
    reason = tk.StringVar()
    ttk.Entry(bar, textvariable=reason, width=30).pack(side="left",
                                                           padx=(0, 8))

    cols = ("rid", "target", "status", "requested_by",
            "dpo_approved_by", "executed_at")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("rid", "Req #", 70),
                       ("target", "Target #", 70),
                       ("status", "Status", 90),
                       ("requested_by", "Requested by", 130),
                       ("dpo_approved_by", "DPO", 130),
                       ("executed_at", "Executed at", 170)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in compliance.list_erasure_requests(gui.auth):
            tree.insert("", "end", iid=str(r["request_id"]), values=(
                r["request_id"], r["target_user_id"], r["status"],
                r["requested_by"] or "",
                r["dpo_approved_by"] or "",
                r["executed_at"] or ""))

    def _open():
        if not uid.get().strip().isdigit():
            return
        try:
            compliance.open_erasure_request(
                gui.auth, target_user_id=int(uid.get()),
                reason=reason.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Erasure", str(e), parent=gui.root)
            return
        _refresh()

    def _execute():
        sel = tree.focus()
        if not sel:
            return
        if not messagebox.askyesno(
                "Execute erasure",
                f"Permanently erase the target of request #{sel}? "
                "This is irreversible.",
                parent=gui.root):
            return
        try:
            compliance.execute_erasure(gui.auth, int(sel))
        except UserAccountError as e:
            messagebox.showerror("Erasure", str(e), parent=gui.root)
            return
        _refresh()
        refresh_all()

    ttk.Button(bar, text="Open request",
               command=_open).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Execute (DPO)…",
               command=_execute).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()
