# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

# Import utility functions
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    _safe_entry_insert,
    _safe_set_combobox,
)

# Import database functions
from education_system.university_system.infrastructure.database.db import get_connection, transaction

# Import activity logger
from education_system.university_system.core.activity_logger import log_activity

# Import i18n
from education_system.university_system.core.i18n import get_text as _t

logger = logging.getLogger(__name__)


def create_staff_dialog(self):
    """Create comprehensive dialog for adding new staff with full form validation"""
    dialog = self.create_themed_toplevel("Create New Staff Member", "600x750")

    # Make dialog visible before grabbing
    dialog.update_idletasks()
    dialog.deiconify()

    try:
        dialog.grab_set()
    except tk.TclError:
        print("Warning: Could not grab dialog focus")

    # Main scrollable frame
    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Create canvas and scrollbar
    canvas = tk.Canvas(main_frame)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Title
    title_label = ttk.Label(scrollable_frame, text=_t("staff.create_staff_title"),
                           font=('Arial', 16, 'bold'))
    title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

    # Form fields
    fields = {}

    # Personal Information Section
    personal_frame = ttk.LabelFrame(scrollable_frame, text=_t("staff.personal_info"), padding=15)
    personal_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    # First Name
    ttk.Label(personal_frame, text=_t("staff.first_name_required")).grid(row=0, column=0, sticky=tk.W, pady=5)
    fields['first_name'] = ttk.Entry(personal_frame, width=30)
    fields['first_name'].grid(row=0, column=1, pady=5, padx=(10, 0))

    # Last Name
    ttk.Label(personal_frame, text=_t("staff.last_name_required")).grid(row=1, column=0, sticky=tk.W, pady=5)
    fields['last_name'] = ttk.Entry(personal_frame, width=30)
    fields['last_name'].grid(row=1, column=1, pady=5, padx=(10, 0))

    # Email
    ttk.Label(personal_frame, text=_t("staff.email_required")).grid(row=2, column=0, sticky=tk.W, pady=5)
    fields['email'] = ttk.Entry(personal_frame, width=30)
    fields['email'].grid(row=2, column=1, pady=5, padx=(10, 0))

    # Account Information Section
    account_frame = ttk.LabelFrame(scrollable_frame, text=_t("staff.account_info"), padding=15)
    account_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    # Username
    ttk.Label(account_frame, text=_t("staff.username_required")).grid(row=0, column=0, sticky=tk.W, pady=5)
    fields['username'] = ttk.Entry(account_frame, width=30)
    fields['username'].grid(row=0, column=1, pady=5, padx=(10, 0))

    # Password
    ttk.Label(account_frame, text=_t("staff.password_required")).grid(row=1, column=0, sticky=tk.W, pady=5)
    fields['password'] = ttk.Entry(account_frame, width=30, show="*")
    fields['password'].grid(row=1, column=1, pady=5, padx=(10, 0))

    # Confirm Password
    ttk.Label(account_frame, text=_t("staff.confirm_password_required")).grid(row=2, column=0, sticky=tk.W, pady=5)
    fields['confirm_password'] = ttk.Entry(account_frame, width=30, show="*")
    fields['confirm_password'].grid(row=2, column=1, pady=5, padx=(10, 0))

    # Role
    ttk.Label(account_frame, text=_t("staff.role_required")).grid(row=3, column=0, sticky=tk.W, pady=5)
    fields['role'] = ttk.Combobox(account_frame, values=['staff', 'instructor', 'admin'],
                                 state='readonly', width=27)
    fields['role'].set('staff')  # Default to staff
    fields['role'].grid(row=3, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    # Show password checkbox
    show_password_var = tk.BooleanVar(value=False)
    def toggle_password_visibility():
        if show_password_var.get():
            fields['password'].config(show="")
            fields['confirm_password'].config(show="")
        else:
            fields['password'].config(show="*")
            fields['confirm_password'].config(show="*")

    ttk.Checkbutton(account_frame, text=_t("staff.show_passwords"),
                   variable=show_password_var,
                   command=toggle_password_visibility).grid(row=4, column=1, sticky=tk.W, pady=5)

    # Validation feedback
    validation_label = ttk.Label(scrollable_frame, text="", foreground="red")
    validation_label.grid(row=3, column=0, columnspan=2, pady=5)

    def validate_form():
        """Validate form inputs"""
        errors = []

        # Check required fields
        if not fields['first_name'].get().strip():
            errors.append(_t("staff.validation.first_name_required"))

        if not fields['last_name'].get().strip():
            errors.append(_t("staff.validation.last_name_required"))

        email = fields['email'].get().strip()
        if not email:
            errors.append(_t("staff.validation.email_required"))
        elif '@' not in email or '.' not in email:
            errors.append(_t("staff.validation.invalid_email_format"))

        username = fields['username'].get().strip()
        if not username:
            errors.append(_t("staff.validation.username_required"))
        elif len(username) < 3:
            errors.append(_t("staff.validation.username_min_length"))

        password = fields['password'].get()
        if not password:
            errors.append(_t("staff.validation.password_required"))
        elif len(password) < 6:
            errors.append(_t("staff.validation.password_min_length"))

        confirm_password = fields['confirm_password'].get()
        if password != confirm_password:
            errors.append(_t("staff.validation.passwords_no_match"))

        if not fields['role'].get():
            errors.append(_t("staff.validation.role_required"))

        return errors

    def create_staff():
        """Create staff account with authentication integration"""
        try:
            # Validate form
            errors = validate_form()
            if errors:
                validation_label.config(text="; ".join(errors))
                return

            validation_label.config(text="")

            # Get form data
            first_name = fields['first_name'].get().strip()
            last_name = fields['last_name'].get().strip()
            email = fields['email'].get().strip()
            username = fields['username'].get().strip()
            password = fields['password'].get()
            role = fields['role'].get()

            # Check if username already exists
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
                if cursor.fetchone():
                    validation_label.config(text=_t("staff.validation.username_exists"))
                    return

                # Check if email already exists
                cursor.execute('SELECT email FROM users WHERE email = ?', (email,))
                if cursor.fetchone():
                    validation_label.config(text=_t("staff.validation.email_exists"))
                    return

            # Hash the password using the same method as the authentication system
            import hashlib
            import secrets

            # Generate salt and hash password (PBKDF2 with 1,000,000 iterations)
            salt = secrets.token_hex(16)
            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt.encode(),
                1_000_000,  # 1 million iterations (OWASP recommendation)
                dklen=64
            )
            password_hash = key.hex()

            # Get current timestamp
            from datetime import datetime as dt
            timestamp = dt.now().strftime('%Y-%m-%d %H:%M:%S')

            # Create staff record in database (using two-table approach)
            with transaction() as conn:
                cursor = conn.cursor()

                # Insert into users table (profile information)
                cursor.execute('''
                    INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (username, first_name, last_name, email, role, timestamp, timestamp))

                user_id = cursor.lastrowid

                # Insert into user_accounts table (authentication information)
                cursor.execute('''
                    INSERT INTO user_accounts (username, password_hash, salt, user_id, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                ''', (username, password_hash, salt, user_id, timestamp, timestamp))

            # Log activity
            log_activity('create', 'staff', user_id=user_id,
                        details={'username': username, 'role': role, 'email': email})

            messagebox.showinfo(_t("common.success"), _t("staff.messages.staff_created_success",
                                          username=username, email=email, role=role))

            # Refresh staff list if method exists
            if hasattr(self, 'view_staff'):
                self.view_staff()

            dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("staff.errors.failed_create_staff", error=str(e)))
            import traceback
            traceback.print_exc()

    # Buttons
    button_frame = ttk.Frame(scrollable_frame)
    button_frame.grid(row=4, column=0, columnspan=2, pady=20)

    ttk.Button(button_frame, text=_t("staff.buttons.create_staff_member"), command=create_staff,
              style="Accent.TButton").pack(side=tk.LEFT, padx=10)
    ttk.Button(button_frame, text=_t("staff.buttons.clear_form"),
              command=lambda: [field.delete(0, tk.END) if hasattr(field, 'delete')
                              else field.set('') for field in fields.values()]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # Pack canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Set focus
    fields['first_name'].focus()

    # Bind mousewheel to canvas
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)


def update_staff_dialog(self, user_id):
    """Update staff member dialog with editing capabilities"""
    dialog = tk.Toplevel(self.root)
    _install_clean_close(dialog)
    dialog.title(f"Update Staff Member (ID: {user_id})")
    dialog.geometry("600x750")
    dialog.transient(self.root)

    # Make dialog visible before grabbing
    dialog.update_idletasks()
    dialog.deiconify()

    try:
        dialog.grab_set()
    except tk.TclError:
        print("Warning: Could not grab dialog focus")

    try:
        # Get current staff data from both tables
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                       COALESCE(ua.is_active, 1) as is_active
                FROM users u
                LEFT JOIN user_accounts ua ON u.id = ua.user_id
                WHERE u.id = ? AND u.role IN ('staff', 'instructor', 'admin')
            ''', (user_id,))
            staff = cursor.fetchone()

            if not staff:
                messagebox.showerror(_t("common.error"), _t("staff.errors.staff_not_found"))
                dialog.destroy()
                return

        # Main scrollable frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Title
        title_label = ttk.Label(scrollable_frame, text=_t("staff.update_staff_title", username=staff[1]),
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Current info display
        current_frame = ttk.LabelFrame(scrollable_frame, text=_t("staff.current_info"), padding=10)
        current_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        current_text = tk.Text(current_frame, height=3, width=60, wrap=tk.WORD)
        current_text.pack(fill=tk.X)
        current_info = f"Username: {staff[1]} | Email: {staff[2]}\nName: {staff[3]} {staff[4]} | Role: {staff[5]}\nStatus: {'Active' if staff[6] else 'Inactive'}"
        current_text.insert(tk.END, current_info)
        current_text.config(state=tk.DISABLED)

        # Form fields
        fields = {}

        # Personal Information Section
        personal_frame = ttk.LabelFrame(scrollable_frame, text=_t("staff.update_personal_info"), padding=15)
        personal_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # First Name
        ttk.Label(personal_frame, text=_t("staff.first_name_required")).grid(row=0, column=0, sticky=tk.W, pady=5)
        fields['first_name'] = ttk.Entry(personal_frame, width=30)
        fields['first_name'].insert(0, staff[3] or '')
        fields['first_name'].grid(row=0, column=1, pady=5, padx=(10, 0))

        # Last Name
        ttk.Label(personal_frame, text=_t("staff.last_name_required")).grid(row=1, column=0, sticky=tk.W, pady=5)
        fields['last_name'] = ttk.Entry(personal_frame, width=30)
        fields['last_name'].insert(0, staff[4] or '')
        fields['last_name'].grid(row=1, column=1, pady=5, padx=(10, 0))

        # Email
        ttk.Label(personal_frame, text=_t("staff.email_required")).grid(row=2, column=0, sticky=tk.W, pady=5)
        fields['email'] = ttk.Entry(personal_frame, width=30)
        fields['email'].insert(0, staff[2] or '')
        fields['email'].grid(row=2, column=1, pady=5, padx=(10, 0))

        # Account Information Section
        account_frame = ttk.LabelFrame(scrollable_frame, text=_t("staff.update_account_info"), padding=15)
        account_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Role
        ttk.Label(account_frame, text=_t("staff.role_required")).grid(row=0, column=0, sticky=tk.W, pady=5)
        fields['role'] = ttk.Combobox(account_frame, values=['staff', 'instructor', 'admin'],
                                     state='readonly', width=27)
        fields['role'].set(staff[5])
        fields['role'].grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)

        # Status
        ttk.Label(account_frame, text=_t("staff.status_required")).grid(row=1, column=0, sticky=tk.W, pady=5)
        fields['is_active'] = ttk.Combobox(account_frame, values=['Active', 'Inactive'],
                                          state='readonly', width=27)
        fields['is_active'].set('Active' if staff[6] else 'Inactive')
        fields['is_active'].grid(row=1, column=1, pady=5, padx=(10, 0), sticky=tk.W)

        # Password Reset Section
        password_frame = ttk.LabelFrame(scrollable_frame, text=_t("staff.reset_password_optional"), padding=15)
        password_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(password_frame, text=_t("staff.new_password_label"), foreground="blue").grid(row=0, column=0, sticky=tk.W, pady=5)
        fields['new_password'] = ttk.Entry(password_frame, width=30, show="*")
        fields['new_password'].grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(password_frame, text=_t("staff.leave_blank_keep_password"),
                 font=('Arial', 8), foreground="gray").grid(row=1, column=0, columnspan=2, sticky=tk.W)

        # Show password checkbox
        show_password_var = tk.BooleanVar(value=False)
        def toggle_password_visibility():
            if show_password_var.get():
                fields['new_password'].config(show="")
            else:
                fields['new_password'].config(show="*")

        ttk.Checkbutton(password_frame, text=_t("staff.show_password"),
                       variable=show_password_var,
                       command=toggle_password_visibility).grid(row=2, column=1, sticky=tk.W, pady=5)

        # Validation feedback
        validation_label = ttk.Label(scrollable_frame, text="", foreground="red")
        validation_label.grid(row=5, column=0, columnspan=2, pady=5)

        def update_staff():
            """Update staff member information"""
            try:
                errors = []

                # Validate required fields
                first_name = fields['first_name'].get().strip()
                if not first_name:
                    errors.append(_t("staff.validation.first_name_required"))

                last_name = fields['last_name'].get().strip()
                if not last_name:
                    errors.append(_t("staff.validation.last_name_required"))

                email = fields['email'].get().strip()
                if not email:
                    errors.append(_t("staff.validation.email_required"))
                elif '@' not in email or '.' not in email:
                    errors.append(_t("staff.validation.invalid_email_format"))

                role = fields['role'].get()
                if not role:
                    errors.append(_t("staff.validation.role_required"))

                new_password = fields['new_password'].get()
                if new_password and len(new_password) < 6:
                    errors.append(_t("staff.validation.password_min_length"))

                if errors:
                    validation_label.config(text="; ".join(errors))
                    return

                validation_label.config(text="")

                # Check if email is taken by another user
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT id FROM users WHERE email = ? AND id != ?', (email, user_id))
                    if cursor.fetchone():
                        validation_label.config(text=_t("staff.validation.email_exists_other_user"))
                        return

                is_active = 1 if fields['is_active'].get() == 'Active' else 0

                # Update staff record in both tables
                with transaction() as conn:
                    cursor = conn.cursor()
                    from datetime import datetime as dt
                    timestamp = dt.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Update basic info in users table
                    cursor.execute('''
                        UPDATE users
                        SET first_name = ?, last_name = ?, email = ?, role = ?, updated_at = ?
                        WHERE id = ?
                    ''', (first_name, last_name, email, role, timestamp, user_id))

                    # Update is_active status in user_accounts table
                    cursor.execute('''
                        UPDATE user_accounts
                        SET is_active = ?, updated_at = ?
                        WHERE user_id = ?
                    ''', (is_active, timestamp, user_id))

                    # Update password if provided
                    if new_password:
                        import hashlib
                        import secrets
                        from datetime import datetime as dt

                        # Generate new salt and hash password (PBKDF2 with 1,000,000 iterations)
                        salt = secrets.token_hex(16)
                        key = hashlib.pbkdf2_hmac(
                            'sha256',
                            new_password.encode(),
                            salt.encode(),
                            1_000_000,
                            dklen=64
                        )
                        password_hash = key.hex()
                        timestamp = dt.now().strftime('%Y-%m-%d %H:%M:%S')

                        # Update password in user_accounts table
                        cursor.execute('''
                            UPDATE user_accounts
                            SET password_hash = ?, salt = ?, updated_at = ?
                            WHERE user_id = ?
                        ''', (password_hash, salt, timestamp, user_id))

                # Log activity
                log_activity('update', 'staff', user_id=user_id,
                           details={'role': role, 'email': email, 'is_active': is_active,
                                   'password_changed': bool(new_password)})

                messagebox.showinfo(_t("common.success"), _t("staff.messages.staff_updated_success", username=staff[1]))

                # Refresh staff list
                if hasattr(self, 'view_staff'):
                    self.view_staff()

                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("staff.errors.failed_update_staff", error=str(e)))
                import traceback
                traceback.print_exc()

        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t("staff.buttons.update_staff_member"), command=update_staff,
                  style="Accent.TButton").pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("staff.errors.failed_load_staff", error=str(e)))
        dialog.destroy()


