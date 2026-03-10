"""Parking lots tab mixin for ParkingManagementGUI."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .. import get_connection, _t
from ..dialogs.lot_dialog import LotDialog


class LotsMixin:
    """Mixin providing parking lots tab functionality."""

    def setup_lots_tab(self):
        """Setup the parking lots management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.lots_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text=_t("parking.btn.add_lot"), command=self.add_lot_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.edit_selected"), command=self.edit_selected_lot).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.delete_selected"), command=self.delete_selected_lot).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_lots).pack(side=tk.LEFT, padx=2)

        # Create treeview for lots
        columns = ("ID", "Name", "Location", "Total Spaces", "Available", "Zone", "Hours")
        self.lots_tree = ttk.Treeview(self.lots_frame, columns=columns, show="headings")

        # Configure columns
        for col in columns:
            self.lots_tree.heading(col, text=col)
            self.lots_tree.column(col, width=100)

        # Add scrollbars
        lots_scrolly = ttk.Scrollbar(self.lots_frame, orient=tk.VERTICAL, command=self.lots_tree.yview)
        lots_scrollx = ttk.Scrollbar(self.lots_frame, orient=tk.HORIZONTAL, command=self.lots_tree.xview)
        self.lots_tree.configure(yscrollcommand=lots_scrolly.set, xscrollcommand=lots_scrollx.set)

        # Pack treeview and scrollbars
        self.lots_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        lots_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        lots_scrollx.pack(side=tk.BOTTOM, fill=tk.X)

        # Load lots data
        self.refresh_lots()

    def refresh_lots(self):
        """Refresh parking lots data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM parking_lots ORDER BY lot_id')
            lots = cursor.fetchall()

            # Clear existing data
            for item in self.lots_tree.get_children():
                self.lots_tree.delete(item)

            # Insert new data - convert sqlite3.Row to tuple for display
            for lot in lots:
                # Convert sqlite3.Row object to tuple to avoid display issues
                lot_values = tuple(lot) if hasattr(lot, '__iter__') else lot
                self.lots_tree.insert("", tk.END, values=lot_values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh lots: {e}")

    def add_lot_dialog(self):
        """Show add lot dialog"""
        dialog = LotDialog(self.root, "Add New Parking Lot")
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            try:
                self.add_lot_from_data(dialog.result)
                self.refresh_lots()
                self.update_status("Parking lot added successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add parking lot: {e}")

    def edit_selected_lot(self):
        """Edit the selected parking lot"""
        selected = self.lots_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a lot to edit")
            return

        lot_id = self.lots_tree.item(selected[0])['values'][0]

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_lots WHERE lot_id = ?', (lot_id,))
            lot_data = cursor.fetchone()
            conn.close()

            if lot_data:
                dialog = LotDialog(self.root, "Edit Parking Lot", lot_data)
                self.root.wait_window(dialog.dialog)

                if dialog.result:
                    self.update_lot_from_data(lot_id, dialog.result)
                    self.refresh_lots()
                    self.update_status("Parking lot updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit lot: {e}")

    def delete_selected_lot(self):
        """Delete the selected parking lot"""
        selected = self.lots_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a lot to delete")
            return

        lot_id = self.lots_tree.item(selected[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete lot {lot_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_lots WHERE lot_id = ?', (lot_id,))
                conn.commit()
                conn.close()

                self.refresh_lots()
                self.update_status("Parking lot deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete lot: {e}")

    def add_lot_from_data(self, data):
        """Add a parking lot from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        # Generate lot ID
        cursor.execute('SELECT COUNT(*) FROM parking_lots')
        count = cursor.fetchone()[0] + 1
        lot_id = f"L{str(count).zfill(3)}"

        # Insert lot
        cursor.execute('''
        INSERT INTO parking_lots VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            lot_id,
            data['lot_name'],
            data['location'],
            data['total_spaces'],
            data['total_spaces'],  # Initially all spaces are available
            data['zone'],
            data['hours']
        ))

        conn.commit()
        conn.close()

    def update_lot_from_data(self, lot_id, data):
        """Update a parking lot from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE parking_lots
        SET lot_name=?, location=?, total_spaces=?, zone=?, hours_of_operation=?
        WHERE lot_id=?
        ''', (
            data['lot_name'],
            data['location'],
            data['total_spaces'],
            data['zone'],
            data['hours'],
            lot_id
        ))

        conn.commit()
        conn.close()

    def update_available_spaces_dialog(self):
        """Show dialog to update available spaces for parking lots"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get all lots
            cursor.execute('SELECT lot_id, lot_name, total_spaces, available_spaces FROM parking_lots ORDER BY lot_id')
            lots = cursor.fetchall()

            if not lots:
                messagebox.showinfo("Info", "No parking lots found.")
                conn.close()
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Update Available Spaces")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            # Create frame with scrollbar
            main_frame = ttk.Frame(dialog)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Create canvas and scrollbar for lots list
            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Add lot entries
            lot_vars = {}

            ttk.Label(scrollable_frame, text="Update Available Spaces", font=("Arial", 12, "bold")).pack(pady=(0, 10))

            for lot in lots:
                lot_frame = ttk.Frame(scrollable_frame)
                lot_frame.pack(fill=tk.X, pady=2)

                ttk.Label(lot_frame, text=f"{lot[0]} - {lot[1]}:").pack(side=tk.LEFT)
                ttk.Label(lot_frame, text=f"(Total: {lot[2]})").pack(side=tk.LEFT, padx=(5, 10))

                var = tk.StringVar(value=str(lot[3]))
                lot_vars[lot[0]] = var

                entry = ttk.Entry(lot_frame, textvariable=var, width=10)
                entry.pack(side=tk.RIGHT)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_changes():
                try:
                    for lot_id_key, var in lot_vars.items():
                        available = int(var.get())
                        if available < 0:
                            messagebox.showerror("Error", f"Available spaces for {lot_id_key} cannot be negative.")
                            return

                        # Get total spaces for validation
                        cursor.execute('SELECT total_spaces FROM parking_lots WHERE lot_id = ?', (lot_id_key,))
                        total = cursor.fetchone()[0]

                        if available > total:
                            messagebox.showerror("Error", f"Available spaces for {lot_id_key} cannot exceed total spaces ({total}).")
                            return

                        # Update available spaces
                        cursor.execute('UPDATE parking_lots SET available_spaces = ? WHERE lot_id = ?', (available, lot_id_key))

                    conn.commit()
                    self.refresh_lots()
                    self.update_status("Available spaces updated successfully")
                    dialog.destroy()

                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numbers for available spaces.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update available spaces: {e}")

            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open update dialog: {e}")
