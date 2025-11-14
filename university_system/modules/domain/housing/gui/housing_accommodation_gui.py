import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
import os
import string
from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete,
    log_search, log_export, log_menu_navigation
)

# Import email service for sending confirmations
try:
    from university_system.infrastructure.email.email_service import send_email, send_email_as_system
    from university_system.infrastructure.email.template_utils import render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

# Import finance GUI for payment status integration
try:
    from university_system.modules.domain.finance.gui.finance_management_gui import FinanceManagementGUI
    FINANCE_GUI_AVAILABLE = True
except ImportError:
    FINANCE_GUI_AVAILABLE = False
    print("Warning: Finance GUI not available")

# Import original functions for backward compatibility
from university_system.modules.domain.housing.services.housing_accommodation import (
    init_housing_db, generate_id, set_auth,
    # Utility functions
    select_student as orig_select_student,
    # Building functions - add the missing create_ prefix
    create_building as orig_create_building,
    view_building as orig_view_building,
    update_building as orig_update_building,
    delete_building as orig_delete_building,
    create_rooms_for_building as orig_create_rooms_for_building,
    # Application functions
    create_application as orig_create_application,
    process_application as orig_process_application,
    view_application as orig_view_application,
    # Assignment functions
    view_assignment as orig_view_assignment,
    update_assignment_status as orig_update_assignment_status,
    # Maintenance functions
    create_maintenance_request as orig_create_maintenance_request,
    view_maintenance_requests as orig_view_maintenance_requests,
    update_maintenance_request as orig_update_maintenance_request,
    # Payment functions
    record_payment as orig_record_payment,
    view_payment_history as orig_view_payment_history,
    # Inventory and inspection functions
    manage_inventory as orig_manage_inventory,
    create_inspection as orig_create_inspection,
    view_inspections as orig_view_inspections,
    # Reports
    generate_occupancy_report as orig_generate_occupancy_report,
    generate_financial_report as orig_generate_financial_report,
    export_housing_data as orig_export_housing_data,
    search_housing_records as orig_search_housing_records,
    check_room_availability as orig_check_room_availability,
    maintenance_summary as orig_maintenance_summary,
    upcoming_moveouts_report as orig_upcoming_moveouts_report,
    # Menu functions (CLI-specific)
    display_housing_accommodation_menu as orig_display_housing_accommodation_menu,
    display_reports_menu as orig_display_reports_menu,
    display_building_menu as orig_display_building_menu,
    display_application_menu as orig_display_application_menu,
    display_assignment_menu as orig_display_assignment_menu,
    display_maintenance_menu as orig_display_maintenance_menu,
    display_payment_menu as orig_display_payment_menu,
    display_inspection_menu as orig_display_inspection_menu
)


