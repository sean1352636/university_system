"""
Room management functions - managing rooms within buildings.
Handles room creation, editing, deletion, batch creation, and filtering.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from university_system.infrastructure.database.db import get_connection, sqlite3
from university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from university_system.modules.shared.utils.i18n import get_text as _t
from university_system.modules.domain.housing.services.housing_accommodation import generate_id


def show_room_management(gui_instance, building_id=None, building_name=None):
    """
    Show room management interface.
    If building_id is provided, show rooms for that building, otherwise show general room management.
    """
    if building_id and building_name:
        show_building_rooms_management(gui_instance, building_id, building_name)
    else:
        show_general_room_management(gui_instance)


def show_general_room_management(gui_instance):
    """Show room management interface"""
    gui_instance.clear_content()

    ttk.Label(gui_instance.content_frame, text="Room Management",
             font=('Arial', 16, 'bold')).pack(pady=(0, 20))

    # Create notebook
    notebook = ttk.Notebook(gui_instance.content_frame)
    notebook.pack(fill='both', expand=True)

    # Add rooms tab
    add_rooms_frame = ttk.Frame(notebook, padding="10")
    notebook.add(add_rooms_frame, text="Add Rooms to Building")
    create_rooms_interface(gui_instance, add_rooms_frame)

    # View rooms tab
    view_rooms_frame = ttk.Frame(notebook, padding="10")
    notebook.add(view_rooms_frame, text="View All Rooms")
    create_rooms_list_view(gui_instance, view_rooms_frame)


def show_building_rooms_management(gui_instance, building_id, building_name):
    """Show room management for a specific building"""
    rooms_window = tk.Toplevel(gui_instance.root)
    rooms_window.title(f"Manage Rooms - {building_name}")
    rooms_window.geometry("800x600")
    rooms_window.transient(gui_instance.root)
    rooms_window.grab_set()

    # Rooms list
    list_frame = ttk.Frame(rooms_window)
    list_frame.pack(fill='both', expand=True, padx=10, pady=10)

    columns = ('Room #', 'Floor', 'Type', 'Max Occ.', 'Current Occ.', 'Status', 'Rent', 'Accessible')
    rooms_tree = ttk.Treeview(list_frame, columns=columns, show='headings')

    for col in columns:
        rooms_tree.heading(col, text=col)
        if col in ['Max Occ.', 'Current Occ.', 'Floor']:
            rooms_tree.column(col, width=80)
        elif col == 'Rent':
            rooms_tree.column(col, width=80, anchor='e')
        else:
            rooms_tree.column(col, width=100)

    # Scrollbar
    scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=rooms_tree.yview)
    rooms_tree.configure(yscrollcommand=scrollbar.set)

    rooms_tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    # Load rooms for this building
    def load_rooms():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT room_id, room_number, floor_number, room_type, max_occupants,
                   current_occupants, status, monthly_rent, is_accessible
            FROM housing_rooms
            WHERE building_id = ?
            ORDER BY floor_number, room_number
            ''', (building_id,))

            rooms = cursor.fetchall()

            for room in rooms:
                accessible = "Yes" if room[8] else "No"
                rooms_tree.insert('', 'end', values=(
                    room[1], room[2], room[3], room[4], room[5],
                    room[6], f"£{room[7]:.2f}", accessible
                ), tags=(room[0],))  # Store room_id in tags

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load rooms: {str(e)}")

    load_rooms()

    # Buttons
    buttons_frame = ttk.Frame(rooms_window)
    buttons_frame.pack(fill='x', padx=10, pady=10)

    def edit_selected_room():
        selected = rooms_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a room to edit")
            return

        room_id = rooms_tree.item(selected[0])['tags'][0]
        room_data = rooms_tree.item(selected[0])['values']

        # Create edit dialog
        edit_window = tk.Toplevel(rooms_window)
        edit_window.title("Edit Room")
        edit_window.geometry("500x600")
        edit_window.transient(rooms_window)
        edit_window.grab_set()

        ttk.Label(edit_window, text="Edit Room Details", font=("Arial", 14, "bold")).pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(edit_window, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Get current room data from database
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT room_number, floor_number, room_type, max_occupants,
                   current_occupants, status, monthly_rent, is_accessible
            FROM housing_rooms WHERE room_id = ?
            ''', (room_id,))
            current_room = cursor.fetchone()
            conn.close()

            if not current_room:
                messagebox.showerror("Error", "Room not found")
                edit_window.destroy()
                return

            # Room Number
            ttk.Label(form_frame, text="Room Number:").grid(row=0, column=0, sticky="w", pady=5)
            room_number_var = tk.StringVar(value=current_room[0])
            ttk.Entry(form_frame, textvariable=room_number_var, width=30).grid(row=0, column=1, pady=5)

            # Floor Number
            ttk.Label(form_frame, text="Floor Number:").grid(row=1, column=0, sticky="w", pady=5)
            floor_var = tk.IntVar(value=current_room[1])
            ttk.Spinbox(form_frame, from_=0, to=50, textvariable=floor_var, width=28).grid(row=1, column=1, pady=5)

            # Room Type
            ttk.Label(form_frame, text="Room Type:").grid(row=2, column=0, sticky="w", pady=5)
            room_type_var = tk.StringVar(value=current_room[2])
            room_type_combo = ttk.Combobox(form_frame, textvariable=room_type_var, width=28,
                                          values=["single", "double", "triple", "suite", "studio"])
            room_type_combo.grid(row=2, column=1, pady=5)

            # Max Occupants
            ttk.Label(form_frame, text="Max Occupants:").grid(row=3, column=0, sticky="w", pady=5)
            max_occ_var = tk.IntVar(value=current_room[3])
            ttk.Spinbox(form_frame, from_=1, to=10, textvariable=max_occ_var, width=28).grid(row=3, column=1, pady=5)

            # Current Occupants (read-only)
            ttk.Label(form_frame, text="Current Occupants:").grid(row=4, column=0, sticky="w", pady=5)
            current_occ_label = ttk.Label(form_frame, text=str(current_room[4]))
            current_occ_label.grid(row=4, column=1, sticky="w", pady=5)

            # Status
            ttk.Label(form_frame, text="Status:").grid(row=5, column=0, sticky="w", pady=5)
            status_var = tk.StringVar(value=current_room[5])
            status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=28,
                                       values=["available", "occupied", "maintenance", "reserved"])
            status_combo.grid(row=5, column=1, pady=5)

            # Monthly Rent
            ttk.Label(form_frame, text="Monthly Rent (£):").grid(row=6, column=0, sticky="w", pady=5)
            rent_var = tk.DoubleVar(value=current_room[6])
            ttk.Entry(form_frame, textvariable=rent_var, width=30).grid(row=6, column=1, pady=5)

            # Accessible
            accessible_var = tk.BooleanVar(value=bool(current_room[7]))
            ttk.Checkbutton(form_frame, text="Wheelchair Accessible",
                          variable=accessible_var).grid(row=7, column=0, columnspan=2, pady=15)

            def save_changes():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    UPDATE housing_rooms
                    SET room_number = ?, floor_number = ?, room_type = ?,
                        max_occupants = ?, status = ?, monthly_rent = ?,
                        is_accessible = ?
                    WHERE room_id = ?
                    ''', (room_number_var.get(), floor_var.get(), room_type_var.get(),
                         max_occ_var.get(), status_var.get(), rent_var.get(),
                         accessible_var.get(), room_id))

                    conn.commit()
                    conn.close()

                    # Refresh the room list
                    rooms_tree.item(selected[0], values=(
                        room_number_var.get(), floor_var.get(), room_type_var.get(),
                        max_occ_var.get(), current_room[4], status_var.get(),
                        f"£{rent_var.get():.2f}", "Yes" if accessible_var.get() else "No"
                    ))

                    messagebox.showinfo("Success", "Room updated successfully")
                    edit_window.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update room: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(edit_window)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load room data: {str(e)}")
            edit_window.destroy()

    def delete_selected_room():
        selected = rooms_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a room to delete")
            return

        room_data = rooms_tree.item(selected[0])['values']
        room_number = room_data[0]
        current_occ = room_data[4]

        if current_occ > 0:
            messagebox.showerror("Error", f"Cannot delete room {room_number} - currently occupied")
            return

        result = messagebox.askyesno("Confirm Delete", f"Delete room {room_number}?")
        if result:
            try:
                room_id = rooms_tree.item(selected[0])['tags'][0]
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('DELETE FROM housing_rooms WHERE room_id = ?', (room_id,))
                cursor.execute('''
                UPDATE housing_buildings
                SET total_rooms = total_rooms - 1, available_rooms = available_rooms - 1
                WHERE building_id = ?
                ''', (building_id,))

                conn.commit()
                conn.close()

                rooms_tree.delete(selected[0])
                messagebox.showinfo("Success", f"Room {room_number} deleted successfully")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete room: {str(e)}")

    def add_new_room():
        """Add a new room to the building"""
        add_window = tk.Toplevel(rooms_window)
        add_window.title("Add New Room")
        add_window.geometry("500x600")
        add_window.transient(rooms_window)
        add_window.grab_set()

        ttk.Label(add_window, text="Add New Room", font=("Arial", 14, "bold")).pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(add_window, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Room Number
        ttk.Label(form_frame, text="Room Number:").grid(row=0, column=0, sticky="w", pady=5)
        room_number_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=room_number_var, width=30).grid(row=0, column=1, pady=5)

        # Floor Number
        ttk.Label(form_frame, text="Floor Number:").grid(row=1, column=0, sticky="w", pady=5)
        floor_var = tk.IntVar(value=1)
        ttk.Spinbox(form_frame, from_=0, to=50, textvariable=floor_var, width=28).grid(row=1, column=1, pady=5)

        # Room Type
        ttk.Label(form_frame, text="Room Type:").grid(row=2, column=0, sticky="w", pady=5)
        room_type_var = tk.StringVar(value="single")
        room_type_combo = ttk.Combobox(form_frame, textvariable=room_type_var, width=28,
                                      values=["single", "double", "triple", "suite", "studio"],
                                      state='readonly')
        room_type_combo.grid(row=2, column=1, pady=5)

        # Max Occupants
        ttk.Label(form_frame, text="Max Occupants:").grid(row=3, column=0, sticky="w", pady=5)
        max_occ_var = tk.IntVar(value=1)
        ttk.Spinbox(form_frame, from_=1, to=10, textvariable=max_occ_var, width=28).grid(row=3, column=1, pady=5)

        # Status
        ttk.Label(form_frame, text="Status:").grid(row=4, column=0, sticky="w", pady=5)
        status_var = tk.StringVar(value="available")
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=28,
                                   values=["available", "occupied", "maintenance", "reserved"],
                                   state='readonly')
        status_combo.grid(row=4, column=1, pady=5)

        # Monthly Rent
        ttk.Label(form_frame, text="Monthly Rent (£):").grid(row=5, column=0, sticky="w", pady=5)
        rent_var = tk.DoubleVar(value=500.00)
        ttk.Entry(form_frame, textvariable=rent_var, width=30).grid(row=5, column=1, pady=5)

        # Accessible
        accessible_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Wheelchair Accessible",
                      variable=accessible_var).grid(row=6, column=0, columnspan=2, pady=15)

        def save_new_room():
            if not room_number_var.get().strip():
                messagebox.showwarning("Room Number Required", "Please enter a room number", parent=add_window)
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Generate room ID
                room_id = generate_id('ROOM')
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert new room
                cursor.execute('''
                INSERT INTO housing_rooms (
                    room_id, building_id, room_number, floor_number, room_type,
                    max_occupants, current_occupants, status, monthly_rent,
                    is_accessible, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                ''', (room_id, building_id, room_number_var.get(), floor_var.get(),
                     room_type_var.get(), max_occ_var.get(), status_var.get(),
                     rent_var.get(), accessible_var.get(), timestamp, timestamp))

                # Update building room counts
                cursor.execute('''
                UPDATE housing_buildings
                SET total_rooms = total_rooms + 1,
                    available_rooms = available_rooms + CASE WHEN ? = 'available' THEN 1 ELSE 0 END,
                    updated_at = ?
                WHERE building_id = ?
                ''', (status_var.get(), timestamp, building_id))

                conn.commit()
                conn.close()

                # Add to tree view
                accessible = "Yes" if accessible_var.get() else "No"
                rooms_tree.insert('', 'end', values=(
                    room_number_var.get(), floor_var.get(), room_type_var.get(),
                    max_occ_var.get(), 0, status_var.get(),
                    f"£{rent_var.get():.2f}", accessible
                ), tags=(room_id,))

                messagebox.showinfo("Success", f"Room {room_number_var.get()} added successfully", parent=add_window)
                add_window.destroy()

            except sqlite3.IntegrityError as e:
                messagebox.showerror("Error", f"Room number already exists in this building: {str(e)}", parent=add_window)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add room: {str(e)}", parent=add_window)

        # Buttons
        button_frame = ttk.Frame(add_window)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Add Room", command=save_new_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=add_window.destroy).pack(side=tk.LEFT, padx=5)

    ttk.Button(buttons_frame, text="Add Room", command=add_new_room).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Edit Room", command=edit_selected_room).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Delete Room", command=delete_selected_room).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Close", command=rooms_window.destroy).pack(side='right', padx=5)


def create_rooms_interface(gui_instance, parent):
    """Create interface for adding rooms to a building"""
    # Building selection
    building_frame = ttk.LabelFrame(parent, text="Select Building", padding="10")
    building_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(building_frame, text="Building:").grid(row=0, column=0, sticky='w')
    gui_instance.rooms_building_combo = ttk.Combobox(building_frame, width=40)
    gui_instance.rooms_building_combo.grid(row=0, column=1, padx=10)

    # Load buildings
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        conn.close()

        building_values = [f"{b[1]}" for b in buildings]
        gui_instance.rooms_building_combo['values'] = building_values

    except Exception as e:
        print(f"Error loading buildings: {str(e)}")

    # Room details frame
    room_frame = ttk.LabelFrame(parent, text="Room Details", padding="10")
    room_frame.pack(fill='both', expand=True)

    # Floor and room count
    ttk.Label(room_frame, text="Floor Number:").grid(row=0, column=0, sticky='w', pady=5)
    gui_instance.floor_entry = ttk.Entry(room_frame, width=10)
    gui_instance.floor_entry.grid(row=0, column=1, padx=10, sticky='w')

    ttk.Label(room_frame, text="Room Number:").grid(row=1, column=0, sticky='w', pady=5)
    gui_instance.room_number_entry = ttk.Entry(room_frame, width=10)
    gui_instance.room_number_entry.grid(row=1, column=1, padx=10, sticky='w')

    ttk.Label(room_frame, text="Room Type:").grid(row=2, column=0, sticky='w', pady=5)
    gui_instance.room_type_combo = ttk.Combobox(room_frame, width=20,
                                       values=["Single", "Double", "Triple", "Suite", "Studio", "Apartment"])
    gui_instance.room_type_combo.grid(row=2, column=1, padx=10, sticky='w')

    ttk.Label(room_frame, text="Max Occupants:").grid(row=3, column=0, sticky='w', pady=5)
    gui_instance.max_occupants_entry = ttk.Entry(room_frame, width=10)
    gui_instance.max_occupants_entry.grid(row=3, column=1, padx=10, sticky='w')

    ttk.Label(room_frame, text="Monthly Rent:").grid(row=4, column=0, sticky='w', pady=5)
    gui_instance.rent_entry = ttk.Entry(room_frame, width=15)
    gui_instance.rent_entry.grid(row=4, column=1, padx=10, sticky='w')

    # Accessible checkbox
    gui_instance.is_accessible_var = tk.BooleanVar()
    ttk.Checkbutton(room_frame, text="Accessible Room", variable=gui_instance.is_accessible_var).grid(
        row=5, column=0, columnspan=2, sticky='w', pady=10)

    # Add room button
    ttk.Button(room_frame, text="Add Room", command=lambda: add_single_room(gui_instance)).grid(
        row=6, column=0, pady=20)
    ttk.Button(room_frame, text="Batch Create Rooms",
              command=lambda: show_batch_room_creation(gui_instance)).grid(row=6, column=1, pady=20, padx=10)


def add_single_room(gui_instance):
    """Add a single room to the selected building"""
    try:
        building_name = gui_instance.rooms_building_combo.get()
        floor = gui_instance.floor_entry.get().strip()
        room_number = gui_instance.room_number_entry.get().strip()
        room_type = gui_instance.room_type_combo.get()
        max_occupants = gui_instance.max_occupants_entry.get().strip()
        rent = gui_instance.rent_entry.get().strip()

        if not all([building_name, floor, room_number, room_type, max_occupants, rent]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            floor_num = int(floor)
            max_occ = int(max_occupants)
            monthly_rent = float(rent)

            if floor_num <= 0 or max_occ <= 0 or monthly_rent <= 0:
                raise ValueError("Values must be positive")

        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values")
            return

        # Get building ID
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT building_id FROM housing_buildings WHERE building_name = ?', (building_name,))
        result = cursor.fetchone()

        if not result:
            messagebox.showerror("Error", "Selected building not found")
            conn.close()
            return

        building_id = result[0]

        # Check if room number already exists in this building
        cursor.execute('SELECT room_id FROM housing_rooms WHERE building_id = ? AND room_number = ?',
                      (building_id, room_number))
        if cursor.fetchone():
            messagebox.showerror("Error", f"Room {room_number} already exists in {building_name}")
            conn.close()
            return

        # Create room
        room_id = f"{building_id}-{room_number}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO housing_rooms (
            room_id, building_id, room_number, floor_number, room_type, max_occupants,
            current_occupants, is_accessible, status, monthly_rent, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            room_id, building_id, room_number, floor_num, room_type, max_occ,
            0, 1 if gui_instance.is_accessible_var.get() else 0, 'Available', monthly_rent,
            timestamp, timestamp
        ))

        # Update building available rooms count
        cursor.execute('''
        UPDATE housing_buildings
        SET available_rooms = available_rooms + 1, total_rooms = total_rooms + 1, updated_at = ?
        WHERE building_id = ?
        ''', (timestamp, building_id))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"Room {room_number} added successfully!")

        # Clear form
        gui_instance.floor_entry.delete(0, tk.END)
        gui_instance.room_number_entry.delete(0, tk.END)
        gui_instance.room_type_combo.set("")
        gui_instance.max_occupants_entry.delete(0, tk.END)
        gui_instance.rent_entry.delete(0, tk.END)
        gui_instance.is_accessible_var.set(False)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to add room: {str(e)}")


def create_rooms_list_view(gui_instance, parent):
    """Create a view of all rooms with filtering"""
    # Filter frame
    filter_frame = ttk.LabelFrame(parent, text="Filter Rooms", padding="10")
    filter_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(filter_frame, text="Building:").grid(row=0, column=0, sticky='w')
    gui_instance.rooms_filter_building = ttk.Combobox(filter_frame, values=['All'])
    gui_instance.rooms_filter_building.set('All')
    gui_instance.rooms_filter_building.grid(row=0, column=1, padx=10)

    ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, sticky='w', padx=(20, 0))
    gui_instance.rooms_filter_status = ttk.Combobox(filter_frame,
                                          values=['All', 'Available', 'Occupied', 'Maintenance', 'Reserved'])
    gui_instance.rooms_filter_status.set('All')
    gui_instance.rooms_filter_status.grid(row=0, column=3, padx=10)

    ttk.Button(filter_frame, text="Apply Filter",
              command=lambda: refresh_rooms_list(gui_instance)).grid(row=0, column=4, padx=10)

    # Load building options
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        conn.close()

        building_values = ['All'] + [b[0] for b in buildings]
        gui_instance.rooms_filter_building['values'] = building_values

    except Exception as e:
        print(f"Error loading buildings: {str(e)}")

    # Rooms list
    list_frame = ttk.Frame(parent)
    list_frame.pack(fill='both', expand=True)

    columns = ('Room ID', 'Building', 'Room #', 'Floor', 'Type', 'Max Occ.', 'Current Occ.', 'Status', 'Rent', 'Accessible')
    gui_instance.all_rooms_tree = ttk.Treeview(list_frame, columns=columns, show='headings')

    for col in columns:
        gui_instance.all_rooms_tree.heading(col, text=col)
        if col in ['Max Occ.', 'Current Occ.', 'Floor']:
            gui_instance.all_rooms_tree.column(col, width=80)
        elif col == 'Rent':
            gui_instance.all_rooms_tree.column(col, width=80, anchor='e')
        else:
            gui_instance.all_rooms_tree.column(col, width=100)

    # Scrollbars
    v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=gui_instance.all_rooms_tree.yview)
    h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=gui_instance.all_rooms_tree.xview)
    gui_instance.all_rooms_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    gui_instance.all_rooms_tree.pack(side='left', fill='both', expand=True)
    v_scroll.pack(side='right', fill='y')

    # Load rooms
    refresh_rooms_list(gui_instance)


def refresh_rooms_list(gui_instance):
    """Refresh the rooms list with filters"""
    for item in gui_instance.all_rooms_tree.get_children():
        gui_instance.all_rooms_tree.delete(item)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Build query based on filters
        where_clauses = []
        params = []

        building_filter = gui_instance.rooms_filter_building.get()
        if building_filter != 'All':
            where_clauses.append("b.building_name = ?")
            params.append(building_filter)

        status_filter = gui_instance.rooms_filter_status.get()
        if status_filter != 'All':
            where_clauses.append("r.status = ?")
            params.append(status_filter)

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        cursor.execute(f'''
        SELECT r.room_id, b.building_name, r.room_number, r.floor_number, r.room_type,
               r.max_occupants, r.current_occupants, r.status, r.monthly_rent, r.is_accessible
        FROM housing_rooms r
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE {where_clause}
        ORDER BY b.building_name, r.floor_number, r.room_number
        ''', params)

        rooms = cursor.fetchall()

        for room in rooms:
            accessible = "Yes" if room[9] else "No"
            gui_instance.all_rooms_tree.insert('', 'end', values=(
                room[0], room[1], room[2], room[3], room[4], room[5],
                room[6], room[7], f"£{room[8]:.2f}", accessible
            ))

        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load rooms: {str(e)}")


def show_batch_room_creation(gui_instance):
    """Show interface for batch room creation"""
    batch_window = tk.Toplevel(gui_instance.root)
    batch_window.title("Batch Room Creation")
    batch_window.geometry("600x500")
    batch_window.transient(gui_instance.root)
    batch_window.grab_set()

    # Building selection
    building_frame = ttk.LabelFrame(batch_window, text="Select Building", padding="10")
    building_frame.pack(fill='x', padx=10, pady=10)

    ttk.Label(building_frame, text="Building:").grid(row=0, column=0, sticky='w')
    batch_building_combo = ttk.Combobox(building_frame, width=40)
    batch_building_combo.grid(row=0, column=1, padx=10)

    # Load buildings
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        conn.close()

        building_values = [f"{b[1]}" for b in buildings]
        batch_building_combo['values'] = building_values

    except Exception as e:
        print(f"Error loading buildings: {str(e)}")

    # Batch creation settings
    settings_frame = ttk.LabelFrame(batch_window, text="Batch Settings", padding="10")
    settings_frame.pack(fill='x', padx=10, pady=10)

    ttk.Label(settings_frame, text="Number of Floors:").grid(row=0, column=0, sticky='w', pady=5)
    floors_entry = ttk.Entry(settings_frame, width=10)
    floors_entry.grid(row=0, column=1, padx=10, sticky='w')

    ttk.Label(settings_frame, text="Rooms per Floor:").grid(row=1, column=0, sticky='w', pady=5)
    rooms_per_floor_entry = ttk.Entry(settings_frame, width=10)
    rooms_per_floor_entry.grid(row=1, column=1, padx=10, sticky='w')

    ttk.Label(settings_frame, text="Room Type:").grid(row=2, column=0, sticky='w', pady=5)
    batch_room_type = ttk.Combobox(settings_frame, width=20,
                                  values=["Single", "Double", "Triple", "Suite", "Studio", "Apartment"])
    batch_room_type.grid(row=2, column=1, padx=10, sticky='w')

    ttk.Label(settings_frame, text="Max Occupants:").grid(row=3, column=0, sticky='w', pady=5)
    batch_max_occ = ttk.Entry(settings_frame, width=10)
    batch_max_occ.grid(row=3, column=1, padx=10, sticky='w')

    ttk.Label(settings_frame, text="Monthly Rent:").grid(row=4, column=0, sticky='w', pady=5)
    batch_rent = ttk.Entry(settings_frame, width=15)
    batch_rent.grid(row=4, column=1, padx=10, sticky='w')

    def create_batch_rooms():
        """Create rooms in batch"""
        try:
            building_name = batch_building_combo.get()
            floors = int(floors_entry.get())
            rooms_per_floor = int(rooms_per_floor_entry.get())
            room_type = batch_room_type.get()
            max_occupants = int(batch_max_occ.get())
            monthly_rent = float(batch_rent.get())

            if not all([building_name, room_type]) or floors <= 0 or rooms_per_floor <= 0:
                messagebox.showerror("Error", "Please fill in all fields with valid values")
                return

            # Get building ID
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT building_id FROM housing_buildings WHERE building_name = ?', (building_name,))
            result = cursor.fetchone()

            if not result:
                messagebox.showerror("Error", "Selected building not found")
                conn.close()
                return

            building_id = result[0]
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            rooms_created = 0

            for floor in range(1, floors + 1):
                for room_num in range(1, rooms_per_floor + 1):
                    room_number = f"{floor}{str(room_num).zfill(2)}"
                    room_id = f"{building_id}-{room_number}"

                    # Check if room already exists
                    cursor.execute('SELECT room_id FROM housing_rooms WHERE room_id = ?', (room_id,))
                    if cursor.fetchone():
                        continue  # Skip existing rooms

                    # Create room
                    cursor.execute('''
                    INSERT INTO housing_rooms (
                        room_id, building_id, room_number, floor_number, room_type, max_occupants,
                        current_occupants, is_accessible, status, monthly_rent, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        room_id, building_id, room_number, floor, room_type, max_occupants,
                        0, 0, 'Available', monthly_rent, timestamp, timestamp
                    ))

                    rooms_created += 1

            # Update building room counts
            cursor.execute('''
            UPDATE housing_buildings
            SET available_rooms = available_rooms + ?, total_rooms = total_rooms + ?, updated_at = ?
            WHERE building_id = ?
            ''', (rooms_created, rooms_created, timestamp, building_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"{rooms_created} rooms created successfully!")
            batch_window.destroy()

        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create rooms: {str(e)}")

    # Buttons
    buttons_frame = ttk.Frame(batch_window)
    buttons_frame.pack(fill='x', padx=10, pady=20)

    ttk.Button(buttons_frame, text="Create Rooms", command=create_batch_rooms).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Cancel", command=batch_window.destroy).pack(side='left', padx=5)
