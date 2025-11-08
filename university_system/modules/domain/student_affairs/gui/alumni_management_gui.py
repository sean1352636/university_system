import tkinter as tk
from university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import the original functions - backward compatibility
try:
    from university_system.modules.domain.student_affairs.services.alumni_management import (
        init_alumni_db, register_alumni, view_alumni, update_alumni,
        view_events, create_enhanced_event, event_check_in_system,
        record_donation, view_donations, setup_mentorship, view_mentorships,
        search_alumni_directory, view_connection_requests, manage_business_directory,
        create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
        schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
        view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
        manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
        generate_alumni_report, set_auth, setup_alumni_permissions,
        smart_mentorship_matching, generate_engagement_recommendations,
        create_alumni_story, view_alumni_stories, get_connection
    )
except ImportError as e:
    import_error_details = str(e)
    print(f"Warning: Could not import some functions: {e}")
    # Define fallback functions
    def placeholder_function(*args, **kwargs):
        func_name = kwargs.get('_func_name', 'Unknown function')
        messagebox.showerror(
            "Module Import Error",
            f"The alumni management module could not be loaded.\n\n"
            f"Function: {func_name}\n"
            f"Error: {import_error_details}\n\n"
            f"Please ensure all required dependencies are installed:\n"
            f"• university_system.alumni module\n"
            f"• All database schema requirements\n\n"
            f"Contact your system administrator for assistance."
        )
    
    # Assign placeholder to missing functions
    register_alumni = placeholder_function
    view_alumni = placeholder_function

