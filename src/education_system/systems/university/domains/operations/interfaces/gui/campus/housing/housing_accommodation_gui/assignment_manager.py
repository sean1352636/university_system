"""
Assignment management functions - managing housing room assignments.
Handles assignment viewing, status updates, and assignment details.
"""
import logging

logger = logging.getLogger(__name__)

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation import generate_id
# The room roster and the "someone has moved in with you" email live with the
# domain, so the CLI and this GUI notify a flat identically.
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.common import (
    LIVE_ASSIGNMENT_STATUSES,
    room_occupants,
    send_assignment_created_emails,
)

# Import immutable audit logging if available
try:
    from education_system.systems.university.infrastructure.security.immutable_audit_log import (
        AuditAction, log_security_event
    )
    from education_system.systems.university.infrastructure.security.audit_helpers import get_gui_context
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

    ttk.Label(gui_instance.content_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.labels.housing_assignments', default="Housing Assignments"),
             font=('Arial', 16, 'bold')).pack(pady=(0, 20))

    # Filter and list frame
    main_frame = ttk.Frame(gui_instance.content_frame)
    main_frame.pack(fill='both', expand=True)

    # Filter frame
    filter_frame = ttk.LabelFrame(main_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.labels.filter_assignments', default="Filter Assignments"), padding="10")
    filter_frame.pack(fill='x', pady=(0, 20))

    ttk.Label(filter_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.labels.status', default="Status:")).grid(row=0, column=0, sticky='w')
    gui_instance.assign_status_filter = ttk.Combobox(filter_frame,
                                           values=['All', 'Active', 'Pending', 'Terminated', 'Expired'])
    gui_instance.assign_status_filter.set('All')
    gui_instance.assign_status_filter.grid(row=0, column=1, padx=10)

    ttk.Button(filter_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.buttons.apply_filter', default="Apply Filter"),
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

    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.buttons.refresh', default="Refresh"), command=lambda: refresh_assignments_list(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.buttons.create_assignment', default="Create Assignment"), command=lambda: show_create_assignment_dialog(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.buttons.view_details', default="View Details"), command=lambda: view_assignment_details(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.buttons.update_status', default="Update Status"), command=lambda: update_assignment_status(gui_instance)).pack(side='left', padx=5)

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
        messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"), f"Failed to load assignments: {str(e)}")


def view_assignment_details(gui_instance):
    """View assignment details"""
    selected = gui_instance.assignments_tree.selection()
    if not selected:
        messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.please_select_an_assignment_to_view', default="Please select an assignment to view"))
        return

    assignment_id = gui_instance.assignments_tree.item(selected[0])['values'][0]
    show_assignment_details_dialog(gui_instance, assignment_id)


def show_assignment_details_dialog(gui_instance, assignment_id):
    """Show assignment details dialog"""
    details_window = tk.Toplevel(gui_instance.root)
    details_window.title(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.windows.assignment_details', default="Assignment Details"))
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
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.assignment_not_found', default="Assignment not found"))
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
        ttk.Button(details_window, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.buttons.close', default="Close"),
                  command=details_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"), f"Failed to load assignment details: {str(e)}")
        details_window.destroy()


def update_assignment_status(gui_instance):
    """Update assignment status"""
    selected = gui_instance.assignments_tree.selection()
    if not selected:
        messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.please_select_an_assignment_to_update', default="Please select an assignment to update"))
        return

    assignment_id = gui_instance.assignments_tree.item(selected[0])['values'][0]
    current_status = gui_instance.assignments_tree.item(selected[0])['values'][5]

    # Status update dialog
    status_window = tk.Toplevel(gui_instance.root)
    status_window.title(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.windows.update_assignment_status', default="Update Assignment Status"))
    status_window.geometry("400x300")
    status_window.transient(gui_instance.root)
    status_window.grab_set()

    ttk.Label(status_window, text=f"Current Status: {current_status}",
             font=('Arial', 12, 'bold')).pack(pady=20)

    ttk.Label(status_window, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.labels.new_status', default="New Status:")).pack(pady=10)

    status_var = tk.StringVar()
    statuses = ['Active', 'Terminated', 'Expired']

    for status in statuses:
        ttk.Radiobutton(status_window, text=status, variable=status_var,
                       value=status).pack(pady=5)

    # Move-out date for terminated/expired
    date_frame = ttk.Frame(status_window)
    date_frame.pack(pady=20)

    ttk.Label(date_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.labels.move_out_date_if_terminated_expired', default="Move-out Date (if terminated/expired):")).pack()
    date_entry = ttk.Entry(date_frame, width=20)
    date_entry.pack(pady=5)
    date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

    def update_status():
        new_status = status_var.get()
        if not new_status:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.please_select_a_status', default="Please select a status"))
            return

        move_out_date = date_entry.get().strip() if new_status in ['Terminated', 'Expired'] else None

        try:
            if move_out_date:
                datetime.strptime(move_out_date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.please_enter_valid_date_yyyy_mm_dd', default="Please enter valid date (YYYY-MM-DD)"))
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

            messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.success', default="Success"), f"Assignment status updated to {new_status}")
            refresh_assignments_list(gui_instance)
            status_window.destroy()

        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"), f"Failed to update status: {str(e)}")

    # Buttons
    buttons_frame = ttk.Frame(status_window)
    buttons_frame.pack(pady=10)

    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.buttons.update', default="Update"), command=update_status).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.buttons.cancel', default="Cancel"), command=status_window.destroy).pack(side='left', padx=5)


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


def show_create_assignment_dialog(gui_instance):
    """Assign a student to a room directly, without an application.

    Mirrors the CLI's Create New Assignment: only rooms with spare capacity
    are offered, an already-housed student is refused, a finance hold blocks
    the assignment, and once it is written everyone sharing the room is
    emailed who has moved in with them.
    """
    if not gui_instance.auth or not gui_instance.auth.check_permission('manage_accommodations'):
        messagebox.showerror(
            _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
            "You don't have permission to create assignments.")
        return

    dialog = tk.Toplevel(gui_instance.root)
    dialog.title("Create Assignment")
    dialog.geometry("640x480")
    dialog.transient(gui_instance.root)
    dialog.grab_set()

    form = ttk.Frame(dialog, padding=20)
    form.pack(fill='both', expand=True)

    ttk.Label(form, text="Create Housing Assignment",
              font=('Arial', 13, 'bold')).grid(row=0, column=0, columnspan=2,
                                               sticky='w', pady=(0, 15))

    ttk.Label(form, text="Student ID:").grid(row=1, column=0, sticky='w', pady=5)
    student_var = tk.StringVar()
    student_entry = ttk.Entry(form, textvariable=student_var, width=32)
    student_entry.grid(row=1, column=1, sticky='w', pady=5, padx=10)

    student_info = ttk.Label(form, text="", foreground='grey')
    student_info.grid(row=2, column=1, sticky='w', padx=10)

    def lookup_student():
        sid = student_var.get().strip()
        if not sid:
            student_info.config(text="Enter a student ID first.", foreground='red')
            return
        try:
            conn = get_connection()
            try:
                row = conn.execute(
                    'SELECT first_name, last_name, email_address FROM students '
                    'WHERE student_id = ?', (sid,)).fetchone()
            finally:
                conn.close()
            if row:
                student_info.config(
                    text=f"{row[0]} {row[1]} - {row[2] or 'no email on file'}",
                    foreground='green')
            else:
                student_info.config(text="Student not found.", foreground='red')
        except Exception as exc:
            student_info.config(text=f"Lookup failed: {exc}", foreground='red')

    ttk.Button(form, text="Look up", command=lookup_student).grid(
        row=1, column=2, padx=5)

    # Only rooms that can take another person are offered.
    rooms = []
    try:
        conn = get_connection()
        try:
            rooms = conn.execute('''
            SELECT r.room_id, b.building_name, r.room_number, r.floor_number,
                   r.room_type, r.max_occupants, r.current_occupants, r.monthly_rent
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.current_occupants < r.max_occupants
              AND r.status IN ('Available', 'Reserved')
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''').fetchall()
        finally:
            conn.close()
    except Exception as exc:
        messagebox.showerror(
            _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
            f"Failed to load rooms: {exc}", parent=dialog)
        dialog.destroy()
        return

    if not rooms:
        messagebox.showwarning(
            "No space", "There are no rooms with space available.", parent=dialog)
        dialog.destroy()
        return

    room_labels = [
        f"{r[1]} room {r[2]} (floor {r[3]}, {r[4]}) - {r[6]}/{r[5]} occupied - £{r[7]:.2f}/mo"
        for r in rooms
    ]

    ttk.Label(form, text="Room:").grid(row=3, column=0, sticky='w', pady=5)
    room_combo = ttk.Combobox(form, values=room_labels, width=52, state='readonly')
    room_combo.grid(row=3, column=1, columnspan=2, sticky='w', pady=5, padx=10)

    ttk.Label(form, text="Move-in Date (YYYY-MM-DD):").grid(row=4, column=0, sticky='w', pady=5)
    move_in_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
    ttk.Entry(form, textvariable=move_in_var, width=32).grid(
        row=4, column=1, sticky='w', pady=5, padx=10)

    ttk.Label(form, text="Duration (months):").grid(row=5, column=0, sticky='w', pady=5)
    duration_var = tk.StringVar(value="9")
    ttk.Entry(form, textvariable=duration_var, width=32).grid(
        row=5, column=1, sticky='w', pady=5, padx=10)

    ttk.Label(form, text="Monthly Rent (blank = room rate):").grid(
        row=6, column=0, sticky='w', pady=5)
    rent_var = tk.StringVar()
    ttk.Entry(form, textvariable=rent_var, width=32).grid(
        row=6, column=1, sticky='w', pady=5, padx=10)

    def save_assignment():
        student_id = student_var.get().strip()
        room_index = room_combo.current()
        move_in_date = move_in_var.get().strip()
        duration_raw = duration_var.get().strip()

        missing = [label for label, value in (
            ("Student ID", student_id),
            ("Room", "" if room_index < 0 else "set"),
            ("Move-in Date", move_in_date),
            ("Duration", duration_raw),
        ) if not value]
        if missing:
            messagebox.showerror(
                _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
                "These fields cannot be left blank:\n\n"
                + "\n".join(f"  • {name}" for name in missing), parent=dialog)
            return

        try:
            datetime.strptime(move_in_date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror(
                _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
                f"'{move_in_date}' is not a valid date. Use YYYY-MM-DD.", parent=dialog)
            return

        try:
            duration = int(duration_raw)
            if duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
                "Duration must be a whole number of months greater than 0.", parent=dialog)
            return

        room = rooms[room_index]
        room_id, building_name, room_number = room[0], room[1], room[2]
        monthly_rent = room[7]
        if rent_var.get().strip():
            try:
                monthly_rent = float(rent_var.get().strip())
            except ValueError:
                messagebox.showerror(
                    _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
                    "Monthly rent must be a number.", parent=dialog)
                return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?',
                           (student_id,))
            name_row = cursor.fetchone()
            if not name_row:
                messagebox.showerror(
                    _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
                    f"No student found with ID {student_id}.", parent=dialog)
                conn.close()
                return

            # One live assignment per student.
            placeholders = ','.join('?' * len(LIVE_ASSIGNMENT_STATUSES))
            cursor.execute('''
            SELECT a.assignment_id, r.room_number, b.building_name, a.status
            FROM housing_assignments a
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.student_id = ? AND a.status IN ({statuses})
            '''.format(statuses=placeholders), [student_id] + list(LIVE_ASSIGNMENT_STATUSES))
            existing = cursor.fetchone()
            if existing:
                messagebox.showerror(
                    _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
                    f"{student_id} already has a {existing[3]} assignment "
                    f"({existing[0]}) in {existing[2]} room {existing[1]}.\n\n"
                    "End that assignment first, then assign the new room.",
                    parent=dialog)
                conn.close()
                return

            # Same finance-hold gate as approving an application.
            try:
                from education_system.systems.university.services.bus import housing_finance
                allowed, reason = housing_finance.can_assign_room(student_id)
                if not allowed:
                    messagebox.showerror(
                        _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
                        f"Cannot assign a room to {student_id}: {reason}.\n\n"
                        "Clear the hold in Finance first.", parent=dialog)
                    conn.close()
                    return
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            move_out_date = (datetime.strptime(move_in_date, '%Y-%m-%d')
                             + timedelta(days=30 * duration)).strftime('%Y-%m-%d')
            assignment_id = generate_id('ASG')
            contract_number = generate_id('CNT')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            actor = gui_instance.auth.current_user.get('username', 'housing')

            cursor.execute('''
            INSERT INTO housing_assignments (
                assignment_id, application_id, student_id, room_id, move_in_date,
                planned_move_out_date, contract_number, monthly_rent, status,
                assigned_by, created_at, updated_at
            ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, 'Active', ?, ?, ?)
            ''', (assignment_id, student_id, room_id, move_in_date, move_out_date,
                  contract_number, monthly_rent, actor, timestamp, timestamp))

            cursor.execute('''
            UPDATE housing_rooms
            SET current_occupants = current_occupants + 1,
                status = CASE WHEN current_occupants + 1 >= max_occupants
                              THEN 'Occupied' ELSE 'Reserved' END,
                updated_at = ?
            WHERE room_id = ?
            ''', (timestamp, room_id))

            cursor.execute('''
            UPDATE housing_buildings
            SET available_rooms = (
                    SELECT COUNT(*) FROM housing_rooms
                    WHERE building_id = housing_buildings.building_id
                      AND status = 'Available'
                ),
                updated_at = ?
            WHERE building_id = (SELECT building_id FROM housing_rooms WHERE room_id = ?)
            ''', (timestamp, room_id))

            cursor.execute('''
            SELECT b.building_name, r.room_number, r.floor_number, r.room_type,
                   b.address, b.campus_location, r.current_occupants, r.max_occupants
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.room_id = ?
            ''', (room_id,))
            detail = cursor.fetchone()

            assignment = {
                'assignment_id': assignment_id,
                'contract_number': contract_number,
                'student_id': student_id,
                'student_name': f"{name_row[0] or ''} {name_row[1] or ''}".strip(),
                'room_id': room_id,
                'building_name': detail[0], 'room_number': detail[1],
                'floor_number': detail[2], 'room_type': detail[3],
                'building_address': detail[4], 'campus_location': detail[5],
                'current_occupants': detail[6], 'max_occupants': detail[7],
                'monthly_rent': monthly_rent,
                'move_in_date': move_in_date,
                'planned_move_out_date': move_out_date,
                'assigned_by': actor,
                'assigned_date': timestamp,
            }
            occupants = room_occupants(cursor, room_id)

            conn.commit()
            conn.close()

            # Notify the whole room after the commit.
            sent, failed = send_assignment_created_emails(assignment, occupants)

            log_create('housing_assignment', assignment_id,
                       f"{student_id} assigned to {building_name} room {room_number}")

            if IMMUTABLE_AUDIT_AVAILABLE:
                admin_user_id, session_id = get_gui_context(gui_instance.auth)
                safe_log_security_event(
                    action=AuditAction.RECORD_CREATE,
                    user_id=admin_user_id,
                    resource_type='housing_assignment',
                    resource_id=assignment_id,
                    session_id=session_id,
                    details={'student_id': student_id, 'room_id': room_id,
                             'move_in_date': move_in_date, 'rent': monthly_rent},
                )

            messagebox.showinfo(
                _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.success', default="Success"),
                f"Assignment created.\n\n"
                f"Assignment ID: {assignment_id}\n"
                f"Student: {student_id}\n"
                f"Room: {building_name} room {room_number}\n"
                f"Move in: {move_in_date}\nMove out: {move_out_date}\n"
                f"Rent: £{monthly_rent:.2f}/month\n\n"
                f"Room notified: {sent} email(s) sent"
                + (f", {failed} failed." if failed else "."),
                parent=dialog)
            dialog.destroy()
            refresh_assignments_list(gui_instance)

        except Exception as exc:
            messagebox.showerror(
                _t('gui.operations.campus.housing.housing_accommodation_gui.assignment_manager.dialogs.error', default="Error"),
                f"Failed to create assignment: {exc}", parent=dialog)

    button_frame = ttk.Frame(dialog)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Create Assignment",
               command=save_assignment).pack(side='left', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
