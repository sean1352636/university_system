"""
Maintenance management functions - handling maintenance requests.
Manages maintenance request creation, viewing, updates, and email notifications.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import generate_id

# Import email notification functions
from education_system.systems.university.interfaces.gui.operations.campus.housing.housing_accommodation_gui.email_notifications import (
    send_housing_email,
    send_maintenance_email
)


def show_maintenance(gui_instance):
    """Show maintenance requests interface"""
    gui_instance.clear_content()

    ttk.Label(gui_instance.content_frame, text="Maintenance Requests",
             font=('Arial', 16, 'bold')).pack(pady=(0, 20))

    # Create notebook
    notebook = ttk.Notebook(gui_instance.content_frame)
    notebook.pack(fill='both', expand=True)

    # Requests list tab
    list_frame = ttk.Frame(notebook, padding="10")
    notebook.add(list_frame, text="View Requests")
    create_maintenance_list(gui_instance, list_frame)

    # New request tab
    new_frame = ttk.Frame(notebook, padding="10")
    notebook.add(new_frame, text="New Request")
    create_maintenance_form(gui_instance, new_frame)


def create_maintenance_list(gui_instance, parent):
    """Create maintenance requests list"""
    # Filter frame
    filter_frame = ttk.LabelFrame(parent, text="Filter Requests", padding="10")
    filter_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, sticky='w')
    gui_instance.maint_status_filter = ttk.Combobox(filter_frame,
                                          values=['All', 'Open', 'In Progress', 'Pending Parts', 'Complete'])
    gui_instance.maint_status_filter.set('Open')
    gui_instance.maint_status_filter.grid(row=0, column=1, padx=10)

    ttk.Label(filter_frame, text="Priority:").grid(row=0, column=2, sticky='w', padx=(20, 0))
    gui_instance.maint_priority_filter = ttk.Combobox(filter_frame,
                                            values=['All', 'Emergency', 'High', 'Medium', 'Low'])
    gui_instance.maint_priority_filter.set('All')
    gui_instance.maint_priority_filter.grid(row=0, column=3, padx=10)

    ttk.Button(filter_frame, text="Apply Filter",
              command=lambda: refresh_maintenance_list(gui_instance)).grid(row=0, column=4, padx=10)

    # Requests list
    list_frame = ttk.Frame(parent)
    list_frame.pack(fill='both', expand=True)

    columns = ('Request ID', 'Date', 'Student', 'Room', 'Issue Type', 'Priority', 'Status')
    gui_instance.maintenance_tree = ttk.Treeview(list_frame, columns=columns, show='headings')

    for col in columns:
        gui_instance.maintenance_tree.heading(col, text=col)
        gui_instance.maintenance_tree.column(col, width=120)

    # Scrollbars
    v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=gui_instance.maintenance_tree.yview)
    h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=gui_instance.maintenance_tree.xview)
    gui_instance.maintenance_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    gui_instance.maintenance_tree.pack(side='left', fill='both', expand=True)
    v_scroll.pack(side='right', fill='y')

    # Buttons
    buttons_frame = ttk.Frame(parent)
    buttons_frame.pack(fill='x', pady=20)

    ttk.Button(buttons_frame, text="Refresh", command=lambda: refresh_maintenance_list(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="View Details", command=lambda: view_maintenance_details(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Update Request", command=lambda: update_maintenance_request(gui_instance)).pack(side='left', padx=5)

    # Load requests
    refresh_maintenance_list(gui_instance)


def refresh_maintenance_list(gui_instance):
    """Refresh maintenance requests list"""
    for item in gui_instance.maintenance_tree.get_children():
        gui_instance.maintenance_tree.delete(item)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Build query based on filters - add safety checks
        where_clauses = []
        params = []

        status_filter = getattr(gui_instance, 'maint_status_filter', None)
        if status_filter and status_filter.get() != 'All':
            where_clauses.append("m.status = ?")
            params.append(status_filter.get())

        priority_filter = getattr(gui_instance, 'maint_priority_filter', None)
        if priority_filter and priority_filter.get() != 'All':
            where_clauses.append("m.priority = ?")
            params.append(priority_filter.get())

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        cursor.execute(
        "SELECT m.request_id, m.request_date, s.first_name, s.last_name,"
        " r.room_number, b.building_name, m.issue_type, m.priority, m.status"
        " FROM housing_maintenance_requests m"
        " JOIN students s ON m.student_id = s.student_id"
        " JOIN housing_rooms r ON m.room_id = r.room_id"
        " JOIN housing_buildings b ON r.building_id = b.building_id"
        " WHERE " + where_clause +
        " ORDER BY"
        " CASE m.priority"
        " WHEN 'Emergency' THEN 1"
        " WHEN 'High' THEN 2"
        " WHEN 'Medium' THEN 3"
        " WHEN 'Low' THEN 4"
        " ELSE 5"
        " END,"
        " m.request_date DESC", params)

        requests = cursor.fetchall()

        for req in requests:
            student_name = f"{req[2]} {req[3]}"
            room_info = f"{req[4]} ({req[5]})"

            # Color code by priority
            tags = []
            if req[7] == 'Emergency':
                tags.append('emergency')
            elif req[7] == 'High':
                tags.append('high')

            gui_instance.maintenance_tree.insert('', 'end', values=(
                req[0], req[1], student_name, room_info, req[6], req[7], req[8]
            ), tags=tags)

        # Configure tags for colors
        gui_instance.maintenance_tree.tag_configure('emergency', background='#ffcccc')
        gui_instance.maintenance_tree.tag_configure('high', background='#ffe6cc')

        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load maintenance requests: {str(e)}")


def view_maintenance_details(gui_instance):
    """View maintenance request details"""
    selected = gui_instance.maintenance_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a request to view")
        return

    request_id = gui_instance.maintenance_tree.item(selected[0])['values'][0]
    show_maintenance_details_dialog(gui_instance, request_id)


def show_maintenance_details_dialog(gui_instance, request_id):
    """Show maintenance request details dialog"""
    details_window = tk.Toplevel(gui_instance.root)
    details_window.title("Maintenance Request Details")
    details_window.geometry("600x500")
    details_window.transient(gui_instance.root)
    details_window.grab_set()

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT m.request_id, s.first_name, s.last_name, s.email_address,
               r.room_number, b.building_name, r.floor_number,
               m.request_date, m.issue_type, m.description, m.priority, m.status,
               m.assigned_to, m.scheduled_date, m.completion_date, m.feedback
        FROM housing_maintenance_requests m
        JOIN students s ON m.student_id = s.student_id
        JOIN housing_rooms r ON m.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE m.request_id = ?
        ''', (request_id,))

        req_data = cursor.fetchone()
        conn.close()

        if not req_data:
            messagebox.showerror("Error", "Request not found")
            details_window.destroy()
            return

        # Create scrolled text widget
        text_widget = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, width=70, height=25)
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)

        # Format details
        details = f"""Maintenance Request Details
{'='*50}

