"""
Cinema Booking System - Staff Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
import hashlib
from datetime import datetime

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.cinema.gui.cinema_gui.database import DB_FILE
from education_system.university_system.modules.domain.cinema.gui.cinema_gui.constants import STAFF_ROLES

# Email support (optional)
try:
    from education_system.university_system.infrastructure.email import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs):
        pass
    render_template = None

def show_staff_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.staff.title"), style="Subtitle.TLabel").pack(pady=10)
    roles_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    roles_frame.pack(fill="x", pady=10)
    tk.Label(roles_frame, text=_t("cinema.staff.roles"), font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    for role, info in STAFF_ROLES.items():
        tk.Label(roles_frame, text=f"{role.title()}: {info['description']}", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text="+ Add Staff", style="Success.TButton", command=self.add_staff).pack(side="left", padx=5)
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)
    columns = ("ID", "Username", "Name", "Role", "Email", "Status")
    self.staff_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        self.staff_tree.heading(col, text=col)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM staff ORDER BY name")
        for row in cursor.fetchall():
            self.staff_tree.insert("", "end", values=(row[0], row[1], row[3], row[6].title(), row[4] or "-", row[9].upper()))
    finally:
        conn.close()
    self.staff_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.staff_tree.yview)
    self.staff_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

def _hash_staff_password(self, password, salt=None):
    """
    Hash a password with a salt using PBKDF2.
    Uses 1,000,000 iterations as recommended by OWASP for PBKDF2-SHA256.
    Matches the university auth system standard.
    """
    import secrets
    if salt is None:
        salt = secrets.token_hex(16)

    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        1_000_000,  # OWASP recommended iterations
        dklen=64
    )
    return salt, key.hex()

def _send_staff_welcome_email(self, name, email, username, role):
    """Send welcome email to new staff member."""
    if not email or not EMAIL_AVAILABLE:
        return False
    try:
        # Render email from template
        subject, body = render_template('commerce/cinema/staff_welcome', {
            'staff_name': name,
            'username': username,
            'role': role,
            'start_date': datetime.now().strftime('%Y-%m-%d')
        })

        # Fallback if template not found
        if not subject or not body:
            subject = "Welcome to University Cinema Staff"
            body = f"""Dear {name},

Welcome to the University Cinema team!

Your staff account has been created with the following details:

Username: {username}
Role: {role}
Start Date: {datetime.now().strftime('%Y-%m-%d')}

Please log in to the Cinema Management System using your provided credentials.
For security reasons, please change your password after your first login.

Important Information:
- Your shifts will be assigned by the manager
- Please review the staff handbook available in the break room
- Report any issues to your supervisor

If you have any questions, please contact the cinema manager.

Best regards,
University Cinema Management
"""
        send_email(email, subject, body)
        return True
    except Exception:
        return False

def add_staff(self):
    form = tk.Toplevel(self.root)
    form.title("Add Staff")
    form.geometry("400x450")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text="Add Staff", font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    fields = [("Username:*", "user"), ("Password:*", "pass"), ("Confirm Password:*", "pass2"),
              ("Name:*", "name"), ("Email:", "email"), ("Role:", "role")]
    entries = {}
    for i, (label, key) in enumerate(fields):
        tk.Label(frame, text=label, bg="#ffffff", fg="#333333").grid(row=i+1, column=0, sticky="w", pady=5)
        if key in ("pass", "pass2"):
            e = ttk.Entry(frame, width=25, show="*")
        elif key == "role":
            role_var = tk.StringVar(value="cashier")
            e = ttk.Combobox(frame, textvariable=role_var, width=22, values=list(STAFF_ROLES.keys()))
            entries['role_var'] = role_var
        else:
            e = ttk.Entry(frame, width=25)
        e.grid(row=i+1, column=1, pady=5)
        entries[key] = e

    # Send welcome email checkbox
    send_email_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(frame, text=_t("cinema.labels.send_welcome_email"), variable=send_email_var).grid(
        row=len(fields)+1, column=0, columnspan=2, pady=5)

    def save():
        username = entries['user'].get().strip()
        password = entries['pass'].get()
        password2 = entries['pass2'].get()
        name = entries['name'].get().strip()
        email = entries['email'].get().strip()
        role = entries['role_var'].get()

        # Validation
        if not username or not password or not name:
            messagebox.showwarning(_t("cinema.common.warning"), "Username, password, and name are required")
            return
        if password != password2:
            messagebox.showwarning(_t("cinema.common.warning"), "Passwords do not match")
            return
        if len(password) < 8:
            messagebox.showwarning(_t("cinema.common.warning"), "Password must be at least 8 characters")
            return

        # Use PBKDF2 password hashing (matches university auth system)
        salt, pw_hash = self._hash_staff_password(password)

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO staff (username, password_hash, salt, name, email, role, hire_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (username, pw_hash, salt, name, email, role, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()

            # Send welcome email if checkbox is checked and email provided
            email_sent = False
            if send_email_var.get() and email:
                email_sent = self._send_staff_welcome_email(name, email, username, role)

            success_msg = f"Staff member '{name}' added successfully!"
            if email_sent:
                success_msg += "\nWelcome email sent."
            elif email and send_email_var.get():
                success_msg += "\nNote: Could not send welcome email."

            messagebox.showinfo(_t("cinema.common.success"), success_msg)
            form.destroy()
            self.show_staff_page()
        except sqlite3.IntegrityError:
            messagebox.showerror(_t("cinema.common.error"), "Username already exists")
        finally:
            conn.close()

    ttk.Button(frame, text="Add Staff", style="Success.TButton", command=save).grid(
        row=len(fields)+2, column=0, columnspan=2, pady=20)
