# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

# Alias for translation function
from education_system.university_system.core.i18n import get_text as _t

# Import database connection
from education_system.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction

logger = logging.getLogger(__name__)

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_gui_context,
    )
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

def show_user_management(self):
    """Show user management interface"""
    if not self.auth.current_user or 'manage_users' not in self.auth.current_user.get('permissions', []):
        messagebox.showerror(_t("user_management_gui.errors.access_denied_title"), _t("user_management_gui.errors.access_denied_message"))
        return

    self.clear_content()

    ttk.Label(self.content_frame, text=_t("user_management_gui.title"), font=('Arial', 14, 'bold')).grid(row=0, column=0, pady=(0, 20))

    # User list frame
    list_frame = ttk.LabelFrame(self.content_frame, text=_t("user_management_gui.users_frame.title"), padding="10")
    list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

    # Create treeview for users
    columns = ('ID', 'Username', 'Name', 'Role', 'Status')
    self.user_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

    # Column header translations
    column_translations = {
        'ID': _t("user_management_gui.columns.id"),
        'Username': _t("user_management_gui.columns.username"),
        'Name': _t("user_management_gui.columns.name"),
        'Role': _t("user_management_gui.columns.role"),
        'Status': _t("user_management_gui.columns.status")
    }
    for col in columns:
        self.user_tree.heading(col, text=column_translations.get(col, col))
        self.user_tree.column(col, width=120)

    user_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.user_tree.yview)
    self.user_tree.configure(yscrollcommand=user_scrollbar.set)

    self.user_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
    user_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=(0, 10))

    # Load users
    self.refresh_user_list()

    # Buttons frame
    button_frame = ttk.Frame(self.content_frame)
    button_frame.grid(row=2, column=0, pady=10)

    ttk.Button(button_frame, text=_t("user_management_gui.buttons.create_user"), command=self.show_create_user).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("user_management_gui.buttons.view_details"), command=self.show_user_details).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("user_management_gui.buttons.edit_user"), command=self.show_edit_user).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("user_management_gui.buttons.reset_password"), command=self.reset_user_password).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("user_management_gui.buttons.refresh"), command=self.refresh_user_list).pack(side=tk.LEFT, padx=5)
def refresh_user_list(self):
    """Refresh the user list"""
    if not hasattr(self, 'user_tree'):
        return

    # Clear existing items
    for item in self.user_tree.get_children():
        self.user_tree.delete(item)

    # Load users
    try:
        users = self.auth.list_users()
        if users is None:
            self.user_tree.insert('', tk.END, values=(_t("user_management_gui.status.error"), _t("user_management_gui.errors.no_permission_or_failed"), '', '', ''))
            return

        if not users:
            self.user_tree.insert('', tk.END, values=(_t("user_management_gui.status.info"), _t("user_management_gui.messages.no_users_found"), '', '', ''))
            return

        for user in users:
            try:
                # Ensure user is a dict (convert from sqlite3.Row if needed)
                if not isinstance(user, dict):
                    user = dict(user)

                # Safely extract fields with defaults
                user_id = str(user.get('id', ''))
                username = str(user.get('username', ''))
                first_name = str(user.get('first_name', ''))
                last_name = str(user.get('last_name', ''))
                full_name = f"{first_name} {last_name}".strip() or _t("user_management_gui.status.not_available")
                role = str(user.get('role', _t("user_management_gui.status.unknown")))
                status = _t("user_management_gui.status.active") if user.get('is_active', True) else _t("user_management_gui.status.inactive")

                self.user_tree.insert('', tk.END, values=(
                    user_id,
                    username,
                    full_name,
                    role,
                    status
                ))
            except Exception as row_error:
                # Insert error row for this specific user
                self.user_tree.insert('', tk.END, values=(
                    _t("user_management_gui.status.error"),
                    _t("user_management_gui.errors.failed_to_display_user", error=str(row_error)[:50]),
                    '', '', ''
                ))
    except Exception as e:
        import traceback
        error_msg = _t("user_management_gui.errors.failed_to_load", error=str(e))
        self.user_tree.insert('', tk.END, values=(_t("user_management_gui.status.error"), error_msg, '', '', ''))
        print(f"User list error: {e}")
        print(traceback.format_exc())
