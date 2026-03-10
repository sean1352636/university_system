"""Criminal record dialog."""

import tkinter as tk
from tkinter import ttk

from education_system.university_system.modules.shared.utils.i18n import get_text as _t


class CriminalDialog:
    """Dialog for adding criminal records"""
    def __init__(self, parent, title, colors):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x500")
        self.dialog.configure(bg=colors["bg_dark"])
        self.dialog.transient(parent)

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 500) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_visibility()
        self.dialog.grab_set()

        fields = [
            ("Name:", "name", None),
            ("Crime:", "crime", ["Theft", "Assault", "Fraud", "Drug Possession", "Vandalism", "Trespassing", "Other"]),
            ("Status:", "status", ["In Custody", "Released", "Wanted", "On Parole", "Under Investigation"]),
            ("Arrest Date:", "arrest_date", None),
            ("Related Case #:", "case_number", None),
        ]

        self.entries = {}
        for label, field, options in fields:
            frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
            frame.pack(fill="x", padx=20, pady=5)

            tk.Label(frame, text=label, font=("Segoe UI", 10), width=14,
                    bg=colors["bg_dark"], fg=colors["text"]).pack(side="left")

            if options:
                self.entries[field] = ttk.Combobox(frame, values=options)
                self.entries[field].set(options[0])
            else:
                self.entries[field] = tk.Entry(frame, font=("Segoe UI", 10),
                                              bg=colors["bg_medium"], fg=colors["text"],
                                              insertbackground=colors["text"])
            self.entries[field].pack(side="right", fill="x", expand=True, ipady=5)

        desc_frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
        desc_frame.pack(fill="both", expand=True, padx=20, pady=5)

        tk.Label(desc_frame, text=_t("police_station.case_details.investigation_notes"), font=("Segoe UI", 10),
                bg=colors["bg_dark"], fg=colors["text"]).pack(anchor="w")

        self.description = tk.Text(desc_frame, height=6, font=("Segoe UI", 10),
                                  bg=colors["bg_medium"], fg=colors["text"],
                                  insertbackground=colors["text"])
        self.description.pack(fill="both", expand=True)

        btn_frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
        btn_frame.pack(fill="x", padx=20, pady=15)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=colors["bg_medium"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.dialog.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_t("police_station.buttons.save"), bg=colors["accent"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.save).pack(side="right", padx=5)

        self.dialog.wait_window()

    def save(self):
        self.result = {
            "name": self.entries["name"].get(),
            "crime": self.entries["crime"].get(),
            "status": self.entries["status"].get(),
            "arrest_date": self.entries["arrest_date"].get(),
            "case_number": self.entries["case_number"].get(),
            "description": self.description.get("1.0", "end-1c")
        }
        self.dialog.destroy()
