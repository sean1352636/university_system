"""
Assignment management functions - managing housing room assignments.
Handles assignment viewing, status updates, and assignment details.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import immutable audit logging if available
try:
    from education_system.university_system.infrastructure.security.immutable_audit_log import (
        AuditAction, log_security_event
    )
    from education_system.university_system.modules.shared.utils.gui_context import get_gui_context
    IMMUTABLE_AUDIT_AVAILABLE = True

    def safe_log_security_event(*args, **kwargs):
        try:
            log_security_event(*args, **kwargs)
        except Exception as e:
            print(f"Warning: Failed to log security event: {e}")
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

    def safe_log_security_event(*args, **kwargs):
        pass


def show_assignments(gui_instance):
    """Show housing assignments interface"""
    gui_instance.clear_content()

    ttk.Label(gui_instance.content_frame, text="Housing Assignments",
             font=('Arial', 16, 'bold')).pack(pady=(0, 20))

    # Filter and list frame
    main_frame = ttk.Frame(gui_instance.content_frame)
    main_frame.pack(fill='both', expand=True)

    # Filter frame
    filter_frame = ttk.LabelFrame(main_frame, text="Filter Assignments", padding="10")
    filter_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, sticky='w')
    gui_instance.assign_status_filter = ttk.Combobox(filter_frame,
                                           values=['All', 'Active', 'Pending', 'Terminated', 'Expired'])
    gui_instance.assign_status_filter.set('All')
    gui_instance.assign_status_filter.grid(row=0, column=1, padx=10)

    ttk.Button(filter_frame, text="Apply Filter",
              command=lambda: refresh_assignments_list(gui_instance)).grid(row=0, column=2, padx=10)

    # Assignments list
    list_frame = ttk.Frame(main_frame)
    list_frame.pack(fill='both', expand=True)

    columns = ('Assignment ID', 'Student', 'Room', 'Building', 'Move-in', 'Status')
    gui_instance.assignments_tree = ttk.Treeview(list_frame, columns=columns, show='headings')

    for col in columns:
        gui_instance.assignments_tree.heading(col, text=col)
        gui_instance.assignments_tree.column(col, width=150)

    # Scrollbars
    v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=gui_instance.assignments_tree.yview)
    h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=gui_instance.assignments_tree.xview)
    gui_instance.assignments_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    gui_instance.assignments_tree.pack(side='left', fill='both', expand=True)
    v_scroll.pack(side='right', fill='y')

    # Buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill='x', pady=20)

    ttk.Button(buttons_frame, text="Refresh", command=lambda: refresh_assignments_list(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="View Details", command=lambda: view_assignment_details(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Update Status", command=lambda: update_assignment_status(gui_instance)).pack(side='left', padx=5)

    # Load assignments
    refresh_assignments_list(gui_instance)


def refresh_assignments_list(gui_instance):
    """Refresh assignments list"""
    for item in gui_instance.assignments_tree.get_children():
        gui_instance.assignments_tree.delete(item)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        status_filter = gui_instance.assign_status_filter.get()
        if status_filter == 'All':
            cursor.execute('''
            SELECT a.assignment_id, s.first_name, s.last_name, r.room_number,
                   b.building_name, a.move_in_date, a.status
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY a.created_at DESC
            ''')
        else:
            cursor.execute('''
            SELECT a.assignment_id, s.first_name, s.last_name, r.room_number,
                   b.building_name, a.move_in_date, a.status
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.status = ?
            ORDER BY a.created_at DESC
            ''', (status_filter,))

        assignments = cursor.fetchall()

        for assign in assignments:
            student_name = f"{assign[1]} {assign[2]}"
            gui_instance.assignments_tree.insert('', 'end', values=(
                assign[0], student_name, assign[3], assign[4], assign[5], assign[6]
            ))

        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load assignments: {str(e)}")


def view_assignment_details(gui_instance):
    """View assignment details"""
    selected = gui_instance.assignments_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select an assignment to view")
        return

    assignment_id = gui_instance.assignments_tree.item(selected[0])['values'][0]
    show_assignment_details_dialog(gui_instance, assignment_id)


def show_assignment_details_dialog(gui_instance, assignment_id):
    """Show assignment details dialog"""
    details_window = tk.Toplevel(gui_instance.root)
    details_window.title("Assignment Details")
    details_window.geometry("600x500")
    details_window.transient(gui_instance.root)
    details_window.grab_set()

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, s.email_address,
               r.room_number, r.floor_number, r.room_type, b.building_name, b.address,
               a.move_in_date, a.planned_move_out_date, a.actual_move_out_date,
               a.contract_number, a.monthly_rent, a.status, a.assigned_by, a.created_at
        FROM housing_assignments a
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.assignment_id = ?
        ''', (assignment_id,))

        assign_data = cursor.fetchone()
        conn.close()

        if not assign_data:
            messagebox.showerror("Error", "Assignment not found")
            details_window.destroy()
            return

        # Create scrolled text widget
        text_widget = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, width=70, height=25)
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)

        # Format details
        details = f"""Assignment Details
{'='*50}

