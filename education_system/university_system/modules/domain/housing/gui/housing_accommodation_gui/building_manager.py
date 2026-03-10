"""
Building management functions - CRUD operations for housing buildings.
Handles building creation, editing, deletion, and room management.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_id


def show_building_management(gui_instance):
    """Show building management interface"""
    gui_instance.clear_content()

    # Title
    ttk.Label(gui_instance.content_frame, text="Building Management",
             font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=(0, 20), sticky='w')

    # Create notebook for different building operations
    notebook = ttk.Notebook(gui_instance.content_frame)
    notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # View Buildings tab
    view_frame = ttk.Frame(notebook, padding="10")
    notebook.add(view_frame, text="View Buildings")
    create_buildings_list(gui_instance, view_frame)

    # Add Building tab
    add_frame = ttk.Frame(notebook, padding="10")
    notebook.add(add_frame, text="Add Building")
    create_add_building_form(gui_instance, add_frame)


def create_buildings_list(gui_instance, parent):
    """Create a list of buildings with management options"""
    # Treeview for buildings list
    tree_frame = ttk.Frame(parent)
    tree_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame)
    v_scrollbar.pack(side='right', fill='y')

    h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal')
    h_scrollbar.pack(side='bottom', fill='x')

    # Treeview
    columns = ('ID', 'Name', 'Location', 'Total Rooms', 'Available', 'Occupancy %')
    gui_instance.buildings_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                      yscrollcommand=v_scrollbar.set,
                                      xscrollcommand=h_scrollbar.set)

    # Configure scrollbars
    v_scrollbar.config(command=gui_instance.buildings_tree.yview)
    h_scrollbar.config(command=gui_instance.buildings_tree.xview)

    # Configure columns
    for col in columns:
        gui_instance.buildings_tree.heading(col, text=col)
        gui_instance.buildings_tree.column(col, width=100)

    gui_instance.buildings_tree.pack(side='left', fill='both', expand=True)

    # Buttons frame
    buttons_frame = ttk.Frame(parent)
    buttons_frame.grid(row=1, column=0, columnspan=2, pady=20)

    ttk.Button(buttons_frame, text="Refresh",
              command=lambda: refresh_buildings_list(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Edit Selected",
              command=lambda: edit_selected_building(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Delete Selected",
              command=lambda: delete_selected_building(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Manage Rooms",
              command=lambda: manage_selected_building_rooms(gui_instance)).pack(side='left', padx=5)

    # Load buildings
    refresh_buildings_list(gui_instance)


def manage_selected_building_rooms(gui_instance):
    """Manage rooms for selected building"""
    selected = gui_instance.buildings_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a building to manage rooms")
        return

    building_data = gui_instance.buildings_tree.item(selected[0])['values']
    building_id = building_data[0]
    building_name = building_data[1]

    show_building_rooms_management(gui_instance, building_id, building_name)


def refresh_buildings_list(gui_instance):
    """Refresh the buildings list"""
    # Clear existing items
    for item in gui_instance.buildings_tree.get_children():
        gui_instance.buildings_tree.delete(item)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT building_id, building_name, campus_location, total_rooms, available_rooms,
               ROUND((CAST(total_rooms - available_rooms AS FLOAT) / total_rooms) * 100, 1) as occupancy_rate
        FROM housing_buildings
        ORDER BY building_name
        ''')

        buildings = cursor.fetchall()

        for building in buildings:
            occupancy = f"{building[5]}%" if building[5] is not None else "0%"
            gui_instance.buildings_tree.insert('', 'end', values=(
                building[0], building[1], building[2],
                building[3], building[4], occupancy
            ))

        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load buildings: {str(e)}")


def create_add_building_form(gui_instance, parent):
    """Create form to add new building"""
    # Form fields
    fields = [
        ("Building Name:", "building_name"),
        ("Address:", "address"),
        ("Campus Location:", "campus_location"),
        ("Total Rooms:", "total_rooms"),
        ("Available Rooms:", "available_rooms")
    ]

    gui_instance.building_entries = {}

    for i, (label, field) in enumerate(fields):
        ttk.Label(parent, text=label).grid(row=i, column=0, sticky='w', pady=5)
        entry = ttk.Entry(parent, width=40)
        entry.grid(row=i, column=1, sticky='w', pady=5, padx=10)
        gui_instance.building_entries[field] = entry

    # Checkboxes for amenities
    amenities_frame = ttk.LabelFrame(parent, text="Building Amenities", padding="10")
    amenities_frame.grid(row=len(fields), column=0, columnspan=2, pady=20, sticky='w')

    gui_instance.building_amenities = {}
    amenities = [
        ("has_elevator", "Has Elevator"),
        ("has_accessible_rooms", "Has Accessible Rooms"),
        ("has_kitchen", "Has Kitchen Facilities"),
        ("has_laundry", "Has Laundry Facilities")
    ]

    for i, (field, label) in enumerate(amenities):
        var = tk.BooleanVar()
        gui_instance.building_amenities[field] = var
        ttk.Checkbutton(amenities_frame, text=label, variable=var).grid(
            row=i//2, column=i%2, sticky='w', padx=10, pady=5
        )

    # Submit button
    ttk.Button(parent, text="Add Building",
              command=lambda: add_building(gui_instance)).grid(row=len(fields)+2, column=0, pady=20)


def add_building(gui_instance):
    """Add a new building"""
    try:
        # Validate inputs
        building_name = gui_instance.building_entries['building_name'].get().strip()
        address = gui_instance.building_entries['address'].get().strip()
        campus_location = gui_instance.building_entries['campus_location'].get().strip()

        if not all([building_name, address, campus_location]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            total_rooms = int(gui_instance.building_entries['total_rooms'].get())
            available_rooms = int(gui_instance.building_entries['available_rooms'].get())

            if total_rooms <= 0 or available_rooms < 0 or available_rooms > total_rooms:
                raise ValueError("Invalid room numbers")

        except ValueError:
            messagebox.showerror("Error", "Please enter valid room numbers")
            return

        # Create building record
        conn = get_connection()
        cursor = conn.cursor()

        building_id = generate_id('BLD')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO housing_buildings (
            building_id, building_name, address, campus_location, total_rooms, available_rooms,
            has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            building_id, building_name, address, campus_location, total_rooms, available_rooms,
            1 if gui_instance.building_amenities['has_elevator'].get() else 0,
            1 if gui_instance.building_amenities['has_accessible_rooms'].get() else 0,
            1 if gui_instance.building_amenities['has_kitchen'].get() else 0,
            1 if gui_instance.building_amenities['has_laundry'].get() else 0,
            timestamp, timestamp
        ))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"Building '{building_name}' created successfully!")

        # Clear form
        for entry in gui_instance.building_entries.values():
            entry.delete(0, tk.END)
        for var in gui_instance.building_amenities.values():
            var.set(False)

        # Refresh buildings list if it exists
        if hasattr(gui_instance, 'buildings_tree'):
            refresh_buildings_list(gui_instance)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to create building: {str(e)}")


def edit_selected_building(gui_instance):
    """Edit the selected building"""
    selected = gui_instance.buildings_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a building to edit")
        return

    building_id = gui_instance.buildings_tree.item(selected[0])['values'][0]
    show_edit_building_dialog(gui_instance, building_id)


def show_edit_building_dialog(gui_instance, building_id):
    """Show dialog to edit building"""
    # Create new window
    edit_window = tk.Toplevel(gui_instance.root)
    edit_window.title("Edit Building")
    edit_window.geometry("500x400")
    edit_window.transient(gui_instance.root)
    edit_window.grab_set()

    try:
        # Load building data
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT building_name, address, campus_location, total_rooms, available_rooms,
               has_elevator, has_accessible_rooms, has_kitchen, has_laundry
        FROM housing_buildings WHERE building_id = ?
        ''', (building_id,))
        building_data = cursor.fetchone()
        conn.close()

        if not building_data:
            messagebox.showerror("Error", "Building not found")
            edit_window.destroy()
            return

        # Create form
        fields = [
            ("Building Name:", "building_name", building_data[0]),
            ("Address:", "address", building_data[1]),
            ("Campus Location:", "campus_location", building_data[2]),
            ("Total Rooms:", "total_rooms", str(building_data[3])),
            ("Available Rooms:", "available_rooms", str(building_data[4]))
        ]

        entries = {}

        for i, (label, field, value) in enumerate(fields):
            ttk.Label(edit_window, text=label).grid(row=i, column=0, sticky='w', pady=5, padx=10)
            entry = ttk.Entry(edit_window, width=40)
            entry.grid(row=i, column=1, sticky='w', pady=5, padx=10)
            entry.insert(0, value)
            entries[field] = entry

        # Amenities
        amenities_frame = ttk.LabelFrame(edit_window, text="Building Amenities", padding="10")
        amenities_frame.grid(row=len(fields), column=0, columnspan=2, pady=20, sticky='w', padx=10)

        amenities = {}
        amenity_data = [
            ("has_elevator", "Has Elevator", building_data[5]),
            ("has_accessible_rooms", "Has Accessible Rooms", building_data[6]),
            ("has_kitchen", "Has Kitchen Facilities", building_data[7]),
            ("has_laundry", "Has Laundry Facilities", building_data[8])
        ]

        for i, (field, label, value) in enumerate(amenity_data):
            var = tk.BooleanVar()
            var.set(bool(value))
            amenities[field] = var
            ttk.Checkbutton(amenities_frame, text=label, variable=var).grid(
                row=i//2, column=i%2, sticky='w', padx=10, pady=5
            )

        def save_changes():
            try:
                # Validate and save
                building_name = entries['building_name'].get().strip()
                address = entries['address'].get().strip()
                campus_location = entries['campus_location'].get().strip()

                if not all([building_name, address, campus_location]):
                    messagebox.showerror("Error", "Please fill in all required fields")
                    return

                total_rooms = int(entries['total_rooms'].get())
                available_rooms = int(entries['available_rooms'].get())

                if total_rooms <= 0 or available_rooms < 0 or available_rooms > total_rooms:
                    raise ValueError("Invalid room numbers")

                # Update database
                conn = get_connection()
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                UPDATE housing_buildings
                SET building_name = ?, address = ?, campus_location = ?, total_rooms = ?, available_rooms = ?,
                    has_elevator = ?, has_accessible_rooms = ?, has_kitchen = ?, has_laundry = ?, updated_at = ?
                WHERE building_id = ?
                ''', (
                    building_name, address, campus_location, total_rooms, available_rooms,
                    1 if amenities['has_elevator'].get() else 0,
                    1 if amenities['has_accessible_rooms'].get() else 0,
                    1 if amenities['has_kitchen'].get() else 0,
                    1 if amenities['has_laundry'].get() else 0,
                    timestamp, building_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Building updated successfully!")
                refresh_buildings_list(gui_instance)
                edit_window.destroy()

            except ValueError as e:
                messagebox.showerror("Error", "Please enter valid values")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update building: {str(e)}")

        # Add buttons frame
        buttons_frame = ttk.Frame(edit_window)
        buttons_frame.grid(row=len(fields)+1, column=0, columnspan=2, pady=20)

        ttk.Button(buttons_frame, text="Save Changes", command=save_changes).pack(side='left', padx=10)
        ttk.Button(buttons_frame, text="Cancel", command=edit_window.destroy).pack(side='left', padx=10)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load building data: {str(e)}")
        edit_window.destroy()


def delete_selected_building(gui_instance):
    """Delete the selected building"""
    selected = gui_instance.buildings_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a building to delete")
        return

    building_data = gui_instance.buildings_tree.item(selected[0])['values']
    building_id = building_data[0]
    building_name = building_data[1]

    # Confirm deletion
    result = messagebox.askyesno("Confirm Delete",
                               f"Are you sure you want to delete building '{building_name}'?\n"
                               "This will also delete all associated rooms.")

    if result:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check for occupied rooms
            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE building_id = ? AND status != "Available"',
                         (building_id,))
            occupied_count = cursor.fetchone()[0]

            if occupied_count > 0:
                messagebox.showerror("Error",
                                   f"Cannot delete building. It has {occupied_count} occupied or reserved rooms.")
                conn.close()
                return

            # Delete rooms and building
            cursor.execute('DELETE FROM housing_rooms WHERE building_id = ?', (building_id,))
            cursor.execute('DELETE FROM housing_buildings WHERE building_id = ?', (building_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Building '{building_name}' deleted successfully!")
            refresh_buildings_list(gui_instance)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete building: {str(e)}")


def show_building_rooms_management(gui_instance, building_id, building_name):
    """Show room management interface for a specific building"""
    # This function will be implemented in room_manager.py
    # For now, import and call from there
    from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.room_manager import show_room_management
    show_room_management(gui_instance, building_id, building_name)
