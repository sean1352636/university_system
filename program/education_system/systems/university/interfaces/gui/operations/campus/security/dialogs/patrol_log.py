"""Patrol log dialog."""

import tkinter as tk
from tkinter import ttk
from datetime import datetime

from education_system.systems.university.infrastructure.i18n import get_text as _t


class PatrolLogDialog(tk.Toplevel):
    """Dialog for logging patrol activities."""

    def __init__(self, parent, colors, current_user, officers_list):
        super().__init__(parent)
        self.title("Patrol Log Entry")
        self.geometry("500x500")
        self.configure(bg=colors["bg_dark"])
        self.transient(parent)

        self.colors = colors
        self.current_user = current_user
        self.officers_list = officers_list
        self.result = None

        self.setup_ui()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 500) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()
        self.wait_window()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg=self.colors["accent"], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=_t("police_station.patrol.new_entry"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["accent"], fg="white").pack(pady=12)

        content = tk.Frame(self, bg=self.colors["bg_dark"])
        content.pack(fill="both", expand=True, padx=30, pady=20)

        # Officer
        tk.Label(content, text=_t("police_station.patrol.officer_label"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        self.officer_combo = ttk.Combobox(content, values=self.officers_list)
        if self.current_user:
            name = self.current_user.get('name') or self.current_user.get('username', '')
            if name in self.officers_list:
                self.officer_combo.set(name)
        self.officer_combo.pack(fill="x", pady=(0, 15))

        # Patrol Area
        tk.Label(content, text=_t("police_station.patrol.patrol_area"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        patrol_areas = [
            "North Campus Zone", "South Campus Zone", "East Campus Zone", "West Campus Zone",
            "Residence Halls", "Academic Buildings", "Library & Study Areas",
            "Athletic Facilities", "Parking Areas", "Campus Perimeter",
            "Student Center Area", "Administrative Buildings"
        ]
        self.area_combo = ttk.Combobox(content, values=patrol_areas)
        self.area_combo.pack(fill="x", pady=(0, 15))

        # Start/End Time
        time_frame = tk.Frame(content, bg=self.colors["bg_dark"])
        time_frame.pack(fill="x", pady=(0, 15))

        tk.Label(time_frame, text=_t("police_station.patrol.start_time"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left")
        self.start_time = tk.Entry(time_frame, width=12, font=("Segoe UI", 10),
                                  bg=self.colors["bg_medium"], fg=self.colors["text"])
        self.start_time.insert(0, datetime.now().strftime("%H:%M"))
        self.start_time.pack(side="left", padx=10)

        tk.Label(time_frame, text=_t("police_station.patrol.end_time"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left", padx=(20, 0))
        self.end_time = tk.Entry(time_frame, width=12, font=("Segoe UI", 10),
                                bg=self.colors["bg_medium"], fg=self.colors["text"])
        self.end_time.pack(side="left", padx=10)

        # Status
        tk.Label(content, text=_t("police_station.patrol.patrol_status"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        self.status_combo = ttk.Combobox(content, values=[
            "Routine - No Incidents", "Suspicious Activity Observed",
            "Incident Reported", "Assistance Provided", "Warning Issued"
        ])
        self.status_combo.set("Routine - No Incidents")
        self.status_combo.pack(fill="x", pady=(0, 15))

        # Notes
        tk.Label(content, text=_t("police_station.patrol.notes"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        self.notes = tk.Text(content, height=6, font=("Segoe UI", 10),
                            bg=self.colors["bg_medium"], fg=self.colors["text"],
                            insertbackground=self.colors["text"])
        self.notes.pack(fill="both", expand=True, pady=(0, 15))

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=self.colors["bg_medium"],
                 fg=self.colors["text"], bd=0, padx=25, pady=10,
                 command=self.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_t("police_station.patrol.save_entry"), bg=self.colors["success"],
                 fg="white", bd=0, padx=25, pady=10,
                 command=self.save).pack(side="right", padx=5)

    def save(self):
        self.result = {
            'officer': self.officer_combo.get(),
            'area': self.area_combo.get(),
            'start_time': self.start_time.get(),
            'end_time': self.end_time.get(),
            'status': self.status_combo.get(),
            'notes': self.notes.get("1.0", "end-1c"),
            'date': datetime.now().strftime("%Y-%m-%d")
        }
        self.destroy()