def show_create_user(self):
    """Show create user dialog"""
    create_window = tk.Toplevel(self.root)
    _install_clean_close(create_window)
    create_window.title(_t("user_management_gui.create_user.window_title"))
    create_window.geometry("500x400")
    create_window.transient(self.root)
    create_window.grab_set()

    main_frame = ttk.Frame(create_window, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text=_t("user_management_gui.create_user.title"), font=('Arial', 14, 'bold')).grid(row=0, column=0, columnspan=2, pady=(0, 20))

    # Form fields
    fields = {}

    ttk.Label(main_frame, text=_t("user_management_gui.labels.username")).grid(row=1, column=0, sticky=tk.W, pady=5)
    fields['username'] = ttk.Entry(main_frame, width=30)
    fields['username'].grid(row=1, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text=_t("user_management_gui.labels.email")).grid(row=2, column=0, sticky=tk.W, pady=5)
    fields['email'] = ttk.Entry(main_frame, width=30)
    fields['email'].grid(row=2, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text=_t("user_management_gui.labels.first_name")).grid(row=3, column=0, sticky=tk.W, pady=5)
    fields['first_name'] = ttk.Entry(main_frame, width=30)
    fields['first_name'].grid(row=3, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text=_t("user_management_gui.labels.last_name")).grid(row=4, column=0, sticky=tk.W, pady=5)
    fields['last_name'] = ttk.Entry(main_frame, width=30)
    fields['last_name'].grid(row=4, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text=_t("user_management_gui.labels.role")).grid(row=5, column=0, sticky=tk.W, pady=5)
    role_var = tk.StringVar()
    role_combo = ttk.Combobox(main_frame, textvariable=role_var, width=27)
    try:
        role_combo['values'] = list(ROLES.keys()) if 'ROLES' in globals() else ['admin', 'staff', 'student', 'instructor']
    except Exception:
        role_combo['values'] = ['admin', 'staff', 'student', 'instructor']
    role_combo.grid(row=5, column=1, pady=5, padx=(10, 0))
    role_combo.set('student')

    status_label = ttk.Label(main_frame, text="", foreground="red")
    status_label.grid(row=6, column=0, columnspan=2, pady=10)

    def create_user():
        username = fields['username'].get().strip()
        email = fields['email'].get().strip()
        first_name = fields['first_name'].get().strip()
        last_name = fields['last_name'].get().strip()
        role = role_var.get()

        if not all([username, email, first_name, last_name, role]):
            status_label.config(text=_t("user_management_gui.errors.all_fields_required"))
            return

        # Generate temporary password
        import secrets
        import string
        temp_password = ''.join(secrets.choices(string.ascii_letters + string.digits, k=12))

        try:
            if self.auth.create_user(username, temp_password, email, first_name, last_name, role, password_reset_required=True):
                # Immutable audit log for user creation
                if IMMUTABLE_AUDIT_AVAILABLE:
                    admin_user_id, session_id = get_gui_context(self.auth)
                    safe_log_security_event(
                        action=AuditAction.USER_CREATE,
                        user_id=admin_user_id,
                        resource_type='user',
                        session_id=session_id,
                        details={'new_username': username, 'role': role, 'email': email}
                    )
                create_window.destroy()
                messagebox.showinfo(_t("user_management_gui.messages.success_title"), _t("user_management_gui.create_user.success_message", password=temp_password))
                self.refresh_user_list()
            else:
                status_label.config(text=_t("user_management_gui.errors.failed_to_create_user"))
        except Exception as e:
            status_label.config(text=_t("user_management_gui.errors.error_with_message", error=str(e)))

    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=7, column=0, columnspan=2, pady=10)

    ttk.Button(button_frame, text=_t("user_management_gui.buttons.create_user"), command=create_user).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("user_management_gui.buttons.cancel"), command=create_window.destroy).pack(side=tk.LEFT, padx=5)

    fields['username'].focus()

