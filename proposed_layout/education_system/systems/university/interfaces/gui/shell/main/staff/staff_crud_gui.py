# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import install_clean_close as _install_clean_close

# Import utility functions
from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import (
    _safe_entry_insert,
    _safe_set_combobox,
)

# Import database functions
from education_system.systems.university.infrastructure.database.db import get_connection, transaction

# Import activity logger
from education_system.systems.university.infrastructure.activity_logger import log_activity

# Import i18n
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

import secrets
import string


def _fetch_hr_profile_staff(search_term='', exclude_usernames=None):
    """Return HR staff who have a ``staff_profiles`` record but no local
    university ``users`` account, so "View Staff Members" can show them too.

    Names/email are resolved from the shared ``auth.db`` (where these staff's
    identities live). Returns a list of dicts with the same fields the staff
    tree renders, plus ``department``. These rows are account-less, so they are
    tagged in the tree and are not editable/deletable from this screen.
    """
    exclude = {str(u).lower() for u in (exclude_usernames or set())}
    rows = []
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            profiles = cursor.execute('''
                SELECT user_id, department, job_title, hire_date
                FROM staff_profiles
                ORDER BY user_id
            ''').fetchall()
    except Exception:
        return rows

    # Resolve display_name/email from the shared auth database.
    identities = {}
    usernames = [str(p[0]) for p in profiles if str(p[0]).lower() not in exclude]
    if usernames:
        try:
            from education_system.platform.identity.auth.db import connect
            auth_conn = connect()
            try:
                placeholders = ','.join('?' * len(usernames))
                for r in auth_conn.execute(
                    'SELECT username, display_name, email FROM users '
                    f'WHERE username IN ({placeholders})',  # nosec B608 - placeholders only
                    tuple(usernames),
                ).fetchall():
                    identities[str(r['username'])] = (
                        r['display_name'] or '', r['email'] or '')
            finally:
                auth_conn.close()
        except Exception:
            identities = {}

    term = search_term.lower().strip()
    for user_id, department, job_title, hire_date in profiles:
        username = str(user_id)
        if username.lower() in exclude:
            continue
        display_name, email = identities.get(username, ('', ''))
        full_name = display_name or username
        # Apply the same search filter the users query uses.
        if term and term not in (
            username.lower() + ' ' + full_name.lower() + ' ' + (email or '').lower()
            + ' ' + (department or '').lower()
        ):
            continue
        rows.append({
            'id': username,               # username, not a numeric users.id
            'username': username,
            'email': email or 'N/A',
            'full_name': full_name or 'N/A',
            'role': job_title or 'Staff',
            'department': department or '',
            'status': 'HR Profile',
            'created': hire_date or '',
        })
    return rows


def _generate_temp_password(length=12):
    """Generate a secure temporary password that meets strength requirements
    (at least one upper, lower, digit and special character)."""
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("@#$%&!?")
    remaining = ''.join(secrets.choice(string.ascii_letters + string.digits + "@#$%&!?")
                        for _ in range(max(0, length - 4)))
    chars = list(upper + lower + digit + special + remaining)
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)


def _generate_unique_username(cursor, first_name, last_name):
    """Build a ``firstname.lastname`` username (lowercase, no spaces), appending
    a counter until it is unique in the ``users`` table."""
    clean_first = first_name.lower().strip().replace(' ', '')
    clean_last = last_name.lower().strip().replace(' ', '')
    base = f"{clean_first}.{clean_last}".strip('.')
    if not base:
        base = 'staff'
    candidate = base
    counter = 1
    while cursor.execute('SELECT 1 FROM users WHERE username = ?', (candidate,)).fetchone():
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


