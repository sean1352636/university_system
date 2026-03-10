"""
Inventory management functions - managing housing inventory and equipment.
Handles inventory tracking, equipment assignments, and maintenance.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_id

def show_inventory(self):
        """Show room inventory management"""
        self.clear_content()

        ttk.Label(self.content_frame, text="Room Inventory Management",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 15), anchor='w')

        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="Building:").pack(side=tk.LEFT)
        building_var = tk.StringVar(value="All")
        status_var = tk.StringVar(value="All")
        accessible_var = tk.BooleanVar(value=False)

        building_map = {}
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            for building_id, building_name in cursor.fetchall():
                building_map[building_name] = building_id
            conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", f"Could not load buildings: {str(e)}")

        building_choices = ['All'] + sorted(building_map.keys())
        building_combo = ttk.Combobox(filter_frame, textvariable=building_var, values=building_choices,
                                      state='readonly', width=25)
        building_combo.pack(side=tk.LEFT, padx=(5, 15))
        if building_choices:
            building_combo.current(0)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT)
        status_combo = ttk.Combobox(filter_frame, textvariable=status_var,
                                    values=['All', 'Available', 'Occupied', 'Maintenance'],
                                    state='readonly', width=15)
        status_combo.pack(side=tk.LEFT, padx=(5, 15))
        status_combo.current(0)

        ttk.Checkbutton(filter_frame, text="Accessible rooms only", variable=accessible_var).pack(side=tk.LEFT)

        ttk.Button(filter_frame, text="Refresh", command=lambda: load_inventory()).pack(side=tk.RIGHT)

        summary_var = tk.StringVar(value="No data loaded")
        ttk.Label(self.content_frame, textvariable=summary_var, font=('Arial', 10, 'italic')).pack(anchor='w')

        columns = ('Room ID', 'Building', 'Room', 'Floor', 'Type', 'Capacity', 'Occupants', 'Accessible', 'Status', 'Monthly Rent')
        tree_frame = ttk.Frame(self.content_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 10))

        inventory_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=18)
        for col in columns:
            width = 110 if col not in ('Room ID', 'Building', 'Room', 'Type') else 130
            inventory_tree.heading(col, text=col)
            inventory_tree.column(col, width=width, anchor='center')

        inventory_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=inventory_tree.yview)
        inventory_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        action_frame = ttk.Frame(self.content_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))

        def change_status(new_status):
            selected = inventory_tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select a room to update.")
                return

            items = inventory_tree.item(selected[0])
            room_id = items['values'][0]

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE housing_rooms
                    SET status = ?, updated_at = ?
                    WHERE room_id = ?
                ''', (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), room_id))
                conn.commit()
                conn.close()
                load_inventory()
                messagebox.showinfo("Status Updated", f"Room {room_id} status changed to {new_status}.")
            except Exception as e:
                messagebox.showerror("Update Failed", f"Could not update room status: {str(e)}")

        ttk.Button(action_frame, text="Mark Available", command=lambda: change_status('Available')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(action_frame, text="Mark Occupied", command=lambda: change_status('Occupied')).pack(side=tk.LEFT, padx=10)
        ttk.Button(action_frame, text="Mark Maintenance", command=lambda: change_status('Maintenance')).pack(side=tk.LEFT, padx=10)

        def show_room_details(event=None):
            selected = inventory_tree.selection()
            if not selected:
                return
            values = inventory_tree.item(selected[0])['values']
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Room Details - {values[0]}")
            detail_window.geometry("400x320")
            detail_window.transient(self.root)

            detail_frame = ttk.Frame(detail_window, padding="15")
            detail_frame.pack(fill=tk.BOTH, expand=True)

            labels = [
                ("Room ID", values[0]),
                ("Building", values[1]),
                ("Room", values[2]),
                ("Floor", values[3]),
                ("Type", values[4]),
                ("Capacity", values[5]),
                ("Current Occupants", values[6]),
                ("Accessible", values[7]),
                ("Status", values[8]),
                ("Monthly Rent", values[9])
            ]

            for idx, (label, val) in enumerate(labels):
                ttk.Label(detail_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(row=idx, column=0, sticky='w', pady=3)
                ttk.Label(detail_frame, text=str(val)).grid(row=idx, column=1, sticky='w', pady=3)

            ttk.Button(detail_frame, text="Close", command=detail_window.destroy).grid(row=len(labels), column=0, columnspan=2, pady=(15, 0))

        inventory_tree.bind('<Double-1>', show_room_details)

        def load_inventory():
            for item in inventory_tree.get_children():
                inventory_tree.delete(item)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                query = '''
                    SELECT r.room_id, b.building_name, r.room_number, r.floor_number, r.room_type,
                           r.max_occupants, r.current_occupants, r.is_accessible, r.status, r.monthly_rent
                    FROM housing_rooms r
                    JOIN housing_buildings b ON r.building_id = b.building_id
                '''
                conditions = []
                params = []

                building_selected = building_var.get()
                if building_selected and building_selected != 'All':
                    building_id = building_map.get(building_selected)
                    if building_id is not None:
                        conditions.append('r.building_id = ?')
                        params.append(building_id)
                    else:
                        summary_var.set("Selected building no longer exists in the database.")
                        return

                status_selected = status_var.get()
                if status_selected and status_selected != 'All':
                    conditions.append('r.status = ?')
                    params.append(status_selected)

                if accessible_var.get():
                    conditions.append('r.is_accessible = 1')

                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)

                query += ' ORDER BY b.building_name, r.room_number'

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                total_rooms = len(rows)
                available = sum(1 for row in rows if row[8] == 'Available')
                occupied = sum(1 for row in rows if row[8] == 'Occupied')
                maintenance = sum(1 for row in rows if row[8] == 'Maintenance')

                summary_var.set(
                    f"Rooms: {total_rooms} | Available: {available} | Occupied: {occupied} | Maintenance: {maintenance}"
                )

                for row in rows:
                    accessible_display = 'Yes' if row[7] else 'No'
                    rent_display = f"£{row[9]:.2f}" if row[9] is not None else 'N/A'
                    inventory_tree.insert('', 'end', values=(
                        row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                        accessible_display, row[8], rent_display
                    ))

                if not rows:
                    messagebox.showinfo("Room Inventory", "No rooms match the selected filters.")

            except Exception as e:
                summary_var.set("Unable to load room data")
                messagebox.showerror("Database Error", f"Could not load room inventory: {str(e)}")

        load_inventory()
