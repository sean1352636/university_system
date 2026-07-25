"""Violation recording/editing dialog."""
import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management import get_connection


class ViolationDialog:
    def __init__(self, parent, title, violation_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("550x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.violation_data = violation_data
        self.vehicle_id = None
        self.student_id = None
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Vehicle Lookup Section
        lookup_frame = ttk.LabelFrame(main_frame, text="Vehicle Lookup", padding="5")
        lookup_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(lookup_frame, text="License Plate:").grid(row=0, column=0, sticky="w", padx=5)
        self.plate_var = tk.StringVar()
        self.plate_entry = ttk.Entry(lookup_frame, textvariable=self.plate_var, width=20)
        self.plate_entry.grid(row=0, column=1, padx=5)

        ttk.Button(lookup_frame, text="Lookup Vehicle",
                  command=self.lookup_vehicle).grid(row=0, column=2, padx=5)

        # Vehicle & Owner Info Display (read-only)
        info_frame = ttk.LabelFrame(main_frame, text="Vehicle & Owner Information", padding="5")
        info_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(info_frame, text="Vehicle:").grid(row=0, column=0, sticky="w", pady=2)
        self.vehicle_info_var = tk.StringVar(value="Not found")
        ttk.Entry(info_frame, textvariable=self.vehicle_info_var, state="readonly", width=40).grid(row=0, column=1, sticky="ew", pady=2, padx=(5, 0))

        ttk.Label(info_frame, text="Owner:").grid(row=1, column=0, sticky="w", pady=2)
        self.owner_info_var = tk.StringVar(value="Not found")
        ttk.Entry(info_frame, textvariable=self.owner_info_var, state="readonly", width=40).grid(row=1, column=1, sticky="ew", pady=2, padx=(5, 0))

        ttk.Label(info_frame, text="Email:").grid(row=2, column=0, sticky="w", pady=2)
        self.email_var = tk.StringVar(value="Not found")
        ttk.Entry(info_frame, textvariable=self.email_var, state="readonly", width=40).grid(row=2, column=1, sticky="ew", pady=2, padx=(5, 0))

        info_frame.columnconfigure(1, weight=1)

        # Violation info
        ttk.Label(main_frame, text="Violation Details", font=('Arial', 10, 'bold')).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 5))

        ttk.Label(main_frame, text="Violation Type:").grid(row=3, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        violation_types = ["No Permit", "Expired Permit", "Wrong Zone", "Improper Parking",
                          "Blocking Access", "Fire Lane", "Handicap Zone", "Other"]
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=violation_types, state="readonly")
        type_combo.grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Location:").grid(row=4, column=0, sticky="w", pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var).grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Fine Amount:").grid(row=5, column=0, sticky="w", pady=5)
        self.fine_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.fine_var).grid(row=5, column=1, sticky="ew", pady=5)

        # Payment status (for editing)
        if self.violation_data:
            ttk.Label(main_frame, text="Payment Status:").grid(row=6, column=0, sticky="w", pady=5)
            self.status_var = tk.StringVar()
            status_combo = ttk.Combobox(main_frame, textvariable=self.status_var,
                                       values=["Paid", "Unpaid", "Appealed", "Waived"], state="readonly")
            status_combo.grid(row=6, column=1, sticky="ew", pady=5)

        # Send Email Notification checkbox
        ttk.Label(main_frame, text="Notification:").grid(row=7, column=0, sticky="w", pady=5)
        self.send_email_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Send violation email to owner",
                       variable=self.send_email_var).grid(row=7, column=1, sticky="w", pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

        # Auto-set fine amount based on violation type
        type_combo.bind('<<ComboboxSelected>>', self.set_default_fine)

        # Load existing data if editing
        if self.violation_data:
            self.load_violation_data()

    def lookup_vehicle(self):
        """Lookup vehicle and owner from license plate"""
        license_plate = self.plate_var.get().strip().upper()

        if not license_plate:
            messagebox.showwarning("Warning", "Please enter a license plate")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Search for vehicle by license plate
            cursor.execute('''
                SELECT vehicle_id, license_plate, make, model, year, color, owner_id
                FROM vehicles
                WHERE UPPER(license_plate) = ?
            ''', (license_plate,))

            vehicle = cursor.fetchone()

            if vehicle:
                self.vehicle_id = vehicle[0]
                vehicle_desc = f"{vehicle[2]} {vehicle[3]} {vehicle[4]} ({vehicle[5]})"
                self.vehicle_info_var.set(vehicle_desc)

                # Lookup owner if vehicle has owner_id
                if vehicle[6]:  # owner_id
                    owner_id = vehicle[6]
                    owner_found = False

                    # First try students table
                    cursor.execute('''
                        SELECT student_id, first_name, last_name, email_address
                        FROM students
                        WHERE student_id = ?
                    ''', (owner_id,))

                    student = cursor.fetchone()

                    if student:
                        self.student_id = student[0]
                        owner_name = f"{student[1]} {student[2]}"
                        email = student[3] if student[3] else "No email on file"
                        owner_found = True
                    else:
                        # Fall back to users table (for admin/staff)
                        cursor.execute('''
                            SELECT username, first_name, last_name, email
                            FROM users
                            WHERE username = ? OR id = ?
                        ''', (owner_id, owner_id))

                        user = cursor.fetchone()

                        if user:
                            self.student_id = user[0]  # Use username as ID
                            owner_name = f"{user[1] or ''} {user[2] or ''}".strip() or user[0]
                            email = user[3] if user[3] else "No email on file"
                            owner_found = True

                    if owner_found:
                        self.owner_info_var.set(owner_name)
                        self.email_var.set(email)

                        messagebox.showinfo("Success",
                            f"Vehicle found!\n\n"
                            f"Vehicle: {vehicle_desc}\n"
                            f"Owner: {owner_name}\n"
                            f"Email: {email}")
                    else:
                        self.owner_info_var.set("Owner not found in database")
                        self.email_var.set("No email")
                        messagebox.showwarning("Partial Match",
                            f"Vehicle found: {vehicle_desc}\n"
                            f"But owner ID {owner_id} not found in students or users database")
                else:
                    self.owner_info_var.set("No owner linked")
                    self.email_var.set("No email")
                    messagebox.showinfo("Vehicle Found",
                        f"Vehicle found: {vehicle_desc}\n"
                        f"No owner is linked to this vehicle")
            else:
                self.vehicle_info_var.set("Not found")
                self.owner_info_var.set("Not found")
                self.email_var.set("Not found")
                self.vehicle_id = None
                self.student_id = None
                messagebox.showwarning("Not Found",
                    f"No vehicle found with license plate: {license_plate}")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to lookup vehicle: {e}")
            logging.error(f"Vehicle lookup error in violation dialog: {e}")

    def set_default_fine(self, event=None):
        violation_type = self.type_var.get()
        fine_amounts = {
            "No Permit": 50.00,
            "Expired Permit": 40.00,
            "Wrong Zone": 40.00,
            "Improper Parking": 30.00,
            "Blocking Access": 75.00,
            "Fire Lane": 100.00,
            "Handicap Zone": 250.00,
            "Other": 50.00
        }

        default_fine = fine_amounts.get(violation_type, 50.00)
        self.fine_var.set(str(default_fine))

    def load_violation_data(self):
        if self.violation_data:
            self.plate_var.set(self.violation_data[2])  # license_plate
            self.type_var.set(self.violation_data[3])   # violation_type
            self.location_var.set(self.violation_data[7])  # location
            self.fine_var.set(str(self.violation_data[5]))  # fine_amount
            if hasattr(self, 'status_var'):
                self.status_var.set(self.violation_data[6])  # payment_status

    def save(self):
        # Validate required fields
        if not all([self.plate_var.get(), self.type_var.get(),
                   self.location_var.get(), self.fine_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            fine_amount = float(self.fine_var.get())
            if fine_amount < 0:
                raise ValueError("Fine amount cannot be negative")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid fine amount")
            return

        self.result = {
            'license_plate': self.plate_var.get().upper(),
            'violation_type': self.type_var.get(),
            'location': self.location_var.get(),
            'fine_amount': fine_amount,
            'payment_status': getattr(self, 'status_var', tk.StringVar(value='Unpaid')).get(),
            'vehicle_id': self.vehicle_id,
            'student_id': self.student_id,
            'send_email': self.send_email_var.get(),
            'student_email': self.email_var.get() if self.email_var.get() not in ["Not found", "No email", "No email on file"] else None
        }

        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()
