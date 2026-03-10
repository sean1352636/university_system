"""Dashboard view for the Academic Misconduct Panel."""

from ._imports import tk, ttk, _t, sqlite3, DEFAULT_DB_PATH


class MisconductDashboardMixin:
    """Mixin providing the dashboard view."""

    def create_dashboard_view(self):
        """Create the dashboard view."""
        dashboard_frame = tk.Frame(self.main_content_frame, bg=self.colors['light'])
        self.views['dashboard'] = dashboard_frame

        # This will be populated with dashboard content
        self.create_dashboard_content(dashboard_frame)

    def create_dashboard_content(self, parent):
        """Create the dashboard content."""
        # Scroll container
        canvas = tk.Canvas(parent, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.colors['light'])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Dashboard title
        title_label = tk.Label(
            scroll_frame,
            text=_t("misconduct.sections.dashboard_overview"),
            font=('Segoe UI', 20, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['light']
        )
        title_label.pack(anchor='w', pady=(0, 20))

        # Stats cards container
        self.dashboard_stats_frame = tk.Frame(scroll_frame, bg=self.colors['light'])
        self.dashboard_stats_frame.pack(fill=tk.X, pady=(0, 30))

        self.update_dashboard_stats()

        # Recent activity section
        recent_frame = tk.Frame(scroll_frame, bg=self.colors['white'], relief='solid', bd=1)
        recent_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        tk.Label(
            recent_frame,
            text=_t("misconduct.btn.recent_cases"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['white']
        ).pack(anchor='w', padx=20, pady=15)

        # Get recent 5 cases
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT case_id, student_name, violation_type, status, date_filed, severity
                FROM academic_misconduct_cases
                ORDER BY created_at DESC
                LIMIT 5
            """)
            recent_cases = cursor.fetchall()
            conn.close()

            if recent_cases:
                for case_id, student, violation, status, date_filed, severity in recent_cases:
                    case_card = tk.Frame(recent_frame, bg=self.colors['light'], relief='solid', bd=1)
                    case_card.pack(fill=tk.X, padx=20, pady=5)

                    info_frame = tk.Frame(case_card, bg=self.colors['light'])
                    info_frame.pack(fill=tk.X, padx=15, pady=10)

                    # Case ID and date
                    header_frame = tk.Frame(info_frame, bg=self.colors['light'])
                    header_frame.pack(fill=tk.X)

                    tk.Label(
                        header_frame,
                        text=case_id,
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['primary'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        header_frame,
                        text=date_filed,
                        font=('Segoe UI', 9),
                        fg=self.colors['text_muted'],
                        bg=self.colors['light']
                    ).pack(side=tk.RIGHT)

                    # Details
                    tk.Label(
                        info_frame,
                        text=f"{student} • {violation}",
                        font=('Segoe UI', 9),
                        fg=self.colors['text_dark'],
                        bg=self.colors['light']
                    ).pack(anchor='w', pady=(5, 0))

                    # Status and severity
                    tags_frame = tk.Frame(info_frame, bg=self.colors['light'])
                    tags_frame.pack(anchor='w', pady=(5, 0))

                    status_colors = {
                        'Under Review': self.colors['warning'],
                        'Pending Hearing': self.colors['info'],
                        'Resolved': self.colors['success']
                    }

                    severity_colors = {
                        'Low': self.colors['success'],
                        'Medium': self.colors['info'],
                        'High': self.colors['warning'],
                        'Critical': self.colors['danger']
                    }

                    # Status badge
                    status_badge = tk.Label(
                        tags_frame,
                        text=status,
                        font=('Segoe UI', 8, 'bold'),
                        fg=self.colors['white'],
                        bg=status_colors.get(status, self.colors['text_muted']),
                        padx=8,
                        pady=2
                    )
                    status_badge.pack(side=tk.LEFT, padx=(0, 5))

                    # Severity badge
                    severity_badge = tk.Label(
                        tags_frame,
                        text=severity,
                        font=('Segoe UI', 8, 'bold'),
                        fg=self.colors['white'],
                        bg=severity_colors.get(severity, self.colors['text_muted']),
                        padx=8,
                        pady=2
                    )
                    severity_badge.pack(side=tk.LEFT)
            else:
                tk.Label(
                    recent_frame,
                    text=_t("misconduct.labels.no_cases_found"),
                    font=('Segoe UI', 10),
                    fg=self.colors['text_muted'],
                    bg=self.colors['white']
                ).pack(padx=20, pady=20)

        except Exception as e:
            tk.Label(
                recent_frame,
                text=f"Error loading recent cases: {e}",
                font=('Segoe UI', 10),
                fg=self.colors['danger'],
                bg=self.colors['white']
            ).pack(padx=20, pady=20)

    def update_dashboard_stats(self):
        """Update dashboard statistics cards."""
        # Clear existing stats
        for widget in self.dashboard_stats_frame.winfo_children():
            widget.destroy()

        # Calculate stats
        total_cases = len(self.cases)
        active_cases = len([c for c in self.cases if c['status'] != 'Resolved'])
        resolved_cases = len([c for c in self.cases if c['status'] == 'Resolved'])
        pending_hearings = len([c for c in self.cases if c['status'] == 'Pending Hearing'])
        critical_cases = len([c for c in self.cases if c['severity'] == 'Critical'])

        stats = [
            ("Total Cases", total_cases, self.colors['info'], "📊"),
            ("Active", active_cases, self.colors['warning'], "🔄"),
            ("Resolved", resolved_cases, self.colors['success'], "✅"),
            ("Hearings", pending_hearings, self.colors['secondary'], "⚖️"),
            ("Critical", critical_cases, self.colors['danger'], "⚠️")
        ]

        for i, (label, value, color, icon) in enumerate(stats):
            stat_card = tk.Frame(self.dashboard_stats_frame, bg=color, relief='flat', bd=0, width=180, height=120)
            stat_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
            stat_card.pack_propagate(False)

            tk.Label(
                stat_card,
                text=icon,
                font=('Segoe UI', 24),
                fg=self.colors['white'],
                bg=color
            ).pack(pady=(15, 0))

            tk.Label(
                stat_card,
                text=str(value),
                font=('Segoe UI', 28, 'bold'),
                fg=self.colors['white'],
                bg=color
            ).pack()

            tk.Label(
                stat_card,
                text=label,
                font=('Segoe UI', 10),
                fg=self.colors['white'],
                bg=color
            ).pack(pady=(0, 15))
