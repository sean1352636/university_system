"""User operations manager for batch operations GUI.

Provides bulk user creation from CSV, bulk permission updates,
batch course enrollment, and batch email campaigns to user segments.
"""

import csv
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.i18n import get_text as _t

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
        """Send targeted email campaign to user segments via the email system."""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title("Batch Email Campaign")
        dialog.geometry("700x650")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Send Targeted Email Campaign",
                  font=("Arial", 14, "bold")).pack(pady=10)

        # Segment selection
        seg_frame = ttk.LabelFrame(dialog, text="Recipient Segment", padding="10")
        seg_frame.pack(fill=tk.X, padx=20, pady=5)

        segment_var = tk.StringVar(value="all_users")
        ttk.Radiobutton(seg_frame, text="All Users in Database",
                        variable=segment_var, value="all_users").pack(anchor="w")
        ttk.Radiobutton(seg_frame, text="All Students",
                        variable=segment_var, value="all_students").pack(anchor="w")
        ttk.Radiobutton(seg_frame, text="All Staff/Instructors",
                        variable=segment_var, value="all_staff").pack(anchor="w")

        # Course selection row
        course_row = ttk.Frame(seg_frame)
        course_row.pack(fill=tk.X, anchor="w")
        ttk.Radiobutton(course_row, text="Students in course:",
                        variable=segment_var, value="by_course").pack(side=tk.LEFT)

        # Load available courses from DB
        course_values = []
        try:
            with get_connection() as conn:
                courses = conn.execute(
                    "SELECT DISTINCT course FROM students WHERE course IS NOT NULL "
                    "AND course != '' ORDER BY course"
                ).fetchall()
                course_values = [c['course'] for c in courses]
        except Exception:
            course_values = ["CS", "DS"]
        if not course_values:
            course_values = ["CS"]

        course_combo = ttk.Combobox(course_row, values=course_values,
                                     state="readonly", width=15)
        course_combo.set(course_values[0] if course_values else "CS")
        course_combo.pack(side=tk.LEFT, padx=(5, 0))

        ttk.Radiobutton(seg_frame, text="Users from CSV file (column: email)",
                        variable=segment_var, value="from_file").pack(anchor="w")

        # Recipient count preview
        count_frame = ttk.Frame(seg_frame)
        count_frame.pack(fill=tk.X, pady=(5, 0))
        count_label = ttk.Label(count_frame, text="", foreground="blue")
        count_label.pack(side=tk.LEFT)

        def preview_count(*_args):
            seg = segment_var.get()
            try:
                with get_connection() as conn:
                    if seg == "all_users":
                        row = conn.execute(
                            "SELECT COUNT(*) as cnt FROM users WHERE email IS NOT NULL AND email != ''"
                        ).fetchone()
                    elif seg == "all_students":
                        row = conn.execute(
                            "SELECT COUNT(*) as cnt FROM users WHERE role = 'student' AND email IS NOT NULL AND email != ''"
                        ).fetchone()
                    elif seg == "all_staff":
                        row = conn.execute(
                            "SELECT COUNT(*) as cnt FROM users WHERE role IN ('staff','instructor','admin') AND email IS NOT NULL AND email != ''"
                        ).fetchone()
                    elif seg == "by_course":
                        row = conn.execute(
                            "SELECT COUNT(DISTINCT u.email) as cnt FROM users u "
                            "JOIN students s ON u.username = s.student_id "
                            "WHERE s.course = ? AND u.email IS NOT NULL AND u.email != ''",
                            (course_combo.get(),)
                        ).fetchone()
                    else:
                        count_label.config(text="(Select CSV file to see count)")
                        return
                    count_label.config(text=f"Estimated recipients: {row['cnt']}")
            except Exception:
                count_label.config(text="")

        segment_var.trace_add("write", preview_count)
        course_combo.bind("<<ComboboxSelected>>", preview_count)
        preview_count()

        # Email content
        content_frame = ttk.LabelFrame(dialog, text="Email Content", padding="10")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        ttk.Label(content_frame, text="Subject:").pack(anchor="w")
        subject_entry = ttk.Entry(content_frame, width=70)
        subject_entry.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(content_frame, text="Body:").pack(anchor="w")
        body_text = scrolledtext.ScrolledText(content_frame, height=10, width=70)
        body_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(content_frame,
                  text="Tip: Use {first_name}, {last_name}, {email} as placeholders",
                  foreground="gray").pack(anchor="w", pady=(2, 0))

        # Execute
        def send():
            subject = subject_entry.get().strip()
            body = body_text.get("1.0", tk.END).strip()

            if not subject or not body:
                messagebox.showerror("Error", "Subject and body are required")
                return

            segment = segment_var.get()
            course = course_combo.get()

            csv_path = None
            if segment == "from_file":
                csv_path = filedialog.askopenfilename(
                    title="Select CSV with email addresses",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                if not csv_path:
                    return

            if not messagebox.askyesno(
                "Confirm Email Campaign",
                f"This will send emails to the selected segment: {segment}.\n\n"
                f"Subject: {subject}\n\n"
                "Emails will be processed through the email system.\n"
                "Continue?"
            ):
                return

            dialog.destroy()
            self._execute_email_campaign(segment, course, subject, body, csv_path)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Send Campaign", command=send,
                   style='Action.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Preview Recipients",
                   command=lambda: self._preview_campaign_recipients(
                       segment_var.get(), course_combo.get()
                   )).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _preview_campaign_recipients(self, segment, course):
        """Show a preview of recipients for the selected segment."""
        try:
            with get_connection() as conn:
                if segment == "all_users":
                    recipients = conn.execute(
                        "SELECT first_name, last_name, email, role FROM users "
                        "WHERE email IS NOT NULL AND email != '' ORDER BY last_name LIMIT 50"
                    ).fetchall()
                elif segment == "all_students":
                    recipients = conn.execute(
                        "SELECT first_name, last_name, email, role FROM users "
                        "WHERE role = 'student' AND email IS NOT NULL AND email != '' "
                        "ORDER BY last_name LIMIT 50"
                    ).fetchall()
                elif segment == "all_staff":
                    recipients = conn.execute(
                        "SELECT first_name, last_name, email, role FROM users "
                        "WHERE role IN ('staff','instructor','admin') AND email IS NOT NULL "
                        "AND email != '' ORDER BY last_name LIMIT 50"
                    ).fetchall()
                elif segment == "by_course":
                    recipients = conn.execute(
                        "SELECT u.first_name, u.last_name, u.email, u.role FROM users u "
                        "JOIN students s ON u.username = s.student_id "
                        "WHERE s.course = ? AND u.email IS NOT NULL AND u.email != '' "
                        "ORDER BY u.last_name LIMIT 50", (course,)
                    ).fetchall()
                else:
                    messagebox.showinfo("Preview", "Select a CSV file to see recipients from file.")
                    return

            if not recipients:
                messagebox.showinfo("Preview", "No recipients found for this segment.")
                return

            preview = "First 50 recipients:\n\n"
            for r in recipients:
                preview += f"  {r['first_name']} {r['last_name']} <{r['email']}> [{r['role']}]\n"

            # Show in a preview dialog
            preview_dialog = tk.Toplevel(self.gui.root)
            preview_dialog.title("Recipient Preview")
            preview_dialog.geometry("500x400")
            preview_dialog.transient(self.gui.root)

            text_widget = scrolledtext.ScrolledText(preview_dialog, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text_widget.insert("1.0", preview)
            text_widget.config(state=tk.DISABLED)

            ttk.Button(preview_dialog, text="Close",
                       command=preview_dialog.destroy).pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not preview recipients: {e}")

    def _execute_email_campaign(self, segment, course, subject, body, csv_path=None):
        """Execute the email campaign via the email system."""
        def worker():
            sent = 0
            failed = 0
            errors = []
            try:
                from datetime import datetime
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                self.gui.message_queue.put({
                    'type': 'status', 'text': 'Loading recipients...'
                })

                # Get recipient list
                recipients = []
                with get_connection() as conn:
                    if segment == "all_users":
                        recipients = conn.execute(
                            "SELECT first_name, last_name, email FROM users "
                            "WHERE email IS NOT NULL AND email != ''"
                        ).fetchall()
                    elif segment == "all_students":
                        recipients = conn.execute(
                            "SELECT first_name, last_name, email FROM users "
                            "WHERE role = 'student' AND email IS NOT NULL AND email != ''"
                        ).fetchall()
                    elif segment == "all_staff":
                        recipients = conn.execute(
                            "SELECT first_name, last_name, email FROM users "
                            "WHERE role IN ('staff', 'instructor', 'admin') "
                            "AND email IS NOT NULL AND email != ''"
                        ).fetchall()
                    elif segment == "by_course":
                        recipients = conn.execute(
                            "SELECT DISTINCT u.first_name, u.last_name, u.email "
                            "FROM users u JOIN students s ON u.username = s.student_id "
                            "WHERE s.course = ? AND u.email IS NOT NULL AND u.email != ''",
                            (course,)
                        ).fetchall()
                    elif segment == "from_file" and csv_path:
                        with open(csv_path, 'r', newline='', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                email = row.get('email', '').strip()
                                if email:
                                    recipients.append({
                                        'first_name': row.get('first_name', ''),
                                        'last_name': row.get('last_name', ''),
                                        'email': email
                                    })

                if not recipients:
                    self.gui.message_queue.put({
                        'type': 'error',
                        'text': 'No recipients found for the selected segment.'
                    })
                    return

                total = len(recipients)
                self.gui.message_queue.put({
                    'type': 'status',
                    'text': f'Sending emails to {total} recipients...'
                })

                # Import email queue function from the email system
                try:
                    from education_system.university_system.infrastructure.email.email_service.queue import queue_email as email_queue_email
                    use_infra_email = True
                except ImportError:
                    use_infra_email = False

                for i, r in enumerate(recipients):
                    email_addr = r['email'] if isinstance(r, dict) else r[2]
                    first_name = (r.get('first_name', '') if isinstance(r, dict)
                                  else (r['first_name'] if 'first_name' in r.keys() else ''))
                    last_name = (r.get('last_name', '') if isinstance(r, dict)
                                 else (r['last_name'] if 'last_name' in r.keys() else ''))

                    # Personalise the body with placeholders
                    personalised_body = body.replace(
                        '{first_name}', first_name
                    ).replace(
                        '{last_name}', last_name
                    ).replace(
                        '{email}', email_addr
                    )

                    try:
                        if use_infra_email:
                            result = email_queue_email(
                                email_addr, subject, personalised_body
                            )
                        else:
                            # Fallback: store directly via notifications table
                            with transaction() as conn:
                                conn.execute(
                                    "INSERT INTO notifications "
                                    "(user_id, title, message, notification_type, "
                                    "is_read, created_datetime) "
                                    "VALUES (?, ?, ?, 'email_campaign', 0, ?)",
                                    (email_addr, subject, personalised_body, now)
                                )
                            result = True

                        if result:
                            sent += 1
                        else:
                            failed += 1
                            errors.append(f"{email_addr}: send returned failure")
                    except Exception as e:
                        failed += 1
                        errors.append(f"{email_addr}: {str(e)}")

                    # Progress update every 5 recipients
                    if (i + 1) % 5 == 0 or (i + 1) == total:
                        self.gui.message_queue.put({
                            'type': 'progress',
                            'current': i + 1,
                            'total': total,
                            'text': f'Sending emails ({sent} sent, {failed} failed)...'
                        })

                # Log the campaign in email_log if the table exists
                try:
                    with transaction() as conn:
                        conn.execute(
                            "INSERT INTO email_log (recipient, subject, sent_date, "
                            "status, related_to) VALUES (?, ?, ?, ?, ?)",
                            (f"Campaign: {segment} ({total} recipients)",
                             subject, now, 'sent',
                             f"Batch campaign - {sent} sent, {failed} failed")
                        )
                except Exception:
                    pass  # email_log table may not exist

                summary = (
                    f"Email campaign complete!\n\n"
                    f"Total recipients: {total}\n"
                    f"Successfully sent: {sent}\n"
                    f"Failed: {failed}"
                )
                if errors:
                    summary += f"\n\nFirst errors:\n" + "\n".join(errors[:10])
                    if len(errors) > 10:
                        summary += f"\n... and {len(errors) - 10} more"

                self.gui.message_queue.put({'type': 'complete', 'text': summary})

            except Exception as e:
                logger.exception("Email campaign failed")
                self.gui.message_queue.put({
                    'type': 'error', 'text': f"Campaign failed: {e}"
                })

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
