"""Decision tab and submission for the Academic Misconduct Panel."""

from education_system.shared.academic_misconduct._imports import (
    tk, ttk, messagebox, scrolledtext, _t,
    sqlite3, DEFAULT_DB_PATH, EMAIL_AVAILABLE, queue_email,
)


class MisconductDecisionsMixin:
    """Mixin providing the decision tab and submission."""

    def create_decision_tab(self, parent):
        """Create the decision tab content with scrollbar."""
        # Create canvas with scrollbar for the entire tab
        canvas_frame = tk.Frame(parent, bg=self.colors['light'])
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)

        padding_frame = tk.Frame(canvas, bg=self.colors['light'])

        # Configure canvas scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        padding_frame.bind("<Configure>", configure_scroll)

        canvas_window = canvas.create_window((0, 0), window=padding_frame, anchor="nw")

        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width - 20)

        canvas.bind("<Configure>", configure_canvas_width)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(
            padding_frame,
            text=_t("misconduct.decision.title", "Panel Decision"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 15))

        # Decision options
        tk.Label(
            padding_frame,
            text=_t("misconduct.decision.ruling_label", "Ruling:"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 5))

        self.ruling_var = tk.StringVar(value="")
        rulings = [
            (_t("misconduct.rulings.not_responsible", "Not Responsible"), "success"),
            (_t("misconduct.rulings.warning", "Responsible - Warning"), "warning"),
            (_t("misconduct.rulings.grade_penalty", "Responsible - Grade Penalty"), "warning"),
            (_t("misconduct.rulings.course_failure", "Responsible - Course Failure"), "danger"),
            (_t("misconduct.rulings.suspension", "Responsible - Suspension"), "danger"),
            (_t("misconduct.rulings.expulsion", "Responsible - Expulsion"), "danger"),
            (_t("misconduct.rulings.academic_probation", "Responsible - Academic Probation"), "warning"),
            (_t("misconduct.rulings.resubmission", "Responsible - Resubmission Required"), "warning"),
            (_t("misconduct.rulings.dismissed", "Case Dismissed - Insufficient Evidence"), "success"),
            (_t("misconduct.rulings.deferred", "Deferred - Pending Investigation"), "warning"),
        ]

        for ruling, severity in rulings:
            color = self.colors[severity] if severity else self.colors['text_dark']
            rb = tk.Radiobutton(
                padding_frame,
                text=ruling,
                variable=self.ruling_var,
                value=ruling,
                font=('Segoe UI', 10),
                fg=color,
                bg=self.colors['light'],
                selectcolor=self.colors['white'],
                activebackground=self.colors['light'],
                activeforeground=color
            )
            rb.pack(anchor='w', pady=3)

        # Rationale
        tk.Label(
            padding_frame,
            text=_t("misconduct.decision.rationale_label", "Decision Rationale:"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(20, 5))

        self.rationale_text = scrolledtext.ScrolledText(
            padding_frame,
            font=('Segoe UI', 10),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=6,
            wrap=tk.WORD,
            insertbackground=self.colors['text_dark']
        )
        self.rationale_text.pack(fill=tk.X, padx=(0, 10))

        # Submit decision
        btn_frame = tk.Frame(padding_frame, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 10))

        self.create_button(btn_frame, "✓ Submit Decision", self.submit_decision, 'primary').pack(side=tk.LEFT)

    def submit_decision(self):
        """Submit panel decision and notify student."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_case_selected"), "Please select a case before submitting a decision.")
            return

        if not self.ruling_var.get():
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a ruling before submitting.")
            return

        ruling = self.ruling_var.get()
        rationale = self.rationale_text.get('1.0', tk.END).strip() if hasattr(self, 'rationale_text') else ''

        # Confirm before submitting
        if not messagebox.askyesno(_t("misconduct.msg_titles.confirm_decision"),
                                   f"Are you sure you want to submit the following decision?\n\n"
                                   f"Case: {self.selected_case['id']}\n"
                                   f"Student: {self.selected_case['student']}\n"
                                   f"Decision: {ruling}\n\n"
                                   f"This action will notify the student via email."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Determine new status based on ruling
            if ruling.startswith("Not Responsible") or ruling.startswith("Case Dismissed"):
                new_status = "Closed - Not Responsible"
            elif ruling.startswith("Deferred"):
                new_status = "Under Investigation"
            else:
                new_status = "Closed - Responsible"

            # Update case with decision
            cursor.execute('''
                UPDATE academic_misconduct_cases
                SET ruling = ?, ruling_rationale = ?, status = ?
                WHERE case_id = ?
            ''', (ruling, rationale, new_status, self.selected_case['id']))

            conn.commit()
            conn.close()

            # Add to case history
            self.add_case_history(
                self.selected_case['id'],
                f"Decision rendered: {ruling}",
                'decision'
            )

            # Send email notification to student
            student_email = self.selected_case.get('student_email', '')
            email_sent = False

            if student_email and EMAIL_AVAILABLE and queue_email:
                # Build rationale section if present
                rationale_section = ""
                if rationale:
                    rationale_section = f"\nDecision Rationale:\n{rationale}\n"

                try:
                    from education_system.university_system.infrastructure.email.template_utils import render_template

                    subject, body = render_template('academics/misconduct_case_decision', {
                        'student_name': self.selected_case['student'],
                        'case_id': self.selected_case['id'],
                        'violation_type': self.selected_case['type'],
                        'course': self.selected_case['course'],
                        'ruling': ruling,
                        'new_status': new_status,
                        'rationale_section': rationale_section
                    })

                    # Fallback if template not found
                    if not subject or not body:
                        subject = f"Academic Misconduct Case Decision - {self.selected_case['id']}"
                        body = f"Dear {self.selected_case['student']},\n\nThe Academic Misconduct Panel has reached a decision.\n\nCase ID: {self.selected_case['id']}\nRuling: {ruling}\nStatus: {new_status}\n{rationale_section}\nRegards,\nAcademic Misconduct Panel"
                except Exception as e:
                    print(f"Error rendering email template: {e}")
                    subject = f"Academic Misconduct Case Decision - {self.selected_case['id']}"
                    body = f"Dear {self.selected_case['student']},\n\nThe Academic Misconduct Panel has reached a decision.\n\nCase ID: {self.selected_case['id']}\nRuling: {ruling}\nStatus: {new_status}\n{rationale_section}\nRegards,\nAcademic Misconduct Panel"

                try:
                    queue_email(student_email, subject, body)
                    self.add_case_history(
                        self.selected_case['id'],
                        f"Decision notification sent to {student_email}",
                        'email'
                    )
                    email_sent = True
                except Exception as e:
                    print(f"Failed to send decision email: {e}")

            # Refresh UI
            self.load_cases_from_db()
            self.populate_tree()

            # Update selected case
            for c in self.cases:
                if c['id'] == self.selected_case['id']:
                    self.selected_case = c
                    break

            self.create_overview_fields()
            if hasattr(self, 'history_frame'):
                self.refresh_history_tab()

            # Clear the form
            self.ruling_var.set("")
            if hasattr(self, 'rationale_text'):
                self.rationale_text.delete('1.0', tk.END)

            success_msg = f"Decision '{ruling}' has been recorded for case {self.selected_case['id']}."
            if email_sent:
                success_msg += f"\n\nNotification email sent to {student_email}."
            elif student_email:
                success_msg += "\n\nNote: Email notification could not be sent."
            else:
                success_msg += "\n\nNote: No email address on file for student."

            messagebox.showinfo(_t("misconduct.msg_titles.decision_submitted"), success_msg)

        except Exception as e:
            messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to submit decision: {str(e)}")
