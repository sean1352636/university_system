"""User management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.primary_school.modules.domain.admin.users.services.user_service import UserService
import traceback


ROLES = ["admin", "teacher", "teaching_assistant", "parent"]


class _UserDialog(tk.Toplevel):
    """Add / Edit user dialog."""

    def __init__(self, parent, db_path, user=None):
        super().__init__(parent)
        self.result = None
        self._user = user
        self.title("Edit User" if user else "Add User")
        self.geometry("450x380")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "username", "Username *")
        if not user:
            self._add_field(frm, "password", "Password *", show="*")
        self._add_combo(frm, "role", "Role *", ROLES)
        self._add_field(frm, "display_name", "Display Name *")
        self._add_field(frm, "email", "Email")

        if user:
            self._add_combo(frm, "is_active", "Active", ["1", "0"])

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=15)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if user:
            for key, widget in self._entries.items():
                val = user.get(key)
                if val is None:
                    continue
                if isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label, show=None):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30, show=show or "")
        entry.pack(side="left", fill="x", expand=True)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("username"):
            messagebox.showwarning("Validation", "Username is required.", parent=self)
            return
        if not self._user and not data.get("password"):
            messagebox.showwarning("Validation", "Password is required.", parent=self)
            return
        if not data.get("display_name"):
            messagebox.showwarning("Validation", "Display name is required.", parent=self)
            return
        if not data.get("role"):
            messagebox.showwarning("Validation", "Role is required.", parent=self)
            return
        self.result = data
        self.destroy()


class UserFrame(tk.Frame):
    """Main user management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = UserService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="User Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add User", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Reset Password", command=self._on_reset_password).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Role:", bg="#d5dbdb").pack(side="left")
        self._role_filter = ttk.Combobox(toolbar, values=["All"] + ROLES,
                                          state="readonly", width=16)
        self._role_filter.set("All")
        self._role_filter.pack(side="left", padx=3)
        self._role_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("id", "username", "role", "display_name", "email", "is_active", "last_login")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("id", width=50)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        role = self._role_filter.get()
        role_filter = None if role == "All" else role
        try:
            users = self._service.list_users(role=role_filter)
            for u in users:
                active = "Yes" if u.get("is_active") else "No"
                self._tree.insert("", tk.END, iid=u.get("id"), values=(
                    u.get("id", ""), u.get("username", ""), u.get("role", ""),
                    u.get("display_name", ""), u.get("email", ""),
                    active, u.get("last_login", ""),
                ))
            self._status_var.set(f"{len(users)} user(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load users: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a user first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _UserDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_user(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        uid = self._selected_id()
        if not uid:
            return
        user = self._service.get_user(uid)
        if not user:
            messagebox.showerror("Error", "User not found.")
            return
        dlg = _UserDialog(self, self._db_path, user=user)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_user(uid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        uid = self._selected_id()
        if not uid:
            return
        if not messagebox.askyesno("Confirm", f"Delete user {uid}?"):
            return
        try:
            self._service.delete_user(uid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_reset_password(self):
        uid = self._selected_id()
        if not uid:
            return
        new_pw = simpledialog.askstring("Reset Password", "Enter new password:",
                                        show="*", parent=self)
        if not new_pw:
            return
        try:
            self._service.reset_password(uid, new_pw)
            messagebox.showinfo("Success", "Password has been reset.", parent=self)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
