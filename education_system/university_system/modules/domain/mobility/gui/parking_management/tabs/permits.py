"""Permits tab mixin for ParkingManagementGUI."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

from .. import get_connection, _t
from ..dialogs.permit_dialog import PermitDialog


class PermitsMixin:
    """Mixin providing permits tab functionality."""

    def setup_permits_tab(self):
        """Setup the permits management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.permits_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text=_t("parking.btn.create_permit"), command=self.create_permit_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.edit_selected"), command=self.edit_selected_permit).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.delete_selected"), command=self.delete_selected_permit).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_permits).pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(self.permits_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
        self.permit_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.permit_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_permits)

        # Create treeview for permits
        columns = ("ID", "User", "Zone", "Type", "Start Date", "End Date", "Status", "Vehicle")
        self.permits_tree = ttk.Treeview(self.permits_frame, columns=columns, show="headings")

        # Configure columns
        for col in columns:
            self.permits_tree.heading(col, text=col)
            self.permits_tree.column(col, width=100)

        # Add scrollbars
        permits_scrolly = ttk.Scrollbar(self.permits_frame, orient=tk.VERTICAL, command=self.permits_tree.yview)
        permits_scrollx = ttk.Scrollbar(self.permits_frame, orient=tk.HORIZONTAL, command=self.permits_tree.xview)
        self.permits_tree.configure(yscrollcommand=permits_scrolly.set, xscrollcommand=permits_scrollx.set)

        # Pack treeview and scrollbars
        self.permits_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        permits_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        permits_scrollx.pack(side=tk.BOTTOM, fill=tk.X)

        # Load permits data
        self.refresh_permits()

    def refresh_permits(self):
        """Refresh permits data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT p.permit_id, p.full_name, p.zone, p.permit_type,
                   p.start_date, p.end_date, p.active_status,
                   COALESCE(v.license_plate, 'N/A') as vehicle
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            ORDER BY p.issue_date DESC
            ''')

            permits = cursor.fetchall()

            # Clear existing data
            for item in self.permits_tree.get_children():
                self.permits_tree.delete(item)

            # Insert new data - convert sqlite3.Row to tuple for display
            for permit in permits:
                permit_values = tuple(permit) if hasattr(permit, '__iter__') else permit
                self.permits_tree.insert("", tk.END, values=permit_values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh permits: {e}")

    def filter_permits(self, event=None):
        """Filter permits based on search term"""
        search_term = self.permit_search_var.get().lower()

        # Get all items
        all_items = self.permits_tree.get_children()

        for item in all_items:
            values = self.permits_tree.item(item)['values']
            # Check if search term is in any of the values
            if any(search_term in str(value).lower() for value in values):
                self.permits_tree.item(item, tags=())
            else:
                self.permits_tree.item(item, tags=('hidden',))

        # Configure tags
        self.permits_tree.tag_configure('hidden', foreground='gray')

    def create_permit_dialog(self):
        """Show create permit dialog"""
        dialog = PermitDialog(self.root, "Create New Permit")
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            # Create permit with the provided data
            try:
                self.create_permit_from_data(dialog.result)
                self.refresh_permits()
                self.update_status("Permit created successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create permit: {e}")

    def edit_selected_permit(self):
        """Edit the selected permit"""
        selected = self.permits_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a permit to edit")
            return

        # Get permit data and show edit dialog
        permit_id = self.permits_tree.item(selected[0])['values'][0]

        try:
            # Get full permit data from database
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_permits WHERE permit_id = ?', (permit_id,))
            permit_data = cursor.fetchone()
            conn.close()

            if permit_data:
                dialog = PermitDialog(self.root, "Edit Permit", permit_data)
                self.root.wait_window(dialog.dialog)

                if dialog.result:
                    self.update_permit_from_data(permit_id, dialog.result)
                    self.refresh_permits()
                    self.update_status("Permit updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit permit: {e}")

    def delete_selected_permit(self):
        """Delete the selected permit"""
        selected = self.permits_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a permit to delete")
            return

        permit_id = self.permits_tree.item(selected[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete permit {permit_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_permits WHERE permit_id = ?', (permit_id,))
                conn.commit()
                conn.close()

                self.refresh_permits()
                self.update_status("Permit deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete permit: {e}")

    def create_permit_from_data(self, data):
        """Create a permit from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        # Generate permit ID
        cursor.execute('SELECT COUNT(*) FROM parking_permits')
        count = cursor.fetchone()[0] + 1
        permit_id = f"P{data['zone']}{datetime.now().year % 100}{str(count).zfill(4)}"

        # Insert permit
        cursor.execute('''
        INSERT INTO parking_permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            permit_id,
            data.get('user_id'),
            data['full_name'],
            data['email'],
            data['zone'],
            data['permit_type'],
            data['start_date'],
            data['end_date'],
            'Active',
            data.get('vehicle_id'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        conn.commit()
        conn.close()

        # Send permit confirmation email automatically
        try:
            from education_system.university_system.infrastructure.email.email_service import send_permit_confirmation
            send_permit_confirmation(
                permit_id,
                data['email'],
                data['zone'],
                data['permit_type'],
                data['start_date'],
                data['end_date']
            )
        except Exception as e:
            logging.warning(f"Failed to send permit confirmation email: {e}")

    def update_permit_from_data(self, permit_id, data):
        """Update a permit from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE parking_permits
        SET full_name=?, email=?, zone=?, permit_type=?,
            start_date=?, end_date=?, active_status=?, vehicle_id=?
        WHERE permit_id=?
        ''', (
            data['full_name'],
            data['email'],
            data['zone'],
            data['permit_type'],
            data['start_date'],
            data['end_date'],
            data.get('active_status', 'Active'),
            data.get('vehicle_id'),
            permit_id
        ))

        conn.commit()
        conn.close()

        # Send permit update confirmation email automatically
        try:
            from education_system.university_system.infrastructure.email.email_service import send_permit_update_confirmation
            # Identify which fields were updated
            updated_fields = []
            if 'full_name' in data:
                updated_fields.append(f"Full Name: {data['full_name']}")
            if 'zone' in data:
                updated_fields.append(f"Zone: {data['zone']}")
            if 'permit_type' in data:
                updated_fields.append(f"Permit Type: {data['permit_type']}")
            if 'start_date' in data:
                updated_fields.append(f"Start Date: {data['start_date']}")
            if 'end_date' in data:
                updated_fields.append(f"End Date: {data['end_date']}")
            if 'active_status' in data:
                updated_fields.append(f"Status: {data.get('active_status', 'Active')}")

            send_permit_update_confirmation(
                permit_id,
                data['email'],
                updated_fields
            )
        except Exception as e:
            logging.warning(f"Failed to send permit update confirmation email: {e}")