def show_user_details(self):
    """Show details for selected user"""
    selection = self.user_tree.selection()
    if not selection:
        messagebox.showwarning(_t("user_management_gui.errors.no_selection_title"), _t("user_management_gui.errors.select_user_to_view"))
        return

    item = self.user_tree.item(selection[0])
    user_id = item['values'][0]

    # Get user details
    users = self.auth.list_users()
    user = None
    for u in users:
        if str(u['id']) == str(user_id):
            user = u
            break

    if not user:
        messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.user_not_found"))
        return

    # Show user details in new window
    details_window = tk.Toplevel(self.root)
    _install_clean_close(details_window)
    details_window.title(_t("user_management_gui.user_details.window_title", username=user['username']))
    details_window.geometry("600x500")
    details_window.transient(self.root)

    text_widget = scrolledtext.ScrolledText(details_window, wrap=tk.WORD)
    text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    active_status = _t("user_management_gui.status.yes") if user.get('is_active', True) else _t("user_management_gui.status.no")
    student_id_value = user.get('student_id', _t("user_management_gui.status.not_available"))
    created_value = user.get('created_at', _t("user_management_gui.status.unknown"))
    last_login_value = user.get('last_login', _t("user_management_gui.status.never"))

    details_text = f"""{_t("user_management_gui.user_details.header")}
{'='*50}

{_t("user_management_gui.user_details.id_label")}: {user['id']}
{_t("user_management_gui.user_details.username_label")}: {user['username']}
{_t("user_management_gui.user_details.email_label")}: {user['email']}
{_t("user_management_gui.user_details.name_label")}: {user['first_name']} {user['last_name']}
{_t("user_management_gui.user_details.role_label")}: {user['role']}
{_t("user_management_gui.user_details.active_label")}: {active_status}
{_t("user_management_gui.user_details.student_id_label")}: {student_id_value}
{_t("user_management_gui.user_details.created_label")}: {created_value}
{_t("user_management_gui.user_details.last_login_label")}: {last_login_value}

{_t("user_management_gui.user_details.permissions_header")}:
{'='*50}
"""

    for perm in user.get('permissions', []):
        details_text += f"• {perm}\n"

    text_widget.insert(tk.END, details_text)
    text_widget.config(state=tk.DISABLED)

