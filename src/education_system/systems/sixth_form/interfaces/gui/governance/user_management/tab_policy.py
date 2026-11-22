"""Policy tab (roles editor, MFA, IP rules, JIT, approvers, preview) of User Management.

Split out of ``user_management_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from typing import Any
from education_system.systems.sixth_form.domain.governance.user_management import permissions as perms_mod
from education_system.systems.sixth_form.domain.governance.user_management import access_policy
from education_system.systems.sixth_form.domain.governance.user_management.user_accounts import (
    UserAccountError,
)


# ── Access-policy tab (21-30) ──────────────────────────────────────

def _build_policy_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    roles_pane = ttk.Frame(nb, padding=8)
    mfa_pane = ttk.Frame(nb, padding=8)
    ip_pane = ttk.Frame(nb, padding=8)
    jit_pane = ttk.Frame(nb, padding=8)
    sens_pane = ttk.Frame(nb, padding=8)
    preview_pane = ttk.Frame(nb, padding=8)

    nb.add(roles_pane,   text="Roles & permissions")
    nb.add(mfa_pane,     text="MFA enforcement")
    nb.add(ip_pane,      text="IP rules")
    nb.add(jit_pane,     text="JIT access")
    nb.add(sens_pane,    text="Sensitive approvals")
    nb.add(preview_pane, text="Preview as user")

    _build_roles_editor(gui, roles_pane, refresh_all)
    _build_mfa_policy(gui, mfa_pane)
    _build_ip_rules(gui, ip_pane)
    _build_jit(gui, jit_pane, refresh_all)
    _build_sensitive(gui, sens_pane, refresh_all)
    _build_preview_as_user(gui, preview_pane)


# ── Role editor + diff + explain (22, 23, 24, 25) ──────────────────

def _build_roles_editor(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Manage role permission sets, clone or rename a "
                    "role, and diff two roles. The catalogue is fixed "
                    "but each role's bitmask is fully editable."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    top = ttk.Frame(parent)
    top.pack(fill="x")
    ttk.Label(top, text="Role:").pack(side="left", padx=(0, 4))
    role_var = tk.StringVar()
    role_combo = ttk.Combobox(top, textvariable=role_var,
                                state="readonly", width=28)
    role_combo.pack(side="left")
    ttk.Button(top, text="Refresh",
               command=lambda: _reload_roles()).pack(side="right")

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True, pady=(8, 4))

    diff_holder = ttk.LabelFrame(parent, text="Diff",
                                    padding=8)
    diff_holder.pack(fill="x", pady=(6, 0))

    state: dict[str, Any] = {"perm_vars": {}, "roles": []}

    def _reload_roles():
        state["roles"] = perms_mod.list_roles(gui.auth)
        role_combo['values'] = [r.role_key for r in state["roles"]]
        if state["roles"]:
            role_combo.current(0)
            _show_role()

    def _show_role():
        for w in table_holder.winfo_children():
            w.destroy()
        state["perm_vars"] = {}
        key = role_var.get()
        if not key:
            return
        role = next((r for r in state["roles"] if r.role_key == key),
                     None)
        if role is None:
            return
        ttk.Label(table_holder,
                  text=f"{role.label}  ({role.role_key})",
                  font=("", 11, "bold")).grid(row=0, column=0,
                                                 columnspan=2, sticky="w")
        ttk.Label(table_holder, text=role.description or "(no description)",
                  foreground="#666").grid(row=1, column=0, columnspan=2,
                                            sticky="w", pady=(0, 6))
        r_idx = 2
        for pkey, plabel in sorted(perms_mod.PERMISSIONS.items()):
            v = tk.BooleanVar(value=(pkey in role.permissions))
            state["perm_vars"][pkey] = v
            ttk.Checkbutton(table_holder, variable=v,
                            text=f"{pkey}  —  {plabel}").grid(
                row=r_idx, column=0, columnspan=2, sticky="w")
            r_idx += 1

    role_combo.bind("<<ComboboxSelected>>", lambda _e: _show_role())

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(6, 4))

    def _save():
        key = role_var.get()
        if not key:
            return
        chosen = {k for k, v in state["perm_vars"].items() if v.get()}
        try:
            perms_mod.set_role_permissions(gui.auth, key, chosen)
        except UserAccountError as e:
            messagebox.showerror("Save", str(e), parent=gui.root)
            return
        messagebox.showinfo("Roles", f"Saved permissions for {key}.",
                              parent=gui.root)
        _reload_roles()
        refresh_all()

    def _new_role():
        new_key = simpledialog.askstring(
            "New role", "Role key (lowercase, no spaces):",
            parent=gui.root)
        if not new_key:
            return
        try:
            perms_mod.create_role(gui.auth, new_key.strip(),
                                     label=new_key.strip().title())
        except UserAccountError as e:
            messagebox.showerror("Roles", str(e), parent=gui.root)
            return
        _reload_roles()

    def _clone_role():
        src = role_var.get()
        if not src:
            return
        new_key = simpledialog.askstring(
            "Clone role", f"New role key (cloning {src}):",
            parent=gui.root)
        if not new_key:
            return
        try:
            perms_mod.clone_role(gui.auth, src, new_key.strip())
        except UserAccountError as e:
            messagebox.showerror("Roles", str(e), parent=gui.root)
            return
        _reload_roles()

    def _rename():
        key = role_var.get()
        if not key:
            return
        new_label = simpledialog.askstring(
            "Rename label", "New display label:",
            parent=gui.root)
        if new_label is None:
            return
        try:
            perms_mod.rename_role(gui.auth, key, new_label=new_label)
        except UserAccountError as e:
            messagebox.showerror("Roles", str(e), parent=gui.root)
            return
        _reload_roles()

    def _delete():
        key = role_var.get()
        if not key:
            return
        if not messagebox.askyesno(
                "Delete role",
                f"Delete custom role {key!r}? (Built-ins cannot be "
                "deleted.)",
                parent=gui.root):
            return
        try:
            perms_mod.delete_role(gui.auth, key)
        except UserAccountError as e:
            messagebox.showerror("Roles", str(e), parent=gui.root)
            return
        _reload_roles()

    ttk.Button(bar, text="Save permissions",
               command=_save).pack(side="left")
    ttk.Button(bar, text="New role…",
               command=_new_role).pack(side="left", padx=(6, 0))
    ttk.Button(bar, text="Clone…",
               command=_clone_role).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Rename label…",
               command=_rename).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Delete custom role",
               command=_delete).pack(side="left", padx=(4, 0))

    # ── Diff sub-pane ──
    diff_left = ttk.Frame(diff_holder)
    diff_left.pack(side="left", fill="both", expand=True)
    ttk.Label(diff_left, text="Compare role:").pack(side="left",
                                                       padx=(0, 4))
    a_var = tk.StringVar()
    a_combo = ttk.Combobox(diff_left, textvariable=a_var,
                             state="readonly", width=20)
    a_combo.pack(side="left", padx=(0, 8))
    ttk.Label(diff_left, text="against:").pack(side="left", padx=(0, 4))
    b_var = tk.StringVar()
    b_combo = ttk.Combobox(diff_left, textvariable=b_var,
                             state="readonly", width=20)
    b_combo.pack(side="left", padx=(0, 8))
    ttk.Button(diff_left, text="Diff",
               command=lambda: _run_diff()).pack(side="left")

    out_text = tk.Text(diff_holder, height=8, wrap="word")
    out_text.pack(fill="x", pady=(6, 0))
    out_text.configure(state="disabled")

    def _run_diff():
        if not a_var.get() or not b_var.get():
            return
        d = perms_mod.diff_roles(gui.auth, a_var.get(), b_var.get())
        lines: list[str] = [f"Only in {a_var.get()}:"]
        lines.extend([f"  + {p}" for p in sorted(d.only_a)]
                     or ["  (none)"])
        lines.append("")
        lines.append(f"Only in {b_var.get()}:")
        lines.extend([f"  + {p}" for p in sorted(d.only_b)]
                     or ["  (none)"])
        lines.append("")
        lines.append(f"Shared: {len(d.shared)} permission(s).")
        out_text.configure(state="normal")
        out_text.delete("1.0", "end")
        out_text.insert("1.0", "\n".join(lines))
        out_text.configure(state="disabled")

    def _populate_diff_combos():
        keys = [r.role_key for r in state["roles"]]
        a_combo['values'] = keys
        b_combo['values'] = keys
        if keys:
            a_combo.current(0)
            b_combo.current(min(1, len(keys) - 1))

    state['_populate_diff_combos'] = _populate_diff_combos
    _reload_roles()
    _populate_diff_combos()

    # Explain panel
    explain_box = ttk.LabelFrame(parent,
                                    text="Why does a user have a permission?",
                                    padding=6)
    explain_box.pack(fill="x", pady=(8, 0))
    ttk.Label(explain_box, text="User id:").pack(side="left", padx=(0, 4))
    uid_var = tk.StringVar()
    ttk.Entry(explain_box, textvariable=uid_var, width=8).pack(side="left",
                                                                  padx=(0, 6))
    ttk.Label(explain_box, text="Permission:").pack(side="left", padx=(0, 4))
    perm_var = tk.StringVar()
    ttk.Combobox(explain_box, textvariable=perm_var, state="readonly",
                  width=28,
                  values=sorted(perms_mod.PERMISSIONS.keys())
                  ).pack(side="left", padx=(0, 6))
    expl_text = tk.Text(parent, height=4, wrap="word")
    expl_text.pack(fill="x", pady=(4, 0))
    expl_text.configure(state="disabled")

    def _explain():
        if not uid_var.get().strip().isdigit() or not perm_var.get():
            return
        t = perms_mod.explain_permission(gui.auth,
                                            int(uid_var.get()),
                                            perm_var.get())
        line = (f"granted={t.granted}, source={t.source}\n"
                 f"{t.detail}")
        expl_text.configure(state="normal")
        expl_text.delete("1.0", "end")
        expl_text.insert("1.0", line)
        expl_text.configure(state="disabled")

    ttk.Button(explain_box, text="Explain",
               command=_explain).pack(side="left")


# ── MFA enforcement (21) ───────────────────────────────────────────

def _build_mfa_policy(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Mark roles that must have MFA enrolled. The list "
                    "below shows users in those roles who haven't "
                    "enrolled yet — chase them or revoke until they "
                    "do."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    pol_frame = ttk.LabelFrame(parent, text="Required-MFA roles",
                                  padding=6)
    pol_frame.pack(fill="x")
    var_map: dict[str, tk.BooleanVar] = {}
    pol = access_policy.mfa_policy(gui.auth)
    for r in perms_mod.list_roles(gui.auth):
        v = tk.BooleanVar(value=pol.get(r.role_key, False))
        var_map[r.role_key] = v
        ttk.Checkbutton(pol_frame, variable=v,
                        text=r.role_key).pack(side="left", padx=4)

    def _save():
        for k, v in var_map.items():
            try:
                access_policy.set_mfa_required(gui.auth, k, v.get())
            except UserAccountError as e:
                messagebox.showerror("MFA policy", str(e),
                                      parent=gui.root)
                return
        _refresh()
        messagebox.showinfo("MFA policy", "Saved.", parent=gui.root)

    ttk.Button(parent, text="Save policy",
               command=_save).pack(anchor="w", pady=(6, 6))

    gaps_frame = ttk.LabelFrame(parent,
                                  text="Users in required-MFA roles "
                                       "without MFA enabled",
                                  padding=6)
    gaps_frame.pack(fill="both", expand=True)

    cols = ("uid", "username", "name", "role")
    tree = ttk.Treeview(gaps_frame, columns=cols, show="headings",
                         height=12)
    for c, lbl, w in [("uid", "User #", 60),
                       ("username", "Username", 160),
                       ("name", "Name", 220),
                       ("role", "Role", 120)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for g in access_policy.mfa_enforcement_gaps(gui.auth):
            tree.insert("", "end", values=(g.user_id, g.username,
                                              g.display_name or "",
                                              g.role or ""))

    ttk.Button(parent, text="Refresh gaps",
               command=_refresh).pack(anchor="w", pady=(4, 0))
    _refresh()


# ── IP rules (22) ──────────────────────────────────────────────────

def _build_ip_rules(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Allow/Deny rules per user or role. Precedence: "
                    "user-deny > user-allow > role-deny > role-allow > "
                    "default-allow. IPv4, CIDR, or wildcards (10.0.0.*)."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    add = ttk.LabelFrame(parent, text="Add rule", padding=6)
    add.pack(fill="x")
    scope_var = tk.StringVar(value="user")
    ttk.Combobox(add, textvariable=scope_var, state="readonly",
                  width=8, values=["user", "role"]
                  ).grid(row=0, column=0, padx=2)
    val_var = tk.StringVar()
    ttk.Entry(add, textvariable=val_var, width=18).grid(
        row=0, column=1, padx=2)
    mode_var = tk.StringVar(value="allow")
    ttk.Combobox(add, textvariable=mode_var, state="readonly",
                  width=8, values=["allow", "deny"]
                  ).grid(row=0, column=2, padx=2)
    pat_var = tk.StringVar()
    ttk.Entry(add, textvariable=pat_var, width=22).grid(
        row=0, column=3, padx=2)
    reason_var = tk.StringVar()
    ttk.Entry(add, textvariable=reason_var, width=24).grid(
        row=0, column=4, padx=2)

    def _add():
        try:
            access_policy.add_ip_rule(
                gui.auth, scope=scope_var.get(),
                scope_value=val_var.get().strip(),
                mode=mode_var.get(),
                pattern=pat_var.get().strip(),
                reason=reason_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("IP rule", str(e), parent=gui.root)
            return
        _refresh()

    ttk.Button(add, text="Add", command=_add).grid(row=0, column=5,
                                                     padx=4)

    cols = ("id", "scope", "value", "mode", "pattern", "reason",
            "set_at")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=12)
    for c, lbl, w in [("id", "ID", 60), ("scope", "Scope", 80),
                       ("value", "Value", 100), ("mode", "Mode", 70),
                       ("pattern", "Pattern", 160),
                       ("reason", "Reason", 200),
                       ("set_at", "Added", 160)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(8, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in access_policy.list_ip_rules(gui.auth):
            tree.insert("", "end", iid=str(r["id"]), values=(
                r["id"], r["scope"], r["scope_value"], r["mode"],
                r["pattern"], r["reason"] or "", r["set_at"]))

    def _delete():
        sel = tree.focus()
        if not sel:
            return
        if not messagebox.askyesno("Delete rule",
                                     f"Delete rule #{sel}?",
                                     parent=gui.root):
            return
        access_policy.remove_ip_rule(gui.auth, int(sel))
        _refresh()

    test_box = ttk.LabelFrame(parent, text="Test an IP", padding=6)
    test_box.pack(fill="x")
    ttk.Label(test_box, text="User id:").pack(side="left")
    test_uid = tk.StringVar()
    ttk.Entry(test_box, textvariable=test_uid, width=8
              ).pack(side="left", padx=(2, 8))
    ttk.Label(test_box, text="IP:").pack(side="left")
    test_ip = tk.StringVar()
    ttk.Entry(test_box, textvariable=test_ip, width=16
              ).pack(side="left", padx=(2, 8))
    result_var = tk.StringVar()
    ttk.Label(test_box, textvariable=result_var,
              foreground="#444").pack(side="left", padx=(8, 0))

    def _test():
        if not test_uid.get().strip().isdigit() or not test_ip.get().strip():
            return
        ok, why = access_policy.check_ip(
            gui.auth, int(test_uid.get()), test_ip.get().strip())
        result_var.set(("ALLOW · " if ok else "DENY · ") + why)

    ttk.Button(test_box, text="Test",
               command=_test).pack(side="left")

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Delete selected",
               command=_delete).pack(side="left")
    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="right")
    _refresh()


# ── JIT access (25, 26) ────────────────────────────────────────────

def _build_jit(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Request a temporary permission grant; an approver "
                    "activates it with a TTL. ‘Sweep expired’ rolls "
                    "back grants whose TTL has passed."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    req = ttk.LabelFrame(parent, text="New request", padding=6)
    req.pack(fill="x")
    ttk.Label(req, text="User id:").grid(row=0, column=0, padx=2)
    u_var = tk.StringVar()
    ttk.Entry(req, textvariable=u_var, width=8).grid(row=0, column=1)
    ttk.Label(req, text="Permission:").grid(row=0, column=2, padx=2)
    p_var = tk.StringVar()
    ttk.Combobox(req, textvariable=p_var, state="readonly", width=28,
                  values=sorted(perms_mod.PERMISSIONS.keys())
                  ).grid(row=0, column=3, padx=2)
    ttk.Label(req, text="Justification:").grid(row=0, column=4, padx=2)
    j_var = tk.StringVar()
    ttk.Entry(req, textvariable=j_var, width=24).grid(row=0, column=5,
                                                          padx=2)

    cols = ("id", "user_id", "permission", "status", "requested_by",
            "requested_at", "approver", "expires_at")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("id", "Req #", 60), ("user_id", "User #", 60),
                       ("permission", "Permission", 200),
                       ("status", "Status", 80),
                       ("requested_by", "Requested by", 120),
                       ("requested_at", "Requested at", 160),
                       ("approver", "Approver", 120),
                       ("expires_at", "Expires", 160)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(6, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in access_policy.list_jit(gui.auth):
            tree.insert("", "end", iid=str(r.request_id), values=(
                r.request_id, r.user_id, r.permission, r.status,
                r.requested_by or "", r.requested_at,
                r.approver or "", r.expires_at or ""))

    def _do_request():
        if not u_var.get().strip().isdigit() or not p_var.get():
            return
        try:
            access_policy.request_jit(
                gui.auth, user_id=int(u_var.get()),
                permission=p_var.get(),
                justification=j_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("JIT", str(e), parent=gui.root)
            return
        _refresh()

    def _approve():
        sel = tree.focus()
        if not sel:
            return
        ttl = simpledialog.askinteger("Approve", "TTL minutes:",
                                         initialvalue=60,
                                         minvalue=1, maxvalue=1440,
                                         parent=gui.root)
        if not ttl:
            return
        try:
            access_policy.approve_jit(gui.auth, int(sel),
                                          ttl_minutes=ttl)
        except UserAccountError as e:
            messagebox.showerror("JIT", str(e), parent=gui.root)
            return
        _refresh()
        refresh_all()

    def _deny():
        sel = tree.focus()
        if not sel:
            return
        try:
            access_policy.deny_jit(gui.auth, int(sel))
        except UserAccountError as e:
            messagebox.showerror("JIT", str(e), parent=gui.root)
            return
        _refresh()

    def _sweep():
        n = access_policy.revoke_expired_jit(gui.auth)
        messagebox.showinfo("JIT sweep",
                              f"Swept {n} expired grant(s).",
                              parent=gui.root)
        _refresh()
        refresh_all()

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 0))
    ttk.Button(bar, text="Submit request",
               command=_do_request).pack(side="left")
    ttk.Button(bar, text="Approve selected…",
               command=_approve).pack(side="left", padx=(6, 0))
    ttk.Button(bar, text="Deny selected",
               command=_deny).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Sweep expired",
               command=_sweep).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="right")
    _refresh()


# ── Sensitive approvers (28) ───────────────────────────────────────

def _build_sensitive(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Two-person rule. A different admin must approve "
                    "Pending requests — the nonce stops accidental "
                    "approvals."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    add = ttk.LabelFrame(parent, text="Open a request", padding=6)
    add.pack(fill="x")
    ttk.Label(add, text="Action:").grid(row=0, column=0, padx=2)
    a_var = tk.StringVar()
    ttk.Combobox(add, textvariable=a_var, state="readonly", width=22,
                  values=sorted(access_policy.SENSITIVE_ACTIONS.keys())
                  ).grid(row=0, column=1, padx=2)
    ttk.Label(add, text="Target user id:").grid(row=0, column=2, padx=2)
    t_var = tk.StringVar()
    ttk.Entry(add, textvariable=t_var, width=8).grid(row=0, column=3,
                                                         padx=2)
    ttk.Label(add, text="Reason:").grid(row=0, column=4, padx=2)
    r_var = tk.StringVar()
    ttk.Entry(add, textvariable=r_var, width=24).grid(row=0, column=5,
                                                          padx=2)

    cols = ("id", "action", "target", "status", "requested_by",
            "approver", "nonce")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=12)
    for c, lbl, w in [("id", "Req #", 60), ("action", "Action", 160),
                       ("target", "Target #", 80),
                       ("status", "Status", 80),
                       ("requested_by", "Requested by", 130),
                       ("approver", "Approver", 130),
                       ("nonce", "Nonce", 180)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(6, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in access_policy.list_sensitive(gui.auth, status=None):
            tree.insert("", "end", iid=str(r.request_id), values=(
                r.request_id, r.action,
                r.target_user_id if r.target_user_id else "",
                r.status, r.requested_by or "",
                r.approver or "", r.nonce))

    def _do_request():
        if not a_var.get():
            return
        try:
            target = int(t_var.get().strip()) if t_var.get().strip() \
                else None
        except ValueError:
            messagebox.showerror("Sensitive",
                                  "Target must be a numeric user-id.",
                                  parent=gui.root)
            return
        try:
            access_policy.request_sensitive(
                gui.auth, action=a_var.get(),
                target_user_id=target,
                reason=r_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Sensitive", str(e), parent=gui.root)
            return
        _refresh()

    def _approve():
        sel = tree.focus()
        if not sel:
            return
        nonce = simpledialog.askstring(
            "Approve sensitive",
            "Enter the request nonce (shown in the table):",
            parent=gui.root)
        if nonce is None:
            return
        try:
            access_policy.decide_sensitive(
                gui.auth, int(sel), approved=True,
                nonce=nonce.strip())
        except UserAccountError as e:
            messagebox.showerror("Sensitive", str(e), parent=gui.root)
            return
        _refresh()
        refresh_all()

    def _deny():
        sel = tree.focus()
        if not sel:
            return
        nonce = simpledialog.askstring(
            "Deny sensitive", "Enter the request nonce:",
            parent=gui.root)
        if nonce is None:
            return
        try:
            access_policy.decide_sensitive(
                gui.auth, int(sel), approved=False,
                nonce=nonce.strip())
        except UserAccountError as e:
            messagebox.showerror("Sensitive", str(e), parent=gui.root)
            return
        _refresh()

    bar = ttk.Frame(parent)
    bar.pack(fill="x")
    ttk.Button(bar, text="Open request",
               command=_do_request).pack(side="left")
    ttk.Button(bar, text="Approve selected…",
               command=_approve).pack(side="left", padx=(6, 0))
    ttk.Button(bar, text="Deny selected…",
               command=_deny).pack(side="left", padx=(4, 0))
    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="right")
    _refresh()


# ── Preview as user (30) ───────────────────────────────────────────

def _build_preview_as_user(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Read-only report of what a given user sees: "
                    "per-system roles, effective permission set, and "
                    "any explicit grants/revokes layered on top."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    row = ttk.Frame(parent)
    row.pack(anchor="w")
    ttk.Label(row, text="User id:").pack(side="left", padx=(0, 4))
    uid_var = tk.StringVar()
    ttk.Entry(row, textvariable=uid_var, width=8).pack(side="left",
                                                          padx=(0, 4))
    ttk.Button(row, text="Preview",
               command=lambda: _run()).pack(side="left", padx=(4, 0))

    out = tk.Text(parent, height=22, wrap="word")
    out.pack(fill="both", expand=True, pady=(6, 0))
    out.configure(state="disabled")

    def _run():
        if not uid_var.get().strip().isdigit():
            return
        try:
            view = access_policy.preview_as_user(
                gui.auth, int(uid_var.get()))
        except UserAccountError as e:
            messagebox.showerror("Preview", str(e), parent=gui.root)
            return
        lines = [
            f"User #{view.user.id} — {view.user.username}",
            f"Display name: {view.user.display_name or ''}",
            f"Active: {view.user.is_active}   "
            f"Locked: {view.user.is_locked}",
            "",
            "Per-system roles:",
        ]
        for sk, role in view.per_system_roles.items():
            lines.append(f"  {sk:>18}: {role or '(no access)'}")
        lines.append("")
        lines.append("Effective permissions by system:")
        for sk, p_set in view.effective_permissions.items():
            lines.append(f"  [{sk}]")
            if not p_set:
                lines.append("    (none)")
            else:
                for p in sorted(p_set):
                    lines.append(f"    • {p}")
        lines.append("")
        lines.append(
            f"Explicit overrides: {len(view.overrides)}")
        for ov in view.overrides:
            lines.append(f"  - {ov['system_key']}/{ov['permission']} "
                          f"= {ov['mode']} (by {ov.get('set_by') or '?'} "
                          f"on {ov.get('set_at')})")
        out.configure(state="normal")
        out.delete("1.0", "end")
        out.insert("1.0", "\n".join(lines))
        out.configure(state="disabled")