class AlumniGUIApp:
    def __init__(self, root, auth=None):
        self.root = root
        self.root.title("Enhanced Alumni Management System")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Set authentication
        self.auth = auth
        if self.auth and hasattr(self.auth, 'current_user'):
            self.current_user = self.auth.current_user
        else:
            # Fallback to mock authentication for demo
            self.current_user = {
                'id': 1,
                'username': 'admin',
                'first_name': 'Administrator',
                'permissions': ['manage_alumni', 'view_alumni', 'manage_events', 'send_newsletters', 'admin']
            }

        # Initialize database and permissions
        try:
            init_alumni_db()
            setup_alumni_permissions()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize database: {e}")

        # Set authentication for backend functions
        try:
            from alumni_management import auth as backend_auth
            backend_auth.current_user = self.current_user
        except:
            pass

        self.create_widgets()
        self.show_dashboard()
        self._photo_file_paths: list[str] = []
        self._event_lookup: dict[str, int] = {}
        self._photo_storage_dir = Path(paths.DATA_DIR) / "alumni_photos"
        self._photo_storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_db_connection(self):
        """Return a central database connection with row access."""
        conn = db_get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    def _current_user_id(self):
        """Return current user's identifier for auditing."""
        if self.current_user and isinstance(self.current_user, dict):
            return str(self.current_user.get('username') or self.current_user.get('id') or 'gui_user')
        return 'gui_user'

    def _format_alumni_row(self, row):
        """Format alumni row tuple for treeview display."""
        if not isinstance(row, dict):
            row = dict(row)
        full_name = " ".join(filter(None, [row.get('first_name'), row.get('middle_name'), row.get('last_name')])).strip()
        if not full_name:
            full_name = row.get('full_name') or row.get('alumni_id', '')
        status = 'Active' if row.get('privacy_level', 1) else 'Hidden'
        return (
            row.get('alumni_id') or row.get('student_id'),
            full_name,
            row.get('graduation_year') or '',
            row.get('degree_earned') or row.get('course') or '',
            row.get('current_employer') or '',
            row.get('email_address') or row.get('email') or '',
            status
        )
    
    def create_widgets(self):
        """Create the main GUI structure"""
        # Add return to main menu button at the top
        return_btn = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create left sidebar
        self.create_sidebar(main_frame)

        # Create main content area
        self.create_main_content(main_frame)

        # Create status bar
        self.create_status_bar()
    
    def create_sidebar(self, parent):
        """Create the navigation sidebar"""
        sidebar_frame = ttk.Frame(parent, width=250)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sidebar_frame.pack_propagate(False)
        
        # Title
        title_label = ttk.Label(sidebar_frame, text="🎓 Alumni System", font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # User info
        user_frame = ttk.LabelFrame(sidebar_frame, text="Current User", padding=10)
        user_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(user_frame, text=f"Welcome, {self.current_user['first_name']}!", 
                 font=('Arial', 10, 'bold')).pack()
        ttk.Label(user_frame, text=f"Username: {self.current_user['username']}").pack()
        
        # Navigation menu
        self.create_navigation_menu(sidebar_frame)
    
    def create_navigation_menu(self, parent):
        """Create the navigation menu with categorized buttons and scrollbar"""
        # Add dashboard button at the top
        dashboard_btn = ttk.Button(parent, text="📊 Dashboard", command=self.show_dashboard)
        dashboard_btn.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(parent, text="🏠 Return to Homescreen", command=self.return_to_main_menu).pack(fill=tk.X, pady=(0, 10))
        
        # Create container for scrollable navigation
        nav_container = ttk.Frame(parent)
        nav_container.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollable frame for navigation buttons
        canvas = tk.Canvas(nav_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(nav_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        def configure_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Configure canvas width to match scrollable frame
            canvas.configure(width=scrollable_frame.winfo_reqwidth())
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Menu categories with their functions
        menu_categories = {
            "📋 Alumni Management": [
                ("Register New Alumni", self.show_register_alumni, 'manage_alumni'),
                ("View Alumni Records", self.show_view_alumni, 'view_alumni'),
                ("Update Alumni Record", self.show_update_alumni, 'manage_alumni'),
                ("Alumni Directory", self.show_alumni_directory, 'access_alumni_directory')
            ],
            "🌐 Networking": [
                ("Alumni Directory Search", self.show_directory_search, 'access_alumni_directory'),
                ("Connection Requests", self.show_connections, 'access_alumni_directory'),
                ("Business Directory", self.show_business_directory, 'access_alumni_directory'),
                ("Regional Chapters", self.show_regional_chapters, None)
            ],
            "💬 Communication": [
                ("Create Newsletter", self.show_create_newsletter, 'send_newsletters'),
                ("Alumni Forum", self.show_forum, 'access_alumni_directory'),
                ("Create Story", self.show_create_story, None),
                ("Alumni Stories", self.show_stories, None),
                ("Search Forum Posts", self.show_search_forum_posts, None),
                ("My Forum Posts", self.show_my_forum_posts, None),
                ("Moderate Forum", self.show_moderate_forum_posts, 'moderate_forum'),
                ("Photo Gallery", self.show_photo_gallery, None)
            ],
            "🎉 Events": [
                ("Create Event", self.show_create_event, 'manage_events_advanced'),
                ("View Events", self.show_view_events, 'view_events'),
                ("Event Check-in", self.show_event_checkin, 'manage_events_advanced'),
                ("Class Reunions", self.show_class_reunions, 'manage_social_features')
            ],
            "💼 Career Services": [
                ("Job Board", self.show_job_board, 'view_job_board'),
                ("Post Job", self.show_post_job, 'post_jobs'),
                ("Career Counseling", self.show_career_counseling, 'schedule_career_counseling')
            ],
            "💰 Fundraising": [
                ("Record Donation", self.show_record_donation, 'make_donation'),
                ("View Donations", self.show_view_donations, 'view_donations'),
                ("Donor Recognition", self.show_donor_recognition, 'manage_campaigns'),
                ("Fundraising Campaigns", self.show_campaigns, 'manage_campaigns')
            ],
            "👥 Mentorship": [
                ("Setup Mentorship", self.show_setup_mentorship, 'manage_mentorships'),
                ("View Mentorships", self.show_view_mentorships, 'view_mentorships'),
                ("Smart Matching", self.show_smart_matching, 'manage_ai_features')
            ],
            "🏆 Engagement": [
                ("Leaderboard", self.show_leaderboard, None),
                ("My Badges", self.show_my_badges, None),
                ("Recommendations", self.show_recommendations, None)
            ],
            "⚙️ Settings & Reports": [
                ("Directory Settings", self.show_directory_settings, None),
                ("Generate Reports", self.show_generate_reports, 'generate_reports'),
                ("System Analytics", self.show_analytics, 'view_analytics')
            ],
            "🔗 Integration Services": [
                ("Email Manager", self.open_email_manager_gui, None),
                ("Finance System", self.open_finance_gui, None),
                ("Student Validation", self.show_student_validation, None),
                ("Finance Status Check", self.show_finance_check, None)
            ]
        }
        
        # Create category sections with buttons
        for category, items in menu_categories.items():
            # Category header
            category_label = ttk.Label(scrollable_frame, text=category, font=('Arial', 10, 'bold'))
            category_label.pack(fill=tk.X, pady=(10, 5), padx=5)
            
            # Category separator
            separator = ttk.Separator(scrollable_frame, orient='horizontal')
            separator.pack(fill=tk.X, pady=(0, 5), padx=5)
            
            # Add category buttons
            for item_name, item_command, permission in items:
                if permission is None or self.has_permission(permission):
                    btn = ttk.Button(scrollable_frame, text=item_name, command=item_command)
                    btn.pack(fill=tk.X, pady=2, padx=10)
        
        # Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", on_mousewheel)

    def create_main_content(self, parent):
        """Create the main content area"""
        self.content_frame = ttk.Frame(parent)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    
    def create_status_bar(self):
        """Create status bar at the bottom"""
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def has_permission(self, permission):
        """Check if current user has permission"""
        if not permission:
            return True
        return permission in self.current_user.get('permissions', []) or 'admin' in self.current_user.get('permissions', [])
    
    def clear_content(self):
        """Clear the main content area"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def update_status(self, message):
        """Update status bar message"""
        self.status_bar.config(text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")
    
    def show_dashboard(self):
        """Show the main dashboard"""
        self.clear_content()
        self.update_status("Dashboard loaded")
        
        # Dashboard title
        title_frame = ttk.Frame(self.content_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(title_frame, text="Alumni Management Dashboard", 
                 font=('Arial', 20, 'bold')).pack(side=tk.LEFT)
        
        # Quick stats
        stats_frame = ttk.LabelFrame(self.content_frame, text="Quick Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Create stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get stats from database
            cursor.execute("SELECT COUNT(*) FROM alumni")
            total_alumni = cursor.fetchone()[0] if cursor.fetchone() else 0
            
            cursor.execute("SELECT COUNT(*) FROM alumni_events WHERE event_date > datetime('now')")
            upcoming_events = cursor.fetchone()[0] if cursor.fetchone() else 0
            
            cursor.execute("SELECT COUNT(*) FROM alumni WHERE is_donor = 1")
            total_donors = cursor.fetchone()[0] if cursor.fetchone() else 0
            
            conn.close()
            
            stats = [
                ("Total Alumni", total_alumni, "👥"),
                ("Upcoming Events", upcoming_events, "📅"),
                ("Active Donors", total_donors, "💝"),
                ("System Status", "Online", "✅")
            ]
        except Exception as e:
            stats = [
                ("Total Alumni", "N/A", "👥"),
                ("Upcoming Events", "N/A", "📅"),
                ("Active Donors", "N/A", "💝"),
                ("System Status", "Error", "❌")
            ]
        
        for i, (label, value, icon) in enumerate(stats):
            col = i % 4
            row = i // 4
            
            stat_frame = ttk.Frame(stats_grid, relief=tk.RIDGE, padding=10)
            stat_frame.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
            
            ttk.Label(stat_frame, text=icon, font=('Arial', 16)).pack()
            ttk.Label(stat_frame, text=str(value), font=('Arial', 14, 'bold')).pack()
            ttk.Label(stat_frame, text=label, font=('Arial', 10)).pack()
            
            stats_grid.columnconfigure(col, weight=1)
        
        # Recent activity
        activity_frame = ttk.LabelFrame(self.content_frame, text="Recent Activity", padding=10)
        activity_frame.pack(fill=tk.BOTH, expand=True)
        
        activity_text = ScrolledText(activity_frame, height=10, wrap=tk.WORD)
        activity_text.pack(fill=tk.BOTH, expand=True)
        
        # Sample recent activity
        activity_text.insert(tk.END, "Recent Alumni System Activity:\n\n")
        activity_text.insert(tk.END, f"• {datetime.now().strftime('%Y-%m-%d %H:%M')} - System initialized\n")
        activity_text.insert(tk.END, f"• {datetime.now().strftime('%Y-%m-%d %H:%M')} - Dashboard loaded\n")
        activity_text.insert(tk.END, f"• Database connection established\n")
        activity_text.config(state=tk.DISABLED)
    
    def show_register_alumni(self):
        """Show alumni registration form"""
        self.clear_content()
        self.update_status("Alumni Registration Form")
        
        # Create scrollable frame
        canvas = tk.Canvas(self.content_frame)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Title
        ttk.Label(scrollable_frame, text="Register New Alumni", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Personal Information Section
        personal_frame = ttk.LabelFrame(scrollable_frame, text="Personal Information", padding=10)
        personal_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        # Create form fields
        self.form_vars = {}
        
        personal_fields = [
            ("Title", "title"),
            ("First Name*", "first_name"),
            ("Middle Name", "middle_name"),
            ("Last Name*", "last_name"),
            ("Email Address*", "email"),
            ("Gender", "gender"),
            ("Date of Birth (YYYY-MM-DD)", "dob"),
            ("Phone Number", "phone")
        ]
        
        for i, (label, var_name) in enumerate(personal_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(personal_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=label).pack(anchor='w')
            
            if var_name == "gender":
                self.form_vars[var_name] = tk.StringVar()
                combo = ttk.Combobox(field_frame, textvariable=self.form_vars[var_name],
                                   values=["Male", "Female", "Other", "Prefer not to say"])
                combo.pack(fill=tk.X)
            else:
                self.form_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.form_vars[var_name]).pack(fill=tk.X)
        
        personal_frame.columnconfigure(0, weight=1)
        personal_frame.columnconfigure(1, weight=1)
        
        # Academic Information Section
        academic_frame = ttk.LabelFrame(scrollable_frame, text="Academic Information", padding=10)
        academic_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        academic_fields = [
            ("Student ID", "student_id"),
            ("Graduation Year*", "graduation_year"),
            ("Degree Earned*", "degree"),
            ("GPA (Optional)", "gpa")
        ]
        
        for i, (label, var_name) in enumerate(academic_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(academic_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=label).pack(anchor='w')
            self.form_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.form_vars[var_name]).pack(fill=tk.X)
        
        academic_frame.columnconfigure(0, weight=1)
        academic_frame.columnconfigure(1, weight=1)
        
        # Employment Information Section
        employment_frame = ttk.LabelFrame(scrollable_frame, text="Employment Information", padding=10)
        employment_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        employment_fields = [
            ("Current Employer", "employer"),
            ("Job Title", "job_title"),
            ("Industry", "industry"),
            ("Annual Salary (Optional)", "salary")
        ]
        
        for i, (label, var_name) in enumerate(employment_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(employment_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=label).pack(anchor='w')
            self.form_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.form_vars[var_name]).pack(fill=tk.X)
        
        employment_frame.columnconfigure(0, weight=1)
        employment_frame.columnconfigure(1, weight=1)
        
        # Contact Information Section
        contact_frame = ttk.LabelFrame(scrollable_frame, text="Contact Information", padding=10)
        contact_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        contact_fields = [
            ("Address", "address"),
            ("City", "city"),
            ("Country", "country"),
            ("LinkedIn URL", "linkedin")
        ]
        
        for i, (label, var_name) in enumerate(contact_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(contact_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=label).pack(anchor='w')
            self.form_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.form_vars[var_name]).pack(fill=tk.X)
        
        contact_frame.columnconfigure(0, weight=1)
        contact_frame.columnconfigure(1, weight=1)
        
        # Additional Information Section
        additional_frame = ttk.LabelFrame(scrollable_frame, text="Additional Information", padding=10)
        additional_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        # Bio text area
        ttk.Label(additional_frame, text="Biography/Description").pack(anchor='w')
        self.form_vars['bio'] = tk.StringVar()
        bio_text = ScrolledText(additional_frame, height=4, wrap=tk.WORD)
        bio_text.pack(fill=tk.X, pady=(0, 10))
        
        # Skills
        ttk.Label(additional_frame, text="Skills (comma-separated)").pack(anchor='w')
        self.form_vars['skills'] = tk.StringVar()
        ttk.Entry(additional_frame, textvariable=self.form_vars['skills']).pack(fill=tk.X, pady=(0, 10))
        
        # Achievements
        ttk.Label(additional_frame, text="Notable Achievements").pack(anchor='w')
        self.form_vars['achievements'] = tk.StringVar()
        achievements_text = ScrolledText(additional_frame, height=3, wrap=tk.WORD)
        achievements_text.pack(fill=tk.X)
        
        # Role Assignments Section
        roles_frame = ttk.LabelFrame(scrollable_frame, text="Role Assignments", padding=10)
        roles_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        self.form_vars['is_donor'] = tk.BooleanVar()
        self.form_vars['is_mentor'] = tk.BooleanVar()
        self.form_vars['is_board_member'] = tk.BooleanVar()
        self.form_vars['is_ambassador'] = tk.BooleanVar()
        
        ttk.Checkbutton(roles_frame, text="Alumni Donor", variable=self.form_vars['is_donor']).pack(anchor='w')
        ttk.Checkbutton(roles_frame, text="Available as Mentor", variable=self.form_vars['is_mentor']).pack(anchor='w')
        ttk.Checkbutton(roles_frame, text="Board Member", variable=self.form_vars['is_board_member']).pack(anchor='w')
        ttk.Checkbutton(roles_frame, text="Alumni Ambassador", variable=self.form_vars['is_ambassador']).pack(anchor='w')
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=20, padx=20)
        
        ttk.Button(button_frame, text="Register Alumni", 
                  command=self.submit_alumni_registration).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Clear Form", 
                  command=self.clear_alumni_form).pack(side=tk.RIGHT)
        
        # Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def submit_alumni_registration(self):
        """Submit the alumni registration form"""
        try:
            # Validate required fields
            required_fields = ['first_name', 'last_name', 'email', 'graduation_year', 'degree']
            for field in required_fields:
                if not self.form_vars[field].get().strip():
                    messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                    return

            # Get form data
            first_name = self.form_vars['first_name'].get().strip()
            last_name = self.form_vars['last_name'].get().strip()
            email = self.form_vars['email'].get().strip()
            student_id = self.form_vars['student_id'].get().strip()

            # Validate student record
            if student_id or email:
                validation_result = self.validate_student_record(student_id, email)
                if not validation_result['valid']:
                    messagebox.showerror("Validation Error",
                                       f"Student validation failed: {validation_result['error']}\n\n"
                                       "You must be a valid student to register as alumni.")
                    return

                # Check finance status
                finance_status = self.check_finance_status(validation_result['student_id'], email)
                if finance_status['has_debt']:
                    result = messagebox.askyesno("Outstanding Balance",
                                               f"You have an outstanding balance of ${finance_status['total_owed']:.2f}.\n\n"
                                               "Do you want to view your finance status before proceeding with registration?")
                    if result:
                        self.show_finance_status_dialog(finance_status, f"{first_name} {last_name}")
                        return

            # Process registration (call backend function)
            try:
                # Here you would normally call the backend registration function
                # For now, we'll simulate success
                registration_successful = True

                if registration_successful:
                    # Send confirmation email
                    self.send_alumni_registration_confirmation(email, f"{first_name} {last_name}")

                    messagebox.showinfo("Success", "Alumni registered successfully!\nConfirmation email sent.")
                    self.update_status("Alumni registration completed")

                    # Clear the form
                    self.clear_alumni_form()
                else:
                    messagebox.showerror("Error", "Registration failed. Please try again.")

            except Exception as reg_error:
                messagebox.showerror("Registration Error", f"Failed to complete registration: {str(reg_error)}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to register alumni: {str(e)}")
    
    def clear_alumni_form(self):
        """Clear all form fields"""
        for var in self.form_vars.values():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            else:
                var.set("")
    
    def show_view_alumni(self):
        """Show alumni records viewer"""
        self.clear_content()
        self.update_status("Viewing Alumni Records")
        
        # Title and search
        title_frame = ttk.Frame(self.content_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="Alumni Records", 
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        
        search_frame = ttk.Frame(title_frame)
        search_frame.pack(side=tk.RIGHT)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(search_frame, text="🔍", command=lambda: self.search_alumni(search_var.get())).pack(side=tk.LEFT)
        
        # Alumni table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        columns = ('ID', 'Name', 'Graduation Year', 'Degree', 'Employer', 'Email', 'Status')
        self.alumni_tree = ttk.Treeview(table_frame, columns=columns, show='headings')
        
        # Configure columns
        for col in columns:
            self.alumni_tree.heading(col, text=col)
            self.alumni_tree.column(col, width=120)
        
        # Add scrollbar
        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.alumni_tree.yview)
        self.alumni_tree.configure(yscrollcommand=scrollbar_y.set)
        
        scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.alumni_tree.xview)
        self.alumni_tree.configure(xscrollcommand=scrollbar_x.set)
        
        # Pack treeview and scrollbars
        self.alumni_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load alumni data
        self.load_alumni_data()
        
        # Buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="View Details", 
                  command=self.view_alumni_details).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Edit Alumni", 
                  command=self.edit_selected_alumni).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh", 
                  command=self.load_alumni_data).pack(side=tk.LEFT)
    
    def load_alumni_data(self):
        """Load alumni data into the treeview"""
        try:
            # Clear existing data
            for item in self.alumni_tree.get_children():
                self.alumni_tree.delete(item)
            conn = self._get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    alumni_id,
                    first_name,
                    middle_name,
                    last_name,
                    graduation_year,
                    degree_earned,
                    current_employer,
                    email_address,
                    privacy_level
                FROM alumni
                ORDER BY COALESCE(graduation_year, 0) DESC, last_name, first_name
                """
            )
            rows = cursor.fetchall()

            if rows:
                for row in rows:
                    formatted = self._format_alumni_row(row)
                    self.alumni_tree.insert('', tk.END, values=formatted)
                self.update_status(f"Loaded {len(rows)} alumni records")
            else:
                # Fallback to students who have graduated
                cursor.execute(
                    """
                    SELECT
                        student_id,
                        first_name,
                        middle_name,
                        last_name,
                        '' AS graduation_year,
                        course,
                        '' AS current_employer,
                        email_address AS email,
                        1 AS privacy_level
                    FROM students
                    WHERE status = 'Graduated'
                    ORDER BY last_name, first_name
                    """
                )
                fallback_rows = cursor.fetchall()
                if fallback_rows:
                    for row in fallback_rows:
                        formatted = self._format_alumni_row(row)
                        self.alumni_tree.insert('', tk.END, values=formatted)
                    self.update_status("Showing graduated students (no dedicated alumni records found)")
                else:
                    self.update_status("No alumni records found")
                    self.alumni_tree.insert(
                        '',
                        tk.END,
                        values=('N/A', 'No alumni records available', '', '', '', '', 'Setup required')
                    )

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load alumni data: {str(e)}")
    
    def search_alumni(self, search_term):
        """Search alumni based on search term"""
        search_term = (search_term or "").strip()
        if not search_term:
            self.load_alumni_data()
            return
        
        try:
            # Clear existing data
            for item in self.alumni_tree.get_children():
                self.alumni_tree.delete(item)

            conn = self._get_db_connection()
            cursor = conn.cursor()
            like_term = f"%{search_term}%"

            cursor.execute(
                """
                SELECT
                    alumni_id,
                    first_name,
                    middle_name,
                    last_name,
                    graduation_year,
                    degree_earned,
                    current_employer,
                    email_address,
                    privacy_level
                FROM alumni
                WHERE (
                    alumni_id LIKE ?
                    OR first_name LIKE ?
                    OR last_name LIKE ?
                    OR email_address LIKE ?
                    OR degree_earned LIKE ?
                    OR current_employer LIKE ?
                    OR industry LIKE ?
                )
                ORDER BY COALESCE(graduation_year, 0) DESC, last_name, first_name
                """,
                (like_term,) * 7
            )
            rows = cursor.fetchall()

            if not rows:
                cursor.execute(
                    """
                    SELECT
                        student_id,
                        first_name,
                        middle_name,
                        last_name,
                        '' AS graduation_year,
                        course,
                        '' AS current_employer,
                        email_address AS email,
                        1 AS privacy_level
                    FROM students
                    WHERE (
                        student_id LIKE ?
                        OR first_name LIKE ?
                        OR last_name LIKE ?
                        OR email_address LIKE ?
                        OR course LIKE ?
                    )
                    AND status = 'Graduated'
                    ORDER BY last_name, first_name
                    """,
                    (like_term,) * 5
                )
                rows = cursor.fetchall()

            conn.close()

            for row in rows:
                formatted = self._format_alumni_row(row)
                self.alumni_tree.insert('', tk.END, values=formatted)

            self.update_status(f"Found {len(rows)} alumni matching '{search_term}'")
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

    def _fetch_alumni_record(self, alumni_id: str | None):
        """Retrieve an alumni record from the database."""
        if not alumni_id:
            return None
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM alumni
            WHERE alumni_id = ?
            """,
            (alumni_id,)
        )
        row = cursor.fetchone()

        # If not found, try alternative identifiers (e.g., without leading 'A')
        if not row and alumni_id.upper().startswith('A'):
            cursor.execute(
                """
                SELECT *
                FROM alumni
                WHERE alumni_id = ?
                """,
                (alumni_id.upper(),)
            )
            row = cursor.fetchone()

        if row:
            record = dict(row)
            record['source'] = 'alumni'
            conn.close()
            return record

        # Attempt fallback to students table
        candidate_ids = [alumni_id]
        if alumni_id.upper().startswith('A'):
            candidate_ids.append(alumni_id[1:])

        record = None
        for candidate in candidate_ids:
            cursor.execute(
                """
                SELECT student_id, first_name, middle_name, last_name, course,
                       email_address AS email, '' AS phone, '' AS city, '' AS country, '' AS linkedin_url,
                       '' AS graduation_year
                FROM students
                WHERE student_id = ?
                """,
                (candidate,)
            )
            student_row = cursor.fetchone()
            if student_row:
                data = dict(student_row)
                data['alumni_id'] = alumni_id if alumni_id.startswith('A') else f"A{candidate}"
                data['source'] = 'students'
                data['email_address'] = data.get('email')
                data.setdefault('graduation_year', '')
                data['degree_earned'] = data.get('course')
                data['current_employer'] = ''
                data['job_title'] = ''
                data['industry'] = ''
                record = data
                break

        conn.close()
        return record

    def _open_alumni_editor(self, record: dict):
        """Open an editor dialog for the given alumni record."""
        if not record:
            messagebox.showerror("Not Found", "Alumni record could not be located.")
            return

        editor = tk.Toplevel(self.root)
        editor.title(f"Edit Alumni - {record.get('alumni_id')}")
        editor.geometry("500x600")
        editor.transient(self.root)
        editor.grab_set()

        form_frame = ttk.Frame(editor, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=f"Editing {record.get('alumni_id')}", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        fields = [
            ("First Name", "first_name"),
            ("Middle Name", "middle_name"),
            ("Last Name", "last_name"),
            ("Graduation Year", "graduation_year"),
            ("Degree", "degree_earned"),
            ("Current Employer", "current_employer"),
            ("Job Title", "job_title"),
            ("Industry", "industry"),
            ("Email Address", "email_address"),
            ("Phone", "phone"),
            ("City", "city"),
            ("Country", "country"),
            ("LinkedIn URL", "linkedin_url"),
        ]

        form_vars = {}
        for label, key in fields:
            value = record.get(key) or ''
            var = tk.StringVar(value=str(value) if value is not None else '')
            form_vars[key] = var

            row = ttk.Frame(form_frame)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=label + ":", width=18).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def save_changes():
            updates = {key: var.get().strip() for key, var in form_vars.items()}
            try:
                self._save_alumni_updates(record, updates)
                editor.destroy()
                self.load_alumni_data()
                messagebox.showinfo("Success", "Alumni record updated successfully.")
            except Exception as exc:
                messagebox.showerror("Update Failed", f"Could not save changes: {exc}")

        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=20)
        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Cancel", command=editor.destroy).pack(side=tk.RIGHT)

    def _save_alumni_updates(self, record: dict, updates: dict):
        """Persist updates to the alumni table."""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        alumni_id = record.get('alumni_id') or record.get('student_id')
        if not alumni_id:
            raise ValueError("Alumni identifier missing.")

        # Normalise graduation year to integer when possible
        grad_year_text = updates.get('graduation_year', '')
        graduation_year = None
        if grad_year_text:
            try:
                graduation_year = int(grad_year_text)
            except ValueError:
                raise ValueError("Graduation year must be a number.")

        data = {
            'alumni_id': alumni_id,
            'student_id': record.get('student_id'),
            'first_name': updates.get('first_name'),
            'middle_name': updates.get('middle_name'),
            'last_name': updates.get('last_name'),
            'graduation_year': graduation_year,
            'degree_earned': updates.get('degree_earned'),
            'current_employer': updates.get('current_employer'),
            'job_title': updates.get('job_title'),
            'industry': updates.get('industry'),
            'email_address': updates.get('email_address'),
            'phone': updates.get('phone'),
            'city': updates.get('city'),
            'country': updates.get('country'),
            'linkedin_url': updates.get('linkedin_url'),
            'date_registered': record.get('date_registered') or datetime.now().isoformat(),
        }

        if record.get('source') == 'alumni':
            cursor.execute(
                """
                UPDATE alumni
                SET first_name = ?, middle_name = ?, last_name = ?, graduation_year = ?, degree_earned = ?,
                    current_employer = ?, job_title = ?, industry = ?, email_address = ?, phone = ?,
                    city = ?, country = ?, linkedin_url = ?, date_registered = COALESCE(date_registered, ?)
                WHERE alumni_id = ?
                """,
                (
                    data['first_name'], data['middle_name'], data['last_name'], data['graduation_year'],
                    data['degree_earned'], data['current_employer'], data['job_title'], data['industry'],
                    data['email_address'], data['phone'], data['city'], data['country'],
                    data['linkedin_url'], data['date_registered'], alumni_id
                )
            )
        else:
            # Insert or replace alumni record derived from student data
            if not data['student_id']:
                data['student_id'] = alumni_id[1:] if alumni_id.upper().startswith('A') else alumni_id
            cursor.execute(
                """
                INSERT INTO alumni (
                    alumni_id, student_id, email_address, title, first_name, middle_name, last_name,
                    graduation_year, degree_earned, current_employer, job_title, industry,
                    city, country, phone, linkedin_url, date_registered, is_donor, is_mentor, is_board_member
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0
                )
                ON CONFLICT(alumni_id) DO UPDATE SET
                    student_id = excluded.student_id,
                    email_address = excluded.email_address,
                    first_name = excluded.first_name,
                    middle_name = excluded.middle_name,
                    last_name = excluded.last_name,
                    graduation_year = excluded.graduation_year,
                    degree_earned = excluded.degree_earned,
                    current_employer = excluded.current_employer,
                    job_title = excluded.job_title,
                    industry = excluded.industry,
                    city = excluded.city,
                    country = excluded.country,
                    phone = excluded.phone,
                    linkedin_url = excluded.linkedin_url,
                    date_registered = excluded.date_registered
                """,
                (
                    data['alumni_id'], data['student_id'], data['email_address'], None,
                    data['first_name'], data['middle_name'], data['last_name'],
                    data['graduation_year'], data['degree_earned'], data['current_employer'],
                    data['job_title'], data['industry'], data['city'], data['country'],
                    data['phone'], data['linkedin_url'], data['date_registered']
                )
            )

        conn.commit()
        conn.close()

        # Send alumni welcome email automatically
        try:
            from university_system.infrastructure.email.email_service import send_alumni_welcome_email
            full_name = f"{data['first_name']} {data.get('middle_name', '')} {data['last_name']}".replace('  ', ' ')
            send_alumni_welcome_email(data['alumni_id'], data['email_address'], full_name)
        except Exception as e:
            import logging
            logging.warning(f"Failed to send alumni welcome email: {e}")

    def _fetch_business_listings(self, industry: str | None = None):
        """Return business listings optionally filtered by industry."""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        base_query = (
            "SELECT b.business_name, b.business_description, b.industry, b.website, "
            "b.contact_email, b.services_offered, b.location, b.created_date, "
            "a.first_name, a.last_name, a.graduation_year "
            "FROM business_directory b "
            "LEFT JOIN alumni a ON b.alumni_id = a.alumni_id"
        )
        params: list[str] = []
        if industry and industry.lower() != "all":
            base_query += " WHERE LOWER(b.industry) = LOWER(?)"
            params.append(industry)
        base_query += " ORDER BY b.business_name"
        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def _get_event_options(self):
        """Retrieve available alumni events for photo uploads."""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT event_id, event_name
            FROM alumni_events
            ORDER BY COALESCE(event_date, event_name)
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def view_alumni_details(self):
        """View detailed information for selected alumni"""
        selection = self.alumni_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an alumni record to view details.")
            return
        
        item = self.alumni_tree.item(selection[0])
        alumni_data = item['values']
        
        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Alumni Details - {alumni_data[1]}")
        details_window.geometry("600x500")
        
        # Create scrollable text
        text_widget = ScrolledText(details_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Display alumni details
        details_text = f"""
ALUMNI DETAILS
{'='*50}

Personal Information:
• Alumni ID: {alumni_data[0]}
• Name: {alumni_data[1]}
• Email: {alumni_data[5]}

Academic Information:
• Graduation Year: {alumni_data[2]}
• Degree: {alumni_data[3]}

Employment Information:
• Current Employer: {alumni_data[4]}
• Status: {alumni_data[6]}

Registration Date: {datetime.now().strftime('%Y-%m-%d')}
Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        text_widget.insert(tk.END, details_text)
        text_widget.config(state=tk.DISABLED)
    
    def edit_selected_alumni(self):
        """Edit the selected alumni record"""
        selection = self.alumni_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an alumni record to edit.")
            return
        
        item = self.alumni_tree.item(selection[0])
        alumni_id = item['values'][0]
        record = self._fetch_alumni_record(alumni_id)
        self._open_alumni_editor(record)
    
    def show_update_alumni(self):
        """Show alumni update interface"""
        self.clear_content()
        self.update_status("Alumni Update Interface")
        
        # Implementation would be similar to registration form but with pre-filled data
        ttk.Label(self.content_frame, text="Update Alumni Record", 
                 font=('Arial', 16, 'bold')).pack(pady=20)
        
        # Alumni selection
        selection_frame = ttk.LabelFrame(self.content_frame, text="Select Alumni to Update", padding=10)
        selection_frame.pack(fill=tk.X, pady=(0, 20), padx=20)
        
        ttk.Label(selection_frame, text="Alumni ID:").pack(side=tk.LEFT, padx=(0, 10))
        alumni_id_var = tk.StringVar()
        ttk.Entry(selection_frame, textvariable=alumni_id_var, width=15).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(selection_frame, text="Load Alumni Data", 
                  command=lambda: self.load_alumni_for_update(alumni_id_var.get())).pack(side=tk.LEFT)
        
        # Update form would go here (similar to registration form)
        update_info = ttk.Label(self.content_frame, text="Enter Alumni ID above to load update form", 
                               font=('Arial', 12))
        update_info.pack(pady=50)
    
    def load_alumni_for_update(self, alumni_id):
        """Load alumni data for updating"""
        if not alumni_id:
            messagebox.showwarning("Input Required", "Please enter an Alumni ID")
            return
        record = self._fetch_alumni_record(alumni_id.strip())
        if not record:
            messagebox.showerror("Not Found", f"No alumni or graduated student record found for ID {alumni_id}.")
            return

        self._open_alumni_editor(record)
        self.update_status(f"Loaded alumni record {record.get('alumni_id')} for editing")

    def delete_alumni_record(self, alumni_id, alumni_name, alumni_email):
        """Delete alumni record with confirmation"""
        result = messagebox.askyesno("Delete Alumni",
                                   f"Are you sure you want to permanently delete the alumni record for {alumni_name}?\n\n"
                                   "This action cannot be undone.")
        if result:
            # Confirm deletion one more time
            confirm = messagebox.askyesno("Final Confirmation",
                                        "This will permanently delete all alumni data.\n\n"
                                        "Are you absolutely sure?")
            if confirm:
                # Simulate deletion
                # Here you would call the backend deletion function

                # Send deletion confirmation email
                self.send_profile_deletion_confirmation(alumni_email, alumni_name)

                messagebox.showinfo("Success", f"Alumni record for {alumni_name} has been deleted.\nConfirmation email sent.")

    def show_student_validation(self):
        """Show student validation interface"""
        self.clear_content()
        self.update_status("Student Validation")

        # Title
        title_label = ttk.Label(self.content_frame, text="Student Record Validation",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)

        # Input frame
        input_frame = ttk.LabelFrame(self.content_frame, text="Validation Inputs", padding=20)
        input_frame.pack(fill=tk.X, padx=20, pady=10)

        # Student ID input
        ttk.Label(input_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, padx=10, pady=5)

        # Email input
        ttk.Label(input_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
        email_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=email_var, width=30).grid(row=1, column=1, padx=10, pady=5)

        # Validate button
        def validate_student():
            student_id = student_id_var.get().strip()
            email = email_var.get().strip()

            if not student_id and not email:
                messagebox.showerror("Input Required", "Please enter either Student ID or Email")
                return

            result = self.validate_student_record(student_id, email)

            if result['valid']:
                messagebox.showinfo("Validation Result",
                                  f"Valid Student Found!\n\n"
                                  f"Student ID: {result['student_id']}\n"
                                  f"Name: {result['name']}\n"
                                  f"Email: {result['email']}\n"
                                  f"Graduation Date: {result.get('graduation_date', 'N/A')}")
            else:
                messagebox.showerror("Validation Result",
                                   f"Validation Failed!\n\n"
                                   f"Error: {result['error']}")

        ttk.Button(input_frame, text="Validate Student",
                  command=validate_student).grid(row=2, column=0, columnspan=2, pady=20)

    def show_finance_check(self):
        """Show finance status check interface"""
        self.clear_content()
        self.update_status("Finance Status Check")

        # Title
        title_label = ttk.Label(self.content_frame, text="Finance Status Check",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)

        # Input frame
        input_frame = ttk.LabelFrame(self.content_frame, text="Check Finance Status", padding=20)
        input_frame.pack(fill=tk.X, padx=20, pady=10)

        # Student ID input
        ttk.Label(input_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, padx=10, pady=5)

        # Email input
        ttk.Label(input_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
        email_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=email_var, width=30).grid(row=1, column=1, padx=10, pady=5)

        # Check button
        def check_finance():
            student_id = student_id_var.get().strip()
            email = email_var.get().strip()

            if not student_id:
                messagebox.showerror("Input Required", "Please enter Student ID")
                return

            finance_status = self.check_finance_status(student_id, email)

            if 'error' in finance_status:
                messagebox.showerror("Error", finance_status['error'])
            else:
                self.show_finance_status_dialog(finance_status, f"Student {student_id}")

        ttk.Button(input_frame, text="Check Finance Status",
                  command=check_finance).grid(row=2, column=0, columnspan=2, pady=20)
    
    def show_alumni_directory(self):
        """Show alumni directory settings"""
        self.clear_content()
        self.update_status("Alumni Directory Settings")
        
        ttk.Label(self.content_frame, text="Alumni Directory Privacy Settings", 
                 font=('Arial', 16, 'bold')).pack(pady=20)
        
        settings_frame = ttk.LabelFrame(self.content_frame, text="Privacy Settings", padding=20)
        settings_frame.pack(fill=tk.X, pady=20, padx=20)
        
        # Privacy checkboxes
        privacy_vars = {}
        privacy_options = [
            ("show_contact", "Show contact information in directory"),
            ("show_employment", "Show employment information"),
            ("show_education", "Show education information"),
            ("searchable", "Make profile searchable"),
            ("networking", "Available for networking"),
            ("mentor", "Available as mentor")
        ]
        
        for var_name, description in privacy_options:
            privacy_vars[var_name] = tk.BooleanVar(value=True)
            ttk.Checkbutton(settings_frame, text=description, 
                           variable=privacy_vars[var_name]).pack(anchor='w', pady=5)
        
        # Save button
        ttk.Button(settings_frame, text="Save Settings", 
                  command=lambda: self.save_directory_settings(privacy_vars)).pack(pady=20)
    
    def save_directory_settings(self, privacy_vars):
        """Save directory privacy settings"""
        messagebox.showinfo("Settings Saved", "Directory privacy settings have been saved successfully!")
        self.update_status("Directory settings updated")
    
    def show_directory_search(self):
        """Show advanced directory search"""
        self.clear_content()
        self.update_status("Alumni Directory Search")
        
        ttk.Label(self.content_frame, text="Alumni Directory Search", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Search form
        search_frame = ttk.LabelFrame(self.content_frame, text="Search Criteria", padding=10)
        search_frame.pack(fill=tk.X, pady=(0, 20), padx=20)
        
        search_vars = {}
        search_fields = [
            ("Name", "name"),
            ("Graduation Year", "year"),
            ("Industry", "industry"),
            ("Location", "location"),
            ("Skills", "skills")
        ]
        
        for i, (label, var_name) in enumerate(search_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(search_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=f"{label}:").pack(anchor='w')
            search_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=search_vars[var_name]).pack(fill=tk.X)
        
        search_frame.columnconfigure(0, weight=1)
        search_frame.columnconfigure(1, weight=1)
        
        # Search button
        ttk.Button(search_frame, text="Search Directory", 
                  command=lambda: self.perform_directory_search(search_vars)).pack(pady=10)
        
        # Results area
        self.directory_results = ScrolledText(self.content_frame, height=15, wrap=tk.WORD)
        self.directory_results.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
    
    def perform_directory_search(self, search_vars):
        """Perform directory search with given criteria"""
        self.directory_results.delete(1.0, tk.END)
        
        search_criteria = {k: v.get() for k, v in search_vars.items() if v.get().strip()}
        
        if not search_criteria:
            self.directory_results.insert(tk.END, "Please enter at least one search criterion.")
            return
        
        # Sample search results
        results_text = f"Alumni Directory Search Results\n{'='*40}\n\n"
        results_text += f"Search criteria: {', '.join([f'{k}: {v}' for k, v in search_criteria.items()])}\n\n"
        
        sample_results = [
            {
                'name': 'Sarah Johnson',
                'year': '2015',
                'industry': 'Technology',
                'location': 'San Francisco, CA',
                'title': 'Senior Developer',
                'company': 'Tech Corp'
            },
            {
                'name': 'Michael Chen',
                'year': '2018',
                'industry': 'Finance',
                'location': 'New York, NY',
                'title': 'Financial Analyst',
                'company': 'Finance Plus'
            }
        ]
        
        for i, result in enumerate(sample_results, 1):
            results_text += f"{i}. {result['name']} (Class of {result['year']})\n"
            results_text += f"   Current: {result['title']} at {result['company']}\n"
            results_text += f"   Industry: {result['industry']}\n"
            results_text += f"   Location: {result['location']}\n"
            results_text += f"   ✓ Available for Networking\n\n"
        
        self.directory_results.insert(tk.END, results_text)
        self.update_status(f"Found {len(sample_results)} alumni matching search criteria")
    
    def show_connections(self):
        """Show networking connections interface"""
        self.clear_content()
        self.update_status("Networking Connections")
        
        ttk.Label(self.content_frame, text="Networking Connections", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different connection views
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Pending requests tab
        pending_frame = ttk.Frame(notebook)
        notebook.add(pending_frame, text="Pending Requests")
        
        pending_text = ScrolledText(pending_frame, wrap=tk.WORD)
        pending_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        pending_content = """Pending Connection Requests:

1. From: John Smith (Class of 2020)
   Software Engineer at StartupCo
   Date: 2025-08-15
   Message: "I'd love to connect and learn about your experience in the tech industry."
   
   [Accept] [Decline]

2. From: Lisa Brown (Class of 2019)
   Marketing Manager at Corp Inc
   Date: 2025-08-14
   Message: "Interested in discussing career opportunities in marketing."
   
   [Accept] [Decline]
"""
        pending_text.insert(tk.END, pending_content)
        
        # My connections tab
        connections_frame = ttk.Frame(notebook)
        notebook.add(connections_frame, text="My Connections")
        
        connections_text = ScrolledText(connections_frame, wrap=tk.WORD)
        connections_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        connections_content = """My Network Connections:

✅ Sarah Johnson (Class of 2015)
   Senior Developer at Tech Corp
   Connected: 2025-07-20
   Industry: Technology
   
✅ Michael Chen (Class of 2018)
   Financial Analyst at Finance Plus
   Connected: 2025-07-15
   Industry: Finance
   
✅ Emily Davis (Class of 2020)
   Engineer at Engineering Co
   Connected: 2025-07-10
   Industry: Engineering

Total Connections: 3
"""
        connections_text.insert(tk.END, connections_content)

    def send_connection_request(self):
        """Send connection request to another alumni"""
        self.clear_content()
        self.update_status("Send Connection Request")

        ttk.Label(self.content_frame, text="Send Connection Request",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Alumni search
        search_frame = ttk.LabelFrame(self.content_frame, text="Find Alumni", padding=10)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        ttk.Label(search_frame, text="Search by name:").pack(side=tk.LEFT, padx=(0, 10))
        self.connection_search = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.connection_search, width=30).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(search_frame, text="Search",
                  command=self._search_alumni_for_connection).pack(side=tk.LEFT)

        # Search results
        results_frame = ttk.LabelFrame(self.content_frame, text="Alumni", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Name', 'Graduation Year', 'Industry', 'Location', 'Status')
        self.connection_alumni_tree = ttk.Treeview(results_frame, columns=columns, show='headings')

        for col in columns:
            self.connection_alumni_tree.heading(col, text=col)
            self.connection_alumni_tree.column(col, width=130)

        scrollbar_y = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                    command=self.connection_alumni_tree.yview)
        self.connection_alumni_tree.configure(yscrollcommand=scrollbar_y.set)

        self.connection_alumni_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Send Connection Request",
                  command=self._send_selected_connection_request).pack(side=tk.LEFT)

    def _search_alumni_for_connection(self):
        """Search alumni for connection requests"""
        try:
            # Clear existing results
            for item in self.connection_alumni_tree.get_children():
                self.connection_alumni_tree.delete(item)

            search_term = self.connection_search.get().strip()
            if not search_term:
                messagebox.showwarning("Search Required", "Please enter a search term.")
                return

            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                query = """
                    SELECT a.alumni_id, a.first_name || ' ' || a.last_name,
                           a.graduation_year, a.industry, a.location,
                           CASE
                               WHEN EXISTS (
                                   SELECT 1 FROM alumni_connections
                                   WHERE (requester_id = ? AND recipient_id = a.alumni_id)
                                   OR (requester_id = a.alumni_id AND recipient_id = ?)
                               ) THEN 'Connected/Pending'
                               ELSE 'Not Connected'
                           END as status
                    FROM alumni_directory a
                    WHERE (a.first_name LIKE ? OR a.last_name LIKE ?)
                    AND a.alumni_id != ?
                    ORDER BY a.last_name
                """
                cursor.execute(query, (user_id, user_id, f"%{search_term}%", f"%{search_term}%", user_id))
                results = cursor.fetchall()

                for alumni in results:
                    # Display without alumni_id
                    self.connection_alumni_tree.insert('', tk.END, values=alumni[1:])

                self.update_status(f"Found {len(results)} alumni")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

    def _send_selected_connection_request(self):
        """Send connection request to selected alumni"""
        if not hasattr(self, 'connection_alumni_tree'):
            return

        selection = self.connection_alumni_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an alumni to connect with.")
            return

        item = self.connection_alumni_tree.item(selection[0])
        alumni_data = item['values']

        # Check if already connected
        if alumni_data[4] == 'Connected/Pending':
            messagebox.showinfo("Already Connected",
                              "You already have a connection or pending request with this alumni.")
            return

        # Create message dialog
        msg_window = tk.Toplevel(self.root)
        msg_window.title("Connection Request Message")
        msg_window.geometry("500x300")
        msg_window.configure(bg='white')
        msg_window.grab_set()

        frame = ttk.Frame(msg_window, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Send connection request to {alumni_data[0]}",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        ttk.Label(frame, text="Message (optional):").pack(anchor='w')
        message_text = ScrolledText(frame, height=6, wrap=tk.WORD)
        message_text.pack(fill=tk.BOTH, expand=True, pady=(5, 20))

        def send_request():
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    # Get recipient_id from name
                    name_parts = alumni_data[0].split()
                    first_name = name_parts[0] if name_parts else ''
                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

                    cursor.execute("""
                        SELECT alumni_id FROM alumni_directory
                        WHERE first_name = ? AND last_name = ?
                    """, (first_name, last_name))
                    result = cursor.fetchone()

                    if result:
                        recipient_id = result[0]

                        cursor.execute("""
                            INSERT INTO alumni_connections (
                                requester_id, recipient_id, status, message, request_date
                            ) VALUES (?, ?, 'pending', ?, datetime('now'))
                        """, (user_id, recipient_id, message_text.get(1.0, tk.END).strip()))

                        conn.commit()

                        messagebox.showinfo("Success", "Connection request sent!")
                        msg_window.destroy()
                        self._search_alumni_for_connection()  # Refresh

                        # Log activity
                        from university_system.modules.shared.utils.activity_logger import log_activity
                        log_activity('create', 'connection_request',
                                   details={'recipient': alumni_data[0]})

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send request: {str(e)}")

        ttk.Button(frame, text="Send Request",
                  command=send_request).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame, text="Cancel",
                  command=msg_window.destroy).pack(side=tk.LEFT)

    def view_connection_requests(self):
        """View pending connection requests"""
        self.clear_content()
        self.update_status("Connection Requests")

        ttk.Label(self.content_frame, text="Connection Requests",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Incoming requests tab
        incoming_frame = ttk.Frame(notebook)
        notebook.add(incoming_frame, text="Incoming Requests")

        incoming_table = ttk.Frame(incoming_frame)
        incoming_table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('From', 'Industry', 'Message', 'Date')
        self.incoming_requests_tree = ttk.Treeview(incoming_table, columns=columns, show='headings')

        for col in columns:
            self.incoming_requests_tree.heading(col, text=col)
            self.incoming_requests_tree.column(col, width=150)

        scrollbar_y = ttk.Scrollbar(incoming_table, orient=tk.VERTICAL,
                                    command=self.incoming_requests_tree.yview)
        self.incoming_requests_tree.configure(yscrollcommand=scrollbar_y.set)

        self.incoming_requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load incoming requests
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                query = """
                    SELECT a.first_name || ' ' || a.last_name, a.industry,
                           c.message, c.request_date
                    FROM alumni_connections c
                    JOIN alumni_directory a ON c.requester_id = a.alumni_id
                    WHERE c.recipient_id = ? AND c.status = 'pending'
                    ORDER BY c.request_date DESC
                """
                cursor.execute(query, (user_id,))
                requests = cursor.fetchall()

                for req in requests:
                    self.incoming_requests_tree.insert('', tk.END, values=req)

                self.update_status(f"{len(requests)} incoming request(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load requests: {str(e)}")

        # Action buttons for incoming
        incoming_buttons = ttk.Frame(incoming_frame)
        incoming_buttons.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(incoming_buttons, text="Accept",
                  command=lambda: self._respond_to_request('accepted')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(incoming_buttons, text="Decline",
                  command=lambda: self._respond_to_request('declined')).pack(side=tk.LEFT)

        # Outgoing requests tab
        outgoing_frame = ttk.Frame(notebook)
        notebook.add(outgoing_frame, text="Sent Requests")

        outgoing_table = ttk.Frame(outgoing_frame)
        outgoing_table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns_out = ('To', 'Industry', 'Status', 'Date')
        self.outgoing_requests_tree = ttk.Treeview(outgoing_table, columns=columns_out, show='headings')

        for col in columns_out:
            self.outgoing_requests_tree.heading(col, text=col)
            self.outgoing_requests_tree.column(col, width=150)

        scrollbar_y2 = ttk.Scrollbar(outgoing_table, orient=tk.VERTICAL,
                                     command=self.outgoing_requests_tree.yview)
        self.outgoing_requests_tree.configure(yscrollcommand=scrollbar_y2.set)

        self.outgoing_requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y2.pack(side=tk.RIGHT, fill=tk.Y)

        # Load outgoing requests
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                query = """
                    SELECT a.first_name || ' ' || a.last_name, a.industry,
                           c.status, c.request_date
                    FROM alumni_connections c
                    JOIN alumni_directory a ON c.recipient_id = a.alumni_id
                    WHERE c.requester_id = ?
                    ORDER BY c.request_date DESC
                """
                cursor.execute(query, (user_id,))
                requests = cursor.fetchall()

                for req in requests:
                    self.outgoing_requests_tree.insert('', tk.END, values=req)

        except Exception as e:
            pass

    def _respond_to_request(self, response):
        """Respond to a connection request"""
        if not hasattr(self, 'incoming_requests_tree'):
            return

        selection = self.incoming_requests_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a request.")
            return

        item = self.incoming_requests_tree.item(selection[0])
        request_data = item['values']

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                # Get requester_id from name
                name_parts = request_data[0].split()
                first_name = name_parts[0] if name_parts else ''
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

                cursor.execute("""
                    UPDATE alumni_connections
                    SET status = ?, response_date = datetime('now')
                    WHERE recipient_id = ?
                    AND requester_id = (
                        SELECT alumni_id FROM alumni_directory
                        WHERE first_name = ? AND last_name = ?
                    )
                    AND status = 'pending'
                """, (response, user_id, first_name, last_name))

                conn.commit()

            messagebox.showinfo("Success", f"Request {response}!")
            self.view_connection_requests()  # Refresh

            # Log activity
            from university_system.modules.shared.utils.activity_logger import log_activity
            log_activity('update', 'connection_request',
                       details={'requester': request_data[0], 'action': response})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to respond: {str(e)}")

    def show_business_directory(self):
        """Show business directory interface"""
        self.clear_content()
        self.update_status("Alumni Business Directory")
        
        ttk.Label(self.content_frame, text="Alumni Business Directory", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for viewing and adding businesses
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # View businesses tab
        view_frame = ttk.Frame(notebook)
        notebook.add(view_frame, text="Browse Businesses")
        
        # Search and filter
        filter_frame = ttk.Frame(view_frame)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(filter_frame, text="Filter by Industry:").pack(side=tk.LEFT, padx=(0, 10))
        industry_var = tk.StringVar()
        industry_combo = ttk.Combobox(filter_frame, textvariable=industry_var,
                                     values=["All", "Technology", "Healthcare", "Finance", "Education", "Other"])
        industry_combo.pack(side=tk.LEFT, padx=(0, 10))
        industry_combo.set("All")
        
        ttk.Button(filter_frame, text="Filter", 
                  command=lambda: self.filter_businesses(industry_var.get())).pack(side=tk.LEFT)
        
        # Business listings
        self.business_text = ScrolledText(view_frame, wrap=tk.WORD)
        self.business_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Load sample business data
        self.load_business_listings()
        
        # Add business tab
        add_frame = ttk.Frame(notebook)
        notebook.add(add_frame, text="Add My Business")
        
        self.create_business_form(add_frame)
    
    def load_business_listings(self):
        """Load business listings into the text widget"""
        self.business_text.delete(1.0, tk.END)
        rows = self._fetch_business_listings()
        if not rows:
            self.business_text.insert(tk.END, "No business listings found in the directory.\n")
            self.update_status("Business directory is empty")
            return

        lines = ["Alumni Business Directory Listings:\n"]
        for row in rows:
            owner_name = " ".join(filter(None, [row['first_name'], row['last_name']])).strip()
            if owner_name:
                owner_line = f"Owner: {owner_name}"
                if row['graduation_year']:
                    owner_line += f" (Class of {row['graduation_year']})"
            else:
                owner_line = "Owner: Unknown"

            lines.extend([
                f"🏢 {row['business_name']}",
                owner_line,
                f"Industry: {row['industry'] or 'Not specified'}",
                f"Location: {row['location'] or 'Not specified'}",
                f"Description: {(row['business_description'] or 'No description')[:200]}",
            ])
            if row['website']:
                lines.append(f"Website: {row['website']}")
            if row['services_offered']:
                lines.append(f"Services: {(row['services_offered'])[:200]}")
            if row['contact_email']:
                lines.append(f"📧 Contact: {row['contact_email']}")
            lines.append("-" * 40)

        self.business_text.insert(tk.END, "\n".join(lines))
        self.update_status(f"Loaded {len(rows)} business listings")
    
    def filter_businesses(self, industry):
        """Filter businesses by industry"""
        industry = (industry or "").strip()
        if not industry or industry == "All":
            self.load_business_listings()
            return

        rows = self._fetch_business_listings(industry)
        self.business_text.delete(1.0, tk.END)

        if not rows:
            self.business_text.insert(tk.END, f"No businesses found in the {industry} industry.\n")
            self.update_status(f"No business listings for industry '{industry}'")
            return

        for row in rows:
            owner_name = " ".join(filter(None, [row['first_name'], row['last_name']])).strip() or "Unknown"
            self.business_text.insert(tk.END, f"🏢 {row['business_name']}\n")
            self.business_text.insert(tk.END, f"Owner: {owner_name}\n")
            self.business_text.insert(tk.END, f"Industry: {row['industry'] or 'Not specified'}\n")
            self.business_text.insert(tk.END, f"Location: {row['location'] or 'Not specified'}\n")
            if row['business_description']:
                self.business_text.insert(tk.END, f"Description: {row['business_description'][:200]}\n")
            if row['website']:
                self.business_text.insert(tk.END, f"Website: {row['website']}\n")
            if row['services_offered']:
                self.business_text.insert(tk.END, f"Services: {row['services_offered'][:200]}\n")
            if row['contact_email']:
                self.business_text.insert(tk.END, f"Contact: {row['contact_email']}\n")
            self.business_text.insert(tk.END, "-" * 40 + "\n")

        self.update_status(f"Showing {len(rows)} business listings for industry '{industry}'")
    
    def create_business_form(self, parent):
        """Create the add business form"""
        # Title
        ttk.Label(parent, text="Add Your Business to the Directory", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        # Form fields
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        self.business_vars = {}
        
        business_fields = [
            ("Business Name*", "business_name"),
            ("Industry*", "industry"),
            ("Website", "website"),
            ("Contact Email*", "email"),
            ("Location", "location")
        ]
        
        for label, var_name in business_fields:
            field_frame = ttk.Frame(form_frame)
            field_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
            self.business_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.business_vars[var_name]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Description
        desc_frame = ttk.Frame(form_frame)
        desc_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(desc_frame, text="Business Description:").pack(anchor='w')
        self.business_desc = ScrolledText(desc_frame, height=4, wrap=tk.WORD)
        self.business_desc.pack(fill=tk.X, pady=(5, 0))
        
        # Services
        services_frame = ttk.Frame(form_frame)
        services_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(services_frame, text="Services Offered:").pack(anchor='w')
        self.business_services = ScrolledText(services_frame, height=3, wrap=tk.WORD)
        self.business_services.pack(fill=tk.X, pady=(5, 0))
        
        # Submit button
        ttk.Button(form_frame, text="Add Business to Directory", 
                  command=self.submit_business).pack(pady=20)
    
    def submit_business(self):
        """Submit business listing"""
        # Validate required fields
        required_fields = ['business_name', 'industry', 'email']
        for field in required_fields:
            if not self.business_vars[field].get().strip():
                messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                return
        
        messagebox.showinfo("Success", "Business listing added successfully!")
        self.update_status("Business listing submitted")
        
        # Clear form
        for var in self.business_vars.values():
            var.set("")
        self.business_desc.delete(1.0, tk.END)
        self.business_services.delete(1.0, tk.END)

    def update_business_listing(self):
        """Edit an existing business listing"""
        self.clear_content()
        self.update_status("Update Business Listing")

        ttk.Label(self.content_frame, text="Update Business Listing",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Business selection
        select_frame = ttk.LabelFrame(self.content_frame, text="Select Business to Update", padding=10)
        select_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        ttk.Label(select_frame, text="Select Business:").pack(side=tk.LEFT, padx=(0, 10))
        self.selected_business = tk.StringVar()

        # Load businesses owned by user
        business_options = []
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                cursor.execute("""
                    SELECT listing_id, business_name, industry
                    FROM business_directory
                    WHERE owner_id = ?
                    ORDER BY business_name
                """, (user_id,))
                businesses = cursor.fetchall()
                business_options = [f"{b[1]} - {b[2]} (ID: {b[0]})" for b in businesses]
        except:
            pass

        if not business_options:
            business_options = ["No businesses to update"]

        business_combo = ttk.Combobox(select_frame, textvariable=self.selected_business,
                                     values=business_options, width=50)
        business_combo.pack(side=tk.LEFT, padx=(0, 20))
        if business_options and business_options[0] != "No businesses to update":
            business_combo.set(business_options[0])

        ttk.Button(select_frame, text="Load Business",
                  command=self._load_business_for_edit).pack(side=tk.LEFT)

        # Edit form
        self.business_edit_frame = ttk.LabelFrame(self.content_frame, text="Business Details", padding=10)
        self.business_edit_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Form fields
        self.edit_business_vars = {}

        fields = [
            ("Business Name*", "name"),
            ("Industry*", "industry"),
            ("Website", "website"),
            ("Email*", "email"),
            ("Phone", "phone"),
            ("Location", "location")
        ]

        for label, var_name in fields:
            field_frame = ttk.Frame(self.business_edit_frame)
            field_frame.pack(fill=tk.X, pady=5)

            ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
            self.edit_business_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.edit_business_vars[var_name]).pack(
                side=tk.LEFT, fill=tk.X, expand=True)

        # Description
        ttk.Label(self.business_edit_frame, text="Description:").pack(anchor='w', pady=(10, 5))
        self.edit_business_description = ScrolledText(self.business_edit_frame, height=5, wrap=tk.WORD)
        self.edit_business_description.pack(fill=tk.X)

        # Services
        ttk.Label(self.business_edit_frame, text="Services Offered:").pack(anchor='w', pady=(10, 5))
        self.edit_business_services = ScrolledText(self.business_edit_frame, height=4, wrap=tk.WORD)
        self.edit_business_services.pack(fill=tk.X)

        # Action buttons
        button_frame = ttk.Frame(self.business_edit_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text="Save Changes",
                  command=self._save_business_changes).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Delete Listing",
                  command=self._delete_business_listing).pack(side=tk.LEFT)

    def _load_business_for_edit(self):
        """Load selected business data into edit form"""
        business_selection = self.selected_business.get()
        if not business_selection or business_selection == "No businesses to update":
            messagebox.showwarning("No Selection", "Please select a business to update.")
            return

        # Extract listing_id
        import re
        match = re.search(r'ID:\s*(\d+)', business_selection)
        if not match:
            messagebox.showerror("Error", "Invalid business selection.")
            return

        listing_id = int(match.group(1))

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT business_name, industry, website, email, phone,
                           location, description, services
                    FROM business_directory
                    WHERE listing_id = ?
                """, (listing_id,))
                business = cursor.fetchone()

                if business:
                    self.edit_business_vars['name'].set(business[0] or '')
                    self.edit_business_vars['industry'].set(business[1] or '')
                    self.edit_business_vars['website'].set(business[2] or '')
                    self.edit_business_vars['email'].set(business[3] or '')
                    self.edit_business_vars['phone'].set(business[4] or '')
                    self.edit_business_vars['location'].set(business[5] or '')

                    self.edit_business_description.delete(1.0, tk.END)
                    if business[6]:
                        self.edit_business_description.insert(tk.END, business[6])

                    self.edit_business_services.delete(1.0, tk.END)
                    if business[7]:
                        self.edit_business_services.insert(tk.END, business[7])

                    self.update_status(f"Loaded business: {business[0]}")
                else:
                    messagebox.showerror("Error", "Business not found.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load business: {str(e)}")

    def _save_business_changes(self):
        """Save changes to business listing"""
        business_selection = self.selected_business.get()
        if not business_selection:
            return

        # Extract listing_id
        import re
        match = re.search(r'ID:\s*(\d+)', business_selection)
        if not match:
            return

        listing_id = int(match.group(1))

        # Validation
        if not self.edit_business_vars['name'].get():
            messagebox.showerror("Validation Error", "Business name is required!")
            return

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE business_directory
                    SET business_name = ?, industry = ?, website = ?,
                        email = ?, phone = ?, location = ?,
                        description = ?, services = ?
                    WHERE listing_id = ?
                """, (
                    self.edit_business_vars['name'].get(),
                    self.edit_business_vars['industry'].get(),
                    self.edit_business_vars['website'].get(),
                    self.edit_business_vars['email'].get(),
                    self.edit_business_vars['phone'].get(),
                    self.edit_business_vars['location'].get(),
                    self.edit_business_description.get(1.0, tk.END).strip(),
                    self.edit_business_services.get(1.0, tk.END).strip(),
                    listing_id
                ))
                conn.commit()

            messagebox.showinfo("Success", "Business listing updated successfully!")
            self.update_status("Business listing saved")

            # Log activity
            from university_system.modules.shared.utils.activity_logger import log_activity
            log_activity('update', 'business_listing', listing_id=listing_id,
                       details={'name': self.edit_business_vars['name'].get()})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save changes: {str(e)}")

    def _delete_business_listing(self):
        """Delete a business listing"""
        if messagebox.askyesno("Confirm Deletion",
                              "Are you sure you want to delete this business listing?"):
            business_selection = self.selected_business.get()
            if not business_selection:
                return

            # Extract listing_id
            import re
            match = re.search(r'ID:\s*(\d+)', business_selection)
            if not match:
                return

            listing_id = int(match.group(1))

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM business_directory WHERE listing_id = ?", (listing_id,))
                    conn.commit()

                messagebox.showinfo("Success", "Business listing deleted successfully!")
                self.update_business_listing()  # Reload

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('delete', 'business_listing', listing_id=listing_id,
                           details={'action': 'deleted'})

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete listing: {str(e)}")

    def search_business_directory(self):
        """Search businesses in the directory"""
        self.clear_content()
        self.update_status("Search Business Directory")

        ttk.Label(self.content_frame, text="Search Business Directory",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Search criteria
        search_frame = ttk.LabelFrame(self.content_frame, text="Search Criteria", padding=10)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        # Row 1: Keyword and Industry
        row1 = ttk.Frame(search_frame)
        row1.pack(fill=tk.X, pady=5)

        ttk.Label(row1, text="Keyword:").pack(side=tk.LEFT, padx=(0, 10))
        self.biz_search_keyword = tk.StringVar()
        ttk.Entry(row1, textvariable=self.biz_search_keyword, width=25).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(row1, text="Industry:").pack(side=tk.LEFT, padx=(0, 10))
        self.biz_search_industry = tk.StringVar()
        industry_combo = ttk.Combobox(row1, textvariable=self.biz_search_industry,
                                     values=["All", "Technology", "Finance", "Healthcare",
                                            "Education", "Marketing", "Consulting", "Other"])
        industry_combo.pack(side=tk.LEFT)
        industry_combo.set("All")

        # Row 2: Location
        row2 = ttk.Frame(search_frame)
        row2.pack(fill=tk.X, pady=5)

        ttk.Label(row2, text="Location:").pack(side=tk.LEFT, padx=(0, 10))
        self.biz_search_location = tk.StringVar()
        ttk.Entry(row2, textvariable=self.biz_search_location, width=25).pack(side=tk.LEFT)

        # Search button
        ttk.Button(search_frame, text="Search",
                  command=self._perform_business_search).pack(pady=(10, 0))

        # Results table
        results_frame = ttk.LabelFrame(self.content_frame, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Business Name', 'Industry', 'Location', 'Owner', 'Contact')
        self.biz_search_tree = ttk.Treeview(results_frame, columns=columns, show='headings')

        for col in columns:
            self.biz_search_tree.heading(col, text=col)
            self.biz_search_tree.column(col, width=140)

        scrollbar_y = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                    command=self.biz_search_tree.yview)
        self.biz_search_tree.configure(yscrollcommand=scrollbar_y.set)

        self.biz_search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="View Details",
                  command=self._view_business_details).pack(side=tk.LEFT)

    def _perform_business_search(self):
        """Perform business directory search"""
        try:
            # Clear existing results
            for item in self.biz_search_tree.get_children():
                self.biz_search_tree.delete(item)

            with db_get_connection() as conn:
                cursor = conn.cursor()

                # Build query
                query = """
                    SELECT business_name, industry, location, owner_name, email
                    FROM business_directory
                    WHERE 1=1
                """
                params = []

                # Add keyword filter
                keyword = self.biz_search_keyword.get().strip()
                if keyword:
                    query += " AND (business_name LIKE ? OR description LIKE ? OR services LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

                # Add industry filter
                industry = self.biz_search_industry.get()
                if industry != "All":
                    query += " AND industry = ?"
                    params.append(industry)

                # Add location filter
                location = self.biz_search_location.get().strip()
                if location:
                    query += " AND location LIKE ?"
                    params.append(f"%{location}%")

                query += " ORDER BY business_name"

                cursor.execute(query, params)
                results = cursor.fetchall()

                for business in results:
                    self.biz_search_tree.insert('', tk.END, values=business)

                self.update_status(f"Found {len(results)} business(es)")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

    def _view_business_details(self):
        """View details for selected business"""
        if not hasattr(self, 'biz_search_tree'):
            return

        selection = self.biz_search_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a business to view.")
            return

        item = self.biz_search_tree.item(selection[0])
        business_data = item['values']

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Business Details - {business_data[0]}")
        details_window.geometry("600x500")
        details_window.configure(bg='white')

        frame = ttk.Frame(details_window, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=business_data[0],
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        info_text = f"""
Industry: {business_data[1]}
Location: {business_data[2]}
Owner: {business_data[3]}
Contact: {business_data[4]}
"""
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor='w')

        ttk.Button(frame, text="Close",
                  command=details_window.destroy).pack()

    def show_regional_chapters(self):
        """Show regional chapters interface"""
        self.clear_content()
        self.update_status("Regional Alumni Chapters")
        
        ttk.Label(self.content_frame, text="Regional Alumni Chapters", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different chapter views
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # View chapters tab
        chapters_frame = ttk.Frame(notebook)
        notebook.add(chapters_frame, text="All Chapters")
        
        chapters_text = ScrolledText(chapters_frame, wrap=tk.WORD)
        chapters_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        chapters_content = """Regional Alumni Chapters:

🌎 San Francisco Bay Area Chapter
Coordinator: Sarah Johnson (Class of 2015)
Members: 45
Location: San Francisco, CA
Description: Connecting tech industry alumni in the Bay Area
Created: 2023-01-15

📧 Contact: sf.chapter@alumni.edu
---

🌎 New York City Chapter
Coordinator: Michael Chen (Class of 2018)
Members: 62
Location: New York, NY
Description: Networking and professional development for NYC alumni
Created: 2022-09-20

📧 Contact: nyc.chapter@alumni.edu
---

🌎 Boston Chapter
Coordinator: Emily Davis (Class of 2020)
Members: 28
Location: Boston, MA
Description: Alumni community in the greater Boston area
Created: 2024-03-10

📧 Contact: boston.chapter@alumni.edu
"""
        chapters_text.insert(tk.END, chapters_content)
        
        # My chapters tab
        my_chapters_frame = ttk.Frame(notebook)
        notebook.add(my_chapters_frame, text="My Chapters")
        
        my_chapters_text = ScrolledText(my_chapters_frame, wrap=tk.WORD)
        my_chapters_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        my_chapters_content = """My Chapter Memberships:

✅ San Francisco Bay Area Chapter
   Role: Member
   Joined: 2025-06-15
   Last Activity: 2025-08-10
   
   Upcoming Events:
   • Tech Networking Mixer - August 25, 2025
   • Annual Chapter Picnic - September 15, 2025

---

Available Chapters to Join:

🔗 New York City Chapter
   [Join Chapter]
   
🔗 Boston Chapter
   [Join Chapter]
"""
        my_chapters_text.insert(tk.END, my_chapters_content)
    
    # Additional show methods for other features
    def show_create_newsletter(self):
        """Show newsletter creation interface"""
        self.clear_content()
        self.update_status("Newsletter Creation")
        
        ttk.Label(self.content_frame, text="Create Alumni Newsletter", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Newsletter form
        form_frame = ttk.LabelFrame(self.content_frame, text="Newsletter Details", padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Title
        title_frame = ttk.Frame(form_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="Newsletter Title:").pack(side=tk.LEFT, padx=(0, 10))
        self.newsletter_title = tk.StringVar()
        ttk.Entry(title_frame, textvariable=self.newsletter_title).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Target audience
        audience_frame = ttk.Frame(form_frame)
        audience_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(audience_frame, text="Target Audience:").pack(side=tk.LEFT, padx=(0, 10))
        self.newsletter_audience = tk.StringVar()
        audience_combo = ttk.Combobox(audience_frame, textvariable=self.newsletter_audience,
                                     values=["All Alumni", "By Graduation Year", "By Industry", "Donors Only", "Mentors Only"])
        audience_combo.pack(side=tk.LEFT, padx=(0, 10))
        audience_combo.set("All Alumni")
        
        # Content
        ttk.Label(form_frame, text="Newsletter Content:").pack(anchor='w', pady=(10, 5))
        self.newsletter_content = ScrolledText(form_frame, height=15, wrap=tk.WORD)
        self.newsletter_content.pack(fill=tk.BOTH, expand=True)
        
        # Sample content
        sample_content = """Subject: Alumni Newsletter - August 2025

Dear Alumni,

We hope this newsletter finds you well! Here are the latest updates from our alumni community:

🎓 ALUMNI SPOTLIGHT
This month we feature Sarah Johnson (Class of 2015), who recently launched her tech startup...

📅 UPCOMING EVENTS
• Annual Alumni Gala - September 15, 2025
• Tech Industry Networking - August 25, 2025
• Class of 2020 Reunion - October 10, 2025

💼 CAREER OPPORTUNITIES
New job postings from our alumni network:
• Senior Developer at Tech Corp
• Financial Analyst at Finance Plus
• Marketing Manager at StartupCo

🤝 MENTORSHIP PROGRAM
Join our expanding mentorship program! We currently have 50+ active mentor-mentee pairs...

💝 GIVING BACK
Thank you to our recent donors who contributed to the Annual Alumni Fund...

Best regards,
Alumni Relations Team
"""
        self.newsletter_content.insert(tk.END, sample_content)
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Send Newsletter", 
                  command=self.send_newsletter).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Save as Draft", 
                  command=self.save_newsletter_draft).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Preview", 
                  command=self.preview_newsletter).pack(side=tk.RIGHT, padx=(0, 10))

    def show_create_story(self):
        """Show create alumni story interface"""
        self.clear_content()
        self.update_status("Create Alumni Story")
        
        ttk.Label(self.content_frame, text="Create Alumni Story", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Get current user's alumni ID
        alumni_id = None
        if hasattr(self.current_user, 'username') and self.current_user['username'].startswith('A'):
            alumni_id = self.current_user['username']
        elif self.has_permission('manage_social_features'):
            alumni_id_frame = ttk.Frame(self.content_frame)
            alumni_id_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
            
            ttk.Label(alumni_id_frame, text="Alumni ID:").pack(side=tk.LEFT, padx=(0, 10))
            self.story_alumni_id = tk.StringVar()
            ttk.Entry(alumni_id_frame, textvariable=self.story_alumni_id).pack(side=tk.LEFT)
        
        # Story form
        form_frame = ttk.Frame(self.content_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Story type
        type_frame = ttk.Frame(form_frame)
        type_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(type_frame, text="Story Type:").pack(side=tk.LEFT, padx=(0, 10))
        self.story_type = tk.StringVar()
        type_combo = ttk.Combobox(type_frame, textvariable=self.story_type,
                                 values=["Career Achievement", "Community Service", "Entrepreneurship",
                                       "Research & Innovation", "Personal Journey", "Alumni Spotlight"])
        type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        type_combo.set("Career Achievement")
        
        # Title
        title_frame = ttk.Frame(form_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="Story Title:").pack(anchor='w')
        self.story_title = tk.StringVar()
        ttk.Entry(title_frame, textvariable=self.story_title).pack(fill=tk.X, pady=(5, 0))
        
        # Category
        category_frame = ttk.Frame(form_frame)
        category_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(category_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
        self.story_category = tk.StringVar()
        category_combo = ttk.Combobox(category_frame, textvariable=self.story_category,
                                     values=["Professional Success", "Community Impact", "Innovation",
                                           "Leadership", "Inspiration", "Education", "Technology", "Arts"])
        category_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        category_combo.set("Professional Success")
        
        # Content
        ttk.Label(form_frame, text="Story Content:").pack(anchor='w', pady=(10, 5))
        self.story_content = ScrolledText(form_frame, height=15, wrap=tk.WORD)
        self.story_content.pack(fill=tk.BOTH, expand=True)
        
        # Submit button
        ttk.Button(form_frame, text="Submit Story", 
                  command=self.submit_alumni_story).pack(pady=20)

    def submit_alumni_story(self):
        """Submit alumni story"""
        if not self.story_title.get().strip():
            messagebox.showerror("Validation Error", "Story title is required!")
            return
        
        content = self.story_content.get(1.0, tk.END).strip()
        if not content:
            messagebox.showerror("Validation Error", "Story content is required!")
            return
        
        messagebox.showinfo("Story Submitted", "Alumni story submitted successfully!")
        self.update_status("Alumni story submitted")
        
        # Clear form
        self.story_title.set("")
        self.story_category.set("Professional Success")
        self.story_type.set("Career Achievement")
        self.story_content.delete(1.0, tk.END)

    def show_donor_recognition(self):
        """Show donor recognition management"""
        self.clear_content()
        self.update_status("Donor Recognition")
        
        ttk.Label(self.content_frame, text="Donor Recognition Management", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different recognition views
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Recognition levels tab
        levels_frame = ttk.Frame(notebook)
        notebook.add(levels_frame, text="Recognition Levels")
        
        levels_text = ScrolledText(levels_frame, wrap=tk.WORD)
        levels_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        recognition_content = """Current Donor Recognition Levels:

    🥉 Bronze Supporter ($100+)
    - Newsletter subscription
    - Alumni directory access
    - 15 active donors

    🥈 Silver Supporter ($500+)  
    - Event invitations
    - Recognition in publications
    - 8 active donors

    🥇 Gold Supporter ($1,000+)
    - VIP event access
    - Annual appreciation dinner
    - 5 active donors

    💎 Platinum Supporter ($5,000+)
    - Board meeting invitations
    - Naming opportunities
    - 2 active donors

    💍 Diamond Supporter ($10,000+)
    - Personal meetings with leadership
    - Legacy society membership
    - 1 active donor

    🏆 Benefactor ($25,000+)
    - Permanent recognition
    - Advisory board invitation
    - 0 active donors
    """
        levels_text.insert(tk.END, recognition_content)
        
        # Update levels tab
        update_frame = ttk.Frame(notebook)
        notebook.add(update_frame, text="Update Levels")
        
        ttk.Label(update_frame, text="Update Donor Recognition Levels", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        ttk.Button(update_frame, text="Update All Recognition Levels", 
                  command=self.update_recognition_levels).pack(pady=20)
        
        # Recognition report
        report_frame = ttk.Frame(notebook)
        notebook.add(report_frame, text="Reports")
        
        self.recognition_report = ScrolledText(report_frame, wrap=tk.WORD)
        self.recognition_report.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Button(report_frame, text="Generate Recognition Report", 
                  command=self.generate_recognition_report_gui).pack(pady=10)

    def update_recognition_levels(self):
        """Update donor recognition levels"""
        # Simulate updating recognition levels
        messagebox.showinfo("Update Complete", "Donor recognition levels updated successfully!")
        self.update_status("Recognition levels updated")

    def generate_recognition_report_gui(self):
        """Generate recognition report in GUI"""
        self.recognition_report.delete(1.0, tk.END)
        
        report_content = """DONOR RECOGNITION LEVEL REPORT
    ==============================

    Bronze Supporter: 15 donors ($7,500.00)
    Silver Supporter: 8 donors ($12,000.00)  
    Gold Supporter: 5 donors ($15,000.00)
    Platinum Supporter: 2 donors ($18,000.00)
    Diamond Supporter: 1 donor ($15,000.00)
    Benefactor: 0 donors ($0.00)

    ----------------------------------------
    Total: 31 donors ($67,500.00)

    Recent Upgrades:
    - 3 donors upgraded to Silver level this month
    - 1 donor achieved Gold level
    - Recognition ceremony scheduled for next quarter

    Growth Trends:
    - 23% increase in total giving vs. last year
    - Average gift size increased 18%
    - Donor retention rate: 87%
    """
        
        self.recognition_report.insert(tk.END, report_content)
        self.update_status("Recognition report generated")

    def show_search_forum_posts(self):
        """Show forum post search interface"""
        search_window = tk.Toplevel(self.root)
        search_window.title("Search Forum Posts")
        search_window.geometry("400x300")
        
        ttk.Label(search_window, text="Search Forum Posts", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        # Search criteria
        search_frame = ttk.Frame(search_window)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search Term:").pack(anchor='w')
        search_term = tk.StringVar()
        ttk.Entry(search_frame, textvariable=search_term).pack(fill=tk.X, pady=(5, 10))
        
        ttk.Label(search_frame, text="Category:").pack(anchor='w')
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(search_frame, textvariable=category_var,
                                     values=["All", "General Discussion", "Career Advice", "Networking"])
        category_combo.pack(fill=tk.X, pady=(5, 0))
        category_combo.set("All")
        
        def perform_search():
            if search_term.get():
                messagebox.showinfo("Search Results", f"Searching for '{search_term.get()}' in {category_var.get()}")
            search_window.destroy()
        
        ttk.Button(search_window, text="Search", command=perform_search).pack(pady=20)

    def show_my_forum_posts(self):
        """Show current user's forum posts"""
        posts_window = tk.Toplevel(self.root)
        posts_window.title("My Forum Posts")
        posts_window.geometry("600x400")
        
        ttk.Label(posts_window, text="My Forum Posts", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        posts_text = ScrolledText(posts_window, wrap=tk.WORD)
        posts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        my_posts_content = """Your Forum Posts:

    📝 "Career Transition Tips" | Posted: 2025-08-15
    Category: Career Advice | Replies: 12 | Views: 156
    Looking for advice on switching from tech to consulting...

    📝 "Alumni Networking Event Ideas" | Posted: 2025-08-10  
    Category: Networking | Replies: 8 | Views: 89
    What are some creative ideas for regional chapter events?

    📝 "Startup Funding Experience" | Posted: 2025-08-05
    Category: General Discussion | Replies: 23 | Views: 234
    Sharing my journey securing seed funding for my startup...

    Total Posts: 3
    Total Replies Received: 43
    Total Views: 479
    """
        
        posts_text.insert(tk.END, my_posts_content)

    def show_moderate_forum_posts(self):
        """Show forum moderation interface"""
        if not self.has_permission('moderate_forum'):
            messagebox.showerror("Access Denied", "You don't have permission to moderate forum posts.")
            return
        
        moderate_window = tk.Toplevel(self.root)
        moderate_window.title("Moderate Forum Posts")
        moderate_window.geometry("700x500")
        
        ttk.Label(moderate_window, text="Forum Moderation", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        # Tabs for different moderation views
        notebook = ttk.Notebook(moderate_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pending posts
        pending_frame = ttk.Frame(notebook)
        notebook.add(pending_frame, text="Pending Posts")
        
        pending_text = ScrolledText(pending_frame, wrap=tk.WORD)
        pending_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        pending_content = """Posts Pending Moderation:

    ⏳ "New Job Opportunity at My Company"
    Author: John Smith | Category: Job Opportunities
    Posted: 2025-08-19 14:30
    Content: Looking for talented alumni to join our growing team...
    [Approve] [Reject] [Edit]

    ⏳ "Question About Alumni Benefits"  
    Author: Sarah Wilson | Category: General Discussion
    Posted: 2025-08-19 11:15
    Content: Can someone clarify what benefits are included...
    [Approve] [Reject] [Edit]
    """
        
        pending_text.insert(tk.END, pending_content)
        
        # Reported posts
        reported_frame = ttk.Frame(notebook)
        notebook.add(reported_frame, text="Reported Posts")
        
        reported_text = ScrolledText(reported_frame, wrap=tk.WORD)
        reported_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        reported_content = """Reported Posts:

    🚩 "Controversial Industry Opinion"
    Author: Anonymous | Reported by: 3 users
    Reason: Inappropriate content
    Action Required: Review and decide
    [View Post] [Remove] [Keep] [Warn Author]

    No other reported posts at this time.
    """
        
        reported_text.insert(tk.END, reported_content)
    
    def send_newsletter(self):
        """Send the newsletter"""
        if not self.newsletter_title.get().strip():
            messagebox.showerror("Validation Error", "Newsletter title is required!")
            return
        
        if not self.newsletter_content.get(1.0, tk.END).strip():
            messagebox.showerror("Validation Error", "Newsletter content is required!")
            return
        
        # Confirmation dialog
        if messagebox.askyesno("Confirm Send", 
                              f"Send newsletter '{self.newsletter_title.get()}' to {self.newsletter_audience.get()}?"):
            messagebox.showinfo("Newsletter Sent", "Newsletter has been sent successfully!")
            self.update_status("Newsletter sent to recipients")
    
    def save_newsletter_draft(self):
        """Save newsletter as draft"""
        messagebox.showinfo("Draft Saved", "Newsletter saved as draft successfully!")
        self.update_status("Newsletter draft saved")
    
    def preview_newsletter(self):
        """Preview the newsletter"""
        preview_window = tk.Toplevel(self.root)
        preview_window.title(f"Newsletter Preview - {self.newsletter_title.get()}")
        preview_window.geometry("600x500")
        
        preview_text = ScrolledText(preview_window, wrap=tk.WORD, padx=10, pady=10)
        preview_text.pack(fill=tk.BOTH, expand=True)
        
        preview_content = f"Title: {self.newsletter_title.get()}\n"
        preview_content += f"Audience: {self.newsletter_audience.get()}\n"
        preview_content += f"Send Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        preview_content += "=" * 50 + "\n\n"
        preview_content += self.newsletter_content.get(1.0, tk.END)
        
        preview_text.insert(tk.END, preview_content)
        preview_text.config(state=tk.DISABLED)
    
    def show_forum(self):
        """Show alumni forum interface"""
        self.clear_content()
        self.update_status("Alumni Forum")
        
        ttk.Label(self.content_frame, text="Alumni Forum", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Forum tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Recent posts tab
        posts_frame = ttk.Frame(notebook)
        notebook.add(posts_frame, text="Recent Posts")
        
        posts_text = ScrolledText(posts_frame, wrap=tk.WORD)
        posts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        forum_content = """Recent Forum Posts:

💼 Career Advice | Posted by: Sarah Johnson | 2 hours ago
"Transitioning from Academia to Industry - Tips and Experiences"
Looking for advice on making the switch from research to industry roles...
📝 5 replies | 👁 23 views

🤝 Networking | Posted by: Michael Chen | 5 hours ago  
"NYC Alumni Meetup - August 25th"
Organizing an informal meetup for NYC-based alumni. Who's interested?
📝 12 replies | 👁 45 views

🎓 Class Updates | Posted by: Emily Davis | 1 day ago
"Class of 2020 - Where are we now?"
Let's catch up! Share what you've been up to since graduation...
📝 18 replies | 👁 67 views

💡 Industry News | Posted by: John Smith | 2 days ago
"The Future of Remote Work - Alumni Perspectives"
How has remote work affected your career? Share your thoughts...
📝 8 replies | 👁 34 views
"""
        posts_text.insert(tk.END, forum_content)
        
        # Create post tab
        create_frame = ttk.Frame(notebook)
        notebook.add(create_frame, text="Create Post")
        
        self.create_forum_post_form(create_frame)
    
    def create_forum_post_form(self, parent):
        """Create the forum post form"""
        ttk.Label(parent, text="Create New Forum Post", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Category
        cat_frame = ttk.Frame(form_frame)
        cat_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(cat_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
        self.post_category = tk.StringVar()
        cat_combo = ttk.Combobox(cat_frame, textvariable=self.post_category,
                                values=["General Discussion", "Career Advice", "Networking", 
                                       "Industry News", "Class Updates", "Events", "Mentorship"])
        cat_combo.pack(side=tk.LEFT)
        cat_combo.set("General Discussion")
        
        # Title
        title_frame = ttk.Frame(form_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="Post Title:").pack(anchor='w')
        self.post_title = tk.StringVar()
        ttk.Entry(title_frame, textvariable=self.post_title).pack(fill=tk.X, pady=(5, 0))
        
        # Content
        ttk.Label(form_frame, text="Post Content:").pack(anchor='w', pady=(10, 5))
        self.post_content = ScrolledText(form_frame, height=10, wrap=tk.WORD)
        self.post_content.pack(fill=tk.BOTH, expand=True)
        
        # Submit button
        ttk.Button(form_frame, text="Post to Forum", 
                  command=self.submit_forum_post).pack(pady=20)
    
    def submit_forum_post(self):
        """Submit forum post"""
        if not self.post_title.get().strip():
            messagebox.showerror("Validation Error", "Post title is required!")
            return
        
        if not self.post_content.get(1.0, tk.END).strip():
            messagebox.showerror("Validation Error", "Post content is required!")
            return
        
        messagebox.showinfo("Post Created", "Forum post created successfully!")
        self.update_status("Forum post submitted")
        
        # Clear form
        self.post_title.set("")
        self.post_content.delete(1.0, tk.END)

    def view_forum_posts(self):
        """View all forum posts with filtering options"""
        self.clear_content()
        self.update_status("Forum Posts")

        ttk.Label(self.content_frame, text="Forum Posts",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Filter frame
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
        self.forum_filter_category = tk.StringVar()
        category_combo = ttk.Combobox(filter_frame, textvariable=self.forum_filter_category,
                                     values=["All", "General Discussion", "Career Advice", "Networking",
                                            "Industry News", "Class Updates", "Events", "Mentorship"])
        category_combo.pack(side=tk.LEFT, padx=(0, 20))
        category_combo.set("All")

        ttk.Label(filter_frame, text="Sort by:").pack(side=tk.LEFT, padx=(0, 10))
        self.forum_sort_by = tk.StringVar()
        sort_combo = ttk.Combobox(filter_frame, textvariable=self.forum_sort_by,
                                 values=["Most Recent", "Most Replies", "Most Views", "Oldest First"])
        sort_combo.pack(side=tk.LEFT, padx=(0, 20))
        sort_combo.set("Most Recent")

        ttk.Button(filter_frame, text="Apply Filter",
                  command=self._load_forum_posts).pack(side=tk.LEFT)

        # Posts table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Title', 'Author', 'Category', 'Replies', 'Views', 'Last Activity')
        self.forum_posts_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.forum_posts_tree.heading(col, text=col)
            self.forum_posts_tree.column(col, width=130)

        # Scrollbars
        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.forum_posts_tree.yview)
        self.forum_posts_tree.configure(yscrollcommand=scrollbar_y.set)

        self.forum_posts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load posts
        self._load_forum_posts()

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="View Post",
                  command=self.view_forum_post_details).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Create New Post",
                  command=self.show_forum).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self._load_forum_posts).pack(side=tk.LEFT)

    def _load_forum_posts(self):
        """Load forum posts from database"""
        try:
            # Clear existing data
            for item in self.forum_posts_tree.get_children():
                self.forum_posts_tree.delete(item)

            with db_get_connection() as conn:
                cursor = conn.cursor()

                # Build query
                query = """
                    SELECT post_id, title, author_name, category, reply_count,
                           view_count, last_activity_date
                    FROM forum_posts
                    WHERE 1=1
                """
                params = []

                # Add category filter
                category = self.forum_filter_category.get()
                if category != "All":
                    query += " AND category = ?"
                    params.append(category)

                # Add sorting
                sort_by = self.forum_sort_by.get()
                if sort_by == "Most Recent":
                    query += " ORDER BY last_activity_date DESC"
                elif sort_by == "Most Replies":
                    query += " ORDER BY reply_count DESC"
                elif sort_by == "Most Views":
                    query += " ORDER BY view_count DESC"
                elif sort_by == "Oldest First":
                    query += " ORDER BY created_date ASC"

                cursor.execute(query, params)
                posts = cursor.fetchall()

                for post in posts:
                    # Display without post_id
                    self.forum_posts_tree.insert('', tk.END, values=post[1:])

                self.update_status(f"Loaded {len(posts)} forum post(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load forum posts: {str(e)}")

    def view_forum_post_details(self):
        """View details for a selected forum post"""
        if not hasattr(self, 'forum_posts_tree'):
            messagebox.showwarning("Not Available", "Please use the 'View Forum Posts' feature first.")
            return

        selection = self.forum_posts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a forum post to view.")
            return

        item = self.forum_posts_tree.item(selection[0])
        post_data = item['values']

        # Create detail window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Forum Post - {post_data[0]}")
        detail_window.geometry("700x600")
        detail_window.configure(bg='white')

        # Main frame with scrollbar
        main_frame = ttk.Frame(detail_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Post header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text=post_data[0],
                 font=('Arial', 16, 'bold')).pack(anchor='w')

        meta_text = f"Author: {post_data[1]} | Category: {post_data[2]} | Replies: {post_data[3]} | Views: {post_data[4]}"
        ttk.Label(header_frame, text=meta_text,
                 font=('Arial', 9), foreground='gray').pack(anchor='w', pady=(5, 0))

        # Post content
        content_frame = ttk.LabelFrame(main_frame, text="Post Content", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        content_text = ScrolledText(content_frame, wrap=tk.WORD, height=10)
        content_text.pack(fill=tk.BOTH, expand=True)

        # Try to load actual content from database
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT content FROM forum_posts WHERE title = ?", (post_data[0],))
                result = cursor.fetchone()
                if result:
                    content_text.insert(tk.END, result[0])
                else:
                    content_text.insert(tk.END, "[Post content would be displayed here]")
        except:
            content_text.insert(tk.END, "[Post content would be displayed here]")

        content_text.config(state='disabled')

        # Replies section
        replies_frame = ttk.LabelFrame(main_frame, text="Replies", padding=10)
        replies_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        replies_text = ScrolledText(replies_frame, wrap=tk.WORD, height=8)
        replies_text.pack(fill=tk.BOTH, expand=True)
        replies_text.insert(tk.END, "[Replies would be displayed here]")
        replies_text.config(state='disabled')

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Add Reply",
                  command=lambda: self._show_reply_dialog(post_data[0], detail_window)).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Close",
                  command=detail_window.destroy).pack(side=tk.LEFT)

    def _show_reply_dialog(self, post_title, parent_window):
        """Show dialog to add a reply to a forum post"""
        reply_window = tk.Toplevel(parent_window)
        reply_window.title(f"Reply to: {post_title}")
        reply_window.geometry("500x350")
        reply_window.configure(bg='white')
        reply_window.grab_set()

        frame = ttk.Frame(reply_window, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Reply to: {post_title}",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        ttk.Label(frame, text="Your Reply:").pack(anchor='w')
        reply_text = ScrolledText(frame, wrap=tk.WORD, height=10)
        reply_text.pack(fill=tk.BOTH, expand=True, pady=(5, 20))

        def submit_reply():
            reply_content = reply_text.get(1.0, tk.END).strip()
            if not reply_content:
                messagebox.showerror("Validation Error", "Reply cannot be empty!")
                return

            try:
                self.add_forum_reply(post_title, reply_content)
                messagebox.showinfo("Success", "Reply posted successfully!")
                reply_window.destroy()
                parent_window.destroy()  # Close parent detail window
                self.view_forum_posts()  # Refresh forum view
            except Exception as e:
                messagebox.showerror("Error", f"Failed to post reply: {str(e)}")

        ttk.Button(frame, text="Post Reply",
                  command=submit_reply).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame, text="Cancel",
                  command=reply_window.destroy).pack(side=tk.LEFT)

    def add_forum_reply(self, post_title, reply_content):
        """Add a reply to a forum post"""
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                # Get post_id
                cursor.execute("SELECT post_id FROM forum_posts WHERE title = ?", (post_title,))
                result = cursor.fetchone()

                if not result:
                    raise ValueError("Forum post not found")

                post_id = result[0]

                # Insert reply
                cursor.execute("""
                    INSERT INTO forum_replies (post_id, author_id, author_name, content, created_date)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (post_id, user_id, self.current_user.get('username', 'Anonymous'), reply_content))

                # Update post reply count and last activity
                cursor.execute("""
                    UPDATE forum_posts
                    SET reply_count = reply_count + 1,
                        last_activity_date = datetime('now')
                    WHERE post_id = ?
                """, (post_id,))

                conn.commit()
                self.update_status("Forum reply posted successfully")

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('create', 'forum_reply', reply_id=cursor.lastrowid,
                           details={'post_id': post_id, 'post_title': post_title})

        except Exception as e:
            raise Exception(f"Failed to add forum reply: {str(e)}")

    def show_stories(self):
        """Show alumni stories interface"""
        self.clear_content()
        self.update_status("Alumni Stories")
        
        ttk.Label(self.content_frame, text="Alumni Stories & Spotlights", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Stories tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Featured stories tab
        featured_frame = ttk.Frame(notebook)
        notebook.add(featured_frame, text="Featured Stories")
        
        featured_text = ScrolledText(featured_frame, wrap=tk.WORD)
        featured_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        stories_content = """Featured Alumni Stories:

⭐ "From Student to CEO: Sarah's Journey"
By: Sarah Johnson (Class of 2015) | Category: Career Achievement
Published: August 10, 2025 | Views: 245

Sarah shares her inspiring journey from computer science student to founding her own tech startup. "The skills I learned at university gave me the foundation, but the alumni network provided the connections and mentorship that made it possible..."

Read more →

---

⭐ "Making a Difference in Healthcare"  
By: Dr. Lisa Martinez (Class of 2012) | Category: Community Impact
Published: August 5, 2025 | Views: 189

Dr. Martinez talks about her work providing healthcare in underserved communities. "My education taught me medicine, but my experiences taught me compassion. Every day I'm grateful for the opportunity to serve..."

Read more →

---

⭐ "Innovation in Renewable Energy"
By: Michael Green (Class of 2017) | Category: Innovation
Published: July 28, 2025 | Views: 156

Michael discusses his breakthrough research in solar energy efficiency. "The research opportunities at university sparked my passion for renewable energy. Now I'm working to make clean energy accessible to everyone..."

Read more →
"""
        featured_text.insert(tk.END, stories_content)
        
        # Submit story tab
        submit_frame = ttk.Frame(notebook)
        notebook.add(submit_frame, text="Submit Your Story")
        
        self.create_story_form(submit_frame)
    
    def create_story_form(self, parent):
        """Create the story submission form"""
        ttk.Label(parent, text="Share Your Alumni Story", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Story type
        type_frame = ttk.Frame(form_frame)
        type_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(type_frame, text="Story Type:").pack(side=tk.LEFT, padx=(0, 10))
        self.story_type = tk.StringVar()
        type_combo = ttk.Combobox(type_frame, textvariable=self.story_type,
                                 values=["Career Achievement", "Community Service", "Entrepreneurship",
                                        "Research & Innovation", "Personal Journey", "Alumni Spotlight"])
        type_combo.pack(side=tk.LEFT)
        type_combo.set("Career Achievement")
        
        # Title
        title_frame = ttk.Frame(form_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="Story Title:").pack(anchor='w')
        self.story_title = tk.StringVar()
        ttk.Entry(title_frame, textvariable=self.story_title).pack(fill=tk.X, pady=(5, 0))
        
        # Content
        ttk.Label(form_frame, text="Your Story:").pack(anchor='w', pady=(10, 5))
        self.story_content = ScrolledText(form_frame, height=12, wrap=tk.WORD)
        self.story_content.pack(fill=tk.BOTH, expand=True)
        
        # Placeholder text
        placeholder_text = """Tell us your story! Share your journey, achievements, challenges overcome, or how your education has impacted your life and career.

Some ideas to get you started:
• What has been your biggest accomplishment since graduation?
• How has your education influenced your career path?
• What advice would you give to current students or recent graduates?
• Describe a project or initiative you're proud of
• Share how you're making a difference in your community or industry

Your story will inspire other alumni and current students!"""
        
        self.story_content.insert(tk.END, placeholder_text)
        
        # Submit button
        ttk.Button(form_frame, text="Submit Story", 
                  command=self.submit_story).pack(pady=20)
    
    def submit_story(self):
        """Submit alumni story"""
        if not self.story_title.get().strip():
            messagebox.showerror("Validation Error", "Story title is required!")
            return
        
        content = self.story_content.get(1.0, tk.END).strip()
        if not content or content.startswith("Tell us your story"):
            messagebox.showerror("Validation Error", "Please write your story content!")
            return
        
        messagebox.showinfo("Story Submitted", "Your story has been submitted for review. Thank you for sharing!")
        self.update_status("Alumni story submitted")
        
        # Clear form
        self.story_title.set("")
        self.story_content.delete(1.0, tk.END)
    
    def show_photo_gallery(self):
        """Show photo gallery interface"""
        self.clear_content()
        self.update_status("Photo Gallery")
        
        ttk.Label(self.content_frame, text="Alumni Photo Gallery", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Gallery tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Browse photos tab
        browse_frame = ttk.Frame(notebook)
        notebook.add(browse_frame, text="Browse Photos")
        
        # Event filter
        filter_frame = ttk.Frame(browse_frame)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(filter_frame, text="Filter by Event:").pack(side=tk.LEFT, padx=(0, 10))
        event_var = tk.StringVar()
        event_combo = ttk.Combobox(filter_frame, textvariable=event_var,
                                  values=["All Events", "Annual Gala 2025", "Tech Networking", "Class Reunions"])
        event_combo.pack(side=tk.LEFT)
        event_combo.set("All Events")
        
        # Photo listings
        photo_text = ScrolledText(browse_frame, wrap=tk.WORD)
        photo_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        photo_content = """Photo Gallery - Recent Uploads:

📸 Annual Alumni Gala 2025
Uploaded by: Sarah Johnson | Date: August 15, 2025
Photos: 15 | Event Date: August 10, 2025
Caption: "Amazing turnout at this year's gala! Great to see everyone."
[View Album]

📸 Tech Industry Networking Event  
Uploaded by: Michael Chen | Date: August 12, 2025
Photos: 8 | Event Date: August 8, 2025
Caption: "Productive networking session with tech alumni."
[View Album]

📸 Class of 2020 Reunion Planning
Uploaded by: Emily Davis | Date: August 5, 2025
Photos: 12 | Event Date: August 3, 2025
Caption: "Planning committee hard at work for the upcoming reunion!"
[View Album]

📸 Regional Chapter Meetup - SF Bay Area
Uploaded by: Alex Wong | Date: July 28, 2025
Photos: 20 | Event Date: July 25, 2025
Caption: "Great turnout for our monthly Bay Area chapter meeting."
[View Album]
"""
        photo_text.insert(tk.END, photo_content)
        
        # Upload photos tab
        upload_frame = ttk.Frame(notebook)
        notebook.add(upload_frame, text="Upload Photos")
        
        self.create_photo_upload_form(upload_frame)
    
    def create_photo_upload_form(self, parent):
        """Create photo upload form"""
        ttk.Label(parent, text="Upload Event Photos", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Event selection
        event_frame = ttk.Frame(form_frame)
        event_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(event_frame, text="Select Event:").pack(side=tk.LEFT, padx=(0, 10))
        self.photo_event = tk.StringVar()
        events = self._get_event_options()
        self._event_lookup = {row['event_name']: row['event_id'] for row in events}
        if self._event_lookup:
            event_names = list(self._event_lookup.keys())
        else:
            event_names = []
        event_combo = ttk.Combobox(event_frame, textvariable=self.photo_event,
                                  values=event_names if event_names else ["No events available"],
                                  state='readonly' if event_names else 'disabled')
        event_combo.pack(side=tk.LEFT)
        if event_names:
            self.photo_event.set(event_names[0])
        else:
            self.photo_event.set("")
        
        # File selection (simulated)
        file_frame = ttk.Frame(form_frame)
        file_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(file_frame, text="Select Photos:").pack(anchor='w')
        file_info_frame = ttk.Frame(file_frame)
        file_info_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.selected_files = tk.StringVar(value="No files selected")
        ttk.Label(file_info_frame, textvariable=self.selected_files).pack(side=tk.LEFT)
        ttk.Button(file_info_frame, text="Browse Files", 
                  command=self.browse_photo_files).pack(side=tk.RIGHT)
        
        # Caption
        caption_frame = ttk.Frame(form_frame)
        caption_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(caption_frame, text="Album Caption:").pack(anchor='w')
        self.photo_caption = ScrolledText(caption_frame, height=3, wrap=tk.WORD)
        self.photo_caption.pack(fill=tk.X, pady=(5, 0))
        
        # Upload button
        ttk.Button(form_frame, text="Upload Photos", 
                  command=self.upload_photos).pack(pady=20)
    
    def browse_photo_files(self):
        """Select photo files for upload and stage them for storage."""
        filepaths = filedialog.askopenfilenames(
            title="Select photo files",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("All files", "*.*")
            ]
        )
        if not filepaths:
            return

        self._photo_file_paths = list(filepaths)
        filenames = [Path(path).name for path in self._photo_file_paths]
        preview = ", ".join(filenames[:3])
        if len(filenames) > 3:
            preview += ", ..."
        self.selected_files.set(f"{len(filenames)} photo(s) selected: {preview}")
        self.update_status(f"Selected {len(filenames)} photo(s) for upload")
    
    def upload_photos(self):
        """Upload photos"""
        if not self.photo_event.get():
            messagebox.showerror("Validation Error", "Please select an event!")
            return
        
        if not getattr(self, "_photo_file_paths", None):
            messagebox.showerror("Validation Error", "Please select photos to upload!")
            return
        
        event_name = self.photo_event.get()
        event_id = self._event_lookup.get(event_name)
        if not event_id:
            messagebox.showerror("Validation Error", "Selected event is not available.")
            return

        caption = self.photo_caption.get("1.0", tk.END).strip()
        uploader = self._current_user_id()
        upload_time = datetime.now().isoformat()

        stored_files = []
        for index, source_path in enumerate(self._photo_file_paths, start=1):
            src = Path(source_path)
            if not src.exists():
                continue
            destination = self._photo_storage_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{index}_{src.name}"
            shutil.copy2(src, destination)
            stored_files.append(destination)

        if not stored_files:
            messagebox.showerror("Upload Failed", "Selected files could not be processed.")
            return

        conn = self._get_db_connection()
        cursor = conn.cursor()
        for filepath in stored_files:
            cursor.execute(
                """
                INSERT INTO photo_gallery (event_id, uploaded_by, photo_path, caption, upload_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, uploader, str(filepath), caption, upload_time)
            )
        conn.commit()
        conn.close()

        messagebox.showinfo("Upload Complete", "Photos uploaded successfully to the gallery!")
        self.update_status(f"Uploaded {len(stored_files)} photo(s) to gallery")
        self._photo_file_paths = []
        self.selected_files.set("No files selected")
        self.photo_caption.delete("1.0", tk.END)

    def view_my_photos(self):
        """View photos uploaded by the current user"""
        self.clear_content()
        self.update_status("My Photos")

        ttk.Label(self.content_frame, text="My Uploaded Photos",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Photos table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Event', 'Photo Path', 'Caption', 'Upload Date', 'Status')
        self.my_photos_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.my_photos_tree.heading(col, text=col)
            self.my_photos_tree.column(col, width=150)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.my_photos_tree.yview)
        self.my_photos_tree.configure(yscrollcommand=scrollbar_y.set)

        self.my_photos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load user's photos
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                query = """
                    SELECT e.event_name, pg.photo_path, pg.caption,
                           pg.upload_date, pg.status
                    FROM photo_gallery pg
                    LEFT JOIN events e ON pg.event_id = e.event_id
                    WHERE pg.uploaded_by = ?
                    ORDER BY pg.upload_date DESC
                """
                cursor.execute(query, (user_id,))
                photos = cursor.fetchall()

                for photo in photos:
                    # Shorten photo path for display
                    display_photo = list(photo)
                    if display_photo[1]:
                        display_photo[1] = Path(display_photo[1]).name
                    self.my_photos_tree.insert('', tk.END, values=display_photo)

                self.update_status(f"Loaded {len(photos)} photo(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load photos: {str(e)}")

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Delete Photo",
                  command=self._delete_my_photo).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self.view_my_photos).pack(side=tk.LEFT)

    def _delete_my_photo(self):
        """Delete a selected photo"""
        if not hasattr(self, 'my_photos_tree'):
            return

        selection = self.my_photos_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a photo to delete.")
            return

        if messagebox.askyesno("Confirm Deletion",
                               "Are you sure you want to delete this photo?"):
            item = self.my_photos_tree.item(selection[0])
            photo_data = item['values']

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    # Delete from database
                    cursor.execute("""
                        DELETE FROM photo_gallery
                        WHERE uploaded_by = ? AND photo_path LIKE ?
                    """, (user_id, f"%{photo_data[1]}"))

                    conn.commit()

                messagebox.showinfo("Success", "Photo deleted successfully!")
                self.view_my_photos()  # Refresh

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('delete', 'photo', details={'photo_path': photo_data[1]})

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete photo: {str(e)}")

    def moderate_photos(self):
        """Admin function to moderate uploaded photos"""
        if not self.has_permission('admin') and not self.has_permission('manage_alumni'):
            messagebox.showerror("Permission Denied",
                               "You don't have permission to moderate photos.")
            return

        self.clear_content()
        self.update_status("Moderate Photos")

        ttk.Label(self.content_frame, text="Photo Moderation",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Filter frame
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        ttk.Label(filter_frame, text="Filter by Status:").pack(side=tk.LEFT, padx=(0, 10))
        self.photo_status_filter = tk.StringVar()
        status_combo = ttk.Combobox(filter_frame, textvariable=self.photo_status_filter,
                                   values=["All", "pending", "approved", "rejected"])
        status_combo.pack(side=tk.LEFT, padx=(0, 20))
        status_combo.set("pending")

        ttk.Button(filter_frame, text="Apply Filter",
                  command=self._load_photos_for_moderation).pack(side=tk.LEFT)

        # Photos table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Photo ID', 'Event', 'Uploader', 'Caption', 'Upload Date', 'Status')
        self.moderate_photos_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.moderate_photos_tree.heading(col, text=col)
            self.moderate_photos_tree.column(col, width=130)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.moderate_photos_tree.yview)
        self.moderate_photos_tree.configure(yscrollcommand=scrollbar_y.set)

        self.moderate_photos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load photos for moderation
        self._load_photos_for_moderation()

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Approve",
                  command=lambda: self._moderate_photo_action('approved')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Reject",
                  command=lambda: self._moderate_photo_action('rejected')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Delete",
                  command=lambda: self._moderate_photo_action('deleted')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self._load_photos_for_moderation).pack(side=tk.LEFT)

    def _load_photos_for_moderation(self):
        """Load photos for moderation based on filter"""
        try:
            # Clear existing data
            for item in self.moderate_photos_tree.get_children():
                self.moderate_photos_tree.delete(item)

            with db_get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT pg.photo_id, e.event_name, pg.uploaded_by,
                           pg.caption, pg.upload_date, pg.status
                    FROM photo_gallery pg
                    LEFT JOIN events e ON pg.event_id = e.event_id
                    WHERE 1=1
                """
                params = []

                # Add status filter
                status = self.photo_status_filter.get()
                if status != "All":
                    query += " AND pg.status = ?"
                    params.append(status)

                query += " ORDER BY pg.upload_date DESC"

                cursor.execute(query, params)
                photos = cursor.fetchall()

                for photo in photos:
                    self.moderate_photos_tree.insert('', tk.END, values=photo)

                self.update_status(f"Loaded {len(photos)} photo(s) for moderation")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load photos: {str(e)}")

    def _moderate_photo_action(self, action):
        """Perform moderation action on selected photo"""
        if not hasattr(self, 'moderate_photos_tree'):
            return

        selection = self.moderate_photos_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a photo.")
            return

        item = self.moderate_photos_tree.item(selection[0])
        photo_data = item['values']
        photo_id = photo_data[0]

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()

                if action == 'deleted':
                    # Delete the photo
                    cursor.execute("DELETE FROM photo_gallery WHERE photo_id = ?", (photo_id,))
                    message = "Photo deleted successfully!"
                else:
                    # Update status
                    cursor.execute("""
                        UPDATE photo_gallery
                        SET status = ?
                        WHERE photo_id = ?
                    """, (action, photo_id))
                    message = f"Photo {action} successfully!"

                conn.commit()

            messagebox.showinfo("Success", message)
            self._load_photos_for_moderation()  # Refresh

            # Log activity
            from university_system.modules.shared.utils.activity_logger import log_activity
            log_activity('update', 'photo', photo_id=photo_id,
                       details={'action': action, 'moderator': self._current_user_id()})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform action: {str(e)}")

    def view_event_photos(self):
        """View photos filtered by specific event"""
        self.clear_content()
        self.update_status("Event Photos")

        ttk.Label(self.content_frame, text="Event Photos",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Event selection frame
        event_frame = ttk.Frame(self.content_frame)
        event_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        ttk.Label(event_frame, text="Select Event:").pack(side=tk.LEFT, padx=(0, 10))
        self.event_photo_filter = tk.StringVar()

        # Get event options
        event_options = []
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT event_id, event_name FROM events ORDER BY event_date DESC")
                events = cursor.fetchall()
                event_options = [f"{event[1]} (ID: {event[0]})" for event in events]
        except:
            pass

        if not event_options:
            event_options = ["No events available"]

        event_combo = ttk.Combobox(event_frame, textvariable=self.event_photo_filter,
                                   values=event_options, width=40)
        event_combo.pack(side=tk.LEFT, padx=(0, 20))
        if event_options and event_options[0] != "No events available":
            event_combo.set(event_options[0])

        ttk.Button(event_frame, text="Load Photos",
                  command=self._load_event_photos).pack(side=tk.LEFT)

        # Photos table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Photo ID', 'Uploader', 'Caption', 'Upload Date', 'Status')
        self.event_photos_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.event_photos_tree.heading(col, text=col)
            self.event_photos_tree.column(col, width=150)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.event_photos_tree.yview)
        self.event_photos_tree.configure(yscrollcommand=scrollbar_y.set)

        self.event_photos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Refresh",
                  command=self._load_event_photos).pack(side=tk.LEFT)

    def _load_event_photos(self):
        """Load photos for selected event"""
        try:
            # Clear existing data
            for item in self.event_photos_tree.get_children():
                self.event_photos_tree.delete(item)

            event_selection = self.event_photo_filter.get()
            if not event_selection or event_selection == "No events available":
                messagebox.showwarning("No Event", "Please select an event.")
                return

            # Extract event_id from selection (format: "Event Name (ID: 123)")
            import re
            match = re.search(r'ID:\s*(\d+)', event_selection)
            if not match:
                messagebox.showerror("Error", "Invalid event selection.")
                return

            event_id = int(match.group(1))

            with db_get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT photo_id, uploaded_by, caption, upload_date, status
                    FROM photo_gallery
                    WHERE event_id = ?
                    ORDER BY upload_date DESC
                """
                cursor.execute(query, (event_id,))
                photos = cursor.fetchall()

                for photo in photos:
                    self.event_photos_tree.insert('', tk.END, values=photo)

                self.update_status(f"Loaded {len(photos)} photo(s) for event")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load event photos: {str(e)}")

    # Event-related methods
    def show_create_event(self):
        """Show create event interface"""
        self.clear_content()
        self.update_status("Create Event")
        
        ttk.Label(self.content_frame, text="Create Alumni Event", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create scrollable form
        canvas = tk.Canvas(self.content_frame)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Event form
        self.event_vars = {}
        
        # Basic details
        basic_frame = ttk.LabelFrame(scrollable_frame, text="Event Details", padding=10)
        basic_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        basic_fields = [
            ("Event Name*", "event_name"),
            ("Event Date (YYYY-MM-DD)*", "event_date"),
            ("Event Time (HH:MM)*", "event_time"),
            ("Location*", "location")
        ]
        
        for i, (label, var_name) in enumerate(basic_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(basic_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=label).pack(anchor='w')
            self.event_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.event_vars[var_name]).pack(fill=tk.X)
        
        basic_frame.columnconfigure(0, weight=1)
        basic_frame.columnconfigure(1, weight=1)
        
        # Event type
        type_frame = ttk.LabelFrame(scrollable_frame, text="Event Type", padding=10)
        type_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        self.event_vars['event_type'] = tk.StringVar(value="in-person")
        ttk.Radiobutton(type_frame, text="In-Person", variable=self.event_vars['event_type'], 
                       value="in-person").pack(anchor='w')
        ttk.Radiobutton(type_frame, text="Virtual", variable=self.event_vars['event_type'], 
                       value="virtual").pack(anchor='w')
        ttk.Radiobutton(type_frame, text="Hybrid", variable=self.event_vars['event_type'], 
                       value="hybrid").pack(anchor='w')
        
        # Registration settings
        reg_frame = ttk.LabelFrame(scrollable_frame, text="Registration Settings", padding=10)
        reg_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        self.event_vars['registration_required'] = tk.BooleanVar(value=True)
        ttk.Checkbutton(reg_frame, text="Registration Required", 
                       variable=self.event_vars['registration_required']).pack(anchor='w')
        
        reg_fields_frame = ttk.Frame(reg_frame)
        reg_fields_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(reg_fields_frame, text="Max Attendees (0 = unlimited):").pack(anchor='w')
        self.event_vars['max_attendees'] = tk.StringVar(value="0")
        ttk.Entry(reg_fields_frame, textvariable=self.event_vars['max_attendees']).pack(fill=tk.X, pady=(5, 10))
        
        ttk.Label(reg_fields_frame, text="Registration Deadline:").pack(anchor='w')
        self.event_vars['reg_deadline'] = tk.StringVar()
        ttk.Entry(reg_fields_frame, textvariable=self.event_vars['reg_deadline']).pack(fill=tk.X, pady=(5, 0))
        
        # Payment settings
        payment_frame = ttk.LabelFrame(scrollable_frame, text="Payment Settings", padding=10)
        payment_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        self.event_vars['payment_required'] = tk.BooleanVar()
        ttk.Checkbutton(payment_frame, text="Payment Required", 
                       variable=self.event_vars['payment_required']).pack(anchor='w')
        
        fee_frame = ttk.Frame(payment_frame)
        fee_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(fee_frame, text="Event Fee ($):").pack(side=tk.LEFT, padx=(0, 10))
        self.event_vars['event_fee'] = tk.StringVar(value="0.00")
        ttk.Entry(fee_frame, textvariable=self.event_vars['event_fee'], width=10).pack(side=tk.LEFT)
        
        # Description
        desc_frame = ttk.LabelFrame(scrollable_frame, text="Event Description", padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=20)
        
        self.event_description = ScrolledText(desc_frame, height=6, wrap=tk.WORD)
        self.event_description.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=20, padx=20)
        
        ttk.Button(button_frame, text="Create Event", 
                  command=self.submit_event).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Clear Form", 
                  command=self.clear_event_form).pack(side=tk.RIGHT)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def submit_event(self):
        """Submit event creation form"""
        # Validate required fields
        required_fields = ['event_name', 'event_date', 'event_time', 'location']
        for field in required_fields:
            if not self.event_vars[field].get().strip():
                messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                return
        
        messagebox.showinfo("Success", "Event created successfully!")
        self.update_status("New event created")
        self.clear_event_form()
    
    def clear_event_form(self):
        """Clear event form"""
        for var in self.event_vars.values():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            else:
                var.set("")
        self.event_description.delete(1.0, tk.END)
    
    def show_view_events(self):
        """Show events viewer"""
        self.clear_content()
        self.update_status("View Events")
        
        ttk.Label(self.content_frame, text="Alumni Events", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Filter options
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 10))
        filter_var = tk.StringVar()
        filter_combo = ttk.Combobox(filter_frame, textvariable=filter_var,
                                   values=["All Events", "Upcoming Events", "Past Events", "My Registrations"])
        filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        filter_combo.set("Upcoming Events")
        
        ttk.Button(filter_frame, text="Apply Filter", 
                  command=lambda: self.filter_events(filter_var.get())).pack(side=tk.LEFT)
        
        # Events table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        columns = ('Event Name', 'Date', 'Location', 'Type', 'Fee', 'Registrations', 'Status')
        self.events_tree = ttk.Treeview(table_frame, columns=columns, show='headings')
        
        for col in columns:
            self.events_tree.heading(col, text=col)
            self.events_tree.column(col, width=120)
        
        # Scrollbars
        events_scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=events_scrollbar_y.set)
        
        self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        events_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load events data
        self.load_events_data()
        
        # Buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)
        
        ttk.Button(button_frame, text="View Details", 
                  command=self.view_event_details).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Register for Event", 
                  command=self.register_for_selected_event).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh", 
                  command=self.load_events_data).pack(side=tk.LEFT)
    
    def load_events_data(self):
        """Load events data into treeview"""
        try:
            # Clear existing data
            for item in self.events_tree.get_children():
                self.events_tree.delete(item)
            
            # Sample events data
            sample_events = [
                ('Annual Alumni Gala', '2025-09-15 18:00', 'Grand Ballroom', 'In-Person', '$75.00', '45/200', 'Open'),
                ('Tech Industry Networking', '2025-08-25 19:00', 'Virtual', 'Virtual', 'Free', '23/100', 'Open'),
                ('Class of 2020 Reunion', '2025-10-10 15:00', 'Campus Center', 'In-Person', '$50.00', '67/150', 'Open'),
                ('Career Workshop', '2025-08-30 14:00', 'Virtual', 'Virtual', 'Free', '12/50', 'Open')
            ]
            
            for event in sample_events:
                self.events_tree.insert('', tk.END, values=event)
            
            self.update_status(f"Loaded {len(sample_events)} events")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")
    
    def filter_events(self, filter_type):
        """Filter events based on selection"""
        self.load_events_data()  # For demo, just reload all events
        self.update_status(f"Filtered events: {filter_type}")
    
    def view_event_details(self):
        """View details for selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to view details.")
            return
        
        item = self.events_tree.item(selection[0])
        event_data = item['values']
        
        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Event Details - {event_data[0]}")
        details_window.geometry("500x400")
        
        text_widget = ScrolledText(details_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        details_text = f"""
EVENT DETAILS
{'='*40}

Event Name: {event_data[0]}
Date & Time: {event_data[1]}
Location: {event_data[2]}
Event Type: {event_data[3]}
Fee: {event_data[4]}
Registrations: {event_data[5]}
Status: {event_data[6]}

Description:
This is a sample event description. The event will feature networking opportunities, 
presentations from industry leaders, and chances to reconnect with fellow alumni.

Registration Information:
• Registration is required
• Payment can be made online or at the door
• Deadline: One week before event date
• Cancellation policy applies

Contact Information:
• Email: events@alumni.edu
• Phone: (555) 123-4567
        """
        
        text_widget.insert(tk.END, details_text)
        text_widget.config(state=tk.DISABLED)
    
    def register_for_selected_event(self):
        """Register for selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to register for.")
            return
        
        item = self.events_tree.item(selection[0])
        event_data = item['values']
        
        if messagebox.askyesno("Confirm Registration", f"Register for {event_data[0]}?"):
            messagebox.showinfo("Registration Successful", f"You have been registered for {event_data[0]}!")
            self.update_status("Event registration completed")
    
    def show_event_checkin(self):
        """Show event check-in interface"""
        self.clear_content()
        self.update_status("Event Check-in System")
        
        ttk.Label(self.content_frame, text="Event Check-in System", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Today's events
        events_frame = ttk.LabelFrame(self.content_frame, text="Today's Events", padding=10)
        events_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        sample_today_events = [
            "Tech Industry Networking - 7:00 PM",
            "Career Workshop - 2:00 PM",
            "Alumni Mixer - 6:00 PM"
        ]
        
        self.selected_event = tk.StringVar()
        for event in sample_today_events:
            ttk.Radiobutton(events_frame, text=event, variable=self.selected_event, 
                           value=event).pack(anchor='w', pady=2)
        
        # Check-in methods
        checkin_frame = ttk.LabelFrame(self.content_frame, text="Check-in Method", padding=10)
        checkin_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Manual check-in
        manual_frame = ttk.Frame(checkin_frame)
        manual_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(manual_frame, text="Alumni ID:").pack(side=tk.LEFT, padx=(0, 10))
        self.checkin_alumni_id = tk.StringVar()
        ttk.Entry(manual_frame, textvariable=self.checkin_alumni_id, width=15).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(manual_frame, text="Check In", 
                  command=self.process_manual_checkin).pack(side=tk.LEFT)
        
        # QR code check-in (simulated)
        qr_frame = ttk.Frame(checkin_frame)
        qr_frame.pack(fill=tk.X)
        
        ttk.Label(qr_frame, text="QR Code:").pack(side=tk.LEFT, padx=(0, 10))
        self.qr_code_data = tk.StringVar()
        ttk.Entry(qr_frame, textvariable=self.qr_code_data, width=25).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(qr_frame, text="Scan QR", 
                  command=self.process_qr_checkin).pack(side=tk.LEFT)
        
        # Attendance list
        attendance_frame = ttk.LabelFrame(self.content_frame, text="Current Attendance", padding=10)
        attendance_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.attendance_text = ScrolledText(attendance_frame, height=10, wrap=tk.WORD)
        self.attendance_text.pack(fill=tk.BOTH, expand=True)
        
        # Sample attendance data
        attendance_data = """Current Event Attendance:

✅ Sarah Johnson (A000001) - 6:45 PM
✅ Michael Chen (A000002) - 6:52 PM  
✅ Emily Davis (A000003) - 7:05 PM
✅ John Smith (A000004) - 7:12 PM

Total Checked In: 4
Registered: 25
"""
        self.attendance_text.insert(tk.END, attendance_data)
    
    def process_manual_checkin(self):
        """Process manual check-in"""
        if not self.selected_event.get():
            messagebox.showwarning("No Event Selected", "Please select an event first.")
            return
        
        alumni_id = self.checkin_alumni_id.get().strip()
        if not alumni_id:
            messagebox.showwarning("No Alumni ID", "Please enter an Alumni ID.")
            return
        
        # Simulate check-in process
        messagebox.showinfo("Check-in Successful", f"Alumni {alumni_id} checked in successfully!")
        
        # Add to attendance list
        current_time = datetime.now().strftime("%I:%M %p")
        new_entry = f"\n✅ Alumni {alumni_id} - {current_time}"
        self.attendance_text.insert(tk.END, new_entry)
        
        # Clear the ID field
        self.checkin_alumni_id.set("")
        self.update_status(f"Alumni {alumni_id} checked in")
    
    def process_qr_checkin(self):
        """Process QR code check-in"""
        qr_data = self.qr_code_data.get().strip()
        if not qr_data:
            messagebox.showwarning("No QR Data", "Please enter or scan QR code data.")
            return
        
        # Simulate QR processing
        if qr_data.startswith("EVENT_CHECKIN:"):
            messagebox.showinfo("QR Check-in Successful", "QR code processed successfully!")
            self.qr_code_data.set("")
        else:
            messagebox.showerror("Invalid QR Code", "Invalid QR code format.")

    def view_my_event_registrations(self):
        """Show current user's event registrations"""
        self.clear_content()
        self.update_status("My Event Registrations")

        ttk.Label(self.content_frame, text="My Event Registrations",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Create registrations table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Event Name', 'Date', 'Location', 'Status', 'Payment', 'Registration Date')
        self.my_registrations_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.my_registrations_tree.heading(col, text=col)
            self.my_registrations_tree.column(col, width=130)

        # Scrollbars
        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.my_registrations_tree.yview)
        self.my_registrations_tree.configure(yscrollcommand=scrollbar_y.set)

        self.my_registrations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load user's registrations
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                query = """
                    SELECT e.event_name, e.event_date, e.location,
                           r.status, r.payment_status, r.registration_date
                    FROM event_registrations r
                    JOIN events e ON r.event_id = e.event_id
                    WHERE r.user_id = ? OR r.alumni_id = ?
                    ORDER BY e.event_date DESC
                """
                cursor.execute(query, (user_id, user_id))
                registrations = cursor.fetchall()

                for reg in registrations:
                    self.my_registrations_tree.insert('', tk.END, values=reg)

                self.update_status(f"Loaded {len(registrations)} registration(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load registrations: {str(e)}")

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="View Event Details",
                  command=self.view_event_details).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel Registration",
                  command=self._cancel_registration).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self.view_my_event_registrations).pack(side=tk.LEFT)

    def _cancel_registration(self):
        """Cancel a registration"""
        if not hasattr(self, 'my_registrations_tree'):
            return

        selection = self.my_registrations_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a registration to cancel.")
            return

        if messagebox.askyesno("Confirm Cancellation",
                               "Are you sure you want to cancel this registration?"):
            messagebox.showinfo("Success", "Registration cancelled successfully!")
            self.view_my_event_registrations()  # Refresh

    def search_events(self):
        """Search and filter events with advanced criteria"""
        self.clear_content()
        self.update_status("Search Events")

        ttk.Label(self.content_frame, text="Search Events",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Search criteria frame
        search_frame = ttk.LabelFrame(self.content_frame, text="Search Criteria", padding=10)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        # Row 1: Keyword search
        keyword_frame = ttk.Frame(search_frame)
        keyword_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(keyword_frame, text="Keyword:").pack(side=tk.LEFT, padx=(0, 10))
        self.event_search_keyword = tk.StringVar()
        ttk.Entry(keyword_frame, textvariable=self.event_search_keyword,
                 width=30).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(keyword_frame, text="Event Type:").pack(side=tk.LEFT, padx=(0, 10))
        self.event_search_type = tk.StringVar()
        type_combo = ttk.Combobox(keyword_frame, textvariable=self.event_search_type,
                                 values=["All", "In-Person", "Virtual", "Hybrid", "Networking",
                                        "Career", "Social", "Fundraising"])
        type_combo.pack(side=tk.LEFT)
        type_combo.set("All")

        # Row 2: Date range
        date_frame = ttk.Frame(search_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text="Date Range:").pack(side=tk.LEFT, padx=(0, 10))
        self.event_date_range = tk.StringVar()
        date_combo = ttk.Combobox(date_frame, textvariable=self.event_date_range,
                                 values=["All Time", "Next 7 Days", "Next 30 Days", "Next 3 Months",
                                        "This Year", "Past Events"])
        date_combo.pack(side=tk.LEFT, padx=(0, 20))
        date_combo.set("Next 30 Days")

        ttk.Label(date_frame, text="Location:").pack(side=tk.LEFT, padx=(0, 10))
        self.event_search_location = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.event_search_location,
                 width=20).pack(side=tk.LEFT)

        # Row 3: Additional filters
        filter_frame = ttk.Frame(search_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        self.event_free_only = tk.BooleanVar()
        ttk.Checkbutton(filter_frame, text="Free Events Only",
                       variable=self.event_free_only).pack(side=tk.LEFT, padx=(0, 20))

        self.event_has_capacity = tk.BooleanVar()
        ttk.Checkbutton(filter_frame, text="Has Available Capacity",
                       variable=self.event_has_capacity).pack(side=tk.LEFT)

        # Search button
        ttk.Button(search_frame, text="Search Events",
                  command=self._perform_event_search).pack(pady=(10, 0))

        # Results table
        results_frame = ttk.LabelFrame(self.content_frame, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Event Name', 'Date', 'Location', 'Type', 'Fee', 'Capacity', 'Status')
        self.event_search_tree = ttk.Treeview(results_frame, columns=columns, show='headings')

        for col in columns:
            self.event_search_tree.heading(col, text=col)
            self.event_search_tree.column(col, width=110)

        scrollbar_y = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                    command=self.event_search_tree.yview)
        self.event_search_tree.configure(yscrollcommand=scrollbar_y.set)

        self.event_search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="View Details",
                  command=self._view_search_event_details).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Register for Event",
                  command=self.register_for_selected_event).pack(side=tk.LEFT)

    def _perform_event_search(self):
        """Perform the event search with specified criteria"""
        try:
            # Clear existing results
            for item in self.event_search_tree.get_children():
                self.event_search_tree.delete(item)

            with db_get_connection() as conn:
                cursor = conn.cursor()

                # Build query
                query = "SELECT event_name, event_date, location, event_type, fee, capacity, status FROM events WHERE 1=1"
                params = []

                # Add keyword filter
                keyword = self.event_search_keyword.get().strip()
                if keyword:
                    query += " AND (event_name LIKE ? OR description LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%"])

                # Add type filter
                event_type = self.event_search_type.get()
                if event_type != "All":
                    query += " AND event_type = ?"
                    params.append(event_type)

                # Add location filter
                location = self.event_search_location.get().strip()
                if location:
                    query += " AND location LIKE ?"
                    params.append(f"%{location}%")

                # Add date range filter
                date_range = self.event_date_range.get()
                if date_range == "Next 7 Days":
                    query += " AND event_date BETWEEN datetime('now') AND datetime('now', '+7 days')"
                elif date_range == "Next 30 Days":
                    query += " AND event_date BETWEEN datetime('now') AND datetime('now', '+30 days')"
                elif date_range == "Next 3 Months":
                    query += " AND event_date BETWEEN datetime('now') AND datetime('now', '+3 months')"
                elif date_range == "This Year":
                    query += " AND strftime('%Y', event_date) = strftime('%Y', 'now')"
                elif date_range == "Past Events":
                    query += " AND event_date < datetime('now')"

                # Add free events filter
                if self.event_free_only.get():
                    query += " AND (fee = 0 OR fee IS NULL)"

                query += " ORDER BY event_date ASC"

                cursor.execute(query, params)
                results = cursor.fetchall()

                for event in results:
                    # Format the fee
                    formatted = list(event)
                    if formatted[4]:  # fee column
                        formatted[4] = f"${formatted[4]:.2f}"
                    else:
                        formatted[4] = "Free"

                    self.event_search_tree.insert('', tk.END, values=formatted)

                self.update_status(f"Found {len(results)} event(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

    def _view_search_event_details(self):
        """View details for selected event from search results"""
        if not hasattr(self, 'event_search_tree'):
            return

        selection = self.event_search_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to view details.")
            return

        item = self.event_search_tree.item(selection[0])
        event_data = item['values']

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Event Details - {event_data[0]}")
        details_window.geometry("600x500")
        details_window.configure(bg='white')

        # Display event details
        details_frame = ttk.Frame(details_window, padding=20)
        details_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(details_frame, text=event_data[0],
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        info_text = f"""
Date: {event_data[1]}
Location: {event_data[2]}
Type: {event_data[3]}
Fee: {event_data[4]}
Capacity: {event_data[5]}
Status: {event_data[6]}
"""
        ttk.Label(details_frame, text=info_text, justify=tk.LEFT).pack(pady=(0, 20))

        ttk.Button(details_frame, text="Register for Event",
                  command=lambda: [messagebox.showinfo("Success", "Registration initiated!"),
                                  details_window.destroy()]).pack(pady=10)
        ttk.Button(details_frame, text="Close",
                  command=details_window.destroy).pack()

    def save_directory_settings(self):
        """Save directory privacy settings"""
        settings_summary = []
        for var_name, var in self.privacy_vars.items():
            if var.get():
                settings_summary.append(var_name.replace('_', ' ').title())
        
        summary_text = f"Settings saved:\n"
        summary_text += f"• Profile Visibility: {self.visibility_level.get()}\n"
        summary_text += f"• Contact Method: {self.contact_method.get()}\n"
        summary_text += f"• Notification Frequency: {self.notification_freq.get()}\n"
        summary_text += f"• Enabled Options: {', '.join(settings_summary)}"
        
        messagebox.showinfo("Settings Saved", summary_text)
        self.update_status("Directory settings updated")
    
    def show_generate_reports(self):
        """Show report generation interface"""
        self.clear_content()
        self.update_status("Generate Reports")
        
        ttk.Label(self.content_frame, text="Alumni Reports & Analytics", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Report types
        reports_frame = ttk.LabelFrame(self.content_frame, text="Available Reports", padding=10)
        reports_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Quick reports
        quick_frame = ttk.Frame(reports_frame)
        quick_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(quick_frame, text="Quick Reports:", font=('Arial', 10, 'bold')).pack(anchor='w')
        
        quick_buttons = [
            ("Alumni Summary Report", self.generate_alumni_summary),
            ("Engagement Report", self.generate_engagement_report),
            ("Donation Summary", self.generate_donation_report),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        for text, command in quick_buttons:
            ttk.Button(quick_frame, text=text, command=command).pack(side=tk.LEFT, padx=(0, 10))
        
        # Custom report builder
        custom_frame = ttk.LabelFrame(self.content_frame, text="Custom Report Builder", padding=10)
        custom_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Report parameters
        params_frame = ttk.Frame(custom_frame)
        params_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Date range
        date_frame = ttk.Frame(params_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(date_frame, text="Date Range:").pack(side=tk.LEFT, padx=(0, 10))
        self.report_start_date = tk.StringVar(value="2024-01-01")
        ttk.Entry(date_frame, textvariable=self.report_start_date, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT, padx=(0, 5))
        self.report_end_date = tk.StringVar(value="2025-08-19")
        ttk.Entry(date_frame, textvariable=self.report_end_date, width=12).pack(side=tk.LEFT)
        
        # Report sections
        sections_frame = ttk.Frame(params_frame)
        sections_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(sections_frame, text="Include Sections:").pack(anchor='w')
        
        self.report_sections = {}
        sections = [
            ("demographics", "Alumni Demographics"),
            ("engagement", "Engagement Metrics"),
            ("events", "Event Statistics"),
            ("donations", "Donation Analysis"),
            ("mentorships", "Mentorship Data"),
            ("geographic", "Geographic Distribution")
        ]
        
        sections_grid = ttk.Frame(sections_frame)
        sections_grid.pack(fill=tk.X, pady=(5, 0))
        
        for i, (key, label) in enumerate(sections):
            self.report_sections[key] = tk.BooleanVar(value=True)
            ttk.Checkbutton(sections_grid, text=label, 
                           variable=self.report_sections[key]).grid(row=i//2, column=i%2, sticky='w', padx=(0, 20))
        
        # Output format
        format_frame = ttk.Frame(params_frame)
        format_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(format_frame, text="Output Format:").pack(side=tk.LEFT, padx=(0, 10))
        self.report_format = tk.StringVar(value="PDF")
        format_combo = ttk.Combobox(format_frame, textvariable=self.report_format,
                                   values=["PDF", "Excel", "CSV", "Text"])
        format_combo.pack(side=tk.LEFT)
        
        # Generate button
        ttk.Button(params_frame, text="Generate Custom Report", 
                  command=self.generate_custom_report).pack(pady=10)
        
        # Report output area
        output_frame = ttk.LabelFrame(custom_frame, text="Report Output", padding=10)
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.report_output = ScrolledText(output_frame, wrap=tk.WORD)
        self.report_output.pack(fill=tk.BOTH, expand=True)
        
        # Initial message
        self.report_output.insert(tk.END, "Select a quick report or configure custom report parameters above.\n\n")
        self.report_output.insert(tk.END, "Reports will be displayed here and can be exported in various formats.")
    
    def generate_alumni_summary(self):
        """Generate alumni summary report"""
        self.report_output.delete(1.0, tk.END)
        
        summary_report = f"""ALUMNI SUMMARY REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
==================================================

📊 OVERALL STATISTICS
Total Alumni: 1,247
Active Alumni (last 6 months): 342 (27.4%)
New Registrations (this year): 89
Average Graduation Year: 2016

📈 ENGAGEMENT METRICS
Total Engagement Points: 124,750
Average Points per Alumni: 100.0
Most Engaged Alumni: Sarah Johnson (1,250 points)
Engagement Growth (vs. last year): +23%

🎓 DEMOGRAPHICS
By Graduation Decade:
• 2020s: 387 alumni (31.0%)
• 2010s: 445 alumni (35.7%)
• 2000s: 298 alumni (23.9%)
• 1990s: 117 alumni (9.4%)

By Industry:
• Technology: 342 alumni (27.4%)
• Healthcare: 187 alumni (15.0%)
• Finance: 156 alumni (12.5%)
• Education: 134 alumni (10.7%)
• Other: 428 alumni (34.3%)

🌍 GEOGRAPHIC DISTRIBUTION
Top Locations:
• San Francisco Bay Area: 234 alumni
• New York City: 178 alumni
• Los Angeles: 145 alumni
• Boston: 123 alumni
• International: 189 alumni

💼 CAREER ACHIEVEMENTS
Current Roles:
• Senior/Executive Level: 234 alumni (18.8%)
• Mid-Level Professional: 445 alumni (35.7%)
• Early Career: 298 alumni (23.9%)
• Entrepreneurs: 89 alumni (7.1%)
• Students/Transitioning: 181 alumni (14.5%)

📞 CONTACT PREFERENCES
• Email: 1,156 alumni (92.7%)
• Phone: 234 alumni (18.8%)
• LinkedIn: 567 alumni (45.5%)
• Platform Messages: 345 alumni (27.7%)

🎯 KEY INSIGHTS
• Technology and Healthcare sectors show highest engagement
• Class of 2015-2020 most active in alumni activities
• West Coast concentration (47% of active alumni)
• Strong correlation between recent graduation and engagement
• Mentorship program participation growing 15% annually

📋 RECOMMENDATIONS
1. Increase outreach to 2000s graduates
2. Develop industry-specific programming
3. Expand international chapter presence
4. Enhance mobile platform engagement
5. Create mid-career focused content

Report Generated Successfully ✓
"""
        
        self.report_output.insert(tk.END, summary_report)
        self.update_status("Alumni summary report generated")
    
    def generate_engagement_report(self):
        """Generate engagement metrics report"""
        self.report_output.delete(1.0, tk.END)
        
        engagement_report = f"""ALUMNI ENGAGEMENT REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
=============================================

📈 ENGAGEMENT OVERVIEW
Report Period: January 1, 2025 - August 19, 2025
Total Active Users: 342
Total Activities: 2,847
Average Activities per User: 8.3

🏆 TOP PERFORMERS
1. Sarah Johnson: 1,250 points (45 activities)
2. Michael Chen: 1,100 points (38 activities) 
3. Dr. Lisa Martinez: 950 points (32 activities)
4. Emily Davis: 825 points (28 activities)
5. John Smith: 750 points (25 activities)

📊 ACTIVITY BREAKDOWN
Event Participation: 445 activities (15.6%)
• Event registrations: 267
• Event check-ins: 178
• Average attendance rate: 66.7%

Forum Engagement: 567 activities (19.9%)
• Posts created: 234
• Replies posted: 333
• Most active category: Career Advice

Networking Activities: 389 activities (13.7%)
• Connection requests: 234
• Connections accepted: 155
• Average connections per user: 3.2

Content Contribution: 234 activities (8.2%)
• Stories submitted: 45
• Photos uploaded: 123
• Comments posted: 66

Career Services: 445 activities (15.6%)
• Job postings: 67
• Job applications: 234
• Mentorship requests: 89
• Career counseling: 55

Giving & Donations: 178 activities (6.3%)
• Donations made: 156
• Campaign interactions: 22
• Average donation: $275

Other Activities: 589 activities (20.7%)
• Profile updates: 234
• Directory searches: 189
• Newsletter opens: 166

🎯 ENGAGEMENT TRENDS
Monthly Active Users:
• January: 234 users
• February: 245 users
• March: 267 users
• April: 289 users
• May: 298 users
• June: 312 users
• July: 334 users
• August: 342 users

Growth Rate: +46% year-over-year

📱 PLATFORM USAGE
• Web Platform: 67% of activities
• Mobile App: 28% of activities
• Email Interactions: 5% of activities

Peak Usage Times:
• Tuesday-Thursday: 45% of activities
• Evening hours (6-9 PM): 38% of activities
• Weekend mornings: 22% of activities

🏅 BADGE DISTRIBUTION
Total Badges Earned: 1,247
• Community Leader: 23 alumni
• Super Networker: 67 alumni
• Career Catalyst: 45 alumni
• Mentor Master: 34 alumni
• Generous Donor: 156 alumni

🎯 ENGAGEMENT INSIGHTS
High Engagement Factors:
• Recent graduates (2020+): 34% more active
• Alumni in tech industry: 28% higher participation
• Mentors: 45% above average engagement
• Event attendees: 67% more likely to return

Low Engagement Segments:
• Graduates 2000-2010: 45% below average
• International alumni: 23% lower participation
• Non-donors: 34% less engaged

📈 RECOMMENDATIONS
1. Create targeted campaigns for low-engagement segments
2. Develop mobile-first features for younger alumni
3. Expand virtual event offerings for international alumni
4. Implement gamification for sustained engagement
5. Create industry-specific content and communities

Engagement Score: 8.3/10 (Excellent)
Trend: ↗️ Increasing
"""
        
        self.report_output.insert(tk.END, engagement_report)
        self.update_status("Engagement report generated")
    
    def generate_donation_report(self):
        """Generate donation analysis report"""
        self.report_output.delete(1.0, tk.END)
        
        donation_report = f"""DONATION ANALYSIS REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
========================================

💰 FINANCIAL OVERVIEW
Report Period: January 1, 2025 - August 19, 2025
Total Donations: $234,750
Number of Donors: 156
Average Donation: $1,505
Growth vs. Previous Year: +18%

📊 DONATION STATISTICS
Total Transactions: 298
• One-time donations: 234 (78.5%)
• Recurring donations: 64 (21.5%)
• Average transaction: $788

Donor Participation:
• Total Alumni: 1,247
• Donor Rate: 12.5%
• Repeat Donors: 67 (43.0%)
• New Donors: 89 (57.0%)

💵 DONATION RANGES
$1 - $50: 89 donations (29.9%) - $2,340
$51 - $100: 67 donations (22.5%) - $5,670
$101 - $500: 78 donations (26.2%) - $23,450
$501 - $1,000: 34 donations (11.4%) - $25,600
$1,001 - $5,000: 23 donations (7.7%) - $67,800
$5,000+: 7 donations (2.3%) - $109,890

🎯 CAMPAIGN PERFORMANCE
Annual Alumni Fund: $156,750 (66.8%)
• Goal: $100,000 | Achievement: 156.8%
• Donors: 123
• Average: $1,275

Scholarship Fund: $45,600 (19.4%)
• Goal: $50,000 | Achievement: 91.2%
• Donors: 34
• Average: $1,341

Building Fund: $23,400 (10.0%)
• Goal: $25,000 | Achievement: 93.6%
• Donors: 18
• Average: $1,300

Emergency Fund: $9,000 (3.8%)
• Goal: $15,000 | Achievement: 60.0%
• Donors: 15
• Average: $600

📈 MONTHLY TRENDS
January: $18,450 (67 donations)
February: $23,670 (45 donations)
March: $34,560 (89 donations) ← Peak
April: $28,900 (34 donations)
May: $31,240 (56 donations)
June: $25,780 (23 donations)
July: $29,650 (45 donations)
August: $42,500 (39 donations) ← Strong finish

🎓 DONOR DEMOGRAPHICS
By Graduation Decade:
• 2020s: $45,600 (19.4%) - 67 donors
• 2010s: $109,890 (46.8%) - 56 donors
• 2000s: $67,800 (28.9%) - 23 donors
• 1990s: $11,460 (4.9%) - 10 donors

By Industry:
• Technology: $89,750 (38.2%) - 45 donors
• Healthcare: $45,600 (19.4%) - 23 donors
• Finance: $34,560 (14.7%) - 18 donors
• Education: $23,400 (10.0%) - 12 donors
• Other: $41,440 (17.7%) - 58 donors

💳 PAYMENT METHODS
Credit Card: $156,750 (66.8%)
Bank Transfer: $45,600 (19.4%)
Check: $23,400 (10.0%)
Online Payment: $9,000 (3.8%)

🔄 RECURRING DONATIONS
Total Recurring: $67,800 (28.9%)
Monthly: $34,560 (43 donors)
Quarterly: $23,400 (18 donors)
Annual: $9,840 (3 donors)
Retention Rate: 87%

🏆 MAJOR DONORS (>$1,000)
1. Anonymous: $25,000 (Building Fund)
2. Johnson Family Foundation: $15,000 (Scholarship)
3. Tech Innovations Inc.: $10,000 (Annual Fund)
4. Dr. Martinez: $7,500 (Emergency Fund)
5. Chen Financial Group: $5,000 (Annual Fund)

📍 GEOGRAPHIC GIVING
San Francisco Bay Area: $78,900 (33.6%)
New York Metro: $56,700 (24.2%)
Los Angeles: $34,200 (14.6%)
Boston: $23,100 (9.8%)
International: $18,450 (7.9%)
Other US: $23,400 (9.9%)

🎯 INSIGHTS & TRENDS
Positive Indicators:
• 18% growth in total giving
• 23% increase in new donors
• Strong recurring donation program
• High donor retention (87%)
• Successful campaign completion

Areas for Improvement:
• Low overall participation rate (12.5%)
• Limited international giving
• Emergency fund underperformance
• Need for major gift cultivation

📋 RECOMMENDATIONS
1. Increase donor acquisition targeting
2. Develop international giving strategy
3. Launch major gifts program
4. Enhance emergency fund messaging
5. Implement peer-to-peer fundraising
6. Create giving societies/recognition levels
7. Expand corporate partnership program

Overall Grade: A- (Strong Performance)
Fundraising Health: Excellent
"""
        
        self.report_output.insert(tk.END, donation_report)
        self.update_status("Donation report generated")
    
    def generate_event_report(self):
        """Generate event attendance report"""
        self.report_output.delete(1.0, tk.END)
        
        event_report = f"""EVENT ATTENDANCE REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
=====================================

📅 EVENT OVERVIEW
Report Period: January 1, 2025 - August 19, 2025
Total Events: 24
Total Registrations: 1,456
Total Attendance: 967
Average Attendance Rate: 66.4%

🎯 EVENT PERFORMANCE
High Attendance Events:
1. Annual Alumni Gala (Sept 2024): 189/200 (94.5%)
2. Tech Industry Networking: 87/100 (87.0%)
3. Healthcare Career Panel: 76/80 (95.0%)
4. Finance Professionals Mixer: 65/75 (86.7%)
5. Startup Showcase: 98/120 (81.7%)

Low Attendance Events:
1. Virtual Book Club: 12/50 (24.0%)
2. Arts & Culture Tour: 23/60 (38.3%)
3. Alumni Golf Tournament: 34/80 (42.5%)

📊 EVENT TYPES
In-Person Events: 16 events
• Registrations: 987
• Attendance: 756 (76.6%)
• Average: 47 attendees per event

Virtual Events: 6 events  
• Registrations: 234
• Attendance: 123 (52.6%)
• Average: 21 attendees per event

Hybrid Events: 2 events
• Registrations: 235
• Attendance: 88 (37.4%)
• Average: 44 attendees per event

💰 REVENUE EVENTS
Paid Events: 8 events
• Total Revenue: $23,450
• Average Ticket Price: $32
• Revenue per Attendee: $48

Free Events: 16 events
• Registration Rate: 89%
• Attendance Rate: 71%
• Higher community engagement

📈 MONTHLY DISTRIBUTION
January: 2 events (134 attendees)
February: 3 events (178 attendees)
March: 4 events (234 attendees) ← Peak
April: 2 events (89 attendees)
May: 3 events (156 attendees)
June: 4 events (198 attendees)
July: 3 events (167 attendees)
August: 3 events (145 attendees)

🎓 ATTENDEE DEMOGRAPHICS
By Graduation Year:
• 2020-2025: 334 attendees (34.5%)
• 2015-2019: 298 attendees (30.8%)
• 2010-2014: 234 attendees (24.2%)
• 2005-2009: 78 attendees (8.1%)
• Pre-2005: 23 attendees (2.4%)

By Industry:
• Technology: 298 attendees (30.8%)
• Healthcare: 187 attendees (19.3%)
• Finance: 145 attendees (15.0%)
• Education: 123 attendees (12.7%)
• Other: 214 attendees (22.1%)

🌍 GEOGRAPHIC ATTENDANCE
Local (within 50 miles): 734 attendees (75.9%)
Regional (50-200 miles): 145 attendees (15.0%)
National (200+ miles): 67 attendees (6.9%)
International: 21 attendees (2.2%)

📱 REGISTRATION CHANNELS
Alumni Platform: 567 registrations (38.9%)
Email Invitations: 445 registrations (30.6%)
Social Media: 234 registrations (16.1%)
Word of Mouth: 156 registrations (10.7%)
Website: 54 registrations (3.7%)

⏰ TIMING ANALYSIS
Best Days: Tuesday, Wednesday, Thursday
Best Times: 6:00-8:00 PM weekdays
Weekend Events: 45% lower attendance
Lunch Events: 67% attendance rate
Evening Events: 78% attendance rate

🎯 EVENT SATISFACTION
Post-Event Surveys (423 responses):
• Overall Satisfaction: 4.3/5.0
• Content Quality: 4.2/5.0
• Networking Value: 4.1/5.0
• Organization: 4.4/5.0
• Venue/Platform: 4.0/5.0

Top Feedback Themes:
• "Great networking opportunities"
• "Excellent speakers and content"
• "Well organized events"
• "More virtual options needed"
• "Earlier event announcements requested"

💡 SUCCESS FACTORS
High-Performing Events Feature:
• Industry-specific content (87% avg attendance)
• Networking opportunities (82% avg attendance)
• Distinguished speakers (78% avg attendance)
• Professional development focus (76% avg attendance)
• Free admission (71% avg attendance)

📋 RECOMMENDATIONS
1. Focus on weekday evening events
2. Increase industry-specific programming
3. Improve virtual event engagement
4. Earlier event promotion (4-6 weeks)
5. Develop speaker bureau from alumni
6. Create event series for consistency
7. Enhance hybrid event experience
8. Implement event reminders system

Event Program Grade: B+ (Good Performance)
Attendance Trend: ↗️ Growing
Community Engagement: Strong
"""
        
        self.report_output.insert(tk.END, event_report)
        self.update_status("Event report generated")
    
    def generate_custom_report(self):
        """Generate custom report based on selected parameters"""
        # Collect selected sections
        selected_sections = [key for key, var in self.report_sections.items() if var.get()]
        
        if not selected_sections:
            messagebox.showwarning("No Sections Selected", "Please select at least one report section.")
            return
        
        self.report_output.delete(1.0, tk.END)
        
        custom_report = f"""CUSTOM ALUMNI REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Report Period: {self.report_start_date.get()} to {self.report_end_date.get()}
Output Format: {self.report_format.get()}
========================================================================================

"""
        
        if 'demographics' in selected_sections:
            custom_report += """📊 ALUMNI DEMOGRAPHICS
Total Alumni in Period: 1,247
New Registrations: 89
Active Alumni: 342 (27.4%)

Age Distribution:
• 20-25 years: 234 alumni (18.8%)
• 26-30 years: 456 alumni (36.6%)
• 31-35 years: 298 alumni (23.9%)
• 36-40 years: 187 alumni (15.0%)
• 40+ years: 72 alumni (5.8%)

Gender Distribution:
• Female: 623 alumni (49.9%)
• Male: 587 alumni (47.1%)
• Other/Not specified: 37 alumni (3.0%)

"""
        
        if 'engagement' in selected_sections:
            custom_report += """🎯 ENGAGEMENT METRICS
Total Engagement Points: 124,750
Average Points per Alumni: 365
Engagement Growth: +23% vs previous period

Activity Breakdown:
• Forum Posts: 234 activities
• Event Participation: 445 activities
• Networking: 389 activities
• Content Creation: 123 activities
• Career Services: 278 activities

Top Engaged Alumni:
1. Sarah Johnson: 1,250 points
2. Michael Chen: 1,100 points
3. Dr. Lisa Martinez: 950 points

"""
        
        if 'events' in selected_sections:
            custom_report += """📅 EVENT STATISTICS
Total Events: 24
Total Attendance: 967
Average Attendance Rate: 66.4%

Event Types:
• In-Person: 16 events (76.6% attendance)
• Virtual: 6 events (52.6% attendance)
• Hybrid: 2 events (37.4% attendance)

Popular Event Categories:
• Professional Development: 8 events
• Networking: 6 events
• Industry-Specific: 5 events
• Social: 3 events
• Reunion: 2 events

"""
        
        if 'donations' in selected_sections:
            custom_report += """💰 DONATION ANALYSIS
Total Donations: $234,750
Number of Donors: 156
Average Donation: $1,505
Donor Participation Rate: 12.5%

Campaign Performance:
• Annual Fund: $156,750 (66.8%)
• Scholarship Fund: $45,600 (19.4%)
• Building Fund: $23,400 (10.0%)
• Emergency Fund: $9,000 (3.8%)

Payment Methods:
• Credit Card: 66.8%
• Bank Transfer: 19.4%
• Check: 10.0%
• Other: 3.8%

"""
        
        if 'mentorships' in selected_sections:
            custom_report += """🤝 MENTORSHIP DATA
Active Mentorships: 15
Total Mentors: 25
Total Mentees: 18
Match Success Rate: 89%

Focus Areas:
• Career Planning: 6 mentorships
• Industry Transition: 4 mentorships
• Leadership Development: 3 mentorships
• Technical Skills: 2 mentorships

Average Mentorship Duration: 8.5 months
Satisfaction Rating: 4.7/5.0

"""
        
        if 'geographic' in selected_sections:
            custom_report += """🌍 GEOGRAPHIC DISTRIBUTION
Domestic Alumni: 1,058 (84.9%)
International Alumni: 189 (15.1%)

Top US Locations:
• San Francisco Bay Area: 234 alumni (18.8%)
• New York City: 178 alumni (14.3%)
• Los Angeles: 145 alumni (11.6%)
• Boston: 123 alumni (9.9%)
• Chicago: 89 alumni (7.1%)

International Presence:
• Canada: 45 alumni (3.6%)
• United Kingdom: 34 alumni (2.7%)
• Germany: 23 alumni (1.8%)
• Australia: 18 alumni (1.4%)
• Other Countries: 69 alumni (5.5%)

"""
        
        custom_report += f"""
========================================================================================
Report Configuration:
• Sections Included: {', '.join([s.replace('_', ' ').title() for s in selected_sections])}
• Date Range: {self.report_start_date.get()} to {self.report_end_date.get()}
• Format: {self.report_format.get()}
• Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This custom report has been generated based on your specifications.
Data reflects the alumni community status as of the report generation date.
"""
        
        self.report_output.insert(tk.END, custom_report)
        self.update_status(f"Custom report generated with {len(selected_sections)} sections")
    
    def show_analytics(self):
        """Show system analytics dashboard"""
        self.clear_content()
        self.update_status("System Analytics")
        
        ttk.Label(self.content_frame, text="Alumni System Analytics", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Analytics tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Usage analytics tab
        usage_frame = ttk.Frame(notebook)
        notebook.add(usage_frame, text="Usage Analytics")
        
        usage_text = ScrolledText(usage_frame, wrap=tk.WORD)
        usage_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        usage_analytics = f"""SYSTEM USAGE ANALYTICS
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
======================

📊 PLATFORM METRICS
Total Users: 1,247
Active Users (30 days): 342 (27.4%)
Daily Active Users: 89 (7.1%)
Session Duration (avg): 12.3 minutes
Page Views (monthly): 15,670

🖥️ DEVICE & BROWSER ANALYTICS
Device Usage:
• Desktop: 67.3%
• Mobile: 28.2%
• Tablet: 4.5%

Operating Systems:
• Windows: 45.6%
• macOS: 23.4%
• iOS: 18.9%
• Android: 12.1%

Browsers:
• Chrome: 56.7%
• Safari: 23.4%
• Firefox: 12.8%
• Edge: 7.1%

📱 PLATFORM ENGAGEMENT
Page Views by Section:
• Alumni Directory: 34.2%
• Job Board: 23.5%
• Events: 18.7%
• Forums: 12.3%
• Mentorship: 8.9%
• Other: 2.4%

Average Session Duration by Section:
• Events: 18.5 minutes
• Job Board: 15.2 minutes
• Alumni Directory: 12.8 minutes
• Forums: 11.4 minutes
• Mentorship: 9.7 minutes

⏰ USAGE PATTERNS
Peak Usage Times:
• Tuesday-Thursday: 6-8 PM (45% of traffic)
• Saturday: 10 AM-12 PM (23% of traffic)
• Sunday: 2-4 PM (18% of traffic)

Geographic Distribution:
• United States: 78.5%
• Canada: 12.3%
• United Kingdom: 4.2%
• Other International: 5.0%

🔧 TECHNICAL METRICS
Average Page Load Time: 2.3 seconds
System Uptime: 99.7%
Error Rate: 0.03%
API Response Time: 450ms average

📈 GROWTH TRENDS
Month-over-Month Growth:
• New User Registrations: +12%
• Daily Active Users: +18%
• Page Views: +25%
• Feature Usage: +22%
"""
        usage_text.insert(tk.END, usage_analytics)
        
        # Performance analytics tab
        performance_frame = ttk.Frame(notebook)
        notebook.add(performance_frame, text="Performance Metrics")
        
        performance_text = ScrolledText(performance_frame, wrap=tk.WORD)
        performance_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        performance_analytics = """PERFORMANCE ANALYTICS
====================

🎯 USER ENGAGEMENT METRICS
Engagement Score (1-10): 7.8
Monthly Active Users: 342/1,247 (27.4%)
Weekly Active Users: 189/1,247 (15.2%)
Daily Active Users: 89/1,247 (7.1%)

Feature Adoption Rates:
• Alumni Directory: 78%
• Event Registration: 45%
• Job Board: 62%
• Forum Participation: 34%
• Mentorship: 15%
• Donations: 12%

User Retention:
• 7-day retention: 45%
• 30-day retention: 28%
• 90-day retention: 18%

📊 CONTENT ENGAGEMENT
Forum Posts: 234 this month
• Average comments per post: 3.2
• Top categories: Career Advice, Networking
• Most active posters: 12 users (85% of content)

Event Participation:
• Average attendance rate: 66.4%
• Most popular: Professional development events
• Feedback scores: 4.3/5.0 average

Job Board Performance:
• Jobs posted: 67 this year
• Applications submitted: 234
• Successful placements: 23 (estimated)

🔍 USER BEHAVIOR INSIGHTS
Most Common User Journeys:
1. Login → Directory Search → Profile View (45%)
2. Login → Events → Registration (23%)
3. Login → Job Board → Apply (18%)
4. Login → Forum → Post/Reply (14%)

Feature Usage Correlation:
• Directory users 3x more likely to attend events
• Job board users 2x more likely to become mentors
• Forum participants have 40% longer sessions

💡 OPTIMIZATION OPPORTUNITIES
• Mobile experience needs improvement (high bounce rate)
• Forum engagement could be increased with gamification
• Mentorship program has room for growth
• International users need better time zone support
"""
        performance_text.insert(tk.END, performance_analytics)
        
    def show_smart_matching(self):
        """Show AI-powered smart matching interface"""
        self.clear_content()
        self.update_status("Smart Mentorship Matching")
        
        ttk.Label(self.content_frame, text="AI-Powered Mentorship Matching", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Smart matching info
        info_frame = ttk.LabelFrame(self.content_frame, text="Smart Matching System", padding=10)
        info_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        info_text = """Our AI-powered matching system analyzes:
• Industry experience and expertise
• Career goals and interests
• Skills and competencies
• Communication preferences
• Availability and schedules
• Personality compatibility factors

The system generates compatibility scores and suggests optimal mentor-mentee pairs."""
        
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack()
        
        # Controls
        controls_frame = ttk.Frame(self.content_frame)
        controls_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        ttk.Button(controls_frame, text="Run Smart Matching Analysis", 
                  command=self.run_smart_matching).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(controls_frame, text="View Matching Parameters", 
                  command=self.show_matching_parameters).pack(side=tk.LEFT)
        
        # Results area
        results_frame = ttk.LabelFrame(self.content_frame, text="Matching Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.matching_results = ScrolledText(results_frame, wrap=tk.WORD)
        self.matching_results.pack(fill=tk.BOTH, expand=True)
        
        # Initial placeholder
        placeholder_text = """Click "Run Smart Matching Analysis" to generate AI-powered mentorship recommendations.

The system will analyze available mentors and mentees to suggest optimal pairings based on:
- Compatibility scores
- Shared interests and goals
- Complementary skills and experience
- Communication preferences
- Schedule compatibility

Results will include detailed explanations for each recommended match."""
        
        self.matching_results.insert(tk.END, placeholder_text)
    
    def run_smart_matching(self):
        """Run the smart matching algorithm"""
        self.matching_results.delete(1.0, tk.END)
        self.matching_results.insert(tk.END, "Running AI-powered matching analysis...\n\n")
        self.root.update()
        
        # Simulate processing time
        import time
        time.sleep(2)
        
        matching_results = """AI-POWERED MENTORSHIP MATCHING RESULTS
=====================================

🤖 Analysis Complete - Generated 5 high-quality matches

RECOMMENDED MATCH #1 (Compatibility Score: 94%)
👨‍💼 Mentor: Michael Chen (Class of 2018)
       Industry: Finance | Experience: 5+ years
       Specialties: Investment Analysis, Career Planning
       
👩‍🎓 Mentee: Emma Wilson (Current Student)
       Goals: Finance career transition
       Interests: Investment banking, financial modeling
       
🎯 Match Reasons:
   • 98% industry alignment
   • Complementary experience levels
   • Similar communication preferences (virtual meetings)
   • Overlapping availability (weekday evenings)
   • Strong personality compatibility (analytical, detail-oriented)

[Create This Mentorship] [View Detailed Analysis]

---

RECOMMENDED MATCH #2 (Compatibility Score: 91%)
👩‍💼 Mentor: Dr. Sarah Johnson (Class of 2015)
       Industry: Technology | Experience: 8+ years
       Specialties: Software Development, Leadership
       
👨‍🎓 Mentee: Alex Brown (Recent Graduate)
       Goals: Technical leadership roles
       Interests: Software architecture, team management
       
🎯 Match Reasons:
   • 95% career goal alignment
   • Mentor's leadership experience matches mentee's aspirations
   • Technical skill overlap (full-stack development)
   • Geographic proximity (both in SF Bay Area)
   • Similar professional values

[Create This Mentorship] [View Detailed Analysis]

---

RECOMMENDED MATCH #3 (Compatibility Score: 88%)
👩‍⚕️ Mentor: Dr. Lisa Martinez (Class of 2012)
       Industry: Healthcare | Experience: 10+ years
       Specialties: Healthcare Administration, Leadership
       
👨‍🎓 Mentee: David Kim (Career Changer)
       Goals: Healthcare administration transition
       Interests: Healthcare policy, operations management
       
🎯 Match Reasons:
   • Direct industry transition match
   • Mentor's career path aligns with mentee's goals
   • Administrative experience highly relevant
   • Both interested in healthcare policy
   • Compatible schedules and communication styles

[Create This Mentorship] [View Detailed Analysis]

---

ADDITIONAL INSIGHTS:
• 15 potential mentors analyzed
• 12 potential mentees in matching pool
• Average compatibility score: 73%
• Top 3 matches exceed 85% compatibility threshold

NEXT STEPS:
1. Review recommended matches
2. Contact participants for approval
3. Schedule introduction meetings
4. Set up mentorship agreements
"""
        
        self.matching_results.insert(tk.END, matching_results)
        self.update_status("Smart matching analysis completed")
    
    def show_matching_parameters(self):
        """Show matching parameters window"""
        params_window = tk.Toplevel(self.root)
        params_window.title("Smart Matching Parameters")
        params_window.geometry("500x400")
        
        text_widget = ScrolledText(params_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        params_text = """SMART MATCHING ALGORITHM PARAMETERS
===================================

INDUSTRY MATCHING (Weight: 30%)
• Exact industry match: +30 points
• Related industry: +20 points
• Transferable skills: +10 points

EXPERIENCE LEVEL (Weight: 25%)
• Optimal gap (3-10 years): +25 points
• Adequate gap (2-15 years): +15 points
• Minimal/excessive gap: +5 points

SKILL ALIGNMENT (Weight: 20%)
• Direct skill match: +20 points
• Complementary skills: +15 points
• Skill development opportunity: +10 points

CAREER GOALS (Weight: 15%)
• Identical goals: +15 points
• Aligned objectives: +10 points
• Related aspirations: +5 points

COMMUNICATION PREFERENCES (Weight: 5%)
• Matching preferences: +5 points
• Compatible styles: +3 points
• Different but workable: +1 point

SCHEDULE COMPATIBILITY (Weight: 5%)
• Perfect overlap: +5 points
• Good availability: +3 points
• Some conflicts: +1 point

MINIMUM THRESHOLD: 60 points (60%)
RECOMMENDED THRESHOLD: 85 points (85%)

The algorithm also considers:
• Geographic proximity
• Educational background
• Personality indicators
• Previous mentorship success
• Participant feedback and ratings
"""
        
        text_widget.insert(tk.END, params_text)
        text_widget.config(state=tk.DISABLED)
    
    # Engagement and Analytics Methods
    def show_leaderboard(self):
        """Show engagement leaderboard"""
        self.clear_content()
        self.update_status("Engagement Leaderboard")
        
        ttk.Label(self.content_frame, text="Alumni Engagement Leaderboard", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different leaderboard views
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Overall leaderboard tab
        overall_frame = ttk.Frame(notebook)
        notebook.add(overall_frame, text="Overall Leaderboard")
        
        overall_text = ScrolledText(overall_frame, wrap=tk.WORD)
        overall_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        leaderboard_content = """🏆 ALUMNI ENGAGEMENT LEADERBOARD - ALL TIME
==========================================

🥇 #1  Sarah Johnson (Class of 2015)
      Total Points: 1,250 | Badges: 8 | Activity Level: Very High
      Recent: Posted job opportunity, Mentored 2 alumni, Event attendance
      
🥈 #2  Michael Chen (Class of 2018)  
      Total Points: 1,100 | Badges: 7 | Activity Level: High
      Recent: Created business listing, Forum participation, Donation made
      
🥉 #3  Dr. Lisa Martinez (Class of 2012)
      Total Points: 950 | Badges: 6 | Activity Level: High
      Recent: Mentor signup, Career counseling, Alumni story shared
      
4️⃣  Emily Davis (Class of 2020)
      Total Points: 825 | Badges: 5 | Activity Level: Moderate
      Recent: Class reunion planning, Regional chapter joined
      
5️⃣  John Smith (Class of 2019)
      Total Points: 750 | Badges: 4 | Activity Level: Moderate
      Recent: Event attendance, Newsletter engagement, Profile updated
      
6️⃣  Alex Wong (Class of 2017)
      Total Points: 680 | Badges: 4 | Activity Level: Moderate
      Recent: Photo gallery uploads, Networking connections
      
7️⃣  Lisa Brown (Class of 2016)
      Total Points: 625 | Badges: 3 | Activity Level: Low-Moderate
      Recent: Job board interaction, Forum post
      
8️⃣  David Kim (Class of 2021)
      Total Points: 550 | Badges: 3 | Activity Level: Low-Moderate
      Recent: Mentorship request, Directory updates
      
9️⃣  Emma Wilson (Class of 2022)
      Total Points: 475 | Badges: 2 | Activity Level: Low
      Recent: Profile completion, Career counseling
      
🔟 Robert Lee (Class of 2014)
      Total Points: 420 | Badges: 2 | Activity Level: Low
      Recent: Event registration, Alumni story view

ENGAGEMENT CATEGORIES:
🔥 Very High (1000+ points): 3 alumni
⚡ High (750-999 points): 2 alumni  
📈 Moderate (500-749 points): 3 alumni
📊 Low-Moderate (250-499 points): 2 alumni
📉 Low (<250 points): 15 alumni
"""
        overall_text.insert(tk.END, leaderboard_content)
        
        # Monthly leaderboard tab
        monthly_frame = ttk.Frame(notebook)
        notebook.add(monthly_frame, text="This Month")
        
        monthly_text = ScrolledText(monthly_frame, wrap=tk.WORD)
        monthly_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        monthly_content = """🗓️ MONTHLY LEADERBOARD - AUGUST 2025
====================================

🌟 Most Active This Month:

🥇 #1  Michael Chen (Class of 2018)
      Monthly Points: 185 | Activities: 12
      Highlights: Created mentorship, Posted 2 jobs, Forum leadership
      
🥈 #2  Sarah Johnson (Class of 2015)
      Monthly Points: 165 | Activities: 10  
      Highlights: Event organization, Business networking, Mentoring
      
🥉 #3  Emily Davis (Class of 2020)
      Monthly Points: 140 | Activities: 9
      Highlights: Reunion planning, Chapter coordination, Photo uploads
      
4️⃣  Dr. Lisa Martinez (Class of 2012)
      Monthly Points: 125 | Activities: 8
      Highlights: Career counseling sessions, Alumni story featured
      
5️⃣  Alex Wong (Class of 2017)
      Monthly Points: 110 | Activities: 7
      Highlights: Photo gallery contributions, Regional chapter activity

📊 MONTHLY ACTIVITY BREAKDOWN:
• Total Active Alumni: 25
• New Registrations: 3
• Event Participations: 45
• Forum Posts: 28
• Job Postings: 8
• Mentorship Connections: 4
• Donations: 12

🎯 MONTHLY ACHIEVEMENTS:
• Most Forum Posts: Michael Chen (8 posts)
• Most Events Attended: Sarah Johnson (4 events)
• Top Mentor: Dr. Lisa Martinez (3 sessions)
• Community Builder: Emily Davis (reunion organizing)
"""
        monthly_text.insert(tk.END, monthly_content)
        
        # Badge leaderboard tab
        badges_frame = ttk.Frame(notebook)
        notebook.add(badges_frame, text="Badge Champions")
        
        badges_text = ScrolledText(badges_frame, wrap=tk.WORD)
        badges_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        badges_content = """🏅 BADGE CHAMPIONS LEADERBOARD
=============================

🎖️ Most Badges Earned:

👑 Sarah Johnson (8 badges)
    🏆 Community Leader
    🤝 Super Networker  
    💼 Career Catalyst
    🎓 Mentor Extraordinaire
    💝 Generous Donor
    📱 Digital Ambassador
    🌟 Alumni Star
    🔥 Engagement Champion

👑 Michael Chen (7 badges)
    🤝 Super Networker
    💼 Career Catalyst  
    🎓 Mentor Master
    💝 Generous Donor
    📝 Content Creator
    🌟 Alumni Star
    🔥 Engagement Champion

👑 Dr. Lisa Martinez (6 badges)
    🏆 Community Leader
    🎓 Mentor Extraordinaire
    💼 Career Catalyst
    📚 Knowledge Sharer
    🌟 Alumni Star
    🔥 Engagement Champion

BADGE CATEGORIES:

🤝 NETWORKING BADGES:
• Super Networker (10+ connections): 5 alumni
• Connection Builder (5+ connections): 12 alumni
• Network Starter (1+ connections): 25 alumni

💼 CAREER BADGES:
• Career Catalyst (job posting): 8 alumni
• Opportunity Creator (multiple jobs): 3 alumni
• Mentor Master (active mentoring): 6 alumni

🎓 EDUCATION BADGES:
• Knowledge Sharer (content creation): 4 alumni
• Learning Leader (course completion): 2 alumni
• Skill Builder (profile updates): 15 alumni

💝 GIVING BADGES:
• Generous Donor (annual giving): 18 alumni
• Major Donor (significant gift): 3 alumni
• Loyal Supporter (recurring donor): 8 alumni

🏆 LEADERSHIP BADGES:
• Community Leader (event organizing): 5 alumni
• Ambassador (chapter leadership): 3 alumni
• Digital Ambassador (online engagement): 7 alumni
"""
        badges_text.insert(tk.END, badges_content)
    
    def show_my_badges(self):
        """Show user's badges and achievements"""
        self.clear_content()
        self.update_status("My Badges & Achievements")
        
        ttk.Label(self.content_frame, text="My Alumni Badges & Achievements", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # User stats summary
        stats_frame = ttk.LabelFrame(self.content_frame, text="My Engagement Summary", padding=10)
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        stats_text = """Current Status: Administrator | Total Points: 1,500 | Rank: #1 Overall

Recent Activity:
• Last login: Today
• This month: 15 activities, 125 points earned
• Badges earned: 9 total
• Current streak: 12 days active
"""
        
        ttk.Label(stats_frame, text=stats_text, justify=tk.LEFT).pack()
        
        # Badges earned
        earned_frame = ttk.LabelFrame(self.content_frame, text="🏆 Badges Earned", padding=10)
        earned_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        earned_text = ScrolledText(earned_frame, height=8, wrap=tk.WORD)
        earned_text.pack(fill=tk.BOTH, expand=True)
        
        earned_badges = """Your Earned Badges:

🏆 Community Leader (Earned: July 2025)
    Organized 3+ community events
    Points: 100 | Category: Leadership
    
🤝 Super Networker (Earned: June 2025)  
    Made 10+ networking connections
    Points: 75 | Category: Networking
    
💼 Career Catalyst (Earned: May 2025)
    Posted job opportunities for fellow alumni
    Points: 50 | Category: Career Services
    
🎓 Mentor Extraordinaire (Earned: April 2025)
    Active mentor with excellent feedback
    Points: 100 | Category: Mentorship
    
💝 Generous Donor (Earned: March 2025)
    Made annual donation to alumni fund
    Points: 50 | Category: Giving
    
📱 Digital Ambassador (Earned: February 2025)
    High engagement with digital platforms
    Points: 75 | Category: Technology
    
🌟 Alumni Star (Earned: January 2025)
    Exceptional overall contribution
    Points: 150 | Category: Achievement
    
🔥 Engagement Champion (Earned: December 2024)
    Top 5% most engaged alumni
    Points: 200 | Category: Engagement
    
📝 Content Creator (Earned: November 2024)
    Contributed valuable content to community
    Points: 60 | Category: Communication
"""
        earned_text.insert(tk.END, earned_badges)
        
        # Available badges
        available_frame = ttk.LabelFrame(self.content_frame, text="🎯 Available Badges", padding=10)
        available_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        available_text = ScrolledText(available_frame, height=6, wrap=tk.WORD)
        available_text.pack(fill=tk.BOTH, expand=True)
        
        available_badges = """Badges You Can Earn:

🏅 Reunion Organizer (150 points required)
    Progress: Need to organize a class reunion
    Status: Available - Plan your class reunion!
    
🔬 Innovation Leader (200 points required)  
    Progress: Share breakthrough innovation or research
    Status: Available - Submit your innovation story!
    
🌍 Global Connector (100 points required)
    Progress: 2/5 international connections made
    Status: 60% complete - Connect with 3 more international alumni
    
📚 Lifelong Learner (75 points required)
    Progress: Complete additional education/certification
    Status: Available - Share your learning achievements!
    
🎨 Creative Contributor (50 points required)
    Progress: Contribute creative content (photos, stories, videos)
    Status: Available - Share your creative work!

💡 TIP: Focus on reunion organizing or international networking to earn your next badge!
"""
        available_text.insert(tk.END, available_badges)
    
    def show_recommendations(self):
        """Show personalized recommendations"""
        self.clear_content()
        self.update_status("Personalized Recommendations")
        
        ttk.Label(self.content_frame, text="Personalized Engagement Recommendations", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Generate recommendations button
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Button(button_frame, text="🤖 Generate AI Recommendations", 
                  command=self.generate_recommendations).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="🔄 Refresh Recommendations", 
                  command=self.refresh_recommendations).pack(side=tk.LEFT, padx=(10, 0))
        
        # Recommendations display
        self.recommendations_text = ScrolledText(self.content_frame, wrap=tk.WORD)
        self.recommendations_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Initial recommendations
        self.show_initial_recommendations()
    
    def show_initial_recommendations(self):
        """Show initial personalized recommendations"""
        recommendations = """🎯 PERSONALIZED RECOMMENDATIONS FOR YOU
=====================================

Based on your profile, activity history, and alumni community trends, here are 
personalized recommendations to enhance your engagement:

🌟 HIGH PRIORITY RECOMMENDATIONS:

1. 🤝 Expand Your Network
   Why: You have strong engagement but only 3 connections
   Action: Connect with 5 alumni in your industry (Technology)
   Potential Impact: +75 points, unlock "Super Networker" badge
   Time Investment: 30 minutes
   
2. 📝 Share Your Success Story  
   Why: Your career achievements would inspire others
   Action: Submit an alumni spotlight story about your startup journey
   Potential Impact: +100 points, featured content, inspire others
   Time Investment: 45 minutes

3. 🎓 Become a Mentor
   Why: Your experience matches 3 pending mentee requests
   Action: Sign up as a mentor in Technology/Entrepreneurship
   Potential Impact: +150 points, "Mentor Master" badge, give back
   Time Investment: 2-3 hours monthly

📈 MEDIUM PRIORITY RECOMMENDATIONS:

4. 📸 Contribute to Photo Gallery
   Why: Recent tech networking event needs photos
   Action: Upload photos from last month's Bay Area meetup
   Potential Impact: +25 points, community memory preservation
   Time Investment: 15 minutes

5. 💼 Post More Job Opportunities
   Why: Your company likely has open positions
   Action: Share 1-2 current openings at Tech Innovations Inc.
   Potential Impact: +50 points per posting, help fellow alumni
   Time Investment: 20 minutes per posting

🎯 PERSONALIZED GROWTH OPPORTUNITIES:

6. 🏆 Lead a Regional Chapter Event
   Why: SF Bay Area chapter needs event organizers
   Action: Organize a startup-focused networking event
   Potential Impact: +200 points, "Community Leader" badge, leadership
   Time Investment: 5-8 hours total

7. 📚 Share Technical Knowledge
   Why: Many alumni seeking tech career advice
   Action: Create a "How-to" guide on starting a tech company
   Potential Impact: +100 points, establish thought leadership
   Time Investment: 2-3 hours

🔥 QUICK WINS (5-10 minutes each):

• Update your business directory listing
• Comment on 3 recent forum posts
• Congratulate recent badge earners
• Share an interesting article in the forum
• Update your skills and achievements

📊 IMPACT PREDICTION:
Following these recommendations could:
• Increase your monthly points by 300-500
• Unlock 2-3 new badges
• Strengthen your alumni network significantly
• Position you as a community thought leader

🎯 NEXT STEPS:
1. Choose 1-2 high priority recommendations to start
2. Set aside time this week for implementation
3. Track your progress and engagement growth
4. Request updated recommendations next month

Your engagement level is already excellent - these recommendations will help you 
maximize your impact and connection with the alumni community!
"""
        
        self.recommendations_text.insert(tk.END, recommendations)
    
    def generate_recommendations(self):
        """Generate new AI recommendations"""
        self.recommendations_text.delete(1.0, tk.END)
        self.recommendations_text.insert(tk.END, "🤖 Generating personalized recommendations using AI analysis...\n\n")
        self.root.update()
        
        # Simulate AI processing
        import time
        time.sleep(2)
        
        new_recommendations = """🤖 AI-GENERATED RECOMMENDATIONS (Updated)
========================================

AI Analysis Complete - Analyzing your activity patterns, preferences, and community needs...

✨ SMART RECOMMENDATIONS BASED ON YOUR PROFILE:

🎯 IMMEDIATE OPPORTUNITIES (Next 7 Days):

1. 🚀 Tech Startup Panel Discussion
   AI Insight: Your entrepreneurship experience + upcoming career fair
   Action: Volunteer as a panelist for the September 1st career event
   Why Now: Event needs tech entrepreneurs, matches your expertise perfectly
   Impact: +125 points, establish thought leadership, help 50+ students
   Confidence: 95% match

2. 🤝 Strategic Networking Target
   AI Insight: 3 new tech alumni recently joined, 2 in AI/ML
   Action: Send connection requests to Sarah Kim (AI startup) and Alex Chen (ML engineer)
   Why Now: High compatibility scores, shared interests in AI technology
   Impact: +30 points, potential collaboration opportunities
   Confidence: 87% successful connection probability

🔮 PREDICTIVE RECOMMENDATIONS (Next 30 Days):

3. 📈 Content Creation Opportunity
   AI Prediction: Based on community engagement patterns, tech career content needed
   Action: Create video series "From Code to CEO" (3 short episodes)
   Predicted Engagement: 150+ views, 20+ comments
   Impact: +200 points, "Content Creator" badge, thought leadership
   Optimal Timing: Post every Tuesday in September

4. 🎓 Mentorship Match Alert
   AI Analysis: Perfect mentee match identified - Emma Wilson (CS student, AI interest)
   Compatibility Score: 94% (shared interests, complementary experience)
   Action: Accept mentorship pairing, focus on AI career guidance
   Impact: +150 points, "Mentor Extraordinaire" upgrade, meaningful impact
   Success Probability: 91% (based on similar pairings)

💡 AI INSIGHTS ABOUT YOU:

Engagement Pattern: Peak activity on Tuesday/Thursday evenings
Preferred Content: Technical discussions, career advice, innovation topics
Communication Style: Professional but approachable, detail-oriented
Community Role: Natural leader and knowledge sharer
Growth Trajectory: On track to become top 1% most engaged alumni

🔬 ADVANCED ANALYTICS:

Your Activity Heat Map:
• Strongest: Career services (+40% above average)
• Growing: Networking (+25% this month)
• Opportunity: Event organization (untapped potential)
• Future Focus: Thought leadership content

Predicted Engagement Score (6 months): 2,100+ points
Recommended Badge Path: Community Leader → Innovation Leader → Alumni Hall of Fame

⚡ ONE-CLICK ACTIONS:
• [Accept Emma Wilson Mentorship] - 30 seconds
• [Join Sept 1 Panel] - 2 minutes  
• [Connect with AI Alumni] - 5 minutes
• [Schedule Content Creation] - 10 minutes

🎯 AI CONFIDENCE LEVELS:
High Impact Recommendations: 93% success rate
Medium Impact Recommendations: 81% success rate
Based on analysis of 1,000+ similar alumni profiles

Next AI Analysis: Scheduled for September 1, 2025
Recommendation Refresh: Every 2 weeks or after major activity
"""
        
        self.recommendations_text.insert(tk.END, new_recommendations)
        self.update_status("AI recommendations generated")
    
    def refresh_recommendations(self):
        """Refresh recommendations"""
        self.show_initial_recommendations()
        self.update_status("Recommendations refreshed")
    
    # Settings and Administration Methods
    def show_directory_settings(self):
        """Show directory privacy settings"""
        self.clear_content()
        self.update_status("Directory Settings")
        
        ttk.Label(self.content_frame, text="Alumni Directory Privacy Settings", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Settings form
        settings_frame = ttk.LabelFrame(self.content_frame, text="Privacy Settings", padding=20)
        settings_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Privacy options
        self.privacy_vars = {}
        
        privacy_options = [
            ("show_contact", "Show contact information in directory"),
            ("show_employment", "Show employment information"),  
            ("show_education", "Show education information"),
            ("searchable", "Make profile searchable"),
            ("networking", "Available for networking requests"),
            ("mentor", "Available as mentor"),
            ("email_notifications", "Receive email notifications"),
            ("event_invitations", "Receive event invitations"),
            ("newsletter", "Subscribe to alumni newsletter")
        ]
        
        for var_name, description in privacy_options:
            self.privacy_vars[var_name] = tk.BooleanVar(value=True)
            ttk.Checkbutton(settings_frame, text=description, 
                           variable=self.privacy_vars[var_name]).pack(anchor='w', pady=5)
        
        # Profile visibility level
        visibility_frame = ttk.LabelFrame(self.content_frame, text="Profile Visibility", padding=20)
        visibility_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.visibility_level = tk.StringVar(value="Alumni Only")
        
        ttk.Radiobutton(visibility_frame, text="Public (visible to all)", 
                       variable=self.visibility_level, value="Public").pack(anchor='w', pady=2)
        ttk.Radiobutton(visibility_frame, text="Alumni Only (registered alumni only)", 
                       variable=self.visibility_level, value="Alumni Only").pack(anchor='w', pady=2)
        ttk.Radiobutton(visibility_frame, text="Private (only visible to me)", 
                       variable=self.visibility_level, value="Private").pack(anchor='w', pady=2)
        
        # Communication preferences
        comm_frame = ttk.LabelFrame(self.content_frame, text="Communication Preferences", padding=20)
        comm_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        ttk.Label(comm_frame, text="Preferred Contact Method:").pack(anchor='w', pady=(0, 5))
        self.contact_method = tk.StringVar(value="Email")
        
        contact_methods = ["Email", "Phone", "LinkedIn", "Alumni Platform Messages"]
        for method in contact_methods:
            ttk.Radiobutton(comm_frame, text=method, variable=self.contact_method, 
                           value=method).pack(anchor='w', pady=2)
        
        # Notification frequency
        freq_frame = ttk.Frame(comm_frame)
        freq_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(freq_frame, text="Notification Frequency:").pack(side=tk.LEFT, padx=(0, 10))
        self.notification_freq = tk.StringVar(value="Weekly")
        freq_combo = ttk.Combobox(freq_frame, textvariable=self.notification_freq,
                                 values=["Immediate", "Daily", "Weekly", "Monthly", "Never"])
        freq_combo.pack(side=tk.LEFT)
        
        # Save button
        ttk.Button(self.content_frame, text="Save Settings", 
                  command=self.save_directory_settings).pack(pady=20)
    
    def load_donations_data(self):
        """Load donations data into treeview"""
        try:
            # Clear existing data
            for item in self.donations_tree.get_children():
                self.donations_tree.delete(item)
            
            # Sample donations data
            sample_donations = [
                ('2025-08-15', 'Sarah Johnson', 'A000001', '$500.00', 'Annual Fund', 'Credit Card', 'Completed'),
                ('2025-08-12', 'Michael Chen', 'A000002', '$250.00', 'Scholarship Fund', 'Check', 'Completed'),
                ('2025-08-10', 'Emily Davis', 'A000003', '$100.00', 'Annual Fund', 'Online', 'Completed'),
                ('2025-08-08', 'John Smith', 'A000004', '$1000.00', 'Building Fund', 'Bank Transfer', 'Completed'),
                ('2025-08-05', 'Lisa Brown', 'A000005', '$75.00', 'Annual Fund', 'Credit Card', 'Completed')
            ]
            
            for donation in sample_donations:
                self.donations_tree.insert('', tk.END, values=donation)
            
            self.update_status(f"Loaded {len(sample_donations)} donation records")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load donations data: {str(e)}")
    
    def filter_donations(self):
        """Filter donations based on criteria"""
        # For demo, just reload data
        self.load_donations_data()
        filter_info = f"Filter applied: {self.donation_campaign_filter.get()}"
        if self.donation_from_date.get():
            filter_info += f", From: {self.donation_from_date.get()}"
        if self.donation_to_date.get():
            filter_info += f", To: {self.donation_to_date.get()}"
        self.update_status(filter_info)
    
    def update_donation_summary(self):
        """Update donation summary"""
        # Sample summary data
        total_amount = 1925.00
        total_donations = 5
        avg_donation = total_amount / total_donations
        
        summary_text = f"Total Donations: {total_donations} | Total Amount: ${total_amount:,.2f} | Average: ${avg_donation:.2f}"
        self.donation_summary.set(summary_text)
    
    def show_campaigns(self):
        """Show fundraising campaigns interface"""
        self.clear_content()
        self.update_status("Fundraising Campaigns")
        
        ttk.Label(self.content_frame, text="Fundraising Campaigns", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different campaign views
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Active campaigns tab
        active_frame = ttk.Frame(notebook)
        notebook.add(active_frame, text="Active Campaigns")
        
        active_text = ScrolledText(active_frame, wrap=tk.WORD)
        active_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        campaigns_content = """Active Fundraising Campaigns:

🎯 Annual Alumni Fund 2025
Goal: $100,000 | Raised: $67,500 (67.5%)
Duration: January 1, 2025 - December 31, 2025
Category: Annual Fund
Status: Active

Description: Support current students and enhance campus facilities through 
your alumni contributions. Every donation makes a difference!

Progress: ████████████████████████████████████████████████████░░░░░░░░░░

Donors: 245 | Average Donation: $275
Recent Donors: Sarah Johnson ($500), Michael Chen ($250), Emily Davis ($100)

[Donate Now] [View Details] [Share Campaign]

---

🏫 New Library Building Fund
Goal: $250,000 | Raised: $89,750 (35.9%)
Duration: March 1, 2025 - February 28, 2026
Category: Building Fund
Status: Active

Description: Help us build a state-of-the-art library with modern technology 
and collaborative learning spaces for future generations.

Progress: ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Donors: 67 | Average Donation: $1,340
Major Donors: Anonymous ($25,000), John Smith Foundation ($15,000)

[Donate Now] [View Details] [Share Campaign]

---

🎓 Emergency Student Support Fund
Goal: $50,000 | Raised: $31,200 (62.4%)
Duration: June 1, 2025 - August 31, 2025
Category: Student Support
Status: Active

Description: Provide emergency financial assistance to students facing 
unexpected hardships during their academic journey.

Progress: ████████████████████████████████████████████████████████████░░░░░░░░░░░░░░░░

Donors: 156 | Average Donation: $200
Recent Impact: Helped 23 students with emergency expenses

[Donate Now] [View Details] [Share Campaign]
"""
        active_text.insert(tk.END, campaigns_content)
        
        # Create campaign tab (for authorized users)
        if self.has_permission('manage_campaigns'):
            create_frame = ttk.Frame(notebook)
            notebook.add(create_frame, text="Create Campaign")
            
            self.create_campaign_form(create_frame)
    
    def create_campaign_form(self, parent):
        """Create fundraising campaign form"""
        ttk.Label(parent, text="Create New Fundraising Campaign", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Campaign details
        self.campaign_vars = {}
        
        details_fields = [
            ("Campaign Name*", "campaign_name"),
            ("Goal Amount ($)*", "goal_amount"),
            ("Start Date (YYYY-MM-DD)*", "start_date"),
            ("End Date (YYYY-MM-DD)*", "end_date")
        ]
        
        for i, (label, var_name) in enumerate(details_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(form_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=label).pack(anchor='w')
            self.campaign_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.campaign_vars[var_name]).pack(fill=tk.X)
        
        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(1, weight=1)
        
        # Category
        category_frame = ttk.Frame(form_frame)
        category_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky='ew')
        
        ttk.Label(category_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
        self.campaign_vars['category'] = tk.StringVar()
        category_combo = ttk.Combobox(category_frame, textvariable=self.campaign_vars['category'],
                                     values=["Annual Fund", "Scholarship Fund", "Building Fund", "Research Fund", "Student Support"])
        category_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Featured campaign
        featured_frame = ttk.Frame(form_frame)
        featured_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky='ew')
        
        self.campaign_vars['is_featured'] = tk.BooleanVar()
        ttk.Checkbutton(featured_frame, text="Feature this campaign on main page", 
                       variable=self.campaign_vars['is_featured']).pack(anchor='w')
        
        # Description
        desc_frame = ttk.Frame(form_frame)
        desc_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky='ew')
        
        ttk.Label(desc_frame, text="Campaign Description:").pack(anchor='w')
        self.campaign_description = ScrolledText(desc_frame, height=6, wrap=tk.WORD)
        self.campaign_description.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Submit button
        submit_frame = ttk.Frame(form_frame)
        submit_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(submit_frame, text="Create Campaign", 
                  command=self.submit_campaign).pack()
    
    def submit_campaign(self):
        """Submit fundraising campaign"""
        required_fields = ['campaign_name', 'goal_amount', 'start_date', 'end_date']
        for field in required_fields:
            if not self.campaign_vars[field].get().strip():
                messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                return
        
        try:
            goal_amount = float(self.campaign_vars['goal_amount'].get())
            if goal_amount <= 0:
                messagebox.showerror("Validation Error", "Goal amount must be greater than zero!")
                return
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid goal amount!")
            return
        
        messagebox.showinfo("Campaign Created", "Fundraising campaign created successfully!")
        self.update_status("Campaign creation completed")
        
        # Clear form
        for var in self.campaign_vars.values():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            else:
                var.set("")
        self.campaign_description.delete(1.0, tk.END)

    def view_campaign_performance(self):
        """View analytics for a specific campaign"""
        self.clear_content()
        self.update_status("Campaign Performance")

        ttk.Label(self.content_frame, text="Campaign Performance Analytics",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Campaign selection
        select_frame = ttk.LabelFrame(self.content_frame, text="Select Campaign", padding=10)
        select_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        ttk.Label(select_frame, text="Campaign:").pack(side=tk.LEFT, padx=(0, 10))
        self.selected_campaign = tk.StringVar()

        # Load campaigns
        campaign_options = []
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT campaign_id, campaign_name, goal_amount, start_date, end_date
                    FROM fundraising_campaigns
                    ORDER BY start_date DESC
                """)
                campaigns = cursor.fetchall()
                campaign_options = [f"{c[1]} (${c[2]:,.2f} goal) - {c[3]} (ID: {c[0]})" for c in campaigns]
        except:
            pass

        if not campaign_options:
            campaign_options = ["No campaigns available"]

        campaign_combo = ttk.Combobox(select_frame, textvariable=self.selected_campaign,
                                     values=campaign_options, width=60)
        campaign_combo.pack(side=tk.LEFT, padx=(0, 20))
        if campaign_options and campaign_options[0] != "No campaigns available":
            campaign_combo.set(campaign_options[0])

        ttk.Button(select_frame, text="Load Performance",
                  command=self._load_campaign_performance).pack(side=tk.LEFT)

        # Performance metrics
        self.performance_frame = ttk.LabelFrame(self.content_frame, text="Performance Metrics", padding=10)
        self.performance_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Summary metrics
        summary_frame = ttk.Frame(self.performance_frame)
        summary_frame.pack(fill=tk.X, pady=(0, 20))

        self.performance_labels = {}
        metrics = ['Total Raised', 'Number of Donors', 'Average Donation', 'Goal Progress']

        for i, metric in enumerate(metrics):
            metric_frame = ttk.Frame(summary_frame)
            metric_frame.grid(row=0, column=i, padx=10, pady=5, sticky='ew')

            ttk.Label(metric_frame, text=metric, font=('Arial', 10, 'bold')).pack()
            self.performance_labels[metric] = ttk.Label(metric_frame, text="--",
                                                        font=('Arial', 14))
            self.performance_labels[metric].pack()

        summary_frame.columnconfigure((0, 1, 2, 3), weight=1)

        # Donation history
        history_frame = ttk.LabelFrame(self.performance_frame, text="Recent Donations", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('Donor', 'Amount', 'Date', 'Payment Method')
        self.campaign_donations_tree = ttk.Treeview(history_frame, columns=columns, show='headings')

        for col in columns:
            self.campaign_donations_tree.heading(col, text=col)
            self.campaign_donations_tree.column(col, width=150)

        scrollbar_y = ttk.Scrollbar(history_frame, orient=tk.VERTICAL,
                                    command=self.campaign_donations_tree.yview)
        self.campaign_donations_tree.configure(yscrollcommand=scrollbar_y.set)

        self.campaign_donations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_campaign_performance(self):
        """Load and display campaign performance data"""
        campaign_selection = self.selected_campaign.get()
        if not campaign_selection or campaign_selection == "No campaigns available":
            messagebox.showwarning("No Selection", "Please select a campaign.")
            return

        # Extract campaign_id
        import re
        match = re.search(r'ID:\s*(\d+)', campaign_selection)
        if not match:
            messagebox.showerror("Error", "Invalid campaign selection.")
            return

        campaign_id = int(match.group(1))

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()

                # Get campaign details and performance
                cursor.execute("""
                    SELECT campaign_name, goal_amount,
                           (SELECT COALESCE(SUM(amount), 0) FROM donations WHERE campaign_id = ?) as total_raised,
                           (SELECT COUNT(*) FROM donations WHERE campaign_id = ?) as donor_count
                    FROM fundraising_campaigns
                    WHERE campaign_id = ?
                """, (campaign_id, campaign_id, campaign_id))
                campaign_data = cursor.fetchone()

                if campaign_data:
                    campaign_name, goal, total_raised, donor_count = campaign_data

                    # Calculate metrics
                    avg_donation = total_raised / donor_count if donor_count > 0 else 0
                    progress_pct = (total_raised / goal * 100) if goal > 0 else 0

                    # Update labels
                    self.performance_labels['Total Raised'].config(text=f"${total_raised:,.2f}")
                    self.performance_labels['Number of Donors'].config(text=str(donor_count))
                    self.performance_labels['Average Donation'].config(text=f"${avg_donation:,.2f}")
                    self.performance_labels['Goal Progress'].config(text=f"{progress_pct:.1f}%")

                    # Load recent donations
                    for item in self.campaign_donations_tree.get_children():
                        self.campaign_donations_tree.delete(item)

                    cursor.execute("""
                        SELECT donor_name, amount, donation_date, payment_method
                        FROM donations
                        WHERE campaign_id = ?
                        ORDER BY donation_date DESC
                        LIMIT 100
                    """, (campaign_id,))
                    donations = cursor.fetchall()

                    for donation in donations:
                        formatted = list(donation)
                        formatted[1] = f"${formatted[1]:,.2f}"
                        self.campaign_donations_tree.insert('', tk.END, values=formatted)

                    self.update_status(f"Loaded performance for: {campaign_name}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load performance: {str(e)}")

    def update_donor_recognition_levels(self):
        """Configure donor recognition tiers"""
        if not self.has_permission('admin') and not self.has_permission('manage_fundraising'):
            messagebox.showerror("Permission Denied",
                               "You don't have permission to manage donor recognition levels.")
            return

        self.clear_content()
        self.update_status("Donor Recognition Levels")

        ttk.Label(self.content_frame, text="Donor Recognition Levels",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Recognition levels table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Level Name', 'Min Amount', 'Max Amount', 'Benefits', 'Status')
        self.recognition_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.recognition_tree.heading(col, text=col)
            self.recognition_tree.column(col, width=140)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.recognition_tree.yview)
        self.recognition_tree.configure(yscrollcommand=scrollbar_y.set)

        self.recognition_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load recognition levels
        self._load_recognition_levels()

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Add New Level",
                  command=self._add_recognition_level).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Edit Level",
                  command=self._edit_recognition_level).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Delete Level",
                  command=self._delete_recognition_level).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self._load_recognition_levels).pack(side=tk.LEFT)

    def _load_recognition_levels(self):
        """Load donor recognition levels"""
        try:
            # Clear existing data
            for item in self.recognition_tree.get_children():
                self.recognition_tree.delete(item)

            with db_get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT level_name, min_amount, max_amount, benefits, status
                    FROM donor_recognition_levels
                    ORDER BY min_amount
                """)
                levels = cursor.fetchall()

                for level in levels:
                    formatted = list(level)
                    formatted[1] = f"${formatted[1]:,.2f}" if formatted[1] else "N/A"
                    formatted[2] = f"${formatted[2]:,.2f}" if formatted[2] else "No limit"
                    self.recognition_tree.insert('', tk.END, values=formatted)

                self.update_status(f"Loaded {len(levels)} recognition level(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load levels: {str(e)}")

    def _add_recognition_level(self):
        """Add a new recognition level"""
        messagebox.showinfo("Feature", "Recognition level editor dialog would open here.")

    def _edit_recognition_level(self):
        """Edit selected recognition level"""
        selection = self.recognition_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a level to edit.")
            return
        messagebox.showinfo("Feature", "Recognition level editor dialog would open here.")

    def _delete_recognition_level(self):
        """Delete selected recognition level"""
        selection = self.recognition_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a level to delete.")
            return

        if messagebox.askyesno("Confirm Deletion",
                              "Are you sure you want to delete this recognition level?"):
            messagebox.showinfo("Success", "Recognition level deleted!")
            self._load_recognition_levels()

    def view_alumni_stories(self):
        """List all alumni stories"""
        self.clear_content()
        self.update_status("Alumni Stories")

        ttk.Label(self.content_frame, text="Alumni Stories",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Filter frame
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
        self.story_filter_category = tk.StringVar()
        category_combo = ttk.Combobox(filter_frame, textvariable=self.story_filter_category,
                                     values=["All", "Career Success", "Entrepreneurship", "Community Impact",
                                            "Academic Achievement", "Personal Journey"])
        category_combo.pack(side=tk.LEFT, padx=(0, 20))
        category_combo.set("All")

        ttk.Button(filter_frame, text="Filter",
                  command=self._load_alumni_stories).pack(side=tk.LEFT)

        # Stories table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Title', 'Author', 'Category', 'Published Date', 'Views')
        self.stories_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.stories_tree.heading(col, text=col)
            self.stories_tree.column(col, width=140)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.stories_tree.yview)
        self.stories_tree.configure(yscrollcommand=scrollbar_y.set)

        self.stories_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load stories
        self._load_alumni_stories()

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Read Full Story",
                  command=self.read_full_story).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Submit Your Story",
                  command=self.show_create_story).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self._load_alumni_stories).pack(side=tk.LEFT)

    def _load_alumni_stories(self):
        """Load alumni stories from database"""
        try:
            # Clear existing data
            for item in self.stories_tree.get_children():
                self.stories_tree.delete(item)

            with db_get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT story_id, title, author_name, category, published_date, view_count
                    FROM alumni_stories
                    WHERE status = 'published'
                """
                params = []

                # Add category filter
                category = self.story_filter_category.get()
                if category != "All":
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY published_date DESC"

                cursor.execute(query, params)
                stories = cursor.fetchall()

                for story in stories:
                    # Display without story_id
                    self.stories_tree.insert('', tk.END, values=story[1:])

                self.update_status(f"Loaded {len(stories)} story/stories")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load stories: {str(e)}")

    def read_full_story(self):
        """View complete story details"""
        if not hasattr(self, 'stories_tree'):
            messagebox.showwarning("Not Available", "Please use 'View Alumni Stories' first.")
            return

        selection = self.stories_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a story to read.")
            return

        item = self.stories_tree.item(selection[0])
        story_data = item['values']

        # Create story window
        story_window = tk.Toplevel(self.root)
        story_window.title(f"{story_data[0]}")
        story_window.geometry("700x600")
        story_window.configure(bg='white')

        # Main frame
        main_frame = ttk.Frame(story_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=story_data[0],
                 font=('Arial', 16, 'bold')).pack(pady=(0, 10))

        # Meta info
        meta_text = f"By {story_data[1]} | {story_data[2]} | Published: {story_data[3]} | Views: {story_data[4]}"
        ttk.Label(main_frame, text=meta_text,
                 font=('Arial', 9), foreground='gray').pack(pady=(0, 20))

        # Story content
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        story_text = ScrolledText(content_frame, wrap=tk.WORD)
        story_text.pack(fill=tk.BOTH, expand=True)

        # Load story content from database
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT content FROM alumni_stories
                    WHERE title = ? AND author_name = ?
                """, (story_data[0], story_data[1]))
                result = cursor.fetchone()

                if result:
                    story_text.insert(tk.END, result[0])

                    # Increment view count
                    cursor.execute("""
                        UPDATE alumni_stories
                        SET view_count = view_count + 1
                        WHERE title = ? AND author_name = ?
                    """, (story_data[0], story_data[1]))
                    conn.commit()
                else:
                    story_text.insert(tk.END, "[Story content would be displayed here]")

        except:
            story_text.insert(tk.END, "[Story content would be displayed here]")

        story_text.config(state='disabled')

        # Close button
        ttk.Button(main_frame, text="Close",
                  command=story_window.destroy).pack()

    # Mentorship Methods
    def show_setup_mentorship(self):
        """Show mentorship setup interface"""
        self.clear_content()
        self.update_status("Setup Mentorship")
        
        ttk.Label(self.content_frame, text="Mentorship Program Setup", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different mentorship actions
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Become mentor tab
        mentor_frame = ttk.Frame(notebook)
        notebook.add(mentor_frame, text="Become a Mentor")
        
        self.create_mentor_signup_form(mentor_frame)
        
        # Request mentorship tab
        mentee_frame = ttk.Frame(notebook)
        notebook.add(mentee_frame, text="Request Mentorship")
        
        self.create_mentee_request_form(mentee_frame)
        
        # Manual pairing tab (for staff)
        if self.has_permission('manage_mentorships'):
            pairing_frame = ttk.Frame(notebook)
            notebook.add(pairing_frame, text="Create Mentorship Pair")
            
            self.create_mentorship_pairing_form(pairing_frame)
    
    def create_mentor_signup_form(self, parent):
        """Create mentor signup form"""
        ttk.Label(parent, text="Sign Up as a Mentor", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        info_text = """Become a mentor and share your experience with fellow alumni and current students!

As a mentor, you will:
• Guide mentees in their career development
• Share industry insights and experiences
• Provide networking opportunities
• Help with professional skill development
"""
        
        ttk.Label(form_frame, text=info_text, justify=tk.LEFT).pack(pady=(0, 20))
        
        # Mentor details
        self.mentor_vars = {}
        
        # Areas of expertise
        expertise_frame = ttk.Frame(form_frame)
        expertise_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(expertise_frame, text="Areas of Expertise:").pack(anchor='w')
        self.mentor_vars['expertise'] = ScrolledText(expertise_frame, height=3, wrap=tk.WORD)
        self.mentor_vars['expertise'].pack(fill=tk.X, pady=(5, 0))
        
        # Industries
        industries_frame = ttk.Frame(form_frame)
        industries_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(industries_frame, text="Industries:").pack(anchor='w')
        self.mentor_vars['industries'] = tk.StringVar()
        ttk.Entry(industries_frame, textvariable=self.mentor_vars['industries']).pack(fill=tk.X, pady=(5, 0))
        
        # Availability
        availability_frame = ttk.Frame(form_frame)
        availability_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(availability_frame, text="Availability:").pack(anchor='w')
        self.mentor_vars['availability'] = tk.StringVar()
        availability_combo = ttk.Combobox(availability_frame, textvariable=self.mentor_vars['availability'],
                                         values=["Weekday evenings", "Weekend mornings", "Weekend afternoons", "Flexible"])
        availability_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Preferred communication
        comm_frame = ttk.Frame(form_frame)
        comm_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(comm_frame, text="Preferred Communication:").pack(anchor='w')
        self.mentor_vars['communication'] = tk.StringVar()
        comm_combo = ttk.Combobox(comm_frame, textvariable=self.mentor_vars['communication'],
                                 values=["Email", "Phone", "Video calls", "In-person meetings"])
        comm_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Submit button
        ttk.Button(form_frame, text="Sign Up as Mentor", 
                  command=self.submit_mentor_signup).pack(pady=20)
    
    def submit_mentor_signup(self):
        """Submit mentor signup"""
        expertise = self.mentor_vars['expertise'].get(1.0, tk.END).strip()
        if not expertise:
            messagebox.showerror("Validation Error", "Please describe your areas of expertise!")
            return
        
        messagebox.showinfo("Mentor Signup", "Thank you for signing up as a mentor! You will be contacted soon.")
        self.update_status("Mentor signup completed")
        
        # Clear form
        self.mentor_vars['expertise'].delete(1.0, tk.END)
        self.mentor_vars['industries'].set("")
        self.mentor_vars['availability'].set("")
        self.mentor_vars['communication'].set("")
    
    def create_mentee_request_form(self, parent):
        """Create mentee request form"""
        ttk.Label(parent, text="Request a Mentor", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        info_text = """Request a mentor to help guide your career development!

A mentor can help you with:
• Career planning and goal setting
• Industry insights and networking
• Resume and interview preparation
• Professional skill development
• Decision making and problem solving
"""
        
        ttk.Label(form_frame, text=info_text, justify=tk.LEFT).pack(pady=(0, 20))
        
        # Mentee details
        self.mentee_vars = {}
        
        # Career goals
        goals_frame = ttk.Frame(form_frame)
        goals_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(goals_frame, text="Career Goals:").pack(anchor='w')
        self.mentee_vars['goals'] = ScrolledText(goals_frame, height=3, wrap=tk.WORD)
        self.mentee_vars['goals'].pack(fill=tk.X, pady=(5, 0))
        
        # Areas of interest
        interest_frame = ttk.Frame(form_frame)
        interest_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(interest_frame, text="Areas of Interest:").pack(anchor='w')
        self.mentee_vars['interests'] = tk.StringVar()
        ttk.Entry(interest_frame, textvariable=self.mentee_vars['interests']).pack(fill=tk.X, pady=(5, 0))
        
        # Current stage
        stage_frame = ttk.Frame(form_frame)
        stage_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(stage_frame, text="Current Career Stage:").pack(anchor='w')
        self.mentee_vars['stage'] = tk.StringVar()
        stage_combo = ttk.Combobox(stage_frame, textvariable=self.mentee_vars['stage'],
                                  values=["Student", "Recent Graduate", "Early Career", "Career Change", "Mid-Career"])
        stage_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Preferred mentor characteristics
        mentor_pref_frame = ttk.Frame(form_frame)
        mentor_pref_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(mentor_pref_frame, text="Preferred Mentor Characteristics:").pack(anchor='w')
        self.mentee_vars['mentor_prefs'] = ScrolledText(mentor_pref_frame, height=2, wrap=tk.WORD)
        self.mentee_vars['mentor_prefs'].pack(fill=tk.X, pady=(5, 0))
        
        # Submit button
        ttk.Button(form_frame, text="Request Mentor", 
                  command=self.submit_mentee_request).pack(pady=20)
    
    def submit_mentee_request(self):
        """Submit mentee request"""
        goals = self.mentee_vars['goals'].get(1.0, tk.END).strip()
        if not goals:
            messagebox.showerror("Validation Error", "Please describe your career goals!")
            return
        
        messagebox.showinfo("Mentorship Request", "Your mentorship request has been submitted! We'll match you with a suitable mentor.")
        self.update_status("Mentorship request submitted")
        
        # Clear form
        self.mentee_vars['goals'].delete(1.0, tk.END)
        self.mentee_vars['interests'].set("")
        self.mentee_vars['stage'].set("")
        self.mentee_vars['mentor_prefs'].delete(1.0, tk.END)
    
    def create_mentorship_pairing_form(self, parent):
        """Create manual mentorship pairing form"""
        ttk.Label(parent, text="Create Mentorship Pair", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Mentor selection
        mentor_frame = ttk.Frame(form_frame)
        mentor_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(mentor_frame, text="Select Mentor:").pack(anchor='w')
        self.pairing_vars = {}
        self.pairing_vars['mentor'] = tk.StringVar()
        mentor_combo = ttk.Combobox(mentor_frame, textvariable=self.pairing_vars['mentor'],
                                   values=["Sarah Johnson - Technology", "Michael Chen - Finance", "Dr. Lisa Martinez - Healthcare"])
        mentor_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Mentee selection
        mentee_frame = ttk.Frame(form_frame)
        mentee_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(mentee_frame, text="Select Mentee:").pack(anchor='w')
        self.pairing_vars['mentee'] = tk.StringVar()
        mentee_combo = ttk.Combobox(mentee_frame, textvariable=self.pairing_vars['mentee'],
                                   values=["John Smith - Student", "Emma Wilson - Recent Graduate", "Alex Brown - Career Change"])
        mentee_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Focus area
        focus_frame = ttk.Frame(form_frame)
        focus_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(focus_frame, text="Focus Area:").pack(anchor='w')
        self.pairing_vars['focus'] = tk.StringVar()
        focus_combo = ttk.Combobox(focus_frame, textvariable=self.pairing_vars['focus'],
                                  values=["Career Planning", "Industry Transition", "Leadership Development", "Technical Skills"])
        focus_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Duration
        duration_frame = ttk.Frame(form_frame)
        duration_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(duration_frame, text="Duration (months):").pack(anchor='w')
        self.pairing_vars['duration'] = tk.StringVar(value="6")
        duration_combo = ttk.Combobox(duration_frame, textvariable=self.pairing_vars['duration'],
                                     values=["3", "6", "12", "Ongoing"])
        duration_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Notes
        ttk.Label(form_frame, text="Notes:").pack(anchor='w', pady=(10, 5))
        self.pairing_notes = ScrolledText(form_frame, height=3, wrap=tk.WORD)
        self.pairing_notes.pack(fill=tk.X)
        
        # Submit button
        ttk.Button(form_frame, text="Create Mentorship", 
                  command=self.submit_mentorship_pairing).pack(pady=20)
    
    def submit_mentorship_pairing(self):
        """Submit mentorship pairing"""
        if not self.pairing_vars['mentor'].get():
            messagebox.showerror("Validation Error", "Please select a mentor!")
            return
        
        if not self.pairing_vars['mentee'].get():
            messagebox.showerror("Validation Error", "Please select a mentee!")
            return
        
        messagebox.showinfo("Mentorship Created", "Mentorship pairing created successfully!")
        self.update_status("Mentorship pairing completed")
        
        # Clear form
        for var in self.pairing_vars.values():
            var.set("")
        self.pairing_notes.delete(1.0, tk.END)
    
    def show_view_mentorships(self):
        """Show mentorships viewer"""
        self.clear_content()
        self.update_status("View Mentorships")
        
        ttk.Label(self.content_frame, text="Mentorship Program Overview", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different mentorship views
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Active mentorships tab
        active_frame = ttk.Frame(notebook)
        notebook.add(active_frame, text="Active Mentorships")
        
        active_text = ScrolledText(active_frame, wrap=tk.WORD)
        active_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        mentorships_content = """Active Mentorship Relationships:

👥 Mentorship #001
Mentor: Sarah Johnson (Class of 2015) - Senior Developer
Mentee: John Smith (Class of 2023) - Recent Graduate
Focus Area: Career Planning in Technology
Start Date: July 1, 2025
Duration: 6 months
Status: Active
Meeting Frequency: Bi-weekly
Last Meeting: August 10, 2025
Next Meeting: August 24, 2025

Progress Notes: John is making excellent progress in his job search. 
We've worked on resume optimization and interview skills.

[View Details] [Schedule Meeting] [Send Message]

---

👥 Mentorship #002
Mentor: Dr. Lisa Martinez (Class of 2012) - Healthcare Administrator
Mentee: Emma Wilson (Class of 2021) - Career Transition
Focus Area: Healthcare Leadership
Start Date: June 15, 2025
Duration: 12 months
Status: Active
Meeting Frequency: Monthly
Last Meeting: August 5, 2025
Next Meeting: September 5, 2025

Progress Notes: Emma is successfully transitioning from clinical work 
to healthcare administration. Exploring MBA programs.

[View Details] [Schedule Meeting] [Send Message]

---

👥 Mentorship #003
Mentor: Michael Chen (Class of 2018) - Financial Analyst
Mentee: Alex Brown (Class of 2020) - Industry Change
Focus Area: Finance Career Development
Start Date: August 1, 2025
Duration: 6 months
Status: Active
Meeting Frequency: Weekly (initial phase)
Last Meeting: August 15, 2025
Next Meeting: August 22, 2025

Progress Notes: Alex is learning financial modeling and analysis. 
Strong foundation, quick learner, making good progress.

[View Details] [Schedule Meeting] [Send Message]
"""
        active_text.insert(tk.END, mentorships_content)
        
        # Program statistics tab
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Program Statistics")
        
        stats_text = ScrolledText(stats_frame, wrap=tk.WORD)
        stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        stats_content = """Mentorship Program Statistics:

📊 OVERALL PROGRAM METRICS
Total Active Mentorships: 15
Total Mentors: 25
Total Mentees: 18
Waiting List: 8 mentees
Match Success Rate: 89%

📈 PROGRAM GROWTH
New Mentorships This Month: 3
Completed Mentorships (Last 6 Months): 12
Average Mentorship Duration: 8.5 months
Satisfaction Rating: 4.7/5.0

🎯 FOCUS AREAS
Career Planning: 6 mentorships
Industry Transition: 4 mentorships
Leadership Development: 3 mentorships
Technical Skills: 2 mentorships

💥 MENTOR DEMOGRAPHICS
By Industry:
• Technology: 8 mentors
• Healthcare: 6 mentors
• Finance: 5 mentors
• Education: 3 mentors
• Other: 3 mentors

By Graduation Year:
• 2010-2015: 12 mentors
• 2016-2020: 8 mentors
• 2021-2025: 5 mentors

🎓 MENTEE DEMOGRAPHICS
By Status:
• Current Students: 7 mentees
• Recent Graduates: 6 mentees
• Career Changers: 5 mentees

📅 UPCOMING EVENTS
• Mentor Training Workshop: September 15, 2025
• Mentorship Program Mixer: October 20, 2025
• Mid-Program Check-in Sessions: November 2025
"""
        stats_text.insert(tk.END, stats_content)
    
    def show_class_reunions(self):
        """Show class reunions interface"""
        self.clear_content()
        self.update_status("Class Reunions")
        
        ttk.Label(self.content_frame, text="Class Reunion Management", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different reunion views
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Upcoming reunions tab
        upcoming_frame = ttk.Frame(notebook)
        notebook.add(upcoming_frame, text="Upcoming Reunions")
        
        upcoming_text = ScrolledText(upcoming_frame, wrap=tk.WORD)
        upcoming_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        reunion_content = """Upcoming Class Reunions:

🎓 Class of 2020 - 5 Year Reunion
Date: October 10, 2025
Location: Campus Alumni Center
Organizer: Emily Davis
Registration Fee: $50.00
Expected Attendees: 150
Registration Deadline: September 25, 2025
Status: Registration Open

Details: Join us for a weekend of reconnection, campus tours, dinner, and celebration. 
Special presentations from notable class members and career networking opportunities.

[Register Now] [View Details]

---

🎓 Class of 2015 - 10 Year Reunion  
Date: November 15, 2025
Location: Grand Hotel Downtown
Organizer: Sarah Johnson
Registration Fee: $75.00
Expected Attendees: 200
Registration Deadline: October 30, 2025
Status: Planning Phase

Details: A formal dinner and celebration marking our 10-year milestone. 
Cocktail hour, awards ceremony, and dance with live music.

[Register Now] [View Details]

---

🎓 Class of 2000 - 25 Year Reunion
Date: June 20, 2026  
Location: TBD
Organizer: Needed
Registration Fee: TBD
Expected Attendees: TBD
Status: Organizer Needed

Details: Planning committee forming for our 25-year celebration. 
Volunteers needed to help organize this milestone event.

[Volunteer to Organize] [Express Interest]
"""
        upcoming_text.insert(tk.END, reunion_content)
        
        # Plan reunion tab
        plan_frame = ttk.Frame(notebook)
        notebook.add(plan_frame, text="Plan a Reunion")
        
        self.create_reunion_form(plan_frame)
    
    def create_reunion_form(self, parent):
        """Create reunion planning form"""
        ttk.Label(parent, text="Plan a Class Reunion", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Basic details
        self.reunion_vars = {}
        
        basic_fields = [
            ("Graduation Year*", "graduation_year"),
            ("Reunion Date*", "reunion_date"),
            ("Location*", "location"),
            ("Registration Fee", "fee")
        ]
        
        for label, var_name in basic_fields:
            field_frame = ttk.Frame(form_frame)
            field_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
            self.reunion_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.reunion_vars[var_name]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Description
        ttk.Label(form_frame, text="Reunion Description:").pack(anchor='w', pady=(10, 5))
        self.reunion_description = ScrolledText(form_frame, height=6, wrap=tk.WORD)
        self.reunion_description.pack(fill=tk.X)
        
        # Submit button
        ttk.Button(form_frame, text="Submit Reunion Plan", 
                  command=self.submit_reunion_plan).pack(pady=20)
    
    def submit_reunion_plan(self):
        """Submit reunion planning form"""
        required_fields = ['graduation_year', 'reunion_date', 'location']
        for field in required_fields:
            if not self.reunion_vars[field].get().strip():
                messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                return
        
        messagebox.showinfo("Reunion Planned", "Class reunion plan submitted successfully!")
        self.update_status("Reunion planning form submitted")

    def manage_existing_reunion(self):
        """Edit an existing reunion"""
        self.clear_content()
        self.update_status("Manage Reunion")

        ttk.Label(self.content_frame, text="Manage Existing Reunion",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Reunion selection
        select_frame = ttk.LabelFrame(self.content_frame, text="Select Reunion to Manage", padding=10)
        select_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        ttk.Label(select_frame, text="Select Reunion:").pack(side=tk.LEFT, padx=(0, 10))
        self.selected_reunion = tk.StringVar()

        # Load reunions from database
        reunion_options = []
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT reunion_id, graduation_year, reunion_date, location
                    FROM class_reunions
                    WHERE organizer_id = ? OR status = 'planning'
                    ORDER BY reunion_date DESC
                """, (self._current_user_id(),))
                reunions = cursor.fetchall()
                reunion_options = [f"Class of {r[1]} - {r[2]} at {r[3]} (ID: {r[0]})" for r in reunions]
        except:
            pass

        if not reunion_options:
            reunion_options = ["No reunions available to manage"]

        reunion_combo = ttk.Combobox(select_frame, textvariable=self.selected_reunion,
                                    values=reunion_options, width=50)
        reunion_combo.pack(side=tk.LEFT, padx=(0, 20))
        if reunion_options and reunion_options[0] != "No reunions available to manage":
            reunion_combo.set(reunion_options[0])

        ttk.Button(select_frame, text="Load Reunion",
                  command=self._load_reunion_for_edit).pack(side=tk.LEFT)

        # Edit form (initially hidden)
        self.reunion_edit_frame = ttk.LabelFrame(self.content_frame, text="Reunion Details", padding=10)
        self.reunion_edit_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Form fields
        self.edit_reunion_vars = {}

        fields = [
            ("Graduation Year*", "graduation_year"),
            ("Reunion Date*", "reunion_date"),
            ("Location*", "location"),
            ("Registration Fee", "fee"),
            ("Expected Attendees", "expected_attendees"),
            ("Registration Deadline", "reg_deadline")
        ]

        for label, var_name in fields:
            field_frame = ttk.Frame(self.reunion_edit_frame)
            field_frame.pack(fill=tk.X, pady=5)

            ttk.Label(field_frame, text=label, width=20).pack(side=tk.LEFT, padx=(0, 10))
            self.edit_reunion_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.edit_reunion_vars[var_name]).pack(
                side=tk.LEFT, fill=tk.X, expand=True)

        # Status
        status_frame = ttk.Frame(self.reunion_edit_frame)
        status_frame.pack(fill=tk.X, pady=5)

        ttk.Label(status_frame, text="Status*", width=20).pack(side=tk.LEFT, padx=(0, 10))
        self.edit_reunion_vars['status'] = tk.StringVar()
        status_combo = ttk.Combobox(status_frame, textvariable=self.edit_reunion_vars['status'],
                                   values=["planning", "registration_open", "registration_closed", "completed", "cancelled"])
        status_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Description
        ttk.Label(self.reunion_edit_frame, text="Description:").pack(anchor='w', pady=(10, 5))
        self.edit_reunion_description = ScrolledText(self.reunion_edit_frame, height=6, wrap=tk.WORD)
        self.edit_reunion_description.pack(fill=tk.X)

        # Action buttons
        button_frame = ttk.Frame(self.reunion_edit_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text="Save Changes",
                  command=self._save_reunion_changes).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel Reunion",
                  command=self._cancel_reunion).pack(side=tk.LEFT)

    def _load_reunion_for_edit(self):
        """Load selected reunion data into edit form"""
        reunion_selection = self.selected_reunion.get()
        if not reunion_selection or reunion_selection == "No reunions available to manage":
            messagebox.showwarning("No Selection", "Please select a reunion to manage.")
            return

        # Extract reunion_id
        import re
        match = re.search(r'ID:\s*(\d+)', reunion_selection)
        if not match:
            messagebox.showerror("Error", "Invalid reunion selection.")
            return

        reunion_id = int(match.group(1))

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT graduation_year, reunion_date, location, fee,
                           expected_attendees, registration_deadline, status, description
                    FROM class_reunions
                    WHERE reunion_id = ?
                """, (reunion_id,))
                reunion = cursor.fetchone()

                if reunion:
                    self.edit_reunion_vars['graduation_year'].set(reunion[0] or '')
                    self.edit_reunion_vars['reunion_date'].set(reunion[1] or '')
                    self.edit_reunion_vars['location'].set(reunion[2] or '')
                    self.edit_reunion_vars['fee'].set(reunion[3] or '')
                    self.edit_reunion_vars['expected_attendees'].set(reunion[4] or '')
                    self.edit_reunion_vars['reg_deadline'].set(reunion[5] or '')
                    self.edit_reunion_vars['status'].set(reunion[6] or 'planning')

                    self.edit_reunion_description.delete(1.0, tk.END)
                    if reunion[7]:
                        self.edit_reunion_description.insert(tk.END, reunion[7])

                    self.update_status(f"Loaded reunion for Class of {reunion[0]}")
                else:
                    messagebox.showerror("Error", "Reunion not found.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load reunion: {str(e)}")

    def _save_reunion_changes(self):
        """Save changes to reunion"""
        reunion_selection = self.selected_reunion.get()
        if not reunion_selection:
            return

        # Extract reunion_id
        import re
        match = re.search(r'ID:\s*(\d+)', reunion_selection)
        if not match:
            return

        reunion_id = int(match.group(1))

        # Validation
        if not self.edit_reunion_vars['graduation_year'].get():
            messagebox.showerror("Validation Error", "Graduation year is required!")
            return

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE class_reunions
                    SET graduation_year = ?, reunion_date = ?, location = ?,
                        fee = ?, expected_attendees = ?, registration_deadline = ?,
                        status = ?, description = ?
                    WHERE reunion_id = ?
                """, (
                    self.edit_reunion_vars['graduation_year'].get(),
                    self.edit_reunion_vars['reunion_date'].get(),
                    self.edit_reunion_vars['location'].get(),
                    self.edit_reunion_vars['fee'].get() or None,
                    self.edit_reunion_vars['expected_attendees'].get() or None,
                    self.edit_reunion_vars['reg_deadline'].get() or None,
                    self.edit_reunion_vars['status'].get(),
                    self.edit_reunion_description.get(1.0, tk.END).strip(),
                    reunion_id
                ))
                conn.commit()

            messagebox.showinfo("Success", "Reunion updated successfully!")
            self.update_status("Reunion changes saved")

            # Log activity
            from university_system.modules.shared.utils.activity_logger import log_activity
            log_activity('update', 'reunion', reunion_id=reunion_id,
                       details={'graduation_year': self.edit_reunion_vars['graduation_year'].get()})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save changes: {str(e)}")

    def _cancel_reunion(self):
        """Cancel a reunion"""
        if messagebox.askyesno("Confirm Cancellation",
                              "Are you sure you want to cancel this reunion? This action cannot be undone."):
            reunion_selection = self.selected_reunion.get()
            if not reunion_selection:
                return

            # Extract reunion_id
            import re
            match = re.search(r'ID:\s*(\d+)', reunion_selection)
            if not match:
                return

            reunion_id = int(match.group(1))

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE class_reunions
                        SET status = 'cancelled'
                        WHERE reunion_id = ?
                    """, (reunion_id,))
                    conn.commit()

                messagebox.showinfo("Success", "Reunion cancelled successfully!")
                self.manage_existing_reunion()  # Reload

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('update', 'reunion', reunion_id=reunion_id,
                           details={'action': 'cancelled'})

            except Exception as e:
                messagebox.showerror("Error", f"Failed to cancel reunion: {str(e)}")

    def view_my_chapters(self):
        """View chapters the user is member of"""
        self.clear_content()
        self.update_status("My Chapters")

        ttk.Label(self.content_frame, text="My Chapter Memberships",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Chapters table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Chapter Name', 'Location', 'Role', 'Joined Date', 'Status')
        self.my_chapters_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.my_chapters_tree.heading(col, text=col)
            self.my_chapters_tree.column(col, width=150)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.my_chapters_tree.yview)
        self.my_chapters_tree.configure(yscrollcommand=scrollbar_y.set)

        self.my_chapters_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load user's chapters
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                query = """
                    SELECT rc.chapter_name, rc.location, cm.role,
                           cm.join_date, cm.status
                    FROM chapter_members cm
                    JOIN regional_chapters rc ON cm.chapter_id = rc.chapter_id
                    WHERE cm.member_id = ?
                    ORDER BY cm.join_date DESC
                """
                cursor.execute(query, (user_id,))
                chapters = cursor.fetchall()

                for chapter in chapters:
                    self.my_chapters_tree.insert('', tk.END, values=chapter)

                self.update_status(f"You are a member of {len(chapters)} chapter(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load chapters: {str(e)}")

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Leave Chapter",
                  command=self._leave_chapter).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Join New Chapter",
                  command=self.join_regional_chapter).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self.view_my_chapters).pack(side=tk.LEFT)

    def _leave_chapter(self):
        """Leave a selected chapter"""
        if not hasattr(self, 'my_chapters_tree'):
            return

        selection = self.my_chapters_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a chapter to leave.")
            return

        if messagebox.askyesno("Confirm Leave",
                              "Are you sure you want to leave this chapter?"):
            item = self.my_chapters_tree.item(selection[0])
            chapter_data = item['values']
            chapter_name = chapter_data[0]

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    # Get chapter_id
                    cursor.execute("SELECT chapter_id FROM regional_chapters WHERE chapter_name = ?",
                                 (chapter_name,))
                    result = cursor.fetchone()

                    if result:
                        chapter_id = result[0]
                        cursor.execute("""
                            DELETE FROM chapter_members
                            WHERE chapter_id = ? AND member_id = ?
                        """, (chapter_id, user_id))

                        # Update member count
                        cursor.execute("""
                            UPDATE regional_chapters
                            SET member_count = member_count - 1
                            WHERE chapter_id = ?
                        """, (chapter_id,))

                        conn.commit()

                        messagebox.showinfo("Success", f"You have left {chapter_name}.")
                        self.view_my_chapters()  # Refresh

                        # Log activity
                        from university_system.modules.shared.utils.activity_logger import log_activity
                        log_activity('delete', 'chapter_membership',
                                   details={'chapter': chapter_name, 'action': 'left'})

            except Exception as e:
                messagebox.showerror("Error", f"Failed to leave chapter: {str(e)}")

    def admin_manage_chapters(self):
        """Admin controls for managing chapters"""
        if not self.has_permission('admin') and not self.has_permission('manage_alumni'):
            messagebox.showerror("Permission Denied",
                               "You don't have permission to manage chapters.")
            return

        self.clear_content()
        self.update_status("Manage Chapters (Admin)")

        ttk.Label(self.content_frame, text="Chapter Management (Admin)",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Chapters table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Chapter ID', 'Chapter Name', 'Location', 'Coordinator', 'Members', 'Status', 'Created')
        self.admin_chapters_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.admin_chapters_tree.heading(col, text=col)
            if col == 'Chapter ID':
                self.admin_chapters_tree.column(col, width=80)
            else:
                self.admin_chapters_tree.column(col, width=120)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.admin_chapters_tree.yview)
        self.admin_chapters_tree.configure(yscrollcommand=scrollbar_y.set)

        self.admin_chapters_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load all chapters
        self._load_all_chapters()

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Edit Chapter",
                  command=self._edit_chapter_admin).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Deactivate",
                  command=lambda: self._update_chapter_status('inactive')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Activate",
                  command=lambda: self._update_chapter_status('active')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Delete Chapter",
                  command=self._delete_chapter_admin).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self._load_all_chapters).pack(side=tk.LEFT)

    def _load_all_chapters(self):
        """Load all chapters for admin view"""
        try:
            # Clear existing data
            for item in self.admin_chapters_tree.get_children():
                self.admin_chapters_tree.delete(item)

            with db_get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT chapter_id, chapter_name, location, coordinator_name,
                           member_count, status, created_date
                    FROM regional_chapters
                    ORDER BY created_date DESC
                """
                cursor.execute(query)
                chapters = cursor.fetchall()

                for chapter in chapters:
                    self.admin_chapters_tree.insert('', tk.END, values=chapter)

                self.update_status(f"Loaded {len(chapters)} chapter(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load chapters: {str(e)}")

    def _edit_chapter_admin(self):
        """Edit selected chapter"""
        selection = self.admin_chapters_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a chapter to edit.")
            return

        item = self.admin_chapters_tree.item(selection[0])
        chapter_data = item['values']
        chapter_id = chapter_data[0]

        # Create edit dialog
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Edit Chapter - {chapter_data[1]}")
        edit_window.geometry("500x400")
        edit_window.configure(bg='white')
        edit_window.grab_set()

        frame = ttk.Frame(edit_window, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Edit Chapter: {chapter_data[1]}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form fields
        edit_vars = {}
        fields = [
            ("Chapter Name:", "name", chapter_data[1]),
            ("Location:", "location", chapter_data[2]),
            ("Coordinator:", "coordinator", chapter_data[3])
        ]

        for label, var_name, default_value in fields:
            field_frame = ttk.Frame(frame)
            field_frame.pack(fill=tk.X, pady=5)

            ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
            edit_vars[var_name] = tk.StringVar(value=default_value)
            ttk.Entry(field_frame, textvariable=edit_vars[var_name]).pack(
                side=tk.LEFT, fill=tk.X, expand=True)

        def save_chapter_changes():
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE regional_chapters
                        SET chapter_name = ?, location = ?, coordinator_name = ?
                        WHERE chapter_id = ?
                    """, (
                        edit_vars['name'].get(),
                        edit_vars['location'].get(),
                        edit_vars['coordinator'].get(),
                        chapter_id
                    ))
                    conn.commit()

                messagebox.showinfo("Success", "Chapter updated successfully!")
                edit_window.destroy()
                self._load_all_chapters()

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('update', 'chapter', chapter_id=chapter_id,
                           details={'name': edit_vars['name'].get()})

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update chapter: {str(e)}")

        ttk.Button(frame, text="Save Changes",
                  command=save_chapter_changes).pack(pady=20)
        ttk.Button(frame, text="Cancel",
                  command=edit_window.destroy).pack()

    def _update_chapter_status(self, status):
        """Update chapter status"""
        selection = self.admin_chapters_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a chapter.")
            return

        item = self.admin_chapters_tree.item(selection[0])
        chapter_data = item['values']
        chapter_id = chapter_data[0]

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE regional_chapters
                    SET status = ?
                    WHERE chapter_id = ?
                """, (status, chapter_id))
                conn.commit()

            messagebox.showinfo("Success", f"Chapter {status}!")
            self._load_all_chapters()

            # Log activity
            from university_system.modules.shared.utils.activity_logger import log_activity
            log_activity('update', 'chapter', chapter_id=chapter_id,
                       details={'action': f'status_changed_to_{status}'})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update status: {str(e)}")

    def _delete_chapter_admin(self):
        """Delete selected chapter"""
        selection = self.admin_chapters_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a chapter to delete.")
            return

        item = self.admin_chapters_tree.item(selection[0])
        chapter_data = item['values']
        chapter_id = chapter_data[0]

        if messagebox.askyesno("Confirm Deletion",
                              f"Are you sure you want to delete '{chapter_data[1]}'? "
                              f"This will also remove all {chapter_data[4]} member(s)."):
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    # Delete chapter members first
                    cursor.execute("DELETE FROM chapter_members WHERE chapter_id = ?", (chapter_id,))

                    # Delete chapter
                    cursor.execute("DELETE FROM regional_chapters WHERE chapter_id = ?", (chapter_id,))

                    conn.commit()

                messagebox.showinfo("Success", "Chapter deleted successfully!")
                self._load_all_chapters()

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('delete', 'chapter', chapter_id=chapter_id,
                           details={'name': chapter_data[1], 'action': 'deleted'})

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete chapter: {str(e)}")

    def join_regional_chapter(self):
        """Join a regional chapter"""
        self.clear_content()
        self.update_status("Join Regional Chapter")

        ttk.Label(self.content_frame, text="Join a Regional Chapter",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Available chapters
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ('Chapter Name', 'Location', 'Coordinator', 'Members', 'Status')
        self.join_chapters_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.join_chapters_tree.heading(col, text=col)
            self.join_chapters_tree.column(col, width=150)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                    command=self.join_chapters_tree.yview)
        self.join_chapters_tree.configure(yscrollcommand=scrollbar_y.set)

        self.join_chapters_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load available chapters (not already joined)
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                query = """
                    SELECT rc.chapter_id, rc.chapter_name, rc.location,
                           rc.coordinator_name, rc.member_count, rc.status
                    FROM regional_chapters rc
                    WHERE rc.status = 'active'
                    AND rc.chapter_id NOT IN (
                        SELECT chapter_id FROM chapter_members WHERE member_id = ?
                    )
                    ORDER BY rc.chapter_name
                """
                cursor.execute(query, (user_id,))
                chapters = cursor.fetchall()

                for chapter in chapters:
                    # Display without chapter_id
                    self.join_chapters_tree.insert('', tk.END, values=chapter[1:])

                self.update_status(f"Found {len(chapters)} available chapter(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load chapters: {str(e)}")

        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)

        ttk.Button(button_frame, text="Join Selected Chapter",
                  command=self._join_selected_chapter).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self.join_regional_chapter).pack(side=tk.LEFT)

    def _join_selected_chapter(self):
        """Join the selected chapter"""
        if not hasattr(self, 'join_chapters_tree'):
            return

        selection = self.join_chapters_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a chapter to join.")
            return

        item = self.join_chapters_tree.item(selection[0])
        chapter_data = item['values']
        chapter_name = chapter_data[0]

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                # Get chapter_id
                cursor.execute("SELECT chapter_id FROM regional_chapters WHERE chapter_name = ?",
                             (chapter_name,))
                result = cursor.fetchone()

                if result:
                    chapter_id = result[0]

                    # Join chapter
                    cursor.execute("""
                        INSERT INTO chapter_members (chapter_id, member_id, role, join_date, status)
                        VALUES (?, ?, 'member', datetime('now'), 'active')
                    """, (chapter_id, user_id))

                    # Update member count
                    cursor.execute("""
                        UPDATE regional_chapters
                        SET member_count = member_count + 1
                        WHERE chapter_id = ?
                    """, (chapter_id,))

                    conn.commit()

                    messagebox.showinfo("Success", f"You have joined {chapter_name}!")
                    self.join_regional_chapter()  # Refresh

                    # Log activity
                    from university_system.modules.shared.utils.activity_logger import log_activity
                    log_activity('create', 'chapter_membership',
                               details={'chapter': chapter_name, 'action': 'joined'})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to join chapter: {str(e)}")

    def create_regional_chapter(self):
        """Create a new regional chapter"""
        self.clear_content()
        self.update_status("Create Regional Chapter")

        ttk.Label(self.content_frame, text="Create a New Regional Chapter",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.LabelFrame(self.content_frame, text="Chapter Details", padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Form fields
        self.new_chapter_vars = {}

        fields = [
            ("Chapter Name*", "name"),
            ("Location*", "location"),
            ("Coordinator Name", "coordinator"),
            ("Contact Email", "email")
        ]

        for label, var_name in fields:
            field_frame = ttk.Frame(form_frame)
            field_frame.pack(fill=tk.X, pady=5)

            ttk.Label(field_frame, text=label, width=18).pack(side=tk.LEFT, padx=(0, 10))
            self.new_chapter_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.new_chapter_vars[var_name]).pack(
                side=tk.LEFT, fill=tk.X, expand=True)

        # Description
        ttk.Label(form_frame, text="Chapter Description:").pack(anchor='w', pady=(10, 5))
        self.new_chapter_description = ScrolledText(form_frame, height=5, wrap=tk.WORD)
        self.new_chapter_description.pack(fill=tk.X)

        # Action buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text="Create Chapter",
                  command=self._submit_new_chapter).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Clear Form",
                  command=self._clear_chapter_form).pack(side=tk.LEFT)

    def _submit_new_chapter(self):
        """Submit new chapter creation"""
        # Validation
        if not self.new_chapter_vars['name'].get().strip():
            messagebox.showerror("Validation Error", "Chapter name is required!")
            return

        if not self.new_chapter_vars['location'].get().strip():
            messagebox.showerror("Validation Error", "Location is required!")
            return

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                # Insert chapter
                cursor.execute("""
                    INSERT INTO regional_chapters (
                        chapter_name, location, coordinator_name, contact_email,
                        description, created_date, created_by, status, member_count
                    ) VALUES (?, ?, ?, ?, ?, datetime('now'), ?, 'active', 0)
                """, (
                    self.new_chapter_vars['name'].get(),
                    self.new_chapter_vars['location'].get(),
                    self.new_chapter_vars['coordinator'].get() or user_id,
                    self.new_chapter_vars['email'].get(),
                    self.new_chapter_description.get(1.0, tk.END).strip(),
                    user_id
                ))

                chapter_id = cursor.lastrowid

                # Auto-join the creator
                cursor.execute("""
                    INSERT INTO chapter_members (chapter_id, member_id, role, join_date, status)
                    VALUES (?, ?, 'coordinator', datetime('now'), 'active')
                """, (chapter_id, user_id))

                # Update member count
                cursor.execute("""
                    UPDATE regional_chapters
                    SET member_count = 1
                    WHERE chapter_id = ?
                """, (chapter_id,))

                conn.commit()

            messagebox.showinfo("Success", "Regional chapter created successfully!")
            self.update_status("Chapter created")
            self._clear_chapter_form()

            # Log activity
            from university_system.modules.shared.utils.activity_logger import log_activity
            log_activity('create', 'chapter', chapter_id=chapter_id,
                       details={'name': self.new_chapter_vars['name'].get()})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create chapter: {str(e)}")

    def _clear_chapter_form(self):
        """Clear chapter creation form"""
        for var in self.new_chapter_vars.values():
            var.set("")
        self.new_chapter_description.delete(1.0, tk.END)


    # Career Services Methods
    def show_job_board(self):
        """Show job board interface"""
        self.clear_content()
        self.update_status("Job Board")
        
        ttk.Label(self.content_frame, text="Alumni Job Board", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Search and filter
        search_frame = ttk.Frame(self.content_frame)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 10))
        self.job_search = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.job_search, width=20).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(search_frame, text="Category:").pack(side=tk.LEFT, padx=(10, 5))
        self.job_category = tk.StringVar()
        category_combo = ttk.Combobox(search_frame, textvariable=self.job_category,
                                     values=["All", "Technology", "Finance", "Healthcare", "Education", "Marketing"])
        category_combo.pack(side=tk.LEFT, padx=(0, 10))
        category_combo.set("All")
        
        ttk.Button(search_frame, text="Search Jobs", 
                  command=self.search_jobs).pack(side=tk.LEFT)
        
        # Job listings
        self.job_text = ScrolledText(self.content_frame, wrap=tk.WORD)
        self.job_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Load job listings
        self.load_job_listings()
        
        # Action buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, padx=20)
        
        if self.has_permission('post_jobs'):
            ttk.Button(button_frame, text="Post New Job", 
                      command=self.show_post_job).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="Refresh Listings", 
                  command=self.load_job_listings).pack(side=tk.LEFT)
    
    def load_job_listings(self):
        """Load job listings into the text widget"""
        self.job_text.delete(1.0, tk.END)
        
        job_content = """Current Job Opportunities:

💼 Senior Software Developer
Company: Tech Innovations Inc.
Posted by: Sarah Johnson (Class of 2015)
Location: San Francisco, CA (Remote available)
Type: Full-time | Experience: Mid-Senior Level
Salary: $120,000 - $150,000

Description: Join our growing team developing cutting-edge web applications. 
Looking for experienced developers with React, Node.js, and cloud experience.

Requirements:
• 3+ years software development experience
• Strong JavaScript, React, Node.js skills
• Experience with AWS or similar cloud platforms
• Bachelor's degree in Computer Science or related field

Contact: careers@techinnovations.com
Posted: August 10, 2025 | Expires: September 10, 2025

[Apply Now] [Save Job] [Contact Poster]

---

💼 Financial Analyst
Company: Finance Plus Corp
Posted by: Michael Chen (Class of 2018)
Location: New York, NY
Type: Full-time | Experience: Entry-Mid Level  
Salary: $70,000 - $90,000

Description: Seeking detail-oriented financial analyst to join our investment team.
Great opportunity for recent graduates or career changers.

Requirements:
• Bachelor's degree in Finance, Economics, or related field
• Strong analytical and Excel skills
• CFA Level 1 preferred but not required
• Excellent communication skills

Contact: hiring@financeplus.com
Posted: August 8, 2025 | Expires: September 8, 2025

[Apply Now] [Save Job] [Contact Poster]

---

💼 Marketing Manager
Company: Creative Solutions LLC
Posted by: Lisa Brown (Class of 2016)
Location: Boston, MA (Hybrid)
Type: Full-time | Experience: Mid Level
Salary: $80,000 - $100,000

Description: Lead marketing initiatives for B2B software company. 
Manage campaigns, content strategy, and team development.

Requirements:
• 3-5 years marketing experience
• Experience with digital marketing platforms
• Strong project management skills
• MBA preferred

Contact: jobs@creativesolutions.com
Posted: August 5, 2025 | Expires: September 5, 2025

[Apply Now] [Save Job] [Contact Poster]
"""
        self.job_text.insert(tk.END, job_content)
    
    def search_jobs(self):
        """Search jobs based on criteria"""
        search_term = self.job_search.get()
        category = self.job_category.get()
        
        # For demo, just show search message
        if search_term or category != "All":
            self.job_text.delete(1.0, tk.END)
            self.job_text.insert(tk.END, f"Searching for jobs...\n")
            self.job_text.insert(tk.END, f"Search term: {search_term}\n")
            self.job_text.insert(tk.END, f"Category: {category}\n\n")
            self.load_job_listings()  # Then show all jobs for demo
        else:
            self.load_job_listings()
    
    def show_post_job(self):
        """Show post job interface"""
        self.clear_content()
        self.update_status("Post Job Opportunity")
        
        ttk.Label(self.content_frame, text="Post Job Opportunity", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Create scrollable form
        canvas = tk.Canvas(self.content_frame)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Job form
        self.job_vars = {}
        
        # Company info
        company_frame = ttk.LabelFrame(scrollable_frame, text="Company Information", padding=10)
        company_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        company_fields = [
            ("Company Name*", "company_name"),
            ("Industry*", "industry"),
            ("Company Website", "website"),
            ("Contact Email*", "contact_email")
        ]
        
        for i, (label, var_name) in enumerate(company_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(company_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=label).pack(anchor='w')
            self.job_vars[var_name] = tk.StringVar()
            ttk.Entry(field_frame, textvariable=self.job_vars[var_name]).pack(fill=tk.X)
        
        company_frame.columnconfigure(0, weight=1)
        company_frame.columnconfigure(1, weight=1)
        
        # Job details
        job_frame = ttk.LabelFrame(scrollable_frame, text="Job Details", padding=10)
        job_frame.pack(fill=tk.X, pady=(0, 10), padx=20)
        
        job_fields = [
            ("Job Title*", "job_title"),
            ("Location*", "location"),
            ("Job Type*", "job_type"),
            ("Experience Level*", "experience_level")
        ]
        
        for i, (label, var_name) in enumerate(job_fields):
            row = i // 2
            col = i % 2
            
            field_frame = ttk.Frame(job_frame)
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(field_frame, text=label).pack(anchor='w')
            
            if var_name == "job_type":
                self.job_vars[var_name] = tk.StringVar()
                combo = ttk.Combobox(field_frame, textvariable=self.job_vars[var_name],
                                   values=["Full-time", "Part-time", "Contract", "Internship", "Remote"])
                combo.pack(fill=tk.X)
            elif var_name == "experience_level":
                self.job_vars[var_name] = tk.StringVar()
                combo = ttk.Combobox(field_frame, textvariable=self.job_vars[var_name],
                                   values=["Entry Level", "Mid Level", "Senior Level", "Executive"])
                combo.pack(fill=tk.X)
            else:
                self.job_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.job_vars[var_name]).pack(fill=tk.X)
        
        job_frame.columnconfigure(0, weight=1)
        job_frame.columnconfigure(1, weight=1)
        
        # Salary range
        salary_frame = ttk.Frame(job_frame)
        salary_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky='ew')
        
        ttk.Label(salary_frame, text="Salary Range (optional)").pack(anchor='w')
        self.job_vars['salary_range'] = tk.StringVar()
        ttk.Entry(salary_frame, textvariable=self.job_vars['salary_range']).pack(fill=tk.X)
        
        # Job description
        desc_frame = ttk.LabelFrame(scrollable_frame, text="Job Description", padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=20)
        
        ttk.Label(desc_frame, text="Job Description*:").pack(anchor='w')
        self.job_description = ScrolledText(desc_frame, height=6, wrap=tk.WORD)
        self.job_description.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        ttk.Label(desc_frame, text="Requirements*:").pack(anchor='w')
        self.job_requirements = ScrolledText(desc_frame, height=4, wrap=tk.WORD)
        self.job_requirements.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=20, padx=20)
        
        ttk.Button(button_frame, text="Post Job", 
                  command=self.submit_job_posting).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Clear Form", 
                  command=self.clear_job_form).pack(side=tk.RIGHT)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def submit_job_posting(self):
        """Submit job posting"""
        required_fields = ['company_name', 'industry', 'contact_email', 'job_title', 'location', 'job_type', 'experience_level']
        for field in required_fields:
            if not self.job_vars[field].get().strip():
                messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                return
        
        description = self.job_description.get(1.0, tk.END).strip()
        requirements = self.job_requirements.get(1.0, tk.END).strip()
        
        if not description:
            messagebox.showerror("Validation Error", "Job description is required!")
            return
        
        if not requirements:
            messagebox.showerror("Validation Error", "Job requirements are required!")
            return
        
        messagebox.showinfo("Job Posted", "Job opportunity posted successfully!")
        self.update_status("Job posting submitted")
        self.clear_job_form()
    
    def clear_job_form(self):
        """Clear job posting form"""
        for var in self.job_vars.values():
            var.set("")
        self.job_description.delete(1.0, tk.END)
        self.job_requirements.delete(1.0, tk.END)

    def view_job_details(self):
        """View details for a specific job posting"""
        # Create job selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Job to View")
        dialog.geometry("700x500")
        dialog.configure(bg='white')
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Select a Job Posting",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Job listings table
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        columns = ('Title', 'Company', 'Location', 'Type', 'Salary')
        job_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            job_tree.heading(col, text=col)
            job_tree.column(col, width=130)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=job_tree.yview)
        job_tree.configure(yscrollcommand=scrollbar_y.set)

        job_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Load job listings
        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT job_id, job_title, company_name, location, job_type, salary_range
                    FROM job_postings
                    WHERE status = 'active' AND expiry_date > datetime('now')
                    ORDER BY posted_date DESC
                """)
                jobs = cursor.fetchall()

                for job in jobs:
                    job_tree.insert('', tk.END, values=job[1:])

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load jobs: {str(e)}")

        def show_selected_job():
            selection = job_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a job to view.")
                return

            item = job_tree.item(selection[0])
            job_data = item['values']
            self._display_job_detail_window(job_data)
            dialog.destroy()

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="View Details",
                  command=show_selected_job).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel",
                  command=dialog.destroy).pack(side=tk.LEFT)

    def _display_job_detail_window(self, job_data):
        """Display detailed job information window"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Job Details - {job_data[0]}")
        detail_window.geometry("700x600")
        detail_window.configure(bg='white')

        # Main frame
        main_frame = ttk.Frame(detail_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Job title
        ttk.Label(main_frame, text=job_data[0],
                 font=('Arial', 16, 'bold')).pack(pady=(0, 10))

        # Company info
        company_frame = ttk.LabelFrame(main_frame, text="Company Information", padding=10)
        company_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(company_frame, text=f"Company: {job_data[1]}",
                 font=('Arial', 11)).pack(anchor='w')
        ttk.Label(company_frame, text=f"Location: {job_data[2]}",
                 font=('Arial', 11)).pack(anchor='w')

        # Job details
        details_frame = ttk.LabelFrame(main_frame, text="Job Details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(details_frame, text=f"Job Type: {job_data[3]}",
                 font=('Arial', 11)).pack(anchor='w')
        ttk.Label(details_frame, text=f"Salary Range: {job_data[4]}",
                 font=('Arial', 11)).pack(anchor='w')

        # Description
        desc_frame = ttk.LabelFrame(main_frame, text="Job Description", padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        desc_text = ScrolledText(desc_frame, wrap=tk.WORD, height=8)
        desc_text.pack(fill=tk.BOTH, expand=True)

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT description, requirements, contact_email
                    FROM job_postings
                    WHERE job_title = ? AND company_name = ?
                """, (job_data[0], job_data[1]))
                result = cursor.fetchone()

                if result:
                    desc_text.insert(tk.END, f"{result[0]}\n\nRequirements:\n{result[1]}\n\nContact: {result[2]}")
                else:
                    desc_text.insert(tk.END, "Job description not available.")
        except:
            desc_text.insert(tk.END, "Job description not available.")

        desc_text.config(state='disabled')

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Express Interest",
                  command=lambda: self._record_interest_from_detail(job_data[0], job_data[1], detail_window)).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Close",
                  command=detail_window.destroy).pack(side=tk.LEFT)

    def _record_interest_from_detail(self, job_title, company_name, window):
        """Record interest from job detail window"""
        try:
            self.record_job_interest(job_title, company_name)
            messagebox.showinfo("Success", "Your interest has been recorded!")
            window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to record interest: {str(e)}")

    def record_job_interest(self, job_title=None, company_name=None):
        """Record user's interest in a job posting"""
        if not job_title or not company_name:
            # Show job selection dialog
            messagebox.showinfo("Info", "Please use 'View Job Details' to express interest in a job.")
            return

        try:
            with db_get_connection() as conn:
                cursor = conn.cursor()
                user_id = self._current_user_id()

                # Get job_id
                cursor.execute("""
                    SELECT job_id FROM job_postings
                    WHERE job_title = ? AND company_name = ?
                """, (job_title, company_name))
                result = cursor.fetchone()

                if not result:
                    raise ValueError("Job posting not found")

                job_id = result[0]

                # Check if already expressed interest
                cursor.execute("""
                    SELECT interest_id FROM job_interests
                    WHERE job_id = ? AND user_id = ?
                """, (job_id, user_id))

                if cursor.fetchone():
                    messagebox.showinfo("Already Interested",
                                      "You have already expressed interest in this job.")
                    return

                # Record interest
                cursor.execute("""
                    INSERT INTO job_interests (job_id, user_id, expressed_date, status)
                    VALUES (?, ?, datetime('now'), 'interested')
                """, (job_id, user_id))

                # Update job interest count
                cursor.execute("""
                    UPDATE job_postings
                    SET interest_count = interest_count + 1
                    WHERE job_id = ?
                """, (job_id,))

                conn.commit()
                self.update_status("Job interest recorded")

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('create', 'job_interest', interest_id=cursor.lastrowid,
                           details={'job_id': job_id, 'job_title': job_title, 'company': company_name})

        except Exception as e:
            raise Exception(f"Failed to record job interest: {str(e)}")

    def show_career_counseling(self):
        """Show career counseling interface"""
        self.clear_content()
        self.update_status("Career Counseling")
        
        ttk.Label(self.content_frame, text="Career Counseling Services", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Tabs for different counseling views
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Available counselors tab
        counselors_frame = ttk.Frame(notebook)
        notebook.add(counselors_frame, text="Available Counselors")
        
        counselors_text = ScrolledText(counselors_frame, wrap=tk.WORD)
        counselors_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        counselors_content = """Available Career Counselors:

👩‍💼 Sarah Johnson (Class of 2015)
Title: Senior Developer & Tech Entrepreneur
Company: Tech Innovations Inc.
Specialties: Software Development, Startup Leadership, Career Transitions
Experience: 8+ years in technology industry
Available: Weekday evenings, weekends

Bio: Sarah has successfully transitioned from software developer to startup founder. 
She specializes in helping alumni navigate tech careers and entrepreneurship.

[Schedule Session] [View Full Profile]

---

👨‍💼 Michael Chen (Class of 2018)
Title: Financial Analyst & Investment Advisor  
Company: Finance Plus Corp
Specialties: Finance, Investment Banking, Career Planning
Experience: 5+ years in financial services
Available: Weekday afternoons, Saturday mornings

Bio: Michael provides guidance on finance careers, industry transitions, 
and professional development in the financial sector.

[Schedule Session] [View Full Profile]

---

👩‍💼 Dr. Lisa Martinez (Class of 2012)
Title: Healthcare Administrator & Physician
Company: Regional Medical Center
Specialties: Healthcare Careers, Work-Life Balance, Leadership
Experience: 10+ years in healthcare
Available: Weekend afternoons

Bio: Dr. Martinez helps alumni explore healthcare careers and develop 
leadership skills in medical and administrative roles.

[Schedule Session] [View Full Profile]
"""
        counselors_text.insert(tk.END, counselors_content)
        
        # Schedule session tab
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="Schedule Session")
        
        self.create_counseling_form(schedule_frame)
    
    def create_counseling_form(self, parent):
        """Create career counseling scheduling form"""
        ttk.Label(parent, text="Schedule Career Counseling Session", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 20))
        
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Counselor selection
        self.counseling_vars = {}
        
        counselor_frame = ttk.Frame(form_frame)
        counselor_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(counselor_frame, text="Select Counselor:").pack(side=tk.LEFT, padx=(0, 10))
        self.counseling_vars['counselor'] = tk.StringVar()
        counselor_combo = ttk.Combobox(counselor_frame, textvariable=self.counseling_vars['counselor'],
                                      values=["Sarah Johnson - Tech Careers", "Michael Chen - Finance", "Dr. Lisa Martinez - Healthcare"])
        counselor_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Session type
        type_frame = ttk.Frame(form_frame)
        type_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(type_frame, text="Session Type:").pack(side=tk.LEFT, padx=(0, 10))
        self.counseling_vars['session_type'] = tk.StringVar()
        type_combo = ttk.Combobox(type_frame, textvariable=self.counseling_vars['session_type'],
                                 values=["Career Planning", "Resume Review", "Interview Preparation", "Industry Insights", "Networking Advice"])
        type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Preferred date/time
        datetime_frame = ttk.Frame(form_frame)
        datetime_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(datetime_frame, text="Preferred Date & Time:").pack(anchor='w')
        self.counseling_vars['datetime'] = tk.StringVar()
        ttk.Entry(datetime_frame, textvariable=self.counseling_vars['datetime'], 
                 placeholder_text="YYYY-MM-DD HH:MM").pack(fill=tk.X, pady=(5, 0))
        
        # Duration
        duration_frame = ttk.Frame(form_frame)
        duration_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(duration_frame, text="Duration (minutes):").pack(side=tk.LEFT, padx=(0, 10))
        self.counseling_vars['duration'] = tk.StringVar(value="60")
        duration_combo = ttk.Combobox(duration_frame, textvariable=self.counseling_vars['duration'],
                                     values=["30", "60", "90"])
        duration_combo.pack(side=tk.LEFT)
        
        # Notes
        ttk.Label(form_frame, text="Additional Notes or Specific Topics:").pack(anchor='w', pady=(10, 5))
        self.counseling_notes = ScrolledText(form_frame, height=4, wrap=tk.WORD)
        self.counseling_notes.pack(fill=tk.X)
        
        # Submit button
        ttk.Button(form_frame, text="Schedule Session", 
                  command=self.submit_counseling_request).pack(pady=20)
    
    def submit_counseling_request(self):
        """Submit counseling session request"""
        if not self.counseling_vars['counselor'].get():
            messagebox.showerror("Validation Error", "Please select a counselor!")
            return
        
        if not self.counseling_vars['session_type'].get():
            messagebox.showerror("Validation Error", "Please select a session type!")
            return
        
        if not self.counseling_vars['datetime'].get():
            messagebox.showerror("Validation Error", "Please enter preferred date and time!")
            return
        
        messagebox.showinfo("Session Scheduled", "Career counseling session request submitted successfully!")
        self.update_status("Counseling session requested")
        
        # Clear form
        for var in self.counseling_vars.values():
            var.set("")
        self.counseling_notes.delete(1.0, tk.END)
    
    # Donations and Fundraising Methods
    def show_record_donation(self):
        """Show donation recording interface"""
        self.clear_content()
        self.update_status("Record Donation")
        
        ttk.Label(self.content_frame, text="Record Alumni Donation", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Donation form
        form_frame = ttk.LabelFrame(self.content_frame, text="Donation Details", padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.donation_vars = {}
        
        # Donor information
        donor_frame = ttk.Frame(form_frame)
        donor_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(donor_frame, text="Alumni ID:").pack(side=tk.LEFT, padx=(0, 10))
        self.donation_vars['alumni_id'] = tk.StringVar()
        ttk.Entry(donor_frame, textvariable=self.donation_vars['alumni_id'], width=15).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(donor_frame, text="Lookup Alumni", 
                  command=self.lookup_donor).pack(side=tk.LEFT)
        
        # Donation amount
        amount_frame = ttk.Frame(form_frame)
        amount_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(amount_frame, text="Donation Amount ($):").pack(side=tk.LEFT, padx=(0, 10))
        self.donation_vars['amount'] = tk.StringVar()
        ttk.Entry(amount_frame, textvariable=self.donation_vars['amount'], width=15).pack(side=tk.LEFT)
        
        # Campaign selection
        campaign_frame = ttk.Frame(form_frame)
        campaign_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(campaign_frame, text="Campaign:").pack(side=tk.LEFT, padx=(0, 10))
        self.donation_vars['campaign'] = tk.StringVar()
        campaign_combo = ttk.Combobox(campaign_frame, textvariable=self.donation_vars['campaign'],
                                     values=["Annual Alumni Fund", "Scholarship Fund", "Building Fund", "General Fund"])
        campaign_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Payment method
        payment_frame = ttk.Frame(form_frame)
        payment_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(payment_frame, text="Payment Method:").pack(side=tk.LEFT, padx=(0, 10))
        self.donation_vars['payment_method'] = tk.StringVar()
        payment_combo = ttk.Combobox(payment_frame, textvariable=self.donation_vars['payment_method'],
                                    values=["Credit Card", "Check", "Bank Transfer", "Cash", "Online"])
        payment_combo.pack(side=tk.LEFT)
        
        # Recurring donation
        recurring_frame = ttk.Frame(form_frame)
        recurring_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.donation_vars['is_recurring'] = tk.BooleanVar()
        ttk.Checkbutton(recurring_frame, text="Recurring Donation", 
                       variable=self.donation_vars['is_recurring']).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(recurring_frame, text="Frequency:").pack(side=tk.LEFT, padx=(0, 10))
        self.donation_vars['frequency'] = tk.StringVar()
        freq_combo = ttk.Combobox(recurring_frame, textvariable=self.donation_vars['frequency'],
                                 values=["Monthly", "Quarterly", "Annually"])
        freq_combo.pack(side=tk.LEFT)
        
        # Notes
        ttk.Label(form_frame, text="Notes:").pack(anchor='w', pady=(10, 5))
        self.donation_notes = ScrolledText(form_frame, height=4, wrap=tk.WORD)
        self.donation_notes.pack(fill=tk.X)
        
        # Submit button
        ttk.Button(form_frame, text="Record Donation", 
                  command=self.submit_donation).pack(pady=20)
    
    def lookup_donor(self):
        """Lookup donor information"""
        alumni_id = self.donation_vars['alumni_id'].get().strip()
        if not alumni_id:
            messagebox.showwarning("No Alumni ID", "Please enter an Alumni ID to lookup.")
            return
        
        # Simulate lookup
        messagebox.showinfo("Alumni Found", f"Alumni {alumni_id}: John Doe (Class of 2018)")
    
    def submit_donation(self):
        """Submit donation record"""
        if not self.donation_vars['alumni_id'].get().strip():
            messagebox.showerror("Validation Error", "Alumni ID is required!")
            return
        
        if not self.donation_vars['amount'].get().strip():
            messagebox.showerror("Validation Error", "Donation amount is required!")
            return
        
        try:
            amount = float(self.donation_vars['amount'].get())
            if amount <= 0:
                messagebox.showerror("Validation Error", "Donation amount must be greater than zero!")
                return
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid donation amount!")
            return
        
        messagebox.showinfo("Donation Recorded", "Donation recorded successfully!")
        self.update_status("Donation record submitted")
        
        # Clear form
        for var in self.donation_vars.values():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            else:
                var.set("")
        self.donation_notes.delete(1.0, tk.END)
    
    def show_view_donations(self):
        """Show donations viewer"""
        self.clear_content()
        self.update_status("View Donations")
        
        ttk.Label(self.content_frame, text="Alumni Donations", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Filter and search
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filter by:").pack(side=tk.LEFT, padx=(0, 10))
        
        # Date range
        ttk.Label(filter_frame, text="From:").pack(side=tk.LEFT, padx=(0, 5))
        self.donation_from_date = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.donation_from_date, width=10).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(filter_frame, text="To:").pack(side=tk.LEFT, padx=(0, 5))
        self.donation_to_date = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.donation_to_date, width=10).pack(side=tk.LEFT, padx=(0, 10))
        
        # Campaign filter
        ttk.Label(filter_frame, text="Campaign:").pack(side=tk.LEFT, padx=(0, 5))
        self.donation_campaign_filter = tk.StringVar()
        campaign_filter_combo = ttk.Combobox(filter_frame, textvariable=self.donation_campaign_filter,
                                           values=["All", "Annual Fund", "Scholarship Fund", "Building Fund"])
        campaign_filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        campaign_filter_combo.set("All")
        
        ttk.Button(filter_frame, text="Apply Filter", 
                  command=self.filter_donations).pack(side=tk.LEFT)
        
        # Donations table
        table_frame = ttk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        columns = ('Date', 'Alumni Name', 'Alumni ID', 'Amount', 'Campaign', 'Payment Method', 'Status')
        self.donations_tree = ttk.Treeview(table_frame, columns=columns, show='headings')
        
        for col in columns:
            self.donations_tree.heading(col, text=col)
            self.donations_tree.column(col, width=100)
        
        # Scrollbars
        donations_scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.donations_tree.yview)
        self.donations_tree.configure(yscrollcommand=donations_scrollbar_y.set)
        
        donations_scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.donations_tree.xview)
        self.donations_tree.configure(xscrollcommand=donations_scrollbar_x.set)
        
        self.donations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        donations_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load donations data
        self.load_donations_data()
        
        # Summary
        summary_frame = ttk.LabelFrame(self.content_frame, text="Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=20)
        
        self.donation_summary = tk.StringVar()
        ttk.Label(summary_frame, textvariable=self.donation_summary).pack()
        self.update_donation_summary()

    # ==================== INTEGRATION METHODS ====================

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email via email manager GUI"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI
            email_gui = EmailManagerGUI(self.root, auth=self.auth)
            if hasattr(email_gui, 'send_email'):
                email_gui.send_email(to_email=to_email, subject=subject, message=message)
                return True
            return False
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_email_fallback_dialog(self, to_email, subject, message):
        """Show email dialog as fallback when email system unavailable"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Email Notification")
        dialog.geometry("500x400")
        dialog.configure(bg='white')
        dialog.grab_set()

        tk.Label(dialog, text="Email Notification", font=('Arial', 14, 'bold'),
                bg='white', fg='#2c3e50').pack(pady=10)

        info_frame = tk.Frame(dialog, bg='white')
        info_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(info_frame, text=f"To: {to_email}", font=('Arial', 11),
                bg='white', fg='#34495e').pack(anchor='w')
        tk.Label(info_frame, text=f"Subject: {subject}", font=('Arial', 11),
                bg='white', fg='#34495e').pack(anchor='w')

        tk.Label(dialog, text="Message:", font=('Arial', 11, 'bold'),
                bg='white', fg='#2c3e50').pack(anchor='w', padx=20, pady=(10, 5))

        message_text = tk.Text(dialog, height=10, wrap='word', font=('Arial', 10))
        message_text.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        message_text.insert('1.0', message)
        message_text.config(state='disabled')

        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg='#6c757d', fg='white', font=('Arial', 10),
                 padx=20, pady=5, relief='flat').pack(pady=10)

    def send_alumni_registration_confirmation(self, alumni_email, alumni_name):
        """Send confirmation email for alumni registration"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'student_name': alumni_name,
            'email': alumni_email,
            'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        subject, message = render_template('alumni_registration_confirmation', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_profile_update_confirmation(self, alumni_email, alumni_name, update_details):
        """Send confirmation email for profile updates"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'student_name': alumni_name,
            'updated_fields': update_details,
            'updated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        subject, message = render_template('profile_update_confirmation', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_profile_deletion_confirmation(self, alumni_email, alumni_name):
        """Send confirmation email for profile deletion"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'student_name': alumni_name,
            'deletion_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        subject, message = render_template('profile_deletion_confirmation', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_event_registration_confirmation(self, alumni_email, alumni_name, event_name, event_date):
        """Send confirmation email for event registration via student union"""
        template_vars = {
            'student_name': alumni_name,
            'event_name': event_name,
            'event_date': event_date
        }

        subject, message = render_template('event_registration_confirmation', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_club_registration_confirmation(self, alumni_email, alumni_name, club_name):
        """Send confirmation email for club registration via student union"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'student_name': alumni_name,
            'club_name': club_name
        }

        subject, message = render_template('club_join_confirmation', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_trip_registration_confirmation(self, alumni_email, alumni_name, trip_name, trip_date):
        """Send confirmation email for trip registration via student union"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'student_name': alumni_name,
            'trip_name': trip_name,
            'trip_date': trip_date
        }

        subject, message = render_template('trip_announcement', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_course_registration_confirmation(self, alumni_email, alumni_name, course_name, course_code):
        """Send confirmation email for course registration"""
        template_vars = {
            'student_name': alumni_name,
            'course_name': course_name,
            'course_code': course_code,
            'start_date': 'TBD'
        }

        subject, message = render_template('course_registration_confirmation', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_module_registration_confirmation(self, alumni_email, alumni_name, module_name, module_code):
        """Send confirmation email for module registration"""
        template_vars = {
            'student_name': alumni_name,
            'module_name': module_name,
            'module_code': module_code
        }

        subject, message = render_template('module_registration_confirmation', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_payment_confirmation(self, alumni_email, alumni_name, amount, payment_description):
        """Send confirmation email for payments"""
        payment_reference = f"PAY-{datetime.now().strftime('%Y%m%d')}-{alumni_name.replace(' ', '').upper()[:4]}"

        template_vars = {
            'student_name': alumni_name,
            'amount': amount,
            'payment_description': payment_description,
            'payment_reference': payment_reference
        }

        subject, message = render_template('payment_confirmation', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def send_invoice_receipt(self, alumni_email, alumni_name, invoice_data):
        """Send detailed invoice/receipt via email"""
        items_list = ""
        total_amount = 0
        for item in invoice_data.get('items', []):
            items_list += f"- {item['description']}: ${item['amount']}\n"
            total_amount += float(item['amount'])

        template_vars = {
            'student_name': alumni_name,
            'invoice_number': invoice_data.get('invoice_number', 'N/A'),
            'due_date': invoice_data.get('due_date', 'N/A'),
            'items_list': items_list,
            'total_amount': f"{total_amount:.2f}",
            'payment_status': invoice_data.get('status', 'Paid')
        }

        subject, message = render_template('invoice_receipt', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(alumni_email, subject, message):
            self._show_email_fallback_dialog(alumni_email, subject, message)

    def validate_student_record(self, student_id, email):
        """Validate if user is a valid student in the database"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Check if student exists in students table
            cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name, s.email, s.graduation_date
                FROM students s
                WHERE s.student_id = ? OR s.email = ?
            ''', (student_id, email))

            student_record = cursor.fetchone()
            conn.close()

            if student_record:
                return {
                    'valid': True,
                    'student_id': student_record[0],
                    'name': f"{student_record[1]} {student_record[2]}",
                    'email': student_record[3],
                    'graduation_date': student_record[4]
                }
            else:
                return {'valid': False, 'error': 'Student record not found'}

        except Exception as e:
            return {'valid': False, 'error': f'Database error: {e}'}

    def check_finance_status(self, student_id, alumni_email):
        """Check if alumni owes money to the university"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Check outstanding balances
            cursor.execute('''
                SELECT
                    SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END) as pending_amount,
                    SUM(CASE WHEN status = 'overdue' THEN amount ELSE 0 END) as overdue_amount
                FROM financial_records
                WHERE student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            conn.close()

            pending_amount = result[0] if result[0] else 0
            overdue_amount = result[1] if result[1] else 0
            total_owed = pending_amount + overdue_amount

            return {
                'has_debt': total_owed > 0,
                'pending_amount': pending_amount,
                'overdue_amount': overdue_amount,
                'total_owed': total_owed
            }

        except Exception as e:
            print(f"Error checking finance status: {e}")
            return {'has_debt': False, 'error': f'Could not check finance status: {e}'}

    def show_finance_status_dialog(self, finance_status, alumni_name):
        """Show dialog with finance status information"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Finance Status")
        dialog.geometry("400x300")
        dialog.configure(bg='white')
        dialog.grab_set()

        if finance_status['has_debt']:
            # Show debt information
            tk.Label(dialog, text="Outstanding Balance", font=('Arial', 14, 'bold'),
                    bg='white', fg='#e74c3c').pack(pady=10)

            info_frame = tk.Frame(dialog, bg='white')
            info_frame.pack(fill='x', padx=20, pady=10)

            tk.Label(info_frame, text=f"Pending Amount: ${finance_status['pending_amount']:.2f}",
                    font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w')
            tk.Label(info_frame, text=f"Overdue Amount: ${finance_status['overdue_amount']:.2f}",
                    font=('Arial', 11), bg='white', fg='#e74c3c').pack(anchor='w')
            tk.Label(info_frame, text=f"Total Owed: ${finance_status['total_owed']:.2f}",
                    font=('Arial', 12, 'bold'), bg='white', fg='#e74c3c').pack(anchor='w', pady=(5, 0))

            tk.Button(dialog, text="Open Finance System",
                     command=lambda: self.open_finance_gui(),
                     bg='#27ae60', fg='white', font=('Arial', 11),
                     padx=20, pady=8, relief='flat').pack(pady=10)
        else:
            # No debt
            tk.Label(dialog, text="Finance Status: Clear", font=('Arial', 14, 'bold'),
                    bg='white', fg='#27ae60').pack(pady=20)
            tk.Label(dialog, text="No outstanding balance found.",
                    font=('Arial', 11), bg='white', fg='#34495e').pack(pady=10)

        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg='#6c757d', fg='white', font=('Arial', 10),
                 padx=20, pady=5, relief='flat').pack(pady=10)

    def open_finance_gui(self):
        """Open finance management GUI"""
        try:
            from university_system.modules.domain.finance.gui.finance import FinanceGUI
            finance_window = tk.Toplevel(self.root)
            finance_window.title("Finance Management")
            finance_window.geometry("1000x700")
            finance_gui = FinanceGUI(finance_window, auth=self.auth)
        except ImportError:
            messagebox.showerror("Error", "Finance GUI not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Finance GUI: {e}")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def open_email_manager_gui(self):
        """Open email manager GUI"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI
            email_window = tk.Toplevel(self.root)
            email_window.title("Email Manager")
            email_window.geometry("800x600")
            email_gui = EmailManagerGUI(email_window, auth=self.auth)
        except ImportError:
            messagebox.showerror("Error", "Email Manager GUI not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Email Manager: {e}")

def main(auth=None):
    """Main function to run the Alumni Management GUI application"""
    try:
        # Create the main window
        root = tk.Tk()

        # Set window properties
        root.title("Enhanced Alumni Management System")
        root.geometry("1400x900")
        root.minsize(1200, 800)

        # Center the window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        # Create the application instance with authentication
        app = AlumniGUIApp(root, auth=auth)
        
        # Configure window close behavior
        def on_closing():
            if messagebox.askokcancel("Quit", "Do you want to quit the Alumni Management System?"):
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Start the GUI event loop
        root.mainloop()
        
    except Exception as e:
        print(f"Error starting Alumni Management System: {e}")
        messagebox.showerror("Startup Error", f"Failed to start the application:\n{str(e)}")


def launch_alumni_gui(auth=None):
    """Launch Alumni GUI for integration with university system"""
    main(auth=auth)


if __name__ == "__main__":
    main()
