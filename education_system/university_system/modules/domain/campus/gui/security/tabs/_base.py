"""Base mixin providing shared UI setup, helpers, and navigation for PoliceStationApp."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _t


class BaseMixin:
    """Shared UI setup and helper methods."""

    def get_user_display_name(self):
        """Get display name for current user."""
        if self.current_user:
            name = self.current_user.get('name') or self.current_user.get('full_name')
            if not name:
                first = self.current_user.get('first_name', '')
                last = self.current_user.get('last_name', '')
                name = f"{first} {last}".strip()
            return name or self.current_user.get('username', 'User')
        return 'Guest'

    def is_admin(self):
        """Check if current user has admin privileges."""
        if self.current_user:
            role = self.current_user.get('role', '').lower()
            return role in ['admin', 'security_admin', 'police_chief', 'officer']
        return False

    def setup_styles(self):
        """Configure ttk styles"""
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Colors
        self.colors = {
            "bg_dark": "#1a1a2e",
            "bg_medium": "#16213e",
            "bg_light": "#0f3460",
            "accent": "#e94560",
            "text": "#ffffff",
            "text_secondary": "#a0a0a0",
            "success": "#00d26a",
            "warning": "#ffc107",
            "danger": "#dc3545"
        }

        # Configure styles
        self.style.configure("Sidebar.TButton",
                            font=("Segoe UI", 11),
                            padding=15,
                            background=self.colors["bg_medium"],
                            foreground=self.colors["text"])

        self.style.configure("Treeview",
                            background=self.colors["bg_medium"],
                            foreground=self.colors["text"],
                            fieldbackground=self.colors["bg_medium"],
                            font=("Segoe UI", 10))

        self.style.configure("Treeview.Heading",
                            background=self.colors["bg_light"],
                            foreground=self.colors["text"],
                            font=("Segoe UI", 10, "bold"))

        self.style.map("Treeview",
                      background=[("selected", self.colors["accent"])])

    def create_header(self):
        """Create header section"""
        header = tk.Frame(self.root, bg=self.colors["bg_medium"], height=80)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Left side - badge and title
        left_frame = tk.Frame(header, bg=self.colors["bg_medium"])
        left_frame.pack(side="left", padx=20)

        badge_label = tk.Label(left_frame, text="\U0001f6e1\ufe0f", font=("Segoe UI", 32),
                              bg=self.colors["bg_medium"], fg=self.colors["accent"])
        badge_label.pack(side="left")

        title_frame = tk.Frame(left_frame, bg=self.colors["bg_medium"])
        title_frame.pack(side="left", padx=15)

        title = tk.Label(title_frame, text=_t("police_station.title_short").upper(),
                        font=("Segoe UI", 20, "bold"),
                        bg=self.colors["bg_medium"], fg=self.colors["text"])
        title.pack(anchor="w")

        subtitle = tk.Label(title_frame, text=_t("police_station.subtitle"),
                           font=("Segoe UI", 10),
                           bg=self.colors["bg_medium"], fg=self.colors["text_secondary"])
        subtitle.pack(anchor="w")

        # Right side - user info and emergency button
        right_frame = tk.Frame(header, bg=self.colors["bg_medium"])
        right_frame.pack(side="right", padx=20)

        # Emergency Alert Button
        emergency_btn = tk.Button(right_frame, text=_t("police_station.header.emergency_alert"),
                                 font=("Segoe UI", 10, "bold"),
                                 bg="#dc3545", fg="white", bd=0,
                                 padx=15, pady=8, cursor="hand2",
                                 command=self.show_emergency_dialog)
        emergency_btn.pack(side="right", padx=10)

        # User info
        user_frame = tk.Frame(right_frame, bg=self.colors["bg_medium"])
        user_frame.pack(side="right", padx=20)

        user_name = self.get_user_display_name()
        tk.Label(user_frame, text=_t("police_station.header.officer", name=user_name),
                font=("Segoe UI", 11), bg=self.colors["bg_medium"],
                fg=self.colors["text"]).pack(anchor="e")

        self.time_label = tk.Label(user_frame, font=("Segoe UI", 10),
                                  bg=self.colors["bg_medium"], fg=self.colors["text_secondary"])
        self.time_label.pack(anchor="e")
        self.update_time()

    def update_time(self):
        """Update the time display"""
        current = datetime.now().strftime("%B %d, %Y | %I:%M:%S %p")
        self.time_label.config(text=current)
        self.root.after(1000, self.update_time)

    def create_sidebar(self):
        """Create sidebar navigation"""
        self.sidebar = tk.Frame(self.root, bg=self.colors["bg_medium"], width=240)
        self.sidebar.pack(fill="y", side="left")
        self.sidebar.pack_propagate(False)

        # Refresh button
        refresh_btn = tk.Button(self.sidebar, text="\U0001f504 " + _t("police_station.sidebar.refresh_data"),
                               font=("Segoe UI", 10), bg=self.colors["bg_light"],
                               fg=self.colors["text"], bd=0, padx=15, pady=8,
                               cursor="hand2", command=self.refresh_data)
        refresh_btn.pack(fill="x", padx=10, pady=10)

        # Menu items
        menu_items = [
            ("\U0001f4ca", _t("police_station.sidebar.dashboard"), self.show_dashboard),
            ("\U0001f4cb", _t("police_station.sidebar.incident_reports"), self.show_cases),
            ("\U0001f46e", _t("police_station.sidebar.officers"), self.show_officers),
            ("\U0001f4dd", _t("police_station.sidebar.safety_concerns"), self.show_complaints),
            ("\U0001f694", _t("police_station.sidebar.campus_patrols"), self.show_patrol_logs),
            ("\U0001f50d", _t("police_station.sidebar.persons_of_interest"), self.show_criminals),
            ("\U0001f4e6", _t("police_station.sidebar.evidence_locker"), self.show_evidence),
            ("\U0001f4c8", _t("police_station.sidebar.reports_analytics"), self.show_reports),
        ]

        for icon, text, command in menu_items:
            btn_frame = tk.Frame(self.sidebar, bg=self.colors["bg_medium"])
            btn_frame.pack(fill="x", pady=2)

            btn = tk.Button(btn_frame, text=f"  {icon}  {text}",
                           font=("Segoe UI", 11),
                           bg=self.colors["bg_medium"],
                           fg=self.colors["text"],
                           activebackground=self.colors["bg_light"],
                           activeforeground=self.colors["text"],
                           bd=0, anchor="w", padx=20, pady=12,
                           command=command, cursor="hand2")
            btn.pack(fill="x")

            # Hover effects
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.colors["bg_light"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.colors["bg_medium"]))

    def create_main_content(self):
        """Create main content area"""
        self.main_frame = tk.Frame(self.root, bg=self.colors["bg_dark"])
        self.main_frame.pack(fill="both", expand=True, side="right")

        self.content_frame = tk.Frame(self.main_frame, bg=self.colors["bg_dark"])
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def clear_content(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def refresh_data(self):
        """Refresh all data"""
        self.load_data()
        messagebox.showinfo(_t("police_station.sidebar.refresh_data"), _t("police_station.messages.refreshed"))

    def create_section_header(self, title, add_callback=None, extra_buttons=None):
        """Create a section header with optional add button"""
        header_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        header_frame.pack(fill="x", pady=(0, 20))

        tk.Label(header_frame, text=title, font=("Segoe UI", 18, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left")

        if add_callback:
            add_btn = tk.Button(header_frame, text=_t("police_station.cases.add_new"),
                               font=("Segoe UI", 10, "bold"),
                               bg=self.colors["accent"], fg=self.colors["text"],
                               bd=0, padx=15, pady=8, cursor="hand2",
                               command=add_callback)
            add_btn.pack(side="right")

        if extra_buttons:
            for btn_text, btn_cmd in extra_buttons:
                btn = tk.Button(header_frame, text=btn_text,
                               font=("Segoe UI", 10),
                               bg=self.colors["bg_light"], fg=self.colors["text"],
                               bd=0, padx=15, pady=8, cursor="hand2",
                               command=btn_cmd)
                btn.pack(side="right", padx=5)

    def get_officers_list(self):
        """Get list of officer names for dropdowns"""
        return [o.get('name', 'Unknown') for o in self.data.get('officers', [])]
