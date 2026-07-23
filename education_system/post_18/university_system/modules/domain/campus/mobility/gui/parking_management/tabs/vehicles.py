"""Vehicles tab mixin for ParkingManagementGUI."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

from education_system.post_18.university_system.modules.domain.campus.mobility.gui.parking_management import get_connection, _t
from education_system.post_18.university_system.modules.domain.campus.mobility.gui.parking_management.dialogs.vehicle_dialog import VehicleDialog


class VehiclesMixin:
    """Mixin providing vehicles tab functionality."""

    def setup_vehicles_tab(self):
        """Setup the vehicles management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.vehicles_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text=_t("parking.btn.register_vehicle"), command=self.register_vehicle_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.edit_selected"), command=self.edit_selected_vehicle).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.delete_selected"), command=self.delete_selected_vehicle).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_vehicles).pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(self.vehicles_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
        self.vehicle_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.vehicle_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_vehicles)

        # Create treeview for vehicles
        columns = ("ID", "License Plate", "Make", "Model", "Year", "Color", "Type", "Owner")
        self.vehicles_tree = ttk.Treeview(self.vehicles_frame, columns=columns, show="headings")

        # Configure columns
        for col in columns:
            self.vehicles_tree.heading(col, text=col)
            self.vehicles_tree.column(col, width=100)

        # Add scrollbars
        vehicles_scrolly = ttk.Scrollbar(self.vehicles_frame, orient=tk.VERTICAL, command=self.vehicles_tree.yview)
        vehicles_scrollx = ttk.Scrollbar(self.vehicles_frame, orient=tk.HORIZONTAL, command=self.vehicles_tree.xview)
        self.vehicles_tree.configure(yscrollcommand=vehicles_scrolly.set, xscrollcommand=vehicles_scrollx.set)

        # Pack treeview and scrollbars
        self.vehicles_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        vehicles_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        vehicles_scrollx.pack(side=tk.BOTTOM, fill=tk.X)

        # Load vehicles data
        self.refresh_vehicles()

    def refresh_vehicles(self):
        """Refresh vehicles data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT v.vehicle_id, v.license_plate, v.make, v.model, v.year,
                   v.color, v.vehicle_type,
                   COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as owner
            FROM vehicles v
            LEFT JOIN users u ON v.owner_id = u.id
            ORDER BY v.vehicle_id
            ''')

            vehicles = cursor.fetchall()

            # Clear existing data
            for item in self.vehicles_tree.get_children():
                self.vehicles_tree.delete(item)

            # Insert new data - convert sqlite3.Row to tuple for display
            for vehicle in vehicles:
                vehicle_values = tuple(vehicle) if hasattr(vehicle, '__iter__') else vehicle
                self.vehicles_tree.insert("", tk.END, values=vehicle_values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh vehicles: {e}")

    def filter_vehicles(self, event=None):
        """Filter vehicles based on search term"""
        search_term = self.vehicle_search_var.get().lower()

        all_items = self.vehicles_tree.get_children()

        for item in all_items:
            values = self.vehicles_tree.item(item)['values']
            if any(search_term in str(value).lower() for value in values):
                self.vehicles_tree.item(item, tags=())
            else:
                self.vehicles_tree.item(item, tags=('hidden',))

        self.vehicles_tree.tag_configure('hidden', foreground='gray')

    def register_vehicle_dialog(self):
        """Show register vehicle dialog"""
        dialog = VehicleDialog(self.root, "Register New Vehicle")
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            try:
                self.register_vehicle_from_data(dialog.result)
                self.refresh_vehicles()
                self.update_status("Vehicle registered successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register vehicle: {e}")

    def edit_selected_vehicle(self):
        """Edit the selected vehicle"""
        selected = self.vehicles_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a vehicle to edit")
            return

        vehicle_id = self.vehicles_tree.item(selected[0])['values'][0]

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
            vehicle_data = cursor.fetchone()
            conn.close()

            if vehicle_data:
                dialog = VehicleDialog(self.root, "Edit Vehicle", vehicle_data)
                self.root.wait_window(dialog.dialog)

                if dialog.result:
                    self.update_vehicle_from_data(vehicle_id, dialog.result)
                    self.refresh_vehicles()
                    self.update_status("Vehicle updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit vehicle: {e}")

    def delete_selected_vehicle(self):
        """Delete the selected vehicle"""
        selected = self.vehicles_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a vehicle to delete")
            return

        vehicle_id = self.vehicles_tree.item(selected[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete vehicle {vehicle_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
                conn.commit()
                conn.close()

                self.refresh_vehicles()
                self.update_status("Vehicle deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete vehicle: {e}")

    def register_vehicle_from_data(self, data):
        """Register a vehicle from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Generate vehicle ID
            cursor.execute('SELECT COUNT(*) FROM vehicles')
            count = cursor.fetchone()[0] + 1
            vehicle_id = f"V{str(count).zfill(6)}"

            # Validate owner_id if provided
            owner_id = data.get('owner_id')
            if owner_id:
                try:
                    owner_id = int(owner_id)
                    # Verify user exists
                    cursor.execute('SELECT id FROM users WHERE id = ?', (owner_id,))
                    if not cursor.fetchone():
                        logging.warning(f"Owner ID {owner_id} not found in users table, setting to NULL")
                        owner_id = None
                except (ValueError, TypeError):
                    logging.warning(f"Invalid owner_id format: {owner_id}, setting to NULL")
                    owner_id = None

            # Insert vehicle
            cursor.execute('''
            INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                vehicle_id,
                data['license_plate'],
                data['make'],
                data['model'],
                data['year'],
                data['color'],
                data['vehicle_type'],
                owner_id,
                data['registration_state']
            ))

            conn.commit()
            logging.info(f"Vehicle {vehicle_id} registered successfully with owner_id={owner_id}")
        except Exception as e:
            conn.rollback()
            logging.error(f"Failed to register vehicle: {e}")
            raise
        finally:
            conn.close()

    def update_vehicle_from_data(self, vehicle_id, data):
        """Update a vehicle from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE vehicles
        SET license_plate=?, make=?, model=?, year=?, color=?,
            vehicle_type=?, registration_state=?
        WHERE vehicle_id=?
        ''', (
            data['license_plate'],
            data['make'],
            data['model'],
            data['year'],
            data['color'],
            data['vehicle_type'],
            data['registration_state'],
            vehicle_id
        ))

        conn.commit()
        conn.close()
