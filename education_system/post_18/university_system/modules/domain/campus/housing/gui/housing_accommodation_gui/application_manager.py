"""
Application management functions - housing application submission and processing.
Handles application creation, reviewing, approval/rejection workflow, and email notifications.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import generate_id

# Import email notification functions
from education_system.post_18.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui.email_notifications import (
    send_housing_email,
    send_maintenance_email
)

# Import immutable audit logging if available
try:
    from education_system.post_18.university_system.infrastructure.security.immutable_audit_log import (
        AuditAction, log_security_event
    )
    from education_system.post_18.university_system.modules.shared.utils.gui_context import get_gui_context
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


def show_applications(gui_instance):
    """Show housing applications interface"""
    gui_instance.clear_content()

    ttk.Label(gui_instance.content_frame, text="Housing Applications",
             font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=(0, 20), sticky='w')

    # Create notebook
    notebook = ttk.Notebook(gui_instance.content_frame)
    notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Applications list tab
    list_frame = ttk.Frame(notebook, padding="10")
    notebook.add(list_frame, text="Applications List")
    create_applications_list(gui_instance, list_frame)

    # New application tab
    new_frame = ttk.Frame(notebook, padding="10")
    notebook.add(new_frame, text="New Application")
    create_new_application_form(gui_instance, new_frame)


def create_applications_list(gui_instance, parent):
    """Create applications list view"""
    # Filter frame
    filter_frame = ttk.LabelFrame(parent, text="Filter Applications", padding="10")
    filter_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))

    ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, sticky='w')
    gui_instance.app_status_filter = ttk.Combobox(filter_frame,
                                        values=['All', 'Pending', 'Approved', 'Rejected', 'Waiting List'])
    gui_instance.app_status_filter.set('All')
    gui_instance.app_status_filter.grid(row=0, column=1, padx=10)

    ttk.Button(filter_frame, text="Apply Filter",
              command=lambda: refresh_applications_list(gui_instance)).grid(row=0, column=2, padx=10)

    # Applications treeview
    tree_frame = ttk.Frame(parent)
    tree_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

    columns = ('ID', 'Student', 'Date', 'Room Type', 'Status', 'Review Date')
    gui_instance.applications_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

    for col in columns:
        gui_instance.applications_tree.heading(col, text=col)
        gui_instance.applications_tree.column(col, width=120)

    # Scrollbars
    v_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=gui_instance.applications_tree.yview)
    h_scroll = ttk.Scrollbar(tree_frame, orient='horizontal', command=gui_instance.applications_tree.xview)
    gui_instance.applications_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    gui_instance.applications_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
    h_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))

    # Buttons
    buttons_frame = ttk.Frame(parent)
    buttons_frame.grid(row=2, column=0, columnspan=2, pady=20)

    ttk.Button(buttons_frame, text="Refresh", command=lambda: refresh_applications_list(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="View Details", command=lambda: view_application_details(gui_instance)).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Process Application", command=lambda: process_selected_application(gui_instance)).pack(side='left', padx=5)

    # Load applications
    refresh_applications_list(gui_instance)


def refresh_applications_list(gui_instance):
    """Refresh the applications list"""
    for item in gui_instance.applications_tree.get_children():
        gui_instance.applications_tree.delete(item)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        status_filter = gui_instance.app_status_filter.get()
        if status_filter == 'All':
            cursor.execute('''
            SELECT a.application_id, s.first_name, s.last_name, a.application_date,
                   a.preferred_room_type, a.status, a.review_date
            FROM housing_applications a
            JOIN students s ON a.student_id = s.student_id
            ORDER BY a.application_date DESC
            ''')
        else:
            cursor.execute('''
            SELECT a.application_id, s.first_name, s.last_name, a.application_date,
                   a.preferred_room_type, a.status, a.review_date
            FROM housing_applications a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.status = ?
            ORDER BY a.application_date DESC
            ''', (status_filter,))

        applications = cursor.fetchall()

        for app in applications:
            student_name = f"{app[1]} {app[2]}"
            gui_instance.applications_tree.insert('', 'end', values=(
                app[0], student_name, app[3], app[4], app[5], app[6] or ''
            ))

        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load applications: {str(e)}")


def view_application_details(gui_instance):
    """View details of selected application"""
    selected = gui_instance.applications_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select an application to view")
        return

    application_id = gui_instance.applications_tree.item(selected[0])['values'][0]
    show_application_details_dialog(gui_instance, application_id)


def show_application_details_dialog(gui_instance, application_id):
    """Show application details dialog"""
    details_window = tk.Toplevel(gui_instance.root)
    details_window.title("Application Details")
    details_window.geometry("600x500")
    details_window.transient(gui_instance.root)
    details_window.grab_set()

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT a.application_id, a.student_id, s.first_name, s.last_name, s.email_address,
               a.application_date, a.preferred_building_id, b.building_name, a.preferred_room_type,
               a.requested_move_in_date, a.requested_duration_months, a.special_requirements,
               a.status, a.notes, a.reviewed_by, a.review_date
        FROM housing_applications a
        JOIN students s ON a.student_id = s.student_id
        LEFT JOIN housing_buildings b ON a.preferred_building_id = b.building_id
        WHERE a.application_id = ?
        ''', (application_id,))

        app_data = cursor.fetchone()
        conn.close()

        if not app_data:
            messagebox.showerror("Error", "Application not found")
            details_window.destroy()
            return

        # Create scrolled text widget for details
        text_widget = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, width=70, height=25)
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)

        # Format application details
        details = f"""Application Details
{'='*50}

