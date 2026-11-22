"""The User Access section of the restaurant window."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.plugins.campus_commerce.domain.services.restaurant.operations import (
    user_access,
)

COLUMNS = (
    ("Login", 130), ("Name", 170), ("Staff ID", 70), ("Staff member", 170), ("Role", 90),
    ("Status", 170), ("Granted by", 110), ("Granted on", 140), ("Removed", 220),
)


def _scrolled_tree(parent, columns):
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, padx=8, pady=8)
    scroll = ttk.Scrollbar(holder, orient="vertical")
    tree = ttk.Treeview(holder, columns=[name for name, _w in columns], show="headings",
                        selectmode="browse", yscrollcommand=scroll.set)
    scroll.config(command=tree.yview)
    for name, width in columns:
        tree.heading(name, text=name)
        tree.column(name, width=width, stretch=name in ("Name", "Staff member", "Removed", "Change"))
    scroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return tree


def create_user_access_tab(self, parent):
    """Build the section. Its contents load each time it is opened."""
    ttk.Label(parent, text="User Access", style="Heading.TLabel").pack(anchor="w", padx=8, pady=(8, 2))

    # Packed before the table so the buttons stay visible on a small screen.
    actions = ttk.Frame(parent)
    actions.pack(fill="x", padx=8, pady=4)
    for label, command in (
        ("Grant access", self.user_access_grant),
        ("Change role", self.user_access_change_role),
        ("Remove access", self.user_access_remove),
        ("Access history", self.user_access_history),
        ("Refresh", self.refresh_user_access),
    ):
        ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 6))

    roles = "   ".join(
        f"{role}: {', '.join(sorted(name.replace('manage_', '').replace('update_takeaway_', '') for name in perms))}"
        for role, perms in user_access.ROLE_PERMISSIONS.items())
    ttk.Label(parent, text=roles, wraplength=1050, justify="left").pack(anchor="w", padx=8)

    self.user_access_tree = _scrolled_tree(parent, COLUMNS)


def refresh_user_access(self):
    tree = self.user_access_tree
    tree.delete(*tree.get_children())
    try:
        rows = user_access.list_access(self.auth)
    except (user_access.AccessError, sqlite3.Error) as exc:
        messagebox.showerror("User Access", str(exc), parent=self.root)
        return
    for row in rows:
        removed = ""
        if not row["active"]:
            removed = f"{row['removed_at'][:10]} by {row['removed_by']}: {row['removed_reason']}"
        tree.insert("", "end", iid=row["username"], values=(
            row["username"], row["name"], row["staff_id"] or "", row["staff_name"], row["role"],
            row["state"], row["granted_by"], row["granted_at"], removed))


def _selected_user(self, must_be_active=True):
    selection = self.user_access_tree.selection()
    if not selection:
        messagebox.showinfo("User Access", "Select a user first.", parent=self.root)
        return None
    username = selection[0]
    if must_be_active and "Removed" in self.user_access_tree.item(username, "values")[5]:
        messagebox.showinfo("User Access", f"{username} no longer has access.", parent=self.root)
        return None
    return username


def _apply(self, action, *args):
    """Run a change, show any refusal, and refresh. True when it worked."""
    try:
        action(self.auth, *args)
    except (user_access.AccessError, sqlite3.Error) as exc:
        messagebox.showerror("User Access", str(exc), parent=self.root)
        return False
    self.refresh_user_access()
    return True


def user_access_grant(self):
    try:
        staff = user_access.staff_available(self.auth)
    except (user_access.AccessError, sqlite3.Error) as exc:
        messagebox.showerror("User Access", str(exc), parent=self.root)
        return
    if not staff:
        messagebox.showinfo(
            "User Access",
            "No active staff member is free to link. Add them in the Staff section first.",
            parent=self.root)
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("Grant restaurant access")
    dialog.geometry("560x520")
    dialog.transient(self.root)

    ttk.Label(dialog, text="Search staff logins").pack(anchor="w", padx=12, pady=(12, 2))
    search = tk.StringVar()
    ttk.Entry(dialog, textvariable=search).pack(fill="x", padx=12)

    # Packed before the login list so the buttons stay on screen.
    buttons = ttk.Frame(dialog)
    buttons.pack(side="bottom", fill="x", padx=12, pady=12)

    form = ttk.Frame(dialog)
    form.pack(side="bottom", fill="x", padx=12)
    form.columnconfigure(1, weight=1)
    staff_labels = {f"{s['name']} (ID {s['staff_id']}, {s['role']})": s["staff_id"] for s in staff}
    staff_box = ttk.Combobox(form, values=list(staff_labels), state="readonly")
    role_box = ttk.Combobox(form, values=list(user_access.ROLES), state="readonly")
    ttk.Label(form, text="Staff member").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    staff_box.grid(row=0, column=1, sticky="ew", pady=4)
    ttk.Label(form, text="Role").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    role_box.grid(row=1, column=1, sticky="ew", pady=4)

    logins = _scrolled_tree(dialog, (("Login", 150), ("Name", 240), ("Email", 130)))

    def load_logins(*_args):
        logins.delete(*logins.get_children())
        try:
            for login in user_access.find_logins(self.auth, search.get()):
                logins.insert("", "end", iid=login["username"],
                              values=(login["username"], login["name"], login["email"]))
        except (user_access.AccessError, sqlite3.Error) as exc:
            messagebox.showerror("User Access", str(exc), parent=dialog)

    def save():
        chosen = logins.selection()
        if not chosen or not staff_box.get() or not role_box.get():
            messagebox.showinfo("User Access", "Choose a login, a staff member and a role.",
                                parent=dialog)
            return
        if _apply(self, user_access.grant_access, chosen[0], staff_labels[staff_box.get()],
                  role_box.get()):
            dialog.destroy()

    search.trace_add("write", load_logins)
    ttk.Button(buttons, text="Grant access", command=save).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=6)
    load_logins()


def user_access_change_role(self):
    username = _selected_user(self)
    if not username:
        return
    current = self.user_access_tree.item(username, "values")[4]

    dialog = tk.Toplevel(self.root)
    dialog.title(f"Change role: {username}")
    dialog.geometry("360x150")
    dialog.transient(self.root)
    ttk.Label(dialog, text="Role").pack(anchor="w", padx=12, pady=(12, 2))
    role_box = ttk.Combobox(dialog, values=list(user_access.ROLES), state="readonly")
    role_box.set(current)
    role_box.pack(fill="x", padx=12)

    def save():
        if _apply(self, user_access.change_role, username, role_box.get()):
            dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.pack(side="bottom", fill="x", padx=12, pady=12)
    ttk.Button(buttons, text="Save", command=save).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=6)


def user_access_remove(self):
    username = _selected_user(self)
    if not username:
        return
    reason = simpledialog.askstring(
        "Remove access",
        f"Remove access for {username}? Their staff record is kept.\n\nReason (optional):",
        parent=self.root)
    if reason is not None:
        _apply(self, user_access.remove_access, username, reason)


def _describe_change(old_values, new_values) -> str:
    old = json.loads(old_values) if old_values else {}
    new = json.loads(new_values) if new_values else {}
    return ", ".join(f"{key}: {old[key]} → {value}" if key in old else f"{key}: {value}"
                     for key, value in new.items())


def user_access_history(self):
    selection = self.user_access_tree.selection()
    username = selection[0] if selection else None
    try:
        rows = user_access.access_history(self.auth, username)
    except (user_access.AccessError, sqlite3.Error) as exc:
        messagebox.showerror("User Access", str(exc), parent=self.root)
        return
    window = tk.Toplevel(self.root)
    window.title(f"Access history: {username}" if username else "Access history")
    window.geometry("1400x900")
    window.minsize(1200, 800)
    tree = _scrolled_tree(window, (("When", 150), ("Changed by", 130), ("Action", 170),
                                   ("Login", 130), ("Change", 600)))
    for row in rows:
        tree.insert("", "end", values=(
            row["timestamp"], row["user_id"], row["action"], row["record_id"],
            _describe_change(row["old_values"], row["new_values"])))
    if not rows:
        tree.insert("", "end", values=("No access changes recorded.", "", "", "", ""))
