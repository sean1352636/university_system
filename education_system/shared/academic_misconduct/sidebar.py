"""Main sidebar navigation for the Academic Misconduct Panel."""

from education_system.shared.academic_misconduct._imports import tk, ttk, messagebox, _t


class MisconductSidebarMixin:
    """Mixin providing the main navigation sidebar."""

    def create_main_sidebar(self):
        """Create the main navigation sidebar on the far left."""
        self.sidebar = tk.Frame(self.root, bg=self.colors['dark'], width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Logo/Title section
        logo_frame = tk.Frame(self.sidebar, bg=self.colors['primary'], height=90)
        logo_frame.pack(fill=tk.X)
        logo_frame.pack_propagate(False)

        logo_label = tk.Label(
            logo_frame,
            text=_t("misconduct.panel_header"),
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['primary'],
            justify=tk.CENTER
        )
        logo_label.pack(expand=True)

        # Separator
        tk.Frame(self.sidebar, bg=self.colors['border'], height=1).pack(fill=tk.X, pady=5)

        # Scrollable navigation area
        nav_canvas = tk.Canvas(self.sidebar, bg=self.colors['dark'], highlightthickness=0)
        nav_scrollbar = ttk.Scrollbar(self.sidebar, orient=tk.VERTICAL, command=nav_canvas.yview)
        nav_scrollable_frame = tk.Frame(nav_canvas, bg=self.colors['dark'])

        nav_scrollable_frame.bind(
            "<Configure>",
            lambda e: nav_canvas.configure(scrollregion=nav_canvas.bbox("all"))
        )

        nav_canvas.create_window((0, 0), window=nav_scrollable_frame, anchor="nw", width=220)
        nav_canvas.configure(yscrollcommand=nav_scrollbar.set)

        # Navigation buttons
        self.main_nav_buttons = {}

        nav_items = [
            ('dashboard', '📊  Dashboard', 'View overview and statistics'),
            ('cases', '📋  Cases', 'Manage all cases'),
            ('create', '➕  New Case', 'Create a new case'),
            ('evidence', '📎  Documents', 'Supporting documents & evidence'),
            ('analytics', '📈  Analytics', 'View reports and trends'),
        ]

        # Add superadmin cross-system view if in superadmin mode
        if getattr(self, 'is_superadmin', False):
            nav_items.append(('superadmin', '🏛  All Systems', 'Cross-system overview'))

        nav_items.extend([
            ('sep1', None, None),  # Separator
            ('refresh', '🔄  Refresh', 'Reload all data'),
            ('export', '📥  Export', 'Export data to file'),
            ('sep2', None, None),  # Separator
            ('home', '🏠  Return Home', 'Back to main menu'),
        ])

        for key, text, tooltip in nav_items:
            if key.startswith('sep'):
                # Add separator
                tk.Frame(nav_scrollable_frame, bg=self.colors['border'], height=1).pack(fill=tk.X, pady=10, padx=15)
            else:
                btn = tk.Button(
                    nav_scrollable_frame,
                    text=text,
                    font=('Segoe UI', 10),
                    fg=self.colors['white'],
                    bg=self.colors['dark'],
                    activebackground=self.colors['secondary'],
                    activeforeground=self.colors['white'],
                    relief='flat',
                    anchor='w',
                    padx=20,
                    pady=15,
                    cursor='hand2',
                    command=lambda k=key: self.main_nav_action(k)
                )
                btn.pack(fill=tk.X, pady=2, padx=5)
                self.main_nav_buttons[key] = btn

                # Add hover effects
                btn.bind('<Enter>', lambda e, b=btn, k=key: self._on_main_nav_enter(b, k))
                btn.bind('<Leave>', lambda e, b=btn, k=key: self._on_main_nav_leave(b, k))

        # Pack canvas and scrollbar (before user info)
        nav_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        nav_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=nav_canvas)

        # User info at bottom
        user_frame = tk.Frame(self.sidebar, bg=self.colors['dark'])
        user_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20, padx=15)

        username = self.current_user.get('username', 'User') if self.current_user else 'User'
        role = self.current_user.get('role', 'Staff') if self.current_user else 'Staff'

        tk.Label(
            user_frame,
            text=f"👤 {username}",
            font=('Segoe UI', 9, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['dark']
        ).pack(anchor='w')

        tk.Label(
            user_frame,
            text=role,
            font=('Segoe UI', 8),
            fg=self.colors['text_muted'],
            bg=self.colors['dark']
        ).pack(anchor='w')

    def main_nav_action(self, key):
        """Handle main navigation button clicks."""
        if key == 'dashboard':
            self.show_view('dashboard')
        elif key == 'cases':
            self.show_view('cases')
        elif key == 'create':
            self.new_case()
        elif key == 'evidence':
            self.refresh_evidence_tab()
            self.show_view('evidence')
        elif key == 'analytics':
            self.show_view('analytics')
        elif key == 'superadmin':
            self.refresh_superadmin_view()
            self.show_view('superadmin')
        elif key == 'refresh':
            self.refresh_all_data()
        elif key == 'export':
            self.export_analytics_csv()
        elif key == 'home':
            self.return_to_home()

    def _on_main_nav_enter(self, button, key):
        """Handle mouse enter on main nav button."""
        if self.current_view != key or key in ['create', 'refresh', 'export', 'home']:
            button.configure(bg=self.colors['primary'])

    def _on_main_nav_leave(self, button, key):
        """Handle mouse leave on main nav button."""
        if self.current_view != key or key in ['create', 'refresh', 'export', 'home']:
            button.configure(bg=self.colors['dark'])

    def show_view(self, view_key):
        """Switch to a specific main view."""
        # Hide all views
        for key, frame in self.views.items():
            frame.pack_forget()

        # Show requested view
        if view_key in self.views:
            self.views[view_key].pack(fill=tk.BOTH, expand=True)
            self.current_view = view_key

            # Update button styles
            for key, btn in self.main_nav_buttons.items():
                if key == view_key:
                    btn.configure(
                        bg=self.colors['secondary'],
                        font=('Segoe UI', 10, 'bold')
                    )
                elif key not in ['create', 'refresh', 'export', 'home']:
                    btn.configure(
                        bg=self.colors['dark'],
                        font=('Segoe UI', 10)
                    )

    def refresh_all_data(self):
        """Refresh all data and views."""
        self.load_cases_from_db()
        if hasattr(self, 'tree'):
            self.populate_tree()
        if hasattr(self, 'dashboard_stats_frame'):
            self.update_dashboard_stats()
        if hasattr(self, 'analytics_content'):
            self.refresh_analytics_tab()
        if hasattr(self, '_sa_scroll_frame'):
            self.refresh_superadmin_view()
        messagebox.showinfo(_t("misconduct.msg_titles.refreshed"), "All data has been refreshed.")
