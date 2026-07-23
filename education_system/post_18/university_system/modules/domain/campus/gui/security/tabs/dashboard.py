"""Dashboard tab mixin."""

import tkinter as tk
from datetime import datetime

from education_system.post_18.university_system.core.i18n import get_text as _t

from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.emergency_alert import EmergencyAlertDialog


class DashboardMixin:
    """Dashboard view methods."""

    def show_emergency_dialog(self):
        """Show emergency alert dialog"""
        dialog = EmergencyAlertDialog(self.root, self.colors, self.current_user)
        if dialog.result:
            if self._db_save_emergency_alert(dialog.result):
                if 'emergency_alerts' not in self.data:
                    self.data['emergency_alerts'] = []
                self.data['emergency_alerts'].append(dialog.result)

    def show_dashboard(self):
        """Display dashboard view"""
        self.clear_content()
        self.create_section_header(_t("police_station.dashboard.title"))

        # Stats cards
        stats_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        stats_frame.pack(fill="x", pady=10)

        open_cases = len([c for c in self.data["cases"] if c.get("status") in ["Open", "In Progress"]])
        pending_complaints = len([c for c in self.data["complaints"] if c.get("status") == "Pending"])
        student_incidents = len([c for c in self.data["cases"] if c.get("is_student_involved")])
        today = datetime.now().strftime("%Y-%m-%d")

        stats = [
            ("\U0001f4cb", _t("police_station.dashboard.active_incidents"), open_cases, self.colors["accent"]),
            ("\U0001f393", _t("police_station.dashboard.student_cases"), student_incidents, self.colors["warning"]),
            ("\U0001f4dd", _t("police_station.dashboard.pending_reports"), pending_complaints, self.colors["warning"]),
            ("\U0001f46e", _t("police_station.dashboard.officers_on_duty"), len([o for o in self.data["officers"] if o.get("status") == "Active"]), self.colors["success"]),
            ("\U0001f694", _t("police_station.dashboard.todays_patrols"), len([p for p in self.data.get("patrol_logs", [])
                                            if p.get("date") == today]),
             self.colors["success"]),
        ]

        for icon, label, value, color in stats:
            card = tk.Frame(stats_frame, bg=color, padx=3, pady=3)
            card.pack(side="left", expand=True, fill="both", padx=8)

            inner = tk.Frame(card, bg=self.colors["bg_medium"])
            inner.pack(fill="both", expand=True)

            tk.Label(inner, text=icon, font=("Segoe UI", 24),
                    bg=self.colors["bg_medium"], fg=color).pack(pady=(15, 5))
            tk.Label(inner, text=str(value), font=("Segoe UI", 28, "bold"),
                    bg=self.colors["bg_medium"], fg=self.colors["text"]).pack()
            tk.Label(inner, text=label, font=("Segoe UI", 10),
                    bg=self.colors["bg_medium"], fg=self.colors["text_secondary"]).pack(pady=(5, 15))

        # Two-column layout
        columns_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        columns_frame.pack(fill="both", expand=True, pady=20)

        # Left column - Recent Activity
        left_col = tk.Frame(columns_frame, bg=self.colors["bg_dark"])
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        activity_frame = tk.Frame(left_col, bg=self.colors["bg_medium"])
        activity_frame.pack(fill="both", expand=True)

        tk.Label(activity_frame, text=_t("police_station.dashboard.recent_cases"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(anchor="w", padx=15, pady=15)

        if self.data["cases"]:
            for case in sorted(self.data["cases"], key=lambda x: x.get('date', ''), reverse=True)[:5]:
                item_frame = tk.Frame(activity_frame, bg=self.colors["bg_medium"])
                item_frame.pack(fill="x", padx=15, pady=5)

                status = case.get("status", "Open")
                status_color = self.colors["success"] if status == "Closed" else self.colors["warning"]
                tk.Label(item_frame, text="\u25cf", fg=status_color,
                        bg=self.colors["bg_medium"], font=("Segoe UI", 12)).pack(side="left")

                case_text = f"Case #{case.get('id', 'N/A')}: {case.get('title', 'Untitled')[:30]}"
                tk.Label(item_frame, text=case_text,
                        bg=self.colors["bg_medium"], fg=self.colors["text"],
                        font=("Segoe UI", 10)).pack(side="left", padx=10)
                tk.Label(item_frame, text=case.get("date", ""),
                        bg=self.colors["bg_medium"], fg=self.colors["text_secondary"],
                        font=("Segoe UI", 9)).pack(side="right")
        else:
            tk.Label(activity_frame, text=_t("police_station.dashboard.no_recent_cases"),
                    bg=self.colors["bg_medium"], fg=self.colors["text_secondary"],
                    font=("Segoe UI", 10)).pack(pady=20)

        # Right column - Quick Actions
        right_col = tk.Frame(columns_frame, bg=self.colors["bg_dark"])
        right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

        actions_frame = tk.Frame(right_col, bg=self.colors["bg_medium"])
        actions_frame.pack(fill="both", expand=True)

        tk.Label(actions_frame, text=_t("police_station.dashboard.quick_actions"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(anchor="w", padx=15, pady=15)

        quick_actions = [
            ("\U0001f4cb " + _t("police_station.dashboard.new_incident_report"), self.add_case),
            ("\U0001f4dd " + _t("police_station.dashboard.submit_safety_concern"), self.add_complaint),
            ("\U0001f694 " + _t("police_station.dashboard.log_campus_patrol"), self.add_patrol_log),
            ("\U0001f4e6 " + _t("police_station.dashboard.log_evidence"), self.add_evidence),
        ]

        for text, command in quick_actions:
            btn = tk.Button(actions_frame, text=text, font=("Segoe UI", 11),
                           bg=self.colors["bg_light"], fg=self.colors["text"],
                           bd=0, padx=15, pady=12, cursor="hand2",
                           command=command, anchor="w")
            btn.pack(fill="x", padx=15, pady=5)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.colors["accent"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.colors["bg_light"]))
