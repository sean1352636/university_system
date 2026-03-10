"""User operations manager for batch operations GUI.

Provides bulk user creation from CSV, bulk permission updates,
batch course enrollment, and batch email campaigns to user segments.
"""

import csv
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

import logging

logger = logging.getLogger(__name__)


class UserOperationsManager:
    """Manages batch user operations for BatchOperationsGUI."""

    def __init__(self, gui):
        self.gui = gui

    # ------------------------------------------------------------------
    # Bulk User Creation from CSV
    # ------------------------------------------------------------------
    def bulk_create_users(self):
        """Create multiple user accounts from a CSV file.

        Expected CSV columns: username, first_name, last_name, email, role
        Optional columns: student_id, password
        """
        file_path = filedialog.askopenfilename(
            title="Select CSV with user data",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return

        # Preview the file first
        try:
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                rows = list(reader)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file: {e}")
            return

        required = {'username', 'first_name', 'last_name', 'email', 'role'}
        missing = required - set(h.strip().lower() for h in headers)
        if missing:
            messagebox.showerror(
                "Missing Columns",
                f"CSV is missing required columns: {', '.join(missing)}\n\n"
                f"Found columns: {', '.join(headers)}"
            )
            return

        if not messagebox.askyesno(
            "Confirm Bulk User Creation",
            f"This will create {len(rows)} user accounts.\n\n"
            f"Columns: {', '.join(headers)}\n\n"
            "Users without a 'password' column will receive a generated password.\n\n"
            "Continue?"
        ):
            return

        def worker():
            created = 0
            errors = []
            try:
                self.gui.message_queue.put({'type': 'status', 'text': 'Creating user accounts...'})

                import hashlib
                import os
                from datetime import datetime

                with transaction() as conn:
                    for i, row in enumerate(rows):
                        try:
                            username = row.get('username', '').strip()
                            first_name = row.get('first_name', '').strip()
                            last_name = row.get('last_name', '').strip()
                            email = row.get('email', '').strip()
                            role = row.get('role', 'student').strip().lower()
                            student_id = row.get('student_id', '').strip()
                            password = row.get('password', '').strip()

                            if not username or not email:
                                errors.append(f"Row {i+1}: Missing username or email")
                                continue

                            # Check for existing user
                            existing = conn.execute(
                                "SELECT id FROM users WHERE username = ?", (username,)
                            ).fetchone()
                            if existing:
                                errors.append(f"Row {i+1}: User '{username}' already exists")
                                continue

                            # Insert into users table
                            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            conn.execute(
                                "INSERT INTO users (username, first_name, last_name, email, role, "
                                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (username, first_name, last_name, email, role, now, now)
                            )

                            user_id = conn.execute(
                                "SELECT id FROM users WHERE username = ?", (username,)
                            ).fetchone()['id']

                            # Create account with password
                            if not password:
                                password = f"Temp{os.urandom(4).hex()}!"

                            salt = os.urandom(16).hex()
                            password_hash = hashlib.pbkdf2_hmac(
                                'sha256', password.encode(), salt.encode(), 100000
                            ).hex()

                            conn.execute(
                                "INSERT INTO user_accounts (username, password_hash, salt, user_id, "
                                "is_active, created_at, updated_at, password_reset_required) "
                                "VALUES (?, ?, ?, ?, 1, ?, ?, 1)",
                                (username, password_hash, salt, user_id, now, now)
                            )

                            # If student role and student_id provided, add to students table
                            if role == 'student' and student_id:
                                try:
                                    conn.execute(
                                        "INSERT OR IGNORE INTO students (student_id, first_name, "
                                        "last_name, email, course, registration_datetime) "
                                        "VALUES (?, ?, ?, ?, 'CS', ?)",
                                        (student_id, first_name, last_name, email, now)
                                    )
                                except Exception:
                                    pass

                            created += 1

                            if (i + 1) % 10 == 0:
                                self.gui.message_queue.put({
                                    'type': 'progress',
                                    'current': i + 1,
                                    'total': len(rows),
                                    'text': f'Creating users...'
                                })

                        except Exception as e:
                            errors.append(f"Row {i+1}: {str(e)}")

                summary = f"Created {created} of {len(rows)} user accounts."
                if errors:
                    summary += f"\n\n{len(errors)} errors:\n" + "\n".join(errors[:20])
                    if len(errors) > 20:
                        summary += f"\n... and {len(errors) - 20} more"

                self.gui.message_queue.put({'type': 'complete', 'text': summary})

            except Exception as e:
                self.gui.message_queue.put({'type': 'error', 'text': f"Bulk creation failed: {e}"})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Bulk Permission Updates
    # ------------------------------------------------------------------
    def bulk_permission_update(self):
        """Update permissions for multiple users at once."""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title("Bulk Permission Update")
        dialog.geometry("650x550")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Bulk Permission Update",
                  font=("Arial", 14, "bold")).pack(pady=10)

        # Role selection
        role_frame = ttk.LabelFrame(dialog, text="Target Users", padding="10")
        role_frame.pack(fill=tk.X, padx=20, pady=5)

        target_var = tk.StringVar(value="role")
        ttk.Radiobutton(role_frame, text="All users with role:",
                        variable=target_var, value="role").pack(anchor="w")
        ttk.Radiobutton(role_frame, text="Users from CSV file",
                        variable=target_var, value="file").pack(anchor="w")

        role_combo = ttk.Combobox(role_frame, values=["student", "staff", "instructor", "admin"],
                                  state="readonly", width=15)
        role_combo.set("student")
        role_combo.pack(anchor="w", padx=20, pady=5)

        # Permission selection
        perm_frame = ttk.LabelFrame(dialog, text="Permissions to Modify", padding="10")
        perm_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        perm_list_frame = ttk.Frame(perm_frame)
        perm_list_frame.pack(fill=tk.BOTH, expand=True)

        perm_listbox = tk.Listbox(perm_list_frame, selectmode=tk.MULTIPLE, height=10)
        perm_scroll = ttk.Scrollbar(perm_list_frame, orient=tk.VERTICAL,
                                    command=perm_listbox.yview)
        perm_listbox.configure(yscrollcommand=perm_scroll.set)
        perm_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        perm_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load available permissions
        try:
            with get_connection() as conn:
                perms = conn.execute(
                    "SELECT name FROM permissions ORDER BY name"
                ).fetchall()
                for p in perms:
                    perm_listbox.insert(tk.END, p['name'])
        except Exception:
            perm_listbox.insert(tk.END, "(Could not load permissions)")

        # Action
        action_frame = ttk.LabelFrame(dialog, text="Action", padding="10")
        action_frame.pack(fill=tk.X, padx=20, pady=5)

        action_var = tk.StringVar(value="grant")
        ttk.Radiobutton(action_frame, text="Grant selected permissions",
                        variable=action_var, value="grant").pack(anchor="w")
        ttk.Radiobutton(action_frame, text="Revoke selected permissions",
                        variable=action_var, value="revoke").pack(anchor="w")

        # Execute
        def execute():
            selected_indices = perm_listbox.curselection()
            if not selected_indices:
                messagebox.showerror("Error", "Select at least one permission")
                return

            selected_perms = [perm_listbox.get(i) for i in selected_indices]
            action = action_var.get()
            target = target_var.get()
            role = role_combo.get()

            dialog.destroy()
            self._execute_permission_update(target, role, selected_perms, action)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Execute", command=execute).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _execute_permission_update(self, target, role, permissions, action):
        """Execute the bulk permission update."""
        def worker():
            updated = 0
            try:
                with transaction() as conn:
                    # Get target user IDs
                    if target == "role":
                        users = conn.execute(
                            "SELECT id FROM users WHERE role = ?", (role,)
                        ).fetchall()
                    else:
                        file_path = filedialog.askopenfilename(
                            title="Select CSV with usernames",
                            filetypes=[("CSV files", "*.csv")]
                        )
                        if not file_path:
                            return
                        with open(file_path, 'r') as f:
                            reader = csv.DictReader(f)
                            usernames = [r.get('username', '').strip() for r in reader if r.get('username')]
                        placeholders = ','.join(['?' for _ in usernames])
                        users = conn.execute(
                            f"SELECT id FROM users WHERE username IN ({placeholders})",
                            usernames
                        ).fetchall()

                    user_ids = [u['id'] for u in users]

                    # Get permission IDs
                    placeholders = ','.join(['?' for _ in permissions])
                    perm_rows = conn.execute(
                        f"SELECT id FROM permissions WHERE name IN ({placeholders})",
                        permissions
                    ).fetchall()
                    perm_ids = [p['id'] for p in perm_rows]

                    for uid in user_ids:
                        for pid in perm_ids:
                            if action == "grant":
                                conn.execute(
                                    "INSERT OR REPLACE INTO user_permissions "
                                    "(user_id, permission_id, granted) VALUES (?, ?, 1)",
                                    (uid, pid)
                                )
                            else:
                                conn.execute(
                                    "DELETE FROM user_permissions "
                                    "WHERE user_id = ? AND permission_id = ?",
                                    (uid, pid)
                                )
                            updated += 1

                self.gui.message_queue.put({
                    'type': 'complete',
                    'text': f"Updated {updated} permission assignments "
                            f"for {len(user_ids)} users."
                })
            except Exception as e:
                self.gui.message_queue.put({'type': 'error', 'text': f"Permission update failed: {e}"})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Batch Course Enrollment
    # ------------------------------------------------------------------
    def batch_course_enrollment(self):
        """Enroll multiple students in courses from a CSV file.

        Expected CSV columns: student_id, module_code
        Optional: status (defaults to 'Enrolled')
        """
        file_path = filedialog.askopenfilename(
            title="Select CSV with enrollment data (student_id, module_code)",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                rows = list(reader)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file: {e}")
            return

        required = {'student_id', 'module_code'}
        missing = required - set(h.strip().lower() for h in headers)
        if missing:
            messagebox.showerror("Missing Columns",
                                 f"CSV missing required columns: {', '.join(missing)}")
            return

        if not messagebox.askyesno(
            "Confirm Batch Enrollment",
            f"This will create {len(rows)} enrollment records.\nContinue?"
        ):
            return

        def worker():
            enrolled = 0
            errors = []
            try:
                self.gui.message_queue.put({'type': 'status', 'text': 'Processing enrollments...'})
                from datetime import datetime
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with transaction() as conn:
                    for i, row in enumerate(rows):
                        try:
                            sid = row.get('student_id', '').strip()
                            mc = row.get('module_code', '').strip()
                            status = row.get('status', 'Enrolled').strip()

                            if not sid or not mc:
                                errors.append(f"Row {i+1}: Missing student_id or module_code")
                                continue

                            # Check if already enrolled
                            existing = conn.execute(
                                "SELECT id FROM student_modules "
                                "WHERE student_id = ? AND module_code = ?",
                                (sid, mc)
                            ).fetchone()
                            if existing:
                                errors.append(f"Row {i+1}: {sid} already enrolled in {mc}")
                                continue

                            conn.execute(
                                "INSERT INTO student_modules (student_id, module_code, status, "
                                "enrollment_date) VALUES (?, ?, ?, ?)",
                                (sid, mc, status, now)
                            )
                            enrolled += 1

                            if (i + 1) % 10 == 0:
                                self.gui.message_queue.put({
                                    'type': 'progress',
                                    'current': i + 1, 'total': len(rows),
                                    'text': 'Enrolling students...'
                                })
                        except Exception as e:
                            errors.append(f"Row {i+1}: {str(e)}")

                summary = f"Enrolled {enrolled} of {len(rows)} records."
                if errors:
                    summary += f"\n\n{len(errors)} errors:\n" + "\n".join(errors[:20])
                    if len(errors) > 20:
                        summary += f"\n... and {len(errors) - 20} more"

                self.gui.message_queue.put({'type': 'complete', 'text': summary})
            except Exception as e:
                self.gui.message_queue.put({'type': 'error', 'text': f"Batch enrollment failed: {e}"})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Batch Email Campaign
    # ------------------------------------------------------------------
    def batch_email_campaign(self):
        """Send batch email to a user segment."""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title("Batch Email Campaign")
        dialog.geometry("600x550")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Batch Email Campaign",
                  font=("Arial", 14, "bold")).pack(pady=10)

        # Segment selection
        seg_frame = ttk.LabelFrame(dialog, text="Recipient Segment", padding="10")
        seg_frame.pack(fill=tk.X, padx=20, pady=5)

        segment_var = tk.StringVar(value="all_students")
        ttk.Radiobutton(seg_frame, text="All Students",
                        variable=segment_var, value="all_students").pack(anchor="w")
        ttk.Radiobutton(seg_frame, text="All Staff/Instructors",
                        variable=segment_var, value="all_staff").pack(anchor="w")
        ttk.Radiobutton(seg_frame, text="Students in course:",
                        variable=segment_var, value="by_course").pack(anchor="w")

        course_combo = ttk.Combobox(seg_frame, values=["CS", "DS"], state="readonly", width=10)
        course_combo.set("CS")
        course_combo.pack(anchor="w", padx=20, pady=2)

        ttk.Radiobutton(seg_frame, text="Users from CSV file",
                        variable=segment_var, value="from_file").pack(anchor="w")

        # Email content
        content_frame = ttk.LabelFrame(dialog, text="Email Content", padding="10")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        ttk.Label(content_frame, text="Subject:").pack(anchor="w")
        subject_entry = ttk.Entry(content_frame, width=60)
        subject_entry.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(content_frame, text="Body:").pack(anchor="w")
        body_text = scrolledtext.ScrolledText(content_frame, height=8, width=60)
        body_text.pack(fill=tk.BOTH, expand=True)

        # Execute
        def send():
            subject = subject_entry.get().strip()
            body = body_text.get("1.0", tk.END).strip()

            if not subject or not body:
                messagebox.showerror("Error", "Subject and body are required")
                return

            segment = segment_var.get()
            course = course_combo.get()
            dialog.destroy()
            self._execute_email_campaign(segment, course, subject, body)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Send Campaign", command=send).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _execute_email_campaign(self, segment, course, subject, body):
        """Execute the email campaign."""
        def worker():
            queued = 0
            try:
                from datetime import datetime
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with transaction() as conn:
                    # Get recipient emails based on segment
                    if segment == "all_students":
                        recipients = conn.execute(
                            "SELECT email FROM users WHERE role = 'student'"
                        ).fetchall()
                    elif segment == "all_staff":
                        recipients = conn.execute(
                            "SELECT email FROM users WHERE role IN ('staff', 'instructor', 'admin')"
                        ).fetchall()
                    elif segment == "by_course":
                        recipients = conn.execute(
                            "SELECT DISTINCT u.email FROM users u "
                            "JOIN students s ON u.username = s.student_id "
                            "WHERE s.course = ?", (course,)
                        ).fetchall()
                    else:
                        recipients = []

                    for r in recipients:
                        email = r['email']
                        if email:
                            try:
                                conn.execute(
                                    "INSERT INTO notifications "
                                    "(user_id, title, message, notification_type, "
                                    "is_read, created_datetime) "
                                    "VALUES (?, ?, ?, 'email_campaign', 0, ?)",
                                    (email, subject, body, now)
                                )
                                queued += 1
                            except Exception:
                                pass

                self.gui.message_queue.put({
                    'type': 'complete',
                    'text': f"Email campaign queued for {queued} recipients."
                })
            except Exception as e:
                self.gui.message_queue.put({'type': 'error', 'text': f"Campaign failed: {e}"})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
