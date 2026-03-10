"""Case details panel and section navigation for the Academic Misconduct Panel."""

from ._imports import tk, _t


class MisconductCaseDetailsMixin:
    """Mixin providing the case details panel and section navigation."""

    def create_case_details(self, parent):
        """Create the case details panel."""
        # Header
        header_frame = tk.Frame(parent, bg=self.colors['primary'], height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        self.detail_header = tk.Label(
            header_frame,
            text=_t("misconduct.details.title", "📄 Case Details"),
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['primary']
        )
        self.detail_header.pack(side=tk.LEFT, padx=15, pady=10)

        # Main container for sidebar + content
        main_container = tk.Frame(parent, bg=self.colors['light'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Sidebar navigation panel
        sidebar = tk.Frame(main_container, bg=self.colors['dark'], width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sidebar.pack_propagate(False)

        # Sidebar header
        sidebar_header = tk.Label(
            sidebar,
            text=_t("misconduct.labels.navigation"),
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['dark'],
            pady=15
        )
        sidebar_header.pack(fill=tk.X)

        # Navigation buttons
        self.nav_buttons = {}
        self.current_section = None

        nav_items = [
            ('overview', '📋  Overview', self.show_overview_section),
            ('evidence', '📎  Evidence', self.show_evidence_section),
            ('decision', '⚖  Decision', self.show_decision_section),
            ('history', '📜  History', self.show_history_section),
            ('student_history', '👤  Student History', self.show_student_history_section),
            ('analytics', '📊  Analytics', self.show_analytics_section),
        ]

        for key, text, command in nav_items:
            btn = tk.Button(
                sidebar,
                text=text,
                font=('Segoe UI', 10),
                fg=self.colors['white'],
                bg=self.colors['dark'],
                activebackground=self.colors['secondary'],
                activeforeground=self.colors['white'],
                relief='flat',
                anchor='w',
                padx=20,
                pady=12,
                cursor='hand2',
                command=command
            )
            btn.pack(fill=tk.X, pady=2)
            self.nav_buttons[key] = btn

            # Add hover effects (only for inactive buttons)
            btn.bind('<Enter>', lambda e, b=btn, k=key: self._on_nav_button_enter(b, k))
            btn.bind('<Leave>', lambda e, b=btn, k=key: self._on_nav_button_leave(b, k))

        # Content area
        self.content_container = tk.Frame(main_container, bg=self.colors['white'], relief='solid', bd=1)
        self.content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create all section frames (hidden by default)
        self.sections = {}

        # Overview section
        overview_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_overview_tab(overview_frame)
        self.sections['overview'] = overview_frame

        # Evidence section
        evidence_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_evidence_tab(evidence_frame)
        self.sections['evidence'] = evidence_frame

        # Decision section
        decision_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_decision_tab(decision_frame)
        self.sections['decision'] = decision_frame

        # History section
        history_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_history_tab(history_frame)
        self.sections['history'] = history_frame

        # Student History section
        student_history_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_student_history_tab(student_history_frame)
        self.sections['student_history'] = student_history_frame

        # Analytics section
        analytics_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_analytics_tab(analytics_frame)
        self.sections['analytics'] = analytics_frame

        # Show overview by default
        self.show_section('overview')

    def show_section(self, section_key):
        """Switch to a specific section."""
        # Hide all sections
        for key, frame in self.sections.items():
            frame.pack_forget()

        # Show the requested section
        if section_key in self.sections:
            self.sections[section_key].pack(fill=tk.BOTH, expand=True)
            self.current_section = section_key

            # Update button styles
            for key, btn in self.nav_buttons.items():
                if key == section_key:
                    # Active button style
                    btn.configure(
                        bg=self.colors['secondary'],
                        fg=self.colors['white'],
                        font=('Segoe UI', 10, 'bold')
                    )
                else:
                    # Inactive button style
                    btn.configure(
                        bg=self.colors['dark'],
                        fg=self.colors['white'],
                        font=('Segoe UI', 10)
                    )

    def show_overview_section(self):
        """Show the overview section."""
        self.show_section('overview')

    def show_evidence_section(self):
        """Show the evidence section."""
        self.show_section('evidence')

    def show_decision_section(self):
        """Show the decision section."""
        self.show_section('decision')

    def show_history_section(self):
        """Show the history section."""
        self.show_section('history')

    def show_student_history_section(self):
        """Show the student history section."""
        self.show_section('student_history')

    def show_analytics_section(self):
        """Show the analytics section."""
        self.show_section('analytics')

    def _on_nav_button_enter(self, button, key):
        """Handle mouse enter on navigation button."""
        # Only apply hover effect if not the active button
        if self.current_section != key:
            button.configure(bg=self.colors['primary'])

    def _on_nav_button_leave(self, button, key):
        """Handle mouse leave on navigation button."""
        # Only remove hover effect if not the active button
        if self.current_section != key:
            button.configure(bg=self.colors['dark'])
