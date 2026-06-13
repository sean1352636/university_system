"""GUI panels for the Secondary School User Management module.

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
from education_system.secondarysch_system.modules.domain.governance.user_management import user_management as data
from education_system.secondarysch_system.modules.shared import user_accounts as ua_data
from education_system.secondarysch_system.modules.shared.user_accounts import (
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

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    summary_tab = ttk.Frame(nb, padding=8)
    matrix_tab = ttk.Frame(nb, padding=8)
    users_tab = ttk.Frame(nb, padding=8)
    nb.add(summary_tab, text="Summary")
    nb.add(matrix_tab,  text="Access matrix")
    nb.add(users_tab,   text="Users & bulk actions")

    state: dict[str, Any] = {
        "refresh_summary": None,
        "refresh_matrix":  None,
        "refresh_users":   None,
    }

    def refresh_all() -> None:
        for k in ("refresh_summary", "refresh_matrix", "refresh_users"):
            if state[k]:
                state[k]()

    _build_summary_tab(gui, summary_tab, state)
    _build_matrix_tab(gui, matrix_tab, state)
    _build_users_tab(gui, users_tab, state, refresh_all)


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
    _tile(1, "Secondary-school",    sixth_var, "Have college access")
    _tile(2, "Active",        active_var, "is_active = true")
    _tile(3, "Locked",        locked_var, "Currently locked", fg="#a33")
    _tile(4, "Admins",        admins_var, "Secondary-school admins")
    _tile(5, "Logins (7d)",   recent_var, "Last 7 days")

    roles_frame = ttk.LabelFrame(parent, text="Secondary-school role distribution",
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
        sixth_var.set(str(s.secondary_school_users))
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
                  f"Users without secondary-school access: "
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
                  values=["All", "Secondary-school only",
                           "Without secondary-school access",
                           "Locked", "Inactive", "Admins (secondary-school)"]
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
            if scope == "Secondary-school only":
                rows = ua_data.list_users(gui.auth, system_key=SYSTEM_KEY)
            elif scope == "Without secondary-school access":
                rows = data.list_without_access(gui.auth)
            elif scope == "Locked":
                rows = data.list_locked(gui.auth)
            elif scope == "Inactive":
                rows = data.list_inactive(gui.auth)
            elif scope == "Admins (secondary-school)":
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
            "sixthform": ("Secondary-school role", 130),
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
    ttk.Button(bulk_bar, text="Revoke secondary-school access",
                command=_do_revoke
                ).pack(side="left", padx=(0, 12))
    ttk.Button(bulk_bar, text="Activate selected",
                command=lambda: _set_active(True)
                ).pack(side="left", padx=(0, 6))
    ttk.Button(bulk_bar, text="Deactivate selected",
                command=lambda: _set_active(False)
                ).pack(side="left", padx=(0, 6))

    state["refresh_users"] = refresh
    refresh()
