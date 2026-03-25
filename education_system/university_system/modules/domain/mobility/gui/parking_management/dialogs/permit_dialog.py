"""Permit creation/editing dialog."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import logging

from education_system.university_system.modules.domain.mobility.gui.parking_management import get_connection, PARKING_ZONES, PERMIT_TYPES


class PermitDialog:
    def __init__(self, parent, title, permit_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.permit_data = permit_data
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Student Lookup Section
        lookup_frame = ttk.LabelFrame(main_frame, text="Student Lookup", padding="5")
        lookup_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(lookup_frame, text="Student ID:").grid(row=0, column=0, sticky="w", padx=5)
        self.student_id_var = tk.StringVar()
        self.student_id_entry = ttk.Entry(lookup_frame, textvariable=self.student_id_var, width=20)
        self.student_id_entry.grid(row=0, column=1, padx=5)

        ttk.Button(lookup_frame, text="Lookup Student",
                  command=self.lookup_student).grid(row=0, column=2, padx=5)

        # User info
        ttk.Label(main_frame, text="Full Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Email:").grid(row=2, column=0, sticky="w", pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.email_var).grid(row=2, column=1, sticky="ew", pady=5)

        # Permit info
        ttk.Label(main_frame, text="Zone:").grid(row=3, column=0, sticky="w", pady=5)
        self.zone_var = tk.StringVar()
        zone_combo = ttk.Combobox(main_frame, textvariable=self.zone_var,
                                 values=list(PARKING_ZONES.keys()), state="readonly")
        zone_combo.grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Permit Type:").grid(row=4, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=PERMIT_TYPES, state="readonly")
        type_combo.grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Start Date:").grid(row=5, column=0, sticky="w", pady=5)
        self.start_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(main_frame, textvariable=self.start_var).grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="End Date:").grid(row=6, column=0, sticky="w", pady=5)
        self.end_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_var).grid(row=6, column=1, sticky="ew", pady=5)

        # Vehicle selection
        ttk.Label(main_frame, text="Vehicle (optional):").grid(row=7, column=0, sticky="w", pady=5)
        self.vehicle_var = tk.StringVar()
        self.vehicle_combo = ttk.Combobox(main_frame, textvariable=self.vehicle_var, state="readonly")
        self.vehicle_combo.grid(row=7, column=1, sticky="ew", pady=5)

        # Load vehicles
        self.load_vehicles()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

        # Auto-calculate end date when type changes
        type_combo.bind('<<ComboboxSelected>>', self.calculate_end_date)

        # Load existing data if editing
        if self.permit_data:
            self.load_permit_data()

    def load_vehicles(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT vehicle_id, license_plate, make, model FROM vehicles')
            vehicles = cursor.fetchall()
            conn.close()

            vehicle_options = ["None"] + [f"{v[0]} - {v[1]} ({v[2]} {v[3]})" for v in vehicles]
            self.vehicle_combo['values'] = vehicle_options
            self.vehicle_combo.current(0)
        except Exception as e:
            print(f"Error loading vehicles: {e}")

    def lookup_student(self):
        """Lookup student in database and autofill form"""
        student_id = self.student_id_var.get().strip()

        if not student_id:
            messagebox.showwarning("Warning", "Please enter a Student ID")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Search for student by student_id
            cursor.execute('''
                SELECT student_id, first_name, last_name, email_address
                FROM students
                WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()

            if student:
                # Autofill the form with student information
                full_name = f"{student[1]} {student[2]}"  # first_name + last_name
                email = student[3] if student[3] else ""

                self.name_var.set(full_name)
                self.email_var.set(email)

                # Also load student's vehicles if any
                cursor.execute('''
                    SELECT vehicle_id, license_plate, make, model
                    FROM vehicles
                    WHERE owner_id = ?
                ''', (student_id,))

                vehicles = cursor.fetchall()

                if vehicles:
                    # Update vehicle combo with student's vehicles at the top
                    cursor.execute('SELECT vehicle_id, license_plate, make, model FROM vehicles')
                    all_vehicles = cursor.fetchall()

                    # Put student vehicles first
                    vehicle_options = ["None"]
                    for v in vehicles:
                        vehicle_options.append(f"{v[0]} - {v[1]} ({v[2]} {v[3]}) [Student's Vehicle]")

                    # Add other vehicles
                    for v in all_vehicles:
                        if v[0] not in [sv[0] for sv in vehicles]:
                            vehicle_options.append(f"{v[0]} - {v[1]} ({v[2]} {v[3]})")

                    self.vehicle_combo['values'] = vehicle_options

                    # Auto-select first student vehicle if available
                    if len(vehicles) > 0:
                        self.vehicle_combo.current(1)  # Select first student vehicle

                messagebox.showinfo("Success", f"Student found: {full_name}\nForm auto-filled with student information.")
            else:
                messagebox.showerror("Not Found", f"No student found with ID: {student_id}")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to lookup student: {e}")
            logging.error(f"Student lookup error: {e}")

    def calculate_end_date(self, event=None):
        permit_type = self.type_var.get()
        start_date = datetime.strptime(self.start_var.get(), '%Y-%m-%d')

        if permit_type == 'Annual':
            end_date = start_date.replace(year=start_date.year + 1)
        elif permit_type == 'Semester':
            end_date = start_date + timedelta(days=120)
        elif permit_type == 'Monthly':
            end_date = start_date + timedelta(days=30)
        elif permit_type == 'Daily':
            end_date = start_date + timedelta(days=1)
        else:  # Temporary
            end_date = start_date + timedelta(days=7)

        self.end_var.set(end_date.strftime('%Y-%m-%d'))

    def load_permit_data(self):
        # Load existing permit data for editing
        if self.permit_data:
            self.name_var.set(self.permit_data[2])  # full_name
            self.email_var.set(self.permit_data[3])  # email
            self.zone_var.set(self.permit_data[4])  # zone
            self.type_var.set(self.permit_data[5])  # permit_type
            self.start_var.set(self.permit_data[6])  # start_date
            self.end_var.set(self.permit_data[7])  # end_date

    def save(self):
        # Validate required fields
        if not all([self.name_var.get(), self.email_var.get(),
                   self.zone_var.get(), self.type_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        # Get vehicle ID if selected
        vehicle_id = None
        if self.vehicle_var.get() and self.vehicle_var.get() != "None":
            vehicle_id = self.vehicle_var.get().split(" - ")[0]

        self.result = {
            'full_name': self.name_var.get(),
            'email': self.email_var.get(),
            'zone': self.zone_var.get(),
            'permit_type': self.type_var.get(),
            'start_date': self.start_var.get(),
            'end_date': self.end_var.get(),
            'vehicle_id': vehicle_id,
            'student_id': self.student_id_var.get().strip() if self.student_id_var.get().strip() else None
        }

        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()
