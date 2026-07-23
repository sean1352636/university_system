"""Case update dialog for the Academic Misconduct Panel."""

from education_system.shared.academic_misconduct._imports import (
    tk, ttk, messagebox, scrolledtext, _t,
    EMAIL_AVAILABLE, queue_email,
)


class MisconductCaseUpdateMixin:
    """Mixin providing the case update dialog."""

    def update_case(self):
        """Update/edit the selected case."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case to update.")
            return

        case = self.selected_case

        # Create update dialog - bigger window
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Update Case - {case['id']}")
        dialog.geometry("700x850")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

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
            text=f"Update Case {case['id']}",
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
        student_id_entry.insert(0, case['student_id'])
        entries['student_id'] = student_id_entry

        lookup_btn = tk.Button(
            id_frame,
            text=_t("misconduct.labels.lookup"),
            font=('Segoe UI', 9),
            bg=self.colors['accent'],
            fg=self.colors['white'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=lambda: self.lookup_student(student_id_entry, entries)
        )
        lookup_btn.pack(side=tk.LEFT, padx=(10, 0), ipady=6)

        # Other editable fields (excluding Course which has special validation)
        other_fields = [
            ("Student Name", "student", case['student']),
            ("Student Email", "student_email", case.get('student_email', '')),
        ]

        for label, key, value in other_fields:
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
            entry.insert(0, value)
            entries[key] = entry

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
        course_combo.set(case['course'])
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

        # Violation type dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.violation_type"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        type_var = tk.StringVar(value=case['type'])
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

        severity_var = tk.StringVar(value=case['severity'])
        severity_combo = ttk.Combobox(
            content,
            textvariable=severity_var,
            values=["Minor", "Major", "Critical"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        severity_combo.pack(fill=tk.X, ipady=4)

        # Status dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.status").replace(":", ""),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        status_var = tk.StringVar(value=case['status'])
        status_combo = ttk.Combobox(
            content,
            textvariable=status_var,
            values=["Under Review", "Pending Hearing", "Resolved"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        status_combo.pack(fill=tk.X, ipady=4)

        # Notes
        tk.Label(
            content,
            text=_t("misconduct.sections.notes"),
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
            height=6,
            wrap=tk.WORD,
            insertbackground=self.colors['text_dark']
        )
        notes_text.pack(fill=tk.X)
        notes_text.insert(tk.END, case.get('notes', ''))

        def save_updates():
            # Validate course (warning only, doesn't block)
            course_value = entries['course'].get().strip()
            if course_value:
                is_valid, message = self.validate_course(course_value)
                if not is_valid:
                    response = messagebox.askyesno(_t("misconduct.msg_titles.course_not_found"),
                        f"{message}\n\nThe course code was not found in the system, but you can still proceed.\n\nDo you want to continue updating this case?",
                        icon='warning'
                    )
                    if not response:
                        return

            # Extract just the course code if in "CODE - Name" or "CODE (Modules: ...)" format
            course_code = course_value.split(' - ')[0].strip() if course_value else ''
            course_code = course_code.split('(')[0].strip()

            updated_case = {
                'id': case['id'],
                'student': entries['student'].get(),
                'student_id': entries['student_id'].get(),
                'student_email': entries['student_email'].get(),
                'course': course_code,
                'type': type_var.get(),
                'severity': severity_var.get(),
                'status': status_var.get(),
                'notes': notes_text.get('1.0', tk.END).strip(),
                'date_filed': case['date_filed'],
                'hearing_date': case.get('hearing_date', ''),
                'hearing_time': case.get('hearing_time', ''),
                'hearing_location': case.get('hearing_location', ''),
                'ruling': case.get('ruling', ''),
                'ruling_rationale': case.get('ruling_rationale', '')
            }

            if all([updated_case['student'], updated_case['student_id'], updated_case['course']]):
                # Track what changed
                changes = []
                if case.get('type') != updated_case['type']:
                    changes.append(f"Violation Type: {case.get('type', 'N/A')} → {updated_case['type']}")
                if case.get('severity') != updated_case['severity']:
                    changes.append(f"Severity: {case.get('severity', 'N/A')} → {updated_case['severity']}")
                if case.get('status') != updated_case['status']:
                    changes.append(f"Status: {case.get('status', 'N/A')} → {updated_case['status']}")
                if case.get('notes', '') != updated_case['notes']:
                    changes.append("Case notes have been updated")

                if self.update_case_in_db(updated_case):
                    change_summary = ", ".join(changes) if changes else "Case details updated"
                    self.add_case_history(case['id'], change_summary, 'info')
                    self.load_cases_from_db()
                    self.populate_tree()

                    # Update selected case reference
                    for c in self.cases:
                        if c['id'] == case['id']:
                            self.selected_case = c
                            break

                    # Refresh dashboard and analytics
                    if hasattr(self, 'dashboard_stats_frame'):
                        self.update_dashboard_stats()
                    if hasattr(self, 'analytics_content'):
                        self.refresh_analytics_tab()

                    # Send email notification about changes
                    student_email = updated_case.get('student_email', '')
                    if student_email and changes and EMAIL_AVAILABLE and queue_email:
                        # Build changes list
                        changes_list = "\n".join([f"• {change}" for change in changes])

                        try:
                            from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

                            subject, body = render_template('academics/misconduct_case_update', {
                                'student_name': updated_case['student'],
                                'case_id': case['id'],
                                'changes_list': changes_list,
                                'status': updated_case['status'],
                                'violation_type': updated_case['type'],
                                'severity': updated_case['severity']
                            })

                            # Fallback if template not found
                            if not subject or not body:
                                subject = f"Academic Misconduct Case Update - {case['id']}"
                                body = f"Dear {updated_case['student']},\n\nYour academic misconduct case ({case['id']}) has been updated.\n\nChanges:\n{changes_list}\n\nStatus: {updated_case['status']}\n\nRegards,\nAcademic Misconduct Panel"
                        except Exception as e:
                            print(f"Error rendering email template: {e}")
                            subject = f"Academic Misconduct Case Update - {case['id']}"
                            body = f"Dear {updated_case['student']},\n\nYour academic misconduct case ({case['id']}) has been updated.\n\nChanges:\n{changes_list}\n\nStatus: {updated_case['status']}\n\nRegards,\nAcademic Misconduct Panel"

                        try:
                            queue_email(student_email, subject, body)
                            self.add_case_history(case['id'], f"Update notification sent to {student_email}", 'email')
                        except Exception as e:
                            print(f"Failed to send update email: {e}")

                    dialog.destroy()
                    messagebox.showinfo(_t("misconduct.msg_titles.success"), f"Case {case['id']} updated successfully." +
                                       ("\nNotification email sent to student." if student_email and changes and EMAIL_AVAILABLE else ""))
                else:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to update case in database.")
            else:
                messagebox.showwarning(_t("misconduct.msg_titles.incomplete"), "Please fill in all required fields.")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "Cancel", dialog.destroy, 'secondary').pack(side=tk.RIGHT, padx=(10, 0))
        self.create_button(btn_frame, "💾 Save Changes", save_updates, 'primary').pack(side=tk.RIGHT)
