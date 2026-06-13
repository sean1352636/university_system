"""Parking lot creation/editing dialog."""
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.campus.mobility.gui.parking_management import PARKING_ZONES


class LotDialog:
    def __init__(self, parent, title, lot_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.lot_data = lot_data
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Lot info
        ttk.Label(main_frame, text="Lot Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Location:").grid(row=1, column=0, sticky="w", pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Total Spaces:").grid(row=2, column=0, sticky="w", pady=5)
        self.spaces_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.spaces_var).grid(row=2, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Zone:").grid(row=3, column=0, sticky="w", pady=5)
        self.zone_var = tk.StringVar()
        zone_combo = ttk.Combobox(main_frame, textvariable=self.zone_var,
                                 values=list(PARKING_ZONES.keys()), state="readonly")
        zone_combo.grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Hours of Operation:").grid(row=4, column=0, sticky="w", pady=5)
        self.hours_var = tk.StringVar(value="24/7")
        ttk.Entry(main_frame, textvariable=self.hours_var).grid(row=4, column=1, sticky="ew", pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

        # Load existing data if editing
        if self.lot_data:
            self.load_lot_data()

    def load_lot_data(self):
        if self.lot_data:
            self.name_var.set(self.lot_data[1])     # lot_name
            self.location_var.set(self.lot_data[2]) # location
            self.spaces_var.set(str(self.lot_data[3]))  # total_spaces
            self.zone_var.set(self.lot_data[5])     # zone
            self.hours_var.set(self.lot_data[6])    # hours_of_operation

    def save(self):
        # Validate required fields
        if not all([self.name_var.get(), self.location_var.get(),
                   self.spaces_var.get(), self.zone_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            total_spaces = int(self.spaces_var.get())
            if total_spaces <= 0:
                raise ValueError("Total spaces must be positive")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number of spaces")
            return

        self.result = {
            'lot_name': self.name_var.get(),
            'location': self.location_var.get(),
            'total_spaces': total_spaces,
            'zone': self.zone_var.get(),
            'hours': self.hours_var.get() or "24/7"
        }

        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()