Request ID: {req_data[0]}
Student: {req_data[1]} {req_data[2]}
Email: {req_data[3]}
Room: {req_data[4]} (Floor {req_data[6]}) in {req_data[5]}

Request Information:
Date: {req_data[7]}
Issue Type: {req_data[8]}
Description: {req_data[9]}
Priority: {req_data[10]}
Status: {req_data[11]}
"""

        if req_data[12]:
            details += f"Assigned to: {req_data[12]}\n"
        if req_data[13]:
            details += f"Scheduled Date: {req_data[13]}\n"
        if req_data[14]:
            details += f"Completion Date: {req_data[14]}\n"
        if req_data[15]:
            details += f"Feedback: {req_data[15]}\n"

        text_widget.insert('1.0', details)
        text_widget.config(state='disabled')

        # Close button
        ttk.Button(details_window, text="Close",
                  command=details_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load request details: {str(e)}")
        details_window.destroy()


def update_maintenance_request(gui_instance):
    """Update maintenance request"""
    selected = gui_instance.maintenance_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a request to update")
        return

    request_id = gui_instance.maintenance_tree.item(selected[0])['values'][0]
    show_update_maintenance_dialog(gui_instance, request_id)


def show_update_maintenance_dialog(gui_instance, request_id):
    """Show maintenance update dialog"""
    update_window = tk.Toplevel(gui_instance.root)
    update_window.title("Update Maintenance Request")
    update_window.geometry("500x400")
    update_window.transient(gui_instance.root)
    update_window.grab_set()

    # Status update
    status_frame = ttk.LabelFrame(update_window, text="Status", padding="10")
    status_frame.pack(fill='x', padx=10, pady=10)

    status_var = tk.StringVar()
    statuses = ['Open', 'In Progress', 'Pending Parts', 'Complete']

    for i, status in enumerate(statuses):
        ttk.Radiobutton(status_frame, text=status, variable=status_var,
                       value=status).grid(row=i//2, column=i%2, sticky='w', pady=5)

    # Assignment
    assign_frame = ttk.LabelFrame(update_window, text="Assignment", padding="10")
    assign_frame.pack(fill='x', padx=10, pady=10)

    ttk.Label(assign_frame, text="Assigned to:").grid(row=0, column=0, sticky='w')
    assigned_entry = ttk.Entry(assign_frame, width=30)
    assigned_entry.grid(row=0, column=1, padx=10)

    ttk.Label(assign_frame, text="Scheduled Date:").grid(row=1, column=0, sticky='w')
    scheduled_entry = ttk.Entry(assign_frame, width=30)
    scheduled_entry.grid(row=1, column=1, padx=10)
    scheduled_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

    # Notes/Feedback
    notes_frame = ttk.LabelFrame(update_window, text="Notes/Feedback", padding="10")
    notes_frame.pack(fill='both', expand=True, padx=10, pady=10)

    notes_text = scrolledtext.ScrolledText(notes_frame, height=6)
    notes_text.pack(fill='both', expand=True)

    def save_update():
        status = status_var.get()
        assigned = assigned_entry.get().strip()
        scheduled = scheduled_entry.get().strip()
        notes = notes_text.get('1.0', tk.END).strip()

        if not status:
            messagebox.showerror("Error", "Please select a status")
            return

        try:
            if scheduled:
                datetime.strptime(scheduled, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Error", "Please enter valid date (YYYY-MM-DD)")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Get current request details before update (for email)
            cursor.execute('''
                SELECT m.student_id, m.request_date, m.issue_type, m.description,
                       m.priority, r.room_number, b.building_name
                FROM housing_maintenance_requests m
                JOIN housing_rooms r ON m.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE m.request_id = ?
            ''', (request_id,))
            request_details = cursor.fetchone()

            completion_date = timestamp if status == 'Complete' else None

            cursor.execute('''
            UPDATE housing_maintenance_requests
            SET status = ?, assigned_to = ?, scheduled_date = ?,
                completion_date = ?, feedback = ?, updated_at = ?
            WHERE request_id = ?
            ''', (status, assigned or None, scheduled or None,
                  completion_date, notes or None, timestamp, request_id))

            conn.commit()
            conn.close()

            # Send email notification based on status change
            if request_details:
                try:
                    location_str = f"{request_details[6]}, Room {request_details[5]}"
                    email_data = {
                        'student_id': request_details[0],
                        'request_date': request_details[1],
                        'issue_type': request_details[2],
                        'description': request_details[3],
                        'priority': request_details[4],
                        'location': location_str,
                        'status': status,
                        'assigned_to': assigned or 'Maintenance Team',
                        'scheduled_date': scheduled or 'To be determined',
                        'completion_date': completion_date or 'N/A',
                        'feedback': notes,
                        'completed_by': assigned or 'Maintenance Team',
                        'work_performed': notes or 'Repair completed',
                        'reviewed_by': assigned or 'Maintenance Team',
                        'investigation_reason': notes or 'Further assessment required'
                    }

                    # Send appropriate email based on status
                    if status == 'Complete':
                        send_maintenance_email('completed', request_id, email_data)
                    elif status == 'Pending Parts':
                        send_maintenance_email('investigation', request_id, email_data)
                except Exception as email_error:
                    print(f"Warning: Failed to send status update email: {email_error}")

            messagebox.showinfo("Success", "Maintenance request updated successfully")
            refresh_maintenance_list(gui_instance)
            update_window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update request: {str(e)}")

    # Buttons
    buttons_frame = ttk.Frame(update_window)
    buttons_frame.pack(fill='x', padx=10, pady=10)

    ttk.Button(buttons_frame, text="Save", command=save_update).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Cancel", command=update_window.destroy).pack(side='left', padx=5)


def create_maintenance_form(gui_instance, parent):
    """Create new maintenance request form"""
    # Room selection
    room_frame = ttk.LabelFrame(parent, text="Room Selection", padding="10")
    room_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(room_frame, text="Building:").grid(row=0, column=0, sticky='w')
    gui_instance.maint_building_combo = ttk.Combobox(room_frame, width=30)
    gui_instance.maint_building_combo.grid(row=0, column=1, padx=10)
    gui_instance.maint_building_combo.bind('<<ComboboxSelected>>', lambda e: load_rooms_for_maintenance(gui_instance))

    ttk.Label(room_frame, text="Room:").grid(row=1, column=0, sticky='w')
    gui_instance.maint_room_combo = ttk.Combobox(room_frame, width=30)
    gui_instance.maint_room_combo.grid(row=1, column=1, padx=10)

    # Load buildings
    load_buildings_for_maintenance(gui_instance)

    # Request details
    details_frame = ttk.LabelFrame(parent, text="Request Details", padding="10")
    details_frame.pack(fill='both', expand=True, pady=(0, 20))

    ttk.Label(details_frame, text="Issue Type:").grid(row=0, column=0, sticky='w')
    gui_instance.issue_type_combo = ttk.Combobox(details_frame, width=30,
                                       values=["Plumbing", "Electrical", "HVAC", "Appliance",
                                              "Furniture", "Pest Control", "Structural",
                                              "Lock/Key", "Cleaning", "Other"])
    gui_instance.issue_type_combo.grid(row=0, column=1, padx=10)

    ttk.Label(details_frame, text="Priority:").grid(row=1, column=0, sticky='w')
    gui_instance.priority_combo = ttk.Combobox(details_frame, width=30,
                                     values=["Low", "Medium", "High", "Emergency"])
    gui_instance.priority_combo.set("Medium")
    gui_instance.priority_combo.grid(row=1, column=1, padx=10)

    ttk.Label(details_frame, text="Description:").grid(row=2, column=0, sticky='nw')
    gui_instance.description_text = tk.Text(details_frame, width=40, height=6)
    gui_instance.description_text.grid(row=2, column=1, padx=10, pady=10)

    # Submit button
    ttk.Button(details_frame, text="Submit Request",
              command=lambda: submit_maintenance_request(gui_instance)).grid(row=3, column=0, pady=20)


def load_buildings_for_maintenance(gui_instance):
    """Load buildings for maintenance form"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        conn.close()

        building_values = [f"{b[1]}" for b in buildings]
        gui_instance.maint_building_combo['values'] = building_values

    except Exception as e:
        print(f"Error loading buildings: {str(e)}")


