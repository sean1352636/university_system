"""Violations tab mixin for ParkingManagementGUI."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging
import os
import json

from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management import get_connection, _t
from education_system.systems.university.interfaces.gui.operations.campus.mobility.parking_management.dialogs.violation_dialog import ViolationDialog


class ViolationsMixin:
    """Mixin providing violations tab functionality."""

    def setup_violations_tab(self):
        """Setup the violations management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.violations_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text=_t("parking.btn.record_violation"), command=self.record_violation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.edit_selected"), command=self.edit_selected_violation).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.delete_selected"), command=self.delete_selected_violation).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Pay Fine", command=self.pay_selected_violation).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_violations).pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(self.violations_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
        self.violation_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.violation_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_violations)

        # Create treeview for violations
        columns = ("ID", "License Plate", "Type", "Date", "Fine", "Status", "Location", "Officer")
        self.violations_tree = ttk.Treeview(self.violations_frame, columns=columns, show="headings")

        # Configure columns
        for col in columns:
            self.violations_tree.heading(col, text=col)
            self.violations_tree.column(col, width=100)

        # Add scrollbars
        violations_scrolly = ttk.Scrollbar(self.violations_frame, orient=tk.VERTICAL, command=self.violations_tree.yview)
        violations_scrollx = ttk.Scrollbar(self.violations_frame, orient=tk.HORIZONTAL, command=self.violations_tree.xview)
        self.violations_tree.configure(yscrollcommand=violations_scrolly.set, xscrollcommand=violations_scrollx.set)

        # Pack treeview and scrollbars
        self.violations_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        violations_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        violations_scrollx.pack(side=tk.BOTTOM, fill=tk.X)

        # Load violations data
        self.refresh_violations()

    def refresh_violations(self):
        """Refresh violations data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT v.violation_id, v.license_plate, v.violation_type,
                   v.violation_date, v.fine_amount, v.payment_status,
                   v.location,
                   COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as officer
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            ORDER BY v.violation_date DESC
            ''')

            violations = cursor.fetchall()

            # Clear existing data
            for item in self.violations_tree.get_children():
                self.violations_tree.delete(item)

            # Insert new data - convert sqlite3.Row to tuple for display
            for violation in violations:
                violation_values = tuple(violation) if hasattr(violation, '__iter__') else violation
                self.violations_tree.insert("", tk.END, values=violation_values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh violations: {e}")

    def filter_violations(self, event=None):
        """Filter violations based on search term"""
        search_term = self.violation_search_var.get().lower()

        all_items = self.violations_tree.get_children()

        for item in all_items:
            values = self.violations_tree.item(item)['values']
            if any(search_term in str(value).lower() for value in values):
                self.violations_tree.item(item, tags=())
            else:
                self.violations_tree.item(item, tags=('hidden',))

        self.violations_tree.tag_configure('hidden', foreground='gray')

    def record_violation_dialog(self):
        """Show record violation dialog"""
        dialog = ViolationDialog(self.root, "Record New Violation")
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            try:
                self.record_violation_from_data(dialog.result)
                self.refresh_violations()
                self.update_status("Violation recorded successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to record violation: {e}")

    def edit_selected_violation(self):
        """Edit the selected violation"""
        selected = self.violations_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a violation to edit")
            return

        violation_id = self.violations_tree.item(selected[0])['values'][0]

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_violations WHERE violation_id = ?', (violation_id,))
            violation_data = cursor.fetchone()
            conn.close()

            if violation_data:
                dialog = ViolationDialog(self.root, "Edit Violation", violation_data)
                self.root.wait_window(dialog.dialog)

                if dialog.result:
                    self.update_violation_from_data(violation_id, dialog.result)
                    self.refresh_violations()
                    self.update_status("Violation updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit violation: {e}")

    def delete_selected_violation(self):
        """Delete the selected violation"""
        selected = self.violations_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a violation to delete")
            return

        violation_id = self.violations_tree.item(selected[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete violation {violation_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_violations WHERE violation_id = ?', (violation_id,))
                conn.commit()
                conn.close()

                self.refresh_violations()
                self.update_status("Violation deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete violation: {e}")

    def pay_selected_violation(self):
        """Pay fine for selected violation"""
        selected = self.violations_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a violation to pay.")
            return

        violation_data = self.violations_tree.item(selected[0])['values']

        # Check if already paid
        if len(violation_data) > 5 and violation_data[5] == 'Paid':
            messagebox.showinfo("Already Paid", "This violation has already been paid.")
            return

        # Process payment
        self.process_payment(violation_data)

    def record_violation_from_data(self, data):
        """Record a violation from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        # Generate violation ID
        cursor.execute('SELECT COUNT(*) FROM parking_violations')
        count = cursor.fetchone()[0] + 1
        violation_id = f"VIO{str(count).zfill(6)}"

        # Insert violation
        cursor.execute('''
        INSERT INTO parking_violations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            violation_id,
            data.get('vehicle_id'),
            data['license_plate'],
            data['violation_type'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            data['fine_amount'],
            'Unpaid',
            data['location'],
            self.current_user['id']
        ))

        conn.commit()
        conn.close()

        # Send email notification if requested
        if data.get('send_email', False) and data.get('student_email'):
            self._send_violation_email(
                violation_id,
                data['student_id'],
                data['student_email'],
                data['license_plate'],
                data['violation_type'],
                data['location'],
                data['fine_amount']
            )

    def update_violation_from_data(self, violation_id, data):
        """Update a violation from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE parking_violations
        SET violation_type=?, fine_amount=?, payment_status=?, location=?
        WHERE violation_id=?
        ''', (
            data['violation_type'],
            data['fine_amount'],
            data['payment_status'],
            data['location'],
            violation_id
        ))

        conn.commit()
        conn.close()

    def _send_violation_email(self, violation_id, student_id, student_email, license_plate, violation_type, location, fine_amount):
        """Send violation notification email to student"""
        try:
            # Get owner name - check both students and users tables
            student_name = "Student"
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # First try students table
                cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                student_data = cursor.fetchone()

                if student_data:
                    student_name = f"{student_data[0]} {student_data[1]}"
                else:
                    # Fall back to users table (for admin/staff)
                    cursor.execute('SELECT first_name, last_name, username FROM users WHERE username = ? OR id = ?',
                                 (student_id, student_id))
                    user_data = cursor.fetchone()
                    if user_data:
                        student_name = f"{user_data[0] or ''} {user_data[1] or ''}".strip() or user_data[2] or "User"

                conn.close()
            except Exception as e:
                logging.error(f"Could not fetch owner name: {e}")

            # Load email template
            # Navigate from this file up to university_system root, then to templates
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))),
                'templates', 'email', 'parking_violation_notice.json'
            )

            with open(template_path, 'r') as f:
                template = json.load(f)

            # Prepare template variables
            violation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            signature = "Parking Services\nUniversity Parking Management\nPhone: (555) 123-4567\nEmail: parking@university.edu"

            # Replace variables in subject and body
            subject = template['subject'].replace('$violation_id', violation_id)

            body = template['body']
            body = body.replace('$student_name', student_name)
            body = body.replace('$violation_id', violation_id)
            body = body.replace('$violation_type', violation_type)
            body = body.replace('$license_plate', license_plate)
            body = body.replace('$location', location)
            body = body.replace('$violation_date', violation_date)
            body = body.replace('$fine_amount', f"{fine_amount:.2f}")
            body = body.replace('$payment_status', 'Unpaid')
            body = body.replace('$signature', signature)

            # Send email using email service
            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email
                send_email(
                    recipient_email=student_email,
                    subject=subject,
                    body=body
                )
                logging.info(f"Violation notification email sent to {student_email} for violation {violation_id}")
            except ImportError:
                # Fallback: Log the email content
                logging.warning(f"Email service not available. Email would have been sent to {student_email}:")
                logging.info(f"Subject: {subject}")
                logging.info(f"Body: {body}")
                messagebox.showinfo("Email Notification",
                    f"Email service unavailable.\n\n"
                    f"Violation notice for {student_name} logged.\n"
                    f"Manual notification required to: {student_email}")

        except Exception as e:
            logging.error(f"Failed to send violation email: {e}")
            messagebox.showwarning("Email Error",
                "Violation recorded successfully, but email notification failed.\n"
                "Please notify the student manually.")