def view_staff(self):
    """View and manage all staff members"""
    self.clear_content()

    # Title
    title_label = ttk.Label(self.content_frame, text=_t("staff.staff_management_title"),
                           font=('Arial', 16, 'bold'))
    title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky=tk.W)

    # Action buttons frame
    action_frame = ttk.Frame(self.content_frame)
    action_frame.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

    ttk.Button(action_frame, text=_t("staff.buttons.create_new_staff"),
              command=lambda: self.create_staff_dialog(),
              style="Accent.TButton").pack(side=tk.LEFT, padx=5)
    ttk.Button(action_frame, text=_t("staff.buttons.refresh_list"),
              command=lambda: self.view_staff()).pack(side=tk.LEFT, padx=5)

    # Search frame
    search_frame = ttk.LabelFrame(self.content_frame, text=_t("staff.search_staff"), padding=10)
    search_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT, padx=5)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)

    def perform_search():
        search_term = search_var.get().strip()
        populate_tree(search_term)

    ttk.Button(search_frame, text=_t("common.search"), command=perform_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(search_frame, text=_t("common.clear"),
              command=lambda: (search_var.set(''), populate_tree(''))).pack(side=tk.LEFT, padx=5)

    # Staff tree
    tree_frame = ttk.Frame(self.content_frame)
    tree_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

    # Configure grid weight
    self.content_frame.rowconfigure(3, weight=1)
    self.content_frame.columnconfigure(0, weight=1)

    # Create treeview with scrollbars
    tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical")
    tree_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal")

    staff_tree = ttk.Treeview(tree_frame,
                             columns=('ID', 'Username', 'Email', 'Name', 'Role', 'Status', 'Created'),
                             show='headings',
                             yscrollcommand=tree_scroll_y.set,
                             xscrollcommand=tree_scroll_x.set)

    tree_scroll_y.config(command=staff_tree.yview)
    tree_scroll_x.config(command=staff_tree.xview)

    # Define headings
    staff_tree.heading('ID', text=_t("staff.columns.id"))
    staff_tree.heading('Username', text=_t("staff.columns.username"))
    staff_tree.heading('Email', text=_t("staff.columns.email"))
    staff_tree.heading('Name', text=_t("staff.columns.full_name"))
    staff_tree.heading('Role', text=_t("staff.columns.role"))
    staff_tree.heading('Status', text=_t("staff.columns.status"))
    staff_tree.heading('Created', text=_t("staff.columns.created_date"))

    # Define column widths
    staff_tree.column('ID', width=50)
    staff_tree.column('Username', width=120)
    staff_tree.column('Email', width=200)
    staff_tree.column('Name', width=180)
    staff_tree.column('Role', width=100)
    staff_tree.column('Status', width=80)
    staff_tree.column('Created', width=150)

    # Grid layout
    staff_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    tree_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
    tree_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))

    tree_frame.rowconfigure(0, weight=1)
    tree_frame.columnconfigure(0, weight=1)

    def populate_tree(search_term=''):
        """Populate tree with staff data"""
        # Clear existing items
        for item in staff_tree.get_children():
            staff_tree.delete(item)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                if search_term:
                    cursor.execute('''
                        SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                               COALESCE(ua.is_active, 1) as is_active, u.created_at
                        FROM users u
                        LEFT JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.role IN ('staff', 'instructor', 'admin')
                        AND (u.username LIKE ? OR u.email LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ?)
                        ORDER BY u.created_at DESC
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                else:
                    cursor.execute('''
                        SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                               COALESCE(ua.is_active, 1) as is_active, u.created_at
                        FROM users u
                        LEFT JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.role IN ('staff', 'instructor', 'admin')
                        ORDER BY u.created_at DESC
                    ''')

                staff_members = cursor.fetchall()

                for staff in staff_members:
                    user_id, username, email, first_name, last_name, role, is_active, created_at = staff
                    full_name = f"{first_name or ''} {last_name or ''}".strip()
                    status = "Active" if is_active else "Inactive"

                    # Format date
                    try:
                        from datetime import datetime
                        date_obj = datetime.fromisoformat(created_at.replace(' ', 'T'))
                        formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                    except (ValueError, TypeError):
                        formatted_date = created_at

                    staff_tree.insert('', 'end', values=(
                        user_id, username, email or 'N/A', full_name or 'N/A',
                        role.capitalize(), status, formatted_date
                    ))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("staff.errors.failed_load_staff_data", error=str(e)))

    # Context menu
    def show_context_menu(event):
        """Show context menu on right-click"""
        item = staff_tree.identify_row(event.y)
        if item:
            staff_tree.selection_set(item)
            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label=_t("staff.context_menu.edit_staff_member"), command=edit_selected)
            context_menu.add_command(label=_t("staff.context_menu.delete_staff_member"), command=delete_selected)
            context_menu.add_separator()
            context_menu.add_command(label=_t("staff.context_menu.view_details"), command=view_selected_details)
            context_menu.post(event.x_root, event.y_root)

    def edit_selected():
        """Edit selected staff member"""
        selection = staff_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff.warnings.no_selection"), _t("staff.warnings.select_staff_to_edit"))
            return

        item = staff_tree.item(selection[0])
        user_id = item['values'][0]
        self.update_staff_dialog(user_id)

    def delete_selected():
        """Delete selected staff member"""
        selection = staff_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff.warnings.no_selection"), _t("staff.warnings.select_staff_to_delete"))
            return

        item = staff_tree.item(selection[0])
        user_id = item['values'][0]
        username = item['values'][1]

        if messagebox.askyesno(_t("staff.confirm_delete_title"),
                              f"Are you sure you want to delete staff member '{username}'?\n\n"
                              f"This action cannot be undone!"):
            try:
                with transaction() as conn:
                    cursor = conn.cursor()
                    # Delete from user_accounts first (authentication data)
                    cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
                    # Delete from users table (profile data)
                    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))

                log_activity('delete', 'staff', user_id=user_id,
                           details={'username': username})

                messagebox.showinfo(_t("common.success"), _t("staff.messages.staff_deleted_success", username=username))
                populate_tree()

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("staff.errors.failed_delete_staff", error=str(e)))

    def view_selected_details():
        """View detailed information about selected staff member"""
        selection = staff_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff.warnings.no_selection"), _t("staff.warnings.select_staff_to_view"))
            return

        item = staff_tree.item(selection[0])
        values = item['values']

        details = f"""
Staff Member Details:
─────────────────────────────────
ID: {values[0]}
Username: {values[1]}
Email: {values[2]}
Full Name: {values[3]}
Role: {values[4]}
Status: {values[5]}
Created: {values[6]}
        """

        messagebox.showinfo(_t("staff.staff_details_title"), details.strip())

    # Bind events
    staff_tree.bind('<Button-3>', show_context_menu)
    staff_tree.bind('<Double-1>', lambda e: edit_selected())

    # Button frame for actions
    button_frame = ttk.Frame(self.content_frame)
    button_frame.grid(row=4, column=0, columnspan=2, pady=10, sticky=tk.W)

    ttk.Button(button_frame, text=_t("staff.buttons.edit_selected"), command=edit_selected).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("staff.buttons.delete_selected"), command=delete_selected).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("staff.buttons.view_details"), command=view_selected_details).pack(side=tk.LEFT, padx=5)

    # Initial population
    populate_tree()


def delete_staff_dialog(self):
    """Quick delete staff dialog with search"""
    dialog = self.create_themed_toplevel("Delete Staff Member", "500x400")

    # Title
    title_label = ttk.Label(dialog, text=_t("staff.delete_staff_title"),
                           font=('Arial', 16, 'bold'))
    title_label.pack(pady=20)

    # Warning
    warning_label = ttk.Label(dialog,
                             text=_t("staff.delete_warning"),
                             foreground="red", font=('Arial', 12, 'bold'))
    warning_label.pack(pady=10)

    # Search frame
    search_frame = ttk.LabelFrame(dialog, text=_t("staff.search_staff_member"), padding=15)
    search_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(search_frame, text=_t("staff.username_or_email_label")).pack(anchor=tk.W, pady=5)
    search_entry = ttk.Entry(search_frame, width=40)
    search_entry.pack(fill=tk.X, pady=5)

    # Results listbox
    results_frame = ttk.LabelFrame(dialog, text=_t("staff.search_results"), padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    results_listbox = tk.Listbox(results_frame, height=8)
    results_listbox.pack(fill=tk.BOTH, expand=True)

    staff_data = []  # Store staff data for selection

    def search_staff():
        """Search for staff members"""
        search_term = search_entry.get().strip()
        if not search_term:
            messagebox.showwarning(_t("staff.warnings.empty_search"), _t("staff.warnings.enter_username_email"))
            return

        results_listbox.delete(0, tk.END)
        staff_data.clear()

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, first_name, last_name, role
                    FROM users
                    WHERE role IN ('staff', 'instructor', 'admin')
                    AND (username LIKE ? OR email LIKE ?)
                ''', (f'%{search_term}%', f'%{search_term}%'))

                results = cursor.fetchall()

                if not results:
                    results_listbox.insert(tk.END, "No staff members found")
                else:
                    for staff in results:
                        user_id, username, email, first_name, last_name, role = staff
                        full_name = f"{first_name or ''} {last_name or ''}".strip()
                        display = f"{username} - {email} ({role}) - {full_name}"
                        results_listbox.insert(tk.END, display)
                        staff_data.append(staff)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("staff.errors.search_failed", error=str(e)))

    def delete_selected():
        """Delete selected staff member"""
        selection = results_listbox.curselection()
        if not selection:
            messagebox.showwarning(_t("staff.warnings.no_selection"), _t("staff.warnings.select_from_results"))
            return

        idx = selection[0]
        if idx >= len(staff_data):
            return

        staff = staff_data[idx]
        user_id, username = staff[0], staff[1]

        if messagebox.askyesno(_t("staff.confirm_delete_title"),
                              f"Delete staff member '{username}'?\n\n"
                              f"This action CANNOT be undone!"):
            try:
                with transaction() as conn:
                    cursor = conn.cursor()
                    # Delete from user_accounts first (authentication data)
                    cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
                    # Delete from users table (profile data)
                    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))

                log_activity('delete', 'staff', user_id=user_id,
                           details={'username': username})

                messagebox.showinfo(_t("common.success"), _t("staff.messages.staff_deleted_success", username=username))
                dialog.destroy()

                # Refresh staff list if viewing
                if hasattr(self, 'view_staff'):
                    self.view_staff()

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("staff.errors.failed_to_delete", error=str(e)))

    # Buttons
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Button(button_frame, text=_t("common.search"), command=search_staff,
              style="Accent.TButton").pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("staff.buttons.delete_selected"), command=delete_selected).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    search_entry.focus()
    search_entry.bind('<Return>', lambda e: search_staff())