def _create_shared_auth_account(username, password, display_name, email, role):
    """Create the shared-auth (``auth.db``) account for a staff member.

    Staff and instructors sign in through the universal login window, which
    authenticates against the shared ``auth.db`` — a local-only ``user_accounts``
    row cannot log in there ("unknown user"). Mirrors the instructor-creation
    path (``_create_instructor_account``). Returns the shared user id, or None
    if creation failed (e.g. weak password or a duplicate username in auth.db).
    """
    try:
        from education_system.platform.identity.auth.core import UserAuth as SharedUserAuth
        shared_auth = SharedUserAuth()
        return shared_auth.create_user(
            username=username,
            password=password,
            display_name=display_name,
            email=email,
            systems=[("university", role)],
        )
    except Exception as e:
        logger.warning("Could not create shared-auth account for '%s': %s", username, e)
        return None


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

    # Role
    ttk.Label(account_frame, text=_t("staff.role_required")).grid(row=0, column=0, sticky=tk.W, pady=5)
    fields['role'] = ttk.Combobox(account_frame, values=['staff', 'instructor', 'admin'],
                                 state='readonly', width=27)
    fields['role'].set('staff')  # Default to staff
    fields['role'].grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    # Username and a temporary password are generated automatically and emailed
    # to the staff member — no manual entry.
    ttk.Label(
        account_frame,
        text=_t("staff.auto_credentials_note",
                default="A username and temporary password will be generated "
                        "automatically and emailed to the staff member."),
        foreground="gray", wraplength=380, justify=tk.LEFT,
    ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

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

        # Username and password are generated automatically — nothing to validate.

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
            role = fields['role'].get()

            # Auto-generate a temporary password (emailed to the staff member).
            password = _generate_temp_password()

            # Check email uniqueness and generate a unique username.
            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT email FROM users WHERE email = ?', (email,))
                if cursor.fetchone():
                    validation_label.config(text=_t("staff.validation.email_exists"))
                    return

                username = _generate_unique_username(cursor, first_name, last_name)

            # Hash the password using the same method as the authentication system
            import hashlib

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

                # Insert into user_accounts table (authentication information).
                # password_reset_required = 1 forces a change of the emailed temp
                # password on first login (honoured by both the legacy and the
                # universal login flows).
                cursor.execute('''
                    INSERT INTO user_accounts (username, password_hash, salt, user_id, is_active, password_reset_required, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, 1, ?, ?)
                ''', (username, password_hash, salt, user_id, timestamp, timestamp))

            # Log activity
            log_activity('create', 'staff', user_id=user_id,
                        details={'username': username, 'role': role, 'email': email})

            # Create the shared-auth (auth.db) account so the member can sign in
            # through the universal login window (which authenticates against
            # auth.db, not the local user_accounts table). Without this the login
            # fails with "unknown user". Runs after the transaction commits.
            login_note = ""
            shared_uid = _create_shared_auth_account(
                username, password, f"{first_name} {last_name}", email, role,
            )
            if shared_uid is None:
                login_note = ("\n\n⚠ Could not create the sign-in account automatically — "
                              "the staff member may be unable to log in until this is resolved.")

            # If this staff member is an instructor, also create their scheduling
            # record (instructors table) via the unified service so they appear
            # in course/module scheduling pickers. The users/user_accounts rows
            # were already created above, so we skip those stores and staff CRUD's
            # own auth handling — this only backfills the instructors row.
            # Runs *after* the transaction() block commits so the service's own
            # BEGIN IMMEDIATE doesn't contend with an open write lock.
            instructor_note = ""
            if role == 'instructor':
                try:
                    from education_system.systems.university.domain.academics.services.course_management.instructor_service import (
                        create_instructor as create_instructor_service,
                    )
                    res = create_instructor_service(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        register_as_staff=False,   # users/user_accounts already created above
                        create_login=False,        # staff CRUD manages its own local auth
                        send_welcome_email=False,
                    )
                    if not res.ok:
                        instructor_note = f"\n\nNote: scheduling record was not created: {res.error}"
                except Exception as exc:
                    instructor_note = f"\n\nNote: scheduling record was not created: {exc}"

            # Send a welcome email carrying the generated credentials.
            email_note = ""
            try:
                from education_system.systems.university.infrastructure.email import send_template_email
                try:
                    from education_system.systems.university.infrastructure.defaults import UNIVERSITY_EMAIL_DOMAIN
                except ImportError:
                    UNIVERSITY_EMAIL_DOMAIN = "university.edu"

                sent = send_template_email(
                    'user_management/staff_welcome',
                    email,
                    {
                        'first_name': first_name,
                        'last_name': last_name,
                        'username': username,
                        'email': email,
                        'role': role,
                        'temp_password': password,
                        'email_domain': UNIVERSITY_EMAIL_DOMAIN,
                    },
                )
                email_note = (f"\n\nWelcome email sent to {email}." if sent
                              else "\n\nWelcome email could not be sent — share the credentials below manually.")
            except Exception as exc:
                logger.warning("Staff welcome email failed: %s", exc)
                email_note = "\n\nWelcome email could not be sent — share the credentials below manually."

            messagebox.showinfo(
                _t("common.success"),
                _t("staff.messages.staff_created_success", username=username, email=email, role=role)
                + f"\n\nUsername: {username}\nTemporary Password: {password}"
                + email_note
                + login_note
                + instructor_note,
            )

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

        # Passwords are no longer typed by hand — resetting generates a new
        # temporary password and emails it to the staff member.
        reset_password_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            password_frame,
            text=_t("staff.reset_password_checkbox",
                    default="Generate a new temporary password and email it to the staff member"),
            variable=reset_password_var,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)

        ttk.Label(password_frame,
                  text=_t("staff.reset_password_hint",
                          default="Leave unchecked to keep the current password. The staff "
                                  "member will be required to change the temporary password "
                                  "on next login."),
                  font=('Arial', 8), foreground="gray", wraplength=420, justify=tk.LEFT
                  ).grid(row=1, column=0, columnspan=2, sticky=tk.W)

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

                # Optionally reset the password to a new auto-generated temp value.
                reset_requested = reset_password_var.get()
                new_temp_password = _generate_temp_password() if reset_requested else None

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

                    # Reset password if requested (auto-generated temp password).
                    if reset_requested:
                        import hashlib

                        # Generate new salt and hash password (PBKDF2 with 1,000,000 iterations)
                        salt = secrets.token_hex(16)
                        key = hashlib.pbkdf2_hmac(
                            'sha256',
                            new_temp_password.encode(),
                            salt.encode(),
                            1_000_000,
                            dklen=64
                        )
                        password_hash = key.hex()

                        # Update password and force a change on next login.
                        cursor.execute('''
                            UPDATE user_accounts
                            SET password_hash = ?, salt = ?, password_reset_required = 1, updated_at = ?
                            WHERE user_id = ?
                        ''', (password_hash, salt, timestamp, user_id))

                # Log activity
                log_activity('update', 'staff', user_id=user_id,
                           details={'role': role, 'email': email, 'is_active': is_active,
                                   'password_reset': reset_requested})

                # Email the new temporary password if one was generated.
                email_note = ""
                if reset_requested:
                    try:
                        from education_system.systems.university.infrastructure.email import send_template_email
                        try:
                            from education_system.systems.university.infrastructure.defaults import UNIVERSITY_EMAIL_DOMAIN
                        except ImportError:
                            UNIVERSITY_EMAIL_DOMAIN = "university.edu"

                        sent = send_template_email(
                            'user_management/staff_password_reset',
                            email,
                            {
                                'first_name': first_name,
                                'last_name': last_name,
                                'username': staff[1],
                                'temp_password': new_temp_password,
                                'email_domain': UNIVERSITY_EMAIL_DOMAIN,
                            },
                        )
                        email_note = (f"\n\nNew temporary password emailed to {email}." if sent
                                      else f"\n\nEmail could not be sent — share manually.\n"
                                           f"Temporary Password: {new_temp_password}")
                    except Exception as exc:
                        logger.warning("Staff password-reset email failed: %s", exc)
                        email_note = (f"\n\nEmail could not be sent — share manually.\n"
                                      f"Temporary Password: {new_temp_password}")

                messagebox.showinfo(_t("common.success"),
                    _t("staff.messages.staff_updated_success", username=staff[1]) + email_note)

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

    # HR-profile staff (no login account) are shown with a subtle tint so it's
    # clear they're managed under Staff HR, not editable on this screen.
    staff_tree.tag_configure('hrprofile', background='#eef2f7')

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

                shown_usernames = set()
                for staff in staff_members:
                    user_id, username, email, first_name, last_name, role, is_active, created_at = staff
                    full_name = f"{first_name or ''} {last_name or ''}".strip()
                    status = "Active" if is_active else "Inactive"
                    shown_usernames.add(str(username).lower())

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
                    ), tags=('account',))

            # Append HR-profile staff who have no local user account so they
            # appear in the list too (account-less, hence not editable here).
            for hr in _fetch_hr_profile_staff(search_term, shown_usernames):
                staff_tree.insert('', 'end', values=(
                    hr['id'], hr['username'], hr['email'], hr['full_name'],
                    hr['role'], hr['status'], hr['created'],
                ), tags=('hrprofile',))

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
        if 'hrprofile' in item.get('tags', ()):
            messagebox.showinfo(
                _t("common.info", default="Info"),
                "This staff member has an HR profile but no login account, so "
                "they can't be edited here. Manage them under Staff HR "
                "→ Directory.")
            return
        user_id = item['values'][0]
        self.update_staff_dialog(user_id)

    def delete_selected():
        """Delete selected staff member"""
        selection = staff_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff.warnings.no_selection"), _t("staff.warnings.select_staff_to_delete"))
            return

        item = staff_tree.item(selection[0])
        if 'hrprofile' in item.get('tags', ()):
            messagebox.showinfo(
                _t("common.info", default="Info"),
                "This staff member has an HR profile but no login account, so "
                "there's nothing to delete here. Manage them under Staff HR "
                "→ Directory.")
            return
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
