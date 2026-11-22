import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class UserManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def load_users(self):
        """Load users into management interface"""
        if hasattr(self.gui, 'users_tree') and self.gui.users_tree is not None:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT u.id, u.username, u.role, u.email, u.created_at,
                       ua.is_active
                FROM users u
                LEFT JOIN user_accounts ua ON ua.user_id = u.id
                ORDER BY u.username
                ''')
                users = cursor.fetchall()
                conn.close()

                # Clear existing items
                for item in self.gui.users_tree.get_children():
                    self.gui.users_tree.delete(item)

                if not users:
                    self.gui.users_tree.insert('', 'end', values=(
                        '', _t('gui.shell.document_manager.users.labels.no_users', default="No users found"),
                        '', '', '', ''))
                    return

                # Insert new items
                for user in users:
                    user_id, username, role, email, created_at, is_active = tuple(user)
                    if is_active is None:
                        active = _t('gui.shell.document_manager.users.labels.no_sign_in', default="No sign-in")
                    elif is_active:
                        active = _t('gui.shell.document_manager.users.labels.yes', default="Yes")
                    else:
                        active = _t('gui.shell.document_manager.users.labels.no', default="No")
                    self.gui.users_tree.insert('', 'end', values=(
                        user_id, username, role, email or '', created_at or '', active
                    ))
            except Exception as e:
                logger.error("Error loading users: %s", e)

    # ------------------------------------------------------------------
    # Account actions go through the university UserAuth facade (the same
    # calls the main User Management screen makes), so sign-in accounts in
    # the shared auth, the university profile and the audit trail stay in
    # step.  Nothing here writes the users table directly.
    # ------------------------------------------------------------------

    def _dialog_parent(self):
        tree = getattr(self.gui, 'users_tree', None)
        try:
            if tree is not None and tree.winfo_exists():
                return tree.winfo_toplevel()
        except tk.TclError:
            pass
        return self.root

    def _admin_auth(self):
        """Return the signed-in auth facade with manage_users, or None."""
        parent = self._dialog_parent()
        auth = getattr(self.gui, 'auth', None)
        current = getattr(auth, 'current_user', None) if auth is not None else None
        if not current:
            messagebox.showerror(
                _t('gui.shell.document_manager.users.dialogs.authentication_required', default="Authentication Required"),
                _t('gui.shell.document_manager.users.dialogs.sign_in_to_manage_users',
                   default="Sign in to the university system to manage users."),
                parent=parent)
            return None
        if 'manage_users' not in (current.get('permissions') or []):
            messagebox.showerror(
                _t('gui.shell.document_manager.users.dialogs.permission_denied', default="Permission Denied"),
                _t('gui.shell.document_manager.users.dialogs.manage_users_required',
                   default="You need the 'manage users' permission for this action."),
                parent=parent)
            return None
        return auth

    def _selected_user(self, warning_key, warning_default):
        """(user_id, username) for the selected row, or None after warning."""
        parent = self._dialog_parent()
        tree = getattr(self.gui, 'users_tree', None)
        if tree is None:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 _t('gui.shell.document_manager.users.dialogs.user_list_not_available', default="User list not available"),
                                 parent=parent)
            return None
        selection = tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.shell.document_manager.users.dialogs.no_selection', default="No Selection"),
                                   _t(warning_key, default=warning_default), parent=parent)
            return None
        values = tree.item(selection[0]).get('values') or []
        try:
            return int(values[0]), str(values[1])
        except (IndexError, TypeError, ValueError):
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 _t('gui.shell.document_manager.users.dialogs.could_not_read_user', default="Could not read the selected user."),
                                 parent=parent)
            return None

    @staticmethod
    def _role_choices():
        try:
            from education_system.systems.university.infrastructure.auth.core_utils.constants import ROLES
            return list(ROLES.keys())
        except Exception:
            return ['admin', 'staff', 'instructor', 'student']

    @staticmethod
    def _temporary_password():
        """A temporary password that satisfies the shared strength policy."""
        import secrets
        import string
        pools = [string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%^&*"]
        chars = [secrets.choice(pool) for pool in pools]
        alphabet = ''.join(pools)
        chars += [secrets.choice(alphabet) for _ in range(16 - len(chars))]
        secrets.SystemRandom().shuffle(chars)
        return ''.join(chars)

    def _user_form(self, title, initial=None, include_username=True):
        """Modal form; returns dict of entered values or None if cancelled."""
        parent = self._dialog_parent()
        initial = initial or {}
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.transient(parent)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill='both', expand=True)

        entries = {}
        fields = [('first_name', _t('gui.shell.document_manager.users.labels.first_name', default="First name:")),
                  ('last_name', _t('gui.shell.document_manager.users.labels.last_name', default="Last name:")),
                  ('email', _t('gui.shell.document_manager.users.labels.email', default="Email:"))]
        if include_username:
            fields.insert(0, ('username', _t('gui.shell.document_manager.users.labels.username', default="Username:")))
        row = 0
        for key, label in fields:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=4)
            entry = ttk.Entry(frame, width=32)
            entry.insert(0, initial.get(key) or '')
            entry.grid(row=row, column=1, pady=4, padx=(10, 0))
            entries[key] = entry
            row += 1
        ttk.Label(frame, text=_t('gui.shell.document_manager.users.labels.role', default="Role:")).grid(row=row, column=0, sticky='w', pady=4)
        role_var = tk.StringVar(value=initial.get('role') or 'student')
        ttk.Combobox(frame, textvariable=role_var, values=self._role_choices(),
                     state='readonly', width=29).grid(row=row, column=1, pady=4, padx=(10, 0))
        row += 1
        status = ttk.Label(frame, text='', foreground='red')
        status.grid(row=row, column=0, columnspan=2, pady=(6, 0))
        row += 1

        result = {}

        def submit():
            values = {k: e.get().strip() for k, e in entries.items()}
            values['role'] = role_var.get().strip()
            if not all(values.values()):
                status.config(text=_t('gui.shell.document_manager.users.labels.all_fields_required', default="All fields are required."))
                return
            result.update(values)
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(buttons, text=_t('gui.shell.document_manager.users.buttons.save', default="Save"), command=submit).pack(side='left', padx=5)
        ttk.Button(buttons, text=_t('gui.shell.document_manager.users.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)
        first = entries.get('username') or entries['first_name']
        first.focus_set()
        dialog.grab_set()
        dialog.wait_window()
        return result or None

    def add_user(self):
        """Add new user"""
        auth = self._admin_auth()
        if auth is None:
            return
        values = self._user_form(_t('gui.shell.document_manager.users.windows.add_user', default="Add User"))
        if not values:
            return
        parent = self._dialog_parent()
        temp_password = self._temporary_password()
        try:
            created = auth.create_user(values['username'], temp_password, values['email'],
                                       values['first_name'], values['last_name'], values['role'],
                                       password_reset_required=True)
        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 f"Could not create user: {e}", parent=parent)
            return
        if not created:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 _t('gui.shell.document_manager.users.dialogs.create_failed',
                                    default="The user could not be created (the username or email may already be in use)."),
                                 parent=parent)
            return
        self.gui.log_event('create', 'user', details={'username': values['username'], 'role': values['role']})
        self.load_users()
        messagebox.showinfo(_t('gui.shell.document_manager.users.dialogs.user_created', default="User Created"),
                            f"User '{values['username']}' created.\n\n"
                            f"Temporary password: {temp_password}\n\n"
                            "They must change it at first sign-in.", parent=parent)

    def edit_user(self):
        """Edit selected user"""
        picked = self._selected_user('gui.shell.document_manager.users.dialogs.please_select_a_user_to_edit',
                                     "Please select a user to edit")
        if picked is None:
            return
        auth = self._admin_auth()
        if auth is None:
            return
        user_id, username = picked
        parent = self._dialog_parent()
        try:
            user = auth.get_user(user_id=user_id)
        except Exception as e:
            user = None
            logger.debug("get_user failed: %s", e)
        if not user:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 f"User '{username}' has no university account record to edit.", parent=parent)
            return
        user = dict(user)
        values = self._user_form(f"Edit User - {username}", initial=user, include_username=False)
        if not values:
            return
        changes = {k: v for k, v in values.items() if v != (user.get(k) or '')}
        if not changes:
            return
        try:
            ok = auth.update_user(user_id, **changes)
        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 f"Could not update user: {e}", parent=parent)
            return
        if not ok:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 _t('gui.shell.document_manager.users.dialogs.update_failed',
                                    default="The update was refused (invalid role/email, or the email is already in use)."),
                                 parent=parent)
            return
        self.gui.log_event('update', 'user', entity_id=user_id, details={'username': username, 'fields': sorted(changes)})
        self.load_users()
        messagebox.showinfo(_t('gui.shell.document_manager.users.dialogs.user_updated', default="User Updated"),
                            f"User '{username}' updated.", parent=parent)

    def reset_user_password(self):
        """Reset user password"""
        picked = self._selected_user('gui.shell.document_manager.users.dialogs.please_select_a_user_to_reset_password',
                                     "Please select a user to reset password")
        if picked is None:
            return
        auth = self._admin_auth()
        if auth is None:
            return
        user_id, username = picked
        parent = self._dialog_parent()
        if not messagebox.askyesno(_t('gui.shell.document_manager.users.dialogs.reset_password', default="Reset Password"),
                                   f"Unlock '{username}' and issue a temporary password?\n"
                                   "Their current sessions will be signed out.", parent=parent):
            return
        current = auth.current_user or {}
        try:
            result = auth.reset_password(username, current.get('user_id') or current.get('id'),
                                         temporary_password=self._temporary_password())
        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 f"Password reset failed: {e}", parent=parent)
            return
        if not result:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 f"Password reset failed for '{username}'.", parent=parent)
            return
        temp = result.get('temp_password') if isinstance(result, dict) else None
        emailed = result.get('email_sent') if isinstance(result, dict) else False
        self.gui.log_event('password_reset', 'user', entity_id=user_id, details={'username': username})
        message = f"Password for '{username}' has been reset and the account unlocked."
        if temp:
            message += f"\n\nTemporary password: {temp}"
        if emailed:
            message += "\n\nThe temporary password was also e-mailed to the user."
        message += "\n\nThey must change it at next sign-in."
        messagebox.showinfo(_t('gui.shell.document_manager.users.dialogs.password_reset', default="Password Reset"),
                            message, parent=parent)

    def deactivate_user(self):
        """Deactivate selected user"""
        picked = self._selected_user('gui.shell.document_manager.users.dialogs.please_select_a_user_to_deactivate',
                                     "Please select a user to deactivate")
        if picked is None:
            return
        auth = self._admin_auth()
        if auth is None:
            return
        user_id, username = picked
        parent = self._dialog_parent()
        if not messagebox.askyesno(_t('gui.shell.document_manager.users.dialogs.deactivate_user', default="Deactivate User"),
                                   f"Deactivate '{username}'? They will no longer be able to sign in.",
                                   parent=parent):
            return
        try:
            ok = auth.deactivate_user(user_id)
        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 f"Could not deactivate user: {e}", parent=parent)
            return
        if not ok:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"),
                                 _t('gui.shell.document_manager.users.dialogs.deactivate_refused',
                                    default="Deactivation was refused (your own account, the last administrator, or no sign-in account)."),
                                 parent=parent)
            return
        self.gui.log_event('deactivate', 'user', entity_id=user_id, details={'username': username})
        self.load_users()
        messagebox.showinfo(_t('gui.shell.document_manager.users.dialogs.user_deactivated', default="User Deactivated"),
                            f"User '{username}' has been deactivated.", parent=parent)

    def ensure_login(self, required_role=None):
        """
        Ensure user is logged in with optional role check

        Args:
            required_role: Required role (e.g., 'admin', 'staff') or None for any logged-in user

        Returns:
            bool: True if user is logged in (and has required role), False otherwise

        Raises:
            PermissionError: If role check fails
        """
        try:
            # Check if authenticated
            if not self.gui.check_authentication():
                messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.authentication_required', default="Authentication Required"),
                                   _t('gui.shell.document_manager.users.dialogs.you_must_be_logged_in_to_perform_this_action', default="You must be logged in to perform this action."))
                return False

            # Check role if required
            if required_role:
                user_role = self.gui.current_user.get('role', '').lower()
                required_role_lower = required_role.lower()

                # Admin has access to everything
                if user_role == 'admin':
                    return True

                # Check specific role
                if user_role != required_role_lower:
                    messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.permission_denied', default="Permission Denied"),
                                       f"This action requires '{required_role}' role.\n"
                                       f"Your role: '{user_role}'")
                    raise PermissionError(f"User role '{user_role}' does not have access "
                                        f"(required: '{required_role}')")

            # Log the access
            self.gui.log_event('access', 'system', details={
                'action': 'ensure_login',
                'required_role': required_role,
                'user_role': self.gui.current_user.get('role', 'unknown')
            })

            return True

        except PermissionError:
            raise
        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.users.dialogs.error', default="Error"), f"Authentication check failed: {e}")
            return False