def show_edit_user(self):
    """Show edit user dialog"""
    if not hasattr(self, 'user_tree'):
        messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.user_list_not_available"))
        return

    selection = self.user_tree.selection()
    if not selection:
        messagebox.showwarning(_t("user_management_gui.errors.no_selection_title"), _t("user_management_gui.errors.select_user_to_edit"))
        return

    item = self.user_tree.item(selection[0])
    user_values = item.get('values', [])
    if not user_values:
        messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.could_not_retrieve_user_data"))
        return

    username = user_values[0]

    # Create edit dialog
    dialog = tk.Toplevel(self.root)
    _install_clean_close(dialog)
    dialog.title(_t("user_management_gui.edit_user.window_title", username=username))
    dialog.geometry("500x600")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text=_t("user_management_gui.edit_user.title", username=username),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Get current user data
    try:
        # Use auth system to get user info if available
        if self.auth:
            user_info = self.auth.get_user_by_username(username)
            if not user_info:
                messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.user_not_found"))
                dialog.destroy()
                return
            # Convert to tuple format for compatibility
            user_data = (
                user_info.get('username'),
                user_info.get('email'),
                user_info.get('first_name'),
                user_info.get('last_name'),
                user_info.get('role'),
                user_info.get('is_active', 1),
                user_info.get('student_id')
            )
            user_id = user_info.get('id')
        else:
            # Fallback to direct DB access
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role, u.is_active, u.student_id
                FROM users u
                WHERE u.username = ?
            ''', (username,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.user_not_found"))
                dialog.destroy()
                return

            user_id = result[0]
            user_data = result[1:]

    except Exception as e:
        messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.failed_to_load_user_data", error=str(e)))
        dialog.destroy()
        return

    # Create form fields
    fields_frame = ttk.Frame(main_frame)
    fields_frame.pack(fill=tk.BOTH, expand=True)

    fields = {}

    # Email
    ttk.Label(fields_frame, text=_t("user_management_gui.labels.email")).grid(row=0, column=0, sticky=tk.W, pady=5)
    fields['email'] = ttk.Entry(fields_frame, width=40)
    fields['email'].grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
    _safe_entry_insert(fields['email'], user_data[1])

    # First Name
    ttk.Label(fields_frame, text=_t("user_management_gui.labels.first_name")).grid(row=1, column=0, sticky=tk.W, pady=5)
    fields['first_name'] = ttk.Entry(fields_frame, width=40)
    fields['first_name'].grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))
    _safe_entry_insert(fields['first_name'], user_data[2])

    # Last Name
    ttk.Label(fields_frame, text=_t("user_management_gui.labels.last_name")).grid(row=2, column=0, sticky=tk.W, pady=5)
    fields['last_name'] = ttk.Entry(fields_frame, width=40)
    fields['last_name'].grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))
    _safe_entry_insert(fields['last_name'], user_data[3])

    # Role
    ttk.Label(fields_frame, text=_t("user_management_gui.labels.role")).grid(row=3, column=0, sticky=tk.W, pady=5)
    role_var = tk.StringVar(value=user_data[4])
    role_combo = ttk.Combobox(fields_frame, textvariable=role_var,
                              values=['admin', 'student', 'lecturer', 'staff'],
                              state='readonly', width=37)
    role_combo.grid(row=3, column=1, sticky=tk.W, pady=5, padx=(10, 0))

    # Active Status
    active_var = tk.BooleanVar(value=bool(user_data[5]))
    ttk.Checkbutton(fields_frame, text=_t("user_management_gui.labels.account_active"), variable=active_var).grid(
        row=4, column=1, sticky=tk.W, pady=10, padx=(10, 0))

    def save_changes():
        try:
            new_email = fields['email'].get().strip()
            new_first_name = fields['first_name'].get().strip()
            new_last_name = fields['last_name'].get().strip()
            new_role = role_var.get()
            new_active = active_var.get()

            # Track old values for logging
            old_role = user_data[4]
            old_active = bool(user_data[5])

            # Use auth system to update user if available
            if self.auth:
                success = self.auth.update_user(
                    user_id,
                    email=new_email,
                    first_name=new_first_name,
                    last_name=new_last_name,
                    role=new_role,
                    is_active=new_active
                )

                if not success:
                    messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.failed_to_update_via_auth"))
                    return
            else:
                # Fallback to direct DB access
                conn = get_db_connection()
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    UPDATE users
                    SET email = ?, first_name = ?, last_name = ?, role = ?, is_active = ?, updated_at = ?
                    WHERE username = ?
                ''', (
                    new_email,
                    new_first_name,
                    new_last_name,
                    new_role,
                    1 if new_active else 0,
                    timestamp,
                    username
                ))
                conn.commit()
                conn.close()

            # Log activity
            changes = {}
            if new_email != user_data[1]:
                changes['email'] = {'old': user_data[1], 'new': new_email}
            if new_first_name != user_data[2]:
                changes['first_name'] = {'old': user_data[2], 'new': new_first_name}
            if new_last_name != user_data[3]:
                changes['last_name'] = {'old': user_data[3], 'new': new_last_name}
            if new_role != old_role:
                changes['role'] = {'old': old_role, 'new': new_role}
            if new_active != old_active:
                changes['is_active'] = {'old': old_active, 'new': new_active}

            if ACTIVITY_LOGGER_AVAILABLE and changes:
                log_activity('update', 'user', user_id=user_id, details={'username': username, 'changes': changes})

            # Immutable audit log for user update
            if IMMUTABLE_AUDIT_AVAILABLE and changes:
                admin_user_id, session_id = get_gui_context(self.auth)
                safe_log_security_event(
                    action=AuditAction.USER_UPDATE,
                    user_id=admin_user_id,
                    resource_type='user',
                    resource_id=str(user_id),
                    session_id=session_id,
                    details={'target_username': username, 'changes': changes}
                )

            messagebox.showinfo(_t("user_management_gui.messages.success_title"), _t("user_management_gui.edit_user.success_message", username=username))
            self.refresh_user_list()
            dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.failed_to_update_user", error=str(e)))

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text=_t("user_management_gui.buttons.save_changes"), command=save_changes,
              style="Accent.TButton").pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("user_management_gui.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)
def reset_user_password(self):
    """Reset password for selected user"""
    if not hasattr(self, 'user_tree'):
        messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.user_list_not_available"))
        return

    selection = self.user_tree.selection()
    if not selection:
        messagebox.showwarning(_t("user_management_gui.errors.no_selection_title"), _t("user_management_gui.errors.select_user_to_reset_password"))
        return

    item = self.user_tree.item(selection[0])
    user_values = item.get('values', [])
    if not user_values:
        messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.could_not_retrieve_user_data"))
        return

    username = user_values[0]

    # Create password reset dialog
    dialog = tk.Toplevel(self.root)
    _install_clean_close(dialog)
    dialog.title(_t("user_management_gui.reset_password.window_title", username=username))
    dialog.geometry("450x300")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text=_t("user_management_gui.reset_password.title", username=username),
             font=('Arial', 12, 'bold')).pack(pady=(0, 20))

    # Password fields
    fields_frame = ttk.Frame(main_frame)
    fields_frame.pack(fill=tk.X, pady=10)

    ttk.Label(fields_frame, text=_t("user_management_gui.labels.new_password")).grid(row=0, column=0, sticky=tk.W, pady=5)
    password_entry = ttk.Entry(fields_frame, width=30, show='*')
    password_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))

    ttk.Label(fields_frame, text=_t("user_management_gui.labels.confirm_password")).grid(row=1, column=0, sticky=tk.W, pady=5)
    confirm_entry = ttk.Entry(fields_frame, width=30, show='*')
    confirm_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))

    # Show password checkbox
    show_password_var = tk.BooleanVar()
    def toggle_password():
        show_char = '' if show_password_var.get() else '*'
        password_entry.config(show=show_char)
        confirm_entry.config(show=show_char)

    ttk.Checkbutton(fields_frame, text=_t("user_management_gui.labels.show_passwords"), variable=show_password_var,
                   command=toggle_password).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))

    status_label = ttk.Label(main_frame, text="", foreground="red")
    status_label.pack(pady=10)

    def perform_reset():
        new_password = password_entry.get()
        confirm_password = confirm_entry.get()

        if not new_password:
            status_label.config(text=_t("user_management_gui.errors.password_cannot_be_empty"))
            return

        if len(new_password) < 6:
            status_label.config(text=_t("user_management_gui.errors.password_too_short"))
            return

        if new_password != confirm_password:
            status_label.config(text=_t("user_management_gui.errors.passwords_do_not_match"))
            return

        try:
            import hashlib
            import secrets

            conn = get_db_connection()
            cursor = conn.cursor()

            # Get user ID
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            user_record = cursor.fetchone()

            if not user_record:
                status_label.config(text=_t("user_management_gui.errors.user_not_found"))
                return

            user_id = user_record[0]

            # Generate new password hash
            salt = secrets.token_hex(16)
            key = hashlib.pbkdf2_hmac('sha256', new_password.encode(), salt.encode(), 100000, dklen=64)
            password_hash = key.hex()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Update password
            cursor.execute('''
                UPDATE user_accounts
                SET password_hash = ?, salt = ?, updated_at = ?
                WHERE user_id = ?
            ''', (password_hash, salt, timestamp, user_id))

            conn.commit()
            conn.close()

            # Immutable audit log for password reset
            if IMMUTABLE_AUDIT_AVAILABLE:
                admin_user_id, session_id = get_gui_context(self.auth)
                safe_log_security_event(
                    action=AuditAction.PASSWORD_RESET,
                    user_id=admin_user_id,
                    resource_type='user',
                    resource_id=str(user_id),
                    session_id=session_id,
                    details={'target_username': username, 'reset_by': 'admin'}
                )

            messagebox.showinfo(_t("user_management_gui.messages.success_title"), _t("user_management_gui.reset_password.success_message", username=username))
            dialog.destroy()

        except Exception as e:
            status_label.config(text=_t("user_management_gui.errors.error_with_message", error=str(e)))

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text=_t("user_management_gui.buttons.reset_password"), command=perform_reset,
              style="Accent.TButton").pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("user_management_gui.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)
def view_all_users(self):
    """View all users in the system"""
    try:
        users_window = tk.Toplevel(self.root)
        _install_clean_close(users_window)
        users_window.title(_t("user_management_gui.view_all_users.window_title"))
        users_window.geometry("900x600")

        # Create treeview
        tree_frame = ttk.Frame(users_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("ID", "Username", "Email", "Role", "Status")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")

        # Column header translations
        column_translations = {
            'ID': _t("user_management_gui.columns.id"),
            'Username': _t("user_management_gui.columns.username"),
            'Email': _t("user_management_gui.columns.email"),
            'Role': _t("user_management_gui.columns.role"),
            'Status': _t("user_management_gui.columns.status")
        }
        for col in columns:
            tree.heading(col, text=column_translations.get(col, col))
            tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load users from database
        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute("SELECT id, username, email, role, 'Active' FROM users ORDER BY username")
            for row in cursor.fetchall():
                # Convert sqlite3.Row to tuple for proper display
                tree.insert("", tk.END, values=tuple(row))

        ttk.Button(users_window, text=_t("user_management_gui.buttons.close"), command=users_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.failed_to_view_users", error=str(e)))
def add_new_user(self):
    """Add a new user to the system — opens the create-user form directly."""
    try:
        # show_create_user builds its own Toplevel with username / email / name
        # / role fields, generates a temp password, calls auth.create_user and
        # audit-logs the creation. It needs a user_tree to refresh on success,
        # so make sure the user management panel exists first.
        if not hasattr(self, 'user_tree'):
            self.show_user_management()
        self.show_create_user()
    except Exception as e:
        messagebox.showerror(_t("user_management_gui.errors.error_title"), _t("user_management_gui.errors.failed_to_add_user", error=str(e)))

def manage_permissions(self):
    """Manage role-level permissions.

    Opens a modal window with a role selector on the left and a searchable,
    scrollable checkbox list of every known permission on the right. Loading a
    role populates its current grants; Save diffs the checkbox state against
    what's in the DB and calls PermissionManager.grant_role_permission /
    revoke_role_permission for each change. All changes are activity-logged and
    audit-logged (PERMISSION_GRANT / PERMISSION_REVOKE).
    """
    if not self.auth.current_user or 'manage_roles' not in self.auth.current_user.get('permissions', []):
        messagebox.showerror(
            _t("user_management_gui.errors.access_denied_title"),
            _t("user_management_gui.manage_permissions.errors.manage_roles_required"),
        )
        return

    try:
        pm = self.auth.permission_manager
        roles = pm.list_roles()
        all_permissions = pm.list_permissions() or []
        if not roles or not all_permissions:
            messagebox.showerror(
                _t("user_management_gui.errors.error_title"),
                _t("user_management_gui.manage_permissions.errors.load_failed"),
            )
            return

        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title(_t("user_management_gui.manage_permissions.window_title"))
        window.geometry("900x640")
        window.transient(self.root)
        window.grab_set()

        ttk.Label(
            window,
            text=_t("user_management_gui.manage_permissions.title"),
            font=('Arial', 14, 'bold'),
        ).pack(pady=(10, 5))

        body = ttk.Frame(window, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ---- Left: role picker ----
        left = ttk.LabelFrame(body, text=_t("user_management_gui.manage_permissions.roles_frame"), padding=8)
        left.grid(row=0, column=0, sticky='nsw', padx=(0, 10))

        role_var = tk.StringVar()
        role_listbox = tk.Listbox(left, listvariable=role_var, exportselection=False, width=22, height=18)
        role_listbox.pack(fill=tk.Y, expand=True)
        for r in roles:
            role_listbox.insert(tk.END, r['role_name'])

        # ---- Right: permission grid ----
        right = ttk.LabelFrame(body, text=_t("user_management_gui.manage_permissions.permissions_frame"), padding=8)
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        # Search box
        search_row = ttk.Frame(right)
        search_row.grid(row=0, column=0, sticky='ew', pady=(0, 5))
        ttk.Label(search_row, text=_t("user_management_gui.manage_permissions.search_label")).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Count / status line
        status_var = tk.StringVar(value=_t("user_management_gui.manage_permissions.no_role_selected"))
        ttk.Label(right, textvariable=status_var, foreground='#666').grid(row=1, column=0, sticky='w', pady=(0, 5))

        # Scrollable check-button area
        canvas = tk.Canvas(right, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(right, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.grid(row=2, column=0, sticky='nsew')
        vscroll.grid(row=2, column=1, sticky='ns')
        check_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=check_frame, anchor='nw')

        def _reflow_scroll(_event=None):
            canvas.configure(scrollregion=canvas.bbox('all'))
        check_frame.bind('<Configure>', _reflow_scroll)

        # Build the checkbox grid once; we reuse the widgets across role switches.
        perm_vars = {}  # permission_name -> (BooleanVar, Checkbutton)
        for idx, perm in enumerate(all_permissions):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(check_frame, text=perm['permission_name'], variable=var)
            cb.grid(row=idx, column=0, sticky='w', padx=5, pady=1)
            perm_vars[perm['permission_name']] = (var, cb)

        current_role = {'name': None, 'original': set()}

        def _apply_search(*_):
            needle = search_var.get().strip().lower()
            for name, (_var, cb) in perm_vars.items():
                visible = needle in name.lower() if needle else True
                if visible:
                    cb.grid()
                else:
                    cb.grid_remove()
            _reflow_scroll()

        search_var.trace_add('write', _apply_search)

        def _load_role(_event=None):
            sel = role_listbox.curselection()
            if not sel:
                return
            role_name = role_listbox.get(sel[0])
            granted = set(pm.get_role_permissions(role_name))
            current_role['name'] = role_name
            current_role['original'] = granted
            for name, (var, _cb) in perm_vars.items():
                var.set(name in granted)
            status_var.set(_t(
                "user_management_gui.manage_permissions.role_summary",
                role=role_name, count=len(granted), total=len(perm_vars),
            ))

        role_listbox.bind('<<ListboxSelect>>', _load_role)

        # ---- Save / revert / close buttons ----
        footer = ttk.Frame(window, padding=(10, 5))
        footer.pack(fill=tk.X)

        def _revert():
            if not current_role['name']:
                return
            for name, (var, _cb) in perm_vars.items():
                var.set(name in current_role['original'])

        def _save():
            if not current_role['name']:
                messagebox.showinfo(
                    _t("user_management_gui.manage_permissions.window_title"),
                    _t("user_management_gui.manage_permissions.errors.pick_role_first"),
                )
                return
            role_name = current_role['name']
            original = current_role['original']
            new_state = {name for name, (var, _cb) in perm_vars.items() if var.get()}
            to_grant = new_state - original
            to_revoke = original - new_state
            if not to_grant and not to_revoke:
                messagebox.showinfo(
                    _t("user_management_gui.manage_permissions.window_title"),
                    _t("user_management_gui.manage_permissions.no_changes"),
                )
                return

            failed = []
            for p in sorted(to_grant):
                if not pm.grant_role_permission(role_name, p):
                    failed.append(p)
            for p in sorted(to_revoke):
                if not pm.revoke_role_permission(role_name, p):
                    failed.append(p)

            # If the admin edited their own role, refresh the in-memory
            # permissions so subsequent checks see the new state this session.
            if self.auth.current_user and self.auth.current_user.get('role') == role_name:
                try:
                    uid = self.auth.current_user.get('id')
                    if uid is not None:
                        self.auth.current_user['permissions'] = pm.get_user_permissions(uid)
                except Exception:
                    pass

            # Refresh the "original" snapshot so the next diff is accurate.
            current_role['original'] = set(pm.get_role_permissions(role_name))
            status_var.set(_t(
                "user_management_gui.manage_permissions.role_summary",
                role=role_name, count=len(current_role['original']), total=len(perm_vars),
            ))
            if failed:
                messagebox.showwarning(
                    _t("user_management_gui.manage_permissions.window_title"),
                    _t("user_management_gui.manage_permissions.save_partial", failed=", ".join(failed)),
                )
            else:
                messagebox.showinfo(
                    _t("user_management_gui.manage_permissions.window_title"),
                    _t(
                        "user_management_gui.manage_permissions.save_success",
                        role=role_name,
                        granted=len(to_grant),
                        revoked=len(to_revoke),
                    ),
                )

        ttk.Button(footer, text=_t("user_management_gui.manage_permissions.save_button"),
                   command=_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text=_t("user_management_gui.manage_permissions.revert_button"),
                   command=_revert).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text=_t("user_management_gui.buttons.close"),
                   command=window.destroy).pack(side=tk.RIGHT, padx=5)

        # Preselect the first role for convenience.
        role_listbox.selection_set(0)
        _load_role()

    except Exception as e:
        logger.exception("Manage Permissions window failed")
        messagebox.showerror(
            _t("user_management_gui.errors.error_title"),
            _t("user_management_gui.errors.failed_to_manage_permissions", error=str(e)),
        )
