"""Superadmin cross-system dashboard for the Academic Misconduct Panel.

Shows aggregate data from all 4 education systems (university, college,
secondary, primary) with per-system breakdowns.
"""

from education_system.shared.academic_misconduct._imports import (
    tk, ttk, _t, sqlite3, DEFAULT_DB_PATH,
)

SYSTEM_DISPLAY_NAMES = {
    'university': 'University',
    'sixth_form': 'College',
    'secondary': 'Secondary School',
    'primary': 'Primary School',
}

SYSTEM_COLORS = {
    'university': '#2980b9',
    'sixth_form': '#8e44ad',
    'secondary': '#27ae60',
    'primary': '#e67e22',
}


class MisconductSuperAdminMixin:
    """Mixin providing the superadmin cross-system dashboard view."""

    def create_superadmin_view(self):
        """Create the superadmin cross-system dashboard view."""
        superadmin_frame = tk.Frame(self.main_content_frame, bg=self.colors['light'])
        self.views['superadmin'] = superadmin_frame

        # Scroll container
        canvas = tk.Canvas(superadmin_frame, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(superadmin_frame, orient=tk.VERTICAL, command=canvas.yview)
        self._sa_scroll_frame = tk.Frame(canvas, bg=self.colors['light'])

        self._sa_scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self._sa_scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._populate_superadmin_view()

    def refresh_superadmin_view(self):
        """Refresh the superadmin view data."""
        if not hasattr(self, '_sa_scroll_frame'):
            return
        for widget in self._sa_scroll_frame.winfo_children():
            widget.destroy()
        self._populate_superadmin_view()

    def _populate_superadmin_view(self):
        """Populate the superadmin dashboard with cross-system data."""
        parent = self._sa_scroll_frame

        # Title
        tk.Label(
            parent,
            text="Cross-System Misconduct Overview",
            font=('Segoe UI', 20, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 5))

        tk.Label(
            parent,
            text="Aggregated data across all education systems",
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        try:
            db_path = str(getattr(self, '_db_path', None) or DEFAULT_DB_PATH)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # ----------------------------------------------------------
            # 1. Global totals row
            # ----------------------------------------------------------
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases")
            global_total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status != 'Resolved'")
            global_active = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Resolved'")
            global_resolved = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE severity = 'Critical'")
            global_critical = cursor.fetchone()[0]

            global_stats_frame = tk.Frame(parent, bg=self.colors['light'])
            global_stats_frame.pack(fill=tk.X, pady=(0, 25))

            global_stats = [
                ("Total (All Systems)", global_total, self.colors['info']),
                ("Active", global_active, self.colors['warning']),
                ("Resolved", global_resolved, self.colors['success']),
                ("Critical", global_critical, self.colors['danger']),
            ]

            for i, (label, value, color) in enumerate(global_stats):
                card = tk.Frame(global_stats_frame, bg=color, width=200, height=90)
                card.pack(side=tk.LEFT, padx=8, fill=tk.BOTH, expand=True)
                card.pack_propagate(False)

                tk.Label(card, text=str(value), font=('Segoe UI', 28, 'bold'),
                         fg='white', bg=color).pack(pady=(12, 0))
                tk.Label(card, text=label, font=('Segoe UI', 9),
                         fg='white', bg=color).pack(pady=(0, 10))

            # ----------------------------------------------------------
            # 2. Per-system breakdown cards
            # ----------------------------------------------------------
            tk.Label(
                parent,
                text="Per-System Breakdown",
                font=('Segoe UI', 16, 'bold'),
                fg=self.colors['primary'],
                bg=self.colors['light']
            ).pack(anchor='w', pady=(10, 15))

            systems_row = tk.Frame(parent, bg=self.colors['light'])
            systems_row.pack(fill=tk.X, pady=(0, 25))

            for sys_key in ('university', 'sixth_form', 'secondary', 'primary'):
                sys_color = SYSTEM_COLORS[sys_key]
                sys_name = SYSTEM_DISPLAY_NAMES[sys_key]

                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ?",
                    (sys_key,))
                sys_total = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ? AND status != 'Resolved'",
                    (sys_key,))
                sys_active = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ? AND status = 'Resolved'",
                    (sys_key,))
                sys_resolved = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ? AND status = 'Pending Hearing'",
                    (sys_key,))
                sys_hearings = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ? AND severity = 'Critical'",
                    (sys_key,))
                sys_critical = cursor.fetchone()[0]

                # System card
                card = tk.Frame(systems_row, bg='white', relief='solid', bd=1)
                card.pack(side=tk.LEFT, padx=6, fill=tk.BOTH, expand=True)

                # Colored header strip
                header = tk.Frame(card, bg=sys_color, height=40)
                header.pack(fill=tk.X)
                header.pack_propagate(False)
                tk.Label(header, text=sys_name, font=('Segoe UI', 11, 'bold'),
                         fg='white', bg=sys_color).pack(expand=True)

                # Stats body
                body = tk.Frame(card, bg='white')
                body.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

                stats_data = [
                    ("Total Cases", sys_total),
                    ("Active", sys_active),
                    ("Resolved", sys_resolved),
                    ("Pending Hearings", sys_hearings),
                    ("Critical", sys_critical),
                ]

                for stat_label, stat_val in stats_data:
                    row = tk.Frame(body, bg='white')
                    row.pack(fill=tk.X, pady=3)
                    tk.Label(row, text=stat_label, font=('Segoe UI', 9),
                             fg=self.colors['text_muted'], bg='white').pack(side=tk.LEFT)

                    val_color = self.colors['danger'] if stat_label == "Critical" and stat_val > 0 else self.colors['text_dark']
                    tk.Label(row, text=str(stat_val), font=('Segoe UI', 10, 'bold'),
                             fg=val_color, bg='white').pack(side=tk.RIGHT)

            # ----------------------------------------------------------
            # 3. Cross-system violation type comparison
            # ----------------------------------------------------------
            tk.Label(
                parent,
                text="Violation Types by System",
                font=('Segoe UI', 16, 'bold'),
                fg=self.colors['primary'],
                bg=self.colors['light']
            ).pack(anchor='w', pady=(10, 15))

            violation_frame = tk.Frame(parent, bg='white', relief='solid', bd=1)
            violation_frame.pack(fill=tk.X, pady=(0, 25))

            # Header row
            viol_header = tk.Frame(violation_frame, bg=self.colors['primary'])
            viol_header.pack(fill=tk.X)

            headers = ["Violation Type"] + [SYSTEM_DISPLAY_NAMES[s] for s in ('university', 'sixth_form', 'secondary', 'primary')] + ["Total"]
            for i, h in enumerate(headers):
                tk.Label(viol_header, text=h, font=('Segoe UI', 9, 'bold'),
                         fg='white', bg=self.colors['primary'],
                         width=18 if i == 0 else 14, anchor='w').grid(row=0, column=i, padx=5, pady=8)

            cursor.execute("""
                SELECT violation_type, system_key, COUNT(*) as cnt
                FROM academic_misconduct_cases
                GROUP BY violation_type, system_key
                ORDER BY violation_type
            """)
            rows = cursor.fetchall()

            # Build pivot: {violation_type: {system_key: count}}
            pivot = {}
            for viol, skey, cnt in rows:
                pivot.setdefault(viol, {})[skey] = cnt

            for row_idx, (viol_type, sys_counts) in enumerate(sorted(pivot.items())):
                bg = 'white' if row_idx % 2 == 0 else self.colors['light']
                viol_row = tk.Frame(violation_frame, bg=bg)
                viol_row.pack(fill=tk.X)

                tk.Label(viol_row, text=viol_type, font=('Segoe UI', 9),
                         fg=self.colors['text_dark'], bg=bg,
                         width=18, anchor='w').grid(row=0, column=0, padx=5, pady=4)

                row_total = 0
                for col_idx, skey in enumerate(('university', 'sixth_form', 'secondary', 'primary'), start=1):
                    cnt = sys_counts.get(skey, 0)
                    row_total += cnt
                    tk.Label(viol_row, text=str(cnt) if cnt else "-",
                             font=('Segoe UI', 9),
                             fg=self.colors['text_dark'] if cnt else self.colors['text_muted'],
                             bg=bg, width=14, anchor='w').grid(row=0, column=col_idx, padx=5, pady=4)

                tk.Label(viol_row, text=str(row_total), font=('Segoe UI', 9, 'bold'),
                         fg=self.colors['primary'], bg=bg,
                         width=14, anchor='w').grid(row=0, column=5, padx=5, pady=4)

            if not pivot:
                tk.Label(violation_frame, text="No cases recorded yet.",
                         font=('Segoe UI', 10), fg=self.colors['text_muted'],
                         bg='white').pack(padx=20, pady=15)

            # ----------------------------------------------------------
            # 4. Severity comparison across systems
            # ----------------------------------------------------------
            tk.Label(
                parent,
                text="Severity Distribution by System",
                font=('Segoe UI', 16, 'bold'),
                fg=self.colors['primary'],
                bg=self.colors['light']
            ).pack(anchor='w', pady=(10, 15))

            severity_frame = tk.Frame(parent, bg='white', relief='solid', bd=1)
            severity_frame.pack(fill=tk.X, pady=(0, 25))

            sev_header = tk.Frame(severity_frame, bg=self.colors['primary'])
            sev_header.pack(fill=tk.X)

            sev_headers = ["Severity"] + [SYSTEM_DISPLAY_NAMES[s] for s in ('university', 'sixth_form', 'secondary', 'primary')] + ["Total"]
            for i, h in enumerate(sev_headers):
                tk.Label(sev_header, text=h, font=('Segoe UI', 9, 'bold'),
                         fg='white', bg=self.colors['primary'],
                         width=18 if i == 0 else 14, anchor='w').grid(row=0, column=i, padx=5, pady=8)

            cursor.execute("""
                SELECT severity, system_key, COUNT(*) as cnt
                FROM academic_misconduct_cases
                GROUP BY severity, system_key
            """)
            sev_rows = cursor.fetchall()

            sev_pivot = {}
            for sev, skey, cnt in sev_rows:
                sev_pivot.setdefault(sev, {})[skey] = cnt

            severity_order = ['Critical', 'High', 'Medium', 'Low']
            severity_colors_map = {
                'Critical': self.colors['danger'],
                'High': self.colors['warning'],
                'Medium': self.colors['info'],
                'Low': self.colors['success'],
            }

            for row_idx, sev in enumerate(severity_order):
                if sev not in sev_pivot:
                    continue
                sys_counts = sev_pivot[sev]
                bg = 'white' if row_idx % 2 == 0 else self.colors['light']
                sev_row = tk.Frame(severity_frame, bg=bg)
                sev_row.pack(fill=tk.X)

                sev_color = severity_colors_map.get(sev, self.colors['text_dark'])
                tk.Label(sev_row, text=f"  {sev}", font=('Segoe UI', 9, 'bold'),
                         fg=sev_color, bg=bg,
                         width=18, anchor='w').grid(row=0, column=0, padx=5, pady=4)

                row_total = 0
                for col_idx, skey in enumerate(('university', 'sixth_form', 'secondary', 'primary'), start=1):
                    cnt = sys_counts.get(skey, 0)
                    row_total += cnt
                    tk.Label(sev_row, text=str(cnt) if cnt else "-",
                             font=('Segoe UI', 9),
                             fg=self.colors['text_dark'] if cnt else self.colors['text_muted'],
                             bg=bg, width=14, anchor='w').grid(row=0, column=col_idx, padx=5, pady=4)

                tk.Label(sev_row, text=str(row_total), font=('Segoe UI', 9, 'bold'),
                         fg=self.colors['primary'], bg=bg,
                         width=14, anchor='w').grid(row=0, column=5, padx=5, pady=4)

            if not sev_pivot:
                tk.Label(severity_frame, text="No cases recorded yet.",
                         font=('Segoe UI', 10), fg=self.colors['text_muted'],
                         bg='white').pack(padx=20, pady=15)

            # ----------------------------------------------------------
            # 5. Recent cases across all systems
            # ----------------------------------------------------------
            tk.Label(
                parent,
                text="Recent Cases (All Systems)",
                font=('Segoe UI', 16, 'bold'),
                fg=self.colors['primary'],
                bg=self.colors['light']
            ).pack(anchor='w', pady=(10, 15))

            recent_frame = tk.Frame(parent, bg='white', relief='solid', bd=1)
            recent_frame.pack(fill=tk.X, pady=(0, 20))

            cursor.execute("""
                SELECT case_id, system_key, student_name, violation_type, status, severity, date_filed
                FROM academic_misconduct_cases
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent = cursor.fetchall()

            if recent:
                # Header
                rh = tk.Frame(recent_frame, bg=self.colors['dark'])
                rh.pack(fill=tk.X)
                for i, h in enumerate(["Case ID", "System", "Student", "Violation", "Status", "Severity", "Date"]):
                    w = 12 if i > 0 else 14
                    tk.Label(rh, text=h, font=('Segoe UI', 9, 'bold'), fg='white',
                             bg=self.colors['dark'], width=w, anchor='w').grid(row=0, column=i, padx=5, pady=6)

                for idx, (cid, skey, student, violation, status, severity, date_filed) in enumerate(recent):
                    bg = 'white' if idx % 2 == 0 else self.colors['light']
                    rr = tk.Frame(recent_frame, bg=bg)
                    rr.pack(fill=tk.X)

                    sys_display = SYSTEM_DISPLAY_NAMES.get(skey, skey or 'Unknown')
                    vals = [cid, sys_display, student, violation, status, severity, date_filed]
                    for i, val in enumerate(vals):
                        w = 12 if i > 0 else 14
                        fg = SYSTEM_COLORS.get(skey, self.colors['text_dark']) if i == 1 else self.colors['text_dark']
                        tk.Label(rr, text=val or '-', font=('Segoe UI', 9), fg=fg,
                                 bg=bg, width=w, anchor='w').grid(row=0, column=i, padx=5, pady=4)
            else:
                tk.Label(recent_frame, text="No cases recorded yet.",
                         font=('Segoe UI', 10), fg=self.colors['text_muted'],
                         bg='white').pack(padx=20, pady=15)

            conn.close()

        except Exception as e:
            tk.Label(parent, text=f"Error loading cross-system data: {e}",
                     font=('Segoe UI', 10), fg=self.colors['danger'],
                     bg=self.colors['light']).pack(padx=20, pady=20)
