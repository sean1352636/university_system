"""Monitoring tab of Sixth Form User Management.

Split out of ``user_management_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from education_system.systems.sixth_form.domain.governance.user_management import audit_monitoring


# ── Monitoring tab (31-38) ─────────────────────────────────────────

def _build_monitoring_tab(gui, parent: ttk.Frame) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    audit_p = ttk.Frame(nb, padding=8)
    perm_p = ttk.Frame(nb, padding=8)
    login_p = ttk.Frame(nb, padding=8)
    concur_p = ttk.Frame(nb, padding=8)
    stale_p = ttk.Frame(nb, padding=8)
    digest_p = ttk.Frame(nb, padding=8)
    anomal_p = ttk.Frame(nb, padding=8)
    snap_p = ttk.Frame(nb, padding=8)
    nb.add(audit_p, text="Audit log")
    nb.add(perm_p, text="Permission changes")
    nb.add(login_p, text="Login map")
    nb.add(concur_p, text="Concurrent sessions")
    nb.add(stale_p, text="Stale accounts")
    nb.add(digest_p, text="Daily digest")
    nb.add(anomal_p, text="Anomalies")
    nb.add(snap_p, text="Snapshots")

    _build_audit_pane(gui, audit_p)
    _build_perm_changes_pane(gui, perm_p)
    _build_login_map_pane(gui, login_p)
    _build_concurrent_pane(gui, concur_p)
    _build_stale_pane(gui, stale_p)
    _build_digest_pane(gui, digest_p)
    _build_anomaly_pane(gui, anomal_p)
    _build_snapshot_pane(gui, snap_p)


def _build_audit_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid_var = tk.StringVar()
    ttk.Entry(bar, textvariable=uid_var, width=8).pack(side="left",
                                                          padx=(0, 8))
    ttk.Label(bar, text="Action prefix:").pack(side="left", padx=(0, 4))
    pref_var = tk.StringVar()
    ttk.Entry(bar, textvariable=pref_var, width=18).pack(side="left",
                                                             padx=(0, 8))
    ttk.Label(bar, text="Hours:").pack(side="left", padx=(0, 4))
    hrs_var = tk.IntVar(value=24)
    ttk.Spinbox(bar, from_=1, to=720, textvariable=hrs_var,
                width=8).pack(side="left", padx=(0, 8))

    cols = ("ts", "actor", "action", "target", "details")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=16)
    for c, lbl, w in [("ts", "When", 160), ("actor", "Actor", 120),
                       ("action", "Action", 180),
                       ("target", "Target #", 70),
                       ("details", "Details", 400)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        try:
            uid = int(uid_var.get()) if uid_var.get().strip() else None
        except ValueError:
            uid = None
        rows = audit_monitoring.list_audit(
            gui.auth, target_user_id=uid,
            action_prefix=pref_var.get().strip() or None,
            since_hours=hrs_var.get())
        for r in rows:
            tree.insert("", "end", values=(
                r.get("ts"), r.get("actor") or "",
                r.get("action"),
                r.get("target_user_id") if r.get("target_user_id")
                is not None else "",
                (r.get("details") or "")[:200]))

    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()


def _build_perm_changes_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Permission-related actions only. The user_audit_log "
                    "is append-only and never UPDATEd."),
              foreground="#555").pack(anchor="w", pady=(0, 6))
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    ttk.Label(bar, text="Hours:").pack(side="left", padx=(0, 4))
    hrs = tk.IntVar(value=168)
    ttk.Spinbox(bar, from_=1, to=4320, textvariable=hrs,
                width=8).pack(side="left", padx=(0, 8))
    cols = ("ts", "actor", "action", "target", "details")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=16)
    for c, lbl, w in [("ts", "When", 160), ("actor", "Actor", 120),
                       ("action", "Action", 200),
                       ("target", "Target #", 70),
                       ("details", "Details", 400)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in audit_monitoring.list_perm_audit(
                gui.auth, since_hours=hrs.get()):
            tree.insert("", "end", values=(
                r.get("ts"), r.get("actor") or "",
                r.get("action"),
                r.get("target_user_id") if r.get("target_user_id")
                is not None else "",
                (r.get("details") or "")[:200]))

    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()


def _build_login_map_pane(gui, parent: ttk.Frame) -> None:
    cols = ("uid", "username", "name", "last_login", "ip", "country")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=18)
    for c, lbl, w in [("uid", "User #", 60),
                       ("username", "Username", 140),
                       ("name", "Name", 200),
                       ("last_login", "Last login", 160),
                       ("ip", "IP", 130),
                       ("country", "Rough country", 110)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(0, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for p in audit_monitoring.login_map(gui.auth):
            tree.insert("", "end", values=(
                p.user_id, p.username, p.display_name or "",
                p.last_login or "(never)", p.ip_address or "—",
                p.rough_country))

    ttk.Button(parent, text="Refresh",
               command=_refresh).pack(anchor="w")
    _refresh()


def _build_concurrent_pane(gui, parent: ttk.Frame) -> None:
    cols = ("uid", "username", "sessions", "ips")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("uid", "User #", 60),
                       ("username", "Username", 160),
                       ("sessions", "Active", 80),
                       ("ips", "Recent IPs", 480)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(0, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for c in audit_monitoring.concurrent_sessions(gui.auth):
            tree.insert("", "end", values=(
                c.user_id, c.username, c.session_count,
                ", ".join(c.ip_set) or "—"))

    ttk.Button(parent, text="Refresh",
               command=_refresh).pack(anchor="w")
    _refresh()


def _build_stale_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    ttk.Label(bar, text="Days idle ≥").pack(side="left", padx=(0, 4))
    days = tk.IntVar(value=180)
    ttk.Spinbox(bar, from_=30, to=3650, textvariable=days,
                width=8).pack(side="left", padx=(0, 8))
    inc = tk.BooleanVar(value=True)
    ttk.Checkbutton(bar, text="Include never-logged-in",
                    variable=inc).pack(side="left")

    cols = ("uid", "username", "name", "last_login", "days", "active")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("uid", "User #", 60),
                       ("username", "Username", 140),
                       ("name", "Name", 220),
                       ("last_login", "Last login", 160),
                       ("days", "Days idle", 80),
                       ("active", "Active", 70)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in audit_monitoring.stale_accounts(
                gui.auth, days=days.get(),
                include_never_logged_in=inc.get()):
            tree.insert("", "end", values=(
                r.user_id, r.username, r.display_name or "",
                r.last_login or "(never)",
                r.days_idle if r.days_idle is not None else "—",
                "yes" if r.is_active else "no"))

    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left", padx=(8, 0))
    _refresh()


def _build_digest_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Build the rolling admin digest. Save / view the "
                    "JSON or email it to an address."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))
    bar = ttk.Frame(parent)
    bar.pack(anchor="w")
    ttk.Label(bar, text="Hours:").pack(side="left", padx=(0, 4))
    h = tk.IntVar(value=24)
    ttk.Spinbox(bar, from_=1, to=168, textvariable=h,
                width=8).pack(side="left", padx=(0, 8))
    out = tk.Text(parent, height=22, wrap="none")
    out.pack(fill="both", expand=True, pady=(6, 6))
    out.configure(state="disabled")

    def _build():
        d = audit_monitoring.build_daily_digest(gui.auth,
                                                  hours=h.get())
        out.configure(state="normal")
        out.delete("1.0", "end")
        import json
        out.insert("1.0", json.dumps(d, indent=2, default=str))
        out.configure(state="disabled")

    def _email():
        to = simpledialog.askstring("Email digest",
                                       "Recipient email:",
                                       parent=gui.root)
        if not to:
            return
        ok = audit_monitoring.email_daily_digest(
            gui.auth, to=to, hours=h.get())
        messagebox.showinfo("Digest",
                              "Sent." if ok else "Send failed (see logs).",
                              parent=gui.root)

    ttk.Button(bar, text="Build digest",
               command=_build).pack(side="left")
    ttk.Button(bar, text="Email…",
               command=_email).pack(side="left", padx=(6, 0))


def _build_anomaly_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    ttk.Label(bar, text="Hours:").pack(side="left", padx=(0, 4))
    h = tk.IntVar(value=24)
    ttk.Spinbox(bar, from_=1, to=168, textvariable=h,
                width=8).pack(side="left", padx=(0, 8))
    cols = ("sev", "user_id", "detail")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=18)
    for c, lbl, w in [("sev", "Severity", 80),
                       ("user_id", "User #", 70),
                       ("detail", "Detail", 700)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for a in audit_monitoring.anomalies(gui.auth, hours=h.get()):
            tree.insert("", "end", values=(
                a.severity,
                a.user_id if a.user_id is not None else "",
                a.detail))

    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()


def _build_snapshot_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))

    def _take():
        label = simpledialog.askstring("Snapshot",
                                          "Label (optional):",
                                          parent=gui.root)
        sid = audit_monitoring.save_snapshot(gui.auth, label=label)
        messagebox.showinfo("Snapshot",
                              f"Saved snapshot #{sid}.",
                              parent=gui.root)
        _refresh()

    ttk.Button(bar, text="Take snapshot",
               command=_take).pack(side="left")

    cols = ("id", "taken_at", "taken_by", "label")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=12)
    for c, lbl, w in [("id", "ID", 60),
                       ("taken_at", "Taken at", 170),
                       ("taken_by", "By", 130),
                       ("label", "Label", 320)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="x", pady=(4, 4))

    out = tk.Text(parent, height=14, wrap="none")
    out.pack(fill="both", expand=True, pady=(4, 0))
    out.configure(state="disabled")

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for s in audit_monitoring.list_snapshots(gui.auth):
            tree.insert("", "end", iid=str(s["snapshot_id"]), values=(
                s["snapshot_id"], s["taken_at"],
                s["taken_by"] or "", s["label"] or ""))

    def _diff():
        sel = tree.selection()
        if len(sel) != 2:
            messagebox.showinfo("Snapshot diff",
                                 "Select exactly two snapshots.",
                                 parent=gui.root)
            return
        a, b = int(sel[0]), int(sel[1])
        d = audit_monitoring.diff_snapshots(gui.auth, a, b)
        out.configure(state="normal")
        out.delete("1.0", "end")
        import json
        out.insert("1.0", json.dumps(d, indent=2, default=str))
        out.configure(state="disabled")

    ttk.Button(bar, text="Diff two selected",
               command=_diff).pack(side="left", padx=(6, 0))
    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left", padx=(6, 0))
    _refresh()
