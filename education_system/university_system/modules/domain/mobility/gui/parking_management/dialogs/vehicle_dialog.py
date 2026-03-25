"""Vehicle registration/editing dialog."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

from education_system.university_system.modules.domain.mobility.gui.parking_management import get_connection, VEHICLE_TYPES


class VehicleDialog:
    def __init__(self, parent, title, vehicle_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.vehicle_data = vehicle_data
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Student/Owner Lookup Section
        lookup_frame = ttk.LabelFrame(main_frame, text="Owner Lookup", padding="5")
        lookup_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(lookup_frame, text="Student ID:").grid(row=0, column=0, sticky="w", padx=5)
        self.owner_id_var = tk.StringVar()
        self.owner_id_entry = ttk.Entry(lookup_frame, textvariable=self.owner_id_var, width=20)
        self.owner_id_entry.grid(row=0, column=1, padx=5)

        ttk.Button(lookup_frame, text="Lookup Owner",
                  command=self.lookup_owner).grid(row=0, column=2, padx=5)

        # Owner name display (read-only)
        ttk.Label(main_frame, text="Owner Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.owner_name_var = tk.StringVar(value="Not linked")
        ttk.Entry(main_frame, textvariable=self.owner_name_var, state="readonly").grid(row=1, column=1, sticky="ew", pady=5)

        # Vehicle info
        ttk.Label(main_frame, text="License Plate:").grid(row=2, column=0, sticky="w", pady=5)
        self.plate_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.plate_var).grid(row=2, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Make:").grid(row=3, column=0, sticky="w", pady=5)
        self.make_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.make_var).grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Model:").grid(row=4, column=0, sticky="w", pady=5)
        self.model_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.model_var).grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Year:").grid(row=5, column=0, sticky="w", pady=5)
        self.year_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.year_var).grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Color:").grid(row=6, column=0, sticky="w", pady=5)
        self.color_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.color_var).grid(row=6, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Vehicle Type:").grid(row=7, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=VEHICLE_TYPES, state="readonly")
        type_combo.grid(row=7, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Registration State:").grid(row=8, column=0, sticky="w", pady=5)
        self.state_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.state_var).grid(row=8, column=1, sticky="ew", pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

        # Load existing data if editing
        if self.vehicle_data:
            self.load_vehicle_data()

    def load_vehicle_data(self):
        if self.vehicle_data:
            self.plate_var.set(self.vehicle_data[1])  # license_plate
            self.make_var.set(self.vehicle_data[2])   # make
            self.model_var.set(self.vehicle_data[3])  # model
            self.year_var.set(str(self.vehicle_data[4]))  # year
            self.color_var.set(self.vehicle_data[5])  # color
            self.type_var.set(self.vehicle_data[6])   # vehicle_type
            self.state_var.set(self.vehicle_data[8])  # registration_state

            # Load owner info if available
            if self.vehicle_data[7]:  # owner_id
                self.owner_id_var.set(self.vehicle_data[7])
                self.lookup_owner()  # Auto-lookup to display owner name

    def lookup_owner(self):
        """Lookup vehicle owner (student/user) in database"""
        owner_id = self.owner_id_var.get().strip()

        if not owner_id:
            self.owner_name_var.set("Not linked")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Try to find in users table first (for foreign key compatibility)
            cursor.execute('''
                SELECT id, first_name, last_name, username
                FROM users
                WHERE username = ? OR id = ?
            ''', (owner_id, owner_id))

            user = cursor.fetchone()

            if user:
                # user = (id, first_name, last_name, username)
                owner_name = f"{user[1] or ''} {user[2] or ''}".strip() or user[3] or "Unknown"
                self.owner_name_var.set(owner_name)
                # Update the owner_id_var to the actual user.id for foreign key
                self.owner_id_var.set(str(user[0]))
                messagebox.showinfo("Success", f"Owner found: {owner_name}")
            else:
                # Fallback to students table
                cursor.execute('''
                    SELECT first_name, last_name
                    FROM students
                    WHERE student_id = ?
                ''', (owner_id,))

                student = cursor.fetchone()

                if student:
                    owner_name = f"{student[0]} {student[1]}"
                    self.owner_name_var.set(owner_name)
                    messagebox.showwarning("Note",
                        f"Student found: {owner_name}\n\n"
                        f"However, this student doesn't have a user account.\n"
                        f"Vehicle will be registered without owner link.\n"
                        f"Owner ID field will be cleared.")
                    # Clear owner_id since no matching user exists
                    self.owner_id_var.set("")
                else:
                    self.owner_name_var.set("Not found")
                    messagebox.showwarning("Not Found",
                        f"No user or student found with ID: {owner_id}\n\n"
                        f"Owner ID field will be cleared.")
                    self.owner_id_var.set("")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to lookup owner: {e}")
            logging.error(f"Owner lookup error: {e}")

    def save(self):
        # Validate required fields
        if not all([self.plate_var.get(), self.make_var.get(),
                   self.model_var.get(), self.year_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            year = int(self.year_var.get())
            if year < 1900 or year > datetime.now().year + 1:
                raise ValueError("Invalid year")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid year")
            return

        self.result = {
            'license_plate': self.plate_var.get().upper(),
            'make': self.make_var.get(),
            'model': self.model_var.get(),
            'year': year,
            'color': self.color_var.get(),
            'vehicle_type': self.type_var.get() or 'Sedan',
            'registration_state': self.state_var.get().upper(),
            'owner_id': self.owner_id_var.get().strip() if self.owner_id_var.get().strip() else None
        }

        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()
