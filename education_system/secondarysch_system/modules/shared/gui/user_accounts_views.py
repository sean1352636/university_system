"""Tkinter views for Secondary School User Accounts admin."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable
from education_system.secondarysch_system.modules.shared import user_accounts as data
from education_system.shared import branding
from education_system.secondarysch_system.modules.shared.user_accounts import (
    DEFAULT_ROLE,
    ROLES,
    SYSTEM_KEY,
    UserAccountError,
    UserRow,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_user_accounts_window(parent=None, *, auth) -> None:
    if auth is None or not getattr(auth, "current_user", None):
        messagebox.showerror(
            "User Accounts",
            "No active session — please sign in again.")
        return
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"User Accounts — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    UsersTab(nb, auth)
    SummaryTab(nb, auth)


def _systems_str(u: UserRow) -> str:
    if not u.systems:
        return "—"
    return ", ".join(f"{s['system_key']}:{s['role']}"
                       for s in u.systems)


# ══ Users tab ══════════════════════════════════════════════════════

class UsersTab:
    def __init__(self, nb: ttk.Notebook, auth) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Users")
        self.auth = auth
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.q_e = ttk.Entry(bar, width=24)
        self.q_e.pack(side="left", padx=(2, 10))
        self.q_e.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(bar, text="Role:").pack(side="left")
        self.f_role = ttk.Combobox(bar, values=("",) + ROLES,
                                      state="readonly", width=18)
        self.f_role.current(0)
        self.f_role.pack(side="left", padx=(2, 10))
        self.f_sixth = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Secondary-school only",
                          variable=self.f_sixth,
                          command=self.refresh).pack(side="left")
        self.f_active = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.f_active,
                          command=self.refresh).pack(side="left",
                                                         padx=(8, 0))
        self.f_locked = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Locked only",
                          variable=self.f_locked,
                          command=self.refresh).pack(side="left",
                                                         padx=(8, 0))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "username", "display", "email",
                "active", "locked", "last_login", "systems")
        widths = {"id": 50, "username": 140, "display": 180,
                  "email": 200, "active": 60, "locked": 60,
                  "last_login": 140, "systems": 280}
        heads = {"id": "#", "username": "Username",
                 "display": "Display", "email": "Email",
                 "active": "Active", "locked": "Locked",
                 "last_login": "Last login",
                 "systems": "Systems"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("inactive", foreground="#888",
                                  background="#f4f4f4")
        self.tree.tag_configure("locked", background="#ffe0e0")
        self.tree.bind("<Double-1>", lambda _e: self._view())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit Profile",
                    command=self._edit_profile).pack(side="left", padx=4)
        ttk.Button(bar, text="Reset Password",
                    command=self._reset_password).pack(side="left", padx=4)
        ttk.Button(bar, text="Lock",
                    command=self._lock).pack(side="left", padx=4)
        ttk.Button(bar, text="Unlock",
                    command=self._unlock).pack(side="left", padx=4)
        ttk.Button(bar, text="Toggle Active",
                    command=self._toggle_active).pack(side="left", padx=4)
        ttk.Button(bar, text="Roles…",
                    command=self._roles).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.q_e.delete(0, "end")
        self.f_role.current(0)
        self.f_sixth.set(True)
        self.f_active.set(False)
        self.f_locked.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_users(
                self.auth,
                query=self.q_e.get().strip() or None,
                role=self.f_role.get() or None,
                system_key=SYSTEM_KEY if self.f_sixth.get() else None,
                active_only=self.f_active.get(),
                locked_only=self.f_locked.get(),
            )
        except UserAccountError as e:
            messagebox.showerror("Filter", str(e))
            return
        for u in rows:
            tags: list[str] = []
            if not u.is_active:
                tags.append("inactive")
            if u.is_locked:
                tags.append("locked")
            self.tree.insert("", "end", iid=str(u.id), values=(
                u.id, u.username, u.display_name or "—",
                u.email or "—",
                "Y" if u.is_active else "N",
                "Y" if u.is_locked else "N",
                u.last_login or "—",
                _systems_str(u),
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} user(s).")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _selected(self) -> UserRow | None:
        uid = self._selected_id()
        return data.get_user(self.auth, uid) if uid is not None else None

    def _view(self) -> None:
        u = self._selected()
        if u is None:
            messagebox.showinfo("View", "Select a user first.")
            return
        lines = [
            f"User #{u.id}",
            f"  Username        : {u.username}",
            f"  Display name    : {u.display_name or '—'}",
            f"  Email           : {u.email or '—'}",
            f"  Active          : {'Yes' if u.is_active else 'No'}",
            "  Locked          : "
            + ("Yes (until " + (u.locked_until or "?") + ")"
                if u.is_locked else "No"),
            f"  Failed attempts : {u.failed_login_attempts}",
            f"  Created         : {u.created_at}",
            f"  Updated         : {u.updated_at}",
            f"  Last login      : {u.last_login or '—'}",
            f"  Pwd changed at  : {u.password_changed_at or '—'}",
        ]
        if u.systems:
            lines.append("")
            lines.append("System access:")
            for s in u.systems:
                lines.append(f"  {s['system_key']:<14} → {s['role']}")
        messagebox.showinfo(f"User #{u.id}", "\n".join(lines))

    def _new(self) -> None:
        NewUserDialog(self.frame.winfo_toplevel(),
                        auth=self.auth, on_save=self.refresh)

    def _edit_profile(self) -> None:
        u = self._selected()
        if u is None:
            messagebox.showinfo("Edit", "Select a user first.")
            return
        EditProfileDialog(self.frame.winfo_toplevel(),
                            auth=self.auth, user=u,
                            on_save=self.refresh)

    def _reset_password(self) -> None:
        u = self._selected()
        if u is None:
            messagebox.showinfo("Reset", "Select a user first.")
            return
        ResetPasswordDialog(self.frame.winfo_toplevel(),
                              auth=self.auth, user=u,
                              on_save=self.refresh)

    def _lock(self) -> None:
        u = self._selected()
        if u is None:
            messagebox.showinfo("Lock", "Select a user first.")
            return
        mins = simpledialog.askinteger(
            "Lock user",
            f"Lock {u.username} for how many minutes?",
            parent=self.frame.winfo_toplevel(),
            initialvalue=60, minvalue=1, maxvalue=525600)
        if mins is None:
            return
        try:
            data.lock_user(self.auth, u.id, mins)
        except UserAccountError as e:
            messagebox.showerror("Lock", str(e))
            return
        self.refresh()

    def _unlock(self) -> None:
        u = self._selected()
        if u is None:
            messagebox.showinfo("Unlock", "Select a user first.")
            return
        try:
            data.unlock_user(self.auth, u.id)
        except UserAccountError as e:
            messagebox.showerror("Unlock", str(e))
            return
        self.refresh()

    def _toggle_active(self) -> None:
        u = self._selected()
        if u is None:
            messagebox.showinfo("Active", "Select a user first.")
            return
        new_state = not u.is_active
        action = "Activate" if new_state else "Deactivate"
        if not messagebox.askyesno(
                action, f"{action} {u.username}?"):
            return
        try:
            data.set_active(self.auth, u.id, new_state)
        except UserAccountError as e:
            messagebox.showerror("Active", str(e))
            return
        self.refresh()

    def _roles(self) -> None:
        u = self._selected()
        if u is None:
            messagebox.showinfo("Roles", "Select a user first.")
            return
        RolesDialog(self.frame.winfo_toplevel(),
                      auth=self.auth, user=u,
                      on_save=self.refresh)

    def _delete(self) -> None:
        u = self._selected()
        if u is None:
            messagebox.showinfo("Delete", "Select a user first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Permanently delete {u.username}?\n\n"
                f"This also removes their sessions, MFA secrets, "
                f"and password history."):
            return
        try:
            if data.delete_user(self.auth, u.id):
                messagebox.showinfo(
                    "Delete", f"Deleted {u.username}.")
        except UserAccountError as e:
            messagebox.showerror("Delete", str(e))
            return
        self.refresh()


# ── Dialogs ────────────────────────────────────────────────────────

class NewUserDialog:
    def __init__(self, parent: tk.Misc, *, auth,
                 on_save: Callable[[], None]) -> None:
        self.auth = auth
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("New User")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        def label(t):
            nonlocal r
            ttk.Label(form, text=t).grid(row=r, column=0,
                                           sticky="e", pady=3)

        label("Username:")
        self.user_e = ttk.Entry(form, width=30)
        self.user_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Display name:")
        self.display_e = ttk.Entry(form, width=30)
        self.display_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Email:")
        self.email_e = ttk.Entry(form, width=30)
        self.email_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Secondary-school role:")
        self.role_cb = ttk.Combobox(form, values=ROLES,
                                       state="readonly", width=22)
        self.role_cb.set(DEFAULT_ROLE)
        self.role_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Password:")
        self.pw_e = ttk.Entry(form, width=30, show="•")
        self.pw_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Confirm:")
        self.conf_e = ttk.Entry(form, width=30, show="•")
        self.conf_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        self.show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Show passwords",
                          variable=self.show_var,
                          command=self._toggle).grid(
            row=r, column=1, sticky="w", padx=6)
        r += 1

        self.status_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.status_var,
                   foreground="#a00", wraplength=320,
                   justify="left").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(4, 0))
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Create",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        self.user_e.focus_set()

    def _toggle(self) -> None:
        ch = "" if self.show_var.get() else "•"
        for e in (self.pw_e, self.conf_e):
            e.configure(show=ch)

    def _save(self) -> None:
        self.status_var.set("")
        if self.pw_e.get() != self.conf_e.get():
            self.status_var.set("Passwords don't match.")
            return
        try:
            data.create_user(
                self.auth,
                username=self.user_e.get().strip(),
                password=self.pw_e.get(),
                display_name=self.display_e.get().strip(),
                email=self.email_e.get().strip(),
                role=self.role_cb.get(),
            )
        except UserAccountError as e:
            self.status_var.set(str(e))
            return
        except Exception as e:
            logger.exception("create user failed")
            self.status_var.set(str(e))
            return
        self.win.destroy()
        self.on_save()


class EditProfileDialog:
    def __init__(self, parent: tk.Misc, *, auth, user: UserRow,
                 on_save: Callable[[], None]) -> None:
        self.auth = auth
        self.user = user
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit profile — {user.username}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form, text=f"User: {self.user.username}",
                   foreground="#555").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Display name:").grid(
            row=1, column=0, sticky="e", pady=3)
        self.display_e = ttk.Entry(form, width=30)
        if self.user.display_name:
            self.display_e.insert(0, self.user.display_name)
        self.display_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Email:").grid(
            row=2, column=0, sticky="e", pady=3)
        self.email_e = ttk.Entry(form, width=30)
        if self.user.email:
            self.email_e.insert(0, self.user.email)
        self.email_e.grid(row=2, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.update_profile(
                self.auth, self.user.id,
                display_name=self.display_e.get().strip(),
                email=self.email_e.get().strip(),
            )
        except UserAccountError as e:
            messagebox.showerror("Edit", str(e))
            return
        self.win.destroy()
        self.on_save()


class ResetPasswordDialog:
    def __init__(self, parent: tk.Misc, *, auth, user: UserRow,
                 on_save: Callable[[], None]) -> None:
        self.auth = auth
        self.user = user
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Reset password — {user.username}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=14, pady=14)
        ttk.Label(form,
                   text=f"Admin reset for {self.user.username}\n"
                        f"The old password is not required. Any "
                        f"active sessions will be invalidated.",
                   foreground="#555", justify="left",
                   wraplength=340).grid(row=0, column=0, columnspan=2,
                                          sticky="w", pady=(0, 8))
        ttk.Label(form, text="New password:").grid(
            row=1, column=0, sticky="e", pady=3)
        self.pw_e = ttk.Entry(form, width=30, show="•")
        self.pw_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Confirm:").grid(
            row=2, column=0, sticky="e", pady=3)
        self.conf_e = ttk.Entry(form, width=30, show="•")
        self.conf_e.grid(row=2, column=1, sticky="w", padx=6)
        self.show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Show",
                          variable=self.show_var,
                          command=self._toggle).grid(
            row=3, column=1, sticky="w", padx=6)
        self.status_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.status_var,
                   foreground="#a00",
                   wraplength=320).grid(row=4, column=0,
                                          columnspan=2, sticky="w",
                                          pady=(6, 0))
        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Reset",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)
        self.pw_e.focus_set()

    def _toggle(self) -> None:
        ch = "" if self.show_var.get() else "•"
        for e in (self.pw_e, self.conf_e):
            e.configure(show=ch)

    def _save(self) -> None:
        self.status_var.set("")
        if self.pw_e.get() != self.conf_e.get():
            self.status_var.set("Passwords don't match.")
            return
        try:
            data.admin_reset_password(
                self.auth, self.user.id, self.pw_e.get())
        except UserAccountError as e:
            self.status_var.set(str(e))
            return
        messagebox.showinfo(
            "Reset",
            f"Password reset for {self.user.username}. "
            f"Active sessions invalidated.")
        self.win.destroy()
        self.on_save()


class RolesDialog:
    def __init__(self, parent: tk.Misc, *, auth, user: UserRow,
                 on_save: Callable[[], None]) -> None:
        self.auth = auth
        self.user = user
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Roles — {user.username}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win)
        outer.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(outer,
                   text=f"System access for {self.user.username}",
                   font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(outer, text=f"User #{self.user.id}",
                   foreground="#555").pack(anchor="w", pady=(0, 6))

        cols = ("system", "role")
        widths = {"system": 200, "role": 200}
        self.tree = ttk.Treeview(outer, columns=cols,
                                    show="headings", height=6)
        self.tree.heading("system", text="System")
        self.tree.heading("role", text="Role")
        self.tree.column("system", width=widths["system"], anchor="w")
        self.tree.column("role", width=widths["role"], anchor="w")
        self.tree.pack(fill="both", expand=True, pady=4)
        self._refresh()

        grant = ttk.LabelFrame(outer, text="Grant / update")
        grant.pack(fill="x", pady=6)
        ttk.Label(grant, text="System:").grid(row=0, column=0,
                                                  padx=4, pady=4)
        self.sys_e = ttk.Entry(grant, width=22)
        self.sys_e.insert(0, SYSTEM_KEY)
        self.sys_e.grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(grant, text="Role:").grid(row=0, column=2,
                                                padx=4, pady=4)
        self.role_cb = ttk.Combobox(grant, values=ROLES,
                                        state="readonly", width=20)
        self.role_cb.set(DEFAULT_ROLE)
        self.role_cb.grid(row=0, column=3, padx=4, pady=4)
        ttk.Button(grant, text="Grant / update",
                    command=self._grant).grid(row=0, column=4,
                                                 padx=4, pady=4)

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Revoke selected",
                    command=self._revoke).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self._close).pack(side="right")

    def _refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        u = data.get_user(self.auth, self.user.id)
        if u is None:
            return
        self.user = u
        for s in u.systems:
            self.tree.insert("", "end",
                                iid=s["system_key"],
                                values=(s["system_key"], s["role"]))

    def _grant(self) -> None:
        sk = self.sys_e.get().strip()
        if not sk:
            messagebox.showerror("Grant", "System key is required.")
            return
        try:
            data.grant_role(self.auth, self.user.id, sk,
                              self.role_cb.get())
        except UserAccountError as e:
            messagebox.showerror("Grant", str(e))
            return
        self._refresh()

    def _revoke(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Revoke",
                                  "Select a row first.")
            return
        sk = sel[0]
        if not messagebox.askyesno(
                "Revoke",
                f"Revoke access to '{sk}' for "
                f"{self.user.username}?"):
            return
        try:
            data.revoke_role(self.auth, self.user.id, sk)
        except UserAccountError as e:
            messagebox.showerror("Revoke", str(e))
            return
        self._refresh()

    def _close(self) -> None:
        self.win.destroy()
        self.on_save()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook, auth) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self.auth = auth
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        s = data.summary(self.auth)
        L: list[str] = []
        L.append("Users")
        L.append("-----")
        L.append(f"  Total                : {s.total}")
        L.append(f"  Active               : {s.active}")
        L.append(f"  Inactive             : {s.inactive}")
        L.append(f"  Locked right now     : {s.locked}")
        L.append(f"  In secondary-school        : {s.sixth_form_users}")
        L.append(f"  Logins in last 7 days: {s.recent_logins_7d}")
        L.append("")
        L.append("Secondary-school roles")
        L.append("----------------")
        for r in ROLES:
            n = s.by_role_in_sixthform.get(r, 0)
            if n:
                L.append(f"  {r:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
