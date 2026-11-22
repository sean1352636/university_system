"""User Management section and its dialogs.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CONTENT_BG,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class UsersMixin:
    def _show_locked_account_alert(self):
        """Offer an immediate one-use password reset for every locked user."""
        svc = self._get_admin_service()
        if not svc:
            return
        try:
            locked_accounts = svc.get_locked_accounts()
        except Exception:
            return

        for account in locked_accounts:
            username = account.get("username", "")
            display_name = account.get("display_name") or username
            attempts = account.get("failed_login_attempts")
            attempts_text = (
                f" after {attempts} failed login attempts" if attempts is not None else ""
            )
            reset_now = messagebox.askyesno(
                "User Account Locked",
                f"{display_name} ({username}) has been locked out{attempts_text}.\n\n"
                "Set a secure temporary password and unlock this account now?",
                parent=self,
            )
            if not reset_now:
                continue
            try:
                result = self.auth.unlock_and_reset_password(username)
            except Exception as exc:
                messagebox.showerror(
                    "Temporary Password Failed", str(exc), parent=self
                )
                continue
            self._show_temporary_password(result)

        if locked_accounts and self._current_section == "dashboard":
            self._show_section("dashboard")

    def _show_temporary_password(self, result):
        """Display a generated password in a selectable, copyable field."""
        dlg = tk.Toplevel(self)
        dlg.title("Temporary Password Created")
        dlg.geometry("500x255")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        username = result.get("username", "user")
        emailed = result.get("email_sent", False)
        tk.Label(
            dlg,
            text=f"'{username}' is unlocked.",
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(20, 6))
        tk.Label(
            dlg,
            text="Temporary password (the user must change it at next login):",
            font=("Segoe UI", 10),
        ).pack(pady=(0, 8))

        password = result.get("temp_password", "")
        pw_var = tk.StringVar(value=password)
        entry = tk.Entry(
            dlg, textvariable=pw_var, font=("Consolas", 12),
            justify=tk.CENTER, state="readonly", width=34,
        )
        entry.pack(ipady=5)

        status = "A copy was also emailed to the user." if emailed else (
            "Email could not be sent; copy this password and give it to the user securely."
        )
        tk.Label(dlg, text=status, font=("Segoe UI", 9), fg=TEXT_MUTED).pack(pady=9)

        buttons = tk.Frame(dlg)
        buttons.pack()

        def _copy():
            self.clipboard_clear()
            self.clipboard_append(password)
            self.update_idletasks()

        tk.Button(buttons, text="Copy Password", command=_copy, padx=12).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(buttons, text="Done", command=dlg.destroy, padx=18).pack(
            side=tk.LEFT, padx=5
        )
        dlg.wait_window()

    # ------------------------------------------------------------------
    # Section: User Management
    # ------------------------------------------------------------------

    def _build_users(self):
        tk.Label(
            self._content_frame,
            text="User Management",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            self._content_frame,
            text="View and filter all users across every education system.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        # Filter bar
        filter_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        filter_bar.pack(fill=tk.X, padx=24, pady=(0, 8))

        tk.Label(filter_bar, text="System:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        system_var = tk.StringVar(value="All")
        system_combo = ttk.Combobox(
            filter_bar,
            textvariable=system_var,
            values=["All", *SYSTEM_ORDER],
            state="readonly",
            width=14,
        )
        system_combo.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(filter_bar, text="Role:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        role_var = tk.StringVar(value="All")
        role_combo = ttk.Combobox(
            filter_bar,
            textvariable=role_var,
            values=["All", "superadmin", "admin", "staff", "student", "parent"],
            state="readonly",
            width=14,
        )
        role_combo.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(filter_bar, text="Search:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        search_var = tk.StringVar()
        search_entry = tk.Entry(filter_bar, textvariable=search_var, width=22, font=("Segoe UI", 10))
        search_entry.pack(side=tk.LEFT, padx=(0, 8))

        # Treeview
        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 12))

        columns = ("username", "display_name", "email", "systems", "roles", "active", "last_login")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=22)

        headings = {
            "username": ("Username", 120),
            "display_name": ("Display Name", 150),
            "email": ("Email", 180),
            "systems": ("System(s)", 160),
            "roles": ("Role(s)", 130),
            "active": ("Active", 60),
            "last_login": ("Last Login", 140),
        }
        for col, (heading, width) in headings.items():
            tree.heading(col, text=heading)
            tree.column(col, width=width, minwidth=50)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Load data
        all_users = []
        svc = self._get_admin_service()
        if svc:
            try:
                all_users = svc.get_all_users()
            except Exception:
                pass

        def _populate(users_list):
            tree.delete(*tree.get_children())
            for u in users_list:
                sys_list = [s["system_key"] for s in u.get("systems", [])]
                role_list = list({s["role"] for s in u.get("systems", [])})
                tree.insert("", tk.END, values=(
                    u.get("username", ""),
                    u.get("display_name", ""),
                    u.get("email", ""),
                    ", ".join(sys_list),
                    ", ".join(role_list),
                    "Yes" if u.get("is_active") else "No",
                    u.get("last_login", "")[:19] if u.get("last_login") else "",
                ))

        def _apply_filter(*_args):
            sys_filter = system_var.get()
            role_filter = role_var.get()
            search_text = search_var.get().strip().lower()

            filtered = all_users
            if sys_filter and sys_filter != "All":
                filtered = [
                    u for u in filtered
                    if any(s["system_key"] == sys_filter for s in u.get("systems", []))
                ]
            if role_filter and role_filter != "All":
                filtered = [
                    u for u in filtered
                    if any(s["role"] == role_filter for s in u.get("systems", []))
                ]
            if search_text:
                filtered = [
                    u for u in filtered
                    if search_text in (u.get("username", "").lower())
                    or search_text in (u.get("display_name", "").lower())
                    or search_text in (u.get("email", "").lower())
                ]
            _populate(filtered)

        system_combo.bind("<<ComboboxSelected>>", _apply_filter)
        role_combo.bind("<<ComboboxSelected>>", _apply_filter)
        search_entry.bind("<KeyRelease>", _apply_filter)

        filter_btn = tk.Button(
            filter_bar,
            text="Apply",
            font=("Segoe UI", 10),
            bg="#3498db",
            fg=TEXT_LIGHT,
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            command=_apply_filter,
        )
        filter_btn.pack(side=tk.LEFT)

        # Action buttons row
        action_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        action_bar.pack(fill=tk.X, padx=24, pady=(0, 4))

        def _get_selected_user():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No Selection", "Select a user first.")
                return None
            vals = tree.item(sel[0], "values")
            username = vals[0]
            for u in all_users:
                if u.get("username") == username:
                    return u
            return None

        def _on_create_user():
            self._show_create_user_dialog()

        def _on_edit_user():
            user = _get_selected_user()
            if user:
                self._show_edit_user_dialog(user)

        def _on_reset_password():
            user = _get_selected_user()
            if not user:
                return
            new_pw = simpledialog.askstring(
                "Reset Password",
                f"Enter new password for '{user['username']}':",
                show="*",
                parent=self,
            )
            if not new_pw:
                return
            svc2 = self._get_admin_service()
            if svc2:
                try:
                    svc2.reset_password(user["id"], new_pw)
                    messagebox.showinfo("Success", f"Password reset for '{user['username']}'.")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))

        def _on_deactivate():
            user = _get_selected_user()
            if not user:
                return
            if not messagebox.askyesno(
                "Confirm Deactivation",
                f"Deactivate user '{user['username']}'?",
            ):
                return
            svc2 = self._get_admin_service()
            if svc2:
                try:
                    svc2.deactivate_user(user["id"])
                    messagebox.showinfo("Success", f"User '{user['username']}' deactivated.")
                    self._show_section("users")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))

        for btn_text, btn_cmd, btn_color in [
            ("Create User", _on_create_user, "#27ae60"),
            ("Edit User", _on_edit_user, "#2980b9"),
            ("Reset Password", _on_reset_password, "#e67e22"),
            ("Deactivate", _on_deactivate, "#e74c3c"),
        ]:
            tk.Button(
                action_bar,
                text=btn_text,
                font=("Segoe UI", 9),
                bg=btn_color,
                fg=TEXT_LIGHT,
                relief=tk.FLAT,
                cursor="hand2",
                padx=10,
                pady=2,
                command=btn_cmd,
            ).pack(side=tk.LEFT, padx=(0, 6))

        _populate(all_users)

    # ------------------------------------------------------------------
    # User dialogs
    # ------------------------------------------------------------------

    def _show_create_user_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Create User")
        dlg.geometry("420x440")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Create New User", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))

        fields_frame = tk.Frame(dlg)
        fields_frame.pack(padx=20, fill=tk.X)

        entries = {}
        for label_text in ("Username", "Display Name", "Email", "Password"):
            row = tk.Frame(fields_frame)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label_text + ":", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar()
            ent = tk.Entry(row, textvariable=var, font=("Segoe UI", 10), width=28)
            if label_text == "Password":
                ent.configure(show="*")
            ent.pack(side=tk.LEFT)
            entries[label_text.lower().replace(" ", "_")] = var

        # System / role assignments
        tk.Label(dlg, text="System / Role Assignments:", font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W, padx=20, pady=(10, 4)
        )
        sr_frame = tk.Frame(dlg)
        sr_frame.pack(padx=20, fill=tk.X)

        sys_role_vars = []
        for sys_key in SYSTEM_ORDER:
            row = tk.Frame(sr_frame)
            row.pack(fill=tk.X, pady=1)
            enabled_var = tk.BooleanVar(value=False)
            tk.Checkbutton(row, text=SYSTEM_LABELS.get(sys_key, sys_key), variable=enabled_var, width=18, anchor=tk.W).pack(
                side=tk.LEFT
            )
            role_var = tk.StringVar(value="student")
            ttk.Combobox(
                row, textvariable=role_var,
                values=["superadmin", "admin", "staff", "student", "parent"],
                state="readonly", width=12,
            ).pack(side=tk.LEFT, padx=4)
            sys_role_vars.append((sys_key, enabled_var, role_var))

        def _save():
            username = entries["username"].get().strip()
            display_name = entries["display_name"].get().strip()
            email = entries["email"].get().strip()
            password = entries["password"].get()
            if not username or not password:
                messagebox.showwarning("Validation", "Username and password are required.", parent=dlg)
                return
            systems_roles = [
                {"system_key": sk, "role": rv.get()}
                for sk, ev, rv in sys_role_vars if ev.get()
            ]
            svc = self._get_admin_service()
            if svc:
                try:
                    svc.create_user(username, display_name, email, password, systems_roles)
                    messagebox.showinfo("Success", f"User '{username}' created.", parent=dlg)
                    dlg.destroy()
                    self._show_section("users")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc), parent=dlg)

        tk.Button(
            dlg, text="Create", font=("Segoe UI", 11), bg="#27ae60", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, pady=4, cursor="hand2", command=_save,
        ).pack(pady=16)

    def _show_edit_user_dialog(self, user):
        dlg = tk.Toplevel(self)
        dlg.title("Edit User")
        dlg.geometry("420x400")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=f"Edit User: {user['username']}", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))

        fields_frame = tk.Frame(dlg)
        fields_frame.pack(padx=20, fill=tk.X)

        dn_var = tk.StringVar(value=user.get("display_name", ""))
        email_var = tk.StringVar(value=user.get("email", ""))
        active_var = tk.BooleanVar(value=user.get("is_active", True))

        for label_text, var in [("Display Name", dn_var), ("Email", email_var)]:
            row = tk.Frame(fields_frame)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label_text + ":", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
            tk.Entry(row, textvariable=var, font=("Segoe UI", 10), width=28).pack(side=tk.LEFT)

        row = tk.Frame(fields_frame)
        row.pack(fill=tk.X, pady=3)
        tk.Checkbutton(row, text="Active", variable=active_var, font=("Segoe UI", 10)).pack(side=tk.LEFT)

        # System / role editing
        tk.Label(dlg, text="System / Role Assignments:", font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W, padx=20, pady=(10, 4)
        )
        sr_frame = tk.Frame(dlg)
        sr_frame.pack(padx=20, fill=tk.X)

        current_systems = {s["system_key"]: s["role"] for s in user.get("systems", [])}
        sr_vars = []
        for sys_key in SYSTEM_ORDER:
            row = tk.Frame(sr_frame)
            row.pack(fill=tk.X, pady=1)
            enabled_var = tk.BooleanVar(value=sys_key in current_systems)
            tk.Checkbutton(row, text=SYSTEM_LABELS.get(sys_key, sys_key), variable=enabled_var, width=18, anchor=tk.W).pack(
                side=tk.LEFT
            )
            role_var = tk.StringVar(value=current_systems.get(sys_key, "student"))
            ttk.Combobox(
                row, textvariable=role_var,
                values=["superadmin", "admin", "staff", "student", "parent"],
                state="readonly", width=12,
            ).pack(side=tk.LEFT, padx=4)
            sr_vars.append((sys_key, enabled_var, role_var))

        def _save():
            svc = self._get_admin_service()
            if not svc:
                return
            try:
                svc.update_user(
                    user["id"],
                    display_name=dn_var.get().strip() or None,
                    email=email_var.get().strip() or None,
                    is_active=active_var.get(),
                )
                new_sr = [
                    {"system_key": sk, "role": rv.get()}
                    for sk, ev, rv in sr_vars if ev.get()
                ]
                svc.update_user_systems(user["id"], new_sr)
                messagebox.showinfo("Success", "User updated.", parent=dlg)
                dlg.destroy()
                self._show_section("users")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dlg)

        tk.Button(
            dlg, text="Save Changes", font=("Segoe UI", 11), bg="#2980b9", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, pady=4, cursor="hand2", command=_save,
        ).pack(pady=16)
