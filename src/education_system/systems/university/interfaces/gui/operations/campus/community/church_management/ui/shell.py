"""Extracted ChurchManagementSystem behaviour."""
from .. import *

class ChurchUiShellMixin:
    def create_header(self):
        """Create the application header with church name and user info."""
        header_frame = tk.Frame(self.root, bg="#4a4a8a", height=100)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        # Church icon (cross symbol)
        cross_label = tk.Label(
            header_frame,
            text="✝",
            font=("Arial", 48),
            fg="gold",
            bg="#4a4a8a"
        )
        cross_label.pack(side=tk.LEFT, padx=20)

        # Church name
        title_label = tk.Label(
            header_frame,
            text=_t("church.church_name"),
            font=("Georgia", 28, "bold"),
            fg="white",
            bg="#4a4a8a"
        )
        title_label.pack(side=tk.LEFT, padx=10)

        # Right side - user info and time
        right_frame = tk.Frame(header_frame, bg="#4a4a8a")
        right_frame.pack(side=tk.RIGHT, padx=20)

        # User info
        user_name = self.get_user_display_name()
        user_role = self.current_user.get('role', 'member').title()
        tk.Label(right_frame, text=_t("church.common.welcome", name=user_name), font=("Arial", 11, "bold"),
                fg="white", bg="#4a4a8a").pack(anchor="e")
        tk.Label(right_frame, text=f"({user_role})", font=("Arial", 9),
                fg="#d0d0d0", bg="#4a4a8a").pack(anchor="e")

        # Current date/time
        self.time_label = tk.Label(
            right_frame,
            text="",
            font=("Arial", 10),
            fg="white",
            bg="#4a4a8a"
        )
        self.time_label.pack(anchor="e", pady=(5, 0))
        self.update_time()

    def update_time(self):
        """Update the time display in the header."""
        current_time = datetime.now().strftime("%A, %B %d, %Y | %I:%M %p")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)

    def create_navigation(self):
        """Create the side navigation menu."""
        self.nav_frame = tk.Frame(self.root, bg="#6a6aaa", width=200)
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.nav_frame.pack_propagate(False)

        nav_buttons = [
            (_t("church.nav.dashboard"), self.show_dashboard),
            (_t("church.nav.members"), self.show_members),
            (_t("church.nav.donations"), self.show_donations),
            (_t("church.nav.events"), self.show_events),
            (_t("church.nav.prayer_requests"), self.show_prayer_requests),
            (_t("church.nav.sermons"), self.show_sermons),
            (_t("church.nav.announcements"), self.show_announcements),
            (_t("church.nav.volunteers"), self.show_volunteers),
            (_t("church.nav.attendance"), self.show_attendance),
            (_t("church.nav.small_groups"), self.show_small_groups),
            (_t("church.nav.expenses"), self.show_expenses),
            (_t("church.nav.reports"), self.show_reports),
        ]

        for text, command in nav_buttons:
            btn = tk.Button(
                self.nav_frame,
                text=text,
                font=("Arial", 11),
                bg="#5a5a9a",
                fg="white",
                activebackground="#7a7aba",
                activeforeground="white",
                relief=tk.FLAT,
                anchor="w",
                padx=15,
                pady=10,
                command=command,
                cursor="hand2"
            )
            btn.pack(fill=tk.X, padx=5, pady=2)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#7a7aba"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#5a5a9a"))

    def create_main_content(self):
        """Create the main content area."""
        self.main_frame = tk.Frame(self.root, bg="#f5f5dc")
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.content_frame = tk.Frame(self.main_frame, bg="white", relief=tk.RAISED, bd=2)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

    def create_footer(self):
        """Create the application footer."""
        footer_frame = tk.Frame(self.root, bg="#4a4a8a", height=30)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        footer_label = tk.Label(
            footer_frame,
            text=_t("church.footer_text"),
            font=("Arial", 9),
            fg="white",
            bg="#4a4a8a"
        )
        footer_label.pack(pady=5)

    def clear_content(self):
        """Clear the main content area."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
