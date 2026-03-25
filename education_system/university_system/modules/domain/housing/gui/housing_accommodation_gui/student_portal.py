"""
Student portal functions - student-facing housing portal interface.
Handles student views for applications, assignments, payments, and maintenance.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_id
from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.application_manager import create_new_application_form, create_applications_list
from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.maintenance_manager import create_maintenance_list
from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.payment_manager import create_payment_history

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
                ttk.Label(assign_frame, text=f"Rent: £{assignment[5]}/month").pack(anchor='w')
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
        show_my_applications(self, my_apps_frame)
        
        # New application tab
        new_app_frame = ttk.Frame(notebook, padding="10")
        notebook.add(new_app_frame, text="Apply for Housing")
        create_new_application_form(self, new_app_frame)
    
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
            ttk.Label(right_frame, text=f"Monthly Rent: £{current_assignment[10]}").pack(anchor='w', pady=2)
            ttk.Label(right_frame, text=f"Assigned: {current_assignment[12]}").pack(anchor='w', pady=2)
            
            # Payment history
            payment_frame = ttk.LabelFrame(self.content_frame, text="Payment History", padding="20")
            payment_frame.pack(fill='both', expand=True)
            
            cursor.execute('''
            SELECT p.source_payment_id, p.amount, p.payment_date, p.payment_method,
                   p.payment_period_start, p.payment_period_end, p.status
            FROM payments p
            WHERE p.source_type = 'housing' AND p.student_id = ?
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
                        payment[0], f"£{payment[1]:.2f}", payment[2], 
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
        show_my_maintenance_requests(self, my_requests_frame)
        
        # New request tab
        new_request_frame = ttk.Frame(notebook, padding="10")
        notebook.add(new_request_frame, text="New Request")
        create_student_maintenance_form(self, new_request_frame)
    
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
                      command=lambda: submit_student_maintenance_request(self)).grid(row=3, column=0, pady=20)
            
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
        create_applications_list(self, self.content_frame)
    
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
        create_maintenance_list(self, self.content_frame)
    
def show_payments_view(self):
        """Show payments view for staff with view-only permissions"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="Payment History", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create read-only payment history
        create_payment_history(self, self.content_frame)
    
