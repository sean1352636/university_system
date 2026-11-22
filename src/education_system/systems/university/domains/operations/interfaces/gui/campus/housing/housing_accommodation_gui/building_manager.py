"""
Building management functions - CRUD operations for housing buildings.
Handles building creation, editing, deletion, and room management.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation import generate_id
# Relocation rules live with the domain so the CLI and this GUI move
# residents — and word the student's email — identically.
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.assignments import (
    apply_relocations, describe_move, notify_relocated_residents, plan_relocations,
)


def show_building_management(gui_instance):
    """Show building management interface"""
    gui_instance.clear_content()

    # Title
    ttk.Label(gui_instance.content_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.labels.building_management', default="Building Management"),
             font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=(0, 20), sticky='w')

    # Create notebook for different building operations
    notebook = ttk.Notebook(gui_instance.content_frame)
    notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # View Buildings tab
    view_frame = ttk.Frame(notebook, padding="10")
    notebook.add(view_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.tabs.view_buildings', default="View Buildings"))
    create_buildings_list(gui_instance, view_frame)

    # Add Building tab
    add_frame = ttk.Frame(notebook, padding="10")
    notebook.add(add_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.tabs.add_building', default="Add Building"))
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

    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.buttons.refresh', default="Refresh"),
              command=lambda: refresh_buildings_list(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.buttons.edit_selected', default="Edit Selected"),
              command=lambda: edit_selected_building(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.buttons.delete_selected', default="Delete Selected"),
              command=lambda: delete_selected_building(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.buttons.manage_rooms', default="Manage Rooms"),
              command=lambda: manage_selected_building_rooms(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.buttons.import_rooms_csv', default="Import Rooms from CSV..."),
              command=lambda: _open_rooms_import(gui_instance)).pack(side='left', padx=5)

    # Shown only when there is nothing to list, so an empty system says what
    # to do next instead of showing an unexplained blank table.
    gui_instance.buildings_empty_label = ttk.Label(parent, text="", foreground='#555555', wraplength=700)
    gui_instance.buildings_empty_label.grid(row=2, column=0, columnspan=2, sticky='w')

    # Load buildings
    refresh_buildings_list(gui_instance)


def _open_rooms_import(gui_instance):
    from education_system.systems.university.domains.operations.interfaces.gui.campus.housing.housing_accommodation_gui.room_manager import show_rooms_csv_import
    show_rooms_csv_import(gui_instance)


def manage_selected_building_rooms(gui_instance):
    """Manage rooms for selected building"""
    selected = gui_instance.buildings_tree.selection()
    if not selected:
        messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.please_select_a_building_to_manage_rooms', default="Please select a building to manage rooms"))
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

        # Counts come from the rooms that exist and occupancy from the beds
        # held by Active/Pending assignments (current_occupants is kept equal
        # to that by triggers) - not from the hand-maintained counters.
        cursor.execute('''
        SELECT b.building_id, b.building_name, b.campus_location,
               COUNT(r.room_id) AS total_rooms,
               COALESCE(SUM(CASE WHEN r.status = 'Available'
                                  AND COALESCE(r.current_occupants, 0) < r.max_occupants
                                 THEN 1 ELSE 0 END), 0) AS available_rooms,
               CASE WHEN COALESCE(SUM(r.max_occupants), 0) > 0
                    THEN ROUND(CAST(SUM(COALESCE(r.current_occupants, 0)) AS FLOAT)
                               / SUM(r.max_occupants) * 100, 1)
               END AS occupancy_rate
        FROM housing_buildings b
        LEFT JOIN housing_rooms r ON r.building_id = b.building_id
        GROUP BY b.building_id, b.building_name, b.campus_location
        ORDER BY b.building_name
        ''')

        buildings = cursor.fetchall()

        for building in buildings:
            occupancy = f"{building[5]}%" if building[5] is not None else "-"
            gui_instance.buildings_tree.insert('', 'end', values=(
                building[0], building[1], building[2],
                building[3], building[4], occupancy
            ))

        conn.close()

        label = getattr(gui_instance, 'buildings_empty_label', None)
        if label is not None:
            if not buildings:
                label.configure(text=_t(
                    'gui.operations.campus.housing.housing_accommodation_gui.building_manager.labels.no_buildings_yet',
                    default="No residences are set up yet. Use the Add Building tab to create one, "
                            "then Manage Rooms (or Import Rooms from CSV) to add its rooms."))
            else:
                label.configure(text="")

    except Exception as e:
        messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), f"Failed to load buildings: {str(e)}")


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
    amenities_frame = ttk.LabelFrame(parent, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.labels.building_amenities', default="Building Amenities"), padding="10")
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
    ttk.Button(parent, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.buttons.add_building', default="Add Building"),
              command=lambda: add_building(gui_instance)).grid(row=len(fields)+2, column=0, pady=20)


def add_building(gui_instance):
    """Add a new building"""
    try:
        # Validate inputs
        building_name = gui_instance.building_entries['building_name'].get().strip()
        address = gui_instance.building_entries['address'].get().strip()
        campus_location = gui_instance.building_entries['campus_location'].get().strip()

        if not all([building_name, address, campus_location]):
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields"))
            return

        try:
            total_rooms = int(gui_instance.building_entries['total_rooms'].get())
            available_rooms = int(gui_instance.building_entries['available_rooms'].get())

            if total_rooms <= 0 or available_rooms < 0 or available_rooms > total_rooms:
                raise ValueError("Invalid room numbers")

        except ValueError:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.please_enter_valid_room_numbers', default="Please enter valid room numbers"))
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

        messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.success', default="Success"), f"Building '{building_name}' created successfully!")

        # Clear form
        for entry in gui_instance.building_entries.values():
            entry.delete(0, tk.END)
        for var in gui_instance.building_amenities.values():
            var.set(False)

        # Refresh buildings list if it exists
        if hasattr(gui_instance, 'buildings_tree'):
            refresh_buildings_list(gui_instance)

    except Exception as e:
        messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), f"Failed to create building: {str(e)}")


def edit_selected_building(gui_instance):
    """Edit the selected building"""
    selected = gui_instance.buildings_tree.selection()
    if not selected:
        messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.please_select_a_building_to_edit', default="Please select a building to edit"))
        return

    building_id = gui_instance.buildings_tree.item(selected[0])['values'][0]
    show_edit_building_dialog(gui_instance, building_id)


def show_edit_building_dialog(gui_instance, building_id):
    """Show dialog to edit building"""
    # Create new window
    edit_window = tk.Toplevel(gui_instance.root)
    edit_window.title(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.windows.edit_building', default="Edit Building"))
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
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.building_not_found', default="Building not found"))
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
        amenities_frame = ttk.LabelFrame(edit_window, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.labels.building_amenities', default="Building Amenities"), padding="10")
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
                    messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields"))
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

                messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.success', default="Success"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.building_updated_successfully', default="Building updated successfully!"))
                refresh_buildings_list(gui_instance)
                edit_window.destroy()

            except ValueError:
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.please_enter_valid_values', default="Please enter valid values"))
            except Exception as e:
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), f"Failed to update building: {str(e)}")

        # Add buttons frame
        buttons_frame = ttk.Frame(edit_window)
        buttons_frame.grid(row=len(fields)+1, column=0, columnspan=2, pady=20)

        ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.buttons.save_changes', default="Save Changes"), command=save_changes).pack(side='left', padx=10)
        ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.buttons.cancel', default="Cancel"), command=edit_window.destroy).pack(side='left', padx=10)

    except Exception as e:
        messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), f"Failed to load building data: {str(e)}")
        edit_window.destroy()


def delete_selected_building(gui_instance):
    """Delete the selected building"""
    selected = gui_instance.buildings_tree.selection()
    if not selected:
        messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.please_select_a_building_to_delete', default="Please select a building to delete"))
        return

    building_data = gui_instance.buildings_tree.item(selected[0])['values']
    building_id = building_data[0]
    building_name = building_data[1]

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Residents no longer block the delete. Work out where each of them
        # would go in the *other* buildings first, and show that plan in the
        # confirmation so the operator approves the moves, not just the delete.
        cursor.execute('SELECT room_id FROM housing_rooms WHERE building_id = ?', (building_id,))
        room_ids = [row[0] for row in cursor.fetchall()]

        moves, unplaced = plan_relocations(cursor, room_ids,
                                           exclude_building_ids=[building_id])

        if unplaced:
            stuck = "\n".join(f"  • {row['student_name']} ({row['student_id']}) "
                              f"in room {row['old_room_number']}"
                              for row in unplaced)
            messagebox.showerror(
                _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"),
                f"Cannot delete '{building_name}': {len(unplaced)} resident(s) "
                f"have nowhere to go — every other building is full.\n\n{stuck}\n\n"
                "Add rooms to another building, or free some up, then try again.")
            conn.close()
            return

        message = (f"Are you sure you want to delete building '{building_name}'?\n"
                   "This will also delete all associated rooms.")
        if moves:
            plan = "\n".join("  • " + describe_move(move) for move in moves)
            message += (f"\n\n{len(moves)} resident(s) will be moved automatically "
                        f"into the remaining buildings:\n\n{plan}\n\n"
                        "Their rent and contract dates stay the same, and each "
                        "will be emailed their new building, room number and floor.")

        if not messagebox.askyesno(
                _t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.confirm_delete', default="Confirm Delete"),
                message):
            conn.close()
            return

        # Moves and deletion share one transaction, so a failure anywhere
        # leaves both the building and its residents untouched.
        if moves:
            actor = 'housing'
            if getattr(gui_instance, 'auth', None) and gui_instance.auth.current_user:
                actor = gui_instance.auth.current_user.get('username', 'housing')
            apply_relocations(
                cursor, moves,
                reason=(f"The building you were living in, {building_name}, "
                        f"has been taken out of service."),
                actor=actor,
            )

        # Delete rooms and building
        cursor.execute('DELETE FROM housing_rooms WHERE building_id = ?', (building_id,))
        cursor.execute('DELETE FROM housing_buildings WHERE building_id = ?', (building_id,))

        conn.commit()
        conn.close()

        # Email only after the commit — a promise of a new room must never
        # go out for a move that was rolled back.
        summary = ""
        if moves:
            sent, failed = notify_relocated_residents(moves)
            summary = (f"\n\n{len(moves)} resident(s) relocated. "
                       f"Emails: {sent} sent, {failed} failed.")

        messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.success', default="Success"), f"Building '{building_name}' deleted successfully!{summary}")
        refresh_buildings_list(gui_instance)

    except Exception as e:
        messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.building_manager.dialogs.error', default="Error"), f"Failed to delete building: {str(e)}")


def show_building_rooms_management(gui_instance, building_id, building_name):
    """Show room management interface for a specific building"""
    # This function will be implemented in room_manager.py
    # For now, import and call from there
    from education_system.systems.university.domains.operations.interfaces.gui.campus.housing.housing_accommodation_gui.room_manager import show_room_management
    show_room_management(gui_instance, building_id, building_name)