def search_staff_dialog(self):
    """Search staff members dialog"""
    dialog = self.create_themed_toplevel("Search Staff Members", "700x500")

    # Title
    title_label = ttk.Label(dialog, text=_t("staff.search_staff_title"),
                           font=('Arial', 16, 'bold'))
    title_label.pack(pady=20)

    # Search frame
    search_frame = ttk.LabelFrame(dialog, text=_t("staff.search_criteria"), padding=15)
    search_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(search_frame, text=_t("staff.search_by_label")).grid(row=0, column=0, sticky=tk.W, pady=5)

    search_by_var = tk.StringVar(value="username")
    search_options = [
        (_t("staff.search_options.username"), "username"),
        (_t("staff.search_options.email"), "email"),
        (_t("staff.search_options.name"), "name"),
        (_t("staff.search_options.role"), "role")
    ]

    for i, (text, value) in enumerate(search_options):
        ttk.Radiobutton(search_frame, text=text, variable=search_by_var,
                       value=value).grid(row=0, column=i+1, padx=5)

    ttk.Label(search_frame, text=_t("staff.search_term_label")).grid(row=1, column=0, sticky=tk.W, pady=5)
    search_entry = ttk.Entry(search_frame, width=50)
    search_entry.grid(row=1, column=1, columnspan=4, sticky=(tk.W, tk.E), pady=5)

    # Results frame
    results_frame = ttk.LabelFrame(dialog, text=_t("staff.search_results"), padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Results tree
    tree_scroll = ttk.Scrollbar(results_frame, orient="vertical")
    results_tree = ttk.Treeview(results_frame,
                                columns=('ID', 'Username', 'Email', 'Name', 'Role', 'Status'),
                                show='headings',
                                yscrollcommand=tree_scroll.set)
    tree_scroll.config(command=results_tree.yview)

    results_tree.heading('ID', text=_t("staff.columns.id"))
    results_tree.heading('Username', text=_t("staff.columns.username"))
    results_tree.heading('Email', text=_t("staff.columns.email"))
    results_tree.heading('Name', text=_t("staff.columns.full_name"))
    results_tree.heading('Role', text=_t("staff.columns.role"))
    results_tree.heading('Status', text=_t("staff.columns.status"))

    results_tree.column('ID', width=50)
    results_tree.column('Username', width=120)
    results_tree.column('Email', width=180)
    results_tree.column('Name', width=150)
    results_tree.column('Role', width=100)
    results_tree.column('Status', width=80)

    results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def perform_search():
        """Perform search based on criteria"""
        # Clear existing results
        for item in results_tree.get_children():
            results_tree.delete(item)

        search_by = search_by_var.get()
        search_term = search_entry.get().strip()

        if not search_term:
            messagebox.showwarning(_t("staff.warnings.empty_search"), _t("staff.warnings.enter_search_term"))
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                if search_by == "username":
                    query = """
                        SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                               COALESCE(ua.is_active, 1) as is_active
                        FROM users u
                        LEFT JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.role IN ('staff', 'instructor', 'admin') AND u.username LIKE ?
                    """
                elif search_by == "email":
                    query = """
                        SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                               COALESCE(ua.is_active, 1) as is_active
                        FROM users u
                        LEFT JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.role IN ('staff', 'instructor', 'admin') AND u.email LIKE ?
                    """
                elif search_by == "name":
                    query = """
                        SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                               COALESCE(ua.is_active, 1) as is_active
                        FROM users u
                        LEFT JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.role IN ('staff', 'instructor', 'admin')
                        AND (u.first_name LIKE ? OR u.last_name LIKE ?)
                    """
                    cursor.execute(query, (f'%{search_term}%', f'%{search_term}%'))
                    results = cursor.fetchall()
                else:  # role
                    query = """
                        SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                               COALESCE(ua.is_active, 1) as is_active
                        FROM users u
                        LEFT JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.role IN ('staff', 'instructor', 'admin') AND u.role LIKE ?
                    """

                if search_by != "name":
                    cursor.execute(query, (f'%{search_term}%',))
                    results = cursor.fetchall()

                for staff in results:
                    user_id, username, email, first_name, last_name, role, is_active = staff
                    full_name = f"{first_name or ''} {last_name or ''}".strip()
                    status = "Active" if is_active else "Inactive"

                    results_tree.insert('', 'end', values=(
                        user_id, username, email or 'N/A', full_name or 'N/A',
                        role.capitalize(), status
                    ))

                if not results:
                    messagebox.showinfo(_t("staff.no_results_title"), _t("staff.no_staff_found"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("staff.errors.search_failed", error=str(e)))

    # Buttons
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Button(button_frame, text=_t("common.search"), command=perform_search,
              style="Accent.TButton").pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.clear"),
              command=lambda: [results_tree.delete(*results_tree.get_children()), search_entry.delete(0, tk.END)]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.close"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    search_entry.focus()
    search_entry.bind('<Return>', lambda e: perform_search())
