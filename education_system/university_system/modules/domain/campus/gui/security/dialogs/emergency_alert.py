"""Emergency alert dialog."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.infrastructure.email.template_utils import render_template

from ..constants import CAMPUS_EMERGENCY_TYPES, CAMPUS_LOCATIONS
from ..utils import get_admin_emails, send_notification_email


class EmergencyAlertDialog(tk.Toplevel):
    """Dialog for sending emergency alerts."""

    def __init__(self, parent, colors, current_user):
        super().__init__(parent)
        self.title("Emergency Alert")
        self.geometry("500x400")
        self.configure(bg="#8B0000")
        self.transient(parent)

        self.colors = colors
        self.current_user = current_user
        self.result = None

        self.setup_ui()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()

    def setup_ui(self):
        # Header
        tk.Label(self, text=_t("police_station.emergency.title"), font=("Segoe UI", 20, "bold"),
                bg="#8B0000", fg="white").pack(pady=20)

        tk.Label(self, text=_t("police_station.emergency.warning"),
                font=("Segoe UI", 10), bg="#8B0000", fg="#ffcccc").pack()

        # Alert type
        type_frame = tk.Frame(self, bg="#8B0000")
        type_frame.pack(fill="x", padx=40, pady=20)

        tk.Label(type_frame, text=_t("police_station.emergency.alert_type"), font=("Segoe UI", 11),
                bg="#8B0000", fg="white").pack(anchor="w")

        self.alert_type = ttk.Combobox(type_frame, values=CAMPUS_EMERGENCY_TYPES, font=("Segoe UI", 11))
        self.alert_type.set("Select alert type...")
        self.alert_type.pack(fill="x", pady=5)

        # Location
        loc_frame = tk.Frame(self, bg="#8B0000")
        loc_frame.pack(fill="x", padx=40, pady=10)

        tk.Label(loc_frame, text=_t("police_station.case_details.location"), font=("Segoe UI", 11),
                bg="#8B0000", fg="white").pack(anchor="w")

        # Add "Campus-Wide" option for alerts that affect the whole campus
        alert_locations = ["Campus-Wide"] + CAMPUS_LOCATIONS
        self.location = ttk.Combobox(loc_frame, values=alert_locations, font=("Segoe UI", 11))
        self.location.set("Select location...")
        self.location.pack(fill="x", pady=5)

        # Description
        desc_frame = tk.Frame(self, bg="#8B0000")
        desc_frame.pack(fill="x", padx=40, pady=10)

        tk.Label(desc_frame, text=_t("police_station.emergency.details"), font=("Segoe UI", 11),
                bg="#8B0000", fg="white").pack(anchor="w")

        self.details = tk.Text(desc_frame, height=4, font=("Segoe UI", 11))
        self.details.pack(fill="x", pady=5)

        # Buttons
        btn_frame = tk.Frame(self, bg="#8B0000")
        btn_frame.pack(fill="x", padx=40, pady=20)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg="#555555", fg="white",
                 font=("Segoe UI", 11), bd=0, padx=25, pady=10,
                 command=self.destroy).pack(side="right", padx=5)

        tk.Button(btn_frame, text=_t("police_station.emergency.send_alert"), bg="#FF0000", fg="white",
                 font=("Segoe UI", 11, "bold"), bd=0, padx=25, pady=10,
                 cursor="hand2", command=self.send_alert).pack(side="right", padx=5)

    def send_alert(self):
        alert_type = self.alert_type.get()
        location = self.location.get()
        details = self.details.get("1.0", "end-1c")

        if "Select" in alert_type:
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.select_alert_type"))
            return

        if not location:
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.enter_location"))
            return

        if messagebox.askyesno(_t("police_station.buttons.confirm"),
                              f"Send {alert_type} alert to all personnel?\n\nThis action will be logged."):
            # Get admin emails
            admin_emails = get_admin_emails()

            reporter = "Unknown"
            if self.current_user:
                reporter = self.current_user.get('name') or self.current_user.get('username', 'Unknown')

            subject, body = render_template('police_emergency_alert', {
                'alert_type': alert_type,
                'location': location,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'reporter': reporter,
                'details': details
            })

            sent_count = 0
            for email in admin_emails:
                if subject and body and send_notification_email(email, subject, body):
                    sent_count += 1

            self.result = {
                'type': alert_type,
                'location': location,
                'details': details,
                'timestamp': datetime.now().isoformat(),
                'reporter': reporter
            }

            messagebox.showinfo(_t("police_station.emergency.alert_sent"),
                              f"Emergency alert sent to {sent_count} personnel")
            self.destroy()