def load_rooms_for_maintenance(gui_instance, event=None):
    """Load rooms for selected building"""
    building_name = gui_instance.maint_building_combo.get()
    if not building_name:
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT r.room_id, r.room_number, r.floor_number
        FROM housing_rooms r
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE b.building_name = ?
        ORDER BY r.floor_number, r.room_number
        ''', (building_name,))

        rooms = cursor.fetchall()
        conn.close()

        room_values = [f"{r[1]} (Floor {r[2]})" for r in rooms]
        gui_instance.maint_room_combo['values'] = room_values
        gui_instance.maint_room_combo.set("")

    except Exception as e:
        print(f"Error loading rooms: {str(e)}")


def submit_maintenance_request(gui_instance):
    """Submit maintenance request"""
    try:
        building_name = gui_instance.maint_building_combo.get()
        room_info = gui_instance.maint_room_combo.get()
        issue_type = gui_instance.issue_type_combo.get()
        priority = gui_instance.priority_combo.get()
        description = gui_instance.description_text.get('1.0', tk.END).strip()

        if not all([building_name, room_info, issue_type, priority, description]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        # Extract room number from room_info
        room_number = room_info.split(' (')[0]

        # Get room_id and student_id
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT r.room_id FROM housing_rooms r
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE b.building_name = ? AND r.room_number = ?
        ''', (building_name, room_number))

        room_result = cursor.fetchone()
        if not room_result:
            messagebox.showerror("Error", "Room not found")
            conn.close()
            return

        room_id = room_result[0]

        # For staff creating request, need to specify student or get from room assignment
        if gui_instance.auth and hasattr(gui_instance.auth, 'current_user') and gui_instance.auth.current_user:
            # Check if user is a student
            cursor.execute('SELECT student_id FROM students WHERE email_address = ? OR student_id = ?',
                         (gui_instance.auth.current_user.get('email', ''), gui_instance.auth.current_user.get('username', '')))
            student_result = cursor.fetchone()

            if student_result:
                student_id = student_result[0]
            else:
                # Staff member - get student from room assignment or ask for student ID
                cursor.execute('''
                SELECT a.student_id FROM housing_assignments a
                WHERE a.room_id = ? AND a.status = 'Active'
                LIMIT 1
                ''', (room_id,))
                assign_result = cursor.fetchone()

                if assign_result:
                    student_id = assign_result[0]
                else:
                    # No active assignment, ask for student ID
                    student_id = simpledialog.askstring("Student ID",
                                                       "Enter Student ID for this request:",
                                                       parent=gui_instance.root)
                    if not student_id:
                        messagebox.showerror("Error", "Student ID is required")
                        conn.close()
                        return

                    # Verify student exists
                    cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                    if not cursor.fetchone():
                        messagebox.showerror("Error", f"Student ID {student_id} not found")
                        conn.close()
                        return
        else:
            messagebox.showerror("Error", "Authentication required to submit maintenance requests")
            conn.close()
            return

        # Create request
        request_id = generate_id('REQ')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO housing_maintenance_requests (
            request_id, room_id, student_id, request_date, issue_type, description,
            priority, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request_id, room_id, student_id, timestamp, issue_type, description,
            priority, 'Open', timestamp, timestamp
        ))

        conn.commit()
        conn.close()

        # Send confirmation email to student
        try:
            location_str = f"{building_name}, Room {room_number}"
            request_email_data = {
                'student_id': student_id,
                'request_date': timestamp,
                'issue_type': issue_type,
                'description': description,
                'priority': priority,
                'status': 'Open',
                'location': location_str
            }
            send_maintenance_email('created', request_id, request_email_data)
        except Exception as email_error:
            print(f"Warning: Failed to send confirmation email: {email_error}")

        messagebox.showinfo("Success", f"Maintenance request submitted successfully!\nRequest ID: {request_id}")

        # Clear form
        gui_instance.maint_building_combo.set("")
        gui_instance.maint_room_combo.set("")
        gui_instance.issue_type_combo.set("")
        gui_instance.priority_combo.set("Medium")
        gui_instance.description_text.delete('1.0', tk.END)

        refresh_maintenance_list(gui_instance)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to submit request: {str(e)}")
