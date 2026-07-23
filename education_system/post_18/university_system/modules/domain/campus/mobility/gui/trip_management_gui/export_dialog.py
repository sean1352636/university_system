import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.post_18.university_system.modules.domain.campus.mobility.gui.trip_management_gui._imports import safe_db_operation


class ExportDataDialog(Dialog):
    def __init__(self, parent, auth):
        self.auth = auth
        super().__init__(parent, "Export Trip Data")

    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text="Select data to export:", font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        # Export options
        self.export_trips_var = tk.BooleanVar(value=True)
        self.export_participants_var = tk.BooleanVar(value=True)
        self.export_expenses_var = tk.BooleanVar()
        self.export_staff_var = tk.BooleanVar()

        ttk.Checkbutton(master, text="Trip Information", variable=self.export_trips_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(master, text="Participant Data", variable=self.export_participants_var).pack(anchor=tk.W, pady=2)

        if self.auth.check_permission('view_financial_reports'):
            ttk.Checkbutton(master, text="Expense Data", variable=self.export_expenses_var).pack(anchor=tk.W, pady=2)

        if self.auth.check_permission('manage_trips'):
            ttk.Checkbutton(master, text="Staff Assignments", variable=self.export_staff_var).pack(anchor=tk.W, pady=2)

        # Format selection
        ttk.Label(master, text="Export format:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(20, 5))

        self.format_var = tk.StringVar(value="CSV")
        ttk.Radiobutton(master, text="CSV (Comma Separated Values)", variable=self.format_var, value="CSV").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(master, text="TSV (Tab Separated Values)", variable=self.format_var, value="TSV").pack(anchor=tk.W, pady=2)

        return None

    def validate(self):
        """Validate export options"""
        if not any([self.export_trips_var.get(), self.export_participants_var.get(),
                   self.export_expenses_var.get(), self.export_staff_var.get()]):
            messagebox.showerror("Validation Error", "Please select at least one data type to export.")
            return False
        return True

    def apply(self):
        """Export the data"""
        try:
            # Ask for save location
            file_extension = "csv" if self.format_var.get() == "CSV" else "tsv"
            delimiter = "," if self.format_var.get() == "CSV" else "\t"

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"trip_data_export_{timestamp}.{file_extension}"

            filename = filedialog.asksaveasfilename(
                defaultextension=f".{file_extension}",
                filetypes=[(f"{self.format_var.get()} files", f"*.{file_extension}"), ("All files", "*.*")],
                initialvalue=default_filename
            )

            if not filename:
                return

            # Export selected data
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                import csv
                writer = csv.writer(csvfile, delimiter=delimiter)

                # Export trips
                if self.export_trips_var.get():
                    self.export_trips_data(writer)

                # Export participants
                if self.export_participants_var.get():
                    self.export_participants_data(writer)

                # Export expenses
                if self.export_expenses_var.get() and self.auth.check_permission('view_financial_reports'):
                    self.export_expenses_data(writer)

                # Export staff
                if self.export_staff_var.get() and self.auth.check_permission('manage_trips'):
                    self.export_staff_data(writer)

            messagebox.showinfo("Success", f"Data exported successfully to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {e}")

    def export_trips_data(self, writer):
        """Export trips data"""
        def get_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.description, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status, t.created_at, t.updated_at,
                   u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN users u ON t.created_by = u.id
            ORDER BY t.start_date
            ''')
            return cursor.fetchall()

        trips = safe_db_operation(get_trips_operation)

        if trips:
            # Write header
            writer.writerow(['=== TRIPS DATA ==='])
            writer.writerow(['Trip ID', 'Name', 'Description', 'Destination', 'Start Date', 'End Date',
                           'Max Participants', 'Cost', 'Status', 'Created At', 'Updated At', 'Created By'])

            # Write data
            for trip in trips:
                writer.writerow(trip)

            writer.writerow([])  # Empty row separator

    def export_participants_data(self, writer):
        """Export participants data"""
        def get_participants_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT tp.id, t.trip_name, tp.student_id,
                   s.first_name || ' ' || s.last_name as student_name,
                   s.email_address, tp.registration_date, tp.payment_status, tp.status,
                   tp.emergency_contact, tp.medical_info, tp.dietary_requirements
            FROM trip_participants tp
            JOIN trips t ON tp.trip_id = t.id
            LEFT JOIN students s ON tp.student_id = s.student_id
            ORDER BY t.trip_name, tp.registration_date
            ''')
            return cursor.fetchall()

        participants = safe_db_operation(get_participants_operation)

        if participants:
            # Write header
            writer.writerow(['=== PARTICIPANTS DATA ==='])
            writer.writerow(['Participant ID', 'Trip Name', 'Student ID', 'Student Name', 'Email',
                           'Registration Date', 'Payment Status', 'Status', 'Emergency Contact',
                           'Medical Info', 'Dietary Requirements'])

            # Write data
            for participant in participants:
                writer.writerow(participant)

            writer.writerow([])  # Empty row separator

    def export_expenses_data(self, writer):
        """Export expenses data"""
        def get_expenses_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT te.id, t.trip_name, te.category, te.description, te.amount, te.date,
                   u.first_name || ' ' || u.last_name as recorded_by
            FROM trip_expenses te
            JOIN trips t ON te.trip_id = t.id
            LEFT JOIN users u ON te.recorded_by = u.id
            ORDER BY t.trip_name, te.date
            ''')
            return cursor.fetchall()

        expenses = safe_db_operation(get_expenses_operation)

        if expenses:
            # Write header
            writer.writerow(['=== EXPENSES DATA ==='])
            writer.writerow(['Expense ID', 'Trip Name', 'Category', 'Description', 'Amount', 'Date', 'Recorded By'])

            # Write data
            for expense in expenses:
                writer.writerow(expense)

            writer.writerow([])  # Empty row separator

    def export_staff_data(self, writer):
        """Export staff assignments data"""
        def get_staff_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT ts.id, t.trip_name, u.first_name || ' ' || u.last_name as staff_name,
                   ts.role, ts.assigned_date
            FROM trip_staff ts
            JOIN trips t ON ts.trip_id = t.id
            JOIN users u ON ts.staff_user_id = u.id
            ORDER BY t.trip_name, ts.role
            ''')
            return cursor.fetchall()

        staff = safe_db_operation(get_staff_operation)

        if staff:
            # Write header
            writer.writerow(['=== STAFF ASSIGNMENTS DATA ==='])
            writer.writerow(['Assignment ID', 'Trip Name', 'Staff Name', 'Role', 'Assigned Date'])

            # Write data
            for assignment in staff:
                writer.writerow(assignment)
