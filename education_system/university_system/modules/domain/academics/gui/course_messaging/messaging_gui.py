"""Course-Targeted Student Messaging GUI (Feature 26)."""

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.email.email_service import send_email
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class CourseMessagingGUI:
    """Toplevel window for sending messages to students in a course."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.instructor_id = ''
        if auth and auth.current_user:
            self.instructor_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Module Messaging")
        self.window.geometry("1000x800")
        self.window.minsize(900, 700)
        self.window.transient(parent)

        self.student_data = []
        self._setup_ui()
        self._load_courses()

    def _setup_ui(self):
        """Build the messaging UI."""
        ttk.Label(
            self.window, text="Module-Targeted Messaging",
            font=('Arial', 16, 'bold')
        ).pack(pady=(10, 5))

        # Step 1: Module selector
        course_frame = ttk.LabelFrame(self.window, text="Step 1: Select Module", padding="10")
        course_frame.pack(fill=tk.X, padx=15, pady=5)

        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            course_frame, textvariable=self.course_var,
            state='readonly', width=50
        )
        self.course_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.course_combo.bind('<<ComboboxSelected>>', lambda e: self._load_students())

        # Step 2: Student selector (fixed height, no expand)
        student_frame = ttk.LabelFrame(self.window, text="Step 2: Select Recipients", padding="10")
        student_frame.pack(fill=tk.X, padx=15, pady=5)

        btn_row = ttk.Frame(student_frame)
        btn_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_row, text="Select All", command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Deselect All", command=self._deselect_all).pack(side=tk.LEFT, padx=5)
        self.selected_label = ttk.Label(btn_row, text="0 selected")
        self.selected_label.pack(side=tk.RIGHT, padx=5)

        tree_container = ttk.Frame(student_frame)
        tree_container.pack(fill=tk.X)

        cols = ('selected', 'student_id', 'name', 'email')
        self.student_tree = ttk.Treeview(tree_container, columns=cols, show='headings', height=6)
        self.student_tree.heading('selected', text='Select')
        self.student_tree.heading('student_id', text='Student ID')
        self.student_tree.heading('name', text='Name')
        self.student_tree.heading('email', text='Email')
        self.student_tree.column('selected', width=60, anchor='center')
        self.student_tree.column('student_id', width=120)
        self.student_tree.column('name', width=250)
        self.student_tree.column('email', width=300)
        self.student_tree.bind('<ButtonRelease-1>', self._toggle_selection)

        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.student_tree.yview)
        self.student_tree.configure(yscrollcommand=scrollbar.set)
        self.student_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.selected_students = set()

        # Step 3: Message composer (expands to fill remaining space)
        msg_frame = ttk.LabelFrame(self.window, text="Step 3: Compose Message", padding="10")
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        subj_row = ttk.Frame(msg_frame)
        subj_row.pack(fill=tk.X, pady=2)
        ttk.Label(subj_row, text="Subject:").pack(side=tk.LEFT, padx=(0, 5))
        self.subject_var = tk.StringVar()
        ttk.Entry(subj_row, textvariable=self.subject_var, width=70).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.body_text = tk.Text(msg_frame, height=6, wrap=tk.WORD)
        self.body_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Send button bar (always visible at bottom)
        send_frame = ttk.Frame(self.window)
        send_frame.pack(fill=tk.X, padx=15, pady=(5, 10))
        self.status_var = tk.StringVar(value="Select a module and recipients.")
        ttk.Label(send_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Button(send_frame, text="Send Email", command=self._send_message).pack(side=tk.RIGHT, padx=5)

    def _load_courses(self):
        """Load modules based on user role."""
        try:
            role = ''
            if self.auth and self.auth.current_user:
                role = self.auth.current_user.get('role', '')

            with get_connection() as conn:
                if role in ('staff', 'admin'):
                    rows = conn.execute(
                        "SELECT module_code, module_name FROM modules ORDER BY module_code"
                    ).fetchall()
                else:
                    user_id = (
                        self.auth.current_user.get('id', '')
                        if self.auth and self.auth.current_user else ''
                    )
                    rows = conn.execute(
                        "SELECT DISTINCT m.module_code, m.module_name FROM modules m "
                        "INNER JOIN module_schedule ms ON m.module_code = ms.module_code "
                        "WHERE ms.instructor_id = ? ORDER BY m.module_code",
                        (user_id,)
                    ).fetchall()
                courses = [f"{r['module_code']} - {r['module_name']}" for r in (rows or [])]
                self.course_combo['values'] = courses
        except Exception as e:
            logger.error(f"Error loading modules: {e}")

    def _load_students(self):
        """Load students for selected course."""
        selection = self.course_var.get()
        if not selection:
            return
        module_code = selection.split(' - ')[0].strip()

        self.selected_students.clear()
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT s.student_id, s.first_name || ' ' || s.last_name as name, s.email_address as email "
                    "FROM students s "
                    "JOIN student_modules sm ON s.student_id = sm.student_id "
                    "WHERE sm.module_code = ? AND sm.status IN ('Enrolled', 'enrolled') "
                    "ORDER BY s.last_name, s.first_name",
                    (module_code,)
                ).fetchall()
                self.student_data = [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Error loading students: {e}")
            self.student_data = []

        self.student_tree.delete(*self.student_tree.get_children())
        for s in self.student_data:
            self.student_tree.insert('', tk.END, iid=s['student_id'], values=(
                '[ ]', s['student_id'], s.get('name', ''), s.get('email', '')
            ))
        self._update_selected_count()

    def _toggle_selection(self, event):
        """Toggle student selection on click."""
        item = self.student_tree.identify_row(event.y)
        if not item:
            return
        if item in self.selected_students:
            self.selected_students.discard(item)
            vals = self.student_tree.item(item, 'values')
            self.student_tree.item(item, values=('[ ]',) + vals[1:])
        else:
            self.selected_students.add(item)
            vals = self.student_tree.item(item, 'values')
            self.student_tree.item(item, values=('[X]',) + vals[1:])
        self._update_selected_count()

    def _select_all(self):
        """Select all students."""
        for item in self.student_tree.get_children():
            self.selected_students.add(item)
            vals = self.student_tree.item(item, 'values')
            self.student_tree.item(item, values=('[X]',) + vals[1:])
        self._update_selected_count()

    def _deselect_all(self):
        """Deselect all students."""
        for item in self.student_tree.get_children():
            self.selected_students.discard(item)
            vals = self.student_tree.item(item, 'values')
            self.student_tree.item(item, values=('[ ]',) + vals[1:])
        self._update_selected_count()

    def _update_selected_count(self):
        """Update the selected count label."""
        self.selected_label.config(text=f"{len(self.selected_students)} selected")

    def _send_message(self):
        """Send email to selected students."""
        if not self.selected_students:
            messagebox.showwarning("No Recipients", "Please select at least one student.", parent=self.window)
            return
        subject = self.subject_var.get().strip()
        body = self.body_text.get("1.0", tk.END).strip()
        if not subject or not body:
            messagebox.showwarning("Missing Fields", "Please enter a subject and message body.", parent=self.window)
            return

        if not messagebox.askyesno(
            "Confirm Send",
            f"Send message to {len(self.selected_students)} students?",
            parent=self.window
        ):
            return

        sent = 0
        failed = 0
        for s in self.student_data:
            if s['student_id'] in self.selected_students:
                email = s.get('email', '')
                if email:
                    try:
                        send_email(email, subject, body)
                        sent += 1
                    except Exception as e:
                        logger.error(f"Failed to send to {email}: {e}")
                        failed += 1
                else:
                    failed += 1

        try:
            uid = self.auth.current_user.get('id', '') if self.auth and self.auth.current_user else ''
            role = self.auth.current_user.get('role', '') if self.auth and self.auth.current_user else ''
            log_activity(
                uid, self.instructor_id, role,
                'course_message', 'course_messaging',
                details=f"Sent message to {sent} students, subject: {subject}"
            )
        except Exception:
            pass

        self.status_var.set(f"Sent: {sent}, Failed: {failed}")
        messagebox.showinfo(
            "Messages Sent",
            f"Successfully sent to {sent} student(s)." + (f"\nFailed: {failed}" if failed else ""),
            parent=self.window
        )
