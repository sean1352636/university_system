"""History tabs for the Academic Misconduct Panel."""

from education_system.shared.academic_misconduct._imports import tk, ttk, _t, sqlite3, DEFAULT_DB_PATH


class MisconductHistoryMixin:
    """Mixin providing case history and student history tabs."""

    def create_history_tab(self, parent):
        """Create the history tab content."""
        # Store reference to history frame for refresh
        self.history_frame = tk.Frame(parent, bg=self.colors['light'])
        self.history_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.refresh_history_tab()

    def refresh_history_tab(self):
        """Refresh the history tab with current case data."""
        # Clear existing widgets
        for widget in self.history_frame.winfo_children():
            widget.destroy()

        tk.Label(
            self.history_frame,
            text=_t("misconduct.sections.case_history_timeline"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 15))

        if not self.selected_case:
            tk.Label(
                self.history_frame,
                text=_t("misconduct.labels.select_case_history"),
                font=('Segoe UI', 11),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(pady=20)
            return

        # Get history from database
        events = self.get_case_history(self.selected_case['id'])

        if not events:
            tk.Label(
                self.history_frame,
                text=_t("misconduct.labels.no_history_found"),
                font=('Segoe UI', 11),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(pady=20)
            return

        for date, description, event_type in events:
            event_frame = tk.Frame(self.history_frame, bg=self.colors['light'])
            event_frame.pack(fill=tk.X, pady=8)

            indicator = tk.Frame(event_frame, bg=self.colors.get(event_type, self.colors['info']), width=4)
            indicator.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))

            content_frame = tk.Frame(event_frame, bg=self.colors['light'])
            content_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(
                content_frame,
                text=date,
                font=('Segoe UI', 9),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(anchor='w')

            tk.Label(
                content_frame,
                text=description,
                font=('Segoe UI', 10),
                fg=self.colors['text_dark'],
                bg=self.colors['light']
            ).pack(anchor='w')

    def create_student_history_tab(self, parent):
        """Create the student history tab showing all cases for a student."""
        # Content frame with scrolling
        canvas = tk.Canvas(parent, bg=self.colors['white'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self.student_history_content = tk.Frame(canvas, bg=self.colors['white'])

        self.student_history_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.student_history_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create initial content
        self.refresh_student_history_tab()

    def refresh_student_history_tab(self):
        """Refresh the student history tab content."""
        # Clear existing widgets
        for widget in self.student_history_content.winfo_children():
            widget.destroy()

        padding_frame = tk.Frame(self.student_history_content, bg=self.colors['white'])
        padding_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        if not self.selected_case:
            placeholder = tk.Label(
                padding_frame,
                text=_t("misconduct.student_history.select_case", "Select a case to view student history"),
                font=('Segoe UI', 12),
                fg=self.colors['text_muted'],
                bg=self.colors['white']
            )
            placeholder.pack(expand=True)
            return

        student_id = self.selected_case.get('student_id', '')
        student_name = self.selected_case.get('student', '')

        # Header
        header = tk.Label(
            padding_frame,
            text=f"Academic Misconduct History - {student_name} ({student_id})",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['white']
        )
        header.pack(anchor='w', pady=(0, 20))

        # Get all cases for this student
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT case_id, date_filed, violation_type, status, severity, ruling
                FROM academic_misconduct_cases
                WHERE student_id = ?
                ORDER BY date_filed DESC
            """, (student_id,))
            student_cases = cursor.fetchall()
            conn.close()

            if not student_cases:
                no_history = tk.Label(
                    padding_frame,
                    text=_t("misconduct.student_history.no_history", "No previous misconduct cases found for this student."),
                    font=('Segoe UI', 11),
                    fg=self.colors['success'],
                    bg=self.colors['white']
                )
                no_history.pack(anchor='w', pady=10)
            else:
                # Summary stats
                stats_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                stats_frame.pack(fill=tk.X, pady=(0, 20))

                stats_grid = tk.Frame(stats_frame, bg=self.colors['light'])
                stats_grid.pack(padx=15, pady=15)

                total_cases = len(student_cases)
                resolved_cases = len([c for c in student_cases if c[3] == 'Resolved'])
                pending_cases = total_cases - resolved_cases
                guilty_rulings = len([c for c in student_cases if c[5] and 'guilty' in c[5].lower()])

                stats = [
                    ("Total Cases", str(total_cases), self.colors['info']),
                    ("Resolved", str(resolved_cases), self.colors['success']),
                    ("Active/Pending", str(pending_cases), self.colors['warning']),
                    ("Guilty Rulings", str(guilty_rulings), self.colors['danger'])
                ]

                for i, (label, value, color) in enumerate(stats):
                    stat_frame = tk.Frame(stats_grid, bg=self.colors['white'], padx=15, pady=10)
                    stat_frame.grid(row=0, column=i, padx=5)

                    tk.Label(
                        stat_frame,
                        text=value,
                        font=('Segoe UI', 18, 'bold'),
                        fg=color,
                        bg=self.colors['white']
                    ).pack()

                    tk.Label(
                        stat_frame,
                        text=label,
                        font=('Segoe UI', 9),
                        fg=self.colors['text_muted'],
                        bg=self.colors['white']
                    ).pack()

                # Case list
                tk.Label(
                    padding_frame,
                    text=_t("misconduct.labels.case_history"),
                    font=('Segoe UI', 11, 'bold'),
                    fg=self.colors['text_dark'],
                    bg=self.colors['white']
                ).pack(anchor='w', pady=(10, 5))

                for case in student_cases:
                    case_id, date_filed, violation_type, status, severity, ruling = case

                    case_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                    case_frame.pack(fill=tk.X, pady=5)

                    # Highlight current case
                    is_current = (case_id == self.selected_case['id'])
                    if is_current:
                        case_frame.configure(bg=self.colors['secondary'], relief='solid', bd=2)

                    case_info_frame = tk.Frame(case_frame, bg=case_frame['bg'])
                    case_info_frame.pack(fill=tk.X, padx=15, pady=10)

                    # Case ID and date
                    header_row = tk.Frame(case_info_frame, bg=case_frame['bg'])
                    header_row.pack(fill=tk.X)

                    case_id_label = tk.Label(
                        header_row,
                        text=f"{'➤ ' if is_current else ''}Case ID: {case_id}",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['white'] if is_current else self.colors['primary'],
                        bg=case_frame['bg']
                    )
                    case_id_label.pack(side=tk.LEFT)

                    date_label = tk.Label(
                        header_row,
                        text=f"Filed: {date_filed}",
                        font=('Segoe UI', 9),
                        fg=self.colors['white'] if is_current else self.colors['text_muted'],
                        bg=case_frame['bg']
                    )
                    date_label.pack(side=tk.RIGHT)

                    # Details
                    details = f"Type: {violation_type} | Severity: {severity} | Status: {status}"
                    if ruling:
                        details += f" | Ruling: {ruling}"

                    details_label = tk.Label(
                        case_info_frame,
                        text=details,
                        font=('Segoe UI', 9),
                        fg=self.colors['white'] if is_current else self.colors['text_dark'],
                        bg=case_frame['bg'],
                        wraplength=600,
                        justify='left'
                    )
                    details_label.pack(anchor='w', pady=(5, 0))

        except Exception as e:
            error_label = tk.Label(
                padding_frame,
                text=f"Error loading student history: {str(e)}",
                font=('Segoe UI', 10),
                fg=self.colors['danger'],
                bg=self.colors['white']
            )
            error_label.pack(anchor='w', pady=10)