Application ID: {app_data[0]}
Student: {app_data[2]} {app_data[3]} ({app_data[1]})
Email: {app_data[4]}
Application Date: {app_data[5]}
Preferred Building: {app_data[7] or 'No preference'}
Preferred Room Type: {app_data[8]}
Requested Move-in Date: {app_data[9]}
Requested Duration: {app_data[10]} months
Special Requirements: {app_data[11] or 'None'}

Status: {app_data[12]}
"""

        if app_data[13]:
            details += f"Notes: {app_data[13]}\n"
        if app_data[14]:
            details += f"Reviewed by: {app_data[14]}\n"
        if app_data[15]:
            details += f"Review Date: {app_data[15]}\n"

        text_widget.insert('1.0', details)
        text_widget.config(state='disabled')

        # Close button
        ttk.Button(details_window, text="Close",
                  command=details_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load application details: {str(e)}")
        details_window.destroy()


def process_selected_application(gui_instance):
    """Process the selected application"""
    selected = gui_instance.applications_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select an application to process")
        return

    application_id = gui_instance.applications_tree.item(selected[0])['values'][0]
    show_process_application_dialog(gui_instance, application_id)


def show_process_application_dialog(gui_instance, application_id):
    """Show dialog to process application"""
    process_window = tk.Toplevel(gui_instance.root)
    process_window.title("Process Application")
    process_window.geometry("500x400")
    process_window.transient(gui_instance.root)
    process_window.grab_set()

    # Decision frame
    decision_frame = ttk.LabelFrame(process_window, text="Decision", padding="10")
    decision_frame.pack(fill='x', padx=10, pady=10)

    decision_var = tk.StringVar()
    decisions = [
        ("Approve", "Approved"),
        ("Reject", "Rejected"),
        ("Waiting List", "Waiting List"),
        ("Request More Info", "More Info Needed")
    ]

    for i, (text, value) in enumerate(decisions):
        ttk.Radiobutton(decision_frame, text=text, variable=decision_var,
                       value=value).grid(row=i//2, column=i%2, sticky='w', pady=5)

    # Notes frame
    notes_frame = ttk.LabelFrame(process_window, text="Notes", padding="10")
    notes_frame.pack(fill='both', expand=True, padx=10, pady=10)

    notes_text = scrolledtext.ScrolledText(notes_frame, height=6)
    notes_text.pack(fill='both', expand=True)

    def process_application():
        decision = decision_var.get()
        notes = notes_text.get('1.0', tk.END).strip()

        if not decision:
            messagebox.showerror("Error", "Please select a decision")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Get application details for email
            cursor.execute('''
                SELECT student_id, preferred_room_type, requested_move_in_date,
                       requested_duration_months, special_requirements, application_date
                FROM housing_applications
                WHERE application_id = ?
            ''', (application_id,))
            app_info = cursor.fetchone()

            if not app_info:
                messagebox.showerror("Error", "Application not found")
                conn.close()
                return

            student_id, room_type, move_in_date, duration, special_req, app_date = app_info

            # Update application
            cursor.execute('''
            UPDATE housing_applications
            SET status = ?, notes = ?, reviewed_by = ?, review_date = ?, updated_at = ?
            WHERE application_id = ?
            ''', (decision, notes, gui_instance.auth.current_user['username'], timestamp, timestamp, application_id))

            conn.commit()
            conn.close()

            # Send email based on decision
            application_data = {
                'application_id': application_id,
                'student_id': student_id,
                'preferred_room_type': room_type,
                'requested_move_in_date': move_in_date,
                'requested_duration_months': duration,
                'special_requirements': special_req or 'None',
                'status': decision,
                'application_date': app_date
            }

            # Prepare additional variables for email
            reviewer_name = gui_instance.auth.current_user.get('username', 'Housing Administration')
            additional_vars = {
                'approval_date': timestamp if decision == 'Approved' else None,
                'review_date': timestamp,
                'approved_by': reviewer_name if decision == 'Approved' else None,
                'reviewed_by': reviewer_name,
                'approval_reason': notes if decision == 'Approved' else None,
                'rejection_reason': notes if decision == 'Rejected' else None,
                'detailed_explanation': notes or 'No additional details provided.',
                'accommodation_details': 'Room assignment details will be provided separately.' if decision == 'Approved' else None,
                'housing_fee': 'TBD',
                'payment_due_date': 'TBD',
                'move_in_date': move_in_date,
                'check_in_time': '2:00 PM - 6:00 PM',
                'check_in_location': 'Housing Office - Main Building',
                'reservation_expiry': (datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') + timedelta(days=7)).strftime('%Y-%m-%d') if decision == 'Approved' else None,
                'documentation_deadline': (datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') + timedelta(days=14)).strftime('%Y-%m-%d') if decision == 'Approved' else None,
                'orientation_date': 'TBD',
                'additional_notes': 'Please contact housing@university.edu if you have any questions.',
                'appeal_deadline': (datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') + timedelta(days=10)).strftime('%Y-%m-%d') if decision == 'Rejected' else None
            }

            # Determine email type
            if decision == 'Approved':
                email_sent = send_housing_email('approved', student_id, application_data, additional_vars)
                email_msg = "\n\nApproval email has been sent to the student." if email_sent else "\n\nNote: Email sending failed."
            elif decision == 'Rejected':
                email_sent = send_housing_email('rejected', student_id, application_data, additional_vars)
                email_msg = "\n\nRejection email has been sent to the student." if email_sent else "\n\nNote: Email sending failed."
            else:
                email_msg = ""

            # Log activity
            log_update('housing_application', f"Application {decision.lower()} by {reviewer_name} - ID: {application_id}")

            messagebox.showinfo("Success", f"Application has been {decision.lower()}{email_msg}")
            refresh_applications_list(gui_instance)
            process_window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process application: {str(e)}")
            import traceback
            traceback.print_exc()

    # Buttons
    buttons_frame = ttk.Frame(process_window)
    buttons_frame.pack(fill='x', padx=10, pady=10)

    ttk.Button(buttons_frame, text="Process", command=process_application).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Cancel", command=process_window.destroy).pack(side='left', padx=5)


def create_new_application_form(gui_instance, parent):
    """Create new application form"""
    # Student selection for staff
    if gui_instance.auth.check_permission('manage_accommodations'):
        student_frame = ttk.LabelFrame(parent, text="Select Student", padding="10")
        student_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))

        ttk.Label(student_frame, text="Student ID:").grid(row=0, column=0, sticky='w')
        gui_instance.student_id_entry = ttk.Entry(student_frame, width=20)
        gui_instance.student_id_entry.grid(row=0, column=1, padx=10)

        ttk.Button(student_frame, text="Search Student",
                  command=lambda: search_student(gui_instance)).grid(row=0, column=2, padx=10)

        gui_instance.student_info_label = ttk.Label(student_frame, text="")
        gui_instance.student_info_label.grid(row=1, column=0, columnspan=3, pady=10)

    # Application form
    form_frame = ttk.LabelFrame(parent, text="Application Details", padding="10")
    form_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Building preference
    ttk.Label(form_frame, text="Preferred Building:").grid(row=0, column=0, sticky='w', pady=5)
    gui_instance.building_combo = ttk.Combobox(form_frame, width=30)
    gui_instance.building_combo.grid(row=0, column=1, sticky='w', pady=5, padx=10)
    load_buildings_combo(gui_instance)

    # Room type
    ttk.Label(form_frame, text="Preferred Room Type:").grid(row=1, column=0, sticky='w', pady=5)
    gui_instance.room_type_combo = ttk.Combobox(form_frame,
                                      values=["Single", "Double", "Triple", "Suite", "Studio", "Apartment"])
    gui_instance.room_type_combo.grid(row=1, column=1, sticky='w', pady=5, padx=10)

    # Move-in date
    ttk.Label(form_frame, text="Requested Move-in Date:").grid(row=2, column=0, sticky='w', pady=5)
    gui_instance.move_in_entry = ttk.Entry(form_frame, width=30)
    gui_instance.move_in_entry.grid(row=2, column=1, sticky='w', pady=5, padx=10)
    gui_instance.move_in_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

    # Duration
    ttk.Label(form_frame, text="Duration (months):").grid(row=3, column=0, sticky='w', pady=5)
    gui_instance.duration_entry = ttk.Entry(form_frame, width=30)
    gui_instance.duration_entry.grid(row=3, column=1, sticky='w', pady=5, padx=10)
    gui_instance.duration_entry.insert(0, "9")

    # Special requirements
    ttk.Label(form_frame, text="Special Requirements:").grid(row=4, column=0, sticky='w', pady=5)
    gui_instance.requirements_text = tk.Text(form_frame, width=40, height=4)
    gui_instance.requirements_text.grid(row=4, column=1, sticky='w', pady=5, padx=10)

    # Submit button
    ttk.Button(form_frame, text="Submit Application",
              command=lambda: submit_application(gui_instance)).grid(row=5, column=0, pady=20)


def load_buildings_combo(gui_instance):
    """Load buildings into combobox"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        conn.close()

        building_values = ["No Preference"] + [f"{b[1]}" for b in buildings]
        gui_instance.building_combo['values'] = building_values
        gui_instance.building_combo.set("No Preference")

    except Exception as e:
        print(f"Error loading buildings: {str(e)}")


