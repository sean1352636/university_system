"""Evidence dialog."""

import tkinter as tk
from tkinter import ttk

from education_system.university_system.modules.shared.utils.i18n import get_text as _t


class EvidenceDialog:
    """Dialog for adding/editing evidence"""
    def __init__(self, parent, title, colors, evidence=None):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x400")
        self.dialog.configure(bg=colors["bg_dark"])
        self.dialog.transient(parent)

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_visibility()
        self.dialog.grab_set()

        fields = [
            ("Description:", "description", None),
            ("Related Case #:", "case_number", None),
            ("Evidence Type:", "type", ["Physical", "Digital", "Document", "Weapon", "Clothing", "Vehicle", "Other"]),
            ("Storage Location:", "location", None),
            ("Chain of Custody:", "custody", None),
        ]

        self.entries = {}
        for label, field, options in fields:
            frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
            frame.pack(fill="x", padx=20, pady=5)

            tk.Label(frame, text=label, font=("Segoe UI", 10), width=16,
                    bg=colors["bg_dark"], fg=colors["text"]).pack(side="left")

            if options:
                self.entries[field] = ttk.Combobox(frame, values=options)
                self.entries[field].set(evidence.get(field, options[0]) if evidence else options[0])
            else:
                self.entries[field] = tk.Entry(frame, font=("Segoe UI", 10),
                                              bg=colors["bg_medium"], fg=colors["text"],
                                              insertbackground=colors["text"])
                if evidence:
                    self.entries[field].insert(0, evidence.get(field, ""))
            self.entries[field].pack(side="right", fill="x", expand=True, ipady=5)

        btn_frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
        btn_frame.pack(fill="x", padx=20, pady=20)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=colors["bg_medium"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.dialog.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_t("police_station.buttons.save"), bg=colors["accent"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.save).pack(side="right", padx=5)

        self.dialog.wait_window()

    def save(self):
        self.result = {field: self.entries[field].get() for field in self.entries}
        self.dialog.destroy()
