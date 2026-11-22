"""Security tab of Sixth Form User Management.

Split out of ``user_management_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.governance.user_management import security_ops
from education_system.systems.sixth_form.domain.governance.user_management.user_accounts import (
    UserAccountError,
)
from ._common import logger


# ── Security tab (features 13-20) ──────────────────────────────────

def _build_security_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    user_actions = ttk.Frame(nb, padding=8)
    failed = ttk.Frame(nb, padding=8)
    pw_age = ttk.Frame(nb, padding=8)
    breach = ttk.Frame(nb, padding=8)
    nb.add(user_actions, text="Per-user actions")
    nb.add(failed,       text="Failed logins")
    nb.add(pw_age,       text="Password age")
    nb.add(breach,       text="Breach list")

    _build_security_user_actions(gui, user_actions, refresh_all)
    _build_failed_logins(gui, failed)
    _build_password_age(gui, pw_age)
    _build_breach(gui, breach)


def _build_security_user_actions(gui, parent: ttk.Frame,
                                    refresh_all) -> None:
    ttk.Label(parent,
              text=("Type a user-id then run one of the security "
                    "actions. The Users tab has Suspend/Unsuspend; "
                    "the deeper actions live here."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    row = ttk.Frame(parent)
    row.pack(anchor="w", pady=4)
    ttk.Label(row, text="User id:").pack(side="left", padx=(0, 4))
    uid_var = tk.StringVar()
    ttk.Entry(row, textvariable=uid_var, width=10).pack(side="left",
                                                          padx=(0, 8))

    out = tk.Text(parent, height=10, wrap="word")
    out.pack(fill="both", expand=True, pady=(8, 6))
    out.configure(state="disabled")

    def _report(text: str) -> None:
        out.configure(state="normal")
        out.delete("1.0", "end")
        out.insert("1.0", text)
        out.configure(state="disabled")

    def _get_uid() -> int | None:
        raw = uid_var.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("User id",
                                 "Enter a numeric user id.",
                                 parent=gui.root)
            return None
        return int(raw)

    def _force_pw():
        uid = _get_uid()
        if uid is None:
            return
        if not messagebox.askyesno(
                "Force password reset",
                f"Force user #{uid} to change password on next login "
                "and invalidate active sessions?",
                parent=gui.root):
            return
        try:
            security_ops.force_password_reset(gui.auth, uid)
            _report(f"User #{uid} flagged for password change. "
                     "Active sessions invalidated.")
        except UserAccountError as e:
            messagebox.showerror("Force reset", str(e), parent=gui.root)

    def _otl():
        uid = _get_uid()
        if uid is None:
            return
        try:
            token = security_ops.generate_one_time_login(gui.auth, uid)
            _report(f"One-time login token for user #{uid} "
                     f"(valid {security_ops.DEFAULT_OTL_TTL_HOURS}h):"
                     f"\n\n  {token}")
        except UserAccountError as e:
            messagebox.showerror("One-time login", str(e),
                                  parent=gui.root)

    def _reset_mfa():
        uid = _get_uid()
        if uid is None:
            return
        if not messagebox.askyesno(
                "Reset MFA",
                f"Clear MFA secret + recovery codes for user #{uid}? "
                "They'll need to re-enrol.",
                parent=gui.root):
            return
        try:
            security_ops.reset_mfa(gui.auth, uid)
            _report(f"MFA reset for user #{uid}.")
        except UserAccountError as e:
            messagebox.showerror("Reset MFA", str(e), parent=gui.root)

    def _list_sess():
        uid = _get_uid()
        if uid is None:
            return
        sess = security_ops.list_sessions(gui.auth, uid,
                                            active_only=False)
        if not sess:
            _report("(no sessions on file)")
            return
        lines = [f"{len(sess)} session(s) for user #{uid}:"]
        for s in sess:
            lines.append(
                f"  #{s.id}  "
                f"{'active' if s.is_active else 'inactive':<8}  "
                f"created {s.created_at}  expires {s.expires_at}")
        _report("\n".join(lines))

    def _revoke_all():
        uid = _get_uid()
        if uid is None:
            return
        if not messagebox.askyesno(
                "Revoke all sessions",
                f"Invalidate every active session for user #{uid}?",
                parent=gui.root):
            return
        n = security_ops.revoke_all_sessions(gui.auth, uid)
        _report(f"Invalidated {n} session(s) for user #{uid}.")

    def _lock():
        uid = _get_uid()
        if uid is None:
            return
        _open_lock_dialog(gui, auth=gui.auth, user_id=uid,
                            on_done=lambda: _report(
                                f"User #{uid} locked."))
        refresh_all()

    def _unlock():
        uid = _get_uid()
        if uid is None:
            return
        try:
            security_ops.unlock_user(gui.auth, uid)
            _report(f"User #{uid} unlocked.")
        except UserAccountError as e:
            messagebox.showerror("Unlock", str(e), parent=gui.root)
        refresh_all()

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=4)
    ttk.Button(bar, text="Force password reset",
               command=_force_pw).pack(side="left")
    ttk.Button(bar, text="One-time login link",
               command=_otl).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Reset MFA",
               command=_reset_mfa).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="List sessions",
               command=_list_sess).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Revoke all sessions",
               command=_revoke_all).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Lock…",
               command=_lock).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Unlock",
               command=_unlock).pack(side="left", padx=(4, 0))


def _open_lock_dialog(gui, *, auth, user_id: int, on_done) -> None:
    dlg = tk.Toplevel(gui.root)
    dlg.title("Lock user")
    dlg.geometry("440x220")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"User: #{user_id}").grid(row=0, column=0,
                                                       columnspan=2,
                                                       sticky="w",
                                                       pady=(0, 6))
    ttk.Label(body, text="Reason:").grid(row=1, column=0, sticky="e",
                                            padx=(0, 6))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40).grid(
        row=1, column=1, sticky="ew")

    ttk.Label(body, text="Duration (hours):").grid(row=2, column=0,
                                                      sticky="e",
                                                      padx=(0, 6))
    hours_var = tk.IntVar(value=24)
    ttk.Spinbox(body, from_=1, to=720, textvariable=hours_var,
                width=10).grid(row=2, column=1, sticky="w")

    def _go():
        try:
            security_ops.lock_user(
                auth, user_id,
                reason=reason_var.get().strip() or None,
                duration_hours=hours_var.get())
        except UserAccountError as e:
            messagebox.showerror("Lock", str(e), parent=dlg)
            return
        dlg.destroy()
        on_done()

    bar = ttk.Frame(body)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Lock",
               command=_go).pack(side="right")


def _build_failed_logins(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=4)
    ttk.Label(bar, text="Window:").pack(side="left", padx=(0, 4))
    hours_var = tk.IntVar(value=24)
    ttk.Combobox(bar, textvariable=hours_var, state="readonly",
                  width=10,
                  values=[1, 6, 24, 72, 168]).pack(side="left",
                                                   padx=(0, 6))
    ttk.Label(bar, text="hours").pack(side="left")

    cols = ("when", "username", "user_id", "ip", "detail")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=18)
    for c, lbl, w in [("when", "When", 170), ("username", "Username", 140),
                       ("user_id", "User #", 60), ("ip", "IP", 130),
                       ("detail", "Detail", 360)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    vs = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    vs.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True, pady=(6, 6))

    footer = ttk.Label(parent, text="", foreground="#555")
    footer.pack(anchor="w")

    def refresh():
        for it in tree.get_children():
            tree.delete(it)
        rows = security_ops.list_failed_logins(gui.auth,
                                                  hours=hours_var.get())
        for r in rows:
            tree.insert("", "end", values=(
                r.when, r.username or "—",
                r.user_id if r.user_id is not None else "",
                r.ip_address or "—", r.detail or ""))
        footer.configure(text=f"{len(rows)} event(s) in last "
                                f"{hours_var.get()}h.")

    ttk.Button(bar, text="Refresh",
               command=refresh).pack(side="left", padx=(8, 0))
    refresh()


def _build_password_age(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=4)
    ttk.Label(bar, text="Min age (days):").pack(side="left",
                                                  padx=(0, 4))
    min_var = tk.IntVar(value=90)
    ttk.Spinbox(bar, from_=1, to=3650, textvariable=min_var,
                width=10).pack(side="left", padx=(0, 8))
    include_never = tk.BooleanVar(value=True)
    ttk.Checkbutton(bar, text="Include never-set",
                    variable=include_never).pack(side="left")

    cols = ("user_id", "username", "display", "changed",
            "days_since")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=18)
    for c, lbl, w in [
        ("user_id", "User #", 60),
        ("username", "Username", 160),
        ("display", "Display name", 220),
        ("changed", "Last changed", 170),
        ("days_since", "Days", 70),
    ]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    vs = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    vs.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True, pady=(6, 6))

    footer = ttk.Label(parent, text="", foreground="#555")
    footer.pack(anchor="w")

    def refresh():
        for it in tree.get_children():
            tree.delete(it)
        rows = security_ops.password_age_report(
            gui.auth, min_age_days=min_var.get(),
            include_never_set=include_never.get())
        for r in rows:
            tree.insert("", "end", values=(
                r.user_id, r.username, r.display_name or "",
                r.password_changed_at or "(never)",
                r.days_since_change if r.days_since_change is not None
                else "—"))
        footer.configure(text=f"{len(rows)} user(s) over threshold.")

    ttk.Button(bar, text="Refresh",
               command=refresh).pack(side="left", padx=(8, 0))
    refresh()


def _build_breach(gui, parent: ttk.Frame) -> None:
    info = ttk.Label(
        parent,
        text=("Local breach-list. Import a file of SHA-1 hashes "
              "(one per line, hex; HIBP 'hash:count' rows accepted "
              "too) and check a candidate password against it. The "
              "hash never leaves the machine."),
        wraplength=820, foreground="#555", justify="left")
    info.pack(anchor="w", pady=(0, 8))

    stats_var = tk.StringVar()
    ttk.Label(parent, textvariable=stats_var,
              foreground="#444").pack(anchor="w")

    def refresh_stats():
        s = security_ops.breach_list_stats(gui.auth)
        stats_var.set(
            f"{s['hashes']:,} hashes loaded · "
            f"latest import: {s['latest_import'] or '(none)'}")

    def _import():
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        p = filedialog.askopenfilename(
            parent=gui.root, title="Pick breach-hash file",
            filetypes=[("Text", "*.txt *.list"), ("All", "*.*")])
        if not p:
            return
        try:
            n = security_ops.import_breach_list(gui.auth, p)
        except UserAccountError as e:
            messagebox.showerror("Breach list", str(e),
                                  parent=gui.root)
            return
        except Exception as e:
            logger.exception("breach import crashed")
            messagebox.showerror("Breach list", f"Unexpected: {e}",
                                  parent=gui.root)
            return
        messagebox.showinfo("Breach list",
                              f"Inserted {n} new hash(es).",
                              parent=gui.root)
        refresh_stats()

    row = ttk.Frame(parent)
    row.pack(anchor="w", pady=(6, 0))
    ttk.Button(row, text="Import file…",
               command=_import).pack(side="left")
    ttk.Button(row, text="Refresh stats",
               command=refresh_stats).pack(side="left", padx=(4, 0))

    ttk.Separator(parent).pack(fill="x", pady=8)

    check_row = ttk.Frame(parent)
    check_row.pack(anchor="w")
    ttk.Label(check_row, text="Check password:").pack(side="left",
                                                        padx=(0, 4))
    pw_var = tk.StringVar()
    ttk.Entry(check_row, textvariable=pw_var, width=30,
              show="*").pack(side="left", padx=(0, 4))
    result_var = tk.StringVar()
    ttk.Label(check_row, textvariable=result_var,
              foreground="#a33").pack(side="left", padx=(8, 0))

    def _check():
        pw = pw_var.get()
        if not pw:
            result_var.set("")
            return
        hit = security_ops.check_password_compromised(gui.auth, pw)
        if hit:
            result_var.set("⚠ FOUND in breach list — do not use.")
        else:
            result_var.set("✓ Not in breach list.")

    ttk.Button(check_row, text="Check",
               command=_check).pack(side="left", padx=(0, 4))

    refresh_stats()