def search_student(gui_instance):
    """Search for student by ID"""
    student_id = gui_instance.student_id_entry.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT student_id, first_name, last_name, email_address
        FROM students WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()
        conn.close()

        if student:
            gui_instance.student_info_label.config(
                text=f"Student: {student[1]} {student[2]} ({student[0]}) - {student[3]}"
            )
        else:
            gui_instance.student_info_label.config(text="Student not found", foreground='red')

    except Exception as e:
        messagebox.showerror("Error", f"Failed to search student: {str(e)}")


def submit_application(gui_instance):
    """Submit new application"""
    try:
        # Get student ID
        if gui_instance.auth.check_permission('manage_accommodations'):
            student_id = gui_instance.student_id_entry.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Please enter a student ID")
                return
        else:
            # For students, get from auth
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (gui_instance.auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror("Error", "No student ID associated with your account")
                return
            student_id = result[0]

        # Validate inputs
        room_type = gui_instance.room_type_combo.get()
        move_in_date = gui_instance.move_in_entry.get()
        duration = gui_instance.duration_entry.get()

        if not all([room_type, move_in_date, duration]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            datetime.strptime(move_in_date, '%Y-%m-%d')
            duration_months = int(duration)
            if duration_months <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Please enter valid date (YYYY-MM-DD) and duration")
            return

        # Get building preference
        building_pref = gui_instance.building_combo.get()
        preferred_building_id = None
        if building_pref != "No Preference":
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT building_id FROM housing_buildings WHERE building_name = ?', (building_pref,))
            result = cursor.fetchone()
            if result:
                preferred_building_id = result[0]
            conn.close()

        # Create application
        conn = get_connection()
        cursor = conn.cursor()

        application_id = generate_id('APP')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        special_req = gui_instance.requirements_text.get('1.0', tk.END).strip() or None

        cursor.execute('''
        INSERT INTO housing_applications (
            application_id, student_id, application_date, preferred_building_id, preferred_room_type,
            requested_move_in_date, requested_duration_months, special_requirements, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            application_id, student_id, timestamp, preferred_building_id, room_type,
            move_in_date, duration_months, special_req, 'Pending', timestamp, timestamp
        ))

        conn.commit()
        conn.close()

        # Send receipt email to student
        application_data = {
            'application_id': application_id,
            'student_id': student_id,
            'preferred_room_type': room_type,
            'requested_move_in_date': move_in_date,
            'requested_duration_months': duration_months,
            'special_requirements': special_req,
            'status': 'Pending',
            'application_date': timestamp
        }
        send_housing_email('receipt', student_id, application_data)

        messagebox.showinfo("Success", f"Application submitted successfully!\nApplication ID: {application_id}\n\nA confirmation email has been sent to your registered email address.")

        # Log activity
        log_create('housing_application', application_id, f"Student {student_id} submitted housing application")

        # Immutable audit log for application creation
        if IMMUTABLE_AUDIT_AVAILABLE:
            admin_user_id, session_id = get_gui_context(gui_instance.auth)
            safe_log_security_event(
                action=AuditAction.RECORD_CREATE,
                user_id=admin_user_id,
                resource_type='housing_application',
                resource_id=application_id,
                session_id=session_id,
                details={
                    'student_id': student_id,
                    'room_type': room_type,
                    'move_in_date': move_in_date,
                    'duration_months': duration_months
                }
            )

        # Clear form
        if hasattr(gui_instance, 'student_id_entry'):
            gui_instance.student_id_entry.delete(0, tk.END)
            gui_instance.student_info_label.config(text="")
        gui_instance.building_combo.set("No Preference")
        gui_instance.room_type_combo.set("")
        gui_instance.move_in_entry.delete(0, tk.END)
        gui_instance.move_in_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        gui_instance.duration_entry.delete(0, tk.END)
        gui_instance.duration_entry.insert(0, "9")
        gui_instance.requirements_text.delete('1.0', tk.END)

        refresh_applications_list(gui_instance)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to submit application: {str(e)}")
