"""Complaint form dialog."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from education_system.university_system.modules.domain.campus.gui.security.constants import CAMPUS_COMPLAINT_TYPES
from education_system.university_system.modules.domain.campus.gui.security.widgets import ScrollableFrame


class ComplaintFormDialog(tk.Toplevel):
    """Dialog for filing complaints with user info pre-filled."""

    def __init__(self, parent, colors, current_user):
        super().__init__(parent)
        self.title("File Complaint")
        self.geometry("550x600")
        self.configure(bg=colors["bg_dark"])
        self.transient(parent)

        self.colors = colors
        self.current_user = current_user
        self.result = None

        self.setup_ui()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 550) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()
        self.wait_window()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg=self.colors["accent"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=_t("police_station.complaints.file_complaint"), font=("Segoe UI", 16, "bold"),
                bg=self.colors["accent"], fg="white").pack(pady=15)

        # Scrollable content
        scroll_frame = ScrollableFrame(self, bg=self.colors["bg_dark"])
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        content = scroll_frame.scrollable_frame

        # Complainant Info Section
        tk.Label(content, text=_t("police_station.complaints.complainant_info"), font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(10, 5))

        info_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        info_frame.pack(fill="x", pady=5)

        # Pre-fill with current user
        name = ""
        email = ""
        phone = ""
        if self.current_user:
            name = self.current_user.get('name') or self.current_user.get('full_name', '')
            if not name:
                first = self.current_user.get('first_name', '')
                last = self.current_user.get('last_name', '')
                name = f"{first} {last}".strip()
            email = self.current_user.get('email', '')
            phone = self.current_user.get('phone', '')

        # Name
        self.name_entry = self.create_field(info_frame, "Name:", name)
        self.email_entry = self.create_field(info_frame, "Email:", email)
        self.phone_entry = self.create_field(info_frame, "Phone:", phone)

        # Complaint Details Section
        tk.Label(content, text=_t("police_station.complaints.complaint_details"), font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(15, 5))

        details_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        details_frame.pack(fill="x", pady=5)

        # Complaint Type
        type_frame = tk.Frame(details_frame, bg=self.colors["bg_medium"])
        type_frame.pack(fill="x", pady=5)
        tk.Label(type_frame, text=_t("police_station.case_details.type"), font=("Segoe UI", 10), width=12,
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.type_combo = ttk.Combobox(type_frame, values=CAMPUS_COMPLAINT_TYPES)
        self.type_combo.set("Select type...")
        self.type_combo.pack(side="right", fill="x", expand=True)

        # Priority
        priority_frame = tk.Frame(details_frame, bg=self.colors["bg_medium"])
        priority_frame.pack(fill="x", pady=5)
        tk.Label(priority_frame, text=_t("police_station.case_details.priority"), font=("Segoe UI", 10), width=12,
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.priority_combo = ttk.Combobox(priority_frame, values=["Low", "Medium", "High", "Urgent"])
        self.priority_combo.set("Medium")
        self.priority_combo.pack(side="right", fill="x", expand=True)

        # Date/Time of Incident
        self.incident_date = self.create_field(details_frame, "Incident Date:",
                                               datetime.now().strftime("%Y-%m-%d"))
        self.incident_time = self.create_field(details_frame, "Incident Time:", "")

        # Location
        self.location_entry = self.create_field(details_frame, "Location:", "")

        # Description
        tk.Label(content, text=_t("police_station.case_details.description"), font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(15, 5))

        desc_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        desc_frame.pack(fill="x", pady=5)

        self.description = tk.Text(desc_frame, height=6, font=("Segoe UI", 10),
                                  bg=self.colors["bg_dark"], fg=self.colors["text"],
                                  insertbackground=self.colors["text"], wrap=tk.WORD)
        self.description.pack(fill="x")

        # Suspect Info (optional)
        tk.Label(content, text=_t("police_station.complaints.suspect_info"), font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(15, 5))

        suspect_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        suspect_frame.pack(fill="x", pady=5)

        self.suspect_desc = self.create_field(suspect_frame, "Description:", "")

        # Buttons
        btn_frame = tk.Frame(self, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", padx=20, pady=15)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=self.colors["bg_medium"],
                 fg=self.colors["text"], font=("Segoe UI", 11), bd=0,
                 padx=25, pady=10, command=self.destroy).pack(side="right", padx=5)

        tk.Button(btn_frame, text=_t("police_station.complaints.submit_complaint"), bg=self.colors["accent"],
                 fg="white", font=("Segoe UI", 11, "bold"), bd=0,
                 padx=25, pady=10, command=self.save).pack(side="right", padx=5)

    def create_field(self, parent, label, value):
        frame = tk.Frame(parent, bg=self.colors["bg_medium"])
        frame.pack(fill="x", pady=5)

        tk.Label(frame, text=label, font=("Segoe UI", 10), width=12,
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")

        entry = tk.Entry(frame, font=("Segoe UI", 10), bg=self.colors["bg_dark"],
                        fg=self.colors["text"], insertbackground=self.colors["text"])
        entry.insert(0, value)
        entry.pack(side="right", fill="x", expand=True, ipady=3)

        return entry

    def save(self):
        if "Select" in self.type_combo.get():
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.select_complaint_type"))
            return

        if not self.description.get("1.0", "end-1c").strip():
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.provide_description"))
            return

        self.result = {
            'complainant': self.name_entry.get(),
            'email': self.email_entry.get(),
            'phone': self.phone_entry.get(),
            'type': self.type_combo.get(),
            'priority': self.priority_combo.get(),
            'incident_date': self.incident_date.get(),
            'incident_time': self.incident_time.get(),
            'location': self.location_entry.get(),
            'description': self.description.get("1.0", "end-1c"),
            'suspect_description': self.suspect_desc.get(),
            'status': 'Pending',
            'date': datetime.now().strftime("%Y-%m-%d")
        }
        self.destroy()