Assignment ID: {assign_data[0]}
Student: {assign_data[2]} {assign_data[3]} ({assign_data[1]})
Email: {assign_data[4]}

Room Information:
Room: {assign_data[5]} (Floor {assign_data[6]})
Type: {assign_data[7]}
Building: {assign_data[8]}
Address: {assign_data[9]}

Assignment Details:
Move-in Date: {assign_data[10]}
Planned Move-out Date: {assign_data[11]}
"""

        if assign_data[12]:
            details += f"Actual Move-out Date: {assign_data[12]}\n"

        details += f"""Contract Number: {assign_data[13]}
Monthly Rent: £{assign_data[14]}
Status: {assign_data[15]}
Assigned by: {assign_data[16]}
Assignment Date: {assign_data[17]}
"""

        text_widget.insert('1.0', details)
        text_widget.config(state='disabled')

        # Close button
        ttk.Button(details_window, text="Close",
                  command=details_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load assignment details: {str(e)}")
        details_window.destroy()


def update_assignment_status(gui_instance):
    """Update assignment status"""
    selected = gui_instance.assignments_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select an assignment to update")
        return

    assignment_id = gui_instance.assignments_tree.item(selected[0])['values'][0]
    current_status = gui_instance.assignments_tree.item(selected[0])['values'][5]

    # Status update dialog
    status_window = tk.Toplevel(gui_instance.root)
    status_window.title("Update Assignment Status")
    status_window.geometry("400x300")
    status_window.transient(gui_instance.root)
    status_window.grab_set()

    ttk.Label(status_window, text=f"Current Status: {current_status}",
             font=('Arial', 12, 'bold')).pack(pady=20)

    ttk.Label(status_window, text="New Status:").pack(pady=10)

    status_var = tk.StringVar()
    statuses = ['Active', 'Terminated', 'Expired']

    for status in statuses:
        ttk.Radiobutton(status_window, text=status, variable=status_var,
                       value=status).pack(pady=5)

    # Move-out date for terminated/expired
    date_frame = ttk.Frame(status_window)
    date_frame.pack(pady=20)

    ttk.Label(date_frame, text="Move-out Date (if terminated/expired):").pack()
    date_entry = ttk.Entry(date_frame, width=20)
    date_entry.pack(pady=5)
    date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

    def update_status():
        new_status = status_var.get()
        if not new_status:
            messagebox.showerror("Error", "Please select a status")
            return

        move_out_date = date_entry.get().strip() if new_status in ['Terminated', 'Expired'] else None

        try:
            if move_out_date:
                datetime.strptime(move_out_date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Error", "Please enter valid date (YYYY-MM-DD)")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if move_out_date:
                cursor.execute('''
                UPDATE housing_assignments
                SET status = ?, actual_move_out_date = ?, updated_at = ?
                WHERE assignment_id = ?
                ''', (new_status, move_out_date, timestamp, assignment_id))
            else:
                cursor.execute('''
                UPDATE housing_assignments
                SET status = ?, updated_at = ?
                WHERE assignment_id = ?
                ''', (new_status, timestamp, assignment_id))

            conn.commit()
            conn.close()

            # Immutable audit log for assignment status update
            if IMMUTABLE_AUDIT_AVAILABLE:
                admin_user_id, session_id = get_gui_context(gui_instance.auth)
                safe_log_security_event(
                    action=AuditAction.RECORD_UPDATE,
                    user_id=admin_user_id,
                    resource_type='housing_assignment',
                    resource_id=assignment_id,
                    session_id=session_id,
                    details={
                        'old_status': current_status,
                        'new_status': new_status,
                        'move_out_date': move_out_date
                    }
                )

            messagebox.showinfo("Success", f"Assignment status updated to {new_status}")
            refresh_assignments_list(gui_instance)
            status_window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update status: {str(e)}")

    # Buttons
    buttons_frame = ttk.Frame(status_window)
    buttons_frame.pack(pady=10)

    ttk.Button(buttons_frame, text="Update", command=update_status).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Cancel", command=status_window.destroy).pack(side='left', padx=5)


def load_active_assignments(gui_instance):
    """Load active assignments for payment"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT a.assignment_id, s.first_name, s.last_name, s.student_id,
               r.room_number, b.building_name, a.monthly_rent
        FROM housing_assignments a
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.status = 'Active'
        ORDER BY s.last_name, s.first_name
        ''')

        assignments = cursor.fetchall()
        conn.close()

        assignment_values = []
        for assign in assignments:
            display_text = f"{assign[1]} {assign[2]} ({assign[3]}) - Room {assign[4]} in {assign[5]} - £{assign[6]}/month"
            assignment_values.append(display_text)

        gui_instance.assignment_combo['values'] = assignment_values

    except Exception as e:
        print(f"Error loading assignments: {str(e)}")
