"""Case dialogs (create, view, delete, edit) for the Academic Misconduct Panel."""

import logging

from education_system.shared.academic_misconduct._imports import (
    tk, ttk, messagebox, scrolledtext, _t, datetime,
    sqlite3, DEFAULT_DB_PATH, EMAIL_AVAILABLE, queue_email,
)

logger = logging.getLogger(__name__)


class MisconductCaseDialogsMixin:
    """Mixin providing case create/view/delete/edit dialogs."""

    def _mirror_case_to_disciplinary(self, new_case):
        """Create a parallel row in disciplinary_records + back-link.

        Mirrors the misconduct case into the Disciplinary Portal's
        canonical store so both surfaces show the same incident, then
        sets the misconduct case's ``source_record_id`` to the new
        disciplinary record id so navigation between panels works.
        Idempotently ensures the back-link column exists on first run.
        """
        db_path = self._get_db_path()
        today = datetime.now().strftime('%Y-%m-%d')

        # Resolve a "reported by" string from the live auth.
        reporter = ''
        try:
            if getattr(self, 'auth', None) and self.auth.current_user:
                cu = self.auth.current_user
                reporter = (cu.get('username')
                            or cu.get('email') or '')
        except Exception:
            pass

        # The Disciplinary Portal's DatabaseManager normally bootstraps
        # the bridge schema on first run, but the misconduct panel can
        # be the very first surface to touch the DB — call the same
        # central helper to make sure the back-link column + status
        # sync triggers exist before we INSERT.
        try:
            from education_system.university_system.modules.domain.operations.legal.disciplinary._db_init import (  # noqa: E501
                ensure_disciplinary_schema,
            )
            ensure_disciplinary_schema(db_path)
        except Exception:
            pass  # not running under university_system — skip

        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()

            cur.execute(
                "INSERT INTO disciplinary_records "
                "(user_id, offense_type, severity, description, "
                " date_occurred, date_reported, reported_by, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'Under Review')",
                (new_case['student_id'], new_case['type'],
                 new_case['severity'],
                 (f"Filed via Academic Misconduct Panel "
                  f"(case {new_case['id']}).\n\n"
                  + (new_case.get('notes') or '')),
                 new_case['date_filed'], today, reporter))
            record_id = cur.lastrowid

            cur.execute(
                "UPDATE academic_misconduct_cases "
                "SET source_record_id = ? "
                "WHERE case_id = ?",
                (record_id, new_case['id']))
            conn.commit()
            return record_id
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    def new_case(self):
        """Create a new case."""
        self.open_case_dialog()

    def edit_case(self):
        """Edit the selected case."""
        if self.selected_case:
            self.open_case_dialog(edit_mode=True)

    def delete_case(self):
        """Delete the selected case."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case to delete.")
            return

        if messagebox.askyesno(_t("misconduct.msg_titles.confirm_delete"), f"Are you sure you want to delete case {self.selected_case['id']}?\n\nThis action cannot be undone."):
            if self.delete_case_from_db(self.selected_case['id']):
                self.selected_case = None
                self.load_cases_from_db()
                self.populate_tree()

                # Refresh dashboard and analytics
                if hasattr(self, 'dashboard_stats_frame'):
                    self.update_dashboard_stats()
                if hasattr(self, 'analytics_content'):
                    self.refresh_analytics_tab()

                messagebox.showinfo(_t("misconduct.msg_titles.deleted"), "Case deleted successfully.")
            else:
                messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to delete case from database.")

    def view_case_details(self):
        """View full details of the selected case in a popup window."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case to view.")
            return

        case = self.selected_case

        # Create view dialog - bigger window
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Case Details - {case['id']}")
        dialog.geometry("800x700")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)

        # Header
        header = tk.Frame(dialog, bg=self.colors['white'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"📄 Case {case['id']}",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['white']
        ).pack(side=tk.LEFT, padx=20, pady=15)

        # Status badge
        status_colors = {
            'Under Review': self.colors['warning'],
            'Pending Hearing': self.colors['info'],
            'Resolved': self.colors['success']
        }
        tk.Label(
            header,
            text=case['status'],
            font=('Segoe UI', 10, 'bold'),
            fg=status_colors.get(case['status'], self.colors['text_dark']),
            bg=self.colors['white']
        ).pack(side=tk.RIGHT, padx=20, pady=15)

        # Content
        content = tk.Frame(dialog, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # Case details
        details = [
            ("Student Name", case['student']),
            ("Student ID", case['student_id']),
            ("Student Email", case.get('student_email', 'Not provided')),
            ("Course", case['course']),
            ("Violation Type", case['type']),
            ("Severity", case['severity']),
            ("Date Filed", case['date_filed']),
            ("Status", case['status']),
        ]

        if case.get('hearing_date'):
            details.append(("Hearing Date", case['hearing_date']))
        if case.get('hearing_time'):
            details.append(("Hearing Time", case['hearing_time']))
        if case.get('hearing_location'):
            details.append(("Hearing Location", case['hearing_location']))
        if case.get('ruling'):
            details.append(("Ruling", case['ruling']))

        for label, value in details:
            row = tk.Frame(content, bg=self.colors['light'])
            row.pack(fill=tk.X, pady=5)

            tk.Label(
                row,
                text=f"{label}:",
                font=('Segoe UI', 10),
                fg=self.colors['text_muted'],
                bg=self.colors['light'],
                width=15,
                anchor='w'
            ).pack(side=tk.LEFT)

            tk.Label(
                row,
                text=value or 'N/A',
                font=('Segoe UI', 10),
                fg=self.colors['text_dark'],
                bg=self.colors['light'],
                anchor='w'
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Notes section
        tk.Label(
            content,
            text=_t("misconduct.labels.case_notes"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(20, 5))

        notes_frame = tk.Frame(content, bg=self.colors['light'])
        notes_frame.pack(fill=tk.BOTH, expand=True)

        notes_text = scrolledtext.ScrolledText(
            notes_frame,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=6,
            wrap=tk.WORD,
            state='normal'
        )
        notes_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        notes_text.insert(tk.END, case.get('notes', 'No notes available.'))
        notes_text.configure(state='disabled')

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, padx=30, pady=20)

        self.create_button(btn_frame, "Close", dialog.destroy, 'secondary').pack(side=tk.RIGHT)
        self.create_button(btn_frame, "✏️ Edit Case", lambda: (dialog.destroy(), self.update_case()), 'primary').pack(side=tk.RIGHT, padx=(0, 10))

    def open_case_dialog(self, edit_mode=False):
        """Open dialog for creating/editing a case."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Case" if not edit_mode else "Edit Case")
        dialog.geometry("700x800")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (350)
        y = (dialog.winfo_screenheight() // 2) - (400)
        dialog.geometry(f"+{x}+{y}")

        # Main container with scrollbar
        main_frame = tk.Frame(dialog, bg=self.colors['light'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas and scrollbar
        canvas = tk.Canvas(main_frame, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['light'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Content inside scrollable frame
        content = tk.Frame(scrollable_frame, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=_t("misconduct.btn.new_case") if not edit_mode else "Edit Case",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        entries = {}

        # Student ID with lookup button
        tk.Label(
            content,
            text=_t("misconduct.labels.student_id"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        id_frame = tk.Frame(content, bg=self.colors['light'])
        id_frame.pack(fill=tk.X)

        student_id_entry = tk.Entry(
            id_frame,
            font=('Segoe UI', 11),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            insertbackground=self.colors['text_dark'],
            relief='flat'
        )
        student_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        entries['student_id'] = student_id_entry

        # Will be set later when assignment dropdown is created
        assignment_loader = {'func': None}

        def lookup_with_assignments():
            self.lookup_student(student_id_entry, entries)
            # Auto-load assignments after lookup
            if assignment_loader['func']:
                assignment_loader['func']()

        lookup_btn = tk.Button(
            id_frame,
            text=_t("misconduct.labels.lookup"),
            font=('Segoe UI', 9),
            bg=self.colors['accent'],
            fg=self.colors['white'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=lookup_with_assignments
        )
        lookup_btn.pack(side=tk.LEFT, padx=(10, 0), ipady=6)

        if edit_mode and self.selected_case:
            student_id_entry.insert(0, self.selected_case.get('student_id', ''))

        # Other student fields
        other_fields = [
            ("Student Name", "student"),
            ("Student Email", "student_email"),
        ]

        for label, key in other_fields:
            tk.Label(
                content,
                text=label,
                font=('Segoe UI', 10),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(anchor='w', pady=(10, 3))

            entry = tk.Entry(
                content,
                font=('Segoe UI', 11),
                bg=self.colors['light'],
                fg=self.colors['text_dark'],
                insertbackground=self.colors['text_dark'],
                relief='flat'
            )
            entry.pack(fill=tk.X, ipady=8)
            entries[key] = entry

            if edit_mode and self.selected_case:
                entry.insert(0, self.selected_case.get(key, ''))

        # Course field with validation
        tk.Label(
            content,
            text=_t("misconduct.labels.course_module"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        course_frame = tk.Frame(content, bg=self.colors['light'])
        course_frame.pack(fill=tk.X)

        # Get valid courses for combobox
        valid_courses = self.get_valid_courses()
        course_values = [c['display'] for c in valid_courses]

        course_var = tk.StringVar()
        course_combo = ttk.Combobox(
            course_frame,
            textvariable=course_var,
            font=('Segoe UI', 11),
            values=course_values,
            width=40
        )
        course_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        entries['course'] = course_combo

        # Course validation status label
        course_status = tk.Label(
            content,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['light']
        )
        course_status.pack(anchor='w', pady=(2, 0))

        def validate_course_field():
            course_value = course_combo.get().strip()
            if not course_value:
                course_status.configure(text=_t("misconduct.labels.enter_course_code"), fg=self.colors['warning'])
                return False
            is_valid, message = self.validate_course(course_value)
            if is_valid:
                course_status.configure(text=f"✓ {message}", fg=self.colors['success'])
                return True
            else:
                course_status.configure(text=f"✗ {message}", fg=self.colors['danger'])
                return False

        validate_course_btn = tk.Button(
            course_frame,
            text=_t("misconduct.btn.validate"),
            font=('Segoe UI', 9),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=validate_course_field
        )
        validate_course_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Store validation function for use when saving
        entries['validate_course'] = validate_course_field

        if edit_mode and self.selected_case:
            course_combo.set(self.selected_case.get('course', ''))

        # Assignment selection section
        tk.Label(
            content,
            text=_t("misconduct.labels.related_assignment"),
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(20, 3))

        assignment_frame = tk.Frame(content, bg=self.colors['light'])
        assignment_frame.pack(fill=tk.X, pady=(0, 10))

        assignment_var = tk.StringVar(value="")
        assignment_combo = ttk.Combobox(
            assignment_frame,
            textvariable=assignment_var,
            font=('Segoe UI', 10),
            state='readonly',
            width=50
        )
        assignment_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        def load_assignments():
            student_id = entries['student_id'].get().strip()
            if student_id:
                assignments = self.get_student_assignments(student_id)
            else:
                # Load all active assignments if no student ID
                assignments = self.get_student_assignments(None)

            if assignments:
                assignment_combo['values'] = [f"{a['id']} - {a['title']}" for a in assignments]
                assignment_combo['state'] = 'readonly'
                if len(assignments) > 0:
                    assignment_combo.set('')  # Clear selection
            else:
                assignment_combo['values'] = ["No assignments found"]
                assignment_combo['state'] = 'readonly'

        # Store reference for auto-loading after lookup
        assignment_loader['func'] = load_assignments

        load_assign_btn = tk.Button(
            assignment_frame,
            text=_t("misconduct.btn.refresh"),
            font=('Segoe UI', 9),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=load_assignments
        )
        load_assign_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Auto-load assignments when dialog opens
        load_assignments()

        # Violation type dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.violation_type"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        type_var = tk.StringVar()
        type_combo = ttk.Combobox(
            content,
            textvariable=type_var,
            values=["Plagiarism", "Unauthorized Collaboration", "Contract Cheating", "Exam Misconduct", "Fabrication", "Other"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        type_combo.pack(fill=tk.X, ipady=4)

        # Severity dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.severity").replace(":", ""),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        severity_var = tk.StringVar()
        severity_combo = ttk.Combobox(
            content,
            textvariable=severity_var,
            values=["Minor", "Major", "Critical"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        severity_combo.pack(fill=tk.X, ipady=4)

        # Notes
        tk.Label(
            content,
            text=_t("misconduct.labels.initial_notes"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        notes_text = scrolledtext.ScrolledText(
            content,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=5,
            wrap=tk.WORD,
            insertbackground=self.colors['text_dark']
        )
        notes_text.pack(fill=tk.X)

        def save_case():
            # Validate course (warning only, doesn't block)
            course_value = entries['course'].get().strip()
            if course_value:
                is_valid, message = self.validate_course(course_value)
                if not is_valid:
                    response = messagebox.askyesno(_t("misconduct.msg_titles.course_not_found"),
                        f"{message}\n\nThe course code was not found in the system, but you can still proceed.\n\nDo you want to continue creating this case?",
                        icon='warning'
                    )
                    if not response:
                        return

            # Include assignment info in notes if selected
            assignment_info = ""
            if assignment_var.get() and assignment_var.get() != "No assignments found":
                assignment_info = f"\n\nRelated Assignment: {assignment_var.get()}"

            # Extract just the course code if in "CODE - Name" or "CODE (Modules: ...)" format
            course_code = course_value.split(' - ')[0].strip() if course_value else ''
            course_code = course_code.split('(')[0].strip()

            new_case = {
                'id': self.get_next_case_id(),
                'student': entries['student'].get(),
                'student_id': entries['student_id'].get(),
                'student_email': entries['student_email'].get() if 'student_email' in entries else '',
                'course': course_code,
                'type': type_var.get(),
                'status': 'Under Review',
                'date_filed': datetime.now().strftime('%Y-%m-%d'),
                'severity': severity_var.get(),
                'notes': notes_text.get('1.0', tk.END).strip() + assignment_info
            }

            if all([new_case['student'], new_case['student_id'], new_case['course'], new_case['type'], new_case['severity']]):
                if self.save_case_to_db(new_case):
                    # Add to case history
                    self.add_case_history(new_case['id'], f"Case created: {new_case['type']} violation", 'info')

                    # Mirror the new case into the Disciplinary Portal's
                    # disciplinary_records so the same incident shows up
                    # in both surfaces. We back-link via source_record_id
                    # on the misconduct case so navigation works both
                    # directions. Failure here is non-fatal — the
                    # misconduct case still saves.
                    try:
                        self._mirror_case_to_disciplinary(new_case)
                    except Exception as _e:
                        logger.warning(
                            "Could not mirror misconduct case %s into "
                            "disciplinary_records: %s",
                            new_case.get('id'), _e)

                    self.load_cases_from_db()
                    self.populate_tree()

                    # Refresh dashboard and analytics
                    if hasattr(self, 'dashboard_stats_frame'):
                        self.update_dashboard_stats()
                    if hasattr(self, 'analytics_content'):
                        self.refresh_analytics_tab()

                    # Send email notification to student
                    student_email = new_case.get('student_email', '').strip()
                    email_sent = False
                    if student_email and EMAIL_AVAILABLE and queue_email:
                        # Build assignment info for email
                        assignment_mention = ""
                        if assignment_var.get() and assignment_var.get() != "No assignments found":
                            assignment_mention = f"\nRelated Assignment: {assignment_var.get()}"

                        try:
                            from education_system.university_system.infrastructure.email.template_utils import render_template

                            subject, body = render_template('academics/misconduct_case_filed', {
                                'student_name': new_case['student'],
                                'case_id': new_case['id'],
                                'student_id': new_case['student_id'],
                                'course': new_case['course'],
                                'violation_type': new_case['type'],
                                'severity': new_case['severity'],
                                'date_filed': new_case['date_filed'],
                                'status': new_case['status'],
                                'assignment_mention': assignment_mention
                            })

                            # Fallback if template not found
                            if not subject or not body:
                                subject = f"Academic Misconduct Case Filed - {new_case['id']}"
                                body = f"Dear {new_case['student']},\n\nThis is to inform you that an academic misconduct case has been filed.\n\nCase ID: {new_case['id']}\nCourse: {new_case['course']}\nViolation: {new_case['type']}\n\nPlease contact the Academic Integrity Office.\n\nSincerely,\nAcademic Misconduct Panel"
                        except Exception as e:
                            print(f"Error rendering email template: {e}")
                            subject = f"Academic Misconduct Case Filed - {new_case['id']}"
                            body = f"Dear {new_case['student']},\n\nThis is to inform you that an academic misconduct case has been filed.\n\nCase ID: {new_case['id']}\nCourse: {new_case['course']}\nViolation: {new_case['type']}\n\nPlease contact the Academic Integrity Office.\n\nSincerely,\nAcademic Misconduct Panel"

                        try:
                            success = queue_email(student_email, subject, body)
                            if success:
                                email_sent = True
                                self.add_case_history(new_case['id'], f"Notification email sent to {student_email}", 'info')
                        except Exception as e:
                            print(f"Failed to send case creation email: {e}")

                    dialog.destroy()

                    # Show success message with email status
                    success_msg = f"Case {new_case['id']} created successfully."
                    if email_sent:
                        success_msg += f"\n\nNotification email has been sent to {student_email}."
                    elif student_email:
                        success_msg += f"\n\nWarning: Could not send notification email to {student_email}."
                    else:
                        success_msg += "\n\nNote: No email address on file. Student was not notified."

                    messagebox.showinfo(_t("misconduct.msg_titles.success"), success_msg)
                else:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to save case to database.")
            else:
                messagebox.showwarning(_t("misconduct.msg_titles.incomplete"), "Please fill in all required fields.")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "Cancel", dialog.destroy, 'secondary').pack(side=tk.RIGHT, padx=(10, 0))
        self.create_button(btn_frame, "Save Case", save_case, 'primary').pack(side=tk.RIGHT)
