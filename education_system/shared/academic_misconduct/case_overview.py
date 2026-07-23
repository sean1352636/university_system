"""Case overview tab for the Academic Misconduct Panel."""

from education_system.shared.academic_misconduct._imports import tk, ttk, scrolledtext, _t


class MisconductOverviewMixin:
    """Mixin providing the case overview tab."""

    def _open_source_record(self, record_id):
        """Open the Disciplinary Portal in a Toplevel pre-pointed at
        the source disciplinary record this case was escalated from."""
        try:
            from education_system.post_18.university_system.modules.domain.operations.legal.disciplinary.disciplinary_portal import (  # noqa: E501
                DisciplinaryPortal,
            )
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror(
                "Disciplinary Portal",
                f"Could not load the Disciplinary Portal:\n{e}",
                parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.geometry("1200x800")
        win.prefill_record_id = int(record_id)
        try:
            DisciplinaryPortal(win)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror(
                "Disciplinary Portal",
                f"Failed to launch Disciplinary Portal:\n{e}",
                parent=self.root)
            try:
                win.destroy()
            except Exception:
                pass

    def create_overview_tab(self, parent):
        """Create the overview tab content."""
        # Content frame with scrolling
        canvas = tk.Canvas(parent, bg=self.colors['white'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self.overview_content = tk.Frame(canvas, bg=self.colors['white'])

        self.overview_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.overview_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Placeholder content
        self.overview_fields = {}
        self.create_overview_fields()

    def create_overview_fields(self):
        """Create the overview fields."""
        if not hasattr(self, 'overview_content') or self.overview_content is None:
            return
        # Clear existing widgets
        for widget in self.overview_content.winfo_children():
            widget.destroy()

        padding_frame = tk.Frame(self.overview_content, bg=self.colors['light'])
        padding_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        if not self.selected_case:
            placeholder = tk.Label(
                padding_frame,
                text=_t("misconduct.overview.select_case", "Select a case to view details"),
                font=('Segoe UI', 12),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            )
            placeholder.pack(expand=True)
            return

        case = self.selected_case

        # Case info grid
        fields = [
            (_t("misconduct.fields.case_id", "Case ID"), case['id']),
            (_t("misconduct.fields.student_name", "Student Name"), case['student']),
            (_t("misconduct.fields.student_id", "Student ID"), case['student_id']),
            (_t("misconduct.fields.course", "Course"), case['course']),
            (_t("misconduct.fields.violation_type", "Violation Type"), case['type']),
            (_t("misconduct.fields.date_filed", "Date Filed"), case['date_filed']),
            (_t("misconduct.fields.severity", "Severity"), case['severity']),
            (_t("misconduct.fields.status", "Status"), case['status']),
        ]

        for i, (label, value) in enumerate(fields):
            row_frame = tk.Frame(padding_frame, bg=self.colors['light'])
            row_frame.pack(fill=tk.X, pady=8)

            tk.Label(
                row_frame,
                text=label + ":",
                font=('Segoe UI', 10),
                fg=self.colors['text_muted'],
                bg=self.colors['light'],
                width=15,
                anchor='w'
            ).pack(side=tk.LEFT)

            # Special styling for status and severity
            status_label = _t("misconduct.fields.status", "Status")
            severity_label = _t("misconduct.fields.severity", "Severity")
            if label == status_label:
                color = {
                    'Under Review': self.colors['warning'],
                    'Pending Hearing': self.colors['info'],
                    'Resolved': self.colors['success']
                }.get(value, self.colors['text_dark'])
            elif label == severity_label:
                color = {
                    'Minor': self.colors['success'],
                    'Major': self.colors['warning'],
                    'Critical': self.colors['danger']
                }.get(value, self.colors['text_dark'])
            else:
                color = self.colors['text_dark']

            value_label = tk.Label(
                row_frame,
                text=value,
                font=('Segoe UI', 10, 'bold') if label in [status_label, severity_label] else ('Segoe UI', 10),
                fg=color,
                bg=self.colors['light'],
                anchor='w'
            )
            value_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Source disciplinary record back-link, when this case was
        # escalated from one. Lets the user hop straight back to the
        # original incident in the Disciplinary Portal.
        source_id = case.get('source_record_id')
        if source_id:
            link_row = tk.Frame(padding_frame, bg=self.colors['light'])
            link_row.pack(fill=tk.X, pady=(8, 0))
            tk.Label(
                link_row,
                text=_t("misconduct.fields.source_record",
                        "Source disciplinary record:"),
                font=('Segoe UI', 10),
                fg=self.colors['text_muted'],
                bg=self.colors['light'],
                width=15, anchor='w',
            ).pack(side=tk.LEFT)
            tk.Button(
                link_row,
                text=f"#{source_id} — open in Disciplinary Portal",
                command=lambda rid=source_id: self._open_source_record(rid),
                font=('Segoe UI', 9, 'bold'),
                bg=self.colors['secondary'],
                fg='white',
                bd=0, padx=12, pady=4, cursor='hand2',
            ).pack(side=tk.LEFT)

        # Notes section
        notes_frame = tk.Frame(padding_frame, bg=self.colors['light'])
        notes_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        tk.Label(
            notes_frame,
            text=_t("misconduct.fields.case_notes", "Case Notes:"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 8))

        notes_text = scrolledtext.ScrolledText(
            notes_frame,
            font=('Segoe UI', 10),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=6,
            wrap=tk.WORD,
            insertbackground=self.colors['text_dark']
        )
        notes_text.pack(fill=tk.BOTH, expand=True)
        notes_text.insert(tk.END, case['notes'])

        # Action buttons
        btn_frame = tk.Frame(padding_frame, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, _t("misconduct.buttons.edit_case", "Edit Case"), self.edit_case, 'primary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, _t("misconduct.buttons.notify_student", "Notify Student"), self.notify_student, 'secondary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, _t("misconduct.buttons.schedule_hearing", "Schedule Hearing"), self.schedule_hearing, 'secondary').pack(side=tk.LEFT)
