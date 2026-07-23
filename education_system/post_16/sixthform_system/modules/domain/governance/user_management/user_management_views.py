"""GUI panels for the Sixth Form User Management module.

Tabbed view that focuses on roles and access (the user-CRUD lives in
the existing User Accounts window):

  * Summary  — headline counts (active / locked / admins / by role)
  * Access matrix — per-system users + role breakdown
  * Users — full user table with checkboxes for bulk actions
              (grant role, revoke access, activate/deactivate)
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.shared.auth.role_manager import ROLE_HIERARCHY
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import user_management as data
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import lifecycle
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import bulk_io
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import onboarding
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import identity
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import security_ops
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import permissions as perms_mod
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import access_policy
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import audit_monitoring
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import compliance
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import integrations as integ
from education_system.post_16.sixthform_system.modules.shared import user_accounts as ua_data
from education_system.post_16.sixthform_system.modules.shared.user_accounts import (
    DEFAULT_ROLE,
    SYSTEM_KEY,
    UserAccountError,
    UserRow,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def open_user_management_window(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "User Management")

    if not getattr(gui, "auth", None):
        ttk.Label(frame, text="No active session — cannot load users.",
                  foreground="#a33").pack(anchor="w")
        return

    # ── Quick search bar (#48) — always visible. ──
    qs = ttk.Frame(frame)
    qs.pack(fill="x", pady=(0, 6))
    ttk.Label(qs, text="🔎 Quick search:").pack(side="left",
                                                   padx=(0, 4))
    qs_var = tk.StringVar()
    qs_entry = ttk.Entry(qs, textvariable=qs_var, width=40)
    qs_entry.pack(side="left", padx=(0, 4))
    qs_result_var = tk.StringVar()
    ttk.Label(qs, textvariable=qs_result_var,
              foreground="#444").pack(side="left", padx=(8, 0))

    def _do_quick_search(_e=None):
        rows = integ.quick_search(gui.auth, qs_var.get(), limit=15)
        if not rows:
            qs_result_var.set("(no matches)")
            return
        names = ", ".join(
            f"#{r['id']} {r['username']}"
            + (f" ({r['display_name']})" if r['display_name'] else "")
            for r in rows[:5])
        suffix = f" …+{len(rows) - 5} more" if len(rows) > 5 else ""
        qs_result_var.set(names + suffix)

    qs_entry.bind("<Return>", _do_quick_search)
    ttk.Button(qs, text="Find",
               command=_do_quick_search).pack(side="left", padx=(4, 0))

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    summary_tab = ttk.Frame(nb, padding=8)
    matrix_tab = ttk.Frame(nb, padding=8)
    users_tab = ttk.Frame(nb, padding=8)
    archived_tab = ttk.Frame(nb, padding=8)
    bulk_tab = ttk.Frame(nb, padding=8)
    security_tab = ttk.Frame(nb, padding=8)
    policy_tab = ttk.Frame(nb, padding=8)
    monitoring_tab = ttk.Frame(nb, padding=8)
    compliance_tab = ttk.Frame(nb, padding=8)
    integ_tab = ttk.Frame(nb, padding=8)
    nb.add(summary_tab, text="Summary")
    nb.add(matrix_tab,  text="Access matrix")
    nb.add(users_tab,   text="Users & bulk actions")
    nb.add(archived_tab, text="Archived")
    nb.add(bulk_tab,    text="Bulk & onboarding")
    nb.add(security_tab, text="Security")
    nb.add(policy_tab,  text="Access policy")
    nb.add(monitoring_tab, text="Monitoring")
    nb.add(compliance_tab, text="Compliance")
    nb.add(integ_tab, text="Integrations")

    state: dict[str, Any] = {
        "refresh_summary": None,
        "refresh_matrix":  None,
        "refresh_users":   None,
        "refresh_archived": None,
    }

    def refresh_all() -> None:
        for k in ("refresh_summary", "refresh_matrix",
                  "refresh_users", "refresh_archived"):
            if state[k]:
                state[k]()

    _build_summary_tab(gui, summary_tab, state)
    _build_matrix_tab(gui, matrix_tab, state)
    _build_users_tab(gui, users_tab, state, refresh_all)
    _build_archived_tab(gui, archived_tab, state, refresh_all)
    _build_bulk_tab(gui, bulk_tab, refresh_all)
    _build_security_tab(gui, security_tab, refresh_all)
    _build_policy_tab(gui, policy_tab, refresh_all)
    _build_monitoring_tab(gui, monitoring_tab)
    _build_compliance_tab(gui, compliance_tab, refresh_all)
    _build_integrations_tab(gui, integ_tab, refresh_all)


# ── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame, state: dict) -> None:
    tiles = ttk.Frame(parent)
    tiles.pack(anchor="w", fill="x", pady=(0, 12))

    total_var = tk.StringVar(value="—")
    sixth_var = tk.StringVar(value="—")
    active_var = tk.StringVar(value="—")
    locked_var = tk.StringVar(value="—")
    admins_var = tk.StringVar(value="—")
    recent_var = tk.StringVar(value="—")

    def _tile(col: int, label: str, var: tk.StringVar,
               hint: str, fg: str = "#222") -> None:
        tile = ttk.LabelFrame(tiles, padding=10)
        tile.grid(row=0, column=col, padx=4, sticky="nsew")
        tiles.columnconfigure(col, weight=1, uniform="t")
        ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(tile, textvariable=var, font=("", 20, "bold"),
                   foreground=fg).pack(anchor="w", pady=(2, 0))
        ttk.Label(tile, text=hint, foreground="#888",
                   font=("", 9)).pack(anchor="w")

    _tile(0, "Total users",   total_var, "Across all systems")
    _tile(1, "Sixth-form",    sixth_var, "Have college access")
    _tile(2, "Active",        active_var, "is_active = true")
    _tile(3, "Locked",        locked_var, "Currently locked", fg="#a33")
    _tile(4, "Admins",        admins_var, "Sixth-form admins")
    _tile(5, "Logins (7d)",   recent_var, "Last 7 days")

    roles_frame = ttk.LabelFrame(parent, text="Sixth-form role distribution",
                                   padding=6)
    roles_frame.pack(fill="both", expand=True, pady=(4, 0))
    role_tree = ttk.Treeview(roles_frame, columns=("role", "count"),
                                show="headings", height=8)
    role_tree.heading("role", text="Role")
    role_tree.heading("count", text="Users")
    role_tree.column("role", width=240, anchor="w")
    role_tree.column("count", width=80, anchor="e")
    role_tree.pack(fill="both", expand=True)

    def refresh() -> None:
        try:
            snap = data.snapshot(gui.auth)
        except Exception as e:
            logger.exception("snapshot failed")
            messagebox.showerror("Error", f"Could not load: {e}",
                                  parent=gui.root)
            return
        s = snap.summary
        total_var.set(str(s.total))
        sixth_var.set(str(s.sixth_form_users))
        active_var.set(str(s.active))
        locked_var.set(str(s.locked))
        admins_var.set(str(snap.admins))
        recent_var.set(str(s.recent_logins_7d))
        for child in role_tree.get_children():
            role_tree.delete(child)
        for role in sorted(ROLE_HIERARCHY.keys(),
                             key=lambda r: -ROLE_HIERARCHY[r]):
            role_tree.insert(
                "", "end",
                values=(role, snap.role_distribution_sixthform.get(role, 0)))
        gui.status_var.set("User management summary refreshed")

    ttk.Button(parent, text="Refresh", command=refresh
                ).pack(anchor="w", pady=(8, 0))
    state["refresh_summary"] = refresh
    refresh()


# ── Access-matrix tab ──────────────────────────────────────────────

def _build_matrix_tab(gui, parent: ttk.Frame, state: dict) -> None:
    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)

    footer = ttk.Label(parent, text="", foreground="#555")
    footer.pack(anchor="w", pady=(6, 0))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        try:
            m = data.access_matrix(gui.auth)
        except Exception as e:
            logger.exception("access matrix failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("system", "users", "roles")
        tree = ttk.Treeview(table_holder, columns=cols,
                              show="headings", height=12)
        tree.heading("system", text="System")
        tree.heading("users",  text="Users")
        tree.heading("roles",  text="Role breakdown")
        tree.column("system", width=140, anchor="w")
        tree.column("users",  width=80,  anchor="e")
        tree.column("roles",  width=520, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for s in m.systems:
            breakdown = ", ".join(
                f"{r}:{n}" for r, n in sorted(s.by_role.items(),
                                                key=lambda kv: -kv[1]))
            tree.insert("", "end", values=(s.system_key, s.users, breakdown))
        footer.configure(
            text=(f"{len(m.systems)} system(s). "
                  f"Users without sixth-form access: "
                  f"{len(m.users_without_sixthform)}"))
        gui.status_var.set("Access matrix refreshed")

    ttk.Button(parent, text="Refresh", command=refresh
                ).pack(anchor="w", pady=(8, 0))
    state["refresh_matrix"] = refresh
    refresh()


# ── Users + bulk-action tab ────────────────────────────────────────

def _build_users_tab(gui, parent: ttk.Frame, state: dict,
                       refresh_all) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    query_var = tk.StringVar()
    scope_var = tk.StringVar(value="All")

    ttk.Label(filt, text="Scope:").pack(side="left")
    ttk.Combobox(filt, textvariable=scope_var, state="readonly", width=22,
                  values=["All", "Sixth-form only",
                           "Without sixth-form access",
                           "Locked", "Inactive", "Admins (sixth-form)"]
                  ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=query_var, width=22
              ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True, pady=(4, 4))
    footer = ttk.Label(parent, text="", foreground="#555")
    footer.pack(anchor="w")

    # Selection store (user_id → bool). Persists across re-renders.
    selection: dict[int, bool] = {}

    bulk_bar = ttk.LabelFrame(parent, text="Bulk actions on selected users",
                                padding=8)
    bulk_bar.pack(fill="x", pady=(8, 0))

    role_var = tk.StringVar(value=DEFAULT_ROLE)
    ttk.Label(bulk_bar, text="Role:").pack(side="left")
    ttk.Combobox(bulk_bar, textvariable=role_var, state="readonly",
                  values=list(ROLE_HIERARCHY.keys()), width=18
                  ).pack(side="left", padx=(4, 12))

    def _selected_ids() -> list[int]:
        return [uid for uid, on in selection.items() if on]

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        try:
            scope = scope_var.get()
            if scope == "Sixth-form only":
                rows = ua_data.list_users(gui.auth, system_key=SYSTEM_KEY)
            elif scope == "Without sixth-form access":
                rows = data.list_without_access(gui.auth)
            elif scope == "Locked":
                rows = data.list_locked(gui.auth)
            elif scope == "Inactive":
                rows = data.list_inactive(gui.auth)
            elif scope == "Admins (sixth-form)":
                rows = data.list_admins(gui.auth)
            else:
                rows = ua_data.list_users(gui.auth)
            q = query_var.get().strip().lower()
            if q:
                rows = [
                    u for u in rows
                    if q in (u.username or "").lower()
                    or q in (u.display_name or "").lower()
                    or q in (u.email or "").lower()
                ]
        except Exception as e:
            logger.exception("list users failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        # Keep selection in sync with what's visible.
        visible_ids = {u.id for u in rows}
        for uid in list(selection.keys()):
            if uid not in visible_ids:
                selection.pop(uid, None)
        for u in rows:
            selection.setdefault(u.id, False)

        cols = ("sel", "id", "username", "display", "sixthform",
                "active", "locked")
        headings = {
            "sel":       ("✓",        40),
            "id":        ("ID",       50),
            "username":  ("Username", 150),
            "display":   ("Display",  200),
            "sixthform": ("Sixth-form role", 130),
            "active":    ("Active",   60),
            "locked":    ("Locked",   60),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings",
                             height=14, selectmode="none")
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        def _ch(u: UserRow) -> str:
            return "☑" if selection.get(u.id) else "☐"

        for u in rows:
            tree.insert("", "end", iid=str(u.id), values=(
                _ch(u), u.id, u.username, u.display_name or "",
                u.role_for(SYSTEM_KEY) or "—",
                "yes" if u.is_active else "no",
                "yes" if u.is_locked else "no",
            ))

        def _toggle(event) -> None:
            iid = tree.identify_row(event.y)
            if not iid:
                return
            col = tree.identify_column(event.x)
            uid = int(iid)
            # Click in the checkbox column flips selection; clicks
            # elsewhere also toggle, since that's the only meaningful
            # action on this view.
            selection[uid] = not selection.get(uid, False)
            tree.set(iid, "sel", "☑" if selection[uid] else "☐")
            _update_footer(rows)

        tree.bind("<Button-1>", _toggle)
        _update_footer(rows)

    def _update_footer(rows: list[UserRow]) -> None:
        chosen = len(_selected_ids())
        footer.configure(text=f"{len(rows)} user(s) · {chosen} selected")
        gui.status_var.set(f"User Management: {chosen} selected / "
                            f"{len(rows)} match(es)")

    def _do_grant() -> None:
        ids = _selected_ids()
        if not ids:
            messagebox.showinfo("Nothing selected", "Tick users first.",
                                  parent=gui.root)
            return
        role = role_var.get()
        if role not in ROLE_HIERARCHY:
            messagebox.showerror("Bad role", "Pick a valid role.",
                                  parent=gui.root)
            return
        if not messagebox.askyesno(
                "Grant role",
                f"Grant '{role}' on '{SYSTEM_KEY}' to {len(ids)} user(s)?",
                parent=gui.root):
            return
        try:
            result = data.bulk_grant(gui.auth, ids, SYSTEM_KEY, role)
        except Exception as e:
            logger.exception("bulk_grant crashed")
            messagebox.showerror("Error", str(e), parent=gui.root)
            return
        msg = (f"Granted '{role}' to {len(result.succeeded)} user(s)."
                + (f"\n{len(result.failed)} failed."
                    if result.failed else ""))
        messagebox.showinfo("Bulk grant", msg, parent=gui.root)
        refresh_all()

    def _do_revoke() -> None:
        ids = _selected_ids()
        if not ids:
            messagebox.showinfo("Nothing selected", "Tick users first.",
                                  parent=gui.root)
            return
        if not messagebox.askyesno(
                "Revoke access",
                f"Revoke '{SYSTEM_KEY}' access for {len(ids)} user(s)?",
                parent=gui.root):
            return
        try:
            result = data.bulk_revoke(gui.auth, ids, SYSTEM_KEY)
        except Exception as e:
            logger.exception("bulk_revoke crashed")
            messagebox.showerror("Error", str(e), parent=gui.root)
            return
        msg = (f"Revoked for {len(result.succeeded)} user(s)."
                + (f"\n{len(result.failed)} failed."
                    if result.failed else ""))
        messagebox.showinfo("Bulk revoke", msg, parent=gui.root)
        refresh_all()

    def _set_active(active: bool) -> None:
        ids = _selected_ids()
        if not ids:
            messagebox.showinfo("Nothing selected", "Tick users first.",
                                  parent=gui.root)
            return
        verb = "Activate" if active else "Deactivate"
        if not messagebox.askyesno(
                f"{verb} users",
                f"{verb} {len(ids)} user(s)?", parent=gui.root):
            return
        try:
            result = data.bulk_set_active(gui.auth, ids, active)
        except Exception as e:
            logger.exception("bulk_set_active crashed")
            messagebox.showerror("Error", str(e), parent=gui.root)
            return
        messagebox.showinfo(
            f"{verb}d",
            (f"{verb}d {len(result.succeeded)} user(s)."
              + (f"\n{len(result.failed)} failed."
                  if result.failed else "")),
            parent=gui.root)
        refresh_all()

    ttk.Button(filt, text="Apply", command=refresh
                ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear selection",
                command=lambda: (selection.clear(), refresh())
                ).pack(side="left", padx=(4, 0))

    ttk.Button(bulk_bar, text="Grant role to selected",
                command=_do_grant
                ).pack(side="left", padx=(0, 6))
    ttk.Button(bulk_bar, text="Revoke sixth-form access",
                command=_do_revoke
                ).pack(side="left", padx=(0, 12))
    ttk.Button(bulk_bar, text="Activate selected",
                command=lambda: _set_active(True)
                ).pack(side="left", padx=(0, 6))
    ttk.Button(bulk_bar, text="Deactivate selected",
                command=lambda: _set_active(False)
                ).pack(side="left", padx=(0, 6))

    # ── Lifecycle (single-user actions) ──
    life_bar = ttk.LabelFrame(parent,
                                text="Lifecycle (single-user actions)",
                                padding=8)
    life_bar.pack(fill="x", pady=(8, 0))

    def _one_selected_or_none() -> int | None:
        ids = _selected_ids()
        if len(ids) != 1:
            messagebox.showinfo(
                "Pick one user",
                "Tick exactly one user for this action.",
                parent=gui.root)
            return None
        return ids[0]

    def _do_create() -> None:
        if _open_user_form(gui, auth=gui.auth, user_id=None):
            refresh_all()

    def _do_edit() -> None:
        uid = _one_selected_or_none()
        if uid is None:
            return
        if _open_user_form(gui, auth=gui.auth, user_id=uid):
            refresh_all()

    def _do_archive() -> None:
        uid = _one_selected_or_none()
        if uid is None:
            return
        if _open_archive_form(gui, auth=gui.auth, user_id=uid):
            refresh_all()

    ttk.Button(life_bar, text="Create user…",
                command=_do_create
                ).pack(side="left", padx=(0, 6))
    ttk.Button(life_bar, text="Edit selected…",
                command=_do_edit
                ).pack(side="left", padx=(0, 6))
    ttk.Button(life_bar, text="Archive selected…",
                command=_do_archive
                ).pack(side="left", padx=(0, 6))

    def _do_suspend() -> None:
        uid = _one_selected_or_none()
        if uid is None:
            return
        if _open_suspend_form(gui, auth=gui.auth, user_id=uid):
            refresh_all()

    def _do_unsuspend() -> None:
        uid = _one_selected_or_none()
        if uid is None:
            return
        if not messagebox.askyesno(
                "Unsuspend",
                f"End the active suspension for user #{uid}?",
                parent=gui.root):
            return
        try:
            lifecycle.unsuspend_user(gui.auth, uid)
        except UserAccountError as e:
            messagebox.showerror("Unsuspend", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("unsuspend crashed")
            messagebox.showerror("Unsuspend", f"Unexpected: {e}",
                                  parent=gui.root)
            return
        refresh_all()

    def _do_offboard() -> None:
        uid = _one_selected_or_none()
        if uid is None:
            return
        if _open_offboard_form(gui, auth=gui.auth, user_id=uid):
            refresh_all()

    ttk.Button(life_bar, text="Suspend…",
                command=_do_suspend
                ).pack(side="left", padx=(0, 6))
    ttk.Button(life_bar, text="Unsuspend",
                command=_do_unsuspend
                ).pack(side="left", padx=(0, 6))
    ttk.Button(life_bar, text="Offboard…",
                command=_do_offboard
                ).pack(side="left", padx=(0, 6))

    def _do_rename() -> None:
        uid = _one_selected_or_none()
        if uid is None:
            return
        if _open_rename_form(gui, auth=gui.auth, user_id=uid):
            refresh_all()

    def _do_merge() -> None:
        ids = _selected_ids()
        if len(ids) != 2:
            messagebox.showinfo("Pick two", "Tick exactly two users "
                                              "to merge.",
                                  parent=gui.root)
            return
        if _open_merge_form(gui, auth=gui.auth, ids=ids):
            refresh_all()

    ttk.Button(life_bar, text="Rename…",
                command=_do_rename
                ).pack(side="left", padx=(0, 6))
    ttk.Button(life_bar, text="Merge two…",
                command=_do_merge
                ).pack(side="left", padx=(0, 6))
    ttk.Label(life_bar,
              text="Restore / permanent-delete on ‘Archived’; bulk + "
                   "onboarding on ‘Bulk & onboarding’; sessions / MFA "
                   "/ failed-logins / breach list on ‘Security’.",
              foreground="#666",
              wraplength=480).pack(side="left", padx=(12, 0))

    state["refresh_users"] = refresh
    refresh()


# ── Archived tab ───────────────────────────────────────────────────

def _build_archived_tab(gui, parent: ttk.Frame, state: dict,
                          refresh_all) -> None:
    info = ttk.Label(
        parent,
        text=("Soft-deleted users. Restore re-activates the account "
              "while the retention window is open. Permanent delete "
              "is irreversible — closes the lifecycle and writes an "
              "immutable audit row."),
        wraplength=820, foreground="#555", justify="left")
    info.pack(anchor="w", pady=(0, 8))

    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 6))
    include_restored = tk.BooleanVar(value=False)
    include_purged = tk.BooleanVar(value=False)
    ttk.Checkbutton(filt, text="Show restored",
                    variable=include_restored,
                    command=lambda: refresh()).pack(side="left")
    ttk.Checkbutton(filt, text="Show purged",
                    variable=include_purged,
                    command=lambda: refresh()).pack(side="left",
                                                     padx=(8, 0))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    footer = ttk.Label(parent, text="", foreground="#555")
    footer.pack(anchor="w", pady=(2, 6))

    cols = ("archive_id", "user_id", "username", "archived_at",
            "archived_by", "retention_until", "status", "reason")
    headings = {
        "archive_id":      ("Archive #", 80),
        "user_id":         ("User #",    60),
        "username":        ("Username",  150),
        "archived_at":     ("Archived",  150),
        "archived_by":     ("By",        120),
        "retention_until": ("Retention until", 150),
        "status":          ("Status",    80),
        "reason":          ("Reason",    320),
    }

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        try:
            rows = lifecycle.list_archived(
                gui.auth,
                include_restored=include_restored.get(),
                include_purged=include_purged.get(),
            )
        except Exception as e:
            logger.exception("list_archived failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            footer.configure(text="")
            return

        tree = ttk.Treeview(table_holder, columns=cols, show="headings",
                             height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for r in rows:
            snap = r.snapshot or {}
            tree.insert("", "end", iid=str(r.archive_id), values=(
                r.archive_id, r.user_id,
                snap.get("username", "?"),
                r.archived_at, r.archived_by or "",
                r.retention_until or "—",
                r.status, r.reason or "",
            ))
        footer.configure(text=f"{len(rows)} archive row(s).")

        def _selected_row():
            sel = tree.focus()
            if not sel:
                return None
            try:
                aid = int(sel)
            except ValueError:
                return None
            for r in rows:
                if r.archive_id == aid:
                    return r
            return None

        def _do_restore():
            r = _selected_row()
            if r is None:
                messagebox.showinfo("Pick a row",
                                      "Select an archive row first.",
                                      parent=gui.root)
                return
            if r.status != 'Archived':
                messagebox.showwarning("Cannot restore",
                                        f"Row is {r.status!r}.",
                                        parent=gui.root)
                return
            if not messagebox.askyesno(
                    "Restore user",
                    f"Restore archive #{r.archive_id} "
                    f"(user {r.snapshot.get('username','?')})?",
                    parent=gui.root):
                return
            try:
                lifecycle.restore_user(gui.auth, r.archive_id)
            except UserAccountError as e:
                messagebox.showerror("Restore", str(e),
                                      parent=gui.root)
                return
            except Exception as e:
                logger.exception("restore_user crashed")
                messagebox.showerror("Restore", f"Unexpected: {e}",
                                      parent=gui.root)
                return
            messagebox.showinfo("Restore", "User restored.",
                                  parent=gui.root)
            refresh_all()

        def _do_purge():
            r = _selected_row()
            if r is None:
                messagebox.showinfo("Pick a row",
                                      "Select an archive row first.",
                                      parent=gui.root)
                return
            _open_purge_dialog(gui, auth=gui.auth, archive=r,
                                on_done=refresh_all)

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(4, 0))
        ttk.Button(bar, text="Restore selected",
                   command=_do_restore).pack(side="left")
        ttk.Button(bar, text="Permanent delete…",
                   command=_do_purge).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Refresh",
                   command=refresh).pack(side="right")

    state["refresh_archived"] = refresh
    refresh()


# ── Create / Edit user dialog ──────────────────────────────────────

def _open_user_form(gui, *, auth, user_id: int | None) -> bool:
    """Modal dialog. Returns True on save, False on cancel/error."""
    is_edit = user_id is not None
    title = "Edit user" if is_edit else "Create user"

    # Load existing values for edit mode.
    initial = {}
    if is_edit:
        u = ua_data.get_user(auth, user_id)
        if u is None:
            messagebox.showerror(title, f"No user #{user_id}",
                                  parent=gui.root)
            return False
        extras = lifecycle.get_extras(auth, user_id)
        initial = {
            "username": u.username,
            "display_name": u.display_name or "",
            "email": u.email or "",
            "role": u.role_for(SYSTEM_KEY) or DEFAULT_ROLE,
            "phone": extras.phone or "",
            "department": extras.department or "",
            "job_title": extras.job_title or "",
            "line_manager_id": (str(extras.line_manager_id)
                                 if extras.line_manager_id else ""),
            "notes": extras.notes or "",
        }

    dlg = tk.Toplevel(gui.root)
    dlg.title(title)
    dlg.geometry("520x520")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    row_idx = 0

    def _row(label: str, widget: tk.Widget) -> None:
        nonlocal row_idx
        ttk.Label(body, text=label).grid(row=row_idx, column=0, sticky="e",
                                            padx=(0, 8), pady=3)
        widget.grid(row=row_idx, column=1, sticky="ew", pady=3)
        row_idx += 1

    username_var = tk.StringVar(value=initial.get("username", ""))
    username_entry = ttk.Entry(body, textvariable=username_var, width=40)
    if is_edit:
        username_entry.configure(state="readonly")
    _row("Username *", username_entry)

    password_var = tk.StringVar()
    if not is_edit:
        _row("Password *",
             ttk.Entry(body, textvariable=password_var, show="*", width=40))

    display_var = tk.StringVar(value=initial.get("display_name", ""))
    _row("Display name", ttk.Entry(body, textvariable=display_var,
                                      width=40))

    email_var = tk.StringVar(value=initial.get("email", ""))
    _row("Email", ttk.Entry(body, textvariable=email_var, width=40))

    role_var = tk.StringVar(value=initial.get("role", DEFAULT_ROLE))
    if not is_edit:
        _row("Sixth-form role",
             ttk.Combobox(body, textvariable=role_var, state="readonly",
                          values=list(ROLE_HIERARCHY.keys()), width=38))

    phone_var = tk.StringVar(value=initial.get("phone", ""))
    _row("Phone", ttk.Entry(body, textvariable=phone_var, width=40))

    dept_var = tk.StringVar(value=initial.get("department", ""))
    _row("Department", ttk.Entry(body, textvariable=dept_var, width=40))

    title_var = tk.StringVar(value=initial.get("job_title", ""))
    _row("Job title", ttk.Entry(body, textvariable=title_var, width=40))

    mgr_var = tk.StringVar(value=initial.get("line_manager_id", ""))
    _row("Line manager user-id (optional)",
         ttk.Entry(body, textvariable=mgr_var, width=40))

    ttk.Label(body, text="Notes").grid(row=row_idx, column=0,
                                          sticky="ne", padx=(0, 8), pady=3)
    notes_text = tk.Text(body, height=4, width=40)
    if initial.get("notes"):
        notes_text.insert("1.0", initial["notes"])
    notes_text.grid(row=row_idx, column=1, sticky="ew", pady=3)
    row_idx += 1

    saved = {"ok": False}

    def _gather():
        try:
            mgr = int(mgr_var.get().strip()) if mgr_var.get().strip() else None
        except ValueError:
            raise UserAccountError("Line manager id must be a number.")
        return {
            "username": username_var.get().strip(),
            "password": password_var.get(),
            "display_name": display_var.get().strip() or None,
            "email": email_var.get().strip() or None,
            "role": role_var.get() or DEFAULT_ROLE,
            "phone": phone_var.get(),
            "department": dept_var.get(),
            "job_title": title_var.get(),
            "line_manager_id": mgr,
            "notes": notes_text.get("1.0", "end").strip() or None,
        }

    def _save():
        try:
            fields = _gather()
        except UserAccountError as e:
            messagebox.showerror(title, str(e), parent=dlg)
            return
        try:
            if is_edit:
                lifecycle.update_user_full(
                    auth, user_id,
                    display_name=fields["display_name"],
                    email=fields["email"],
                    phone=fields["phone"],
                    department=fields["department"],
                    job_title=fields["job_title"],
                    line_manager_id=fields["line_manager_id"],
                    notes=fields["notes"])
            else:
                if not fields["username"] or not fields["password"]:
                    raise UserAccountError(
                        "Username and password are required.")
                lifecycle.create_user_full(
                    auth, username=fields["username"],
                    password=fields["password"],
                    display_name=fields["display_name"],
                    email=fields["email"], role=fields["role"],
                    phone=fields["phone"],
                    department=fields["department"],
                    job_title=fields["job_title"],
                    line_manager_id=fields["line_manager_id"],
                    notes=fields["notes"])
        except UserAccountError as e:
            messagebox.showerror(title, str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("%s crashed", title)
            messagebox.showerror(title, f"Unexpected: {e}", parent=dlg)
            return
        saved["ok"] = True
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=row_idx, column=0, columnspan=2, sticky="e",
              pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return saved["ok"]


# ── Archive dialog ─────────────────────────────────────────────────

def _open_archive_form(gui, *, auth, user_id: int) -> bool:
    u = ua_data.get_user(auth, user_id)
    if u is None:
        messagebox.showerror("Archive", f"No user #{user_id}",
                              parent=gui.root)
        return False

    dlg = tk.Toplevel(gui.root)
    dlg.title("Archive user")
    dlg.geometry("440x240")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"User: {u.username} (#{u.id})").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

    ttk.Label(body, text="Reason:").grid(row=1, column=0, sticky="e",
                                            padx=(0, 8))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40).grid(
        row=1, column=1, sticky="ew")

    ttk.Label(body, text="Retention (days):").grid(row=2, column=0,
                                                      sticky="e", padx=(0, 8))
    retention_var = tk.IntVar(value=lifecycle.DEFAULT_RETENTION_DAYS)
    ttk.Spinbox(body, from_=1, to=3650, textvariable=retention_var,
                width=10).grid(row=2, column=1, sticky="w")

    ttk.Label(body, text="Archiving disables login. Restore is possible "
                          "until retention expires.",
              foreground="#666", wraplength=380).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    ok = {"ok": False}

    def _go():
        try:
            lifecycle.archive_user(auth, user_id,
                                     reason=reason_var.get(),
                                     retention_days=retention_var.get())
        except UserAccountError as e:
            messagebox.showerror("Archive", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("archive_user crashed")
            messagebox.showerror("Archive", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Archive",
               command=_go).pack(side="right")

    dlg.wait_window()
    return ok["ok"]


# ── Permanent-delete dialog (two-step) ─────────────────────────────

def _open_purge_dialog(gui, *, auth, archive, on_done) -> None:
    username = archive.snapshot.get("username", "")
    if not messagebox.askyesno(
            "Permanent delete",
            f"This permanently deletes user '{username}' "
            f"(#{archive.user_id}) and cannot be undone.\n\n"
            "Proceed to the confirmation step?",
            parent=gui.root):
        return

    dlg = tk.Toplevel(gui.root)
    dlg.title("Permanent delete — confirmation")
    dlg.geometry("420x220")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)

    ttk.Label(body, text=f"Type the username '{username}' to confirm.",
              wraplength=380).pack(anchor="w", pady=(0, 6))
    confirm_var = tk.StringVar()
    ttk.Entry(body, textvariable=confirm_var, width=40
              ).pack(anchor="w", pady=(0, 6))
    ttk.Label(body, text="Reason (optional):").pack(anchor="w")
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40
              ).pack(anchor="w")

    def _go():
        try:
            ok = lifecycle.purge_user(
                auth, archive.user_id,
                reason=reason_var.get().strip() or None,
                confirmation_token=confirm_var.get())
        except UserAccountError as e:
            messagebox.showerror("Permanent delete", str(e),
                                  parent=dlg)
            return
        except Exception as e:
            logger.exception("purge_user crashed")
            messagebox.showerror("Permanent delete",
                                  f"Unexpected: {e}", parent=dlg)
            return
        if not ok:
            messagebox.showerror("Permanent delete",
                                  "Delete returned without success.",
                                  parent=dlg)
            return
        messagebox.showinfo("Permanent delete",
                              f"User '{username}' permanently deleted.",
                              parent=gui.root)
        dlg.destroy()
        on_done()

    bar = ttk.Frame(body)
    bar.pack(fill="x", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Permanently delete",
               command=_go).pack(side="right")


# ── Suspend dialog ─────────────────────────────────────────────────

def _open_suspend_form(gui, *, auth, user_id: int) -> bool:
    u = ua_data.get_user(auth, user_id)
    if u is None:
        messagebox.showerror("Suspend", f"No user #{user_id}",
                              parent=gui.root)
        return False

    dlg = tk.Toplevel(gui.root)
    dlg.title("Suspend user")
    dlg.geometry("440x240")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"User: {u.username} (#{u.id})").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

    ttk.Label(body, text="Reason:").grid(row=1, column=0, sticky="e",
                                            padx=(0, 8))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40
              ).grid(row=1, column=1, sticky="ew")

    ttk.Label(body, text="Auto-resume on (YYYY-MM-DD, optional):").grid(
        row=2, column=0, sticky="e", padx=(0, 8))
    resume_var = tk.StringVar()
    ttk.Entry(body, textvariable=resume_var, width=20).grid(
        row=2, column=1, sticky="w")

    ttk.Label(body,
              text=("Suspension disables the login. Auto-resume is "
                    "informational only — Unsuspend manually when "
                    "ready."),
              foreground="#666", wraplength=380).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    ok = {"ok": False}

    def _go():
        try:
            lifecycle.suspend_user(
                auth, user_id,
                reason=reason_var.get(),
                resume_at=resume_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Suspend", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("suspend crashed")
            messagebox.showerror("Suspend", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=4, column=0, columnspan=2, sticky="e",
              pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Suspend",
               command=_go).pack(side="right")
    dlg.wait_window()
    return ok["ok"]


# ── Offboard dialog ────────────────────────────────────────────────

def _open_offboard_form(gui, *, auth, user_id: int) -> bool:
    u = ua_data.get_user(auth, user_id)
    if u is None:
        messagebox.showerror("Offboard", f"No user #{user_id}",
                              parent=gui.root)
        return False

    dlg = tk.Toplevel(gui.root)
    dlg.title("Offboard user")
    dlg.geometry("520x320")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"Offboarding user: {u.username} (#{u.id})",
              font=("", 11, "bold")).grid(row=0, column=0, columnspan=2,
                                            sticky="w", pady=(0, 8))
    ttk.Label(body, text=("This is a single-action workflow: rotate "
                            "password (invalidates sessions), record a "
                            "reassignment plan, then archive."),
              foreground="#666", wraplength=480).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

    ttk.Label(body, text="Reason:").grid(row=2, column=0, sticky="e",
                                            padx=(0, 8))
    reason_var = tk.StringVar(value="Offboarding")
    ttk.Entry(body, textvariable=reason_var, width=46).grid(
        row=2, column=1, sticky="ew")

    ttk.Label(body, text="Retention (days):").grid(row=3, column=0,
                                                      sticky="e", padx=(0, 8))
    ret_var = tk.IntVar(value=lifecycle.DEFAULT_RETENTION_DAYS)
    ttk.Spinbox(body, from_=1, to=3650, textvariable=ret_var,
                width=10).grid(row=3, column=1, sticky="w")

    ttk.Label(body, text="Reassign owned records to user-id "
                          "(optional):").grid(
        row=4, column=0, sticky="e", padx=(0, 8))
    reassign_var = tk.StringVar()
    ttk.Entry(body, textvariable=reassign_var, width=14).grid(
        row=4, column=1, sticky="w")

    ok = {"ok": False}

    def _go():
        try:
            r_id = (int(reassign_var.get().strip())
                    if reassign_var.get().strip() else None)
        except ValueError:
            messagebox.showerror("Offboard",
                                  "Reassign id must be a number.",
                                  parent=dlg)
            return
        try:
            result = lifecycle.offboard_user(
                auth, user_id,
                reason=reason_var.get(),
                retention_days=ret_var.get(),
                reassign_to_user_id=r_id)
        except UserAccountError as e:
            messagebox.showerror("Offboard", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("offboard crashed")
            messagebox.showerror("Offboard", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()
        messagebox.showinfo(
            "Offboard",
            (f"Offboarded user #{user_id}.\n"
             f"  Archive #{result.archive_id}\n"
             f"  Sessions invalidated: "
             f"{'yes' if result.sessions_invalidated else 'no'}\n\n"
             "Reassignment plan logged. Per-domain re-owners "
             "still need to be run for any records owned by this "
             "user."),
            parent=gui.root)

    bar = ttk.Frame(body)
    bar.grid(row=5, column=0, columnspan=2, sticky="e",
              pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Offboard",
               command=_go).pack(side="right")
    dlg.wait_window()
    return ok["ok"]


# ── Bulk & onboarding tab ──────────────────────────────────────────

def _build_bulk_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    imp = ttk.Frame(nb, padding=8)
    exp = ttk.Frame(nb, padding=8)
    onb = ttk.Frame(nb, padding=8)
    nb.add(imp, text="Import")
    nb.add(exp, text="Export")
    nb.add(onb, text="Onboard")

    _build_import_pane(gui, imp, refresh_all)
    _build_export_pane(gui, exp)
    _build_onboard_pane(gui, onb, refresh_all)


def _build_import_pane(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Bulk-create users from a CSV/XLSX file. Required "
                    "columns: username, password. Optional: "
                    "display_name, email, role, phone, department, "
                    "job_title, line_manager_id, notes. The wizard "
                    "validates every row, lets you preview the result, "
                    "and only commits when you say so."),
              wraplength=820, foreground="#555", justify="left").pack(
        anchor="w", pady=(0, 8))

    path_var = tk.StringVar()
    pick = ttk.Frame(parent)
    pick.pack(fill="x")
    ttk.Label(pick, text="File:").pack(side="left", padx=(0, 4))
    ttk.Entry(pick, textvariable=path_var, width=60).pack(side="left",
                                                            padx=(0, 4))

    def _browse():
        from tkinter import filedialog
        p = filedialog.askopenfilename(
            parent=gui.root,
            title="Pick CSV / XLSX",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx *.xlsm"),
                       ("All", "*.*")])
        if p:
            path_var.set(p)

    ttk.Button(pick, text="Browse…", command=_browse).pack(side="left")

    def _template():
        from tkinter import filedialog
        p = filedialog.asksaveasfilename(
            parent=gui.root, defaultextension=".csv",
            initialfile="users_template.csv",
            filetypes=[("CSV", "*.csv")])
        if not p:
            return
        try:
            bulk_io.write_template_csv(p)
        except Exception as e:
            logger.exception("Template write failed")
            messagebox.showerror("Template", str(e), parent=gui.root)
            return
        messagebox.showinfo("Template",
                             f"Template written to:\n{p}",
                             parent=gui.root)

    ttk.Button(pick, text="Download template…",
               command=_template).pack(side="left", padx=(8, 0))

    report = tk.Text(parent, height=22, wrap="none")
    yscroll = ttk.Scrollbar(parent, orient="vertical",
                              command=report.yview)
    report.configure(yscrollcommand=yscroll.set)
    yscroll.pack(side="right", fill="y")
    report.pack(fill="both", expand=True, pady=(6, 6))
    report.insert("1.0", "Pick a file then click 'Validate / Preview'.")
    report.configure(state="disabled")

    preview_holder = {"preview": None}

    def _set_report(text: str) -> None:
        report.configure(state="normal")
        report.delete("1.0", "end")
        report.insert("1.0", text)
        report.configure(state="disabled")

    def _validate():
        path = path_var.get().strip()
        if not path:
            messagebox.showinfo("Import", "Pick a file first.",
                                 parent=gui.root)
            return
        try:
            records = bulk_io.parse_file(path)
            preview = bulk_io.dry_run(gui.auth, records)
        except UserAccountError as e:
            messagebox.showerror("Import", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Import preview crashed")
            messagebox.showerror("Import", f"Unexpected: {e}",
                                  parent=gui.root)
            return
        preview_holder["preview"] = preview
        lines = [f"Parsed {len(preview.rows)} row(s).",
                  f"  valid:   {len(preview.valid)}",
                  f"  invalid: {len(preview.invalid)}",
                  ""]
        for r in preview.invalid:
            lines.append(f"  line {r.line_no}: "
                          f"{', '.join(r.errors)}")
        _set_report("\n".join(lines))

    def _commit():
        preview = preview_holder.get("preview")
        if preview is None:
            messagebox.showinfo("Import",
                                 "Validate first to preview the rows.",
                                 parent=gui.root)
            return
        valid = preview.valid
        if not valid:
            messagebox.showwarning("Import",
                                    "No valid rows to import.",
                                    parent=gui.root)
            return
        if not messagebox.askyesno(
                "Import",
                f"Create {len(valid)} user(s)? Invalid rows will "
                f"be skipped ({len(preview.invalid)}).",
                parent=gui.root):
            return
        try:
            result = bulk_io.commit_import(gui.auth, preview)
        except Exception as e:
            logger.exception("Import commit crashed")
            messagebox.showerror("Import", f"Unexpected: {e}",
                                  parent=gui.root)
            return
        lines = ["Imported.",
                  f"  created: {len(result.created_user_ids)}",
                  f"  failed:  {len(result.failed)}",
                  ""]
        for ln, err in result.failed[:50]:
            lines.append(f"  line {ln}: {err}")
        _set_report("\n".join(lines))
        refresh_all()

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 0))
    ttk.Button(bar, text="Validate / Preview",
               command=_validate).pack(side="left")
    ttk.Button(bar, text="Commit import",
               command=_commit).pack(side="left", padx=(6, 0))


def _build_export_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Export every user (or just one sixth-form role) "
                    "to CSV / JSON / XLSX. XLSX needs the openpyxl "
                    "package; CSV always works."),
              wraplength=820, foreground="#555", justify="left").pack(
        anchor="w", pady=(0, 8))

    row1 = ttk.Frame(parent)
    row1.pack(anchor="w", pady=4)
    ttk.Label(row1, text="Filter role:").pack(side="left", padx=(0, 4))
    role_var = tk.StringVar(value="(all)")
    ttk.Combobox(row1, textvariable=role_var, state="readonly",
                  width=22,
                  values=["(all)"] + list(ROLE_HIERARCHY.keys())
                  ).pack(side="left")

    ttk.Label(row1, text="Format:").pack(side="left", padx=(12, 4))
    fmt_var = tk.StringVar(value="csv")
    ttk.Combobox(row1, textvariable=fmt_var, state="readonly",
                  width=8,
                  values=["csv", "json"]
                       + (["xlsx"] if bulk_io.XLSX_AVAILABLE else [])
                  ).pack(side="left")

    def _go():
        from tkinter import filedialog
        fmt = fmt_var.get()
        p = filedialog.asksaveasfilename(
            parent=gui.root,
            defaultextension=f".{fmt}",
            initialfile=f"users_export.{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")])
        if not p:
            return
        role = role_var.get()
        try:
            n = bulk_io.export(
                gui.auth, p, fmt=fmt,
                sixthform_role=None if role == "(all)" else role)
        except UserAccountError as e:
            messagebox.showerror("Export", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Export crashed")
            messagebox.showerror("Export", f"Unexpected: {e}",
                                  parent=gui.root)
            return
        messagebox.showinfo("Export",
                             f"Wrote {n} user(s) to:\n{p}",
                             parent=gui.root)

    ttk.Button(parent, text="Export…", command=_go).pack(anchor="w",
                                                            pady=(8, 0))


def _build_onboard_pane(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Run the onboarding wizard: pick a role template, "
                    "review the permissions preview, fill in profile "
                    "details, and the system creates the user, issues "
                    "a one-time setup token, and emails it to them."),
              wraplength=820, foreground="#555", justify="left").pack(
        anchor="w", pady=(0, 8))

    row1 = ttk.Frame(parent)
    row1.pack(anchor="w", pady=4)
    ttk.Label(row1, text="Template:").pack(side="left", padx=(0, 4))
    tpl_var = tk.StringVar()
    tpl_combo = ttk.Combobox(row1, textvariable=tpl_var,
                               state="readonly", width=32)
    templates = onboarding.list_templates()
    tpl_combo['values'] = [f"{t.label}  ({t.role})" for t in templates]
    tpl_combo.current(0)
    tpl_combo.pack(side="left")

    preview = tk.Text(parent, height=10, wrap="word")
    preview.pack(fill="x", pady=(6, 6))
    preview.configure(state="disabled")

    def _refresh_preview(_e=None):
        i = tpl_combo.current()
        if i < 0 or i >= len(templates):
            return
        t = templates[i]
        text = (f"{t.label}\n"
                f"Role mapped: {t.role}\n\n"
                f"{t.description}\n\n"
                f"Permissions preview:\n"
                + "\n".join(f"  • {p}" for p in t.permissions_preview))
        preview.configure(state="normal")
        preview.delete("1.0", "end")
        preview.insert("1.0", text)
        preview.configure(state="disabled")

    tpl_combo.bind("<<ComboboxSelected>>", _refresh_preview)
    _refresh_preview()

    ttk.Button(parent, text="Start wizard…",
               command=lambda: _open_onboard_wizard(
                   gui, refresh_all,
                   template=templates[tpl_combo.current()])
               ).pack(anchor="w", pady=(0, 0))


def _open_onboard_wizard(gui, refresh_all, *, template) -> None:
    dlg = tk.Toplevel(gui.root)
    dlg.title(f"Onboard — {template.label}")
    dlg.geometry("520x440")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    row_idx = 0

    def _row(label: str, widget: tk.Widget) -> None:
        nonlocal row_idx
        ttk.Label(body, text=label).grid(row=row_idx, column=0,
                                            sticky="e", padx=(0, 8),
                                            pady=3)
        widget.grid(row=row_idx, column=1, sticky="ew", pady=3)
        row_idx += 1

    username_var = tk.StringVar()
    _row("Username *", ttk.Entry(body, textvariable=username_var,
                                    width=40))

    display_var = tk.StringVar()
    _row("Display name", ttk.Entry(body, textvariable=display_var,
                                      width=40))

    email_var = tk.StringVar()
    _row("Email (for welcome link)",
         ttk.Entry(body, textvariable=email_var, width=40))

    phone_var = tk.StringVar()
    _row("Phone", ttk.Entry(body, textvariable=phone_var, width=40))

    dept_var = tk.StringVar(value=template.default_department or "")
    _row("Department", ttk.Entry(body, textvariable=dept_var, width=40))

    title_var = tk.StringVar(value=template.default_job_title or "")
    _row("Job title", ttk.Entry(body, textvariable=title_var, width=40))

    mgr_var = tk.StringVar()
    _row("Line manager user-id (optional)",
         ttk.Entry(body, textvariable=mgr_var, width=40))

    ttk.Label(body,
              text=("A secure random initial password is set; the user "
                    "logs in with the emailed one-time token and "
                    "chooses their own password."),
              foreground="#666", wraplength=480).grid(
        row=row_idx, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _go():
        try:
            mgr_id = int(mgr_var.get().strip()) if mgr_var.get().strip() \
                else None
        except ValueError:
            messagebox.showerror("Onboard",
                                  "Line manager id must be a number.",
                                  parent=dlg)
            return
        try:
            result = onboarding.onboard(
                gui.auth, template_key=template.key,
                username=username_var.get().strip(),
                display_name=display_var.get().strip() or None,
                email=email_var.get().strip() or None,
                phone=phone_var.get(),
                department=dept_var.get(),
                job_title=title_var.get(),
                line_manager_id=mgr_id)
        except UserAccountError as e:
            messagebox.showerror("Onboard", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("onboard crashed")
            messagebox.showerror("Onboard", f"Unexpected: {e}",
                                  parent=dlg)
            return
        dlg.destroy()
        refresh_all()
        messagebox.showinfo(
            "Onboard",
            (f"Created user #{result.user.id} ({result.user.username}).\n"
             f"Template: {result.template.label}\n"
             f"Email sent: {'yes' if result.email_sent else 'no'}\n\n"
             f"One-time setup token (share if email failed):\n"
             f"  {result.token}"),
            parent=gui.root)

    bar = ttk.Frame(body)
    bar.grid(row=row_idx + 1, column=0, columnspan=2, sticky="e",
              pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Onboard",
               command=_go).pack(side="right")


# ── Rename dialog (feature 11) ─────────────────────────────────────

def _open_rename_form(gui, *, auth, user_id: int) -> bool:
    u = ua_data.get_user(auth, user_id)
    if u is None:
        messagebox.showerror("Rename", f"No user #{user_id}",
                              parent=gui.root)
        return False
    dlg = tk.Toplevel(gui.root)
    dlg.title("Rename user")
    dlg.geometry("480x260")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text=f"User #{u.id} — current username "
                          f"'{u.username}'.").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    ttk.Label(body, text="New username:").grid(row=1, column=0,
                                                  sticky="e", padx=(0, 6))
    uname_var = tk.StringVar(value=u.username)
    ttk.Entry(body, textvariable=uname_var, width=40).grid(
        row=1, column=1, sticky="ew")

    ttk.Label(body, text="New display name:").grid(row=2, column=0,
                                                      sticky="e",
                                                      padx=(0, 6))
    disp_var = tk.StringVar(value=u.display_name or "")
    ttk.Entry(body, textvariable=disp_var, width=40).grid(
        row=2, column=1, sticky="ew")

    ttk.Label(body, text="Reason:").grid(row=3, column=0, sticky="e",
                                            padx=(0, 6))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=40).grid(
        row=3, column=1, sticky="ew")

    ttk.Label(body, text=("Prior values are kept in "
                          "user_name_history."),
              foreground="#666").grid(row=4, column=0, columnspan=2,
                                        sticky="w", pady=(8, 0))

    ok = {"ok": False}

    def _go():
        try:
            identity.force_rename(
                auth, user_id,
                new_username=uname_var.get().strip(),
                new_display_name=disp_var.get().strip() or None,
                reason=reason_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Rename", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("rename crashed")
            messagebox.showerror("Rename", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Rename",
               command=_go).pack(side="right")
    dlg.wait_window()
    return ok["ok"]


# ── Merge dialog (feature 12) ──────────────────────────────────────

def _open_merge_form(gui, *, auth, ids: list[int]) -> bool:
    u1 = ua_data.get_user(auth, ids[0])
    u2 = ua_data.get_user(auth, ids[1])
    if u1 is None or u2 is None:
        messagebox.showerror("Merge",
                              "One or both users missing.",
                              parent=gui.root)
        return False
    dlg = tk.Toplevel(gui.root)
    dlg.title("Merge users")
    dlg.geometry("520x300")
    dlg.transient(gui.root)
    body = ttk.Frame(dlg, padding=10)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text="Pick the canonical user (the loser is "
                          "archived).",
              wraplength=480).grid(row=0, column=0, columnspan=2,
                                     sticky="w", pady=(0, 8))

    canonical_var = tk.IntVar(value=u1.id)
    ttk.Radiobutton(body,
                    text=f"#{u1.id} {u1.username} ({u1.display_name or ''})",
                    variable=canonical_var,
                    value=u1.id).grid(row=1, column=0, columnspan=2,
                                        sticky="w")
    ttk.Radiobutton(body,
                    text=f"#{u2.id} {u2.username} ({u2.display_name or ''})",
                    variable=canonical_var,
                    value=u2.id).grid(row=2, column=0, columnspan=2,
                                        sticky="w")

    ttk.Label(body, text="Reason:").grid(row=3, column=0, sticky="e",
                                            padx=(0, 6), pady=(8, 0))
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=46).grid(
        row=3, column=1, sticky="ew", pady=(8, 0))

    ttk.Label(body, text=("Cross-domain records (gradebook, finance, "
                          "housing) are NOT moved by this action — run "
                          "each domain's reassign tool separately."),
              foreground="#666",
              wraplength=480).grid(row=4, column=0, columnspan=2,
                                     sticky="w", pady=(8, 0))

    ok = {"ok": False}

    def _go():
        canonical = canonical_var.get()
        loser = u2.id if canonical == u1.id else u1.id
        if not messagebox.askyesno(
                "Merge",
                f"Merge #{loser} into #{canonical}? The loser will be "
                f"archived and its sessions invalidated.",
                parent=dlg):
            return
        try:
            r = identity.merge_accounts(
                auth, canonical_user_id=canonical,
                loser_user_id=loser,
                reason=reason_var.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Merge", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("merge crashed")
            messagebox.showerror("Merge", f"Unexpected: {e}",
                                  parent=dlg)
            return
        ok["ok"] = True
        dlg.destroy()
        summary = "\n".join(f"  {t}: {n}"
                              for t, n in sorted(r.moved.items()))
        messagebox.showinfo("Merge",
                              (f"Merged #{loser} -> #{canonical}.\n\n"
                               f"Rows moved:\n{summary}\n\n"
                               f"{r.cross_domain_note}"),
                              parent=gui.root)

    bar = ttk.Frame(body)
    bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(bar, text="Merge",
               command=_go).pack(side="right")
    dlg.wait_window()
    return ok["ok"]


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
        from tkinter import filedialog
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


# ── Integrations tab (44-47) + saved filters + notes ───────────────

def _build_integrations_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    sso_p = ttk.Frame(nb, padding=8)
    sync_p = ttk.Frame(nb, padding=8)
    hooks_p = ttk.Frame(nb, padding=8)
    filt_p = ttk.Frame(nb, padding=8)
    notes_p = ttk.Frame(nb, padding=8)

    nb.add(sso_p,  text="SSO mappings")
    nb.add(sync_p, text="HRIS / MIS sync")
    nb.add(hooks_p, text="Webhooks")
    nb.add(filt_p, text="Saved filters")
    nb.add(notes_p, text="Admin notes")

    _build_sso_pane(gui, sso_p)
    _build_sync_pane(gui, sync_p, refresh_all)
    _build_webhooks_pane(gui, hooks_p)
    _build_filters_pane(gui, filt_p)
    _build_notes_pane(gui, notes_p)


def _build_sso_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid = tk.StringVar()
    ttk.Entry(bar, textvariable=uid, width=8).pack(side="left",
                                                       padx=(0, 8))
    ttk.Label(bar, text="Provider:").pack(side="left", padx=(0, 4))
    prov = tk.StringVar()
    ttk.Combobox(bar, textvariable=prov, state="readonly", width=14,
                  values=["microsoft", "google", "other"]
                  ).pack(side="left", padx=(0, 8))
    ttk.Label(bar, text="Subject:").pack(side="left", padx=(0, 4))
    sub = tk.StringVar()
    ttk.Entry(bar, textvariable=sub, width=28).pack(side="left",
                                                        padx=(0, 8))
    ttk.Label(bar, text="Email:").pack(side="left", padx=(0, 4))
    em = tk.StringVar()
    ttk.Entry(bar, textvariable=em, width=22).pack(side="left",
                                                       padx=(0, 8))

    cols = ("id", "uid", "provider", "subject", "email", "created")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("id", "ID", 60),
                       ("uid", "User #", 60),
                       ("provider", "Provider", 100),
                       ("subject", "External subject", 220),
                       ("email", "Email", 200),
                       ("created", "Created", 160)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for r in integ.list_sso_mappings(gui.auth):
            tree.insert("", "end", iid=str(r["id"]), values=(
                r["id"], r["user_id"], r["provider"],
                r["external_subject"], r["email"] or "",
                r["created_at"]))

    def _add():
        if not uid.get().strip().isdigit():
            return
        try:
            integ.add_sso_mapping(
                gui.auth, user_id=int(uid.get()),
                provider=prov.get() or "other",
                external_subject=sub.get().strip(),
                email=em.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("SSO", str(e), parent=gui.root)
            return
        _refresh()

    def _remove():
        sel = tree.focus()
        if not sel:
            return
        integ.remove_sso_mapping(gui.auth, int(sel))
        _refresh()

    ttk.Button(bar, text="Add",
               command=_add).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Remove selected",
               command=_remove).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()


def _build_sync_pane(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent,
              text=("Compare a CSV feed (HRIS / MIS) against the local "
                    "users. Columns expected: external_id, username, "
                    "display_name, email, department, job_title. "
                    "Reconcile, then create only the rows you want."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 4))
    path = tk.StringVar()
    ttk.Entry(bar, textvariable=path, width=60).pack(side="left",
                                                          padx=(0, 4))

    def _browse():
        from tkinter import filedialog
        p = filedialog.askopenfilename(
            parent=gui.root, title="Pick feed",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if p:
            path.set(p)

    ttk.Button(bar, text="Browse…",
               command=_browse).pack(side="left", padx=(0, 8))

    out = tk.Text(parent, height=20, wrap="word")
    out.pack(fill="both", expand=True, pady=(6, 6))
    out.configure(state="disabled")
    state = {"report": None}

    def _preview():
        if not path.get().strip():
            return
        try:
            r = integ.reconcile_sync(gui.auth, path.get().strip())
        except UserAccountError as e:
            messagebox.showerror("Sync", str(e), parent=gui.root)
            return
        state["report"] = r
        lines = [
            f"New (in feed, not local): {len(r.new)}",
            f"Matched: {len(r.matched)}",
            f"Missing externally (in local, not feed): "
            f"{len(r.missing_externally)}",
            "",
        ]
        for row in r.new:
            lines.append(f"  + {row.username} · {row.display_name or ''} "
                          f"· {row.email or ''} · {row.department or ''}")
        out.configure(state="normal")
        out.delete("1.0", "end")
        out.insert("1.0", "\n".join(lines))
        out.configure(state="disabled")

    def _apply_create():
        r = state.get("report")
        if r is None or not r.new:
            messagebox.showinfo("Sync",
                                 "Run a preview with 'new' rows first.",
                                 parent=gui.root)
            return
        if not messagebox.askyesno(
                "Sync",
                f"Create {len(r.new)} user(s) with role 'student' on "
                f"sixth-form? Random initial passwords will be set.",
                parent=gui.root):
            return
        ids = integ.apply_sync_create(
            gui.auth, r.new, role="student",
            system_key="college")
        messagebox.showinfo("Sync",
                              f"Created {len(ids)} user(s).",
                              parent=gui.root)
        refresh_all()

    bar2 = ttk.Frame(parent)
    bar2.pack(fill="x")
    ttk.Button(bar2, text="Preview reconcile",
               command=_preview).pack(side="left")
    ttk.Button(bar2, text="Create new (role=student)",
               command=_apply_create).pack(side="left", padx=(6, 0))


def _build_webhooks_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Register external URLs to receive user events. "
                    "Subscribed events go to the outbox; a delivery "
                    "worker (not shipped here) would POST them."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))
    bar = ttk.Frame(parent)
    bar.pack(anchor="w")
    url = tk.StringVar()
    ttk.Entry(bar, textvariable=url, width=46).pack(side="left",
                                                        padx=(0, 4))
    events = tk.StringVar(value="user_create,user_archive,user_purge")
    ttk.Entry(bar, textvariable=events, width=40).pack(side="left",
                                                            padx=(0, 4))
    secret = tk.StringVar()
    ttk.Entry(bar, textvariable=secret, width=20).pack(side="left",
                                                            padx=(0, 4))

    cols = ("id", "url", "events", "active")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=12)
    for c, lbl, w in [("id", "ID", 50),
                       ("url", "URL", 360),
                       ("events", "Events", 320),
                       ("active", "Active", 70)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(6, 4))

    out = tk.Text(parent, height=10, wrap="none")
    out.pack(fill="both", expand=True)
    out.configure(state="disabled")

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        for w in integ.list_webhooks(gui.auth):
            tree.insert("", "end", iid=str(w["id"]), values=(
                w["id"], w["url"], w["events"],
                "yes" if w["is_active"] else "no"))
        out.configure(state="normal")
        out.delete("1.0", "end")
        for r in integ.list_outbox(gui.auth, limit=30):
            out.insert("end",
                         f"#{r['id']:>4}  ep={r['endpoint_id']}  "
                         f"event={r['event']:<20}  "
                         f"status={r['status']:<10}  "
                         f"enqueued={r['enqueued_at']}\n")
        out.configure(state="disabled")

    def _add():
        if not url.get().strip():
            return
        evs = [e.strip() for e in events.get().split(",") if e.strip()]
        try:
            integ.add_webhook(gui.auth, url=url.get().strip(),
                                events=evs,
                                secret=secret.get().strip() or None)
        except UserAccountError as e:
            messagebox.showerror("Webhooks", str(e), parent=gui.root)
            return
        _refresh()

    def _remove():
        sel = tree.focus()
        if not sel:
            return
        integ.remove_webhook(gui.auth, int(sel))
        _refresh()

    btns = ttk.Frame(parent)
    btns.pack(fill="x")
    ttk.Button(btns, text="Add",
               command=_add).pack(side="left", padx=(0, 4))
    ttk.Button(btns, text="Disable selected",
               command=_remove).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Refresh",
               command=_refresh).pack(side="left")
    _refresh()


def _build_filters_pane(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Save a filter payload (any JSON-able dict). The "
                    "Users tab could load these as quick filters."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                        pady=(0, 8))

    bar = ttk.Frame(parent)
    bar.pack(anchor="w")
    name = tk.StringVar()
    ttk.Entry(bar, textvariable=name, width=22).pack(side="left",
                                                          padx=(0, 4))
    payload = tk.StringVar(
        value='{"scope": "Locked", "query": ""}')
    ttk.Entry(bar, textvariable=payload, width=50).pack(side="left",
                                                            padx=(0, 4))

    cols = ("id", "name", "payload", "created_at")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("id", "ID", 50),
                       ("name", "Name", 200),
                       ("payload", "Payload", 460),
                       ("created_at", "Created", 160)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(6, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        import json
        for f in integ.list_filters(gui.auth):
            tree.insert("", "end", iid=str(f["id"]), values=(
                f["id"], f["name"],
                json.dumps(f["payload"], default=str),
                f["created_at"]))

    def _save():
        if not name.get().strip():
            return
        import json
        try:
            pl = json.loads(payload.get() or "{}")
        except Exception:
            messagebox.showerror("Filter", "Payload must be JSON.",
                                  parent=gui.root)
            return
        try:
            integ.save_filter(gui.auth, name=name.get().strip(),
                                 payload=pl)
        except UserAccountError as e:
            messagebox.showerror("Filter", str(e), parent=gui.root)
            return
        _refresh()

    def _delete():
        sel = tree.focus()
        if not sel:
            return
        row = next((f for f in integ.list_filters(gui.auth)
                     if str(f["id"]) == sel), None)
        if row is None:
            return
        integ.delete_filter(gui.auth, name=row["name"])
        _refresh()

    btns = ttk.Frame(parent)
    btns.pack(fill="x")
    ttk.Button(btns, text="Save",
               command=_save).pack(side="left", padx=(0, 4))
    ttk.Button(btns, text="Delete selected",
               command=_delete).pack(side="left")
    _refresh()


def _build_notes_pane(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 6))
    ttk.Label(bar, text="User id:").pack(side="left", padx=(0, 4))
    uid = tk.StringVar()
    ttk.Entry(bar, textvariable=uid, width=8).pack(side="left",
                                                       padx=(0, 8))
    body = tk.StringVar()
    ttk.Entry(bar, textvariable=body, width=60).pack(side="left",
                                                          padx=(0, 4))
    visible = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Visible to user",
                    variable=visible).pack(side="left", padx=(0, 4))

    cols = ("id", "ts", "author", "body", "vis")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                         height=14)
    for c, lbl, w in [("id", "ID", 60),
                       ("ts", "When", 160),
                       ("author", "Author", 120),
                       ("body", "Note", 460),
                       ("vis", "User-visible", 110)]:
        tree.heading(c, text=lbl)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(4, 4))

    def _refresh():
        for it in tree.get_children():
            tree.delete(it)
        if not uid.get().strip().isdigit():
            return
        for n in integ.list_notes(gui.auth, int(uid.get())):
            tree.insert("", "end", iid=str(n["id"]), values=(
                n["id"], n["created_at"], n["author"] or "",
                n["body"],
                "yes" if n["visible_to_user"] else "no"))

    def _add():
        if not uid.get().strip().isdigit() or not body.get().strip():
            return
        try:
            integ.add_note(gui.auth, user_id=int(uid.get()),
                              body=body.get().strip(),
                              visible_to_user=visible.get())
        except UserAccountError as e:
            messagebox.showerror("Note", str(e), parent=gui.root)
            return
        body.set("")
        _refresh()

    def _delete():
        sel = tree.focus()
        if not sel:
            return
        integ.delete_note(gui.auth, int(sel))
        _refresh()

    btns = ttk.Frame(parent)
    btns.pack(fill="x")
    ttk.Button(btns, text="Add",
               command=_add).pack(side="left", padx=(0, 4))
    ttk.Button(btns, text="Delete selected",
               command=_delete).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Load / refresh",
               command=_refresh).pack(side="left")
    _refresh()