def send_housing_email(email_type, student_id, application_data, additional_vars=None):
    """
    Send housing-related emails to students

    Args:
        email_type: Type of email ('receipt', 'approved', 'rejected')
        student_id: Student ID to send email to
        application_data: Dictionary containing application details
        additional_vars: Additional template variables (optional)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not EMAIL_SERVICE_AVAILABLE:
        print(f"Email service not available - cannot send {email_type} email to student {student_id}")
        return False

    try:
        # Get student email and name from database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT email_address, first_name, last_name
            FROM students
            WHERE student_id = ?
        ''', (student_id,))
        student_info = cursor.fetchone()
        conn.close()

        if not student_info or not student_info[0]:
            print(f"No email address found for student {student_id}")
            return False

        student_email = student_info[0]
        student_name = f"{student_info[1] or ''} {student_info[2] or ''}".strip() or "Student"

        # Map email types to template names
        template_map = {
            'receipt': 'accommodation_application_receipt',
            'approved': 'accommodation_approved',
            'rejected': 'accommodation_rejected'
        }

        template_name = template_map.get(email_type)
        if not template_name:
            print(f"Unknown email type: {email_type}")
            return False

        # Prepare template variables
        template_vars = {
            'student_name': student_name,
            'student_id': student_id,
            'accommodation_id': application_data.get('application_id', 'N/A'),
            'accommodation_type': application_data.get('preferred_room_type', 'N/A'),
            'description': application_data.get('special_requirements', 'No special requirements'),
            'start_date': application_data.get('requested_move_in_date', 'N/A'),
            'end_date': 'N/A',  # Calculate if duration available
            'status': application_data.get('status', 'N/A'),
            'submission_date': application_data.get('application_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        }

        # Calculate end date if duration available
        if application_data.get('requested_duration_months') and application_data.get('requested_move_in_date'):
            try:
                start_date = datetime.strptime(application_data['requested_move_in_date'], '%Y-%m-%d')
                duration = int(application_data['requested_duration_months'])
                end_date = start_date + timedelta(days=duration * 30)
                template_vars['end_date'] = end_date.strftime('%Y-%m-%d')
            except:
                pass

        # Add additional variables if provided
        if additional_vars:
            template_vars.update(additional_vars)

        # Render template
        subject, body = render_template(template_name, template_vars)

        # Send email (using correct parameter name: recipient_email not recipient)
        send_email(
            recipient_email=student_email,
            subject=subject,
            body=body
        )

        # Log the email activity
        log_create('housing_email', f"Sent {email_type} email ({template_name}) to student {student_id}")

        print(f"✓ {email_type.title()} email sent to {student_name} ({student_email})")
        return True

    except Exception as e:
        print(f"✗ Failed to send {email_type} email to student {student_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_maintenance_email(email_type, request_id, request_data, additional_vars=None):
    """
    Send maintenance request-related emails to students

    Args:
        email_type: Type of email ('created', 'completed', 'investigation')
        request_id: Request ID
        request_data: Dictionary containing request details
        additional_vars: Additional template variables (optional)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not EMAIL_SERVICE_AVAILABLE:
        print(f"Email service not available - cannot send {email_type} email for request {request_id}")
        return False

    try:
        # Get student email and name from database
        student_id = request_data.get('student_id')
        if not student_id:
            print(f"No student_id provided for request {request_id}")
            return False

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT email_address, first_name, last_name
            FROM students
            WHERE student_id = ?
        ''', (student_id,))
        student_info = cursor.fetchone()
        conn.close()

        if not student_info or not student_info[0]:
            print(f"No email address found for student {student_id}")
            return False

        student_email = student_info[0]
        student_name = f"{student_info[1] or ''} {student_info[2] or ''}".strip() or "Student"

        # Map email types to template names
        template_map = {
            'created': 'maintenance_request_created',
            'completed': 'maintenance_request_completed',
            'investigation': 'maintenance_request_investigation'
        }

        template_name = template_map.get(email_type)
        if not template_name:
            print(f"Unknown email type: {email_type}")
            return False

        # Prepare template variables with comprehensive defaults
        template_vars = {
            'student_name': student_name,
            'student_id': student_id,
            'request_id': request_id,
            'issue_type': request_data.get('issue_type', 'N/A'),
            'priority': request_data.get('priority', 'Medium'),
            'created_by': student_name,
            'created_date': request_data.get('request_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'location': request_data.get('location', 'N/A'),
            'description': request_data.get('description', 'No description provided'),
            'status': request_data.get('status', 'Open'),
            'assigned_to': request_data.get('assigned_to', 'Maintenance Team'),
            'scheduled_date': request_data.get('scheduled_date', 'To be determined'),
            'completion_date': request_data.get('completion_date', 'N/A'),
            'feedback': request_data.get('feedback', ''),
            'estimated_response': request_data.get('estimated_response', '2-3 business days'),
            'estimated_completion': request_data.get('estimated_completion', '5-7 business days'),

            # Additional variables for completed emails
            'completed_by': request_data.get('completed_by', 'Maintenance Team'),
            'resolution_time': request_data.get('resolution_time', 'N/A'),
            'work_performed': request_data.get('work_performed', request_data.get('feedback', 'Repair completed')),
            'resolution_notes': request_data.get('resolution_notes', ''),
            'materials_used': request_data.get('materials_used', 'Standard materials'),
            'follow_up_info': request_data.get('follow_up_info', 'None required'),
            'maintenance_tips': request_data.get('maintenance_tips', 'None'),
            'warranty_period': request_data.get('warranty_period', '30 days'),
            'warranty_coverage': request_data.get('warranty_coverage', 'Standard repair warranty'),
            'warranty_restrictions': request_data.get('warranty_restrictions', 'None'),

            # Additional variables for investigation emails
            'reviewed_by': request_data.get('reviewed_by', 'Maintenance Team'),
            'review_date': request_data.get('review_date', datetime.now().strftime('%Y-%m-%d')),
            'investigation_reason': request_data.get('investigation_reason', 'Further assessment required'),
            'root_cause_details': request_data.get('root_cause_details', 'To be determined during inspection'),
            'scope_details': request_data.get('scope_details', 'To be assessed'),
            'resource_requirements': request_data.get('resource_requirements', 'To be determined'),
            'inspection_date': request_data.get('inspection_date', 'To be scheduled'),
            'inspector_name': request_data.get('inspector_name', 'Maintenance Technician'),
            'inspection_scope': request_data.get('inspection_scope', 'Full diagnostic assessment'),
            'specialist_info': request_data.get('specialist_info', 'Will be determined if needed'),
            'parts_assessment': request_data.get('parts_assessment', 'To be evaluated'),
            'investigation_start': request_data.get('investigation_start', datetime.now().strftime('%Y-%m-%d')),
            'investigation_duration': request_data.get('investigation_duration', '2-3 business days'),
            'assessment_target': request_data.get('assessment_target', 'Within 1 week'),
            'inspection_appointment': request_data.get('inspection_appointment', 'To be scheduled'),
            'inspection_time': request_data.get('inspection_time', '30-60 minutes'),
            'special_requirements': request_data.get('special_requirements', 'None'),
            'access_instructions': request_data.get('access_instructions', 'Please ensure access to the affected area'),
            'action_item_1': request_data.get('action_item_1', 'Keep the area accessible'),
            'action_item_2': request_data.get('action_item_2', 'Respond to scheduling requests promptly'),
            'action_item_3': request_data.get('action_item_3', 'Report any changes in the issue'),
            'temporary_measures': request_data.get('temporary_measures', 'None currently in place'),
            'priority_update': request_data.get('priority_update', 'Priority remains unchanged'),
            'cost_information': request_data.get('cost_information', 'No charge for standard repairs'),
            'alternative_arrangements': request_data.get('alternative_arrangements', 'None needed at this time'),
            'additional_notes': request_data.get('additional_notes', ''),
            'next_update_date': request_data.get('next_update_date', 'When investigation is complete'),
            'contact_person': request_data.get('contact_person', 'Maintenance Office'),
            'contact_email': request_data.get('contact_email', 'maintenance@university.edu'),
            'contact_phone': request_data.get('contact_phone', '(555) 123-4567')
        }

        # Add any additional variables
        if additional_vars:
            template_vars.update(additional_vars)

        # Render template
        subject, body = render_template(template_name, template_vars)

        # Send email
        send_email(
            recipient_email=student_email,
            subject=subject,
            body=body
        )

        # Log the email activity
        log_create('maintenance_email', f"Sent {email_type} email ({template_name}) for request {request_id} to student {student_id}")

        print(f"✓ {email_type.title()} email sent to {student_name} ({student_email}) for request {request_id}")
        return True

    except Exception as e:
        print(f"✗ Failed to send {email_type} email for request {request_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


class HousingGUI:
    def __init__(self, auth_instance=None):
        self.auth = auth_instance
        self.root = tk.Tk()  # Remove the conditional reference to undefined 'root'
        self.root.title("Housing Accommodation Management System")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')
        
        # Set the auth instance for backward compatibility
        if auth_instance:
            set_auth(auth_instance)
        
        # Initialize database
        init_housing_db()
        
        # Create main interface
        self.create_main_interface()
        
    def create_main_interface(self):
        """Create the main GUI interface"""
        # Clear any existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Toolbar with quick actions
        toolbar = ttk.Frame(self.root, padding="6 6 6 6")
        toolbar.grid(row=0, column=0, sticky='ew')
        ttk.Button(toolbar, text="Return to Main Menu", command=self.return_to_main_menu).pack(side=tk.LEFT)

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Housing Accommodation Management", 
                               font=('Arial', 18, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Left sidebar with menu buttons
        sidebar_frame = ttk.Frame(main_frame)
        sidebar_frame.grid(row=1, column=0, sticky=(tk.W, tk.N, tk.S), padx=(0, 20))
        
        # Main content area
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)
        
        # Create menu buttons based on permissions
        self.create_menu_buttons(sidebar_frame)
        
        # Show default content
        self.show_dashboard()

    def return_to_main_menu(self):
        """Close the housing window and return control to the launcher."""
        try:
            self.root.destroy()
        except Exception:
            self.root.quit()
        
    def create_menu_buttons(self, parent):
        """Create menu buttons based on user permissions"""
        if not self.auth or not self.auth.current_user:
            ttk.Label(parent, text="Please log in to access housing features",
                     foreground='red').pack(pady=10)
            return
            
        current_role = self.auth.current_user.get('role', '')
        
        if self.auth.check_permission('manage_accommodations'):
            # Administrator menu
            ttk.Button(parent, text="Dashboard", width=20,
                      command=self.show_dashboard).pack(pady=2)
            ttk.Button(parent, text="Building Management", width=20,
                      command=self.show_building_management).pack(pady=2)
            ttk.Button(parent, text="Room Management", width=20,
                      command=self.show_room_management).pack(pady=2)
            ttk.Button(parent, text="Housing Applications", width=20,
                      command=self.show_applications).pack(pady=2)
            ttk.Button(parent, text="Housing Assignments", width=20,
                      command=self.show_assignments).pack(pady=2)
            ttk.Button(parent, text="Maintenance Requests", width=20,
                      command=self.show_maintenance).pack(pady=2)
            ttk.Button(parent, text="Payment Management", width=20,
                      command=self.show_payments).pack(pady=2)
            ttk.Button(parent, text="Room Inventory", width=20,
                      command=self.show_inventory).pack(pady=2)
            ttk.Button(parent, text="Room Inspections", width=20,
                      command=self.show_inspections).pack(pady=2)
            ttk.Button(parent, text="Reports & Analytics", width=20,
                      command=self.show_reports).pack(pady=2)
                      
        elif self.auth.check_permission('view_accommodations'):
            # View-only staff menu
            ttk.Button(parent, text="Dashboard", width=20,
                      command=self.show_dashboard).pack(pady=2)
            ttk.Button(parent, text="View Buildings", width=20,
                      command=self.show_building_view).pack(pady=2)
            ttk.Button(parent, text="View Applications", width=20,
                      command=self.show_applications_view).pack(pady=2)
            ttk.Button(parent, text="View Assignments", width=20,
                      command=self.show_assignments_view).pack(pady=2)
            ttk.Button(parent, text="View Maintenance", width=20,
                      command=self.show_maintenance_view).pack(pady=2)
            ttk.Button(parent, text="View Payments", width=20,
                      command=self.show_payments_view).pack(pady=2)
                      
        elif self.auth.check_permission('view_own_record'):
            # Student menu
            ttk.Button(parent, text="My Dashboard", width=20,
                      command=self.show_student_dashboard).pack(pady=2)
            ttk.Button(parent, text="My Application", width=20,
                      command=self.show_student_application).pack(pady=2)
            ttk.Button(parent, text="My Assignment", width=20,
                      command=self.show_student_assignment).pack(pady=2)
            ttk.Button(parent, text="Maintenance Requests", width=20,
                      command=self.show_student_maintenance).pack(pady=2)
        else:
            ttk.Label(parent, text="No permissions available",
                     foreground='red').pack(pady=10)
                     
        # Backward compatibility button
        ttk.Separator(parent).pack(fill='x', pady=10)
        ttk.Button(parent, text="Classic Interface", width=20,
                  command=self.launch_classic_interface).pack(pady=2)
    
    def clear_content(self):
        """Clear the content area"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def show_dashboard(self):
        """Show the main dashboard"""
        self.clear_content()
        
        # Dashboard title
        ttk.Label(self.content_frame, text="Housing Dashboard", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=(0, 20), sticky='w')
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
        
        # Overview tab
        overview_frame = ttk.Frame(notebook, padding="20")
        notebook.add(overview_frame, text="Overview")
        
        # Quick stats frame
        stats_frame = ttk.LabelFrame(overview_frame, text="Quick Statistics", padding="10")
        stats_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get statistics
            cursor.execute('SELECT COUNT(*) FROM housing_buildings')
            total_buildings = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM housing_rooms')
            total_rooms = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Occupied"')
            occupied_rooms = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM housing_assignments WHERE status = "Active"')
            active_assignments = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM housing_applications WHERE status = "Pending"')
            pending_applications = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status != "Complete"')
            open_maintenance = cursor.fetchone()[0]
            
            occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
            
            conn.close()
            
            # Display stats in grid
            stats = [
                ("Total Buildings", total_buildings),
                ("Total Rooms", total_rooms),
                ("Occupied Rooms", occupied_rooms),
                ("Occupancy Rate", f"{occupancy_rate:.1f}%"),
                ("Active Assignments", active_assignments),
                ("Pending Applications", pending_applications),
                ("Open Maintenance", open_maintenance)
            ]
            
            for i, (label, value) in enumerate(stats):
                row = i // 3
                col = i % 3
                stat_frame = ttk.Frame(stats_frame)
                stat_frame.grid(row=row, column=col, padx=20, pady=10)
                
                ttk.Label(stat_frame, text=str(value), font=('Arial', 20, 'bold')).pack()
                ttk.Label(stat_frame, text=label).pack()
                
        except Exception as e:
            ttk.Label(stats_frame, text=f"Error loading statistics: {str(e)}", 
                     foreground='red').pack()
        
        # Recent activity frame (placeholder)
        activity_frame = ttk.LabelFrame(overview_frame, text="Recent Activity", padding="10")
        activity_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(activity_frame, text="Recent activity will be displayed here").pack()

    def show_building_management(self):
        """Show building management interface"""
        self.clear_content()
        
        # Title
        ttk.Label(self.content_frame, text="Building Management", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=(0, 20), sticky='w')
        
        # Create notebook for different building operations
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # View Buildings tab
        view_frame = ttk.Frame(notebook, padding="10")
        notebook.add(view_frame, text="View Buildings")
        self.create_buildings_list(view_frame)
        
        # Add Building tab
        add_frame = ttk.Frame(notebook, padding="10")
        notebook.add(add_frame, text="Add Building")
        self.create_add_building_form(add_frame)
    
    def show_building_rooms_management(self, building_id, building_name):
        """Show room management for a specific building"""
        rooms_window = tk.Toplevel(self.root)
        rooms_window.title(f"Manage Rooms - {building_name}")
        rooms_window.geometry("800x600")
        rooms_window.transient(self.root)
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
                    room[6], f"${room[7]:.2f}", accessible
                ), tags=(room[0],))  # Store room_id in tags
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load rooms: {str(e)}")
        
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
                ttk.Label(form_frame, text="Monthly Rent ($):").grid(row=6, column=0, sticky="w", pady=5)
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
                            f"${rent_var.get():.2f}", "Yes" if accessible_var.get() else "No"
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
            ttk.Label(form_frame, text="Monthly Rent ($):").grid(row=5, column=0, sticky="w", pady=5)
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
                        f"${rent_var.get():.2f}", accessible
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
        
    def show_room_management(self):
        """Show room management interface"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Room Management", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create notebook
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True)
        
        # Add rooms tab
        add_rooms_frame = ttk.Frame(notebook, padding="10")
        notebook.add(add_rooms_frame, text="Add Rooms to Building")
        self.create_rooms_interface(add_rooms_frame)
        
        # View rooms tab
        view_rooms_frame = ttk.Frame(notebook, padding="10")
        notebook.add(view_rooms_frame, text="View All Rooms")
        self.create_rooms_list_view(view_rooms_frame)

    def create_rooms_interface(self, parent):
        """Create interface for adding rooms to a building"""
        # Building selection
        building_frame = ttk.LabelFrame(parent, text="Select Building", padding="10")
        building_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(building_frame, text="Building:").grid(row=0, column=0, sticky='w')
        self.rooms_building_combo = ttk.Combobox(building_frame, width=40)
        self.rooms_building_combo.grid(row=0, column=1, padx=10)
        
        # Load buildings
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            conn.close()
            
            building_values = [f"{b[1]}" for b in buildings]
            self.rooms_building_combo['values'] = building_values
            
        except Exception as e:
            print(f"Error loading buildings: {str(e)}")
        
        # Room details frame
        room_frame = ttk.LabelFrame(parent, text="Room Details", padding="10")
        room_frame.pack(fill='both', expand=True)
        
        # Floor and room count
        ttk.Label(room_frame, text="Floor Number:").grid(row=0, column=0, sticky='w', pady=5)
        self.floor_entry = ttk.Entry(room_frame, width=10)
        self.floor_entry.grid(row=0, column=1, padx=10, sticky='w')
        
        ttk.Label(room_frame, text="Room Number:").grid(row=1, column=0, sticky='w', pady=5)
        self.room_number_entry = ttk.Entry(room_frame, width=10)
        self.room_number_entry.grid(row=1, column=1, padx=10, sticky='w')
        
        ttk.Label(room_frame, text="Room Type:").grid(row=2, column=0, sticky='w', pady=5)
        self.room_type_combo = ttk.Combobox(room_frame, width=20,
                                           values=["Single", "Double", "Triple", "Suite", "Studio", "Apartment"])
        self.room_type_combo.grid(row=2, column=1, padx=10, sticky='w')
        
        ttk.Label(room_frame, text="Max Occupants:").grid(row=3, column=0, sticky='w', pady=5)
        self.max_occupants_entry = ttk.Entry(room_frame, width=10)
        self.max_occupants_entry.grid(row=3, column=1, padx=10, sticky='w')
        
        ttk.Label(room_frame, text="Monthly Rent:").grid(row=4, column=0, sticky='w', pady=5)
        self.rent_entry = ttk.Entry(room_frame, width=15)
        self.rent_entry.grid(row=4, column=1, padx=10, sticky='w')
        
        # Accessible checkbox
        self.is_accessible_var = tk.BooleanVar()
        ttk.Checkbutton(room_frame, text="Accessible Room", variable=self.is_accessible_var).grid(
            row=5, column=0, columnspan=2, sticky='w', pady=10)
        
        # Add room button
        ttk.Button(room_frame, text="Add Room", command=self.add_single_room).grid(
            row=6, column=0, pady=20)
        ttk.Button(room_frame, text="Batch Create Rooms", 
                  command=self.show_batch_room_creation).grid(row=6, column=1, pady=20, padx=10)

    def add_single_room(self):
        """Add a single room to the selected building"""
        try:
            building_name = self.rooms_building_combo.get()
            floor = self.floor_entry.get().strip()
            room_number = self.room_number_entry.get().strip()
            room_type = self.room_type_combo.get()
            max_occupants = self.max_occupants_entry.get().strip()
            rent = self.rent_entry.get().strip()
            
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
                0, 1 if self.is_accessible_var.get() else 0, 'Available', monthly_rent, 
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
            self.floor_entry.delete(0, tk.END)
            self.room_number_entry.delete(0, tk.END)
            self.room_type_combo.set("")
            self.max_occupants_entry.delete(0, tk.END)
            self.rent_entry.delete(0, tk.END)
            self.is_accessible_var.set(False)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add room: {str(e)}")

    def create_rooms_list_view(self, parent):
        """Create a view of all rooms with filtering"""
        # Filter frame
        filter_frame = ttk.LabelFrame(parent, text="Filter Rooms", padding="10")
        filter_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(filter_frame, text="Building:").grid(row=0, column=0, sticky='w')
        self.rooms_filter_building = ttk.Combobox(filter_frame, values=['All'])
        self.rooms_filter_building.set('All')
        self.rooms_filter_building.grid(row=0, column=1, padx=10)
        
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, sticky='w', padx=(20, 0))
        self.rooms_filter_status = ttk.Combobox(filter_frame, 
                                              values=['All', 'Available', 'Occupied', 'Maintenance', 'Reserved'])
        self.rooms_filter_status.set('All')
        self.rooms_filter_status.grid(row=0, column=3, padx=10)
        
        ttk.Button(filter_frame, text="Apply Filter", 
                  command=self.refresh_rooms_list).grid(row=0, column=4, padx=10)
        
        # Load building options
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            conn.close()
            
            building_values = ['All'] + [b[0] for b in buildings]
            self.rooms_filter_building['values'] = building_values
            
        except Exception as e:
            print(f"Error loading buildings: {str(e)}")
        
        # Rooms list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True)
        
        columns = ('Room ID', 'Building', 'Room #', 'Floor', 'Type', 'Max Occ.', 'Current Occ.', 'Status', 'Rent', 'Accessible')
        self.all_rooms_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        for col in columns:
            self.all_rooms_tree.heading(col, text=col)
            if col in ['Max Occ.', 'Current Occ.', 'Floor']:
                self.all_rooms_tree.column(col, width=80)
            elif col == 'Rent':
                self.all_rooms_tree.column(col, width=80, anchor='e')
            else:
                self.all_rooms_tree.column(col, width=100)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.all_rooms_tree.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=self.all_rooms_tree.xview)
        self.all_rooms_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.all_rooms_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        
        # Load rooms
        self.refresh_rooms_list()

    def refresh_rooms_list(self):
        """Refresh the rooms list with filters"""
        for item in self.all_rooms_tree.get_children():
            self.all_rooms_tree.delete(item)
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Build query based on filters
            where_clauses = []
            params = []
            
            building_filter = self.rooms_filter_building.get()
            if building_filter != 'All':
                where_clauses.append("b.building_name = ?")
                params.append(building_filter)
            
            status_filter = self.rooms_filter_status.get()
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
                self.all_rooms_tree.insert('', 'end', values=(
                    room[0], room[1], room[2], room[3], room[4], room[5], 
                    room[6], room[7], f"${room[8]:.2f}", accessible
                ))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load rooms: {str(e)}")

    def show_batch_room_creation(self):
        """Show interface for batch room creation"""
        batch_window = tk.Toplevel(self.root)
        batch_window.title("Batch Room Creation")
        batch_window.geometry("600x500")
        batch_window.transient(self.root)
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
    
    def create_buildings_list(self, parent):
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
        self.buildings_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                          yscrollcommand=v_scrollbar.set,
                                          xscrollcommand=h_scrollbar.set)
        
        # Configure scrollbars
        v_scrollbar.config(command=self.buildings_tree.yview)
        h_scrollbar.config(command=self.buildings_tree.xview)
        
        # Configure columns
        for col in columns:
            self.buildings_tree.heading(col, text=col)
            self.buildings_tree.column(col, width=100)
        
        self.buildings_tree.pack(side='left', fill='both', expand=True)
        
        # Buttons frame
        buttons_frame = ttk.Frame(parent)
        buttons_frame.grid(row=1, column=0, columnspan=2, pady=20)
        
        ttk.Button(buttons_frame, text="Refresh", 
                  command=self.refresh_buildings_list).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Edit Selected", 
                  command=self.edit_selected_building).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Delete Selected", 
                  command=self.delete_selected_building).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Manage Rooms", 
                  command=self.manage_selected_building_rooms).pack(side='left', padx=5)

        # Load buildings
        self.refresh_buildings_list()

    def manage_selected_building_rooms(self):
        """Manage rooms for selected building"""
        selected = self.buildings_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a building to manage rooms")
            return
        
        building_data = self.buildings_tree.item(selected[0])['values']
        building_id = building_data[0]
        building_name = building_data[1]
        
        self.show_building_rooms_management(building_id, building_name)
    
    def refresh_buildings_list(self):
        """Refresh the buildings list"""
        # Clear existing items
        for item in self.buildings_tree.get_children():
            self.buildings_tree.delete(item)
        
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
                self.buildings_tree.insert('', 'end', values=(
                    building[0], building[1], building[2], 
                    building[3], building[4], occupancy
                ))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load buildings: {str(e)}")
    
    def create_add_building_form(self, parent):
        """Create form to add new building"""
        # Form fields
        fields = [
            ("Building Name:", "building_name"),
            ("Address:", "address"),
            ("Campus Location:", "campus_location"),
            ("Total Rooms:", "total_rooms"),
            ("Available Rooms:", "available_rooms")
        ]
        
        self.building_entries = {}
        
        for i, (label, field) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=i, column=0, sticky='w', pady=5)
            entry = ttk.Entry(parent, width=40)
            entry.grid(row=i, column=1, sticky='w', pady=5, padx=10)
            self.building_entries[field] = entry
        
        # Checkboxes for amenities
        amenities_frame = ttk.LabelFrame(parent, text="Building Amenities", padding="10")
        amenities_frame.grid(row=len(fields), column=0, columnspan=2, pady=20, sticky='w')
        
        self.building_amenities = {}
        amenities = [
            ("has_elevator", "Has Elevator"),
            ("has_accessible_rooms", "Has Accessible Rooms"),
            ("has_kitchen", "Has Kitchen Facilities"),
            ("has_laundry", "Has Laundry Facilities")
        ]
        
        for i, (field, label) in enumerate(amenities):
            var = tk.BooleanVar()
            self.building_amenities[field] = var
            ttk.Checkbutton(amenities_frame, text=label, variable=var).grid(
                row=i//2, column=i%2, sticky='w', padx=10, pady=5
            )
        
        # Submit button
        ttk.Button(parent, text="Add Building", 
                  command=self.add_building).grid(row=len(fields)+2, column=0, pady=20)
    
    def add_building(self):
        """Add a new building"""
        try:
            # Validate inputs
            building_name = self.building_entries['building_name'].get().strip()
            address = self.building_entries['address'].get().strip()
            campus_location = self.building_entries['campus_location'].get().strip()
            
            if not all([building_name, address, campus_location]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return
            
            try:
                total_rooms = int(self.building_entries['total_rooms'].get())
                available_rooms = int(self.building_entries['available_rooms'].get())
                
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
                1 if self.building_amenities['has_elevator'].get() else 0,
                1 if self.building_amenities['has_accessible_rooms'].get() else 0,
                1 if self.building_amenities['has_kitchen'].get() else 0,
                1 if self.building_amenities['has_laundry'].get() else 0,
                timestamp, timestamp
            ))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Building '{building_name}' created successfully!")
            
            # Clear form
            for entry in self.building_entries.values():
                entry.delete(0, tk.END)
            for var in self.building_amenities.values():
                var.set(False)
            
            # Refresh buildings list if it exists
            if hasattr(self, 'buildings_tree'):
                self.refresh_buildings_list()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create building: {str(e)}")
    
    def edit_selected_building(self):
        """Edit the selected building"""
        selected = self.buildings_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a building to edit")
            return
        
        building_id = self.buildings_tree.item(selected[0])['values'][0]
        self.show_edit_building_dialog(building_id)

    def show_edit_building_dialog(self, building_id):
        """Show dialog to edit building"""
        # Create new window
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Building")
        edit_window.geometry("500x400")
        edit_window.transient(self.root)
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
                    self.refresh_buildings_list()
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

    def show_maintenance(self):
        """Show maintenance requests interface"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Maintenance Requests", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create notebook
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True)
        
        # Requests list tab
        list_frame = ttk.Frame(notebook, padding="10")
        notebook.add(list_frame, text="View Requests")
        self.create_maintenance_list(list_frame)
        
        # New request tab
        new_frame = ttk.Frame(notebook, padding="10")
        notebook.add(new_frame, text="New Request")
        self.create_maintenance_form(new_frame)
    
    def create_maintenance_list(self, parent):
        """Create maintenance requests list"""
        # Filter frame
        filter_frame = ttk.LabelFrame(parent, text="Filter Requests", padding="10")
        filter_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, sticky='w')
        self.maint_status_filter = ttk.Combobox(filter_frame, 
                                              values=['All', 'Open', 'In Progress', 'Pending Parts', 'Complete'])
        self.maint_status_filter.set('Open')
        self.maint_status_filter.grid(row=0, column=1, padx=10)
        
        ttk.Label(filter_frame, text="Priority:").grid(row=0, column=2, sticky='w', padx=(20, 0))
        self.maint_priority_filter = ttk.Combobox(filter_frame, 
                                                values=['All', 'Emergency', 'High', 'Medium', 'Low'])
        self.maint_priority_filter.set('All')
        self.maint_priority_filter.grid(row=0, column=3, padx=10)
        
        ttk.Button(filter_frame, text="Apply Filter", 
                  command=self.refresh_maintenance_list).grid(row=0, column=4, padx=10)
        
        # Requests list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True)
        
        columns = ('Request ID', 'Date', 'Student', 'Room', 'Issue Type', 'Priority', 'Status')
        self.maintenance_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        for col in columns:
            self.maintenance_tree.heading(col, text=col)
            self.maintenance_tree.column(col, width=120)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.maintenance_tree.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=self.maintenance_tree.xview)
        self.maintenance_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.maintenance_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        
        # Buttons
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill='x', pady=20)
        
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_maintenance_list).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="View Details", command=self.view_maintenance_details).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Update Request", command=self.update_maintenance_request).pack(side='left', padx=5)
        
        # Load requests
        self.refresh_maintenance_list()
    
    def refresh_maintenance_list(self):
        """Refresh maintenance requests list"""
        for item in self.maintenance_tree.get_children():
            self.maintenance_tree.delete(item)
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Build query based on filters - add safety checks
            where_clauses = []
            params = []
            
            status_filter = getattr(self, 'maint_status_filter', None)
            if status_filter and status_filter.get() != 'All':
                where_clauses.append("m.status = ?")
                params.append(status_filter.get())
            
            priority_filter = getattr(self, 'maint_priority_filter', None) 
            if priority_filter and priority_filter.get() != 'All':
                where_clauses.append("m.priority = ?")
                params.append(priority_filter.get())
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                
            cursor.execute(f'''
            SELECT m.request_id, m.request_date, s.first_name, s.last_name,
                   r.room_number, b.building_name, m.issue_type, m.priority, m.status
            FROM housing_maintenance_requests m
            JOIN students s ON m.student_id = s.student_id
            JOIN housing_rooms r ON m.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE {where_clause}
            ORDER BY 
                CASE m.priority
                    WHEN 'Emergency' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    WHEN 'Low' THEN 4
                    ELSE 5
                END,
                m.request_date DESC
            ''', params)
            
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
                
                self.maintenance_tree.insert('', 'end', values=(
                    req[0], req[1], student_name, room_info, req[6], req[7], req[8]
                ), tags=tags)
            
            # Configure tags for colors
            self.maintenance_tree.tag_configure('emergency', background='#ffcccc')
            self.maintenance_tree.tag_configure('high', background='#ffe6cc')
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load maintenance requests: {str(e)}")
    
    def view_maintenance_details(self):
        """View maintenance request details"""
        selected = self.maintenance_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a request to view")
            return
        
        request_id = self.maintenance_tree.item(selected[0])['values'][0]
        self.show_maintenance_details_dialog(request_id)
    
    def show_maintenance_details_dialog(self, request_id):
        """Show maintenance request details dialog"""
        details_window = tk.Toplevel(self.root)
        details_window.title("Maintenance Request Details")
        details_window.geometry("600x500")
        details_window.transient(self.root)
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
    
    def update_maintenance_request(self):
        """Update maintenance request"""
        selected = self.maintenance_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a request to update")
            return
        
        request_id = self.maintenance_tree.item(selected[0])['values'][0]
        self.show_update_maintenance_dialog(request_id)
    
    def show_update_maintenance_dialog(self, request_id):
        """Show maintenance update dialog"""
        update_window = tk.Toplevel(self.root)
        update_window.title("Update Maintenance Request")
        update_window.geometry("500x400")
        update_window.transient(self.root)
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
                self.refresh_maintenance_list()
                update_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update request: {str(e)}")
        
        # Buttons
        buttons_frame = ttk.Frame(update_window)
        buttons_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Save", command=save_update).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=update_window.destroy).pack(side='left', padx=5)
    
    def create_maintenance_form(self, parent):
        """Create new maintenance request form"""
        # Room selection
        room_frame = ttk.LabelFrame(parent, text="Room Selection", padding="10")
        room_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(room_frame, text="Building:").grid(row=0, column=0, sticky='w')
        self.maint_building_combo = ttk.Combobox(room_frame, width=30)
        self.maint_building_combo.grid(row=0, column=1, padx=10)
        self.maint_building_combo.bind('<<ComboboxSelected>>', self.load_rooms_for_maintenance)
        
        ttk.Label(room_frame, text="Room:").grid(row=1, column=0, sticky='w')
        self.maint_room_combo = ttk.Combobox(room_frame, width=30)
        self.maint_room_combo.grid(row=1, column=1, padx=10)
        
        # Load buildings
        self.load_buildings_for_maintenance()
        
        # Request details
        details_frame = ttk.LabelFrame(parent, text="Request Details", padding="10")
        details_frame.pack(fill='both', expand=True, pady=(0, 20))
        
        ttk.Label(details_frame, text="Issue Type:").grid(row=0, column=0, sticky='w')
        self.issue_type_combo = ttk.Combobox(details_frame, width=30,
                                           values=["Plumbing", "Electrical", "HVAC", "Appliance", 
                                                  "Furniture", "Pest Control", "Structural", 
                                                  "Lock/Key", "Cleaning", "Other"])
        self.issue_type_combo.grid(row=0, column=1, padx=10)
        
        ttk.Label(details_frame, text="Priority:").grid(row=1, column=0, sticky='w')
        self.priority_combo = ttk.Combobox(details_frame, width=30,
                                         values=["Low", "Medium", "High", "Emergency"])
        self.priority_combo.set("Medium")
        self.priority_combo.grid(row=1, column=1, padx=10)
        
        ttk.Label(details_frame, text="Description:").grid(row=2, column=0, sticky='nw')
        self.description_text = tk.Text(details_frame, width=40, height=6)
        self.description_text.grid(row=2, column=1, padx=10, pady=10)
        
        # Submit button
        ttk.Button(details_frame, text="Submit Request", 
                  command=self.submit_maintenance_request).grid(row=3, column=0, pady=20)
    
    def load_buildings_for_maintenance(self):
        """Load buildings for maintenance form"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            conn.close()
            
            building_values = [f"{b[1]}" for b in buildings]
            self.maint_building_combo['values'] = building_values
            
        except Exception as e:
            print(f"Error loading buildings: {str(e)}")
    
    def load_rooms_for_maintenance(self, event=None):
        """Load rooms for selected building"""
        building_name = self.maint_building_combo.get()
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
            self.maint_room_combo['values'] = room_values
            self.maint_room_combo.set("")
            
        except Exception as e:
            print(f"Error loading rooms: {str(e)}")
    
    def submit_maintenance_request(self):
        """Submit maintenance request"""
        try:
            building_name = self.maint_building_combo.get()
            room_info = self.maint_room_combo.get()
            issue_type = self.issue_type_combo.get()
            priority = self.priority_combo.get()
            description = self.description_text.get('1.0', tk.END).strip()
            
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
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                # Check if user is a student
                cursor.execute('SELECT student_id FROM students WHERE email_address = ? OR student_id = ?',
                             (self.auth.current_user.get('email', ''), self.auth.current_user.get('username', '')))
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
                                                           parent=self.root)
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
            self.maint_building_combo.set("")
            self.maint_room_combo.set("")
            self.issue_type_combo.set("")
            self.priority_combo.set("Medium")
            self.description_text.delete('1.0', tk.END)
            
            self.refresh_maintenance_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit request: {str(e)}")
    
    def show_payments(self):
        """Show payments interface"""
        self.clear_content()

        # Header with title and finance button
        header_frame = ttk.Frame(self.content_frame)
        header_frame.pack(fill='x', pady=(0, 20))

        ttk.Label(header_frame, text="Payment Management",
                 font=('Arial', 16, 'bold')).pack(side='left', padx=(0, 20))

        # Button to open Finance Management GUI
        ttk.Button(header_frame, text="📊 Open Finance Management",
                  command=self.open_finance_gui).pack(side='left')

        # Create notebook
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True)

        # Payment history tab
        history_frame = ttk.Frame(notebook, padding="10")
        notebook.add(history_frame, text="Payment History")
        self.create_payment_history(history_frame)

        # Record payment tab
        record_frame = ttk.Frame(notebook, padding="10")
        notebook.add(record_frame, text="Record Payment")
        self.create_payment_form(record_frame)

    def open_finance_gui(self):
        """Open Finance Management GUI in a new window"""
        if not FINANCE_GUI_AVAILABLE:
            messagebox.showerror(
                "Finance GUI Not Available",
                "The Finance Management system is not available.\n\n"
                "Please ensure the finance module is properly installed."
            )
            return

        try:
            # Create new top-level window for finance GUI
            finance_window = tk.Toplevel(self.root)
            finance_window.title("Finance Management System")
            finance_window.geometry("1400x900")
            finance_window.transient(self.root)

            # Ensure parent window regains focus when finance window closes
            def on_finance_close():
                """Handle finance window closing"""
                try:
                    self.root.lift()
                    self.root.focus_force()
                    finance_window.destroy()
                except:
                    pass

            finance_window.protocol("WM_DELETE_WINDOW", on_finance_close)

            # Initialize Finance Management GUI with the new window and current auth
            finance_gui = FinanceManagementGUI(finance_window, self.auth)

            # Show the finance management interface and navigate to housing tab
            finance_gui.show_finance_management(initial_tab='housing')

            # Log the action
            log_menu_navigation(description='Opened finance management from housing payment management')

            print("✓ Finance Management GUI opened successfully")

        except Exception as e:
            messagebox.showerror(
                "Error Opening Finance GUI",
                f"Failed to open Finance Management system:\n\n{str(e)}"
            )
            print(f"✗ Failed to open Finance GUI: {e}")
            import traceback
            traceback.print_exc()

    def create_payment_history(self, parent):
        """Create payment history view"""
        # Filter frame
        filter_frame = ttk.LabelFrame(parent, text="Filter Payments", padding="10")
        filter_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(filter_frame, text="Student ID:").grid(row=0, column=0, sticky='w')
        self.payment_student_filter = ttk.Entry(filter_frame, width=20)
        self.payment_student_filter.grid(row=0, column=1, padx=10)
        
        ttk.Button(filter_frame, text="Filter", 
                  command=self.refresh_payment_history).grid(row=0, column=2, padx=10)
        ttk.Button(filter_frame, text="Show All", 
                  command=self.show_all_payments).grid(row=0, column=3, padx=5)
        
        # Payments list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True)
        
        columns = ('Payment ID', 'Student', 'Amount', 'Date', 'Method', 'Period', 'Status')
        self.payments_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        for col in columns:
            self.payments_tree.heading(col, text=col)
            if col == 'Amount':
                self.payments_tree.column(col, width=100, anchor='e')
            else:
                self.payments_tree.column(col, width=120)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.payments_tree.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=self.payments_tree.xview)
        self.payments_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.payments_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        
        # Load recent payments
        self.show_all_payments()
    
    def refresh_payment_history(self):
        """Refresh payment history with filter"""
        student_filter = self.payment_student_filter.get().strip()
        
        for item in self.payments_tree.get_children():
            self.payments_tree.delete(item)
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            if student_filter:
                cursor.execute('''
                SELECT p.payment_id, s.first_name, s.last_name, p.amount, p.payment_date,
                       p.payment_method, p.payment_period_start, p.payment_period_end, p.status
                FROM housing_payments p
                JOIN students s ON p.student_id = s.student_id
                WHERE p.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
                ORDER BY p.payment_date DESC
                LIMIT 100
                ''', (f'%{student_filter}%', f'%{student_filter}%', f'%{student_filter}%'))
            else:
                cursor.execute('''
                SELECT p.payment_id, s.first_name, s.last_name, p.amount, p.payment_date,
                       p.payment_method, p.payment_period_start, p.payment_period_end, p.status
                FROM housing_payments p
                JOIN students s ON p.student_id = s.student_id
                ORDER BY p.payment_date DESC
                LIMIT 50
                ''')
            
            payments = cursor.fetchall()
            
            for payment in payments:
                student_name = f"{payment[1]} {payment[2]}"
                period = f"{payment[6]} to {payment[7]}"
                
                self.payments_tree.insert('', 'end', values=(
                    payment[0], student_name, f"${payment[3]:.2f}", payment[4],
                    payment[5], period, payment[8]
                ))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load payments: {str(e)}")
    
    def show_all_payments(self):
        """Show all recent payments"""
        self.payment_student_filter.delete(0, tk.END)
        self.refresh_payment_history()
    
    def create_payment_form(self, parent):
        """Create payment recording form"""
        # Assignment selection
        assign_frame = ttk.LabelFrame(parent, text="Select Assignment", padding="10")
        assign_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(assign_frame, text="Active Assignment:").grid(row=0, column=0, sticky='w')
        self.assignment_combo = ttk.Combobox(assign_frame, width=50)
        self.assignment_combo.grid(row=0, column=1, padx=10)
        
        ttk.Button(assign_frame, text="Refresh", 
                  command=self.load_active_assignments).grid(row=0, column=2, padx=10)
        
        self.load_active_assignments()
        
        # Payment details
        payment_frame = ttk.LabelFrame(parent, text="Payment Details", padding="10")
        payment_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(payment_frame, text="Amount:").grid(row=0, column=0, sticky='w')
        self.payment_amount_entry = ttk.Entry(payment_frame, width=20)
        self.payment_amount_entry.grid(row=0, column=1, padx=10)
        
        ttk.Label(payment_frame, text="Payment Method:").grid(row=1, column=0, sticky='w')
        self.payment_method_combo = ttk.Combobox(payment_frame, width=20,
                                               values=["Credit Card", "Bank Transfer", "Cash", "Check", "Other"])
        self.payment_method_combo.grid(row=1, column=1, padx=10)
        
        ttk.Label(payment_frame, text="Transaction Reference:").grid(row=2, column=0, sticky='w')
        self.transaction_ref_entry = ttk.Entry(payment_frame, width=30)
        self.transaction_ref_entry.grid(row=2, column=1, padx=10)
        
        # Payment period
        period_frame = ttk.LabelFrame(parent, text="Payment Period", padding="10")
        period_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(period_frame, text="Period Start:").grid(row=0, column=0, sticky='w')
        self.period_start_entry = ttk.Entry(period_frame, width=20)
        self.period_start_entry.grid(row=0, column=1, padx=10)
        self.period_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        ttk.Label(period_frame, text="Period End:").grid(row=0, column=2, sticky='w', padx=(20, 0))
        self.period_end_entry = ttk.Entry(period_frame, width=20)
        self.period_end_entry.grid(row=0, column=3, padx=10)
        # Set default end date to end of month
        next_month = datetime.now().replace(day=28) + timedelta(days=4)
        end_of_month = next_month - timedelta(days=next_month.day)
        self.period_end_entry.insert(0, end_of_month.strftime('%Y-%m-%d'))
        
        # Buttons frame
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(pady=20)

        ttk.Button(buttons_frame, text="Record Payment",
                  command=self.record_payment).pack(side='left', padx=5)

        if FINANCE_GUI_AVAILABLE:
            ttk.Button(buttons_frame, text="View in Finance System",
                      command=self.open_finance_gui).pack(side='left', padx=5)

    def delete_selected_building(self):
        """Delete the selected building"""
        selected = self.buildings_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a building to delete")
            return
        
        building_data = self.buildings_tree.item(selected[0])['values']
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
                self.refresh_buildings_list()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete building: {str(e)}")
    
    def show_applications(self):
        """Show housing applications interface"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Housing Applications", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=(0, 20), sticky='w')
        
        # Create notebook
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Applications list tab
        list_frame = ttk.Frame(notebook, padding="10")
        notebook.add(list_frame, text="Applications List")
        self.create_applications_list(list_frame)
        
        # New application tab
        new_frame = ttk.Frame(notebook, padding="10")
        notebook.add(new_frame, text="New Application")
        self.create_new_application_form(new_frame)
    
    def create_applications_list(self, parent):
        """Create applications list view"""
        # Filter frame
        filter_frame = ttk.LabelFrame(parent, text="Filter Applications", padding="10")
        filter_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, sticky='w')
        self.app_status_filter = ttk.Combobox(filter_frame, 
                                            values=['All', 'Pending', 'Approved', 'Rejected', 'Waiting List'])
        self.app_status_filter.set('All')
        self.app_status_filter.grid(row=0, column=1, padx=10)
        
        ttk.Button(filter_frame, text="Apply Filter", 
                  command=self.refresh_applications_list).grid(row=0, column=2, padx=10)
        
        # Applications treeview
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        columns = ('ID', 'Student', 'Date', 'Room Type', 'Status', 'Review Date')
        self.applications_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        
        for col in columns:
            self.applications_tree.heading(col, text=col)
            self.applications_tree.column(col, width=120)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.applications_tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.applications_tree.xview)
        self.applications_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.applications_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Buttons
        buttons_frame = ttk.Frame(parent)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_applications_list).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="View Details", command=self.view_application_details).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Process Application", command=self.process_selected_application).pack(side='left', padx=5)
        
        # Load applications
        self.refresh_applications_list()
    
    def refresh_applications_list(self):
        """Refresh the applications list"""
        for item in self.applications_tree.get_children():
            self.applications_tree.delete(item)
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            status_filter = self.app_status_filter.get()
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
                self.applications_tree.insert('', 'end', values=(
                    app[0], student_name, app[3], app[4], app[5], app[6] or ''
                ))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load applications: {str(e)}")
    
    def view_application_details(self):
        """View details of selected application"""
        selected = self.applications_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an application to view")
            return
        
        application_id = self.applications_tree.item(selected[0])['values'][0]
        self.show_application_details_dialog(application_id)
    
    def show_application_details_dialog(self, application_id):
        """Show application details dialog"""
        details_window = tk.Toplevel(self.root)
        details_window.title("Application Details")
        details_window.geometry("600x500")
        details_window.transient(self.root)
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
    
    def process_selected_application(self):
        """Process the selected application"""
        selected = self.applications_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an application to process")
            return
        
        application_id = self.applications_tree.item(selected[0])['values'][0]
        self.show_process_application_dialog(application_id)
    
    def show_process_application_dialog(self, application_id):
        """Show dialog to process application"""
        process_window = tk.Toplevel(self.root)
        process_window.title("Process Application")
        process_window.geometry("500x400")
        process_window.transient(self.root)
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
                ''', (decision, notes, self.auth.current_user['username'], timestamp, timestamp, application_id))

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
                reviewer_name = self.auth.current_user.get('username', 'Housing Administration')
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
                self.refresh_applications_list()
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
    
    def create_new_application_form(self, parent):
        """Create new application form"""
        # Student selection for staff
        if self.auth.check_permission('manage_accommodations'):
            student_frame = ttk.LabelFrame(parent, text="Select Student", padding="10")
            student_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
            
            ttk.Label(student_frame, text="Student ID:").grid(row=0, column=0, sticky='w')
            self.student_id_entry = ttk.Entry(student_frame, width=20)
            self.student_id_entry.grid(row=0, column=1, padx=10)
            
            ttk.Button(student_frame, text="Search Student", 
                      command=self.search_student).grid(row=0, column=2, padx=10)
            
            self.student_info_label = ttk.Label(student_frame, text="")
            self.student_info_label.grid(row=1, column=0, columnspan=3, pady=10)
        
        # Application form
        form_frame = ttk.LabelFrame(parent, text="Application Details", padding="10")
        form_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Building preference
        ttk.Label(form_frame, text="Preferred Building:").grid(row=0, column=0, sticky='w', pady=5)
        self.building_combo = ttk.Combobox(form_frame, width=30)
        self.building_combo.grid(row=0, column=1, sticky='w', pady=5, padx=10)
        self.load_buildings_combo()
        
        # Room type
        ttk.Label(form_frame, text="Preferred Room Type:").grid(row=1, column=0, sticky='w', pady=5)
        self.room_type_combo = ttk.Combobox(form_frame, 
                                          values=["Single", "Double", "Triple", "Suite", "Studio", "Apartment"])
        self.room_type_combo.grid(row=1, column=1, sticky='w', pady=5, padx=10)
        
        # Move-in date
        ttk.Label(form_frame, text="Requested Move-in Date:").grid(row=2, column=0, sticky='w', pady=5)
        self.move_in_entry = ttk.Entry(form_frame, width=30)
        self.move_in_entry.grid(row=2, column=1, sticky='w', pady=5, padx=10)
        self.move_in_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        # Duration
        ttk.Label(form_frame, text="Duration (months):").grid(row=3, column=0, sticky='w', pady=5)
        self.duration_entry = ttk.Entry(form_frame, width=30)
        self.duration_entry.grid(row=3, column=1, sticky='w', pady=5, padx=10)
        self.duration_entry.insert(0, "9")
        
        # Special requirements
        ttk.Label(form_frame, text="Special Requirements:").grid(row=4, column=0, sticky='w', pady=5)
        self.requirements_text = tk.Text(form_frame, width=40, height=4)
        self.requirements_text.grid(row=4, column=1, sticky='w', pady=5, padx=10)
        
        # Submit button
        ttk.Button(form_frame, text="Submit Application", 
                  command=self.submit_application).grid(row=5, column=0, pady=20)
    
    def load_buildings_combo(self):
        """Load buildings into combobox"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            conn.close()
            
            building_values = ["No Preference"] + [f"{b[1]}" for b in buildings]
            self.building_combo['values'] = building_values
            self.building_combo.set("No Preference")
            
        except Exception as e:
            print(f"Error loading buildings: {str(e)}")
    
    def search_student(self):
        """Search for student by ID"""
        student_id = self.student_id_entry.get().strip()
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
                self.student_info_label.config(
                    text=f"Student: {student[1]} {student[2]} ({student[0]}) - {student[3]}"
                )
            else:
                self.student_info_label.config(text="Student not found", foreground='red')
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to search student: {str(e)}")
    
    def submit_application(self):
        """Submit new application"""
        try:
            # Get student ID
            if self.auth.check_permission('manage_accommodations'):
                student_id = self.student_id_entry.get().strip()
                if not student_id:
                    messagebox.showerror("Error", "Please enter a student ID")
                    return
            else:
                # For students, get from auth
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                result = cursor.fetchone()
                conn.close()
                
                if not result:
                    messagebox.showerror("Error", "No student ID associated with your account")
                    return
                student_id = result[0]
            
            # Validate inputs
            room_type = self.room_type_combo.get()
            move_in_date = self.move_in_entry.get()
            duration = self.duration_entry.get()
            
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
            building_pref = self.building_combo.get()
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
            special_req = self.requirements_text.get('1.0', tk.END).strip() or None
            
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

            # Clear form
            if hasattr(self, 'student_id_entry'):
                self.student_id_entry.delete(0, tk.END)
                self.student_info_label.config(text="")
            self.building_combo.set("No Preference")
            self.room_type_combo.set("")
            self.move_in_entry.delete(0, tk.END)
            self.move_in_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            self.duration_entry.delete(0, tk.END)
            self.duration_entry.insert(0, "9")
            self.requirements_text.delete('1.0', tk.END)
            
            self.refresh_applications_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit application: {str(e)}")
    
    def show_assignments(self):
        """Show housing assignments interface"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Housing Assignments", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Filter and list frame
        main_frame = ttk.Frame(self.content_frame)
        main_frame.pack(fill='both', expand=True)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text="Filter Assignments", padding="10")
        filter_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, sticky='w')
        self.assign_status_filter = ttk.Combobox(filter_frame, 
                                               values=['All', 'Active', 'Pending', 'Terminated', 'Expired'])
        self.assign_status_filter.set('All')
        self.assign_status_filter.grid(row=0, column=1, padx=10)
        
        ttk.Button(filter_frame, text="Apply Filter", 
                  command=self.refresh_assignments_list).grid(row=0, column=2, padx=10)
        
        # Assignments list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True)
        
        columns = ('Assignment ID', 'Student', 'Room', 'Building', 'Move-in', 'Status')
        self.assignments_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        for col in columns:
            self.assignments_tree.heading(col, text=col)
            self.assignments_tree.column(col, width=150)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.assignments_tree.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=self.assignments_tree.xview)
        self.assignments_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.assignments_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        
        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='x', pady=20)
        
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_assignments_list).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="View Details", command=self.view_assignment_details).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Update Status", command=self.update_assignment_status).pack(side='left', padx=5)
        
        # Load assignments
        self.refresh_assignments_list()
    
    def refresh_assignments_list(self):
        """Refresh assignments list"""
        for item in self.assignments_tree.get_children():
            self.assignments_tree.delete(item)
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            status_filter = self.assign_status_filter.get()
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
                self.assignments_tree.insert('', 'end', values=(
                    assign[0], student_name, assign[3], assign[4], assign[5], assign[6]
                ))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {str(e)}")
    
    def view_assignment_details(self):
        """View assignment details"""
        selected = self.assignments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an assignment to view")
            return
        
        assignment_id = self.assignments_tree.item(selected[0])['values'][0]
        self.show_assignment_details_dialog(assignment_id)
    
    def show_assignment_details_dialog(self, assignment_id):
        """Show assignment details dialog"""
        details_window = tk.Toplevel(self.root)
        details_window.title("Assignment Details")
        details_window.geometry("600x500")
        details_window.transient(self.root)
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
Monthly Rent: ${assign_data[14]}
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
    
    def update_assignment_status(self):
        """Update assignment status"""
        selected = self.assignments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an assignment to update")
            return
        
        assignment_id = self.assignments_tree.item(selected[0])['values'][0]
        current_status = self.assignments_tree.item(selected[0])['values'][5]
        
        # Status update dialog
        status_window = tk.Toplevel(self.root)
        status_window.title("Update Assignment Status")
        status_window.geometry("400x300")
        status_window.transient(self.root)
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
                
                messagebox.showinfo("Success", f"Assignment status updated to {new_status}")
                self.refresh_assignments_list()
                status_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update status: {str(e)}")
    
    def load_active_assignments(self):
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
                display_text = f"{assign[1]} {assign[2]} ({assign[3]}) - Room {assign[4]} in {assign[5]} - ${assign[6]}/month"
                assignment_values.append(display_text)
            
            self.assignment_combo['values'] = assignment_values
            
        except Exception as e:
            print(f"Error loading assignments: {str(e)}")
    
    def record_payment(self):
        """Record a new payment"""
        try:
            assignment_text = self.assignment_combo.get()
            amount_text = self.payment_amount_entry.get().strip()
            payment_method = self.payment_method_combo.get()
            transaction_ref = self.transaction_ref_entry.get().strip() or None
            period_start = self.period_start_entry.get().strip()
            period_end = self.period_end_entry.get().strip()
            
            if not all([assignment_text, amount_text, payment_method, period_start, period_end]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return
            
            # Extract assignment ID from combo text
            if not assignment_text or '(' not in assignment_text:
                messagebox.showerror("Error", "Please select an assignment")
                return
            
            student_id = assignment_text.split('(')[1].split(')')[0]
            
            # Get assignment_id
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT assignment_id FROM housing_assignments 
            WHERE student_id = ? AND status = 'Active'
            ''', (student_id,))
            
            result = cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Assignment not found")
                conn.close()
                return
            
            assignment_id = result[0]
            
            # Validate amount
            try:
                amount = float(amount_text)
                if amount <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid payment amount")
                conn.close()
                return
            
            # Validate dates
            try:
                datetime.strptime(period_start, '%Y-%m-%d')
                datetime.strptime(period_end, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Please enter valid dates (YYYY-MM-DD)")
                conn.close()
                return
            
            # Create payment record
            payment_id = generate_id('PAY')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO housing_payments (
                payment_id, assignment_id, student_id, amount, payment_date, payment_method,
                transaction_reference, payment_period_start, payment_period_end, status,
                received_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                payment_id, assignment_id, student_id, amount, timestamp, payment_method,
                transaction_ref, period_start, period_end, 'Completed',
                self.auth.current_user['username'], timestamp, timestamp
            ))
            
            # Get student details for email
            cursor.execute('''
            SELECT s.first_name, s.last_name, s.email, r.room_number, b.building_name
            FROM students s
            JOIN housing_assignments a ON s.student_id = a.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.assignment_id = ?
            ''', (assignment_id,))

            student_info = cursor.fetchone()

            conn.commit()
            conn.close()

            # Send email confirmation if available
            email_sent = False
            email_error = None

            if EMAIL_SERVICE_AVAILABLE and student_info and student_info[2]:  # Check if email exists
                try:
                    student_name = f"{student_info[0]} {student_info[1]}"
                    student_email = student_info[2]
                    room_number = student_info[3]
                    building_name = student_info[4]

                    email_subject = f"Housing Payment Confirmation - {payment_id}"
                    email_body = f"""Dear {student_name},

This email confirms your housing payment has been received.

Payment Details:
- Payment ID: {payment_id}
- Amount: ${amount:.2f}
- Payment Date: {timestamp}
- Payment Method: {payment_method}
- Transaction Reference: {transaction_ref or 'N/A'}
- Payment Period: {period_start} to {period_end}

Housing Assignment:
- Building: {building_name}
- Room: {room_number}

Thank you for your payment.

Best regards,
Housing Administration"""

                    # Attempt to send email
                    send_email_as_system(
                        student_email,
                        email_subject,
                        email_body,
                        system_name="Housing Administration"
                    )
                    email_sent = True
                    print(f"✓ Payment confirmation email sent to {student_email}")

                except Exception as e:
                    email_error = str(e)
                    print(f"✗ Failed to send email confirmation: {email_error}")

            # Show immediate confirmation dialog with email status
            if email_sent:
                result = messagebox.showinfo(
                    "Payment Recorded - Email Sent",
                    f"✓ Payment recorded successfully!\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Amount: ${amount:.2f}\n\n"
                    f"✓ Email confirmation sent to:\n{student_email}"
                )
            elif EMAIL_SERVICE_AVAILABLE and student_info and student_info[2]:
                # Email service available but failed
                result = messagebox.showerror(
                    "Payment Recorded - Email Failed",
                    f"✓ Payment recorded successfully!\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Amount: ${amount:.2f}\n\n"
                    f"✗ Failed to send email confirmation:\n{email_error}\n\n"
                    f"Please notify the student manually."
                )
            elif student_info and not student_info[2]:
                # No email address on file
                messagebox.showwarning(
                    "Payment Recorded - No Email",
                    f"✓ Payment recorded successfully!\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Amount: ${amount:.2f}\n\n"
                    f"⚠ No email address on file for this student.\n"
                    f"Please notify the student manually."
                )
            else:
                # Email service not available
                messagebox.showinfo(
                    "Payment Recorded",
                    f"✓ Payment recorded successfully!\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Amount: ${amount:.2f}\n\n"
                    f"Note: Email service is not available."
                )

            # Clear form
            self.assignment_combo.set("")
            self.payment_amount_entry.delete(0, tk.END)
            self.payment_method_combo.set("")
            self.transaction_ref_entry.delete(0, tk.END)
            self.period_start_entry.delete(0, tk.END)
            self.period_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            self.period_end_entry.delete(0, tk.END)
            next_month = datetime.now().replace(day=28) + timedelta(days=4)
            end_of_month = next_month - datetime.timedelta(days=next_month.day)
            self.period_end_entry.insert(0, end_of_month.strftime('%Y-%m-%d'))
            
            # Refresh payment history
            self.refresh_payment_history()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to record payment: {str(e)}")
    
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
                    rent_display = f"${row[9]:.2f}" if row[9] is not None else 'N/A'
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
    
    def show_inspections(self):
        """Show room inspections interface"""
        self.clear_content()

        ttk.Label(self.content_frame, text="Room Inspections",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Control buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill='x', pady=10)

        ttk.Button(button_frame, text="Schedule Inspection",
                  command=self.schedule_inspection_dialog).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Record Inspection",
                  command=self.record_inspection_dialog).pack(side='left', padx=5)
        ttk.Button(button_frame, text="View Details",
                  command=lambda: self.view_inspection_details(inspections_tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Edit Inspection",
                  command=lambda: self.edit_inspection(inspections_tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete Inspection",
                  command=lambda: self.delete_inspection(inspections_tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=lambda: self.load_inspections(inspections_tree)).pack(side='left', padx=5)

        # Inspections list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, pady=10)

        inspections_tree = ttk.Treeview(list_frame,
                                       columns=('ID', 'Room', 'Date', 'Type', 'Inspector', 'Status', 'Issues'),
                                       show='headings', height=20)

        inspections_tree.heading('ID', text='Inspection ID')
        inspections_tree.heading('Room', text='Room')
        inspections_tree.heading('Date', text='Date')
        inspections_tree.heading('Type', text='Type')
        inspections_tree.heading('Inspector', text='Inspector')
        inspections_tree.heading('Status', text='Status')
        inspections_tree.heading('Issues', text='Issues Found')

        for col in ('ID', 'Room', 'Date', 'Type', 'Inspector', 'Status', 'Issues'):
            inspections_tree.column(col, width=120)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=inspections_tree.yview)
        inspections_tree.configure(yscrollcommand=scrollbar.set)

        inspections_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load inspections
        self.load_inspections(inspections_tree)

    def schedule_inspection_dialog(self):
        """Schedule a new inspection"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Schedule Inspection")
        dialog.geometry("800x700")
        dialog.transient(self.root)

        ttk.Label(dialog, text="Schedule Room Inspection",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Building selection
        ttk.Label(form_frame, text="Building:").grid(row=0, column=0, sticky='w', pady=5)
        building_var = tk.StringVar()
        building_combo = ttk.Combobox(form_frame, textvariable=building_var, width=28, state='readonly')
        building_combo.grid(row=0, column=1, pady=5, padx=5)

        # Load buildings from database
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            conn.close()

            building_dict = {f"{row[1]} (ID: {row[0]})": row[0] for row in buildings}
            building_combo['values'] = list(building_dict.keys())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load buildings: {str(e)}", parent=dialog)
            building_dict = {}

        # Inspection scope selection
        ttk.Label(form_frame, text="Inspection Scope:").grid(row=1, column=0, sticky='w', pady=5)
        scope_var = tk.StringVar(value="Single Room")
        scope_combo = ttk.Combobox(form_frame, textvariable=scope_var,
                                   values=['Single Room', 'Full Building'],
                                   width=28, state='readonly')
        scope_combo.grid(row=1, column=1, pady=5, padx=5)

        # Room selection (shown only for single room)
        room_label = ttk.Label(form_frame, text="Room Number:")
        room_label.grid(row=2, column=0, sticky='w', pady=5)
        room_var = tk.StringVar()
        room_combo = ttk.Combobox(form_frame, textvariable=room_var, width=28, state='readonly')
        room_combo.grid(row=2, column=1, pady=5, padx=5)

        def update_rooms(*args):
            """Update room dropdown based on selected building"""
            selected_building = building_var.get()
            if selected_building and selected_building in building_dict:
                building_id = building_dict[selected_building]
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT room_id, room_number
                        FROM housing_rooms
                        WHERE building_id = ?
                        ORDER BY room_number
                    ''', (building_id,))
                    rooms = cursor.fetchall()
                    conn.close()

                    room_dict[building_id] = {f"Room {row[1]}": row[0] for row in rooms}
                    room_combo['values'] = list(room_dict.get(building_id, {}).keys())
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load rooms: {str(e)}", parent=dialog)

        def toggle_room_selection(*args):
            """Show/hide room selection based on scope"""
            if scope_var.get() == "Single Room":
                room_label.grid(row=2, column=0, sticky='w', pady=5)
                room_combo.grid(row=2, column=1, pady=5, padx=5)
            else:
                room_label.grid_remove()
                room_combo.grid_remove()

        room_dict = {}
        building_var.trace('w', update_rooms)
        scope_var.trace('w', toggle_room_selection)

        # Date
        ttk.Label(form_frame, text="Inspection Date:").grid(row=3, column=0, sticky='w', pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(form_frame, textvariable=date_var, width=30)
        date_entry.grid(row=3, column=1, pady=5, padx=5)

        # Time
        ttk.Label(form_frame, text="Inspection Time:").grid(row=4, column=0, sticky='w', pady=5)
        time_var = tk.StringVar(value="10:00 AM")
        time_entry = ttk.Entry(form_frame, textvariable=time_var, width=30)
        time_entry.grid(row=4, column=1, pady=5, padx=5)

        # Type
        ttk.Label(form_frame, text="Inspection Type:").grid(row=5, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value="Routine")
        type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                  values=['Routine', 'Move-in', 'Move-out', 'Maintenance', 'Safety'],
                                  width=28, state='readonly')
        type_combo.grid(row=5, column=1, pady=5, padx=5)

        # Inspector
        ttk.Label(form_frame, text="Inspector:").grid(row=6, column=0, sticky='w', pady=5)
        inspector_var = tk.StringVar()
        inspector_entry = ttk.Entry(form_frame, textvariable=inspector_var, width=30)
        inspector_entry.grid(row=6, column=1, pady=5, padx=5)

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=7, column=0, sticky='nw', pady=5)
        notes_text = tk.Text(form_frame, height=4, width=30)
        notes_text.grid(row=7, column=1, pady=5, padx=5)

        # Email notification checkbox
        send_email_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Send email notification to affected students",
                       variable=send_email_var).grid(row=8, column=0, columnspan=2, sticky='w', pady=10)

        def save_inspection():
            # Validation
            selected_building = building_var.get()
            if not selected_building:
                messagebox.showwarning("Building Required", "Please select a building", parent=dialog)
                return

            if scope_var.get() == "Single Room" and not room_var.get().strip():
                messagebox.showwarning("Room Required", "Please select a room", parent=dialog)
                return

            if not inspector_var.get().strip():
                messagebox.showwarning("Inspector Required", "Please enter an inspector name", parent=dialog)
                return

            try:
                # Validate date format
                inspection_date = date_var.get().strip()
                datetime.strptime(inspection_date, '%Y-%m-%d')

                # Get the notes
                notes = notes_text.get("1.0", tk.END).strip()
                inspection_time = time_var.get().strip()

                # Save to database
                conn = get_connection()
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                building_id = building_dict[selected_building]

                # Get rooms to inspect
                if scope_var.get() == "Single Room":
                    # Get specific room_id
                    selected_room = room_var.get()
                    if selected_room in room_dict.get(building_id, {}):
                        room_ids = [room_dict[building_id][selected_room]]
                    else:
                        messagebox.showerror("Error", "Please select a valid room", parent=dialog)
                        conn.close()
                        return
                else:
                    # Get all rooms in building
                    cursor.execute('SELECT room_id FROM housing_rooms WHERE building_id = ?', (building_id,))
                    room_ids = [row[0] for row in cursor.fetchall()]

                if not room_ids:
                    messagebox.showerror("Error", "No rooms found for inspection", parent=dialog)
                    conn.close()
                    return

                inspection_ids = []
                # Insert inspection for each room
                for room_id in room_ids:
                    inspection_id = generate_id('INSP')
                    cursor.execute('''
                    INSERT INTO housing_inspections (
                        inspection_id, room_id, inspection_date, inspection_type,
                        inspector, findings, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'Scheduled', ?, ?)
                    ''', (inspection_id, room_id, inspection_date, type_var.get(),
                         inspector_var.get(), notes, timestamp, timestamp))
                    inspection_ids.append(inspection_id)

                conn.commit()

                # Send email notifications if requested
                if send_email_var.get():
                    self.send_inspection_emails(cursor, building_id, room_ids, inspection_date,
                                               inspection_time, type_var.get(), inspector_var.get(),
                                               notes, scope_var.get() == "Full Building")

                conn.close()

                messagebox.showinfo("Success",
                                  f"Inspection(s) scheduled successfully!\n\n"
                                  f"Total inspections: {len(inspection_ids)}\n"
                                  f"Building: {selected_building}\n"
                                  f"Date: {inspection_date}\n"
                                  f"Type: {type_var.get()}\n"
                                  f"{'Email notifications sent' if send_email_var.get() else 'No emails sent'}",
                                  parent=dialog)
                dialog.destroy()

            except ValueError:
                messagebox.showerror("Error", "Please enter a valid date (YYYY-MM-DD)", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to schedule inspection: {str(e)}", parent=dialog)
                import traceback
                traceback.print_exc()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Schedule", command=save_inspection).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def send_inspection_emails(self, cursor, building_id, room_ids, inspection_date,
                               inspection_time, inspection_type, inspector_name, notes, is_building_wide):
        """Send email notifications to students about scheduled inspections"""
        try:
            # Get building info
            cursor.execute('SELECT building_name FROM housing_buildings WHERE building_id = ?', (building_id,))
            building_result = cursor.fetchone()
            building_name = building_result[0] if building_result else "Unknown Building"

            # Get students in the affected rooms
            cursor.execute('''
                SELECT DISTINCT
                    s.student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    s.email_address,
                    r.room_number
                FROM housing_assignments ha
                JOIN students s ON ha.student_id = s.student_id
                JOIN housing_rooms r ON ha.room_id = r.room_id
                WHERE ha.room_id IN ({})
                AND ha.status = 'Active'
            '''.format(','.join('?' * len(room_ids))), room_ids)

            students = cursor.fetchall()

            if not students:
                print("No active students found in selected rooms")
                return

            # Load appropriate email template
            template_name = 'building_inspection_notice' if is_building_wide else 'inspection_scheduled'

            try:
                import json
                from university_system.modules.shared.constants import paths
                template_path = paths.PROJECT_ROOT / 'university_system' / 'templates' / 'email' / f'{template_name}.json'

                with open(template_path, 'r') as f:
                    template = json.load(f)

                # Send email to each student
                from university_system.infrastructure.email.email_service import send_email

                for student_id, student_name, email, room_number in students:
                    if not email:
                        continue

                    # Replace template variables
                    subject = template['subject'].replace('{{building_name}}', building_name).replace('{{room_number}}', room_number)

                    body = template['body']
                    replacements = {
                        '{{student_name}}': student_name,
                        '{{building_name}}': building_name,
                        '{{room_number}}': room_number,
                        '{{inspection_date}}': inspection_date,
                        '{{inspection_time}}': inspection_time,
                        '{{inspection_type}}': inspection_type,
                        '{{inspector_name}}': inspector_name,
                        '{{notes}}': notes if notes else '',
                        '{{additional_notes}}': notes if notes else ''
                    }

                    for key, value in replacements.items():
                        body = body.replace(key, value)

                    # Send email
                    send_email(
                        to_email=email,
                        subject=subject,
                        body=body,
                        email_type='inspection_notification'
                    )

                print(f"✓ Sent {len(students)} inspection notification emails")

            except Exception as email_error:
                print(f"Error sending emails: {email_error}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            print(f"Error in send_inspection_emails: {e}")
            import traceback
            traceback.print_exc()

    def send_post_inspection_email(self, cursor, room_id, inspection_id, inspection_date,
                                   inspection_type, inspector_name, findings, status, action_required, followup_date):
        """Send email notification to students after inspection is completed"""
        try:
            # Get room and building info
            cursor.execute('''
                SELECT r.room_number, b.building_name
                FROM housing_rooms r
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE r.room_id = ?
            ''', (room_id,))

            room_info = cursor.fetchone()
            if not room_info:
                print(f"Room {room_id} not found")
                return

            room_number = room_info[0]
            building_name = room_info[1]

            # Get students assigned to this room
            cursor.execute('''
                SELECT DISTINCT
                    s.student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    s.email_address
                FROM housing_assignments ha
                JOIN students s ON ha.student_id = s.student_id
                WHERE ha.room_id = ?
                AND ha.status = 'Active'
            ''', (room_id,))

            students = cursor.fetchall()

            if not students:
                print(f"No active students found for room {room_number}")
                return

            # Load email service
            from university_system.infrastructure.email.email_service import send_email

            # Determine which template to use based on status
            if status == 'Issues Found':
                template_name = 'inspection_issues_found'
            else:
                template_name = 'inspection_completed'

            # Load email template
            template_path = f"/home/seancatchpole989/university_system/templates/email/{template_name}.json"
            try:
                with open(template_path, 'r') as f:
                    import json
                    template = json.load(f)
            except Exception as e:
                print(f"Failed to load email template {template_name}: {e}")
                return

            # Determine pass/fail result
            if status == 'Issues Found':
                pass_fail = "FAIL - Issues Identified"
            elif status == 'Completed':
                pass_fail = "PASS - No Issues"
            else:
                pass_fail = status

            # Send email to each student
            emails_sent = 0
            for student in students:
                student_id, student_name, email_address = student

                if not email_address:
                    print(f"No email address for student {student_name}")
                    continue

                # Prepare template variables
                variables = {
                    'student_name': student_name,
                    'building_name': building_name,
                    'room_number': room_number,
                    'inspection_date': inspection_date,
                    'inspection_type': inspection_type,
                    'inspector_name': inspector_name,
                    'status': status,
                    'pass_fail': pass_fail,
                    'findings': findings if findings else 'No issues found',
                    'issues': findings if findings else 'No issues identified',
                    'required_actions': action_required if action_required else 'No action required',
                    'action_required': action_required if action_required else 'No action required at this time',
                    'action_deadline': followup_date if followup_date else 'N/A',
                    'follow_up_instructions': f"A follow-up inspection is scheduled for {followup_date}" if followup_date else ""
                }

                # Render email subject and body
                subject = template['subject']
                body = template['body']

                for key, value in variables.items():
                    subject = subject.replace('{{' + key + '}}', str(value))
                    body = body.replace('{{' + key + '}}', str(value))

                # Send email
                success = send_email(
                    recipient_email=email_address,
                    subject=subject,
                    body=body
                )

                if success:
                    emails_sent += 1
                    print(f"✓ Sent inspection result email to {student_name} ({email_address})")

            print(f"✓ Sent {emails_sent} post-inspection notification emails")

        except Exception as e:
            print(f"Error in send_post_inspection_email: {e}")
            import traceback
            traceback.print_exc()

    def record_inspection_dialog(self):
        """Record inspection results"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Inspection")
        dialog.geometry("600x500")
        dialog.transient(self.root)

        ttk.Label(dialog, text="Record Inspection Results",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Inspection ID
        ttk.Label(form_frame, text="Inspection ID:").grid(row=0, column=0, sticky='w', pady=5)
        id_var = tk.StringVar()
        id_entry = ttk.Entry(form_frame, textvariable=id_var, width=30)
        id_entry.grid(row=0, column=1, pady=5, padx=5)

        # Status
        ttk.Label(form_frame, text="Status:").grid(row=1, column=0, sticky='w', pady=5)
        status_var = tk.StringVar(value="Completed")
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                    values=['Completed', 'Issues Found', 'Follow-up Required'],
                                    width=28, state='readonly')
        status_combo.grid(row=1, column=1, pady=5, padx=5)

        # Issues found
        ttk.Label(form_frame, text="Issues Found:").grid(row=2, column=0, sticky='nw', pady=5)
        issues_text = tk.Text(form_frame, height=6, width=30)
        issues_text.grid(row=2, column=1, pady=5, padx=5)

        # Pass/Fail
        pass_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Inspection Passed", variable=pass_var).grid(row=3, column=1, sticky='w', pady=5)

        def save_results():
            if not id_var.get().strip():
                messagebox.showwarning("ID Required", "Please enter inspection ID", parent=dialog)
                return

            try:
                inspection_id = id_var.get().strip()
                status = status_var.get()
                issues = issues_text.get("1.0", tk.END).strip()
                passed = pass_var.get()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Update inspection in database
                conn = get_connection()
                cursor = conn.cursor()

                # Check if inspection exists
                cursor.execute('SELECT inspection_id FROM housing_inspections WHERE inspection_id = ?',
                             (inspection_id,))
                if not cursor.fetchone():
                    messagebox.showerror("Error", f"Inspection ID {inspection_id} not found", parent=dialog)
                    conn.close()
                    return

                # Update inspection with results
                cursor.execute('''
                UPDATE housing_inspections
                SET status = ?, findings = ?, action_required = ?, updated_at = ?
                WHERE inspection_id = ?
                ''', (status, issues, 'Follow-up Required' if not passed else 'None', timestamp, inspection_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success",
                                  f"Inspection results recorded successfully!\n\n"
                                  f"Inspection ID: {inspection_id}\n"
                                  f"Status: {status}\n"
                                  f"Passed: {'Yes' if passed else 'No'}",
                                  parent=dialog)
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to record inspection results: {str(e)}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=save_results).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def view_inspection_details(self, tree):
        """View detailed inspection report"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an inspection to view")
            return

        values = tree.item(selection[0], 'values')
        messagebox.showinfo("Inspection Details",
                          f"Inspection ID: {values[0]}\n"
                          f"Room: {values[1]}\n"
                          f"Date: {values[2]}\n"
                          f"Type: {values[3]}\n"
                          f"Inspector: {values[4]}\n"
                          f"Status: {values[5]}\n"
                          f"Issues: {values[6]}")

    def load_inspections(self, tree):
        """Load inspections from database"""
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT i.inspection_id, r.room_number, i.inspection_date, i.inspection_type,
                   i.inspector, i.status, COALESCE(i.findings, 'None')
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            ORDER BY i.inspection_date DESC
            LIMIT 100
            ''')

            inspections = cursor.fetchall()
            conn.close()

            for inspection in inspections:
                # Convert sqlite3.Row to tuple to avoid errors
                if hasattr(inspection, '__iter__') and not isinstance(inspection, (str, bytes)):
                    values = tuple(inspection)
                else:
                    values = inspection
                tree.insert('', 'end', values=values)

            if not inspections:
                # Insert a message if no inspections found
                tree.insert('', 'end', values=('No inspections found', '', '', '', '', '', ''))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load inspections: {str(e)}")
            # Show sample data on error for demo purposes
            tree.insert('', 'end', values=(f'Error: {str(e)}', '', '', '', '', '', ''))
            import traceback
            traceback.print_exc()

    def edit_inspection(self, tree):
        """Edit an existing inspection"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an inspection to edit")
            return

        values = tree.item(selection[0], 'values')
        inspection_id = values[0]

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Inspection")
        dialog.geometry("700x600")
        dialog.transient(self.root)

        ttk.Label(dialog, text=f"Edit Inspection {inspection_id}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Get current data from database
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT i.room_id, r.room_number, i.inspection_date, i.inspection_type,
                   i.inspector, i.findings, i.status, i.action_required, i.follow_up_date
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            WHERE i.inspection_id = ?
            ''', (inspection_id,))

            inspection_data = cursor.fetchone()
            conn.close()

            if not inspection_data:
                messagebox.showerror("Error", "Inspection not found")
                dialog.destroy()
                return

            # Room Number (read-only)
            ttk.Label(form_frame, text="Room Number:").grid(row=0, column=0, sticky='w', pady=5)
            ttk.Label(form_frame, text=inspection_data[1]).grid(row=0, column=1, sticky='w', pady=5, padx=5)

            # Date
            ttk.Label(form_frame, text="Inspection Date:").grid(row=1, column=0, sticky='w', pady=5)
            date_var = tk.StringVar(value=inspection_data[2])
            ttk.Entry(form_frame, textvariable=date_var, width=30).grid(row=1, column=1, pady=5, padx=5)

            # Type
            ttk.Label(form_frame, text="Inspection Type:").grid(row=2, column=0, sticky='w', pady=5)
            type_var = tk.StringVar(value=inspection_data[3])
            ttk.Combobox(form_frame, textvariable=type_var, width=28,
                        values=['Routine', 'Move-in', 'Move-out', 'Maintenance', 'Safety'],
                        state='readonly').grid(row=2, column=1, pady=5, padx=5)

            # Inspector
            ttk.Label(form_frame, text="Inspector:").grid(row=3, column=0, sticky='w', pady=5)
            inspector_var = tk.StringVar(value=inspection_data[4])
            ttk.Entry(form_frame, textvariable=inspector_var, width=30).grid(row=3, column=1, pady=5, padx=5)

            # Status
            ttk.Label(form_frame, text="Status:").grid(row=4, column=0, sticky='w', pady=5)
            status_var = tk.StringVar(value=inspection_data[6])
            ttk.Combobox(form_frame, textvariable=status_var, width=28,
                        values=['Scheduled', 'Completed', 'Issues Found', 'Follow-up Required'],
                        state='readonly').grid(row=4, column=1, pady=5, padx=5)

            # Findings
            ttk.Label(form_frame, text="Findings:").grid(row=5, column=0, sticky='nw', pady=5)
            findings_text = tk.Text(form_frame, height=4, width=30)
            findings_text.grid(row=5, column=1, pady=5, padx=5)
            if inspection_data[5]:
                findings_text.insert("1.0", inspection_data[5])

            # Action Required
            ttk.Label(form_frame, text="Action Required:").grid(row=6, column=0, sticky='nw', pady=5)
            action_text = tk.Text(form_frame, height=4, width=30)
            action_text.grid(row=6, column=1, pady=5, padx=5)
            if inspection_data[7]:
                action_text.insert("1.0", inspection_data[7])

            # Follow-up Date
            ttk.Label(form_frame, text="Follow-up Date:").grid(row=7, column=0, sticky='w', pady=5)
            followup_var = tk.StringVar(value=inspection_data[8] if inspection_data[8] else '')
            ttk.Entry(form_frame, textvariable=followup_var, width=30).grid(row=7, column=1, pady=5, padx=5)

            # Email notification checkbox
            ttk.Label(form_frame, text="Email Notification:").grid(row=8, column=0, sticky='w', pady=5)
            email_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(form_frame, text="Send email notification to student(s)",
                           variable=email_var).grid(row=8, column=1, sticky='w', pady=5, padx=5)

            def save_changes():
                try:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    findings = findings_text.get("1.0", tk.END).strip()
                    action = action_text.get("1.0", tk.END).strip()
                    followup = followup_var.get().strip() if followup_var.get().strip() else None
                    new_status = status_var.get()
                    old_status = inspection_data[6]  # Get the original status

                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    UPDATE housing_inspections
                    SET inspection_date = ?, inspection_type = ?, inspector = ?,
                        findings = ?, status = ?, action_required = ?, follow_up_date = ?,
                        updated_at = ?
                    WHERE inspection_id = ?
                    ''', (date_var.get(), type_var.get(), inspector_var.get(),
                         findings, new_status, action, followup,
                         timestamp, inspection_id))

                    conn.commit()

                    # Send email notification if status changed and checkbox is checked
                    if email_var.get() and new_status != old_status and new_status in ['Completed', 'Issues Found']:
                        self.send_post_inspection_email(
                            cursor, inspection_data[0], inspection_id,
                            date_var.get(), type_var.get(), inspector_var.get(),
                            findings, new_status, action, followup
                        )

                    conn.close()

                    messagebox.showinfo("Success", "Inspection updated successfully!")
                    dialog.destroy()
                    self.load_inspections(tree)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update inspection: {str(e)}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load inspection data: {str(e)}")
            dialog.destroy()

    def delete_inspection(self, tree):
        """Delete an inspection"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an inspection to delete")
            return

        values = tree.item(selection[0], 'values')
        inspection_id = values[0]
        room = values[1]

        result = messagebox.askyesno("Confirm Delete",
                                     f"Delete inspection {inspection_id} for room {room}?")
        if result:
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('DELETE FROM housing_inspections WHERE inspection_id = ?',
                             (inspection_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Inspection {inspection_id} deleted successfully")
                self.load_inspections(tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete inspection: {str(e)}")

    def show_reports(self):
        """Show reports and analytics interface"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Reports & Analytics", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Reports menu
        reports_frame = ttk.Frame(self.content_frame)
        reports_frame.pack(fill='both', expand=True)
        
        # Left side - report buttons
        buttons_frame = ttk.LabelFrame(reports_frame, text="Available Reports", padding="20")
        buttons_frame.pack(side='left', fill='y', padx=(0, 20))
        
        report_buttons = [
            ("Occupancy Report", self.show_occupancy_report),
            ("Financial Summary", self.show_financial_summary),
            ("Maintenance Summary", self.show_maintenance_summary_gui),
            ("Room Availability", self.show_room_availability),
            ("Export Data", self.show_export_options),
            ("─" * 20, None),  # Separator
            ("Schedule Reports", self.show_scheduled_reports_manager),
            ("Template Settings", self.show_report_template_settings)
        ]
        
        for text, command in report_buttons:
            if command is None:
                # Separator
                ttk.Separator(buttons_frame, orient='horizontal').pack(fill='x', pady=10)
            else:
                ttk.Button(buttons_frame, text=text, width=20,
                          command=command).pack(pady=5)
        
        # Right side - report display area
        self.report_display_frame = ttk.LabelFrame(reports_frame, text="Report Output", padding="20")
        self.report_display_frame.pack(side='right', fill='both', expand=True)
        
        ttk.Label(self.report_display_frame, 
                 text="Select a report from the menu to view results here").pack()
    
    def open_report_window(self, title, report_content, report_type='text'):
        """Open a report in a new window with export and send options"""
        # Create new window
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry("900x700")

        # Main frame
        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Report content area with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill='both', expand=True, pady=(0, 10))

        report_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD,
                                               width=80, height=30, font=('Courier', 10))
        report_text.pack(fill='both', expand=True)
        report_text.insert('1.0', report_content)
        report_text.config(state='disabled')

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        # Export buttons
        ttk.Label(button_frame, text="Export as:", font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))

        ttk.Button(button_frame, text="TXT", width=10,
                  command=lambda: self.export_report_as_txt(title, report_content, report_window)).pack(side='left', padx=5)

        ttk.Button(button_frame, text="CSV", width=10,
                  command=lambda: self.export_report_as_csv(title, report_content, report_window)).pack(side='left', padx=5)

        ttk.Button(button_frame, text="PDF", width=10,
                  command=lambda: self.export_report_as_pdf(title, report_content, report_window)).pack(side='left', padx=5)

        # Separator
        ttk.Separator(button_frame, orient='vertical').pack(side='left', fill='y', padx=15)

        # Send to admin button
        ttk.Button(button_frame, text="Send to Admin", width=15,
                  command=lambda: self.send_report_to_admin(title, report_content, report_window)).pack(side='left', padx=5)

        # Close button
        ttk.Button(button_frame, text="Close", width=10,
                  command=report_window.destroy).pack(side='right', padx=5)

    def export_report_as_txt(self, title, content, parent_window):
        """Export report as TXT file"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            parent=parent_window,
            title="Save Report as TXT",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report exported to:\n{filename}", parent=parent_window)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report:\n{str(e)}", parent=parent_window)

    def export_report_as_csv(self, title, content, parent_window):
        """Export report as CSV file"""
        import csv
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            parent=parent_window,
            title="Save Report as CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if filename:
            try:
                # Parse report content into CSV format
                lines = content.split('\n')

                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)

                    # Write header
                    writer.writerow([title])
                    writer.writerow([])  # Empty row

                    # Write content line by line
                    for line in lines:
                        writer.writerow([line])

                messagebox.showinfo("Success", f"Report exported to:\n{filename}", parent=parent_window)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report:\n{str(e)}", parent=parent_window)

    def export_report_as_pdf(self, title, content, parent_window):
        """Export report as PDF file"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            parent=parent_window,
            title="Save Report as PDF",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )

        if filename:
            try:
                # Try to use reportlab if available
                try:
                    from reportlab.lib.pagesizes import letter
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.units import inch

                    c = canvas.Canvas(filename, pagesize=letter)
                    width, height = letter

                    # Title
                    c.setFont("Helvetica-Bold", 16)
                    c.drawString(1*inch, height - 1*inch, title)

                    # Content
                    c.setFont("Courier", 9)
                    y_position = height - 1.5*inch
                    line_height = 12

                    lines = content.split('\n')
                    for line in lines:
                        if y_position < 1*inch:
                            c.showPage()
                            c.setFont("Courier", 9)
                            y_position = height - 1*inch

                        # Truncate long lines
                        if len(line) > 100:
                            line = line[:100] + "..."

                        c.drawString(0.5*inch, y_position, line)
                        y_position -= line_height

                    c.save()
                    messagebox.showinfo("Success", f"Report exported to:\n{filename}", parent=parent_window)

                except ImportError:
                    # Fallback: save as text with .pdf extension
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"{title}\n{'='*60}\n\n{content}")
                    messagebox.showwarning("Limited PDF Support",
                                         f"reportlab not available. Report saved as text file with .pdf extension.\n\n"
                                         f"Install reportlab for proper PDF support:\n"
                                         f"pip install reportlab\n\n"
                                         f"File saved to: {filename}",
                                         parent=parent_window)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report:\n{str(e)}", parent=parent_window)

    def send_report_to_admin(self, title, content, parent_window):
        """Send report to admin via email"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get admin email from database
            cursor.execute('''
                SELECT email, first_name, last_name
                FROM users
                WHERE (role = 'admin' OR role = 'staff')
                AND email IS NOT NULL
                AND email != ''
                ORDER BY
                    CASE
                        WHEN username = '7591239' THEN 1
                        WHEN role = 'admin' THEN 2
                        WHEN role = 'staff' THEN 3
                        ELSE 4
                    END
                LIMIT 1
            ''')

            admin = cursor.fetchone()

            if not admin:
                messagebox.showerror("Error",
                                   "No administrator email found in database.\n"
                                   "Please ensure an administrator account exists.",
                                   parent=parent_window)
                conn.close()
                return

            admin_email = admin[0]
            admin_name = f"{admin[1]} {admin[2]}"
            conn.close()

            # Get current user info
            sender_name = "Housing System"
            try:
                if self.auth and hasattr(self.auth, 'is_logged_in') and self.auth.is_logged_in():
                    current_user = self.auth.get_current_user()
                    if current_user and 'first_name' in current_user and 'last_name' in current_user:
                        sender_name = f"{current_user['first_name']} {current_user['last_name']}"
            except Exception as e:
                # If auth fails, just use default sender name
                print(f"Warning: Could not get current user: {e}")
                pass

            # Prepare email
            from university_system.infrastructure.email.email_service import send_email

            # Format email body
            email_body = f"""Hello {admin_name},

A housing report has been generated and sent to you for review.

Report: {title}
Generated by: {sender_name}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

--- REPORT CONTENT ---

{content}

---

This is an automated message from the University Housing Management System.
"""

            # Send email
            success = send_email(
                recipient_email=admin_email,
                subject=f"Housing Report: {title}",
                body=email_body
            )

            if success:
                messagebox.showinfo("Success",
                                  f"Report sent successfully to:\n{admin_name} ({admin_email})",
                                  parent=parent_window)
            else:
                messagebox.showerror("Error",
                                   "Failed to send email. Please check email configuration.",
                                   parent=parent_window)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send report to admin:\n{str(e)}", parent=parent_window)

    def show_occupancy_report(self):
        """Show occupancy report in new window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Generate report content
            report_content = "HOUSING OCCUPANCY REPORT\n"
            report_content += "=" * 50 + "\n\n"

            # Overall statistics
            cursor.execute('SELECT COUNT(*) FROM housing_buildings')
            total_buildings = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms')
            total_rooms = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Occupied"')
            occupied_rooms = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Available"')
            available_rooms = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_assignments WHERE status = "Active"')
            active_assignments = cursor.fetchone()[0]

            occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0

            report_content += f"Total Buildings: {total_buildings}\n"
            report_content += f"Total Rooms: {total_rooms}\n"
            report_content += f"Occupied Rooms: {occupied_rooms}\n"
            report_content += f"Available Rooms: {available_rooms}\n"
            report_content += f"Active Assignments: {active_assignments}\n"
            report_content += f"Occupancy Rate: {occupancy_rate:.1f}%\n\n"

            # Building breakdown
            report_content += "BUILDING BREAKDOWN:\n"
            report_content += "-" * 80 + "\n"
            report_content += f"{'Building':<25} {'Total':<8} {'Occupied':<10} {'Available':<10} {'Rate':<8}\n"
            report_content += "-" * 80 + "\n"

            cursor.execute('''
            SELECT b.building_name, b.total_rooms, b.available_rooms,
                   (b.total_rooms - b.available_rooms) as occupied_rooms,
                   ROUND((CAST(b.total_rooms - b.available_rooms AS FLOAT) / b.total_rooms) * 100, 1) as occupancy_rate
            FROM housing_buildings b
            ORDER BY b.building_name
            ''')

            buildings = cursor.fetchall()

            for building in buildings:
                report_content += f"{building[0]:<25} {building[1]:<8} {building[3]:<10} {building[2]:<10} {building[4]:.1f}%\n"

            # Room type breakdown
            report_content += "\n\nROOM TYPE DISTRIBUTION:\n"
            report_content += "-" * 50 + "\n"
            report_content += f"{'Type':<12} {'Total':<8} {'Occupied':<10} {'Available':<10}\n"
            report_content += "-" * 50 + "\n"

            cursor.execute('''
            SELECT room_type, COUNT(*) as total,
                   SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occupied,
                   SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available
            FROM housing_rooms
            GROUP BY room_type
            ORDER BY room_type
            ''')

            room_types = cursor.fetchall()

            for room_type in room_types:
                report_content += f"{room_type[0]:<12} {room_type[1]:<8} {room_type[2]:<10} {room_type[3]:<10}\n"

            conn.close()

            # Open report in new window
            self.open_report_window("Housing Occupancy Report", report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")
    
    def show_financial_summary(self):
        """Show financial summary in new window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "HOUSING FINANCIAL SUMMARY\n"
            report_content += "=" * 50 + "\n\n"

            # Monthly revenue calculation
            cursor.execute('''
            SELECT SUM(monthly_rent) as monthly_revenue
            FROM housing_assignments
            WHERE status = 'Active'
            ''')

            monthly_revenue = cursor.fetchone()[0] or 0

            report_content += f"Current Monthly Revenue: ${monthly_revenue:,.2f}\n"
            report_content += f"Projected Annual Revenue: ${monthly_revenue * 12:,.2f}\n\n"

            # Payment statistics for current year
            current_year = datetime.now().year

            cursor.execute('''
            SELECT COUNT(*) as payment_count, SUM(amount) as total_amount
            FROM housing_payments
            WHERE strftime('%Y', payment_date) = ?
            ''', (str(current_year),))

            year_stats = cursor.fetchone()
            payment_count = year_stats[0] or 0
            total_collected = year_stats[1] or 0

            report_content += f"Payments Collected This Year ({current_year}):\n"
            report_content += f"Number of Payments: {payment_count}\n"
            report_content += f"Total Amount Collected: ${total_collected:,.2f}\n\n"

            # Revenue by building
            cursor.execute('''
            SELECT b.building_name, COUNT(a.assignment_id) as active_assignments,
                   SUM(a.monthly_rent) as monthly_revenue
            FROM housing_buildings b
            LEFT JOIN housing_rooms r ON b.building_id = r.building_id
            LEFT JOIN housing_assignments a ON r.room_id = a.room_id AND a.status = 'Active'
            GROUP BY b.building_id, b.building_name
            ORDER BY monthly_revenue DESC
            ''')

            building_revenue = cursor.fetchall()

            report_content += "REVENUE BY BUILDING:\n"
            report_content += "-" * 60 + "\n"
            report_content += f"{'Building':<25} {'Assignments':<12} {'Monthly Revenue':<15}\n"
            report_content += "-" * 60 + "\n"

            for building in building_revenue:
                assignments = building[1] or 0
                revenue = building[2] or 0
                report_content += f"{building[0]:<25} {assignments:<12} ${revenue:,.2f}\n"

            conn.close()

            # Open report in new window
            self.open_report_window("Housing Financial Summary", report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")
    
    def show_maintenance_summary_gui(self):
        """Show maintenance summary in new window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "MAINTENANCE REQUESTS SUMMARY\n"
            report_content += "=" * 40 + "\n\n"

            # Overall statistics
            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests')
            total_requests = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Open"')
            open_requests = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "In Progress"')
            in_progress = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Complete"')
            completed = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE priority = "Emergency"')
            emergency_requests = cursor.fetchone()[0]

            report_content += f"Total Requests: {total_requests}\n"
            report_content += f"Open Requests: {open_requests}\n"
            report_content += f"In Progress: {in_progress}\n"
            report_content += f"Completed: {completed}\n"
            report_content += f"Emergency Priority: {emergency_requests}\n\n"

            # Requests by status
            cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM housing_maintenance_requests
            GROUP BY status
            ORDER BY
                CASE status
                    WHEN 'Open' THEN 1
                    WHEN 'In Progress' THEN 2
                    WHEN 'Pending Parts' THEN 3
                    WHEN 'Complete' THEN 4
                    ELSE 5
                END
            ''')

            status_breakdown = cursor.fetchall()

            report_content += "REQUESTS BY STATUS:\n"
            report_content += "-" * 25 + "\n"
            for status, count in status_breakdown:
                report_content += f"{status}: {count}\n"
            report_content += "\n"

            # Requests by priority
            cursor.execute('''
            SELECT priority, COUNT(*) as count
            FROM housing_maintenance_requests
            GROUP BY priority
            ORDER BY
                CASE priority
                    WHEN 'Emergency' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    WHEN 'Low' THEN 4
                    ELSE 5
                END
            ''')

            priority_breakdown = cursor.fetchall()

            report_content += "REQUESTS BY PRIORITY:\n"
            report_content += "-" * 25 + "\n"
            for priority, count in priority_breakdown:
                report_content += f"{priority}: {count}\n"
            report_content += "\n"

            # Outstanding emergency requests
            cursor.execute('''
            SELECT COUNT(*) FROM housing_maintenance_requests
            WHERE priority = 'Emergency' AND status != 'Complete'
            ''')

            outstanding_emergency = cursor.fetchone()[0]

            if outstanding_emergency > 0:
                report_content += f"⚠️ URGENT: {outstanding_emergency} outstanding emergency request(s)\n"

            conn.close()

            # Open report in new window
            self.open_report_window("Maintenance Requests Summary", report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")
    
    def show_room_availability(self):
        """Show room availability report in new window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "ROOM AVAILABILITY REPORT\n"
            report_content += "=" * 35 + "\n\n"

            # All available rooms
            cursor.execute('''
            SELECT r.room_number, b.building_name, r.floor_number, r.room_type,
                   r.max_occupants, r.monthly_rent, r.is_accessible
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.status = 'Available'
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''')

            available_rooms = cursor.fetchall()

            report_content += f"AVAILABLE ROOMS ({len(available_rooms)} total):\n"
            report_content += "-" * 90 + "\n"
            report_content += f"{'Room':<8} {'Building':<20} {'Floor':<8} {'Type':<12} {'Max Occ.':<10} {'Rent':<10} {'Accessible':<12}\n"
            report_content += "-" * 90 + "\n"

            for room in available_rooms:
                accessible = "Yes" if room[6] else "No"
                report_content += f"{room[0]:<8} {room[1]:<20} {room[2]:<8} {room[3]:<12} {room[4]:<10} ${room[5]:<9.2f} {accessible:<12}\n"

            # Summary by type
            cursor.execute('''
            SELECT room_type, COUNT(*) as count
            FROM housing_rooms
            WHERE status = 'Available'
            GROUP BY room_type
            ORDER BY room_type
            ''')

            type_summary = cursor.fetchall()

            report_content += "\n\nAVAILABILITY SUMMARY BY TYPE:\n"
            report_content += "-" * 30 + "\n"
            for room_type, count in type_summary:
                report_content += f"{room_type}: {count} rooms\n"

            conn.close()

            # Open report in new window
            self.open_report_window("Room Availability Report", report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")
    
    def show_export_options(self):
        """Show data export options"""
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        
        ttk.Label(self.report_display_frame, text="Data Export Options", 
                 font=('Arial', 14, 'bold')).pack(pady=20)
        
        export_buttons = [
            ("Export Building Data", lambda: self.export_data_gui('buildings')),
            ("Export Room Data", lambda: self.export_data_gui('rooms')),
            ("Export Assignment Data", lambda: self.export_data_gui('assignments')),
            ("Export Application Data", lambda: self.export_data_gui('applications')),
            ("Export Payment Data", lambda: self.export_data_gui('payments')),
            ("Export Maintenance Requests", lambda: self.export_data_gui('maintenance'))
        ]
        
        for text, command in export_buttons:
            ttk.Button(self.report_display_frame, text=text, width=25,
                      command=command).pack(pady=5)
    
    def export_data_gui(self, data_type):
        """Export data to CSV with GUI feedback"""
        try:
            import csv
            from tkinter import filedialog
            
            # Let user choose save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title=f"Save {data_type.title()} Data"
            )
            
            if not filename:
                return
            
            conn = get_connection()
            cursor = conn.cursor()
            
            if data_type == 'buildings':
                cursor.execute('''
                SELECT building_id, building_name, address, campus_location, total_rooms, available_rooms,
                       has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at
                FROM housing_buildings
                ORDER BY building_name
                ''')
                headers = ['Building ID', 'Building Name', 'Address', 'Campus Location', 
                          'Total Rooms', 'Available Rooms', 'Has Elevator', 'Has Accessible Rooms',
                          'Has Kitchen', 'Has Laundry', 'Created At']
            
            elif data_type == 'rooms':
                cursor.execute('''
                SELECT r.room_id, b.building_name, r.room_number, r.floor_number, r.room_type,
                       r.max_occupants, r.current_occupants, r.is_accessible, r.status, r.monthly_rent
                FROM housing_rooms r
                JOIN housing_buildings b ON r.building_id = b.building_id
                ORDER BY b.building_name, r.floor_number, r.room_number
                ''')
                headers = ['Room ID', 'Building', 'Room Number', 'Floor', 'Type',
                          'Max Occupants', 'Current Occupants', 'Accessible', 'Status', 'Monthly Rent']
            
            elif data_type == 'assignments':
                cursor.execute('''
                SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, 
                       b.building_name, r.room_number, a.move_in_date, a.planned_move_out_date,
                       a.monthly_rent, a.status, a.assigned_by
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                ORDER BY a.created_at DESC
                ''')
                headers = ['Assignment ID', 'Student ID', 'First Name', 'Last Name',
                          'Building', 'Room', 'Move In Date', 'Planned Move Out', 
                          'Monthly Rent', 'Status', 'Assigned By']
            
            elif data_type == 'applications':
                cursor.execute('''
                SELECT app.application_id, app.student_id, s.first_name, s.last_name,
                       app.application_date, b.building_name, app.preferred_room_type,
                       app.requested_move_in_date, app.requested_duration_months, app.status
                FROM housing_applications app
                JOIN students s ON app.student_id = s.student_id
                LEFT JOIN housing_buildings b ON app.preferred_building_id = b.building_id
                ORDER BY app.application_date DESC
                ''')
                headers = ['Application ID', 'Student ID', 'First Name', 'Last Name',
                          'Application Date', 'Preferred Building', 'Preferred Room Type',
                          'Requested Move In', 'Duration (Months)', 'Status']
            
            elif data_type == 'payments':
                cursor.execute('''
                SELECT p.payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_date, p.payment_method, p.payment_period_start,
                       p.payment_period_end, p.status, b.building_name, r.room_number
                FROM housing_payments p
                JOIN students s ON p.student_id = s.student_id
                JOIN housing_assignments a ON p.assignment_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                ORDER BY p.payment_date DESC
                ''')
                headers = ['Payment ID', 'Student ID', 'First Name', 'Last Name',
                          'Amount', 'Payment Date', 'Payment Method', 'Period Start',
                          'Period End', 'Status', 'Building', 'Room']
            
            elif data_type == 'maintenance':
                cursor.execute('''
                SELECT m.request_id, m.student_id, s.first_name, s.last_name,
                       b.building_name, r.room_number, m.request_date, m.issue_type,
                       m.description, m.priority, m.status, m.assigned_to, m.completion_date
                FROM housing_maintenance_requests m
                JOIN students s ON m.student_id = s.student_id
                JOIN housing_rooms r ON m.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                ORDER BY m.request_date DESC
                ''')
                headers = ['Request ID', 'Student ID', 'First Name', 'Last Name',
                          'Building', 'Room', 'Request Date', 'Issue Type',
                          'Description', 'Priority', 'Status', 'Assigned To', 'Completion Date']
            
            data = cursor.fetchall()
            conn.close()
            
            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(data)
            
            messagebox.showinfo("Success", f"{data_type.title()} data exported successfully to:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {str(e)}")

    def show_scheduled_reports_manager(self):
        """Show scheduled reports management window"""
        # Create window
        manager_window = tk.Toplevel(self.root)
        manager_window.title("Scheduled Reports Manager")
        manager_window.geometry("1000x600")

        # Main frame
        main_frame = ttk.Frame(manager_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text="Scheduled Reports Manager",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(button_frame, text="Add Schedule", width=15,
                  command=lambda: self.add_scheduled_report(manager_window, tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Edit Schedule", width=15,
                  command=lambda: self.edit_scheduled_report(tree, manager_window)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete Schedule", width=15,
                  command=lambda: self.delete_scheduled_report(tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Run Now", width=15,
                  command=lambda: self.run_scheduled_report_now(tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh", width=15,
                  command=lambda: self.load_scheduled_reports(tree)).pack(side='left', padx=5)

        # Tree view for scheduled reports
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True)

        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side='right', fill='y')

        tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set,
                           columns=('ID', 'Name', 'Type', 'Frequency', 'Recipients', 'Last Run', 'Next Run', 'Status'),
                           show='headings', height=15)

        tree.heading('ID', text='ID')
        tree.heading('Name', text='Report Name')
        tree.heading('Type', text='Report Type')
        tree.heading('Frequency', text='Frequency')
        tree.heading('Recipients', text='Recipients')
        tree.heading('Last Run', text='Last Run')
        tree.heading('Next Run', text='Next Run')
        tree.heading('Status', text='Status')

        tree.column('ID', width=50)
        tree.column('Name', width=150)
        tree.column('Type', width=120)
        tree.column('Frequency', width=100)
        tree.column('Recipients', width=200)
        tree.column('Last Run', width=100)
        tree.column('Next Run', width=100)
        tree.column('Status', width=80)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=tree.yview)

        # Load data
        self.load_scheduled_reports(tree)

        # Close button
        ttk.Button(main_frame, text="Close", command=manager_window.destroy).pack(pady=(10, 0))

    def load_scheduled_reports(self, tree):
        """Load scheduled reports into tree view"""
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT report_id, report_name, report_type, schedule_frequency,
                       recipients, last_run_date, next_run_date, is_active
                FROM scheduled_reports
                ORDER BY report_id DESC
            ''')

            reports = cursor.fetchall()
            conn.close()

            for report in reports:
                status = "Active" if report[7] else "Inactive"
                values = (
                    report[0],  # ID
                    report[1],  # Name
                    report[2],  # Type
                    report[3],  # Frequency
                    report[4],  # Recipients
                    report[5] if report[5] else 'Never',  # Last Run
                    report[6] if report[6] else 'Not Set',  # Next Run
                    status
                )
                tree.insert('', 'end', values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load scheduled reports: {str(e)}")

    def add_scheduled_report(self, parent_window, tree):
        """Add a new scheduled report"""
        dialog = tk.Toplevel(parent_window)
        dialog.title("Add Scheduled Report")
        dialog.geometry("600x550")
        dialog.transient(parent_window)

        ttk.Label(dialog, text="Add Scheduled Report",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Report Name
        ttk.Label(form_frame, text="Report Name:").grid(row=0, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5, padx=5)

        # Report Type
        ttk.Label(form_frame, text="Report Type:").grid(row=1, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value="Occupancy Report")
        ttk.Combobox(form_frame, textvariable=type_var, width=38,
                    values=['Occupancy Report', 'Financial Summary', 'Maintenance Summary', 'Room Availability'],
                    state='readonly').grid(row=1, column=1, pady=5, padx=5)

        # Frequency
        ttk.Label(form_frame, text="Frequency:").grid(row=2, column=0, sticky='w', pady=5)
        frequency_var = tk.StringVar(value="Weekly")
        ttk.Combobox(form_frame, textvariable=frequency_var, width=38,
                    values=['Daily', 'Weekly', 'Monthly', 'Quarterly'],
                    state='readonly').grid(row=2, column=1, pady=5, padx=5)

        # Recipients
        ttk.Label(form_frame, text="Recipients:").grid(row=3, column=0, sticky='nw', pady=5)
        ttk.Label(form_frame, text="(comma-separated emails)", font=('TkDefaultFont', 8)).grid(row=4, column=0, sticky='w')
        recipients_text = tk.Text(form_frame, height=4, width=40)
        recipients_text.grid(row=3, column=1, rowspan=2, pady=5, padx=5)

        # Active
        active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Active", variable=active_var).grid(row=5, column=1, sticky='w', pady=5)

        # Description
        ttk.Label(form_frame, text="Description:").grid(row=6, column=0, sticky='nw', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=40)
        desc_text.grid(row=6, column=1, pady=5, padx=5)

        def save_schedule():
            if not name_var.get().strip():
                messagebox.showwarning("Missing Info", "Please enter a report name", parent=dialog)
                return

            recipients = recipients_text.get("1.0", tk.END).strip()
            if not recipients:
                messagebox.showwarning("Missing Info", "Please enter at least one recipient email", parent=dialog)
                return

            try:
                # Calculate next run date based on frequency
                from datetime import datetime, timedelta
                now = datetime.now()
                frequency = frequency_var.get()

                if frequency == 'Daily':
                    next_run = (now + timedelta(days=1)).strftime('%Y-%m-%d 08:00:00')
                elif frequency == 'Weekly':
                    next_run = (now + timedelta(weeks=1)).strftime('%Y-%m-%d 08:00:00')
                elif frequency == 'Monthly':
                    next_run = (now + timedelta(days=30)).strftime('%Y-%m-%d 08:00:00')
                else:  # Quarterly
                    next_run = (now + timedelta(days=90)).strftime('%Y-%m-%d 08:00:00')

                config = {
                    'description': desc_text.get("1.0", tk.END).strip()
                }

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO scheduled_reports
                    (report_name, report_type, schedule_frequency, recipients, next_run_date, is_active, report_config)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name_var.get().strip(), type_var.get(), frequency_var.get(),
                     recipients, next_run, int(active_var.get()), str(config)))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Scheduled report added successfully!", parent=dialog)
                dialog.destroy()
                self.load_scheduled_reports(tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add scheduled report: {str(e)}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=save_schedule).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def edit_scheduled_report(self, tree, parent_window):
        """Edit an existing scheduled report"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scheduled report to edit", parent=parent_window)
            return

        report_id = tree.item(selection[0], 'values')[0]

        # Implementation similar to add_scheduled_report but with pre-filled values
        messagebox.showinfo("Coming Soon", "Edit functionality will be available in the next update", parent=parent_window)

    def delete_scheduled_report(self, tree):
        """Delete a scheduled report"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scheduled report to delete")
            return

        values = tree.item(selection[0], 'values')
        report_id = values[0]
        report_name = values[1]

        result = messagebox.askyesno("Confirm Delete",
                                     f"Delete scheduled report '{report_name}'?\n\nThis will stop all future report generation and emails.")
        if result:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM scheduled_reports WHERE report_id = ?', (report_id,))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Scheduled report '{report_name}' deleted successfully")
                self.load_scheduled_reports(tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete scheduled report: {str(e)}")

    def run_scheduled_report_now(self, tree):
        """Run a scheduled report immediately"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scheduled report to run")
            return

        values = tree.item(selection[0], 'values')
        report_id = values[0]
        report_name = values[1]
        report_type = values[2]
        recipients = values[4]

        result = messagebox.askyesno("Confirm Run",
                                     f"Run '{report_name}' now and email to:\n{recipients}?")
        if result:
            try:
                # Generate report content based on type
                if report_type == 'Occupancy Report':
                    report_content = self.generate_occupancy_report_content()
                elif report_type == 'Financial Summary':
                    report_content = self.generate_financial_report_content()
                elif report_type == 'Maintenance Summary':
                    report_content = self.generate_maintenance_report_content()
                elif report_type == 'Room Availability':
                    report_content = self.generate_room_availability_content()
                else:
                    messagebox.showerror("Error", "Unknown report type")
                    return

                # Send email to recipients
                from university_system.infrastructure.email.email_service import send_email

                recipient_list = [email.strip() for email in recipients.split(',')]

                for recipient in recipient_list:
                    if recipient:
                        success = send_email(
                            recipient_email=recipient,
                            subject=f"Housing Report: {report_name}",
                            body=f"Automated Housing Report\n\n{report_content}"
                        )

                # Update last run date
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE scheduled_reports
                    SET last_run_date = datetime('now')
                    WHERE report_id = ?
                ''', (report_id,))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Report '{report_name}' generated and emailed successfully!")
                self.load_scheduled_reports(tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to run report: {str(e)}")

    def generate_occupancy_report_content(self):
        """Generate occupancy report content (returns string)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "HOUSING OCCUPANCY REPORT\n"
            report_content += "=" * 50 + "\n\n"

            cursor.execute('SELECT COUNT(*) FROM housing_buildings')
            total_buildings = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms')
            total_rooms = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Occupied"')
            occupied_rooms = cursor.fetchone()[0]

            occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0

            report_content += f"Total Buildings: {total_buildings}\n"
            report_content += f"Total Rooms: {total_rooms}\n"
            report_content += f"Occupied Rooms: {occupied_rooms}\n"
            report_content += f"Occupancy Rate: {occupancy_rate:.1f}%\n"

            conn.close()
            return report_content

        except Exception as e:
            return f"Error generating report: {str(e)}"

    def generate_financial_report_content(self):
        """Generate financial report content (returns string)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "HOUSING FINANCIAL SUMMARY\n"
            report_content += "=" * 50 + "\n\n"

            cursor.execute('SELECT SUM(monthly_rent) FROM housing_assignments WHERE status = "Active"')
            monthly_revenue = cursor.fetchone()[0] or 0

            report_content += f"Current Monthly Revenue: ${monthly_revenue:,.2f}\n"
            report_content += f"Projected Annual Revenue: ${monthly_revenue * 12:,.2f}\n"

            conn.close()
            return report_content

        except Exception as e:
            return f"Error generating report: {str(e)}"

    def generate_maintenance_report_content(self):
        """Generate maintenance report content (returns string)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "MAINTENANCE REQUESTS SUMMARY\n"
            report_content += "=" * 40 + "\n\n"

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests')
            total_requests = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Open"')
            open_requests = cursor.fetchone()[0]

            report_content += f"Total Requests: {total_requests}\n"
            report_content += f"Open Requests: {open_requests}\n"

            conn.close()
            return report_content

        except Exception as e:
            return f"Error generating report: {str(e)}"

    def generate_room_availability_content(self):
        """Generate room availability report content (returns string)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            report_content = "ROOM AVAILABILITY REPORT\n"
            report_content += "=" * 35 + "\n\n"

            cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Available"')
            available_rooms = cursor.fetchone()[0]

            report_content += f"Available Rooms: {available_rooms}\n"

            conn.close()
            return report_content

        except Exception as e:
            return f"Error generating report: {str(e)}"

    def show_report_template_settings(self):
        """Show report template customization settings"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Report Template Settings")
        settings_window.geometry("700x650")

        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Report Template Settings",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Load current settings or create defaults
        template_file = "/home/seancatchpole989/university_system/data/report_templates.json"
        default_settings = {
            'title_font': 'Arial',
            'title_size': 16,
            'content_font': 'Courier',
            'content_size': 10,
            'line_spacing': 1.2,
            'page_width': 80,
            'include_timestamp': True,
            'include_generator_name': True,
            'section_separator': '=',
            'subsection_separator': '-',
            'currency_symbol': '$',
            'date_format': '%Y-%m-%d',
            'header_text': 'Housing Management Report',
            'footer_text': 'Generated by University Housing System'
        }

        try:
            import json
            import os
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    current_settings = json.load(f)
            else:
                current_settings = default_settings.copy()
        except:
            current_settings = default_settings.copy()

        # Create form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Title Font
        ttk.Label(form_frame, text="Title Font:").grid(row=0, column=0, sticky='w', pady=5)
        title_font_var = tk.StringVar(value=current_settings.get('title_font', 'Arial'))
        ttk.Combobox(form_frame, textvariable=title_font_var, width=30,
                    values=['Arial', 'Helvetica', 'Times New Roman', 'Courier', 'Verdana'],
                    state='readonly').grid(row=0, column=1, pady=5, padx=5, sticky='w')

        # Title Size
        ttk.Label(form_frame, text="Title Size:").grid(row=1, column=0, sticky='w', pady=5)
        title_size_var = tk.IntVar(value=current_settings.get('title_size', 16))
        ttk.Spinbox(form_frame, from_=10, to=24, textvariable=title_size_var, width=10).grid(row=1, column=1, pady=5, padx=5, sticky='w')

        # Content Font
        ttk.Label(form_frame, text="Content Font:").grid(row=2, column=0, sticky='w', pady=5)
        content_font_var = tk.StringVar(value=current_settings.get('content_font', 'Courier'))
        ttk.Combobox(form_frame, textvariable=content_font_var, width=30,
                    values=['Arial', 'Helvetica', 'Times New Roman', 'Courier', 'Verdana'],
                    state='readonly').grid(row=2, column=1, pady=5, padx=5, sticky='w')

        # Content Size
        ttk.Label(form_frame, text="Content Size:").grid(row=3, column=0, sticky='w', pady=5)
        content_size_var = tk.IntVar(value=current_settings.get('content_size', 10))
        ttk.Spinbox(form_frame, from_=8, to=14, textvariable=content_size_var, width=10).grid(row=3, column=1, pady=5, padx=5, sticky='w')

        # Line Spacing
        ttk.Label(form_frame, text="Line Spacing:").grid(row=4, column=0, sticky='w', pady=5)
        line_spacing_var = tk.DoubleVar(value=current_settings.get('line_spacing', 1.2))
        ttk.Spinbox(form_frame, from_=1.0, to=2.0, increment=0.1, textvariable=line_spacing_var, width=10).grid(row=4, column=1, pady=5, padx=5, sticky='w')

        # Page Width
        ttk.Label(form_frame, text="Page Width (chars):").grid(row=5, column=0, sticky='w', pady=5)
        page_width_var = tk.IntVar(value=current_settings.get('page_width', 80))
        ttk.Spinbox(form_frame, from_=60, to=120, textvariable=page_width_var, width=10).grid(row=5, column=1, pady=5, padx=5, sticky='w')

        # Section Separator
        ttk.Label(form_frame, text="Section Separator:").grid(row=6, column=0, sticky='w', pady=5)
        section_sep_var = tk.StringVar(value=current_settings.get('section_separator', '='))
        ttk.Combobox(form_frame, textvariable=section_sep_var, width=30,
                    values=['=', '-', '#', '*', '_', '~'],
                    state='readonly').grid(row=6, column=1, pady=5, padx=5, sticky='w')

        # Subsection Separator
        ttk.Label(form_frame, text="Subsection Separator:").grid(row=7, column=0, sticky='w', pady=5)
        subsection_sep_var = tk.StringVar(value=current_settings.get('subsection_separator', '-'))
        ttk.Combobox(form_frame, textvariable=subsection_sep_var, width=30,
                    values=['=', '-', '#', '*', '_', '~'],
                    state='readonly').grid(row=7, column=1, pady=5, padx=5, sticky='w')

        # Currency Symbol
        ttk.Label(form_frame, text="Currency Symbol:").grid(row=8, column=0, sticky='w', pady=5)
        currency_var = tk.StringVar(value=current_settings.get('currency_symbol', '$'))
        ttk.Entry(form_frame, textvariable=currency_var, width=10).grid(row=8, column=1, pady=5, padx=5, sticky='w')

        # Date Format
        ttk.Label(form_frame, text="Date Format:").grid(row=9, column=0, sticky='w', pady=5)
        date_format_var = tk.StringVar(value=current_settings.get('date_format', '%Y-%m-%d'))
        ttk.Combobox(form_frame, textvariable=date_format_var, width=30,
                    values=['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y'],
                    state='readonly').grid(row=9, column=1, pady=5, padx=5, sticky='w')

        # Include Timestamp
        include_timestamp_var = tk.BooleanVar(value=current_settings.get('include_timestamp', True))
        ttk.Checkbutton(form_frame, text="Include Timestamp", variable=include_timestamp_var).grid(row=10, column=1, sticky='w', pady=5)

        # Include Generator Name
        include_generator_var = tk.BooleanVar(value=current_settings.get('include_generator_name', True))
        ttk.Checkbutton(form_frame, text="Include Generator Name", variable=include_generator_var).grid(row=11, column=1, sticky='w', pady=5)

        # Header Text
        ttk.Label(form_frame, text="Header Text:").grid(row=12, column=0, sticky='w', pady=5)
        header_var = tk.StringVar(value=current_settings.get('header_text', 'Housing Management Report'))
        ttk.Entry(form_frame, textvariable=header_var, width=40).grid(row=12, column=1, pady=5, padx=5, sticky='w')

        # Footer Text
        ttk.Label(form_frame, text="Footer Text:").grid(row=13, column=0, sticky='w', pady=5)
        footer_var = tk.StringVar(value=current_settings.get('footer_text', 'Generated by University Housing System'))
        ttk.Entry(form_frame, textvariable=footer_var, width=40).grid(row=13, column=1, pady=5, padx=5, sticky='w')

        def save_settings():
            try:
                new_settings = {
                    'title_font': title_font_var.get(),
                    'title_size': title_size_var.get(),
                    'content_font': content_font_var.get(),
                    'content_size': content_size_var.get(),
                    'line_spacing': line_spacing_var.get(),
                    'page_width': page_width_var.get(),
                    'include_timestamp': include_timestamp_var.get(),
                    'include_generator_name': include_generator_var.get(),
                    'section_separator': section_sep_var.get(),
                    'subsection_separator': subsection_sep_var.get(),
                    'currency_symbol': currency_var.get(),
                    'date_format': date_format_var.get(),
                    'header_text': header_var.get(),
                    'footer_text': footer_var.get()
                }

                import json
                import os
                os.makedirs(os.path.dirname(template_file), exist_ok=True)
                with open(template_file, 'w') as f:
                    json.dump(new_settings, f, indent=4)

                messagebox.showinfo("Success", "Report template settings saved successfully!", parent=settings_window)
                settings_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {str(e)}", parent=settings_window)

        def reset_to_defaults():
            result = messagebox.askyesno("Reset to Defaults",
                                         "Reset all template settings to default values?",
                                         parent=settings_window)
            if result:
                try:
                    import json
                    with open(template_file, 'w') as f:
                        json.dump(default_settings, f, indent=4)

                    messagebox.showinfo("Success", "Settings reset to defaults. Please reopen this window to see changes.",
                                      parent=settings_window)
                    settings_window.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to reset settings: {str(e)}", parent=settings_window)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save Settings", width=15, command=save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", width=18, command=reset_to_defaults).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", width=15, command=settings_window.destroy).pack(side='left', padx=5)

        # Preview section
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="10")
        preview_frame.pack(fill='x', pady=(10, 0))

        preview_text = f"""Font: {content_font_var.get()} {content_size_var.get()}pt
Header: {header_var.get()}
Section Sep: {section_sep_var.get() * 20}
Currency: {currency_var.get()}1,234.56
Footer: {footer_var.get()}"""

        ttk.Label(preview_frame, text=preview_text, font=(current_settings.get('content_font', 'Courier'), 9)).pack()

    def get_report_template_settings(self):
        """Load report template settings from file"""
        template_file = "/home/seancatchpole989/university_system/data/report_templates.json"
        default_settings = {
            'title_font': 'Arial',
            'title_size': 16,
            'content_font': 'Courier',
            'content_size': 10,
            'line_spacing': 1.2,
            'page_width': 80,
            'include_timestamp': True,
            'include_generator_name': True,
            'section_separator': '=',
            'subsection_separator': '-',
            'currency_symbol': '$',
            'date_format': '%Y-%m-%d',
            'header_text': 'Housing Management Report',
            'footer_text': 'Generated by University Housing System'
        }

        try:
            import json
            import os
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    return json.load(f)
        except:
            pass

        return default_settings

    # Student-specific interface methods
    def show_student_dashboard(self):
        """Show student dashboard"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="My Housing Dashboard", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        try:
            # Get student ID
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            
            if not result:
                ttk.Label(self.content_frame, text="No student ID associated with your account",
                         foreground='red').pack()
                conn.close()
                return
            
            student_id = result[0]
            
            # Get student info
            cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (student_id,))
            student_info = cursor.fetchone()
            
            if student_info:
                welcome_text = f"Welcome, {student_info[0]} {student_info[1]} ({student_id})"
                ttk.Label(self.content_frame, text=welcome_text, 
                         font=('Arial', 12)).pack(pady=(0, 20))
            
            # Create info panels
            info_frame = ttk.Frame(self.content_frame)
            info_frame.pack(fill='both', expand=True)
            
            # Application status
            app_frame = ttk.LabelFrame(info_frame, text="Application Status", padding="20")
            app_frame.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')
            
            cursor.execute('''
            SELECT application_id, status, application_date, review_date
            FROM housing_applications 
            WHERE student_id = ? 
            ORDER BY application_date DESC LIMIT 1
            ''', (student_id,))
            
            application = cursor.fetchone()
            
            if application:
                ttk.Label(app_frame, text=f"Latest Application: {application[0]}").pack(anchor='w')
                ttk.Label(app_frame, text=f"Status: {application[1]}").pack(anchor='w')
                ttk.Label(app_frame, text=f"Applied: {application[2]}").pack(anchor='w')
                if application[3]:
                    ttk.Label(app_frame, text=f"Reviewed: {application[3]}").pack(anchor='w')
            else:
                ttk.Label(app_frame, text="No applications found").pack()
            
            # Housing assignment
            assign_frame = ttk.LabelFrame(info_frame, text="Housing Assignment", padding="20")
            assign_frame.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')
            
            cursor.execute('''
            SELECT a.assignment_id, r.room_number, b.building_name, a.move_in_date, 
                   a.planned_move_out_date, a.monthly_rent, a.status
            FROM housing_assignments a
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.student_id = ? AND a.status = 'Active'
            ''', (student_id,))
            
            assignment = cursor.fetchone()
            
            if assignment:
                ttk.Label(assign_frame, text=f"Room: {assignment[1]}").pack(anchor='w')
                ttk.Label(assign_frame, text=f"Building: {assignment[2]}").pack(anchor='w')
                ttk.Label(assign_frame, text=f"Move-in: {assignment[3]}").pack(anchor='w')
                ttk.Label(assign_frame, text=f"Rent: ${assignment[5]}/month").pack(anchor='w')
            else:
                ttk.Label(assign_frame, text="No active housing assignment").pack()
            
            # Maintenance requests
            maint_frame = ttk.LabelFrame(info_frame, text="Maintenance Requests", padding="20")
            maint_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')
            
            cursor.execute('''
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open,
                   SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress
            FROM housing_maintenance_requests 
            WHERE student_id = ?
            ''', (student_id,))
            
            maint_stats = cursor.fetchone()
            
            ttk.Label(maint_frame, text=f"Total Requests: {maint_stats[0]}").pack(anchor='w')
            ttk.Label(maint_frame, text=f"Open: {maint_stats[1]}").pack(anchor='w')
            ttk.Label(maint_frame, text=f"In Progress: {maint_stats[2]}").pack(anchor='w')
            
            # Configure grid weights
            info_frame.columnconfigure(0, weight=1)
            info_frame.columnconfigure(1, weight=1)
            info_frame.rowconfigure(0, weight=1)
            info_frame.rowconfigure(1, weight=1)
            
            conn.close()
            
        except Exception as e:
            ttk.Label(self.content_frame, text=f"Error loading dashboard: {str(e)}",
                     foreground='red').pack()
    
    def show_student_application(self):
        """Show student application interface"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="My Housing Application", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create notebook
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True)
        
        # My applications tab
        my_apps_frame = ttk.Frame(notebook, padding="10")
        notebook.add(my_apps_frame, text="My Applications")
        self.show_my_applications(my_apps_frame)
        
        # New application tab
        new_app_frame = ttk.Frame(notebook, padding="10")
        notebook.add(new_app_frame, text="Apply for Housing")
        self.create_new_application_form(new_app_frame)
    
    def show_my_applications(self, parent):
        """Show student's applications"""
        try:
            # Get student ID
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            
            if not result:
                ttk.Label(parent, text="No student ID associated with your account",
                         foreground='red').pack()
                conn.close()
                return
            
            student_id = result[0]
            
            # Get applications
            cursor.execute('''
            SELECT a.application_id, a.application_date, a.preferred_room_type, 
                   a.requested_move_in_date, a.requested_duration_months, a.status, 
                   a.review_date, b.building_name, a.special_requirements, a.notes
            FROM housing_applications a
            LEFT JOIN housing_buildings b ON a.preferred_building_id = b.building_id
            WHERE a.student_id = ?
            ORDER BY a.application_date DESC
            ''', (student_id,))
            
            applications = cursor.fetchall()
            conn.close()
            
            if not applications:
                ttk.Label(parent, text="You have no housing applications.",
                         font=('Arial', 12)).pack(pady=20)
                return
            
            # Display applications
            for i, app in enumerate(applications):
                app_frame = ttk.LabelFrame(parent, text=f"Application {app[0]}", padding="15")
                app_frame.pack(fill='x', pady=10)
                
                details_frame = ttk.Frame(app_frame)
                details_frame.pack(fill='x')
                
                # Left column
                left_frame = ttk.Frame(details_frame)
                left_frame.pack(side='left', fill='both', expand=True)
                
                ttk.Label(left_frame, text=f"Applied: {app[1]}").pack(anchor='w')
                ttk.Label(left_frame, text=f"Room Type: {app[2]}").pack(anchor='w')
                ttk.Label(left_frame, text=f"Move-in Date: {app[3]}").pack(anchor='w')
                ttk.Label(left_frame, text=f"Duration: {app[4]} months").pack(anchor='w')
                
                # Right column
                right_frame = ttk.Frame(details_frame)
                right_frame.pack(side='right', fill='both', expand=True)
                
                status_color = 'green' if app[5] == 'Approved' else 'red' if app[5] == 'Rejected' else 'blue'
                ttk.Label(right_frame, text=f"Status: {app[5]}", 
                         foreground=status_color, font=('Arial', 10, 'bold')).pack(anchor='w')
                
                if app[6]:
                    ttk.Label(right_frame, text=f"Reviewed: {app[6]}").pack(anchor='w')
                
                if app[7]:
                    ttk.Label(right_frame, text=f"Preferred Building: {app[7]}").pack(anchor='w')
                
                if app[8]:
                    ttk.Label(left_frame, text=f"Special Requirements: {app[8]}").pack(anchor='w', pady=(5, 0))
                
                if app[9]:
                    ttk.Label(app_frame, text=f"Notes: {app[9]}", 
                             wraplength=600).pack(anchor='w', pady=(5, 0))
                
        except Exception as e:
            ttk.Label(parent, text=f"Error loading applications: {str(e)}",
                     foreground='red').pack()
    
    def show_student_assignment(self):
        """Show student's housing assignment"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="My Housing Assignment", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        try:
            # Get student ID
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            
            if not result:
                ttk.Label(self.content_frame, text="No student ID associated with your account",
                         foreground='red').pack()
                conn.close()
                return
                
            student_id = result[0]
            
            # Get assignment details
            cursor.execute('''
            SELECT a.assignment_id, a.room_id, r.room_number, r.floor_number, r.room_type,
                   b.building_name, b.address, a.move_in_date, a.planned_move_out_date,
                   a.contract_number, a.monthly_rent, a.status, a.created_at
            FROM housing_assignments a
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.student_id = ?
            ORDER BY a.created_at DESC
            ''', (student_id,))
            
            assignments = cursor.fetchall()
            
            if not assignments:
                ttk.Label(self.content_frame, text="You do not have any housing assignments.",
                         font=('Arial', 12)).pack(pady=20)
                conn.close()
                return
            
            # Show current assignment
            current_assignment = assignments[0]
            
            # Assignment details frame
            details_frame = ttk.LabelFrame(self.content_frame, text="Assignment Details", padding="20")
            details_frame.pack(fill='x', pady=(0, 20))
            
            # Create two columns
            left_frame = ttk.Frame(details_frame)
            left_frame.pack(side='left', fill='both', expand=True)
            
            right_frame = ttk.Frame(details_frame)
            right_frame.pack(side='right', fill='both', expand=True)
            
            # Left column
            ttk.Label(left_frame, text=f"Assignment ID: {current_assignment[0]}", 
                     font=('Arial', 10, 'bold')).pack(anchor='w', pady=2)
            ttk.Label(left_frame, text=f"Room: {current_assignment[2]}").pack(anchor='w', pady=2)
            ttk.Label(left_frame, text=f"Floor: {current_assignment[3]}").pack(anchor='w', pady=2)
            ttk.Label(left_frame, text=f"Room Type: {current_assignment[4]}").pack(anchor='w', pady=2)
            ttk.Label(left_frame, text=f"Building: {current_assignment[5]}").pack(anchor='w', pady=2)
            ttk.Label(left_frame, text=f"Address: {current_assignment[6]}").pack(anchor='w', pady=2)
            
            # Right column
            status_color = 'green' if current_assignment[11] == 'Active' else 'red'
            ttk.Label(right_frame, text=f"Status: {current_assignment[11]}", 
                     foreground=status_color, font=('Arial', 10, 'bold')).pack(anchor='w', pady=2)
            ttk.Label(right_frame, text=f"Move-in Date: {current_assignment[7]}").pack(anchor='w', pady=2)
            ttk.Label(right_frame, text=f"Move-out Date: {current_assignment[8]}").pack(anchor='w', pady=2)
            ttk.Label(right_frame, text=f"Contract: {current_assignment[9]}").pack(anchor='w', pady=2)
            ttk.Label(right_frame, text=f"Monthly Rent: ${current_assignment[10]}").pack(anchor='w', pady=2)
            ttk.Label(right_frame, text=f"Assigned: {current_assignment[12]}").pack(anchor='w', pady=2)
            
            # Payment history
            payment_frame = ttk.LabelFrame(self.content_frame, text="Payment History", padding="20")
            payment_frame.pack(fill='both', expand=True)
            
            cursor.execute('''
            SELECT p.payment_id, p.amount, p.payment_date, p.payment_method,
                   p.payment_period_start, p.payment_period_end, p.status
            FROM housing_payments p
            WHERE p.student_id = ?
            ORDER BY p.payment_date DESC
            LIMIT 10
            ''', (student_id,))
            
            payments = cursor.fetchall()
            
            if payments:
                # Create treeview for payments
                columns = ('Payment ID', 'Amount', 'Date', 'Method', 'Period', 'Status')
                payment_tree = ttk.Treeview(payment_frame, columns=columns, show='headings', height=8)
                
                for col in columns:
                    payment_tree.heading(col, text=col)
                    if col == 'Amount':
                        payment_tree.column(col, width=80, anchor='e')
                    else:
                        payment_tree.column(col, width=100)
                
                for payment in payments:
                    period = f"{payment[4]} to {payment[5]}"
                    payment_tree.insert('', 'end', values=(
                        payment[0], f"${payment[1]:.2f}", payment[2], 
                        payment[3], period, payment[6]
                    ))
                
                payment_tree.pack(fill='both', expand=True)
            else:
                ttk.Label(payment_frame, text="No payment records found").pack()
            
            conn.close()
            
        except Exception as e:
            ttk.Label(self.content_frame, text=f"Error loading assignment: {str(e)}",
                     foreground='red').pack()
    
    def show_student_maintenance(self):
        """Show student maintenance requests interface"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="My Maintenance Requests", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create notebook
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True)
        
        # My requests tab
        my_requests_frame = ttk.Frame(notebook, padding="10")
        notebook.add(my_requests_frame, text="My Requests")
        self.show_my_maintenance_requests(my_requests_frame)
        
        # New request tab
        new_request_frame = ttk.Frame(notebook, padding="10")
        notebook.add(new_request_frame, text="New Request")
        self.create_student_maintenance_form(new_request_frame)
    
    def show_my_maintenance_requests(self, parent):
        """Show student's maintenance requests"""
        try:
            # Get student ID
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            
            if not result:
                ttk.Label(parent, text="No student ID associated with your account",
                         foreground='red').pack()
                conn.close()
                return
            
            student_id = result[0]
            
            # Get maintenance requests
            cursor.execute('''
            SELECT m.request_id, m.request_date, m.issue_type, m.description, m.priority,
                   m.status, m.assigned_to, m.scheduled_date, m.completion_date,
                   r.room_number, b.building_name
            FROM housing_maintenance_requests m
            JOIN housing_rooms r ON m.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE m.student_id = ?
            ORDER BY m.request_date DESC
            ''', (student_id,))
            
            requests = cursor.fetchall()
            conn.close()
            
            if not requests:
                ttk.Label(parent, text="You have no maintenance requests.",
                         font=('Arial', 12)).pack(pady=20)
                return
            
            # Create scrollable frame for requests
            canvas = tk.Canvas(parent)
            scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Display requests
            for req in requests:
                req_frame = ttk.LabelFrame(scrollable_frame, text=f"Request {req[0]}", padding="15")
                req_frame.pack(fill='x', pady=10, padx=10)
                
                # Request details
                info_frame = ttk.Frame(req_frame)
                info_frame.pack(fill='x')
                
                # Left column
                left_frame = ttk.Frame(info_frame)
                left_frame.pack(side='left', fill='both', expand=True)
                
                ttk.Label(left_frame, text=f"Date: {req[1]}").pack(anchor='w')
                ttk.Label(left_frame, text=f"Issue: {req[2]}").pack(anchor='w')
                ttk.Label(left_frame, text=f"Room: {req[9]} in {req[10]}").pack(anchor='w')
                ttk.Label(left_frame, text=f"Priority: {req[4]}").pack(anchor='w')
                
                # Right column
                right_frame = ttk.Frame(info_frame)
                right_frame.pack(side='right', fill='both', expand=True)
                
                status_color = 'green' if req[5] == 'Complete' else 'blue' if req[5] == 'In Progress' else 'orange'
                ttk.Label(right_frame, text=f"Status: {req[5]}", 
                         foreground=status_color, font=('Arial', 10, 'bold')).pack(anchor='w')
                
                if req[6]:
                    ttk.Label(right_frame, text=f"Assigned to: {req[6]}").pack(anchor='w')
                if req[7]:
                    ttk.Label(right_frame, text=f"Scheduled: {req[7]}").pack(anchor='w')
                if req[8]:
                    ttk.Label(right_frame, text=f"Completed: {req[8]}").pack(anchor='w')
                
                # Description
                ttk.Label(req_frame, text=f"Description: {req[3]}", 
                         wraplength=600).pack(anchor='w', pady=(10, 0))
                
        except Exception as e:
            ttk.Label(parent, text=f"Error loading requests: {str(e)}",
                     foreground='red').pack()
    
    def create_student_maintenance_form(self, parent):
        """Create maintenance request form for students"""
        try:
            # Get student's room info
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            
            if not result:
                ttk.Label(parent, text="No student ID associated with your account",
                         foreground='red').pack()
                conn.close()
                return
            
            student_id = result[0]
            
            # Get active housing assignment
            cursor.execute('''
            SELECT a.room_id, r.room_number, b.building_name
            FROM housing_assignments a
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.student_id = ? AND a.status = 'Active'
            ''', (student_id,))
            
            room_info = cursor.fetchone()
            conn.close()
            
            if not room_info:
                ttk.Label(parent, text="You do not have an active housing assignment.",
                         font=('Arial', 12)).pack(pady=20)
                return
            
            # Display room info
            room_frame = ttk.LabelFrame(parent, text="Your Room", padding="10")
            room_frame.pack(fill='x', pady=(0, 20))
            
            ttk.Label(room_frame, text=f"Room: {room_info[1]} in {room_info[2]}",
                     font=('Arial', 12, 'bold')).pack()
            
            # Request form
            form_frame = ttk.LabelFrame(parent, text="Maintenance Request", padding="20")
            form_frame.pack(fill='both', expand=True)
            
            # Issue type
            ttk.Label(form_frame, text="Issue Type:").grid(row=0, column=0, sticky='w', pady=10)
            self.student_issue_combo = ttk.Combobox(form_frame, width=30,
                                                  values=["Plumbing", "Electrical", "HVAC", "Appliance", 
                                                         "Furniture", "Pest Control", "Lock/Key", "Cleaning", "Other"])
            self.student_issue_combo.grid(row=0, column=1, padx=10, sticky='w')
            
            # Priority
            ttk.Label(form_frame, text="Priority:").grid(row=1, column=0, sticky='w', pady=10)
            self.student_priority_combo = ttk.Combobox(form_frame, width=30,
                                                     values=["Low", "Medium", "High", "Emergency"])
            self.student_priority_combo.set("Medium")
            self.student_priority_combo.grid(row=1, column=1, padx=10, sticky='w')
            
            # Description
            ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=10)
            self.student_description_text = tk.Text(form_frame, width=50, height=8)
            self.student_description_text.grid(row=2, column=1, padx=10, pady=10)
            
            # Submit button
            ttk.Button(form_frame, text="Submit Request", 
                      command=self.submit_student_maintenance_request).grid(row=3, column=0, pady=20)
            
        except Exception as e:
            ttk.Label(parent, text=f"Error loading form: {str(e)}",
                     foreground='red').pack()
    
    def submit_student_maintenance_request(self):
        """Submit student maintenance request"""
        try:
            issue_type = self.student_issue_combo.get()
            priority = self.student_priority_combo.get()
            description = self.student_description_text.get('1.0', tk.END).strip()
            
            if not all([issue_type, priority, description]):
                messagebox.showerror("Error", "Please fill in all fields")
                return
            
            # Get student info
            conn = get_connection()
            cursor = conn.cursor()

            # Try to get student_id from auth or students table
            if self.auth and self.auth.current_user:
                # First check if username IS the student_id
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?',
                             (self.auth.current_user.get('username', ''),))
                result = cursor.fetchone()

                if not result:
                    # Try matching by email
                    cursor.execute('SELECT student_id FROM students WHERE email_address = ?',
                                 (self.auth.current_user.get('email', ''),))
                    result = cursor.fetchone()

                if not result:
                    messagebox.showerror("Error", "No student record found for your account.\n"
                                       "Please contact housing administration.")
                    conn.close()
                    return

                student_id = result[0]
            else:
                messagebox.showerror("Error", "Authentication required")
                conn.close()
                return
            
            # Get room info
            cursor.execute('''
            SELECT a.room_id
            FROM housing_assignments a
            WHERE a.student_id = ? AND a.status = 'Active'
            ''', (student_id,))
            
            room_result = cursor.fetchone()
            if not room_result:
                messagebox.showerror("Error", "No active housing assignment found")
                conn.close()
                return
            
            room_id = room_result[0]
            
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
            
            messagebox.showinfo("Success", f"Maintenance request submitted successfully!\n"
                                         f"Request ID: {request_id}\n\n"
                                         f"You will be notified when it is processed.")
            
            # Clear form
            self.student_issue_combo.set("")
            self.student_priority_combo.set("Medium")
            self.student_description_text.delete('1.0', tk.END)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit request: {str(e)}")
    
    # View-only methods for staff with limited permissions
    def show_building_view(self):
        """Show buildings view for staff with view-only permissions"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Buildings Overview", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create simple list view
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True)
        
        columns = ('Building Name', 'Location', 'Total Rooms', 'Available', 'Occupancy %')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load data
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT building_name, campus_location, total_rooms, available_rooms,
                   ROUND((CAST(total_rooms - available_rooms AS FLOAT) / total_rooms) * 100, 1) as occupancy_rate
            FROM housing_buildings
            ORDER BY building_name
            ''')
            
            buildings = cursor.fetchall()
            
            for building in buildings:
                occupancy = f"{building[4]}%" if building[4] is not None else "0%"
                tree.insert('', 'end', values=(
                    building[0], building[1], building[2], building[3], occupancy
                ))
            
            conn.close()
            
        except Exception as e:
            ttk.Label(list_frame, text=f"Error loading buildings: {str(e)}",
                     foreground='red').pack()
    
    def show_applications_view(self):
        """Show applications view for staff with view-only permissions"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Housing Applications", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Simple applications list
        self.create_applications_list(self.content_frame)
    
    def show_assignments_view(self):
        """Show assignments view for staff with view-only permissions"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Housing Assignments", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Simple assignments list without edit capabilities
        main_frame = ttk.Frame(self.content_frame)
        main_frame.pack(fill='both', expand=True)
        
        columns = ('Student', 'Room', 'Building', 'Move-in', 'Status')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings')
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load data
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT s.first_name, s.last_name, r.room_number, b.building_name,
                   a.move_in_date, a.status
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY a.created_at DESC
            LIMIT 100
            ''')
            
            assignments = cursor.fetchall()
            
            for assign in assignments:
                student_name = f"{assign[0]} {assign[1]}"
                tree.insert('', 'end', values=(
                    student_name, assign[2], assign[3], assign[4], assign[5]
                ))
            
            conn.close()
            
        except Exception as e:
            ttk.Label(main_frame, text=f"Error loading assignments: {str(e)}",
                     foreground='red').pack()
    
    def show_maintenance_view(self):
        """Show maintenance requests view for staff with view-only permissions"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Maintenance Requests", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create read-only maintenance list
        self.create_maintenance_list(self.content_frame)
    
    def show_payments_view(self):
        """Show payments view for staff with view-only permissions"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Payment History", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create read-only payment history
        self.create_payment_history(self.content_frame)
    
    def launch_classic_interface(self):
        """Launch the classic command-line interface for backward compatibility"""
        try:
            # Import and run the original housing menu
            orig_display_housing_accommodation_menu(self.auth)  # Pass the auth instance
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch classic interface: {str(e)}")
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

# Backward compatibility wrapper functions
def display_housing_accommodation_menu_gui(auth_instance=None):
    """GUI version of the housing accommodation menu"""
    app = HousingGUI(auth_instance)
    app.run()

# Main entry point
if __name__ == "__main__":
    # Create a basic auth instance for testing
    class TestAuth:
        def __init__(self):
            self.current_user = {
                'id': 1,
                'username': 'admin',
                'role': 'admin'
            }
        
        def check_permission(self, permission):
            # For testing, grant all permissions
            return True
    
    test_auth = TestAuth()
    app = HousingGUI(test_auth)
    app.run()

# Export functions for backward compatibility
__all__ = [
    'HousingGUI',
    'display_housing_accommodation_menu_gui',
    'orig_init_housing_db',  # These should reference the orig_ versions
    'orig_generate_id',
    'orig_set_auth',
    'orig_select_student',
    'orig_create_building',
    'orig_view_building',
    'orig_update_building',
    'orig_delete_building',
    'orig_create_rooms_for_building',
    'orig_create_application',
    'orig_process_application',
    'orig_view_application',
    'orig_view_assignment',
    'orig_update_assignment_status',
    'orig_create_maintenance_request',
    'orig_view_maintenance_requests',
    'orig_update_maintenance_request',
    'orig_record_payment',
    'orig_view_payment_history',
    'orig_manage_inventory',
    'orig_create_inspection',
    'orig_view_inspections',
    'orig_generate_occupancy_report',
    'orig_generate_financial_report',
    'orig_export_housing_data',
    'orig_search_housing_records',
    'orig_check_room_availability',
    'orig_maintenance_summary',
    'orig_upcoming_moveouts_report',
    'orig_display_housing_accommodation_menu',
    'orig_display_reports_menu',
    'orig_display_building_menu',
    'orig_display_application_menu',
    'orig_display_assignment_menu',
    'orig_display_maintenance_menu',
    'orig_display_payment_menu',
    'orig_display_inspection_menu'
]

# Create aliases for backward compatibility
orig_init_housing_db = init_housing_db
orig_generate_id = generate_id
orig_set_auth = set_auth
