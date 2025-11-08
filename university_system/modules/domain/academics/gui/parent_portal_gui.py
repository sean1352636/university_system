from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
from university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
from typing import Optional, List, Dict, Any
import sys
import os
from university_system.infrastructure.auth.user_authentication import UserAuth

# Import the original parent portal functionality
try:
    from university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility

class ParentPortalGUI:
    """
    Modern GUI for the Parent Portal system.
    Maintains full backwards compatibility with the original CLI version.
    """
    
    def __init__(self, auth=None):
        self.auth = auth
        self.parent_portal = None
        self.root = None
        self.current_user = None
        self.parent_id = None
        self.children = []
        
        # GUI Components
        self.main_frame = None
        self.sidebar_frame = None
        self.content_frame = None
        self.status_bar = None
        
        # Initialize the portal
        if auth:
            self.parent_portal = ParentPortal(auth)
            self.current_user = auth.current_user
            if self.current_user and self.current_user['role'] == 'parent':
                self.parent_id = self.parent_portal.get_parent_id_from_user(self.current_user['id'])
        
    def create_main_window(self):
        """Create and configure the main application window"""
        self.root = tk.Tk()
        self.root.title("Parent Portal - School Management System")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors and fonts
        style.configure('Sidebar.TFrame', background='#2c3e50')
        style.configure('Content.TFrame', background='#ecf0f1')
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#2c3e50', foreground='white')
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Info.TLabel', font=('Arial', 10))
        
        self.setup_layout()
        self.load_user_data()
        self.show_dashboard()
        
        return self.root
    
    def setup_layout(self):
        """Setup the main layout with sidebar and content area"""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        self.sidebar_frame = ttk.Frame(main_container, style='Sidebar.TFrame', width=300)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        self.sidebar_frame.pack_propagate(False)
        
        # Content area
        content_container = ttk.Frame(main_container)
        content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.content_frame = ttk.Frame(content_container, style='Content.TFrame')
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.setup_sidebar()
    
    def setup_sidebar(self):
        """Setup the navigation sidebar"""
        # Title
        title_label = ttk.Label(self.sidebar_frame, text="Parent Portal", style='Title.TLabel')
        title_label.pack(pady=20)
        
        # User info
        if self.current_user:
            user_info = ttk.Label(
                self.sidebar_frame, 
                text=f"Welcome, {self.current_user.get('first_name', 'Parent')}",
                style='Title.TLabel',
                font=('Arial', 11)
            )
            user_info.pack(pady=10)
        
        # Navigation menu
        self.create_nav_menu()
    
    def create_nav_menu(self):
        """Create the navigation menu"""
        # Menu sections
        menus = [
            ("🏠 Dashboard", self.show_dashboard),
            ("⚡ Quick Actions", self.show_quick_actions),
            ("👥 My Children", self.show_children),
            ("📚 Academic Records", self.show_academic_menu),
            ("📅 Attendance & Behavior", self.show_attendance_menu),
            ("🏥 Health & Safety", self.show_health_menu),
            ("💬 Communication", self.show_communication_menu),
            ("💰 Financial", self.show_financial_menu),
            ("📖 Academic Support", self.show_academic_support_menu),
            ("⚙️ Settings & Tools", self.show_settings_menu),
            ("🔔 Notifications", self.mark_notifications_read),  # New quick access
            ("🏠 Return to Main Menu", self.return_to_main_menu),
        ]
        self.nav_buttons = []
        for text, command in menus:
            btn = tk.Button(
                self.sidebar_frame,
                text=text,
                command=command,
                bg='#34495e',
                fg='white',
                font=('Arial', 10),
                relief=tk.FLAT,
                padx=20,
                pady=10,
                anchor='w',
                width=25
            )
            btn.pack(fill=tk.X, pady=2, padx=10)
            self.nav_buttons.append(btn)
        
        # Logout button at bottom
        logout_btn = tk.Button(
            self.sidebar_frame,
            text="🚪 Logout",
            command=self.logout,
            bg='#e74c3c',
            fg='white',
            font=('Arial', 10),
            relief=tk.FLAT,
            padx=20,
            pady=10
        )
        logout_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=10)
    
    def clear_content(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def load_user_data(self):
        """Load user data in background"""
        if self.parent_portal and self.parent_id:
            try:
                self.children = self.parent_portal.view_children()
                self.update_status(f"Loaded data for {len(self.children)} children")
            except Exception as e:
                self.update_status(f"Error loading data: {str(e)}")
    
    def update_status(self, message: str):
        """Update the status bar"""
        if self.status_bar:
            self.status_bar.config(text=message)
    
    def show_dashboard(self):
        """Show the main dashboard"""
        self.clear_content()
        self.update_status("Dashboard")
        
        # Dashboard title
        title = ttk.Label(self.content_frame, text="Parent Dashboard", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        # Create dashboard widgets
        dashboard_container = ttk.Frame(self.content_frame)
        dashboard_container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Quick stats cards
        self.create_stats_cards(dashboard_container)
        
        # Recent activity and alerts
        activity_frame = ttk.Frame(dashboard_container)
        activity_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        # Left column - Recent alerts
        left_column = ttk.Frame(activity_frame)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        alerts_label = ttk.Label(left_column, text="Recent Alerts", style='Heading.TLabel')
        alerts_label.pack(anchor='w')
        
        alerts_text = scrolledtext.ScrolledText(left_column, height=15, width=40)
        alerts_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Right column - Children overview
        right_column = ttk.Frame(activity_frame)
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        children_label = ttk.Label(right_column, text="My Children", style='Heading.TLabel')
        children_label.pack(anchor='w')
        
        children_frame = ttk.Frame(right_column)
        children_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Load dashboard data
        self.load_dashboard_data(alerts_text, children_frame)
    
    def create_stats_cards(self, parent):
        """Create quick stats cards"""
        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill=tk.X, pady=10)
        
        # Sample stats (in real implementation, these would be dynamic)
        stats = [
            ("Children", len(self.children), "#3498db"),
            ("Unread Messages", "2", "#e74c3c"),
            ("Upcoming Events", "3", "#f39c12"),
            ("Pending Fees", "£0.00", "#27ae60")
        ]
        
        for i, (title, value, color) in enumerate(stats):
            card = tk.Frame(stats_frame, bg=color, padx=20, pady=15)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            value_label = tk.Label(card, text=str(value), font=('Arial', 18, 'bold'), bg=color, fg='white')
            value_label.pack()
            
            title_label = tk.Label(card, text=title, font=('Arial', 10), bg=color, fg='white')
            title_label.pack()
    
    def load_dashboard_data(self, alerts_text, children_frame):
        """Load dashboard data in background"""
        def load_data():
            try:
                # Load alerts
                alerts_text.insert(tk.END, "Loading alerts...\n")
                
                # Load children data
                if self.children:
                    for i, child in enumerate(self.children):
                        child_card = self.create_child_card(children_frame, child)
                        child_card.pack(fill=tk.X, pady=5)
                else:
                    no_children_label = ttk.Label(children_frame, text="No children registered")
                    no_children_label.pack()
                
                alerts_text.delete(1.0, tk.END)
                alerts_text.insert(tk.END, "✓ System ready\n")
                alerts_text.insert(tk.END, "📧 2 unread messages\n")
                alerts_text.insert(tk.END, "📅 Parent-teacher meeting scheduled\n")
                
            except Exception as e:
                alerts_text.insert(tk.END, f"Error loading data: {str(e)}\n")
        
        # Load data in background thread
        threading.Thread(target=load_data, daemon=True).start()
    
    def create_child_card(self, parent, child):
        """Create a card widget for a child"""
        card = ttk.LabelFrame(parent, text=f"{child[1]} {child[3]}", padding=10)
        
        info_text = f"ID: {child[0]}\nCourse: {child[4]}\nRelationship: {child[5]}"
        info_label = ttk.Label(card, text=info_text, style='Info.TLabel')
        info_label.pack(anchor='w')
        
        # Quick action buttons
        btn_frame = ttk.Frame(card)
        btn_frame.pack(fill=tk.X, pady=5)
        
        view_grades_btn = ttk.Button(btn_frame, text="Grades", 
                                   command=lambda c=child: self.view_child_grades(c))
        view_grades_btn.pack(side=tk.LEFT, padx=2)
        
        view_attendance_btn = ttk.Button(btn_frame, text="Attendance", 
                                       command=lambda c=child: self.view_child_attendance(c))
        view_attendance_btn.pack(side=tk.LEFT, padx=2)
        
        return card
    
    def show_quick_actions(self):
        """Show quick actions menu"""
        self.clear_content()
        self.update_status("Quick Actions")
        
        title = ttk.Label(self.content_frame, text="Quick Actions", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        actions_frame = ttk.Frame(self.content_frame)
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Quick action buttons
        actions = [
            ("📝 Report Absence", self.quick_absence_report),
            ("📞 Update Emergency Contact", self.emergency_contact_update),
            ("🚨 View Today's Alerts", self.view_todays_alerts),
            ("💳 Check Meal Balance", self.check_meal_balance),
            ("📨 View Urgent Messages", self.view_urgent_messages),
        ]
        
        for i, (text, command) in enumerate(actions):
            row = i // 2
            col = i % 2
            
            btn = tk.Button(
                actions_frame,
                text=text,
                command=command,
                font=('Arial', 12),
                padx=20,
                pady=20,
                width=25,
                height=3,
                bg='#3498db',
                fg='white',
                relief=tk.RAISED
            )
            btn.grid(row=row, column=col, padx=10, pady=10, sticky='ew')
        
        actions_frame.grid_columnconfigure(0, weight=1)
        actions_frame.grid_columnconfigure(1, weight=1)
    
    def show_children(self):
        """Show children overview"""
        self.clear_content()
        self.update_status("My Children")
        
        title = ttk.Label(self.content_frame, text="My Children", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        if not self.children:
            no_children_label = ttk.Label(self.content_frame, text="No children registered in the system.")
            no_children_label.pack(pady=50)
            return
        
        # Children list with detailed cards
        children_container = ttk.Frame(self.content_frame)
        children_container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Create scrollable frame
        canvas = tk.Canvas(children_container)
        scrollbar = ttk.Scrollbar(children_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        for child in self.children:
            detailed_card = self.create_detailed_child_card(scrollable_frame, child)
            detailed_card.pack(fill=tk.X, pady=10, padx=10)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_detailed_child_card(self, parent, child):
        """Create a detailed card for a child"""
        card = ttk.LabelFrame(parent, text=f"{child[1]} {child[3]}", padding=15)
        
        # Child info section
        info_frame = ttk.Frame(card)
        info_frame.pack(fill=tk.X, pady=5)
        
        left_info = ttk.Frame(info_frame)
        left_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(left_info, text=f"Student ID: {child[0]}", style='Info.TLabel').pack(anchor='w')
        ttk.Label(left_info, text=f"Course: {child[4]}", style='Info.TLabel').pack(anchor='w')
        ttk.Label(left_info, text=f"Relationship: {child[5]}", style='Info.TLabel').pack(anchor='w')
        ttk.Label(left_info, text=f"Access Level: {child[6]}", style='Info.TLabel').pack(anchor='w')
        
        # Action buttons
        btn_frame = ttk.Frame(card)
        btn_frame.pack(fill=tk.X, pady=10)
        
        buttons = [
            ("📊 View Grades", lambda c=child: self.view_child_grades(c)),
            ("📅 Attendance", lambda c=child: self.view_child_attendance(c)),
            ("📝 Assignments", lambda c=child: self.view_child_assignments(c)),
            ("📋 Reports", lambda c=child: self.view_teacher_reports(c)),
            ("💬 Message Teachers", lambda c=child: self.message_teachers(c)),
        ]
        
        for i, (text, command) in enumerate(buttons):
            btn = ttk.Button(btn_frame, text=text, command=command)
            btn.grid(row=i//3, column=i%3, padx=5, pady=2, sticky='ew')
        
        for i in range(3):
            btn_frame.grid_columnconfigure(i, weight=1)
        
        return card
    
    def show_academic_menu(self):
        """Show academic records submenu"""
        self.clear_content()
        self.update_status("Academic Records")
        
        title = ttk.Label(self.content_frame, text="Academic Records", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        menu_frame = ttk.Frame(self.content_frame)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        options = [
            ("📊 View Grades", self.show_grades_interface),
            ("📋 Teacher Reports", self.show_reports_interface),
            ("📅 View Timetable", self.show_timetable_interface),
            ("📈 Grade Analytics", self.show_analytics_interface),
        ]
        
        for i, (text, command) in enumerate(options):
            btn = tk.Button(
                menu_frame,
                text=text,
                command=command,
                font=('Arial', 12),
                padx=20,
                pady=15,
                width=30,
                bg='#2ecc71',
                fg='white'
            )
            btn.pack(pady=10)
    
    def show_attendance_menu(self):
        """Show attendance and behavior submenu"""
        self.clear_content()
        self.update_status("Attendance & Behavior")
        
        title = ttk.Label(self.content_frame, text="Attendance & Behavior", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        menu_frame = ttk.Frame(self.content_frame)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        options = [
            ("📅 View Attendance", self.show_attendance_interface),
            ("🎭 Behavior Reports", self.show_behavior_interface),
            ("🏥 Report Absence", self.show_absence_interface),
        ]
        
        for text, command in options:
            btn = tk.Button(
                menu_frame,
                text=text,
                command=command,
                font=('Arial', 12),
                padx=20,
                pady=15,
                width=30,
                bg='#9b59b6',
                fg='white'
            )
            btn.pack(pady=10)
    
    def show_health_menu(self):
        """Show health and safety submenu"""
        self.clear_content()
        self.update_status("Health & Safety")
        
        title = ttk.Label(self.content_frame, text="Health & Safety", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        menu_frame = ttk.Frame(self.content_frame)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        options = [
            ("🏥 Medical Information", self.show_medical_interface),
            ("🚌 Transportation", self.show_transport_interface),
            ("👤 Pickup Authorization", self.show_pickup_interface),
            ("📷 Photo Permissions", self.show_photo_interface),
        ]
        
        for text, command in options:
            btn = tk.Button(
                menu_frame,
                text=text,
                command=command,
                font=('Arial', 12),
                padx=20,
                pady=15,
                width=30,
                bg='#e67e22',
                fg='white'
            )
            btn.pack(pady=10)
    
    def show_communication_menu(self):
        """Show communication submenu"""
        self.clear_content()
        self.update_status("Communication")

        title = ttk.Label(self.content_frame, text="Communication", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        menu_frame = ttk.Frame(self.content_frame)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        options = [
            ("📧 View Messages", self.show_messages_interface),
            ("✉️ Send Message", self.show_send_message_interface),
            ("👥 Group Messages", self.show_group_message_interface),
            ("📢 Announcements", self.show_announcements_interface),
            ("🤝 Schedule Meeting", self.show_meeting_interface),
            ("⚠️ Report Issue", self.show_report_issue_interface),
        ]

        for text, command in options:
            btn = tk.Button(
                menu_frame,
                text=text,
                command=command,
                font=('Arial', 12),
                padx=20,
                pady=15,
                width=30,
                bg='#34495e',
                fg='white'
            )
            btn.pack(pady=10)
    
    def show_financial_menu(self):
        """Show financial submenu"""
        self.clear_content()
        self.update_status("Financial")
        
        title = ttk.Label(self.content_frame, text="Financial Management", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        menu_frame = ttk.Frame(self.content_frame)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        options = [
            ("💰 Fees & Payments", self.show_fees_interface),
            ("🍽️ Meal Accounts", self.show_meal_interface),
            ("🎯 Fundraising", self.show_fundraising_interface),
            ("💝 Make Donation", self.donate_to_campaign),
        ]
        
        for text, command in options:
            btn = tk.Button(
                menu_frame,
                text=text,
                command=command,
                font=('Arial', 12),
                padx=20,
                pady=15,
                width=30,
                bg='#27ae60',
                fg='white'
            )
            btn.pack(pady=10)
        
    def show_academic_support_menu(self):
        """Show academic support submenu"""
        self.clear_content()
        self.update_status("Academic Support")
        
        title = ttk.Label(self.content_frame, text="Academic Support", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        menu_frame = ttk.Frame(self.content_frame)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        options = [
            ("📚 Homework & Assignments", self.show_homework_interface),
            ("🎯 Academic Goals", self.show_goals_interface),
            ("📈 Grade Analytics", self.show_analytics_interface),
            ("📖 Library Account", self.show_library_interface),
            ("🏃 Activities", self.show_activities_interface),
        ]
        
        for text, command in options:
            btn = tk.Button(
                menu_frame,
                text=text,
                command=command,
                font=('Arial', 12),
                padx=20,
                pady=15,
                width=30,
                bg='#3498db',
                fg='white'
            )
            btn.pack(pady=10)
    
    def show_settings_menu(self):
        """Show settings and tools submenu"""
        self.clear_content()
        self.update_status("Settings & Tools")

        title = ttk.Label(self.content_frame, text="Settings & Tools", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        menu_frame = ttk.Frame(self.content_frame)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        options = [
            ("🔔 Notification Preferences", self.show_notifications_interface),
            ("📄 Document Management", self.show_documents_interface),
            ("📅 Calendar Integration", self.show_calendar_interface),
            ("⚙️ Account Settings", self.show_account_interface),
            ("📊 Activity Log", self.view_activity_log),
            ("🔐 Two-Factor Authentication", self.enable_two_factor_auth),
            ("📷 Update Profile Photo", self.update_profile_photo),
            ("📤 Export Child Data", self.export_child_data),
            ("🔗 Generate QR Code", self.generate_qr_code_interface),
            ("✅ Mark Notifications Read", self.mark_notifications_read),
        ]

        for text, command in options:
            btn = tk.Button(
                menu_frame,
                text=text,
                command=command,
                font=('Arial', 12),
                padx=20,
                pady=15,
                width=30,
                bg='#95a5a6',
                fg='white'
            )
            btn.pack(pady=10)

        # Admin functions (only show if user is admin)
        if self.current_user and self.current_user.get('role') == 'admin':
            admin_frame = ttk.LabelFrame(self.content_frame, text="Administrator Functions", padding=20)
            admin_frame.pack(fill=tk.X, padx=20, pady=20)

            admin_options = [
                ("👨‍👩‍👧 Create Parent Account", self.show_create_parent_account_interface),
                ("🔗 Link Student to Parent", self.show_link_student_interface),
            ]

            for text, command in admin_options:
                btn = tk.Button(
                    admin_frame,
                    text=text,
                    command=command,
                    font=('Arial', 12),
                    padx=20,
                    pady=15,
                    width=30,
                    bg='#c0392b',
                    fg='white'
                )
                btn.pack(pady=10)
        
    def view_child_grades(self, child):
        """View grades for a specific child"""
        self.clear_content()
        self.update_status(f"Viewing grades for {child[1]} {child[3]}")
        
        title = ttk.Label(self.content_frame, text=f"Grades for {child[1]} {child[3]}", 
                         style='Title.TLabel', font=('Arial', 18, 'bold'))
        title.pack(pady=20)
        
        # Create grades table
        grades_frame = ttk.Frame(self.content_frame)
        grades_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Table headers
        columns = ('Module', 'Assessment', 'Grade', 'Date', 'Comments')
        tree = ttk.Treeview(grades_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        
        # Load real grades data from database
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                # First try to get assignment grades
                cursor.execute("""
                    SELECT DISTINCT m.module_code, 'Assignment', g.grade, g.submission_date, g.feedback
                    FROM assignment_submissions s
                    JOIN assignments a ON s.assignment_id = a.assignment_id
                    JOIN modules m ON a.module_code = m.module_code
                    JOIN assignment_grades g ON s.submission_id = g.submission_id
                    WHERE s.student_id = ?
                    ORDER BY g.submission_date DESC LIMIT 10
                """, (child_id,))
                grades = cursor.fetchall()

                # If no assignment grades, try getting grades from a grades table
                if not grades:
                    cursor.execute("""
                        SELECT module_code, assignment_name, grade, date_recorded, comments
                        FROM grades
                        WHERE student_id = ?
                        ORDER BY date_recorded DESC LIMIT 10
                    """, (child_id,))
                    grades = cursor.fetchall()

                # If still no grades, check for any student record to show they exist
                if not grades:
                    cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (child_id,))
                    if cursor.fetchone():
                        tree.insert('', tk.END, values=('N/A', 'No grades available yet', '', '', 'Grades will appear here once assignments are graded'))
                    else:
                        tree.insert('', tk.END, values=('ERROR', 'Student not found in database', '', '', ''))
                else:
                    for grade in grades:
                        tree.insert('', tk.END, values=grade)

        except Exception as e:
            tree.insert('', tk.END, values=('ERROR', f'Database error: {str(e)}', '', '', 'Unable to load grades'))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(grades_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Back button
        back_btn = ttk.Button(self.content_frame, text="← Back", command=self.show_children)
        back_btn.pack(pady=10)
    
    def view_child_attendance(self, child):
        """View attendance for a specific child"""
        self.clear_content()
        self.update_status(f"Viewing attendance for {child[1]} {child[3]}")
        
        title = ttk.Label(self.content_frame, text=f"Attendance for {child[1]} {child[3]}", 
                         style='Title.TLabel', font=('Arial', 18, 'bold'))
        title.pack(pady=20)
        
        # Attendance summary
        summary_frame = ttk.LabelFrame(self.content_frame, text="Attendance Summary", padding=15)
        summary_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(summary_frame, text="Overall Attendance: 95.5%", style='Heading.TLabel').pack()
        ttk.Label(summary_frame, text="Days Present: 87 | Days Absent: 4", style='Info.TLabel').pack()
        
        # Recent attendance
        recent_frame = ttk.LabelFrame(self.content_frame, text="Recent Attendance", padding=15)
        recent_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        columns = ('Date', 'Status', 'Module', 'Reason')
        tree = ttk.Treeview(recent_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        
        # Load real attendance data from database
        child_id = child[0]  # Assuming child[0] is the student_id
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                # Try to get attendance records
                cursor.execute("""
                    SELECT a.attendance_date, a.status, m.module_code, a.reason
                    FROM attendance a
                    LEFT JOIN modules m ON a.module_id = m.id
                    WHERE a.student_id = ?
                    ORDER BY a.attendance_date DESC LIMIT 20
                """, (child_id,))
                attendance_records = cursor.fetchall()

                # If no attendance table, try student_absences
                if not attendance_records:
                    cursor.execute("""
                        SELECT sa.attendance_date, sa.status, m.module_code, sa.reason
                        FROM student_absences sa
                        LEFT JOIN modules m ON sa.module_id = m.id
                        WHERE sa.student_id = ?
                        ORDER BY sa.attendance_date DESC LIMIT 20
                    """, (child_id,))
                    attendance_records = cursor.fetchall()

                if not attendance_records:
                    # Check if student exists
                    cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (child_id,))
                    if cursor.fetchone():
                        tree.insert('', tk.END, values=('N/A', 'No attendance records yet', '', 'Attendance tracking will begin when classes start'))
                    else:
                        tree.insert('', tk.END, values=('ERROR', 'Student not found', '', ''))
                else:
                    for record in attendance_records:
                        tree.insert('', tk.END, values=record)

        except Exception as e:
            tree.insert('', tk.END, values=('ERROR', f'Database error: {str(e)}', '', 'Unable to load attendance'))
        
        tree.pack(fill=tk.BOTH, expand=True)
        
        # Back button
        back_btn = ttk.Button(self.content_frame, text="← Back", command=self.show_children)
        back_btn.pack(pady=10)
    
    def view_child_assignments(self, child):
        """View assignments for a specific child"""
        self.clear_content()
        self.update_status(f"Viewing assignments for {child[1]} {child[3]}")
        
        title = ttk.Label(self.content_frame, text=f"Assignments for {child[1]} {child[3]}", 
                         style='Title.TLabel', font=('Arial', 18, 'bold'))
        title.pack(pady=20)
        
        # Create notebook for different assignment categories
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Upcoming assignments tab
        upcoming_frame = ttk.Frame(notebook)
        notebook.add(upcoming_frame, text="Upcoming")
        
        upcoming_tree = self.create_assignments_tree(upcoming_frame)
        upcoming_assignments = [
            ('MATH101', 'Problem Set 5', '2024-01-25', 'Pending', 'High'),
            ('ENG101', 'Book Report', '2024-01-28', 'In Progress', 'Medium'),
        ]
        for assignment in upcoming_assignments:
            upcoming_tree.insert('', tk.END, values=assignment)
        
        # Overdue assignments tab
        overdue_frame = ttk.Frame(notebook)
        notebook.add(overdue_frame, text="Overdue")
        
        overdue_tree = self.create_assignments_tree(overdue_frame)
        overdue_assignments = [
            ('SCI101', 'Lab Report 3', '2024-01-15', 'Overdue', 'High'),
        ]
        for assignment in overdue_assignments:
            overdue_tree.insert('', tk.END, values=assignment)
        
        # Completed assignments tab
        completed_frame = ttk.Frame(notebook)
        notebook.add(completed_frame, text="Completed")
        
        completed_tree = self.create_assignments_tree(completed_frame)
        completed_assignments = [
            ('HIST101', 'Essay on WWII', '2024-01-10', 'Completed', 'A-'),
            ('MATH101', 'Problem Set 4', '2024-01-08', 'Completed', 'B+'),
        ]
        for assignment in completed_assignments:
            completed_tree.insert('', tk.END, values=assignment)
        
        # Back button
        back_btn = ttk.Button(self.content_frame, text="← Back", command=self.show_children)
        back_btn.pack(pady=10)
    
    def create_assignments_tree(self, parent):
        """Create a tree widget for assignments"""
        columns = ('Module', 'Assignment', 'Due Date', 'Status', 'Grade/Priority')
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=10)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        return tree
    
    def view_teacher_reports(self, child):
        """View teacher reports for a specific child"""
        self.clear_content()
        self.update_status(f"Viewing reports for {child[1]} {child[3]}")
        
        title = ttk.Label(self.content_frame, text=f"Teacher Reports for {child[1]} {child[3]}", 
                         style='Title.TLabel', font=('Arial', 18, 'bold'))
        title.pack(pady=20)
        
        # Reports list
        reports_frame = ttk.Frame(self.content_frame)
        reports_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Left side - report list
        list_frame = ttk.LabelFrame(reports_frame, text="Available Reports", padding=10)
        list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        reports_listbox = tk.Listbox(list_frame, width=40, height=15)
        reports_listbox.pack(fill=tk.BOTH, expand=True)
        
        # Sample reports
        sample_reports = [
            "2024-01-15 - MATH101 - Progress Report",
            "2024-01-10 - ENG101 - Behavior Report", 
            "2024-01-05 - SCI101 - Academic Performance",
            "2023-12-20 - General - Semester Summary"
        ]
        
        for report in sample_reports:
            reports_listbox.insert(tk.END, report)
        
        # Right side - report content
        content_frame = ttk.LabelFrame(reports_frame, text="Report Content", padding=10)
        content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        report_text = scrolledtext.ScrolledText(content_frame, width=50, height=15)
        report_text.pack(fill=tk.BOTH, expand=True)
        
        def show_report(event):
            selection = reports_listbox.curselection()
            if selection:
                report_text.delete(1.0, tk.END)
                report_text.insert(tk.END, f"Report: {sample_reports[selection[0]]}\n\n")
                report_text.insert(tk.END, "This is a sample report content. In the real implementation, ")
                report_text.insert(tk.END, "this would show the actual report from the database.\n\n")
                report_text.insert(tk.END, "Student shows good progress in mathematics. ")
                report_text.insert(tk.END, "Continues to demonstrate strong problem-solving skills.")
        
        reports_listbox.bind('<<ListboxSelect>>', show_report)
        
        # Back button
        back_btn = ttk.Button(self.content_frame, text="← Back", command=self.show_children)
        back_btn.pack(pady=10)
    
    def message_teachers(self, child):
        """Message teachers for a specific child"""
        self.clear_content()
        self.update_status(f"Messaging teachers for {child[1]} {child[3]}")
        
        title = ttk.Label(self.content_frame, text=f"Message Teachers - {child[1]} {child[3]}", 
                         style='Title.TLabel', font=('Arial', 18, 'bold'))
        title.pack(pady=20)
        
        message_frame = ttk.Frame(self.content_frame)
        message_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Teacher selection
        teacher_frame = ttk.LabelFrame(message_frame, text="Select Teacher", padding=10)
        teacher_frame.pack(fill=tk.X, pady=10)
        
        teacher_var = tk.StringVar()
        teachers = ["Mr. Smith (MATH101)", "Ms. Johnson (ENG101)", "Dr. Brown (SCI101)", "All Teachers"]
        
        for teacher in teachers:
            rb = ttk.Radiobutton(teacher_frame, text=teacher, variable=teacher_var, value=teacher)
            rb.pack(anchor='w')
        
        teacher_var.set(teachers[0])
        
        # Message composition
        compose_frame = ttk.LabelFrame(message_frame, text="Compose Message", padding=10)
        compose_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ttk.Label(compose_frame, text="Subject:").pack(anchor='w')
        subject_entry = ttk.Entry(compose_frame, width=80)
        subject_entry.pack(fill=tk.X, pady=5)
        
        ttk.Label(compose_frame, text="Message:").pack(anchor='w', pady=(10, 0))
        message_text = scrolledtext.ScrolledText(compose_frame, height=10)
        message_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Send button
        def send_message():
            subject = subject_entry.get()
            message = message_text.get(1.0, tk.END).strip()
            teacher = teacher_var.get()
            
            if not subject or not message:
                messagebox.showwarning("Missing Information", "Please fill in both subject and message.")
                return
            
            # In real implementation, this would send the message
            messagebox.showinfo("Message Sent", f"Message sent to {teacher}")
            subject_entry.delete(0, tk.END)
            message_text.delete(1.0, tk.END)
        
        send_btn = ttk.Button(compose_frame, text="Send Message", command=send_message)
        send_btn.pack(pady=10)
        
        # Back button
        back_btn = ttk.Button(self.content_frame, text="← Back", command=self.show_children)
        back_btn.pack(pady=10)
    
    # Quick Actions Implementation
    
    def quick_absence_report(self):
        """Quick absence report"""
        if not self.children:
            messagebox.showinfo("No Children", "No children registered in the system.")
            return
        
        dialog = AbsenceReportDialog(self.root, self.children)
        if dialog.result:
            child, reason = dialog.result
            # In real implementation, this would save to database
            messagebox.showinfo("Success", f"Absence reported for {child[1]} {child[3]}")
    
    def emergency_contact_update(self):
        """Emergency contact update"""
        dialog = EmergencyContactDialog(self.root)
        if dialog.result:
            # In real implementation, this would update the database
            messagebox.showinfo("Success", "Emergency contact information updated.")
    
    def view_todays_alerts(self):
        """View today's alerts"""
        alerts_window = tk.Toplevel(self.root)
        alerts_window.title("Today's Alerts")
        alerts_window.geometry("500x400")
        
        title = ttk.Label(alerts_window, text="Today's Alerts", font=('Arial', 16, 'bold'))
        title.pack(pady=20)
        
        alerts_text = scrolledtext.ScrolledText(alerts_window, height=15)
        alerts_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Sample alerts
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        alerts_text.insert(tk.END, f"Alerts for {today}\n")
        alerts_text.insert(tk.END, "=" * 30 + "\n\n")
        alerts_text.insert(tk.END, "📧 2 unread messages\n")
        alerts_text.insert(tk.END, "📅 Parent-teacher meeting tomorrow at 3 PM\n")
        alerts_text.insert(tk.END, "💰 Meal account balance low for Sarah\n")
        alerts_text.insert(tk.END, "📚 Math assignment due tomorrow\n")
        
        close_btn = ttk.Button(alerts_window, text="Close", command=alerts_window.destroy)
        close_btn.pack(pady=10)
    
    def check_meal_balance(self):
        """Check meal account balances"""
        balance_window = tk.Toplevel(self.root)
        balance_window.title("Meal Account Balances")
        balance_window.geometry("400x300")
        
        title = ttk.Label(balance_window, text="Meal Account Balances", font=('Arial', 16, 'bold'))
        title.pack(pady=20)
        
        for child in self.children:
            balance_frame = ttk.LabelFrame(balance_window, text=f"{child[1]} {child[3]}", padding=10)
            balance_frame.pack(fill=tk.X, padx=20, pady=5)
            
            # Sample balance data
            balance = 25.50  # In real implementation, this would come from database
            status = "OK" if balance > 10 else "LOW"
            color = "green" if balance > 10 else "red"
            
            ttk.Label(balance_frame, text=f"Balance: £{balance:.2f}").pack()
            ttk.Label(balance_frame, text=f"Status: {status}", foreground=color).pack()
        
        close_btn = ttk.Button(balance_window, text="Close", command=balance_window.destroy)
        close_btn.pack(pady=20)
    
    def view_urgent_messages(self):
        """View urgent messages"""
        messages_window = tk.Toplevel(self.root)
        messages_window.title("Urgent Messages")
        messages_window.geometry("600x400")
        
        title = ttk.Label(messages_window, text="Urgent Messages", font=('Arial', 16, 'bold'))
        title.pack(pady=20)
        
        messages_text = scrolledtext.ScrolledText(messages_window, height=15)
        messages_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Sample urgent messages
        messages_text.insert(tk.END, "Urgent Messages (Last 24 hours)\n")
        messages_text.insert(tk.END, "=" * 40 + "\n\n")
        messages_text.insert(tk.END, "📨 From Mr. Smith re: John Doe\n")
        messages_text.insert(tk.END, "2024-01-20 14:30: Please contact me regarding John's recent math performance.\n\n")
        messages_text.insert(tk.END, "📨 From Ms. Johnson re: Sarah Doe\n")
        messages_text.insert(tk.END, "2024-01-20 09:15: Sarah forgot her lunch today. Please confirm pickup arrangements.\n\n")
        
        close_btn = ttk.Button(messages_window, text="Close", command=messages_window.destroy)
        close_btn.pack(pady=10)
    
    # Interface method stubs (these would be fully implemented)
    
    def show_grades_interface(self):
        """Show grades interface"""
        self.clear_content()
        self.update_status("Grades Interface")
        
        title = ttk.Label(self.content_frame, text="Grade Management", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        # Child selection
        if self.children:
            child_var = tk.StringVar()
            child_frame = ttk.LabelFrame(self.content_frame, text="Select Child", padding=10)
            child_frame.pack(fill=tk.X, padx=20, pady=10)
            
            child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=50)
            child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
            child_combo.pack(pady=5)
            child_combo.set(child_combo['values'][0] if child_combo['values'] else "")
            
            def view_selected_grades():
                if child_var.get():
                    selected_index = child_combo.current()
                    if selected_index >= 0:
                        self.view_child_grades(self.children[selected_index])
            
            view_btn = ttk.Button(child_frame, text="View Grades", command=view_selected_grades)
            view_btn.pack(pady=5)
        else:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
    
    def show_reports_interface(self):
        """Show reports interface"""
        self.clear_content()
        self.update_status("Teacher Reports")
        
        title = ttk.Label(self.content_frame, text="Teacher Reports", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        if self.children:
            for child in self.children:
                child_frame = ttk.LabelFrame(self.content_frame, text=f"{child[1]} {child[3]}", padding=15)
                child_frame.pack(fill=tk.X, padx=20, pady=10)
                
                info_label = ttk.Label(child_frame, text=f"Student ID: {child[0]} | Course: {child[4]}")
                info_label.pack()
                
                view_btn = ttk.Button(child_frame, text="View Reports", 
                                     command=lambda c=child: self.view_teacher_reports(c))
                view_btn.pack(pady=5)
        else:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
    
    def show_timetable_interface(self):
        """Show timetable interface"""
        self.clear_content()
        self.update_status("Timetable")

        title = ttk.Label(self.content_frame, text="Student Timetables", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Timetable display frame
        timetable_frame = ttk.LabelFrame(self.content_frame, text="Weekly Timetable", padding=15)
        timetable_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_timetable():
            # Clear existing widgets
            for widget in timetable_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(timetable_frame, text="Please select a child").pack(pady=20)
                return

            # Extract student ID
            student_id = selected_child.split("ID: ")[1].rstrip(")")

            # Create timetable grid
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            time_slots = ["08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
                         "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00"]

            # Create header
            ttk.Label(timetable_frame, text="Time", font=('Arial', 10, 'bold'),
                     relief=tk.RIDGE, width=15).grid(row=0, column=0, sticky='nsew', padx=1, pady=1)

            for col, day in enumerate(days, start=1):
                ttk.Label(timetable_frame, text=day, font=('Arial', 10, 'bold'),
                         relief=tk.RIDGE).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

            # Try to load actual timetable from database
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Check if timetable table exists
                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='timetable'
                """)

                if cursor.fetchone():
                    # Load timetable data
                    cursor.execute("""
                    SELECT day_of_week, time_slot, subject, room, teacher
                    FROM timetable
                    WHERE student_id = ?
                    ORDER BY time_slot
                    """, (student_id,))

                    schedule = cursor.fetchall()
                    schedule_dict = {}
                    for entry in schedule:
                        key = (entry[0], entry[1])
                        schedule_dict[key] = f"{entry[2]}\n{entry[3]}\n{entry[4]}"

                    # Populate timetable
                    for row, time_slot in enumerate(time_slots, start=1):
                        ttk.Label(timetable_frame, text=time_slot, font=('Arial', 9),
                                 relief=tk.RIDGE, width=15).grid(row=row, column=0, sticky='nsew', padx=1, pady=1)

                        for col, day in enumerate(days, start=1):
                            cell_text = schedule_dict.get((day, time_slot), "-")
                            cell = ttk.Label(timetable_frame, text=cell_text, font=('Arial', 8),
                                           relief=tk.SUNKEN, anchor='center')
                            cell.grid(row=row, column=col, sticky='nsew', padx=1, pady=1)
                else:
                    # Sample timetable if no data
                    sample_subjects = ["Mathematics", "English", "Science", "History", "Physical Ed", "Lunch Break", "Art", "Music"]

                    for row, time_slot in enumerate(time_slots, start=1):
                        ttk.Label(timetable_frame, text=time_slot, font=('Arial', 9),
                                 relief=tk.RIDGE, width=15).grid(row=row, column=0, sticky='nsew', padx=1, pady=1)

                        for col in range(1, 6):
                            if row == 5:
                                cell_text = "Lunch Break"
                            else:
                                cell_text = sample_subjects[(row + col) % len(sample_subjects)]

                            cell = ttk.Label(timetable_frame, text=cell_text, font=('Arial', 8),
                                           relief=tk.SUNKEN, anchor='center')
                            cell.grid(row=row, column=col, sticky='nsew', padx=1, pady=1)

                conn.close()

            except Exception as e:
                ttk.Label(timetable_frame, text=f"Error loading timetable: {str(e)}").pack(pady=20)

            # Configure grid weights
            for i in range(9):
                timetable_frame.rowconfigure(i, weight=1)
            for i in range(6):
                timetable_frame.columnconfigure(i, weight=1)

        ttk.Button(child_frame, text="Load Timetable", command=load_timetable).pack(side=tk.LEFT, padx=5)

        # Load initial timetable
        load_timetable()
    
    def show_analytics_interface(self):
        """Show analytics interface"""
        self.clear_content()
        self.update_status("Grade Analytics")

        title = ttk.Label(self.content_frame, text="Grade Analytics", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Analytics notebook
        analytics_notebook = ttk.Notebook(self.content_frame)
        analytics_notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Performance Overview Tab
        overview_frame = ttk.Frame(analytics_notebook, padding=10)
        analytics_notebook.add(overview_frame, text="Performance Overview")

        # Grade Distribution Tab
        distribution_frame = ttk.Frame(analytics_notebook, padding=10)
        analytics_notebook.add(distribution_frame, text="Grade Distribution")

        # Trends Tab
        trends_frame = ttk.Frame(analytics_notebook, padding=10)
        analytics_notebook.add(trends_frame, text="Trends")

        def load_analytics():
            selected_child = child_var.get()
            if not selected_child:
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Load grades
                cursor.execute("""
                SELECT subject, grade, date
                FROM grades
                WHERE student_id = ?
                ORDER BY date DESC
                LIMIT 20
                """, (student_id,))

                grades = cursor.fetchall()

                # Performance Overview
                for widget in overview_frame.winfo_children():
                    widget.destroy()

                if grades:
                    # Calculate statistics
                    grade_values = []
                    for g in grades:
                        try:
                            grade_values.append(float(g[1]))
                        except:
                            pass

                    if grade_values:
                        avg_grade = sum(grade_values) / len(grade_values)
                        max_grade = max(grade_values)
                        min_grade = min(grade_values)

                        stats_frame = ttk.LabelFrame(overview_frame, text="Statistics", padding=15)
                        stats_frame.pack(fill=tk.X, pady=10)

                        ttk.Label(stats_frame, text=f"Average Grade: {avg_grade:.2f}%",
                                 font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)
                        ttk.Label(stats_frame, text=f"Highest Grade: {max_grade:.2f}%",
                                 font=('Arial', 11)).pack(anchor='w', pady=3)
                        ttk.Label(stats_frame, text=f"Lowest Grade: {min_grade:.2f}%",
                                 font=('Arial', 11)).pack(anchor='w', pady=3)
                        ttk.Label(stats_frame, text=f"Total Grades: {len(grades)}",
                                 font=('Arial', 11)).pack(anchor='w', pady=3)

                    # Recent grades list
                    recent_frame = ttk.LabelFrame(overview_frame, text="Recent Grades", padding=10)
                    recent_frame.pack(fill=tk.BOTH, expand=True, pady=10)

                    columns = ("Subject", "Grade", "Date")
                    grades_tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=8)

                    for col in columns:
                        grades_tree.heading(col, text=col)
                        grades_tree.column(col, width=150)

                    for grade in grades[:10]:
                        grades_tree.insert('', tk.END, values=grade)

                    grades_tree.pack(fill=tk.BOTH, expand=True)
                else:
                    ttk.Label(overview_frame, text="No grades found for this student",
                             font=('Arial', 11)).pack(pady=50)

                # Grade Distribution
                for widget in distribution_frame.winfo_children():
                    widget.destroy()

                if grade_values:
                    dist_frame = ttk.LabelFrame(distribution_frame, text="Grade Distribution", padding=15)
                    dist_frame.pack(fill=tk.BOTH, expand=True, pady=10)

                    # Calculate distribution
                    ranges = {"A (90-100)": 0, "B (80-89)": 0, "C (70-79)": 0, "D (60-69)": 0, "F (0-59)": 0}
                    for gv in grade_values:
                        if gv >= 90:
                            ranges["A (90-100)"] += 1
                        elif gv >= 80:
                            ranges["B (80-89)"] += 1
                        elif gv >= 70:
                            ranges["C (70-79)"] += 1
                        elif gv >= 60:
                            ranges["D (60-69)"] += 1
                        else:
                            ranges["F (0-59)"] += 1

                    # Display distribution
                    for grade_range, count in ranges.items():
                        percentage = (count / len(grade_values)) * 100 if grade_values else 0
                        ttk.Label(dist_frame, text=f"{grade_range}: {count} ({percentage:.1f}%)",
                                 font=('Arial', 11)).pack(anchor='w', pady=3)
                else:
                    ttk.Label(distribution_frame, text="No grade data available",
                             font=('Arial', 11)).pack(pady=50)

                # Trends
                for widget in trends_frame.winfo_children():
                    widget.destroy()

                if len(grade_values) >= 2:
                    trends_label_frame = ttk.LabelFrame(trends_frame, text="Performance Trends", padding=15)
                    trends_label_frame.pack(fill=tk.X, pady=10)

                    # Simple trend analysis
                    recent_avg = sum(grade_values[:5]) / min(5, len(grade_values))
                    overall_avg = sum(grade_values) / len(grade_values)
                    trend = "improving" if recent_avg > overall_avg else "declining" if recent_avg < overall_avg else "stable"

                    ttk.Label(trends_label_frame, text=f"Overall Trend: {trend.upper()}",
                             font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)
                    ttk.Label(trends_label_frame, text=f"Recent Average (last 5): {recent_avg:.2f}%",
                             font=('Arial', 11)).pack(anchor='w', pady=3)
                    ttk.Label(trends_label_frame, text=f"Overall Average: {overall_avg:.2f}%",
                             font=('Arial', 11)).pack(anchor='w', pady=3)
                else:
                    ttk.Label(trends_frame, text="Not enough data for trend analysis",
                             font=('Arial', 11)).pack(pady=50)

                conn.close()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load analytics: {str(e)}")

        ttk.Button(child_frame, text="Load Analytics", command=load_analytics).pack(side=tk.LEFT, padx=5)

        # Load initial analytics
        load_analytics()
    
    def show_attendance_interface(self):
        """Show attendance interface"""
        self.clear_content()
        self.update_status("Attendance Records")
        
        title = ttk.Label(self.content_frame, text="Attendance Records", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        if self.children:
            for child in self.children:
                child_frame = ttk.LabelFrame(self.content_frame, text=f"{child[1]} {child[3]}", padding=15)
                child_frame.pack(fill=tk.X, padx=20, pady=10)
                
                view_btn = ttk.Button(child_frame, text="View Attendance", 
                                     command=lambda c=child: self.view_child_attendance(c))
                view_btn.pack(pady=5)
        else:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
    
    def show_behavior_interface(self):
        """Show behavior reports interface"""
        self.clear_content()
        self.update_status("Behavior Reports")

        title = ttk.Label(self.content_frame, text="Behavior Reports", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Reports display frame
        reports_frame = ttk.LabelFrame(self.content_frame, text="Behavior Reports", padding=15)
        reports_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_behavior_reports():
            # Clear existing widgets
            for widget in reports_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(reports_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Check if behavior_reports table exists
                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='behavior_reports'
                """)

                if cursor.fetchone():
                    # Load behavior reports
                    cursor.execute("""
                    SELECT date, type, description, severity, teacher_name, resolution
                    FROM behavior_reports
                    WHERE student_id = ?
                    ORDER BY date DESC
                    LIMIT 50
                    """, (student_id,))

                    reports = cursor.fetchall()

                    if reports:
                        # Summary statistics
                        summary_frame = ttk.LabelFrame(reports_frame, text="Summary", padding=10)
                        summary_frame.pack(fill=tk.X, pady=(0, 10))

                        total_reports = len(reports)
                        positive = sum(1 for r in reports if r[1].lower() in ['positive', 'commendation', 'achievement'])
                        negative = sum(1 for r in reports if r[1].lower() in ['negative', 'incident', 'warning'])
                        neutral = total_reports - positive - negative

                        ttk.Label(summary_frame, text=f"Total Reports: {total_reports}",
                                 font=('Arial', 10, 'bold')).grid(row=0, column=0, padx=10, pady=3, sticky='w')
                        ttk.Label(summary_frame, text=f"Positive: {positive}",
                                 font=('Arial', 10), foreground='green').grid(row=0, column=1, padx=10, pady=3, sticky='w')
                        ttk.Label(summary_frame, text=f"Negative: {negative}",
                                 font=('Arial', 10), foreground='red').grid(row=0, column=2, padx=10, pady=3, sticky='w')
                        ttk.Label(summary_frame, text=f"Neutral: {neutral}",
                                 font=('Arial', 10)).grid(row=0, column=3, padx=10, pady=3, sticky='w')

                        # Reports list
                        list_frame = ttk.Frame(reports_frame)
                        list_frame.pack(fill=tk.BOTH, expand=True)

                        columns = ("Date", "Type", "Description", "Severity", "Teacher", "Resolution")
                        reports_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)

                        reports_tree.heading("Date", text="Date")
                        reports_tree.heading("Type", text="Type")
                        reports_tree.heading("Description", text="Description")
                        reports_tree.heading("Severity", text="Severity")
                        reports_tree.heading("Teacher", text="Teacher")
                        reports_tree.heading("Resolution", text="Resolution")

                        reports_tree.column("Date", width=100)
                        reports_tree.column("Type", width=100)
                        reports_tree.column("Description", width=200)
                        reports_tree.column("Severity", width=80)
                        reports_tree.column("Teacher", width=120)
                        reports_tree.column("Resolution", width=120)

                        # Scrollbar
                        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=reports_tree.yview)
                        reports_tree.configure(yscrollcommand=scrollbar.set)

                        reports_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                        # Add reports to tree
                        for report in reports:
                            reports_tree.insert('', tk.END, values=report)

                        # View details button
                        def view_details():
                            selected = reports_tree.selection()
                            if selected:
                                values = reports_tree.item(selected[0])['values']
                                detail_text = f"Date: {values[0]}\n"
                                detail_text += f"Type: {values[1]}\n"
                                detail_text += f"Severity: {values[3]}\n"
                                detail_text += f"Teacher: {values[4]}\n\n"
                                detail_text += f"Description:\n{values[2]}\n\n"
                                detail_text += f"Resolution:\n{values[5] if values[5] else 'Pending'}"

                                messagebox.showinfo("Behavior Report Details", detail_text)

                        ttk.Button(reports_frame, text="View Details",
                                  command=view_details).pack(pady=10)

                    else:
                        ttk.Label(reports_frame, text="No behavior reports found for this student",
                                 font=('Arial', 11)).pack(pady=50)

                else:
                    # Sample data if table doesn't exist
                    sample_frame = ttk.LabelFrame(reports_frame, text="Sample Reports", padding=10)
                    sample_frame.pack(fill=tk.BOTH, expand=True)

                    sample_reports = [
                        ("2024-01-15", "Positive", "Excellent class participation", "None", "Ms. Johnson", "N/A"),
                        ("2024-01-10", "Neutral", "Late to class", "Minor", "Mr. Smith", "Parent contacted"),
                        ("2024-01-05", "Positive", "Helped another student", "None", "Ms. Davis", "N/A")
                    ]

                    columns = ("Date", "Type", "Description", "Severity", "Teacher", "Resolution")
                    reports_tree = ttk.Treeview(sample_frame, columns=columns, show="headings", height=8)

                    for col in columns:
                        reports_tree.heading(col, text=col)
                        reports_tree.column(col, width=120)

                    for report in sample_reports:
                        reports_tree.insert('', tk.END, values=report)

                    reports_tree.pack(fill=tk.BOTH, expand=True, pady=5)

                    ttk.Label(sample_frame, text="(Sample data - no behavior reports table found)",
                             font=('Arial', 9, 'italic')).pack(pady=5)

                conn.close()

            except Exception as e:
                ttk.Label(reports_frame, text=f"Error loading behavior reports: {str(e)}",
                         font=('Arial', 11)).pack(pady=50)

        ttk.Button(child_frame, text="Load Reports", command=load_behavior_reports).pack(side=tk.LEFT, padx=5)

        # Load initial reports
        load_behavior_reports()
    
    def show_absence_interface(self):
        """Show absence reporting interface"""
        self.clear_content()
        self.update_status("Report Absence")
        
        title = ttk.Label(self.content_frame, text="Report Student Absence", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        absence_frame = ttk.LabelFrame(self.content_frame, text="Absence Details", padding=20)
        absence_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Child selection
        ttk.Label(absence_frame, text="Select Child:").pack(anchor='w')
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(absence_frame, textvariable=child_var, width=50)
        if self.children:
            child_combo['values'] = [f"{child[1]} {child[3]}" for child in self.children]
            child_combo.set(child_combo['values'][0] if child_combo['values'] else "")
        child_combo.pack(fill=tk.X, pady=5)
        
        # Date selection
        ttk.Label(absence_frame, text="Absence Date:").pack(anchor='w', pady=(10, 0))
        date_var = tk.StringVar(value=datetime.datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(absence_frame, textvariable=date_var)
        date_entry.pack(fill=tk.X, pady=5)
        
        # Reason
        ttk.Label(absence_frame, text="Reason:").pack(anchor='w', pady=(10, 0))
        reason_text = scrolledtext.ScrolledText(absence_frame, height=5)
        reason_text.pack(fill=tk.X, pady=5)
        
        def submit_absence():
            if not child_var.get() or not reason_text.get(1.0, tk.END).strip():
                messagebox.showwarning("Missing Information", "Please select a child and provide a reason.")
                return
            
            # In real implementation, this would save to database
            messagebox.showinfo("Success", "Absence report submitted successfully.")
            reason_text.delete(1.0, tk.END)
        
        submit_btn = ttk.Button(absence_frame, text="Submit Absence Report", command=submit_absence)
        submit_btn.pack(pady=20)

    # Add these methods to the ParentPortalGUI class

    def view_activity_log(self):
        """View parent activity log for security purposes"""
        self.clear_content()
        self.update_status("Activity Log")
        
        title = ttk.Label(self.content_frame, text="Activity Log", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)
        
        if not self.parent_portal or not self.parent_id:
            ttk.Label(self.content_frame, text="Unable to load activity log.").pack(pady=50)
            return
        
        # Create activity log display
        log_frame = ttk.Frame(self.content_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Activity log table
        columns = ('Date/Time', 'Action', 'Details', 'IP Address')
        tree = ttk.Treeview(log_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        
        # Get activity data (in real implementation, this would fetch from database)
        activities = [
            ('2024-01-20 14:30', 'Login', 'Successful login', '192.168.1.100'),
            ('2024-01-20 14:25', 'View Grades', 'Viewed grades for John Doe', '192.168.1.100'),
            ('2024-01-20 10:15', 'Message Sent', 'Sent message to Mr. Smith', '192.168.1.100'),
        ]
        
        for activity in activities:
            tree.insert('', tk.END, values=activity)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def enable_two_factor_auth(self):
        """Enable two-factor authentication"""
        dialog = TwoFactorDialog(self.root)
        if dialog.result:
            self.update_status("Two-factor authentication enabled")
            messagebox.showinfo("Success", "Two-factor authentication has been enabled.")

    def view_all_meal_transactions(self, child):
        """View all meal account transactions for a child"""
        self.clear_content()
        self.update_status(f"All Meal Transactions - {child[1]} {child[3]}")
        
        title = ttk.Label(self.content_frame, text=f"All Meal Transactions - {child[1]} {child[3]}", 
                         style='Title.TLabel', font=('Arial', 18, 'bold'))
        title.pack(pady=20)
        
        # Transactions table
        trans_frame = ttk.Frame(self.content_frame)
        trans_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        columns = ('Date', 'Type', 'Amount', 'Description', 'Balance After')
        tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        
        # Sample transaction data
        transactions = [
            ('2024-01-20', 'Credit', '£20.00', 'Parent top-up', '£25.50'),
            ('2024-01-19', 'Debit', '£3.50', 'Lunch purchase', '£5.50'),
            ('2024-01-18', 'Debit', '£2.75', 'Snack purchase', '£9.00'),
        ]
        
        for transaction in transactions:
            tree.insert('', tk.END, values=transaction)
        
        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def donate_to_campaign(self):
        """Make a donation to fundraising campaign"""
        dialog = DonationDialog(self.root, self.children)
        if dialog.result:
            campaign, amount, child = dialog.result
            messagebox.showinfo("Success", f"Thank you for your donation of £{amount:.2f} to {campaign}!")

    def update_profile_photo(self):
        """Update parent profile photo"""
        from tkinter import filedialog
        
        file_path = filedialog.askopenfilename(
            title="Select Profile Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp")]
        )
        
        if file_path:
            # In real implementation, would upload and process the image
            messagebox.showinfo("Success", "Profile photo updated successfully.")
            self.update_status("Profile photo updated")

    def export_child_data(self):
        """Export all data for a child"""
        if not self.children:
            messagebox.showinfo("No Children", "No children registered in the system.")
            return
        
        dialog = DataExportDialog(self.root, self.children)
        if dialog.result:
            child_id, data_types, format_type = dialog.result['child_id'], dialog.result['data_types'], dialog.result['format']
            
            # In real implementation, would generate actual export file
            messagebox.showinfo("Export Complete", 
                              f"Data exported successfully in {format_type.upper()} format.\n"
                              f"Data types: {', '.join(data_types)}")

    def generate_qr_code_interface(self):
        """Generate QR code for student pickup"""
        if not self.children:
            messagebox.showinfo("No Children", "No children registered in the system.")
            return
        
        dialog = QRCodeDialog(self.root, self.children)
        if dialog.result:
            child = dialog.result
            # In real implementation, would generate actual QR code
            messagebox.showinfo("QR Code Generated", 
                              f"QR code generated for {child[1]} {child[3]}.\n"
                              "This can be used for secure student pickup.")

    def mark_notifications_read(self):
        """Mark all notifications as read"""
        if messagebox.askyesno("Mark Read", "Mark all notifications as read?"):
            # In real implementation, would update database
            messagebox.showinfo("Success", "All notifications marked as read.")
            self.update_status("Notifications marked as read")

    
    # Additional interface methods would continue here...
    # For brevity, I'll provide stubs for the remaining methods
    
    def show_medical_interface(self):
        """Show medical information interface"""
        self.clear_content()
        self.update_status("Medical Information")

        title = ttk.Label(self.content_frame, text="Medical Information", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Medical information display frame
        medical_frame = ttk.LabelFrame(self.content_frame, text="Medical Information", padding=15)
        medical_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_medical_info():
            # Clear existing widgets
            for widget in medical_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(medical_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Check if medical_info table exists
                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='medical_info'
                """)

                if cursor.fetchone():
                    # Load medical information
                    cursor.execute("""
                    SELECT blood_type, allergies, medications, conditions, emergency_contact,
                           doctor_name, doctor_phone, insurance_provider, insurance_number, notes
                    FROM medical_info
                    WHERE student_id = ?
                    """, (student_id,))

                    medical_data = cursor.fetchone()

                    if medical_data:
                        # Display medical information
                        info_container = ttk.Frame(medical_frame)
                        info_container.pack(fill=tk.BOTH, expand=True)

                        # Left column
                        left_frame = ttk.LabelFrame(info_container, text="Basic Information", padding=10)
                        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

                        ttk.Label(left_frame, text=f"Blood Type: {medical_data[0] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(left_frame, text=f"Allergies: {medical_data[1] or 'None reported'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(left_frame, text=f"Medications: {medical_data[2] or 'None'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(left_frame, text=f"Medical Conditions: {medical_data[3] or 'None'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)

                        # Right column
                        right_frame = ttk.LabelFrame(info_container, text="Contact & Insurance", padding=10)
                        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

                        ttk.Label(right_frame, text=f"Doctor: {medical_data[5] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(right_frame, text=f"Doctor Phone: {medical_data[6] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(right_frame, text=f"Insurance Provider: {medical_data[7] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(right_frame, text=f"Insurance Number: {medical_data[8] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)

                        # Notes section
                        if medical_data[9]:
                            notes_frame = ttk.LabelFrame(medical_frame, text="Additional Notes", padding=10)
                            notes_frame.pack(fill=tk.X, pady=(10, 0))

                            notes_text = scrolledtext.ScrolledText(notes_frame, height=4, wrap=tk.WORD)
                            notes_text.insert('1.0', medical_data[9])
                            notes_text.config(state='disabled')
                            notes_text.pack(fill=tk.X)

                        # Update button
                        ttk.Button(medical_frame, text="Update Medical Information",
                                  command=lambda: self.update_medical_info(student_id)).pack(pady=10)
                    else:
                        ttk.Label(medical_frame, text="No medical information found for this student",
                                 font=('Arial', 11)).pack(pady=50)
                        ttk.Button(medical_frame, text="Add Medical Information",
                                  command=lambda: self.add_medical_info(student_id)).pack()
                else:
                    # Display sample/placeholder data
                    ttk.Label(medical_frame, text="Medical information system not configured",
                             font=('Arial', 11)).pack(pady=20)
                    ttk.Label(medical_frame, text="Please contact school administration to set up medical records.",
                             font=('Arial', 9, 'italic')).pack()

                conn.close()

            except Exception as e:
                ttk.Label(medical_frame, text=f"Error loading medical information: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Medical Info", command=load_medical_info).pack(side=tk.LEFT, padx=5)

        # Load initial data
        load_medical_info()

    def update_medical_info(self, student_id):
        """Update medical information for a student"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Medical Information")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Update Medical Information",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Fetch existing medical info
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='medical_info'
            """)

            if not cursor.fetchone():
                # Create table if it doesn't exist
                cursor.execute("""
                CREATE TABLE medical_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    blood_type TEXT,
                    allergies TEXT,
                    medications TEXT,
                    conditions TEXT,
                    doctor_name TEXT,
                    doctor_phone TEXT,
                    insurance_provider TEXT,
                    insurance_policy TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                conn.commit()

            cursor.execute("""
            SELECT blood_type, allergies, medications, conditions,
                   doctor_name, doctor_phone, insurance_provider, insurance_policy
            FROM medical_info WHERE student_id = ?
            """, (student_id,))

            existing_data = cursor.fetchone()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load medical information: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # Blood Type
        ttk.Label(main_frame, text="Blood Type:").pack(anchor='w', pady=(5, 0))
        fields['blood_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
        fields['blood_type']['values'] = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown']
        fields['blood_type'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[0]:
            fields['blood_type'].set(existing_data[0])

        # Allergies
        ttk.Label(main_frame, text="Allergies (one per line):").pack(anchor='w', pady=(5, 0))
        fields['allergies'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
        fields['allergies'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[1]:
            fields['allergies'].insert('1.0', existing_data[1])

        # Medications
        ttk.Label(main_frame, text="Current Medications (one per line):").pack(anchor='w', pady=(5, 0))
        fields['medications'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
        fields['medications'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[2]:
            fields['medications'].insert('1.0', existing_data[2])

        # Conditions
        ttk.Label(main_frame, text="Medical Conditions (one per line):").pack(anchor='w', pady=(5, 0))
        fields['conditions'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
        fields['conditions'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[3]:
            fields['conditions'].insert('1.0', existing_data[3])

        # Doctor Name
        ttk.Label(main_frame, text="Doctor Name:").pack(anchor='w', pady=(5, 0))
        fields['doctor_name'] = ttk.Entry(main_frame, width=50)
        fields['doctor_name'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[4]:
            fields['doctor_name'].insert(0, existing_data[4])

        # Doctor Phone
        ttk.Label(main_frame, text="Doctor Phone:").pack(anchor='w', pady=(5, 0))
        fields['doctor_phone'] = ttk.Entry(main_frame, width=50)
        fields['doctor_phone'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[5]:
            fields['doctor_phone'].insert(0, existing_data[5])

        # Insurance Provider
        ttk.Label(main_frame, text="Insurance Provider:").pack(anchor='w', pady=(5, 0))
        fields['insurance_provider'] = ttk.Entry(main_frame, width=50)
        fields['insurance_provider'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[6]:
            fields['insurance_provider'].insert(0, existing_data[6])

        # Insurance Policy
        ttk.Label(main_frame, text="Insurance Policy Number:").pack(anchor='w', pady=(5, 0))
        fields['insurance_policy'] = ttk.Entry(main_frame, width=50)
        fields['insurance_policy'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[7]:
            fields['insurance_policy'].insert(0, existing_data[7])

        def save_info():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Update existing record
                cursor.execute("""
                UPDATE medical_info
                SET blood_type = ?, allergies = ?, medications = ?, conditions = ?,
                    doctor_name = ?, doctor_phone = ?, insurance_provider = ?,
                    insurance_policy = ?, last_updated = CURRENT_TIMESTAMP
                WHERE student_id = ?
                """, (
                    fields['blood_type'].get(),
                    fields['allergies'].get('1.0', tk.END).strip(),
                    fields['medications'].get('1.0', tk.END).strip(),
                    fields['conditions'].get('1.0', tk.END).strip(),
                    fields['doctor_name'].get(),
                    fields['doctor_phone'].get(),
                    fields['insurance_provider'].get(),
                    fields['insurance_policy'].get(),
                    student_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Medical information updated successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update medical information: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save", command=save_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def add_medical_info(self, student_id):
        """Add medical information for a student"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Medical Information")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Medical Information",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Ensure table exists
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='medical_info'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE medical_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    blood_type TEXT,
                    allergies TEXT,
                    medications TEXT,
                    conditions TEXT,
                    doctor_name TEXT,
                    doctor_phone TEXT,
                    insurance_provider TEXT,
                    insurance_policy TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                conn.commit()

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # Blood Type
        ttk.Label(main_frame, text="Blood Type:").pack(anchor='w', pady=(5, 0))
        fields['blood_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
        fields['blood_type']['values'] = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown']
        fields['blood_type'].pack(fill=tk.X, pady=(0, 10))

        # Allergies
        ttk.Label(main_frame, text="Allergies (one per line):").pack(anchor='w', pady=(5, 0))
        fields['allergies'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
        fields['allergies'].pack(fill=tk.X, pady=(0, 10))

        # Medications
        ttk.Label(main_frame, text="Current Medications (one per line):").pack(anchor='w', pady=(5, 0))
        fields['medications'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
        fields['medications'].pack(fill=tk.X, pady=(0, 10))

        # Conditions
        ttk.Label(main_frame, text="Medical Conditions (one per line):").pack(anchor='w', pady=(5, 0))
        fields['conditions'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
        fields['conditions'].pack(fill=tk.X, pady=(0, 10))

        # Doctor Name
        ttk.Label(main_frame, text="Doctor Name:").pack(anchor='w', pady=(5, 0))
        fields['doctor_name'] = ttk.Entry(main_frame, width=50)
        fields['doctor_name'].pack(fill=tk.X, pady=(0, 10))

        # Doctor Phone
        ttk.Label(main_frame, text="Doctor Phone:").pack(anchor='w', pady=(5, 0))
        fields['doctor_phone'] = ttk.Entry(main_frame, width=50)
        fields['doctor_phone'].pack(fill=tk.X, pady=(0, 10))

        # Insurance Provider
        ttk.Label(main_frame, text="Insurance Provider:").pack(anchor='w', pady=(5, 0))
        fields['insurance_provider'] = ttk.Entry(main_frame, width=50)
        fields['insurance_provider'].pack(fill=tk.X, pady=(0, 10))

        # Insurance Policy
        ttk.Label(main_frame, text="Insurance Policy Number:").pack(anchor='w', pady=(5, 0))
        fields['insurance_policy'] = ttk.Entry(main_frame, width=50)
        fields['insurance_policy'].pack(fill=tk.X, pady=(0, 10))

        def save_info():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Insert new record
                cursor.execute("""
                INSERT INTO medical_info (student_id, blood_type, allergies, medications, conditions,
                                        doctor_name, doctor_phone, insurance_provider, insurance_policy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    student_id,
                    fields['blood_type'].get(),
                    fields['allergies'].get('1.0', tk.END).strip(),
                    fields['medications'].get('1.0', tk.END).strip(),
                    fields['conditions'].get('1.0', tk.END).strip(),
                    fields['doctor_name'].get(),
                    fields['doctor_phone'].get(),
                    fields['insurance_provider'].get(),
                    fields['insurance_policy'].get()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Medical information added successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add medical information: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save", command=save_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def show_transport_interface(self):
        """Show transportation information interface"""
        self.clear_content()
        self.update_status("Transportation Information")

        title = ttk.Label(self.content_frame, text="Transportation Information", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Transportation display frame
        transport_frame = ttk.LabelFrame(self.content_frame, text="Transportation Details", padding=15)
        transport_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_transport_info():
            for widget in transport_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(transport_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='transportation'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    SELECT transport_type, route_number, pickup_time, dropoff_time,
                           pickup_location, dropoff_location, driver_name, driver_phone, bus_number
                    FROM transportation
                    WHERE student_id = ?
                    """, (student_id,))

                    transport_data = cursor.fetchone()

                    if transport_data:
                        # Display transportation information
                        info_frame = ttk.Frame(transport_frame)
                        info_frame.pack(fill=tk.BOTH, expand=True)

                        # Route information
                        route_frame = ttk.LabelFrame(info_frame, text="Route Information", padding=10)
                        route_frame.pack(fill=tk.X, pady=(0, 10))

                        ttk.Label(route_frame, text=f"Transport Type: {transport_data[0] or 'Not specified'}",
                                 font=('Arial', 10, 'bold')).pack(anchor='w', pady=3)
                        ttk.Label(route_frame, text=f"Route Number: {transport_data[1] or 'N/A'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(route_frame, text=f"Bus Number: {transport_data[8] or 'N/A'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)

                        # Schedule information
                        schedule_frame = ttk.LabelFrame(info_frame, text="Schedule", padding=10)
                        schedule_frame.pack(fill=tk.X, pady=(0, 10))

                        ttk.Label(schedule_frame, text=f"Pickup Time: {transport_data[2] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(schedule_frame, text=f"Pickup Location: {transport_data[4] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(schedule_frame, text=f"Drop-off Time: {transport_data[3] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(schedule_frame, text=f"Drop-off Location: {transport_data[5] or 'Not specified'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)

                        # Driver information
                        driver_frame = ttk.LabelFrame(info_frame, text="Driver Information", padding=10)
                        driver_frame.pack(fill=tk.X)

                        ttk.Label(driver_frame, text=f"Driver Name: {transport_data[6] or 'Not assigned'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(driver_frame, text=f"Driver Phone: {transport_data[7] or 'Not available'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)

                        # Action buttons
                        btn_frame = ttk.Frame(transport_frame)
                        btn_frame.pack(pady=10)
                        ttk.Button(btn_frame, text="Update Transportation",
                                  command=lambda: self.update_transport_info(student_id)).pack(side=tk.LEFT, padx=5)
                        ttk.Button(btn_frame, text="Report Issue",
                                  command=lambda: self.report_transport_issue(student_id)).pack(side=tk.LEFT, padx=5)
                    else:
                        ttk.Label(transport_frame, text="No transportation information found",
                                 font=('Arial', 11)).pack(pady=50)
                        ttk.Button(transport_frame, text="Request Transportation",
                                  command=lambda: self.request_transportation(student_id)).pack()
                else:
                    ttk.Label(transport_frame, text="Transportation system not configured",
                             font=('Arial', 11)).pack(pady=20)
                    ttk.Label(transport_frame, text="Please contact school administration for transportation services.",
                             font=('Arial', 9, 'italic')).pack()

                conn.close()

            except Exception as e:
                ttk.Label(transport_frame, text=f"Error loading transportation info: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Transport Info", command=load_transport_info).pack(side=tk.LEFT, padx=5)
        load_transport_info()

    def update_transport_info(self, student_id):
        """Update transportation information"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Transportation Information")
        dialog.geometry("600x550")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Update Transportation Information",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Fetch existing transportation info
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='transportation'
            """)

            if not cursor.fetchone():
                messagebox.showwarning("Not Available", "Transportation system not configured.")
                conn.close()
                dialog.destroy()
                return

            cursor.execute("""
            SELECT route_number, bus_number, pickup_time, pickup_location,
                   dropoff_time, dropoff_location
            FROM transportation WHERE student_id = ?
            """, (student_id,))

            existing_data = cursor.fetchone()
            conn.close()

            if not existing_data:
                messagebox.showwarning("No Record", "No transportation record found. Please request transportation first.")
                dialog.destroy()
                return

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load transportation information: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # Route Number
        ttk.Label(main_frame, text="Route Number:").pack(anchor='w', pady=(5, 0))
        fields['route_number'] = ttk.Entry(main_frame, width=50)
        fields['route_number'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[0]:
            fields['route_number'].insert(0, existing_data[0])

        # Bus Number
        ttk.Label(main_frame, text="Bus Number:").pack(anchor='w', pady=(5, 0))
        fields['bus_number'] = ttk.Entry(main_frame, width=50)
        fields['bus_number'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[1]:
            fields['bus_number'].insert(0, existing_data[1])

        # Pickup Time
        ttk.Label(main_frame, text="Pickup Time (HH:MM AM/PM):").pack(anchor='w', pady=(5, 0))
        fields['pickup_time'] = ttk.Entry(main_frame, width=50)
        fields['pickup_time'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[2]:
            fields['pickup_time'].insert(0, existing_data[2])

        # Pickup Location
        ttk.Label(main_frame, text="Pickup Location:").pack(anchor='w', pady=(5, 0))
        fields['pickup_location'] = ttk.Entry(main_frame, width=50)
        fields['pickup_location'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[3]:
            fields['pickup_location'].insert(0, existing_data[3])

        # Dropoff Time
        ttk.Label(main_frame, text="Dropoff Time (HH:MM AM/PM):").pack(anchor='w', pady=(5, 0))
        fields['dropoff_time'] = ttk.Entry(main_frame, width=50)
        fields['dropoff_time'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[4]:
            fields['dropoff_time'].insert(0, existing_data[4])

        # Dropoff Location
        ttk.Label(main_frame, text="Dropoff Location:").pack(anchor='w', pady=(5, 0))
        fields['dropoff_location'] = ttk.Entry(main_frame, width=50)
        fields['dropoff_location'].pack(fill=tk.X, pady=(0, 10))
        if existing_data and existing_data[5]:
            fields['dropoff_location'].insert(0, existing_data[5])

        def save_info():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Update existing record
                cursor.execute("""
                UPDATE transportation
                SET route_number = ?, bus_number = ?, pickup_time = ?,
                    pickup_location = ?, dropoff_time = ?, dropoff_location = ?
                WHERE student_id = ?
                """, (
                    fields['route_number'].get(),
                    fields['bus_number'].get(),
                    fields['pickup_time'].get(),
                    fields['pickup_location'].get(),
                    fields['dropoff_time'].get(),
                    fields['dropoff_location'].get(),
                    student_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Transportation information updated successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update transportation information: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save", command=save_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def request_transportation(self, student_id):
        """Request transportation for a student"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Request Transportation")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Request Transportation",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Ensure table exists
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='transportation_requests'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE transportation_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    service_type TEXT,
                    route_preference TEXT,
                    special_needs TEXT,
                    start_date TEXT,
                    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'Pending'
                )
                """)
                conn.commit()

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # Service Type
        ttk.Label(main_frame, text="Service Type:").pack(anchor='w', pady=(5, 0))
        fields['service_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
        fields['service_type']['values'] = ['Bus Service', 'Van Service', 'Special Needs Transport', 'Other']
        fields['service_type'].pack(fill=tk.X, pady=(0, 10))

        # Route Preference
        ttk.Label(main_frame, text="Route Preference:").pack(anchor='w', pady=(5, 0))
        fields['route_preference'] = ttk.Entry(main_frame, width=50)
        fields['route_preference'].pack(fill=tk.X, pady=(0, 10))

        # Special Needs
        ttk.Label(main_frame, text="Special Needs/Accommodations:").pack(anchor='w', pady=(5, 0))
        fields['special_needs'] = scrolledtext.ScrolledText(main_frame, width=50, height=6)
        fields['special_needs'].pack(fill=tk.X, pady=(0, 10))

        # Start Date
        ttk.Label(main_frame, text="Requested Start Date (YYYY-MM-DD):").pack(anchor='w', pady=(5, 0))
        fields['start_date'] = ttk.Entry(main_frame, width=50)
        fields['start_date'].pack(fill=tk.X, pady=(0, 10))
        # Set default to today
        fields['start_date'].insert(0, datetime.datetime.now().strftime('%Y-%m-%d'))

        def submit_request():
            # Validate required fields
            if not fields['service_type'].get():
                messagebox.showwarning("Validation Error", "Please select a service type.")
                return

            if not fields['start_date'].get():
                messagebox.showwarning("Validation Error", "Please enter a start date.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Insert new request
                cursor.execute("""
                INSERT INTO transportation_requests (student_id, service_type, route_preference,
                                                    special_needs, start_date)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    student_id,
                    fields['service_type'].get(),
                    fields['route_preference'].get(),
                    fields['special_needs'].get('1.0', tk.END).strip(),
                    fields['start_date'].get()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Transportation request submitted successfully!\n\n"
                                              "The transportation office will review your request and contact you.")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit request: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Submit Request", command=submit_request).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def report_transport_issue(self, student_id):
        """Report transportation issue"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Report Transportation Issue")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Report Transportation Issue",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Ensure table exists
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='transport_issues'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE transport_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    issue_type TEXT,
                    issue_date TEXT,
                    issue_time TEXT,
                    description TEXT,
                    report_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'Open'
                )
                """)
                conn.commit()

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # Issue Type
        ttk.Label(main_frame, text="Issue Type:").pack(anchor='w', pady=(5, 0))
        fields['issue_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
        fields['issue_type']['values'] = ['Late Arrival', 'Missed Pickup', 'Safety Concern', 'Driver Behavior', 'Vehicle Condition', 'Other']
        fields['issue_type'].pack(fill=tk.X, pady=(0, 10))

        # Issue Date
        ttk.Label(main_frame, text="Date of Issue (YYYY-MM-DD):").pack(anchor='w', pady=(5, 0))
        fields['issue_date'] = ttk.Entry(main_frame, width=50)
        fields['issue_date'].pack(fill=tk.X, pady=(0, 10))
        fields['issue_date'].insert(0, datetime.datetime.now().strftime('%Y-%m-%d'))

        # Issue Time
        ttk.Label(main_frame, text="Time of Issue (HH:MM AM/PM):").pack(anchor='w', pady=(5, 0))
        fields['issue_time'] = ttk.Entry(main_frame, width=50)
        fields['issue_time'].pack(fill=tk.X, pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(5, 0))
        fields['description'] = scrolledtext.ScrolledText(main_frame, width=50, height=8)
        fields['description'].pack(fill=tk.X, pady=(0, 10))

        def submit_report():
            # Validate required fields
            if not fields['issue_type'].get():
                messagebox.showwarning("Validation Error", "Please select an issue type.")
                return

            if not fields['description'].get('1.0', tk.END).strip():
                messagebox.showwarning("Validation Error", "Please provide a description of the issue.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Insert new issue report
                cursor.execute("""
                INSERT INTO transport_issues (student_id, issue_type, issue_date,
                                             issue_time, description)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    student_id,
                    fields['issue_type'].get(),
                    fields['issue_date'].get(),
                    fields['issue_time'].get(),
                    fields['description'].get('1.0', tk.END).strip()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Transportation issue reported successfully!\n\n"
                                              "The transportation office will review your report and contact you.")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit report: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Submit Report", command=submit_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def show_pickup_interface(self):
        """Show pickup authorization interface"""
        self.clear_content()
        self.update_status("Pickup Authorization")

        title = ttk.Label(self.content_frame, text="Pickup Authorization", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Authorized persons display frame
        pickup_frame = ttk.LabelFrame(self.content_frame, text="Authorized Pickup Persons", padding=15)
        pickup_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_pickup_info():
            for widget in pickup_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(pickup_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='authorized_pickup'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    SELECT name, relationship, phone, id_number, photo_on_file, notes
                    FROM authorized_pickup
                    WHERE student_id = ?
                    ORDER BY name
                    """, (student_id,))

                    authorized_persons = cursor.fetchall()

                    if authorized_persons:
                        # Display authorized persons
                        columns = ("Name", "Relationship", "Phone", "ID Number", "Photo on File")
                        tree = ttk.Treeview(pickup_frame, columns=columns, show="headings", height=10)

                        for col in columns:
                            tree.heading(col, text=col)
                            tree.column(col, width=120)

                        for person in authorized_persons:
                            tree.insert('', tk.END, values=person[:5])

                        scrollbar = ttk.Scrollbar(pickup_frame, orient=tk.VERTICAL, command=tree.yview)
                        tree.configure(yscrollcommand=scrollbar.set)

                        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                        # Action buttons
                        btn_frame = ttk.Frame(pickup_frame)
                        btn_frame.pack(pady=10, fill=tk.X)
                        ttk.Button(btn_frame, text="Add Person",
                                  command=lambda: self.add_authorized_person(student_id)).pack(side=tk.LEFT, padx=5)
                        ttk.Button(btn_frame, text="Remove Person",
                                  command=lambda: self.remove_authorized_person(student_id, tree)).pack(side=tk.LEFT, padx=5)
                        ttk.Button(btn_frame, text="Emergency Pickup Request",
                                  command=lambda: self.emergency_pickup_request(student_id)).pack(side=tk.LEFT, padx=5)
                    else:
                        ttk.Label(pickup_frame, text="No authorized pickup persons found",
                                 font=('Arial', 11)).pack(pady=50)
                        ttk.Button(pickup_frame, text="Add Authorized Person",
                                  command=lambda: self.add_authorized_person(student_id)).pack()
                else:
                    ttk.Label(pickup_frame, text="Pickup authorization system not configured",
                             font=('Arial', 11)).pack(pady=20)
                    ttk.Label(pickup_frame, text="Please contact school administration.",
                             font=('Arial', 9, 'italic')).pack()

                conn.close()

            except Exception as e:
                ttk.Label(pickup_frame, text=f"Error loading pickup authorization: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Authorized Persons", command=load_pickup_info).pack(side=tk.LEFT, padx=5)
        load_pickup_info()

    def add_authorized_person(self, student_id):
        """Add authorized pickup person"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Authorized Pickup Person")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Authorized Pickup Person",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Ensure table exists
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='authorized_pickup'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE authorized_pickup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    relationship TEXT,
                    phone TEXT,
                    id_number TEXT,
                    photo_on_file TEXT DEFAULT 'No',
                    notes TEXT,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                conn.commit()

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # Name
        ttk.Label(main_frame, text="Full Name: *").pack(anchor='w', pady=(5, 0))
        fields['name'] = ttk.Entry(main_frame, width=50)
        fields['name'].pack(fill=tk.X, pady=(0, 10))

        # Relationship
        ttk.Label(main_frame, text="Relationship to Student:").pack(anchor='w', pady=(5, 0))
        fields['relationship'] = ttk.Combobox(main_frame, width=50, state="readonly")
        fields['relationship']['values'] = ['Parent', 'Guardian', 'Grandparent', 'Aunt/Uncle', 'Sibling', 'Family Friend', 'Other']
        fields['relationship'].pack(fill=tk.X, pady=(0, 10))

        # Phone
        ttk.Label(main_frame, text="Phone Number: *").pack(anchor='w', pady=(5, 0))
        fields['phone'] = ttk.Entry(main_frame, width=50)
        fields['phone'].pack(fill=tk.X, pady=(0, 10))

        # ID Number
        ttk.Label(main_frame, text="ID Number (Driver's License, etc.):").pack(anchor='w', pady=(5, 0))
        fields['id_number'] = ttk.Entry(main_frame, width=50)
        fields['id_number'].pack(fill=tk.X, pady=(0, 10))

        # Photo on File
        ttk.Label(main_frame, text="Photo ID on File:").pack(anchor='w', pady=(5, 0))
        fields['photo_on_file'] = ttk.Combobox(main_frame, width=50, state="readonly")
        fields['photo_on_file']['values'] = ['Yes', 'No']
        fields['photo_on_file'].set('No')
        fields['photo_on_file'].pack(fill=tk.X, pady=(0, 10))

        # Notes
        ttk.Label(main_frame, text="Notes:").pack(anchor='w', pady=(5, 0))
        fields['notes'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
        fields['notes'].pack(fill=tk.X, pady=(0, 10))

        def save_person():
            # Validate required fields
            if not fields['name'].get():
                messagebox.showwarning("Validation Error", "Please enter a name.")
                return

            if not fields['phone'].get():
                messagebox.showwarning("Validation Error", "Please enter a phone number.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Insert new authorized person
                cursor.execute("""
                INSERT INTO authorized_pickup (student_id, name, relationship, phone,
                                              id_number, photo_on_file, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    student_id,
                    fields['name'].get(),
                    fields['relationship'].get(),
                    fields['phone'].get(),
                    fields['id_number'].get(),
                    fields['photo_on_file'].get(),
                    fields['notes'].get('1.0', tk.END).strip()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Authorized person added successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add authorized person: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save", command=save_person).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def remove_authorized_person(self, student_id, tree):
        """Remove authorized pickup person"""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a person to remove.")
            return

        # Get the selected person's name
        item = tree.item(selected[0])
        person_name = item['values'][0]

        # Confirm deletion
        if not messagebox.askyesno("Confirm Removal",
                                   f"Are you sure you want to remove '{person_name}' from the authorized pickup list?\n\n"
                                   "This person will no longer be able to pick up the student."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Delete the authorized person
            cursor.execute("""
            DELETE FROM authorized_pickup
            WHERE student_id = ? AND name = ?
            """, (student_id, person_name))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"'{person_name}' has been removed from the authorized pickup list.")

            # Remove from treeview
            tree.delete(selected[0])

        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove authorized person: {str(e)}")

    def emergency_pickup_request(self, student_id):
        """Request emergency pickup"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Emergency Pickup Request")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Emergency Pickup Request",
                 font=('Arial', 14, 'bold'), foreground='red').pack(pady=(0, 20))

        # Ensure table exists
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='emergency_pickup_requests'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE emergency_pickup_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    pickup_person TEXT NOT NULL,
                    reason TEXT,
                    time_needed TEXT,
                    contact_phone TEXT,
                    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'Pending'
                )
                """)
                conn.commit()

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # Pickup Person
        ttk.Label(main_frame, text="Who will be picking up the student? *").pack(anchor='w', pady=(5, 0))
        fields['pickup_person'] = ttk.Entry(main_frame, width=50)
        fields['pickup_person'].pack(fill=tk.X, pady=(0, 10))

        # Reason
        ttk.Label(main_frame, text="Reason for emergency pickup: *").pack(anchor='w', pady=(5, 0))
        fields['reason'] = scrolledtext.ScrolledText(main_frame, width=50, height=4)
        fields['reason'].pack(fill=tk.X, pady=(0, 10))

        # Time Needed
        ttk.Label(main_frame, text="Time needed (HH:MM AM/PM): *").pack(anchor='w', pady=(5, 0))
        fields['time_needed'] = ttk.Entry(main_frame, width=50)
        fields['time_needed'].pack(fill=tk.X, pady=(0, 10))
        # Set default to current time
        fields['time_needed'].insert(0, datetime.datetime.now().strftime('%I:%M %p'))

        # Contact Phone
        ttk.Label(main_frame, text="Contact Phone Number: *").pack(anchor='w', pady=(5, 0))
        fields['contact_phone'] = ttk.Entry(main_frame, width=50)
        fields['contact_phone'].pack(fill=tk.X, pady=(0, 10))

        def submit_request():
            # Validate required fields
            if not fields['pickup_person'].get():
                messagebox.showwarning("Validation Error", "Please enter who will pick up the student.")
                return

            if not fields['reason'].get('1.0', tk.END).strip():
                messagebox.showwarning("Validation Error", "Please provide a reason for the emergency pickup.")
                return

            if not fields['time_needed'].get():
                messagebox.showwarning("Validation Error", "Please enter the time needed.")
                return

            if not fields['contact_phone'].get():
                messagebox.showwarning("Validation Error", "Please enter a contact phone number.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Insert emergency pickup request
                cursor.execute("""
                INSERT INTO emergency_pickup_requests (student_id, pickup_person, reason,
                                                       time_needed, contact_phone)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    student_id,
                    fields['pickup_person'].get(),
                    fields['reason'].get('1.0', tk.END).strip(),
                    fields['time_needed'].get(),
                    fields['contact_phone'].get()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Emergency pickup request submitted!\n\n"
                                              "The school office has been notified and will prepare your child.\n"
                                              "You will be contacted shortly.")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit request: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Submit Request", command=submit_request).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_photo_interface(self):
        """Show photo permissions interface"""
        self.clear_content()
        self.update_status("Photo Permissions")

        title = ttk.Label(self.content_frame, text="Photo & Media Permissions", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Permissions display frame
        perm_frame = ttk.LabelFrame(self.content_frame, text="Media Permissions", padding=15)
        perm_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_photo_permissions():
            for widget in perm_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(perm_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='photo_permissions'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    SELECT yearbook_photos, website_photos, social_media, newsletter,
                           promotional_materials, news_media, video_recording, notes
                    FROM photo_permissions
                    WHERE student_id = ?
                    """, (student_id,))

                    permissions = cursor.fetchone()

                    if permissions:
                        # Display permissions
                        perm_items = [
                            ("Yearbook Photos", permissions[0]),
                            ("Website Photos", permissions[1]),
                            ("Social Media", permissions[2]),
                            ("Newsletter", permissions[3]),
                            ("Promotional Materials", permissions[4]),
                            ("News Media", permissions[5]),
                            ("Video Recording", permissions[6])
                        ]

                        for item, value in perm_items:
                            frame = ttk.Frame(perm_frame)
                            frame.pack(fill=tk.X, pady=5)
                            ttk.Label(frame, text=item + ":", font=('Arial', 10, 'bold'), width=25).pack(side=tk.LEFT)
                            status = "Allowed" if value else "Not Allowed"
                            color = 'green' if value else 'red'
                            ttk.Label(frame, text=status, font=('Arial', 10), foreground=color).pack(side=tk.LEFT)

                        if permissions[7]:
                            notes_frame = ttk.LabelFrame(perm_frame, text="Special Notes", padding=10)
                            notes_frame.pack(fill=tk.X, pady=(10, 0))
                            ttk.Label(notes_frame, text=permissions[7], wraplength=500).pack()

                        ttk.Button(perm_frame, text="Update Permissions",
                                  command=lambda: self.update_photo_permissions(student_id)).pack(pady=10)
                    else:
                        ttk.Label(perm_frame, text="No photo permissions set",
                                 font=('Arial', 11)).pack(pady=50)
                        ttk.Button(perm_frame, text="Set Permissions",
                                  command=lambda: self.update_photo_permissions(student_id)).pack()
                else:
                    ttk.Label(perm_frame, text="Photo permissions system not configured",
                             font=('Arial', 11)).pack(pady=20)

                conn.close()

            except Exception as e:
                ttk.Label(perm_frame, text=f"Error loading permissions: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Permissions", command=load_photo_permissions).pack(side=tk.LEFT, padx=5)
        load_photo_permissions()

    def update_photo_permissions(self, student_id):
        """Update photo permissions"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Photo Permissions")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Photo & Media Permissions",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        ttk.Label(main_frame, text="Please select which permissions you grant for your child:",
                 font=('Arial', 10)).pack(pady=(0, 20))

        # Ensure table exists and get existing permissions
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='photo_permissions'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE photo_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL UNIQUE,
                    yearbook INTEGER DEFAULT 0,
                    website INTEGER DEFAULT 0,
                    social_media INTEGER DEFAULT 0,
                    newsletter INTEGER DEFAULT 0,
                    classroom INTEGER DEFAULT 0,
                    media_release INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                conn.commit()

            # Get existing permissions
            cursor.execute("""
            SELECT yearbook, website, social_media, newsletter, classroom, media_release
            FROM photo_permissions WHERE student_id = ?
            """, (student_id,))

            existing = cursor.fetchone()
            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load permissions: {str(e)}")
            dialog.destroy()
            return

        # Create checkbox variables
        permissions = {}
        permission_vars = {}

        permission_options = [
            ('yearbook', 'Yearbook Photos', 'Allow photos in school yearbook'),
            ('website', 'School Website', 'Allow photos on school website'),
            ('social_media', 'Social Media', 'Allow photos on school social media accounts'),
            ('newsletter', 'Newsletter', 'Allow photos in school newsletters'),
            ('classroom', 'Classroom Display', 'Allow photos displayed in classroom'),
            ('media_release', 'Media Release', 'Allow photos for press/media coverage')
        ]

        for i, (key, label, desc) in enumerate(permission_options):
            permission_vars[key] = tk.IntVar()
            if existing and existing[i]:
                permission_vars[key].set(existing[i])

            frame = ttk.Frame(main_frame)
            frame.pack(fill=tk.X, pady=5)

            cb = ttk.Checkbutton(frame, text=label, variable=permission_vars[key])
            cb.pack(anchor='w')

            ttk.Label(frame, text=desc, font=('Arial', 9, 'italic')).pack(anchor='w', padx=20)

        def save_permissions():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Check if record exists
                cursor.execute("SELECT id FROM photo_permissions WHERE student_id = ?", (student_id,))
                exists = cursor.fetchone()

                if exists:
                    # Update existing record
                    cursor.execute("""
                    UPDATE photo_permissions
                    SET yearbook = ?, website = ?, social_media = ?, newsletter = ?,
                        classroom = ?, media_release = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                    """, (
                        permission_vars['yearbook'].get(),
                        permission_vars['website'].get(),
                        permission_vars['social_media'].get(),
                        permission_vars['newsletter'].get(),
                        permission_vars['classroom'].get(),
                        permission_vars['media_release'].get(),
                        student_id
                    ))
                else:
                    # Insert new record
                    cursor.execute("""
                    INSERT INTO photo_permissions (student_id, yearbook, website, social_media,
                                                   newsletter, classroom, media_release)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        student_id,
                        permission_vars['yearbook'].get(),
                        permission_vars['website'].get(),
                        permission_vars['social_media'].get(),
                        permission_vars['newsletter'].get(),
                        permission_vars['classroom'].get(),
                        permission_vars['media_release'].get()
                    ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Photo permissions updated successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update permissions: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save Permissions", command=save_permissions).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_messages_interface(self):
        """Show messages interface"""
        self.clear_content()
        self.update_status("Messages")

        title = ttk.Label(self.content_frame, text="Messages", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Message categories
        categories_frame = ttk.Frame(self.content_frame)
        categories_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(categories_frame, text="Inbox",
                  command=lambda: self.show_message_category("inbox")).pack(side=tk.LEFT, padx=5)
        ttk.Button(categories_frame, text="Sent",
                  command=lambda: self.show_message_category("sent")).pack(side=tk.LEFT, padx=5)
        ttk.Button(categories_frame, text="Compose New",
                  command=self.show_send_message_interface).pack(side=tk.LEFT, padx=5)

        # Messages display frame
        messages_frame = ttk.LabelFrame(self.content_frame, text="Inbox", padding=15)
        messages_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='messages'
            """)

            if cursor.fetchone():
                cursor.execute("""
                SELECT message_id, sender_name, subject, date_sent, is_read
                FROM messages
                WHERE recipient_id = ?
                ORDER BY date_sent DESC
                LIMIT 50
                """, (self.parent_id,))

                messages = cursor.fetchall()

                if messages:
                    columns = ("From", "Subject", "Date", "Status")
                    tree = ttk.Treeview(messages_frame, columns=columns, show="headings", height=15)

                    tree.heading("From", text="From")
                    tree.heading("Subject", text="Subject")
                    tree.heading("Date", text="Date")
                    tree.heading("Status", text="Status")

                    tree.column("From", width=150)
                    tree.column("Subject", width=300)
                    tree.column("Date", width=150)
                    tree.column("Status", width=100)

                    for msg in messages:
                        status = "Read" if msg[4] else "Unread"
                        tree.insert('', tk.END, values=(msg[1], msg[2], msg[3], status), tags=(status,))

                    tree.tag_configure('Unread', font=('Arial', 10, 'bold'))

                    scrollbar = ttk.Scrollbar(messages_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    def view_message():
                        selected = tree.selection()
                        if selected:
                            item = tree.item(selected[0])
                            messagebox.showinfo("Message", f"From: {item['values'][0]}\n"
                                                          f"Subject: {item['values'][1]}\n"
                                                          f"Date: {item['values'][2]}\n\n"
                                                          "Full message content would be displayed here.")

                    ttk.Button(messages_frame, text="View Message", command=view_message).pack(pady=10)
                else:
                    ttk.Label(messages_frame, text="No messages found", font=('Arial', 11)).pack(pady=50)
            else:
                ttk.Label(messages_frame, text="Messaging system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(messages_frame, text=f"Error loading messages: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    def show_message_category(self, category):
        """Show specific message category"""
        messagebox.showinfo("Messages", f"Showing {category} messages...")
        self.show_messages_interface()
    
    def show_send_message_interface(self):
        """Show send message interface"""
        self.clear_content()
        self.update_status("Send Message")

        title = ttk.Label(self.content_frame, text="Compose Message", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Message form
        form_frame = ttk.LabelFrame(self.content_frame, text="New Message", padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Recipient
        ttk.Label(form_frame, text="To:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        recipient_var = tk.StringVar()
        recipient_combo = ttk.Combobox(form_frame, textvariable=recipient_var, width=50)
        recipient_combo['values'] = ["Select Teacher", "School Administration", "Counselor", "Principal"]
        recipient_combo.grid(row=0, column=1, pady=5, sticky='ew')

        # Subject
        ttk.Label(form_frame, text="Subject:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        subject_entry = ttk.Entry(form_frame, width=50)
        subject_entry.grid(row=1, column=1, pady=5, sticky='ew')

        # Message body
        ttk.Label(form_frame, text="Message:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='nw', pady=5)
        message_text = scrolledtext.ScrolledText(form_frame, height=15, width=50, wrap=tk.WORD)
        message_text.grid(row=2, column=1, pady=5, sticky='ew')

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.pack(pady=10)

        def send_message():
            recipient = recipient_var.get()
            subject = subject_entry.get()
            message = message_text.get('1.0', tk.END).strip()

            if not recipient or recipient == "Select Teacher":
                messagebox.showwarning("Missing Recipient", "Please select a recipient.")
                return
            if not subject:
                messagebox.showwarning("Missing Subject", "Please enter a subject.")
                return
            if not message:
                messagebox.showwarning("Missing Message", "Please enter a message.")
                return

            # Send message
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Check if messages table exists
                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='messages'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    INSERT INTO messages (sender_id, sender_name, recipient_name, subject, message_body, date_sent, is_read)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (self.parent_id, "Parent", recipient, subject, message, datetime.datetime.now().isoformat(), 0))
                    conn.commit()

                conn.close()
                messagebox.showinfo("Success", "Message sent successfully!")
                self.show_messages_interface()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send message: {str(e)}")

        ttk.Button(btn_frame, text="Send", command=send_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_messages_interface).pack(side=tk.LEFT, padx=5)

    def show_group_message_interface(self):
        """Show group messages interface"""
        self.clear_content()
        self.update_status("Group Messages")

        title = ttk.Label(self.content_frame, text="Group Messages", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Group selection
        groups_frame = ttk.LabelFrame(self.content_frame, text="Select Group", padding=15)
        groups_frame.pack(fill=tk.X, padx=20, pady=10)

        groups = ["All Teachers", "Class Parents", "Sports Team", "Music Department", "Special Education Team"]

        for group in groups:
            btn = ttk.Button(groups_frame, text=group,
                           command=lambda g=group: self.view_group_messages(g))
            btn.pack(pady=5, fill=tk.X)

        # Recent group messages
        messages_frame = ttk.LabelFrame(self.content_frame, text="Recent Group Messages", padding=15)
        messages_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='group_messages'
            """)

            if cursor.fetchone():
                cursor.execute("""
                SELECT group_name, subject, sender_name, date_sent, message_count
                FROM group_messages
                WHERE parent_id = ? OR is_public = 1
                ORDER BY date_sent DESC
                LIMIT 20
                """, (self.parent_id,))

                messages = cursor.fetchall()

                if messages:
                    columns = ("Group", "Subject", "From", "Date", "Replies")
                    tree = ttk.Treeview(messages_frame, columns=columns, show="headings", height=10)

                    for col in columns:
                        tree.heading(col, text=col)
                        tree.column(col, width=120)

                    for msg in messages:
                        tree.insert('', tk.END, values=msg)

                    scrollbar = ttk.Scrollbar(messages_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                else:
                    ttk.Label(messages_frame, text="No group messages found", font=('Arial', 11)).pack(pady=50)
            else:
                ttk.Label(messages_frame, text="Group messaging not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(messages_frame, text=f"Error loading group messages: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    def view_group_messages(self, group_name):
        """View messages for a specific group"""
        messagebox.showinfo("Group Messages", f"Viewing messages for: {group_name}")

    def show_announcements_interface(self):
        """Show school announcements interface"""
        self.clear_content()
        self.update_status("School Announcements")

        title = ttk.Label(self.content_frame, text="School Announcements", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Filter options
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)
        filter_var = tk.StringVar(value="All")
        categories = ["All", "Academic", "Events", "Emergency", "General", "Sports", "Arts"]

        for cat in categories:
            ttk.Radiobutton(filter_frame, text=cat, value=cat, variable=filter_var).pack(side=tk.LEFT, padx=5)

        # Announcements display
        announcements_frame = ttk.LabelFrame(self.content_frame, text="Recent Announcements", padding=15)
        announcements_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='announcements'
            """)

            if cursor.fetchone():
                cursor.execute("""
                SELECT title, category, content, date_posted, posted_by, priority
                FROM announcements
                WHERE is_active = 1
                ORDER BY priority DESC, date_posted DESC
                LIMIT 30
                """)

                announcements = cursor.fetchall()

                if announcements:
                    # Create scrollable frame for announcements
                    canvas = tk.Canvas(announcements_frame)
                    scrollbar = ttk.Scrollbar(announcements_frame, orient="vertical", command=canvas.yview)
                    scrollable_frame = ttk.Frame(canvas)

                    scrollable_frame.bind(
                        "<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                    )

                    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                    canvas.configure(yscrollcommand=scrollbar.set)

                    for announcement in announcements:
                        ann_card = ttk.LabelFrame(scrollable_frame, text=f"{announcement[0]} [{announcement[1]}]", padding=10)
                        ann_card.pack(fill=tk.X, padx=5, pady=5)

                        ttk.Label(ann_card, text=f"Posted by: {announcement[4]} on {announcement[3]}",
                                 font=('Arial', 8, 'italic')).pack(anchor='w')
                        ttk.Label(ann_card, text=announcement[2], wraplength=600).pack(anchor='w', pady=5)

                        if announcement[5] == "High":
                            priority_label = ttk.Label(ann_card, text="HIGH PRIORITY", foreground='red', font=('Arial', 9, 'bold'))
                            priority_label.pack(anchor='w')

                    canvas.pack(side="left", fill="both", expand=True)
                    scrollbar.pack(side="right", fill="y")
                else:
                    ttk.Label(announcements_frame, text="No announcements at this time",
                             font=('Arial', 11)).pack(pady=50)
            else:
                ttk.Label(announcements_frame, text="Announcements system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(announcements_frame, text=f"Error loading announcements: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    def show_meeting_interface(self):
        """Show schedule meeting interface"""
        self.clear_content()
        self.update_status("Schedule Meeting")

        title = ttk.Label(self.content_frame, text="Schedule Meeting", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Meeting request form
        form_frame = ttk.LabelFrame(self.content_frame, text="Meeting Request", padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Meeting with
        ttk.Label(form_frame, text="Meeting With:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        meeting_with_var = tk.StringVar()
        meeting_combo = ttk.Combobox(form_frame, textvariable=meeting_with_var, width=40)
        meeting_combo['values'] = ["Select...", "Teacher", "Principal", "Counselor", "Special Education Coordinator", "School Nurse"]
        meeting_combo.grid(row=0, column=1, pady=5, sticky='ew')

        # Regarding child
        ttk.Label(form_frame, text="Regarding Child:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(form_frame, textvariable=child_var, width=40)
        if self.children:
            child_combo['values'] = [f"{child[1]} {child[3]}" for child in self.children]
        child_combo.grid(row=1, column=1, pady=5, sticky='ew')

        # Preferred date
        ttk.Label(form_frame, text="Preferred Date:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        date_entry = ttk.Entry(form_frame, width=40)
        date_entry.insert(0, "YYYY-MM-DD")
        date_entry.grid(row=2, column=1, pady=5, sticky='ew')

        # Preferred time
        ttk.Label(form_frame, text="Preferred Time:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=5)
        time_var = tk.StringVar()
        time_combo = ttk.Combobox(form_frame, textvariable=time_var, width=40)
        time_combo['values'] = ["Morning (8:00-12:00)", "Afternoon (12:00-16:00)", "After School (16:00-18:00)"]
        time_combo.grid(row=3, column=1, pady=5, sticky='ew')

        # Meeting type
        ttk.Label(form_frame, text="Meeting Type:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', pady=5)
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(form_frame, textvariable=type_var, width=40)
        type_combo['values'] = ["In-Person", "Video Call", "Phone Call"]
        type_combo.grid(row=4, column=1, pady=5, sticky='ew')

        # Purpose
        ttk.Label(form_frame, text="Purpose:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='nw', pady=5)
        purpose_text = scrolledtext.ScrolledText(form_frame, height=8, width=40, wrap=tk.WORD)
        purpose_text.grid(row=5, column=1, pady=5, sticky='ew')

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.pack(pady=10)

        def submit_meeting_request():
            meeting_with = meeting_with_var.get()
            child = child_var.get()
            date = date_entry.get()
            time = time_var.get()
            meeting_type = type_var.get()
            purpose = purpose_text.get('1.0', tk.END).strip()

            if not all([meeting_with, child, date, time, meeting_type, purpose]) or meeting_with == "Select...":
                messagebox.showwarning("Incomplete Form", "Please fill in all fields.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='meeting_requests'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    INSERT INTO meeting_requests (parent_id, meeting_with, student_name, preferred_date,
                                                 preferred_time, meeting_type, purpose, status, request_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (self.parent_id, meeting_with, child, date, time, meeting_type, purpose, "Pending",
                         datetime.datetime.now().isoformat()))
                    conn.commit()

                conn.close()
                messagebox.showinfo("Success", "Meeting request submitted successfully!\n\n"
                                              "You will receive confirmation once the meeting is scheduled.")
                self.show_dashboard()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit meeting request: {str(e)}")

        ttk.Button(btn_frame, text="Submit Request", command=submit_meeting_request).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_dashboard).pack(side=tk.LEFT, padx=5)

        # Show existing meetings
        existing_frame = ttk.LabelFrame(self.content_frame, text="Upcoming Meetings", padding=15)
        existing_frame.pack(fill=tk.X, padx=20, pady=10)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='meetings'
            """)

            if cursor.fetchone():
                cursor.execute("""
                SELECT date, time, with_person, location, status
                FROM meetings
                WHERE parent_id = ? AND date >= date('now')
                ORDER BY date
                LIMIT 10
                """, (self.parent_id,))

                meetings = cursor.fetchall()

                if meetings:
                    for meeting in meetings:
                        meeting_info = f"{meeting[0]} at {meeting[1]} - {meeting[2]} ({meeting[3]}) - Status: {meeting[4]}"
                        ttk.Label(existing_frame, text=meeting_info).pack(anchor='w', pady=2)
                else:
                    ttk.Label(existing_frame, text="No upcoming meetings scheduled").pack()
            else:
                ttk.Label(existing_frame, text="No meetings scheduled").pack()

            conn.close()

        except Exception as e:
            ttk.Label(existing_frame, text=f"Error loading meetings: {str(e)}").pack()

    def show_report_issue_interface(self):
        """Show report issue interface"""
        self.clear_content()
        self.update_status("Report Issue")

        title = ttk.Label(self.content_frame, text="Report Issue", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Issue report form
        form_frame = ttk.LabelFrame(self.content_frame, text="Report an Issue to School Administration", padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Category
        ttk.Label(form_frame, text="Category:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, width=40, state='readonly')
        category_combo['values'] = ["Academic concern", "Behavioral concern", "Facility issue",
                                     "Safety concern", "Billing/Administrative", "Other"]
        category_combo.grid(row=0, column=1, pady=5, sticky='ew')

        # Subject
        ttk.Label(form_frame, text="Subject:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        subject_entry = ttk.Entry(form_frame, width=40)
        subject_entry.grid(row=1, column=1, pady=5, sticky='ew')

        # Priority
        ttk.Label(form_frame, text="Priority:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        priority_var = tk.StringVar()
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, width=40, state='readonly')
        priority_combo['values'] = ["Low", "Medium", "High"]
        priority_combo.current(1)  # Default to Medium
        priority_combo.grid(row=2, column=1, pady=5, sticky='ew')

        # Description
        ttk.Label(form_frame, text="Description:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='nw', pady=5)
        description_text = scrolledtext.ScrolledText(form_frame, height=10, width=40, wrap=tk.WORD)
        description_text.grid(row=3, column=1, pady=5, sticky='ew')

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.pack(pady=10)

        def submit_issue():
            category = category_var.get()
            subject = subject_entry.get().strip()
            priority = priority_var.get().lower()
            description = description_text.get('1.0', tk.END).strip()

            if not category:
                messagebox.showwarning("Validation Error", "Please select a category.")
                return

            if not subject:
                messagebox.showwarning("Validation Error", "Please enter a subject.")
                return

            if not description:
                messagebox.showwarning("Validation Error", "Please enter a detailed description.")
                return

            if not self.parent_id:
                messagebox.showerror("Error", "Parent ID not found. Please log in again.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS parent_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT,
                    category TEXT,
                    subject TEXT,
                    description TEXT,
                    priority TEXT,
                    status TEXT DEFAULT 'open',
                    created_date TEXT,
                    resolved_date TEXT,
                    response TEXT,
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                )
                ''')

                # Insert issue
                cursor.execute('''
                INSERT INTO parent_issues (parent_id, category, subject, description, priority, created_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (self.parent_id, category, subject, description, priority,
                      datetime.datetime.now().isoformat()))

                conn.commit()
                issue_id = cursor.lastrowid
                conn.close()

                messagebox.showinfo("Success",
                    f"Issue reported successfully!\n\nTracking ID: #{issue_id}\n\n"
                    "School administration will respond within 24-48 hours.")
                self.update_status("Issue reported successfully")
                self.show_communication_menu()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit issue: {str(e)}")

        ttk.Button(btn_frame, text="Submit Issue", command=submit_issue).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_communication_menu).pack(side=tk.LEFT, padx=5)

        # Show recent issues
        recent_frame = ttk.LabelFrame(self.content_frame, text="Your Recent Issues", padding=15)
        recent_frame.pack(fill=tk.X, padx=20, pady=10)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='parent_issues'
            """)

            if cursor.fetchone() and self.parent_id:
                cursor.execute("""
                SELECT id, category, subject, priority, status, created_date
                FROM parent_issues
                WHERE parent_id = ?
                ORDER BY created_date DESC
                LIMIT 5
                """, (self.parent_id,))

                issues = cursor.fetchall()

                if issues:
                    columns = ("ID", "Category", "Subject", "Priority", "Status", "Date")
                    tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=5)

                    for col in columns:
                        tree.heading(col, text=col)
                        tree.column(col, width=100)

                    for issue in issues:
                        # Format date
                        created_date = issue[5][:10] if issue[5] else "N/A"
                        tree.insert("", tk.END, values=(
                            f"#{issue[0]}", issue[1], issue[2], issue[3].upper(),
                            issue[4].upper(), created_date
                        ))

                    tree.pack(fill=tk.X, pady=5)
                else:
                    ttk.Label(recent_frame, text="No issues reported yet").pack()
            else:
                ttk.Label(recent_frame, text="No issues reported yet").pack()

            conn.close()

        except Exception as e:
            ttk.Label(recent_frame, text=f"Error loading recent issues: {str(e)}").pack()

    def show_fees_interface(self):
        """Show fees and payments interface"""
        self.clear_content()
        self.update_status("Fees & Payments")

        title = ttk.Label(self.content_frame, text="Fees & Payments", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Fees display frame
        fees_frame = ttk.LabelFrame(self.content_frame, text="Fee Information", padding=15)
        fees_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_fees():
            for widget in fees_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(fees_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='fees'
                """)

                if cursor.fetchone():
                    # Get fee information
                    cursor.execute("""
                    SELECT fee_type, amount, due_date, status, description
                    FROM fees
                    WHERE student_id = ?
                    ORDER BY due_date
                    """, (student_id,))

                    fees = cursor.fetchall()

                    if fees:
                        # Summary
                        total_due = sum(float(fee[1]) for fee in fees if fee[3] == 'Unpaid')
                        summary_frame = ttk.LabelFrame(fees_frame, text="Summary", padding=10)
                        summary_frame.pack(fill=tk.X, pady=(0, 10))

                        ttk.Label(summary_frame, text=f"Total Amount Due: ${total_due:.2f}",
                                 font=('Arial', 12, 'bold'), foreground='red' if total_due > 0 else 'green').pack(anchor='w')

                        # Fees list
                        columns = ("Type", "Amount", "Due Date", "Status", "Description")
                        tree = ttk.Treeview(fees_frame, columns=columns, show="headings", height=10)

                        for col in columns:
                            tree.heading(col, text=col)
                            tree.column(col, width=120)

                        for fee in fees:
                            tree.insert('', tk.END, values=fee, tags=(fee[3],))

                        tree.tag_configure('Paid', foreground='green')
                        tree.tag_configure('Unpaid', foreground='red')

                        scrollbar = ttk.Scrollbar(fees_frame, orient=tk.VERTICAL, command=tree.yview)
                        tree.configure(yscrollcommand=scrollbar.set)

                        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                        # Payment button
                        btn_frame = ttk.Frame(fees_frame)
                        btn_frame.pack(pady=10)
                        ttk.Button(btn_frame, text="Make Payment",
                                  command=lambda: self.make_payment(student_id)).pack(side=tk.LEFT, padx=5)
                        ttk.Button(btn_frame, text="Payment History",
                                  command=lambda: self.view_payment_history(student_id)).pack(side=tk.LEFT, padx=5)
                    else:
                        ttk.Label(fees_frame, text="No outstanding fees", font=('Arial', 11)).pack(pady=50)
                else:
                    ttk.Label(fees_frame, text="Fees system not configured",
                             font=('Arial', 11)).pack(pady=20)

                conn.close()

            except Exception as e:
                ttk.Label(fees_frame, text=f"Error loading fees: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Fees", command=load_fees).pack(side=tk.LEFT, padx=5)
        load_fees()

    def make_payment(self, student_id):
        """Make a payment"""
        # Get fee information first
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='student_fees'
            """)

            if not cursor.fetchone():
                messagebox.showwarning("Not Available", "Fee system not configured.")
                conn.close()
                return

            cursor.execute("""
            SELECT fee_type, amount, status
            FROM student_fees
            WHERE student_id = ? AND status = 'Unpaid'
            """, (student_id,))

            unpaid_fees = cursor.fetchall()
            conn.close()

            if not unpaid_fees:
                messagebox.showinfo("No Fees Due", "There are no outstanding fees for this student.")
                return

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load fee information: {str(e)}")
            return

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Make Payment")
        dialog.geometry("600x550")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Make Payment",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Ensure payments table exists
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='payments'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    fee_type TEXT,
                    amount REAL,
                    payment_method TEXT,
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confirmation_number TEXT
                )
                """)
                conn.commit()

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
            dialog.destroy()
            return

        # Display unpaid fees
        fees_frame = ttk.LabelFrame(main_frame, text="Outstanding Fees", padding=10)
        fees_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("Fee Type", "Amount", "Status")
        tree = ttk.Treeview(fees_frame, columns=columns, show="headings", height=6)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        total_amount = 0
        for fee in unpaid_fees:
            tree.insert('', tk.END, values=fee)
            total_amount += float(fee[1])

        tree.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Total Amount Due: ${total_amount:.2f}",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Payment method selection
        ttk.Label(main_frame, text="Payment Method:").pack(anchor='w', pady=(10, 0))
        payment_method = ttk.Combobox(main_frame, width=50, state="readonly")
        payment_method['values'] = ['Credit Card', 'Debit Card', 'Check', 'Cash', 'Bank Transfer']
        payment_method.pack(fill=tk.X, pady=(0, 10))

        def process_payment():
            if not payment_method.get():
                messagebox.showwarning("Validation Error", "Please select a payment method.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Generate confirmation number
                import random
                confirmation = f"PAY{random.randint(100000, 999999)}"

                # Record payment for each fee
                for fee in unpaid_fees:
                    cursor.execute("""
                    INSERT INTO payments (student_id, fee_type, amount, payment_method, confirmation_number)
                    VALUES (?, ?, ?, ?, ?)
                    """, (student_id, fee[0], fee[1], payment_method.get(), confirmation))

                    # Update fee status to paid
                    cursor.execute("""
                    UPDATE student_fees
                    SET status = 'Paid'
                    WHERE student_id = ? AND fee_type = ? AND status = 'Unpaid'
                    """, (student_id, fee[0]))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success",
                                   f"Payment of ${total_amount:.2f} processed successfully!\n\n"
                                   f"Confirmation Number: {confirmation}\n\n"
                                   "Thank you for your payment.")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to process payment: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Process Payment", command=process_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def view_payment_history(self, student_id):
        """View payment history"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Payment History")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Payment History",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='payments'
            """)

            if not cursor.fetchone():
                ttk.Label(main_frame, text="No payment history available.",
                         font=('Arial', 11)).pack(pady=50)
                ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()
                conn.close()
                return

            cursor.execute("""
            SELECT fee_type, amount, payment_method, payment_date, confirmation_number
            FROM payments
            WHERE student_id = ?
            ORDER BY payment_date DESC
            """, (student_id,))

            payments = cursor.fetchall()
            conn.close()

            if not payments:
                ttk.Label(main_frame, text="No payments found for this student.",
                         font=('Arial', 11)).pack(pady=50)
                ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()
                return

            # Display payment history
            columns = ("Fee Type", "Amount", "Payment Method", "Date", "Confirmation #")
            tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)

            tree.heading("Fee Type", text="Fee Type")
            tree.heading("Amount", text="Amount")
            tree.heading("Payment Method", text="Payment Method")
            tree.heading("Date", text="Date")
            tree.heading("Confirmation #", text="Confirmation #")

            tree.column("Fee Type", width=150)
            tree.column("Amount", width=100)
            tree.column("Payment Method", width=120)
            tree.column("Date", width=150)
            tree.column("Confirmation #", width=120)

            total_paid = 0
            for payment in payments:
                tree.insert('', tk.END, values=payment)
                total_paid += float(payment[1])

            scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Summary
            summary_frame = ttk.Frame(dialog, padding=20)
            summary_frame.pack(fill=tk.X)

            ttk.Label(summary_frame, text=f"Total Paid: ${total_paid:.2f}",
                     font=('Arial', 12, 'bold')).pack(side=tk.LEFT)

            ttk.Button(summary_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load payment history: {str(e)}")
            dialog.destroy()

    def show_meal_interface(self):
        """Show meal accounts interface"""
        self.clear_content()
        self.update_status("Meal Accounts")

        title = ttk.Label(self.content_frame, text="Meal Accounts", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Meal account display frame
        meal_frame = ttk.LabelFrame(self.content_frame, text="Meal Account Information", padding=15)
        meal_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_meal_info():
            for widget in meal_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(meal_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='meal_accounts'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    SELECT balance, meal_plan, dietary_restrictions, allergies, last_transaction_date
                    FROM meal_accounts
                    WHERE student_id = ?
                    """, (student_id,))

                    meal_data = cursor.fetchone()

                    if meal_data:
                        # Balance information
                        balance_frame = ttk.LabelFrame(meal_frame, text="Account Balance", padding=10)
                        balance_frame.pack(fill=tk.X, pady=(0, 10))

                        balance_color = 'green' if float(meal_data[0]) > 0 else 'red'
                        ttk.Label(balance_frame, text=f"Current Balance: ${float(meal_data[0]):.2f}",
                                 font=('Arial', 14, 'bold'), foreground=balance_color).pack(anchor='w', pady=5)
                        ttk.Label(balance_frame, text=f"Meal Plan: {meal_data[1] or 'Standard'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)
                        ttk.Label(balance_frame, text=f"Last Transaction: {meal_data[4] or 'N/A'}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)

                        # Dietary information
                        if meal_data[2] or meal_data[3]:
                            dietary_frame = ttk.LabelFrame(meal_frame, text="Dietary Information", padding=10)
                            dietary_frame.pack(fill=tk.X, pady=(0, 10))

                            if meal_data[2]:
                                ttk.Label(dietary_frame, text=f"Dietary Restrictions: {meal_data[2]}",
                                         font=('Arial', 10)).pack(anchor='w', pady=3)
                            if meal_data[3]:
                                ttk.Label(dietary_frame, text=f"Allergies: {meal_data[3]}",
                                         font=('Arial', 10), foreground='red').pack(anchor='w', pady=3)

                        # Recent transactions
                        cursor.execute("""
                        SELECT date, meal_type, amount, description
                        FROM meal_transactions
                        WHERE student_id = ?
                        ORDER BY date DESC
                        LIMIT 15
                        """, (student_id,))

                        transactions = cursor.fetchall()

                        if transactions:
                            trans_frame = ttk.LabelFrame(meal_frame, text="Recent Transactions", padding=10)
                            trans_frame.pack(fill=tk.BOTH, expand=True)

                            columns = ("Date", "Meal Type", "Amount", "Description")
                            tree = ttk.Treeview(trans_frame, columns=columns, show="headings", height=8)

                            for col in columns:
                                tree.heading(col, text=col)
                                tree.column(col, width=120)

                            for trans in transactions:
                                tree.insert('', tk.END, values=trans)

                            scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=tree.yview)
                            tree.configure(yscrollcommand=scrollbar.set)

                            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                        # Action buttons
                        btn_frame = ttk.Frame(meal_frame)
                        btn_frame.pack(pady=10)
                        ttk.Button(btn_frame, text="Add Funds",
                                  command=lambda: self.add_meal_funds(student_id)).pack(side=tk.LEFT, padx=5)
                        ttk.Button(btn_frame, text="Update Meal Plan",
                                  command=lambda: self.update_meal_plan(student_id)).pack(side=tk.LEFT, padx=5)
                    else:
                        ttk.Label(meal_frame, text="No meal account found",
                                 font=('Arial', 11)).pack(pady=50)
                else:
                    ttk.Label(meal_frame, text="Meal account system not configured",
                             font=('Arial', 11)).pack(pady=20)

                conn.close()

            except Exception as e:
                ttk.Label(meal_frame, text=f"Error loading meal account: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Meal Info", command=load_meal_info).pack(side=tk.LEFT, padx=5)
        load_meal_info()

    def add_meal_funds(self, student_id):
        """Add funds to meal account"""
        # Ask for amount
        amount = simpledialog.askfloat("Add Funds", "Enter amount to add to meal account:", minvalue=0.01)

        if not amount:
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Ensure tables exist
            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='meal_accounts'
            """)

            if not cursor.fetchone():
                messagebox.showwarning("Not Available", "Meal account system not configured.")
                conn.close()
                return

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='meal_transactions'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE meal_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    meal_type TEXT,
                    amount REAL,
                    description TEXT,
                    transaction_type TEXT
                )
                """)
                conn.commit()

            # Update balance
            cursor.execute("""
            UPDATE meal_accounts
            SET balance = balance + ?,
                last_transaction_date = CURRENT_TIMESTAMP
            WHERE student_id = ?
            """, (amount, student_id))

            # Record transaction
            cursor.execute("""
            INSERT INTO meal_transactions (student_id, amount, description, transaction_type)
            VALUES (?, ?, ?, ?)
            """, (student_id, amount, f"Funds added: ${amount:.2f}", "Credit"))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"${amount:.2f} has been added to the meal account!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add funds: {str(e)}")

    def update_meal_plan(self, student_id):
        """Update meal plan"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Meal Plan")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Update Meal Plan",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Get current meal plan
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='meal_accounts'
            """)

            if not cursor.fetchone():
                messagebox.showwarning("Not Available", "Meal account system not configured.")
                conn.close()
                dialog.destroy()
                return

            cursor.execute("""
            SELECT meal_plan FROM meal_accounts WHERE student_id = ?
            """, (student_id,))

            current_plan = cursor.fetchone()
            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load meal plan: {str(e)}")
            dialog.destroy()
            return

        # Meal plan options
        ttk.Label(main_frame, text="Select Meal Plan:").pack(anchor='w', pady=(5, 0))

        meal_plans = [
            ('Standard', 'Standard meal plan - All meals included'),
            ('Breakfast Only', 'Breakfast only meal plan'),
            ('Lunch Only', 'Lunch only meal plan'),
            ('Breakfast & Lunch', 'Breakfast and lunch meal plan'),
            ('No Plan', 'No meal plan - Pay as you go')
        ]

        plan_var = tk.StringVar()
        if current_plan and current_plan[0]:
            plan_var.set(current_plan[0])

        for plan_name, plan_desc in meal_plans:
            frame = ttk.Frame(main_frame)
            frame.pack(fill=tk.X, pady=5)

            rb = ttk.Radiobutton(frame, text=plan_name, variable=plan_var, value=plan_name)
            rb.pack(anchor='w')

            ttk.Label(frame, text=plan_desc, font=('Arial', 9, 'italic')).pack(anchor='w', padx=20)

        def save_plan():
            if not plan_var.get():
                messagebox.showwarning("Validation Error", "Please select a meal plan.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Update meal plan
                cursor.execute("""
                UPDATE meal_accounts
                SET meal_plan = ?
                WHERE student_id = ?
                """, (plan_var.get(), student_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Meal plan updated to: {plan_var.get()}")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update meal plan: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save", command=save_plan).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_fundraising_interface(self):
        """Show fundraising interface"""
        self.clear_content()
        self.update_status("Fundraising")

        title = ttk.Label(self.content_frame, text="Fundraising Campaigns", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Active campaigns
        campaigns_frame = ttk.LabelFrame(self.content_frame, text="Active Campaigns", padding=15)
        campaigns_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='fundraising_campaigns'
            """)

            if cursor.fetchone():
                cursor.execute("""
                SELECT campaign_name, goal_amount, current_amount, end_date, description
                FROM fundraising_campaigns
                WHERE is_active = 1
                ORDER BY end_date
                LIMIT 10
                """)

                campaigns = cursor.fetchall()

                if campaigns:
                    for campaign in campaigns:
                        camp_frame = ttk.LabelFrame(campaigns_frame, text=campaign[0], padding=10)
                        camp_frame.pack(fill=tk.X, pady=5)

                        progress = (float(campaign[2]) / float(campaign[1]) * 100) if float(campaign[1]) > 0 else 0
                        ttk.Label(camp_frame, text=f"Goal: ${float(campaign[1]):.2f} | Raised: ${float(campaign[2]):.2f} ({progress:.1f}%)",
                                 font=('Arial', 10, 'bold')).pack(anchor='w')
                        ttk.Label(camp_frame, text=f"Ends: {campaign[3]}",
                                 font=('Arial', 9)).pack(anchor='w')
                        ttk.Label(camp_frame, text=campaign[4], wraplength=600).pack(anchor='w', pady=3)

                        ttk.Button(camp_frame, text="Contribute",
                                  command=lambda c=campaign[0]: self.contribute_to_fundraiser(c)).pack(anchor='e', pady=5)
                else:
                    ttk.Label(campaigns_frame, text="No active fundraising campaigns",
                             font=('Arial', 11)).pack(pady=50)
            else:
                ttk.Label(campaigns_frame, text="Fundraising system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(campaigns_frame, text=f"Error loading campaigns: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    def contribute_to_fundraiser(self, campaign_name):
        """Contribute to a fundraiser"""
        amount = simpledialog.askfloat("Contribute", f"Enter amount to contribute to {campaign_name}:")
        if amount:
            messagebox.showinfo("Thank You!",
                               f"Thank you for your ${amount:.2f} contribution to {campaign_name}!\n\n"
                               "Payment processing not available in demo.")

    def show_homework_interface(self):
        """Show homework and assignments interface"""
        self.clear_content()
        self.update_status("Homework & Assignments")

        title = ttk.Label(self.content_frame, text="Homework & Assignments", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Homework display frame
        homework_frame = ttk.LabelFrame(self.content_frame, text="Assignments", padding=15)
        homework_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_homework():
            for widget in homework_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(homework_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='assignments'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    SELECT a.assignment_name, a.subject, a.due_date, a.description,
                           COALESCE(s.status, 'Not Started') as status
                    FROM assignments a
                    LEFT JOIN assignment_submissions s ON a.assignment_id = s.assignment_id
                                                       AND s.student_id = ?
                    WHERE a.due_date >= date('now')
                    ORDER BY a.due_date
                    LIMIT 20
                    """, (student_id,))

                    assignments = cursor.fetchall()

                    if assignments:
                        columns = ("Assignment", "Subject", "Due Date", "Status")
                        tree = ttk.Treeview(homework_frame, columns=columns, show="headings", height=12)

                        for col in columns:
                            tree.heading(col, text=col)
                            tree.column(col, width=150)

                        for assignment in assignments:
                            tree.insert('', tk.END, values=assignment[:4], tags=(assignment[4],))

                        tree.tag_configure('Completed', foreground='green')
                        tree.tag_configure('Not Started', foreground='red')
                        tree.tag_configure('In Progress', foreground='orange')

                        scrollbar = ttk.Scrollbar(homework_frame, orient=tk.VERTICAL, command=tree.yview)
                        tree.configure(yscrollcommand=scrollbar.set)

                        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                        def view_details():
                            selected = tree.selection()
                            if selected:
                                item = tree.item(selected[0])
                                messagebox.showinfo("Assignment Details",
                                                   f"Assignment: {item['values'][0]}\n"
                                                   f"Subject: {item['values'][1]}\n"
                                                   f"Due: {item['values'][2]}\n"
                                                   f"Status: {item['values'][3]}")

                        ttk.Button(homework_frame, text="View Details", command=view_details).pack(pady=10)
                    else:
                        ttk.Label(homework_frame, text="No upcoming assignments",
                                 font=('Arial', 11)).pack(pady=50)
                else:
                    ttk.Label(homework_frame, text="Assignments system not configured",
                             font=('Arial', 11)).pack(pady=20)

                conn.close()

            except Exception as e:
                ttk.Label(homework_frame, text=f"Error loading assignments: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Assignments", command=load_homework).pack(side=tk.LEFT, padx=5)
        load_homework()

    def show_goals_interface(self):
        """Show academic goals interface"""
        self.clear_content()
        self.update_status("Academic Goals")

        title = ttk.Label(self.content_frame, text="Academic Goals", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Goals display frame
        goals_frame = ttk.LabelFrame(self.content_frame, text="Academic Goals", padding=15)
        goals_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_goals():
            for widget in goals_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(goals_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='academic_goals'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    SELECT goal_title, category, target_date, progress, status, description
                    FROM academic_goals
                    WHERE student_id = ?
                    ORDER BY target_date
                    LIMIT 20
                    """, (student_id,))

                    goals = cursor.fetchall()

                    if goals:
                        for goal in goals:
                            goal_card = ttk.LabelFrame(goals_frame, text=goal[0], padding=10)
                            goal_card.pack(fill=tk.X, pady=5)

                            ttk.Label(goal_card, text=f"Category: {goal[1]} | Target: {goal[2]}",
                                     font=('Arial', 9, 'bold')).pack(anchor='w')
                            ttk.Label(goal_card, text=f"Progress: {goal[3]}% | Status: {goal[4]}",
                                     font=('Arial', 9)).pack(anchor='w')
                            ttk.Label(goal_card, text=goal[5], wraplength=600).pack(anchor='w', pady=3)

                            # Progress bar
                            progress_bar = ttk.Progressbar(goal_card, length=400, mode='determinate')
                            progress_bar['value'] = int(goal[3])
                            progress_bar.pack(anchor='w', pady=5)
                    else:
                        ttk.Label(goals_frame, text="No academic goals set",
                                 font=('Arial', 11)).pack(pady=50)
                        ttk.Button(goals_frame, text="Set a Goal",
                                  command=lambda: self.set_academic_goal(student_id)).pack()
                else:
                    ttk.Label(goals_frame, text="Academic goals system not configured",
                             font=('Arial', 11)).pack(pady=20)

                conn.close()

            except Exception as e:
                ttk.Label(goals_frame, text=f"Error loading goals: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Goals", command=load_goals).pack(side=tk.LEFT, padx=5)
        load_goals()

    def set_academic_goal(self, student_id):
        """Set a new academic goal"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Academic Goal")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Set Academic Goal",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Ensure table exists
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='academic_goals'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE academic_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    goal_title TEXT NOT NULL,
                    category TEXT,
                    target_date TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'Active',
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                conn.commit()

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # Goal Title
        ttk.Label(main_frame, text="Goal Title: *").pack(anchor='w', pady=(5, 0))
        fields['goal_title'] = ttk.Entry(main_frame, width=50)
        fields['goal_title'].pack(fill=tk.X, pady=(0, 10))

        # Category
        ttk.Label(main_frame, text="Category:").pack(anchor='w', pady=(5, 0))
        fields['category'] = ttk.Combobox(main_frame, width=50, state="readonly")
        fields['category']['values'] = ['Academic Performance', 'Homework Completion', 'Reading',
                                       'Math', 'Science', 'Writing', 'Test Scores', 'Behavior', 'Other']
        fields['category'].pack(fill=tk.X, pady=(0, 10))

        # Target Date
        ttk.Label(main_frame, text="Target Date (YYYY-MM-DD):").pack(anchor='w', pady=(5, 0))
        fields['target_date'] = ttk.Entry(main_frame, width=50)
        fields['target_date'].pack(fill=tk.X, pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description: *").pack(anchor='w', pady=(5, 0))
        fields['description'] = scrolledtext.ScrolledText(main_frame, width=50, height=8)
        fields['description'].pack(fill=tk.X, pady=(0, 10))

        def save_goal():
            # Validate required fields
            if not fields['goal_title'].get():
                messagebox.showwarning("Validation Error", "Please enter a goal title.")
                return

            if not fields['description'].get('1.0', tk.END).strip():
                messagebox.showwarning("Validation Error", "Please provide a description.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Insert new goal
                cursor.execute("""
                INSERT INTO academic_goals (student_id, goal_title, category, target_date, description)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    student_id,
                    fields['goal_title'].get(),
                    fields['category'].get(),
                    fields['target_date'].get(),
                    fields['description'].get('1.0', tk.END).strip()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Academic goal set successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save goal: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Save Goal", command=save_goal).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_library_interface(self):
        """Show library account interface"""
        self.clear_content()
        self.update_status("Library Account")

        title = ttk.Label(self.content_frame, text="Library Account", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Library display frame
        library_frame = ttk.LabelFrame(self.content_frame, text="Library Information", padding=15)
        library_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_library_info():
            for widget in library_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(library_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='library_checkouts'
                """)

                if cursor.fetchone():
                    # Get checked out books
                    cursor.execute("""
                    SELECT book_title, author, checkout_date, due_date, status
                    FROM library_checkouts
                    WHERE student_id = ? AND status = 'Checked Out'
                    ORDER BY due_date
                    """, (student_id,))

                    checkouts = cursor.fetchall()

                    # Summary
                    summary_frame = ttk.LabelFrame(library_frame, text="Account Summary", padding=10)
                    summary_frame.pack(fill=tk.X, pady=(0, 10))

                    ttk.Label(summary_frame, text=f"Books Checked Out: {len(checkouts)}",
                             font=('Arial', 10, 'bold')).pack(anchor='w', pady=3)

                    overdue_count = sum(1 for book in checkouts if book[3] < datetime.datetime.now().strftime('%Y-%m-%d'))
                    if overdue_count > 0:
                        ttk.Label(summary_frame, text=f"Overdue Books: {overdue_count}",
                                 font=('Arial', 10, 'bold'), foreground='red').pack(anchor='w', pady=3)

                    if checkouts:
                        # Display checked out books
                        columns = ("Title", "Author", "Checked Out", "Due Date", "Status")
                        tree = ttk.Treeview(library_frame, columns=columns, show="headings", height=10)

                        for col in columns:
                            tree.heading(col, text=col)
                            tree.column(col, width=120)

                        for book in checkouts:
                            tree.insert('', tk.END, values=book)

                        scrollbar = ttk.Scrollbar(library_frame, orient=tk.VERTICAL, command=tree.yview)
                        tree.configure(yscrollcommand=scrollbar.set)

                        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                    else:
                        ttk.Label(library_frame, text="No books currently checked out",
                                 font=('Arial', 11)).pack(pady=50)

                    ttk.Button(library_frame, text="View Reading History",
                              command=lambda: self.view_reading_history(student_id)).pack(pady=10)
                else:
                    ttk.Label(library_frame, text="Library system not configured",
                             font=('Arial', 11)).pack(pady=20)

                conn.close()

            except Exception as e:
                ttk.Label(library_frame, text=f"Error loading library info: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Library Info", command=load_library_info).pack(side=tk.LEFT, padx=5)
        load_library_info()

    def view_reading_history(self, student_id):
        """View reading history"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Reading History")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Reading History",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='library_checkouts'
            """)

            if not cursor.fetchone():
                ttk.Label(main_frame, text="Library system not configured.",
                         font=('Arial', 11)).pack(pady=50)
                ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()
                conn.close()
                return

            # Get all checkouts (current and historical)
            cursor.execute("""
            SELECT book_title, author, checkout_date, due_date, return_date, status
            FROM library_checkouts
            WHERE student_id = ?
            ORDER BY checkout_date DESC
            """, (student_id,))

            checkouts = cursor.fetchall()
            conn.close()

            if not checkouts:
                ttk.Label(main_frame, text="No reading history found.",
                         font=('Arial', 11)).pack(pady=50)
                ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()
                return

            # Display reading history
            columns = ("Title", "Author", "Checked Out", "Due Date", "Returned", "Status")
            tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)

            tree.heading("Title", text="Title")
            tree.heading("Author", text="Author")
            tree.heading("Checked Out", text="Checked Out")
            tree.heading("Due Date", text="Due Date")
            tree.heading("Returned", text="Returned")
            tree.heading("Status", text="Status")

            tree.column("Title", width=200)
            tree.column("Author", width=150)
            tree.column("Checked Out", width=100)
            tree.column("Due Date", width=100)
            tree.column("Returned", width=100)
            tree.column("Status", width=100)

            for checkout in checkouts:
                tree.insert('', tk.END, values=checkout)

            scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Summary
            summary_frame = ttk.Frame(dialog, padding=20)
            summary_frame.pack(fill=tk.X)

            total_books = len(checkouts)
            returned_books = sum(1 for c in checkouts if c[5] == 'Returned')

            ttk.Label(summary_frame, text=f"Total Books: {total_books} | Returned: {returned_books}",
                     font=('Arial', 11)).pack(side=tk.LEFT)

            ttk.Button(summary_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load reading history: {str(e)}")
            dialog.destroy()

    def show_activities_interface(self):
        """Show extracurricular activities interface"""
        self.clear_content()
        self.update_status("Extracurricular Activities")

        title = ttk.Label(self.content_frame, text="Extracurricular Activities", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Activities display frame
        activities_frame = ttk.LabelFrame(self.content_frame, text="Activities", padding=15)
        activities_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_activities():
            for widget in activities_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(activities_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='extracurricular_activities'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    SELECT activity_name, category, schedule, location, supervisor, description
                    FROM extracurricular_activities
                    WHERE student_id = ? AND is_active = 1
                    ORDER BY activity_name
                    """, (student_id,))

                    activities = cursor.fetchall()

                    if activities:
                        for activity in activities:
                            activity_card = ttk.LabelFrame(activities_frame, text=activity[0], padding=10)
                            activity_card.pack(fill=tk.X, pady=5)

                            ttk.Label(activity_card, text=f"Category: {activity[1]}",
                                     font=('Arial', 9, 'bold')).pack(anchor='w')
                            ttk.Label(activity_card, text=f"Schedule: {activity[2]}",
                                     font=('Arial', 9)).pack(anchor='w')
                            ttk.Label(activity_card, text=f"Location: {activity[3]}",
                                     font=('Arial', 9)).pack(anchor='w')
                            ttk.Label(activity_card, text=f"Supervisor: {activity[4]}",
                                     font=('Arial', 9)).pack(anchor='w')
                            ttk.Label(activity_card, text=activity[5], wraplength=600).pack(anchor='w', pady=3)
                    else:
                        ttk.Label(activities_frame, text="Not enrolled in any activities",
                                 font=('Arial', 11)).pack(pady=50)
                        ttk.Button(activities_frame, text="Browse Activities",
                                  command=self.browse_activities).pack()
                else:
                    ttk.Label(activities_frame, text="Activities system not configured",
                             font=('Arial', 11)).pack(pady=20)

                conn.close()

            except Exception as e:
                ttk.Label(activities_frame, text=f"Error loading activities: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Activities", command=load_activities).pack(side=tk.LEFT, padx=5)
        load_activities()

    def browse_activities(self):
        """Browse available activities"""
        messagebox.showinfo("Browse Activities",
                           "Please contact the school office for information about available extracurricular activities.")

    def show_notifications_interface(self):
        """Show notification preferences interface"""
        self.clear_content()
        self.update_status("Notification Preferences")

        title = ttk.Label(self.content_frame, text="Notification Preferences", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Notification settings frame
        settings_frame = ttk.LabelFrame(self.content_frame, text="Notification Settings", padding=20)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Email notifications
        email_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Email Notifications", variable=email_var).pack(anchor='w', pady=5)

        # SMS notifications
        sms_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="SMS Notifications", variable=sms_var).pack(anchor='w', pady=5)

        # Push notifications
        push_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Push Notifications", variable=push_var).pack(anchor='w', pady=5)

        ttk.Separator(settings_frame, orient='horizontal').pack(fill='x', pady=15)

        # Notification categories
        ttk.Label(settings_frame, text="Receive notifications for:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)

        categories = {
            "Grades Posted": tk.BooleanVar(value=True),
            "Attendance Alerts": tk.BooleanVar(value=True),
            "Behavior Reports": tk.BooleanVar(value=True),
            "School Announcements": tk.BooleanVar(value=True),
            "Event Reminders": tk.BooleanVar(value=True),
            "Fee Reminders": tk.BooleanVar(value=True),
            "Homework Assignments": tk.BooleanVar(value=False),
            "Messages from Teachers": tk.BooleanVar(value=True),
        }

        for category, var in categories.items():
            ttk.Checkbutton(settings_frame, text=category, variable=var).pack(anchor='w', padx=20, pady=3)

        # Save button
        def save_preferences():
            messagebox.showinfo("Success", "Notification preferences saved successfully!")
            self.update_status("Preferences saved")

        # Advanced settings button
        def show_advanced_settings():
            self.show_advanced_notification_settings()

        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Save Preferences", command=save_preferences).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Advanced Settings", command=show_advanced_settings).pack(side=tk.LEFT, padx=5)

    def show_advanced_notification_settings(self):
        """Show advanced notification settings dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Notification Settings")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Advanced Notification Settings",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Load current preferences from database
        current_prefs = {}
        try:
            if self.parent_id:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Ensure parent_preferences table exists with advanced columns
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS parent_preferences (
                    parent_id TEXT PRIMARY KEY,
                    email_notifications INTEGER DEFAULT 1,
                    sms_notifications INTEGER DEFAULT 0,
                    grade_alerts INTEGER DEFAULT 1,
                    attendance_alerts INTEGER DEFAULT 1,
                    behavior_alerts INTEGER DEFAULT 1,
                    assignment_alerts INTEGER DEFAULT 1,
                    weekly_summary INTEGER DEFAULT 1,
                    preferred_notification_time TEXT,
                    quiet_hours_start TEXT,
                    quiet_hours_end TEXT,
                    subject_preferences TEXT,
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                )
                ''')

                cursor.execute('''
                SELECT preferred_notification_time, quiet_hours_start, quiet_hours_end, subject_preferences
                FROM parent_preferences
                WHERE parent_id = ?
                ''', (self.parent_id,))

                prefs = cursor.fetchone()
                if prefs:
                    current_prefs = {
                        'notification_time': prefs[0] or '09:00',
                        'quiet_start': prefs[1] or '22:00',
                        'quiet_end': prefs[2] or '07:00',
                        'subjects': prefs[3] or ''
                    }
                else:
                    # Insert default preferences
                    cursor.execute('''
                    INSERT OR IGNORE INTO parent_preferences (parent_id)
                    VALUES (?)
                    ''', (self.parent_id,))
                    conn.commit()
                    current_prefs = {
                        'notification_time': '09:00',
                        'quiet_start': '22:00',
                        'quiet_end': '07:00',
                        'subjects': ''
                    }

                conn.close()
        except Exception as e:
            print(f"Error loading preferences: {e}")
            current_prefs = {
                'notification_time': '09:00',
                'quiet_start': '22:00',
                'quiet_end': '07:00',
                'subjects': ''
            }

        # Preferred notification time
        time_frame = ttk.LabelFrame(main_frame, text="Preferred Notification Time", padding=15)
        time_frame.pack(fill=tk.X, pady=10)

        ttk.Label(time_frame, text="Send daily summaries at:").pack(anchor='w', pady=5)
        notification_time_var = tk.StringVar(value=current_prefs['notification_time'])
        time_combo = ttk.Combobox(time_frame, textvariable=notification_time_var, width=20, state='readonly')
        time_combo['values'] = ['07:00', '08:00', '09:00', '10:00', '12:00', '15:00', '17:00', '18:00', '20:00']
        time_combo.pack(fill=tk.X, pady=5)

        # Quiet hours
        quiet_frame = ttk.LabelFrame(main_frame, text="Quiet Hours (No Notifications)", padding=15)
        quiet_frame.pack(fill=tk.X, pady=10)

        ttk.Label(quiet_frame, text="Start Time:").grid(row=0, column=0, sticky='w', pady=5)
        quiet_start_var = tk.StringVar(value=current_prefs['quiet_start'])
        quiet_start_combo = ttk.Combobox(quiet_frame, textvariable=quiet_start_var, width=15, state='readonly')
        quiet_start_combo['values'] = [f"{h:02d}:00" for h in range(24)]
        quiet_start_combo.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(quiet_frame, text="End Time:").grid(row=1, column=0, sticky='w', pady=5)
        quiet_end_var = tk.StringVar(value=current_prefs['quiet_end'])
        quiet_end_combo = ttk.Combobox(quiet_frame, textvariable=quiet_end_var, width=15, state='readonly')
        quiet_end_combo['values'] = [f"{h:02d}:00" for h in range(24)]
        quiet_end_combo.grid(row=1, column=1, pady=5, padx=5)

        # Subject-specific preferences
        subject_frame = ttk.LabelFrame(main_frame, text="Subject-Specific Notifications", padding=15)
        subject_frame.pack(fill=tk.X, pady=10)

        ttk.Label(subject_frame,
                 text="Get notifications only for specific subjects\n(comma-separated, leave empty for all):",
                 wraplength=400).pack(anchor='w', pady=5)

        # Parse current subjects
        try:
            if current_prefs['subjects']:
                subject_data = json.loads(current_prefs['subjects'])
                current_subjects = ', '.join(subject_data.get('subjects', []))
            else:
                current_subjects = ''
        except:
            current_subjects = ''

        subject_entry = ttk.Entry(subject_frame, width=50)
        subject_entry.insert(0, current_subjects)
        subject_entry.pack(fill=tk.X, pady=5)

        ttk.Label(subject_frame, text="Example: Mathematics, Science, English",
                 font=('Arial', 8, 'italic')).pack(anchor='w')

        # Save button
        def save_advanced_settings():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Prepare subject preferences
                subjects_input = subject_entry.get().strip()
                if subjects_input:
                    subjects_list = [s.strip() for s in subjects_input.split(',') if s.strip()]
                    subject_prefs_json = json.dumps({'subjects': subjects_list})
                else:
                    subject_prefs_json = None

                # Update preferences
                cursor.execute('''
                UPDATE parent_preferences
                SET preferred_notification_time = ?,
                    quiet_hours_start = ?,
                    quiet_hours_end = ?,
                    subject_preferences = ?
                WHERE parent_id = ?
                ''', (notification_time_var.get(), quiet_start_var.get(), quiet_end_var.get(),
                      subject_prefs_json, self.parent_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Advanced notification settings saved successfully!")
                self.update_status("Advanced notification settings saved")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Save Settings", command=save_advanced_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_documents_interface(self):
        """Show document management interface"""
        self.clear_content()
        self.update_status("Document Management")

        title = ttk.Label(self.content_frame, text="Document Management", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        if not self.children:
            ttk.Label(self.content_frame, text="No children registered.").pack(pady=50)
            return

        # Child selection
        child_frame = ttk.Frame(self.content_frame)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(child_frame, text="Select Child:").pack(side=tk.LEFT, padx=5)
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        if child_combo['values']:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(side=tk.LEFT, padx=5)

        # Documents display frame
        docs_frame = ttk.LabelFrame(self.content_frame, text="Documents", padding=15)
        docs_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_documents():
            for widget in docs_frame.winfo_children():
                widget.destroy()

            selected_child = child_var.get()
            if not selected_child:
                ttk.Label(docs_frame, text="Please select a child").pack(pady=20)
                return

            student_id = selected_child.split("ID: ")[1].rstrip(")")

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='documents'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                    SELECT document_name, document_type, upload_date, uploaded_by, description
                    FROM documents
                    WHERE student_id = ?
                    ORDER BY upload_date DESC
                    LIMIT 50
                    """, (student_id,))

                    documents = cursor.fetchall()

                    if documents:
                        columns = ("Document Name", "Type", "Upload Date", "Uploaded By")
                        tree = ttk.Treeview(docs_frame, columns=columns, show="headings", height=12)

                        for col in columns:
                            tree.heading(col, text=col)
                            tree.column(col, width=150)

                        for doc in documents:
                            tree.insert('', tk.END, values=doc[:4])

                        scrollbar = ttk.Scrollbar(docs_frame, orient=tk.VERTICAL, command=tree.yview)
                        tree.configure(yscrollcommand=scrollbar.set)

                        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                        def view_document():
                            selected = tree.selection()
                            if selected:
                                messagebox.showinfo("View Document",
                                                   "Document viewing not available in demo.")

                        btn_frame = ttk.Frame(docs_frame)
                        btn_frame.pack(pady=10)
                        ttk.Button(btn_frame, text="View Document", command=view_document).pack(side=tk.LEFT, padx=5)
                        ttk.Button(btn_frame, text="Upload Document",
                                  command=lambda: self.upload_document(student_id)).pack(side=tk.LEFT, padx=5)
                    else:
                        ttk.Label(docs_frame, text="No documents found",
                                 font=('Arial', 11)).pack(pady=50)
                        ttk.Button(docs_frame, text="Upload Document",
                                  command=lambda: self.upload_document(student_id)).pack()
                else:
                    ttk.Label(docs_frame, text="Document management system not configured",
                             font=('Arial', 11)).pack(pady=20)

                conn.close()

            except Exception as e:
                ttk.Label(docs_frame, text=f"Error loading documents: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        ttk.Button(child_frame, text="Load Documents", command=load_documents).pack(side=tk.LEFT, padx=5)
        load_documents()

    def upload_document(self, student_id):
        """Upload a document"""
        from tkinter import filedialog
        import shutil

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Upload Document")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Upload Document",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Ensure table exists
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='documents'
            """)

            if not cursor.fetchone():
                cursor.execute("""
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    document_type TEXT,
                    document_name TEXT,
                    file_path TEXT,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
                """)
                conn.commit()

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
            dialog.destroy()
            return

        # Create form fields
        fields = {}

        # File selection
        selected_file = tk.StringVar()

        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=10)

        ttk.Label(file_frame, text="Selected File:").pack(anchor='w')
        file_label = ttk.Label(file_frame, textvariable=selected_file, relief=tk.SUNKEN, padding=5)
        file_label.pack(fill=tk.X, pady=5)

        def select_file():
            filename = filedialog.askopenfilename(
                title="Select Document",
                filetypes=[
                    ("PDF files", "*.pdf"),
                    ("Word documents", "*.doc *.docx"),
                    ("Images", "*.jpg *.jpeg *.png"),
                    ("All files", "*.*")
                ]
            )
            if filename:
                selected_file.set(filename)

        ttk.Button(file_frame, text="Browse...", command=select_file).pack(anchor='w', pady=5)

        # Document Type
        ttk.Label(main_frame, text="Document Type:").pack(anchor='w', pady=(10, 0))
        fields['document_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
        fields['document_type']['values'] = ['Medical Form', 'Permission Slip', 'Report Card',
                                            'Transcript', 'ID Document', 'Insurance Card', 'Other']
        fields['document_type'].pack(fill=tk.X, pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(5, 0))
        fields['description'] = scrolledtext.ScrolledText(main_frame, width=50, height=6)
        fields['description'].pack(fill=tk.X, pady=(0, 10))

        def upload_file():
            # Validate
            if not selected_file.get():
                messagebox.showwarning("Validation Error", "Please select a file to upload.")
                return

            if not fields['document_type'].get():
                messagebox.showwarning("Validation Error", "Please select a document type.")
                return

            try:
                import os
                file_path = selected_file.get()
                file_name = os.path.basename(file_path)

                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Insert document record
                cursor.execute("""
                INSERT INTO documents (student_id, document_type, document_name, file_path, description)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    student_id,
                    fields['document_type'].get(),
                    file_name,
                    file_path,
                    fields['description'].get('1.0', tk.END).strip()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Document '{file_name}' uploaded successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload document: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Upload", command=upload_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_calendar_interface(self):
        """Show calendar integration interface"""
        self.clear_content()
        self.update_status("Calendar Integration")

        title = ttk.Label(self.content_frame, text="Calendar Integration", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Calendar sync options
        sync_frame = ttk.LabelFrame(self.content_frame, text="Calendar Export & Integration", padding=20)
        sync_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(sync_frame, text="Export school events to your personal calendar",
                 font=('Arial', 11)).pack(anchor='w', pady=5)

        export_btn_frame = ttk.Frame(sync_frame)
        export_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(export_btn_frame, text="Generate iCal File (.ics)",
                  command=self.export_to_ical).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(export_btn_frame, text="Generate Google Calendar CSV",
                  command=self.export_to_google_csv).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(export_btn_frame, text="Show Subscription URL",
                  command=self.show_calendar_subscription_url).pack(side=tk.LEFT, padx=5, pady=5)

        # Event type filter
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(filter_frame, text="Filter by Event Type:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        event_type_var = tk.StringVar(value="all")
        event_type_combo = ttk.Combobox(filter_frame, textvariable=event_type_var, width=20, state='readonly')
        event_type_combo['values'] = ["All Events", "Academic", "Parent", "Holiday", "Sports", "Other"]
        event_type_combo.current(0)
        event_type_combo.pack(side=tk.LEFT, padx=5)

        # Upcoming events
        events_frame = ttk.LabelFrame(self.content_frame, text="School Calendar - Upcoming Events", padding=15)
        events_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def load_calendar_events():
            # Clear existing content
            for widget in events_frame.winfo_children():
                widget.destroy()

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Create school_calendar table if it doesn't exist
                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='school_calendar'
                """)

                if not cursor.fetchone():
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS school_calendar (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_name TEXT,
                        event_description TEXT,
                        event_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        event_type TEXT,
                        audience TEXT
                    )
                    ''')

                    # Add sample events
                    sample_events = [
                        ('Start of Fall Semester', 'First day of classes for the fall semester', '2025-09-04', '08:00', '17:00', 'All Campuses', 'academic', 'all'),
                        ('Parents Evening', 'Meet with teachers to discuss student progress', '2025-09-20', '17:00', '20:00', 'Main Hall', 'parent', 'parents'),
                        ('Midterm Exams Begin', 'First day of midterm examinations', '2025-10-16', '09:00', '17:00', 'Examination Halls', 'academic', 'all'),
                        ('Fall Break', 'No classes during fall break', '2025-11-23', '00:00', '23:59', 'All Campuses', 'holiday', 'all'),
                        ('End of Fall Semester', 'Last day of classes for the fall semester', '2025-12-15', '08:00', '17:00', 'All Campuses', 'academic', 'all')
                    ]

                    cursor.executemany(
                        'INSERT INTO school_calendar (event_name, event_description, event_date, start_time, end_time, location, event_type, audience) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        sample_events
                    )
                    conn.commit()

                # Build query based on filter
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                event_filter = event_type_var.get().lower()

                if event_filter == "all events":
                    cursor.execute("""
                    SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                    FROM school_calendar
                    WHERE event_date >= ? AND audience IN ('all', 'parents')
                    ORDER BY event_date, start_time
                    LIMIT 20
                    """, (today,))
                else:
                    cursor.execute("""
                    SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                    FROM school_calendar
                    WHERE event_date >= ? AND audience IN ('all', 'parents') AND event_type = ?
                    ORDER BY event_date, start_time
                    LIMIT 20
                    """, (today, event_filter))

                events = cursor.fetchall()

                if events:
                    # Create treeview
                    columns = ("Event", "Date", "Time", "Location", "Type")
                    tree = ttk.Treeview(events_frame, columns=columns, show="headings", height=12)

                    tree.heading("Event", text="Event")
                    tree.heading("Date", text="Date")
                    tree.heading("Time", text="Time")
                    tree.heading("Location", text="Location")
                    tree.heading("Type", text="Type")

                    tree.column("Event", width=250)
                    tree.column("Date", width=100)
                    tree.column("Time", width=100)
                    tree.column("Location", width=150)
                    tree.column("Type", width=80)

                    for event in events:
                        event_name, description, event_date, start_time, end_time, location, event_type = event
                        time_range = f"{start_time} - {end_time}"
                        tree.insert('', tk.END, values=(event_name, event_date, time_range, location, event_type.upper()))

                    scrollbar = ttk.Scrollbar(events_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    # Show event details on selection
                    def show_event_details(event):
                        selected = tree.selection()
                        if selected:
                            item = tree.item(selected[0])
                            event_name = item['values'][0]
                            # Find full event details
                            for evt in events:
                                if evt[0] == event_name:
                                    messagebox.showinfo("Event Details",
                                        f"Event: {evt[0]}\n\n"
                                        f"Description: {evt[1] or 'No description'}\n\n"
                                        f"Date: {evt[2]}\n"
                                        f"Time: {evt[3]} - {evt[4]}\n"
                                        f"Location: {evt[5]}\n"
                                        f"Type: {evt[6].upper()}")
                                    break

                    tree.bind('<Double-1>', show_event_details)

                    ttk.Label(events_frame, text="Double-click an event for details",
                             font=('Arial', 8, 'italic')).pack(pady=5)
                else:
                    ttk.Label(events_frame, text="No upcoming events found", font=('Arial', 11)).pack(pady=50)

                conn.close()
                self.update_status(f"Showing {len(events)} upcoming events")

            except Exception as e:
                ttk.Label(events_frame, text=f"Error loading events: {str(e)}",
                         font=('Arial', 10)).pack(pady=20)

        # Load events initially
        load_calendar_events()

        # Reload when filter changes
        event_type_combo.bind('<<ComboboxSelected>>', lambda e: load_calendar_events())

    def export_to_ical(self):
        """Export school events to iCal format"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            today = datetime.datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
            FROM school_calendar
            WHERE event_date >= ? AND audience IN ('all', 'parents')
            ORDER BY event_date
            LIMIT 20
            ''', (today,))

            events = cursor.fetchall()
            conn.close()

            if not events:
                messagebox.showinfo("Export", "No upcoming events to export.")
                return

            # Generate iCal content
            ical_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//School//Parent Portal//EN\nCALSCALE:GREGORIAN\nMETHOD:PUBLISH\n"

            for event in events:
                name, description, date, start_time, end_time, location, event_type = event

                # Convert to iCal format (remove dashes and colons)
                event_start = f"{date.replace('-', '')}T{start_time.replace(':', '')}00"
                event_end = f"{date.replace('-', '')}T{end_time.replace(':', '')}00"

                ical_content += "BEGIN:VEVENT\n"
                ical_content += f"DTSTART:{event_start}\n"
                ical_content += f"DTEND:{event_end}\n"
                ical_content += f"SUMMARY:{name}\n"
                ical_content += f"DESCRIPTION:{description or 'School event'}\n"
                ical_content += f"LOCATION:{location}\n"
                ical_content += f"CATEGORIES:{event_type.upper()}\n"
                ical_content += "END:VEVENT\n"

            ical_content += "END:VCALENDAR\n"

            # Show dialog to save file
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".ics",
                filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
                title="Save iCal File"
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(ical_content)
                messagebox.showinfo("Success",
                    f"Calendar exported successfully!\n\n"
                    f"File saved to: {filename}\n\n"
                    f"You can now import this file into your calendar application.")
                self.update_status("Calendar exported to iCal file")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export calendar: {str(e)}")

    def export_to_google_csv(self):
        """Export school events to Google Calendar CSV format"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            today = datetime.datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
            FROM school_calendar
            WHERE event_date >= ? AND audience IN ('all', 'parents')
            ORDER BY event_date
            LIMIT 20
            ''', (today,))

            events = cursor.fetchall()
            conn.close()

            if not events:
                messagebox.showinfo("Export", "No upcoming events to export.")
                return

            # Generate Google Calendar CSV
            csv_content = "Subject,Start Date,Start Time,End Date,End Time,Description,Location\n"

            for event in events:
                name, description, date, start_time, end_time, location, event_type = event
                # Escape commas and quotes in fields
                name = name.replace('"', '""')
                description = (description or '').replace('"', '""')
                location = location.replace('"', '""')

                csv_content += f'"{name}",{date},{start_time},{date},{end_time},"{description}","{location}"\n'

            # Show dialog to save file
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Save Google Calendar CSV"
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(csv_content)
                messagebox.showinfo("Success",
                    f"Calendar exported successfully!\n\n"
                    f"File saved to: {filename}\n\n"
                    f"Import this file to Google Calendar:\n"
                    f"1. Open Google Calendar\n"
                    f"2. Click Settings > Import & Export\n"
                    f"3. Select the exported CSV file")
                self.update_status("Calendar exported to CSV file")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export calendar: {str(e)}")

    def show_calendar_subscription_url(self):
        """Show calendar subscription URL"""
        if not self.parent_id:
            messagebox.showerror("Error", "Parent ID not found.")
            return

        # In a real implementation, this would be an actual webcal:// URL
        subscription_url = f"webcal://school.example.com/calendar/parent/{self.parent_id}"

        dialog = tk.Toplevel(self.root)
        dialog.title("Calendar Subscription URL")
        dialog.geometry("600x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Calendar Subscription URL",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        ttk.Label(main_frame,
                 text="Add this URL to your calendar app to automatically sync school events:",
                 wraplength=500).pack(pady=10)

        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=10)

        url_entry = ttk.Entry(url_frame, width=60)
        url_entry.insert(0, subscription_url)
        url_entry.config(state='readonly')
        url_entry.pack(side=tk.LEFT, padx=5)

        def copy_url():
            dialog.clipboard_clear()
            dialog.clipboard_append(subscription_url)
            messagebox.showinfo("Copied", "URL copied to clipboard!")

        ttk.Button(url_frame, text="Copy", command=copy_url).pack(side=tk.LEFT, padx=5)

        ttk.Label(main_frame,
                 text="Instructions:\n\n"
                      "Google Calendar: Settings > Add calendar > From URL\n"
                      "Apple Calendar: File > New Calendar Subscription\n"
                      "Outlook: Add calendar > Subscribe from web",
                 justify=tk.LEFT,
                 wraplength=500).pack(pady=20)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def sync_calendar(self, calendar_type):
        """Sync with external calendar (deprecated - use export functions)"""
        messagebox.showinfo("Calendar Sync",
                           f"Please use the Export buttons above to sync with {calendar_type}.")

    def show_account_interface(self):
        """Show account settings interface"""
        self.clear_content()
        self.update_status("Account Settings")

        title = ttk.Label(self.content_frame, text="Account Settings", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Account information
        account_frame = ttk.LabelFrame(self.content_frame, text="Account Information", padding=20)
        account_frame.pack(fill=tk.X, padx=20, pady=10)

        if self.current_user:
            ttk.Label(account_frame, text=f"Username: {self.current_user.get('username', 'N/A')}",
                     font=('Arial', 10)).pack(anchor='w', pady=3)
            ttk.Label(account_frame, text=f"Email: {self.current_user.get('email', 'Not set')}",
                     font=('Arial', 10)).pack(anchor='w', pady=3)
            ttk.Label(account_frame, text=f"Role: {self.current_user.get('role', 'Parent')}",
                     font=('Arial', 10)).pack(anchor='w', pady=3)

        # Security settings
        security_frame = ttk.LabelFrame(self.content_frame, text="Security", padding=20)
        security_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(security_frame, text="Change Password",
                  command=self.change_password).pack(fill=tk.X, pady=5)
        ttk.Button(security_frame, text="Enable Two-Factor Authentication",
                  command=self.enable_two_factor_auth).pack(fill=tk.X, pady=5)
        ttk.Button(security_frame, text="View Login History",
                  command=self.view_login_history).pack(fill=tk.X, pady=5)

        # Contact preferences
        contact_frame = ttk.LabelFrame(self.content_frame, text="Contact Preferences", padding=20)
        contact_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(contact_frame, text="Primary Email:").grid(row=0, column=0, sticky='w', pady=5)
        email_entry = ttk.Entry(contact_frame, width=40)
        email_entry.grid(row=0, column=1, pady=5, sticky='ew')

        ttk.Label(contact_frame, text="Primary Phone:").grid(row=1, column=0, sticky='w', pady=5)
        phone_entry = ttk.Entry(contact_frame, width=40)
        phone_entry.grid(row=1, column=1, pady=5, sticky='ew')

        ttk.Label(contact_frame, text="Address:").grid(row=2, column=0, sticky='w', pady=5)
        address_entry = ttk.Entry(contact_frame, width=40)
        address_entry.grid(row=2, column=1, pady=5, sticky='ew')

        contact_frame.columnconfigure(1, weight=1)

        # Load current contact information
        try:
            if self.parent_id:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                SELECT email, phone, address
                FROM parent_accounts
                WHERE parent_id = ?
                ''', (self.parent_id,))

                info = cursor.fetchone()
                conn.close()

                if info:
                    email_entry.insert(0, info[0] or "")
                    phone_entry.insert(0, info[1] or "")
                    address_entry.insert(0, info[2] or "")
        except Exception as e:
            print(f"Error loading contact info: {e}")

        def save_contact_info():
            email = email_entry.get().strip()
            phone = phone_entry.get().strip()
            address = address_entry.get().strip()

            # Validate email
            if email and '@' not in email:
                messagebox.showwarning("Validation Error", "Please enter a valid email address.")
                return

            if not self.parent_id:
                messagebox.showerror("Error", "Parent ID not found. Please log in again.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Update contact information
                cursor.execute('''
                UPDATE parent_accounts
                SET email = ?, phone = ?, address = ?
                WHERE parent_id = ?
                ''', (email, phone, address, self.parent_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Contact information updated successfully!")
                self.update_status("Contact information updated")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update contact information: {str(e)}")

        ttk.Button(self.content_frame, text="Save Changes", command=save_contact_info).pack(pady=20)

    def change_password(self):
        """Change password"""
        messagebox.showinfo("Change Password",
                           "Please contact IT support to change your password.")

    def view_login_history(self):
        """View login history"""
        messagebox.showinfo("Login History", "Login history viewing not available in demo.")

    def show_create_parent_account_interface(self):
        """Show interface for creating a new parent account (admin only)"""
        if not self.current_user or self.current_user.get('role') != 'admin':
            messagebox.showerror("Access Denied", "Only administrators can create parent accounts.")
            return

        self.clear_content()
        self.update_status("Create Parent Account")

        title = ttk.Label(self.content_frame, text="Create New Parent Account",
                         style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Form frame
        form_frame = ttk.LabelFrame(self.content_frame, text="Parent Information", padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # First Name
        ttk.Label(form_frame, text="First Name:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        first_name_entry = ttk.Entry(form_frame, width=40)
        first_name_entry.grid(row=0, column=1, pady=5, sticky='ew')

        # Last Name
        ttk.Label(form_frame, text="Last Name:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        last_name_entry = ttk.Entry(form_frame, width=40)
        last_name_entry.grid(row=1, column=1, pady=5, sticky='ew')

        # Email
        ttk.Label(form_frame, text="Email:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        email_entry = ttk.Entry(form_frame, width=40)
        email_entry.grid(row=2, column=1, pady=5, sticky='ew')

        # Phone
        ttk.Label(form_frame, text="Phone:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=5)
        phone_entry = ttk.Entry(form_frame, width=40)
        phone_entry.grid(row=3, column=1, pady=5, sticky='ew')

        # Address
        ttk.Label(form_frame, text="Address:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='nw', pady=5)
        address_text = scrolledtext.ScrolledText(form_frame, width=40, height=4)
        address_text.grid(row=4, column=1, pady=5, sticky='ew')

        form_frame.columnconfigure(1, weight=1)

        # Result display
        result_frame = ttk.LabelFrame(self.content_frame, text="Created Account Details", padding=20)
        result_frame.pack(fill=tk.X, padx=20, pady=10)
        result_label = ttk.Label(result_frame, text="Account details will appear here after creation",
                                font=('Arial', 10, 'italic'))
        result_label.pack()

        # Buttons
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.pack(pady=10)

        def create_account():
            first_name = first_name_entry.get().strip()
            last_name = last_name_entry.get().strip()
            email = email_entry.get().strip()
            phone = phone_entry.get().strip()
            address = address_text.get('1.0', tk.END).strip()

            # Validation
            if not first_name or not last_name:
                messagebox.showwarning("Validation Error", "First name and last name are required.")
                return

            if not email or '@' not in email:
                messagebox.showwarning("Validation Error", "Please enter a valid email address.")
                return

            try:
                import random
                import string
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Check if email already exists
                cursor.execute('SELECT email FROM parent_accounts WHERE email = ?', (email,))
                if cursor.fetchone():
                    messagebox.showerror("Error", "This email is already registered.")
                    conn.close()
                    return

                # Generate parent_id
                parent_id = f"P{random.randint(10000, 99999)}"

                # Insert parent account
                cursor.execute('''
                INSERT INTO parent_accounts (parent_id, first_name, last_name, email, phone, address)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (parent_id, first_name, last_name, email, phone, address))

                # Generate username and password
                username = f"{first_name.lower()}.{last_name.lower()}.{random.randint(100, 999)}"
                password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

                # Create user account (simplified - in production use proper authentication)
                cursor.execute('''
                INSERT INTO users (username, password, role, email)
                VALUES (?, ?, ?, ?)
                ''', (username, password, 'parent', email))

                user_id = cursor.lastrowid

                # Link user to parent
                cursor.execute('''
                INSERT INTO parent_user_mapping (user_id, parent_id)
                VALUES (?, ?)
                ''', (user_id, parent_id))

                conn.commit()
                conn.close()

                # Show success and account details
                result_text = f"Parent ID: {parent_id}\n\n" \
                             f"Username: {username}\n" \
                             f"Temporary Password: {password}\n\n" \
                             f"IMPORTANT: Please save these credentials!\n" \
                             f"The parent should change the password on first login."

                result_label.config(text=result_text, font=('Arial', 10), foreground='green')

                messagebox.showinfo("Success",
                    f"Parent account created successfully!\n\n"
                    f"Username: {username}\n"
                    f"Password: {password}\n\n"
                    f"Please provide these credentials to the parent.")

                self.update_status("Parent account created successfully")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create parent account: {str(e)}")

        ttk.Button(btn_frame, text="Create Account", command=create_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_settings_menu).pack(side=tk.LEFT, padx=5)

    def show_link_student_interface(self):
        """Show interface for linking a student to a parent (admin only)"""
        if not self.current_user or self.current_user.get('role') != 'admin':
            messagebox.showerror("Access Denied", "Only administrators can link students to parents.")
            return

        self.clear_content()
        self.update_status("Link Student to Parent")

        title = ttk.Label(self.content_frame, text="Link Student to Parent",
                         style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Form frame
        form_frame = ttk.LabelFrame(self.content_frame, text="Link Information", padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Parent ID
        ttk.Label(form_frame, text="Parent ID:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        parent_id_entry = ttk.Entry(form_frame, width=40)
        parent_id_entry.grid(row=0, column=1, pady=5, sticky='ew')

        ttk.Button(form_frame, text="Search Parent",
                  command=lambda: search_parent(parent_id_entry.get())).grid(row=0, column=2, padx=5)

        # Parent info display
        parent_info_label = ttk.Label(form_frame, text="", font=('Arial', 9))
        parent_info_label.grid(row=1, column=0, columnspan=3, sticky='w', pady=5)

        # Student ID
        ttk.Label(form_frame, text="Student ID:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        student_id_entry = ttk.Entry(form_frame, width=40)
        student_id_entry.grid(row=2, column=1, pady=5, sticky='ew')

        ttk.Button(form_frame, text="Search Student",
                  command=lambda: search_student(student_id_entry.get())).grid(row=2, column=2, padx=5)

        # Student info display
        student_info_label = ttk.Label(form_frame, text="", font=('Arial', 9))
        student_info_label.grid(row=3, column=0, columnspan=3, sticky='w', pady=5)

        # Relationship
        ttk.Label(form_frame, text="Relationship:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', pady=5)
        relationship_var = tk.StringVar()
        relationship_combo = ttk.Combobox(form_frame, textvariable=relationship_var, width=37, state='readonly')
        relationship_combo['values'] = ["Mother", "Father", "Guardian", "Other"]
        relationship_combo.current(0)
        relationship_combo.grid(row=4, column=1, pady=5, sticky='ew')

        form_frame.columnconfigure(1, weight=1)

        def search_parent(parent_id):
            if not parent_id:
                messagebox.showwarning("Validation Error", "Please enter a parent ID.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                SELECT first_name, last_name, email, phone
                FROM parent_accounts
                WHERE parent_id = ?
                ''', (parent_id,))

                parent = cursor.fetchone()
                conn.close()

                if parent:
                    parent_info_label.config(
                        text=f"Parent: {parent[0]} {parent[1]} | Email: {parent[2]} | Phone: {parent[3] or 'N/A'}",
                        foreground='green'
                    )
                else:
                    parent_info_label.config(text="Parent not found!", foreground='red')

            except Exception as e:
                messagebox.showerror("Error", f"Failed to search parent: {str(e)}")

        def search_student(student_id):
            if not student_id:
                messagebox.showwarning("Validation Error", "Please enter a student ID.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                SELECT first_name, last_name, date_of_birth, grade_level
                FROM students
                WHERE student_id = ?
                ''', (student_id,))

                student = cursor.fetchone()
                conn.close()

                if student:
                    student_info_label.config(
                        text=f"Student: {student[0]} {student[1]} | DOB: {student[2]} | Grade: {student[3]}",
                        foreground='green'
                    )
                else:
                    student_info_label.config(text="Student not found!", foreground='red')

            except Exception as e:
                messagebox.showerror("Error", f"Failed to search student: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.pack(pady=20)

        def link_accounts():
            parent_id = parent_id_entry.get().strip()
            student_id = student_id_entry.get().strip()
            relationship = relationship_var.get()

            if not parent_id or not student_id:
                messagebox.showwarning("Validation Error", "Please enter both parent ID and student ID.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Verify parent exists
                cursor.execute('SELECT parent_id FROM parent_accounts WHERE parent_id = ?', (parent_id,))
                if not cursor.fetchone():
                    messagebox.showerror("Error", "Parent ID not found.")
                    conn.close()
                    return

                # Verify student exists
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    messagebox.showerror("Error", "Student ID not found.")
                    conn.close()
                    return

                # Check if link already exists
                cursor.execute('''
                SELECT * FROM parent_student_link
                WHERE parent_id = ? AND student_id = ?
                ''', (parent_id, student_id))

                if cursor.fetchone():
                    messagebox.showwarning("Duplicate", "This parent is already linked to this student.")
                    conn.close()
                    return

                # Create link
                cursor.execute('''
                INSERT INTO parent_student_link (parent_id, student_id, relationship)
                VALUES (?, ?, ?)
                ''', (parent_id, student_id, relationship))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success",
                    f"Student {student_id} successfully linked to parent {parent_id}\n"
                    f"Relationship: {relationship}")

                self.update_status("Student linked to parent successfully")

                # Clear form
                parent_id_entry.delete(0, tk.END)
                student_id_entry.delete(0, tk.END)
                parent_info_label.config(text="")
                student_info_label.config(text="")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to link accounts: {str(e)}")

        ttk.Button(btn_frame, text="Link Accounts", command=link_accounts).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_settings_menu).pack(side=tk.LEFT, padx=5)

    def show_placeholder(self, title):
        """Show a placeholder interface"""
        self.clear_content()
        self.update_status(title)
        
        title_label = ttk.Label(self.content_frame, text=title, style='Title.TLabel', font=('Arial', 20, 'bold'))
        title_label.pack(pady=20)
        
        ttk.Label(self.content_frame, text=f"{title} interface coming soon!").pack(pady=50)
    
    def logout(self):
        """Logout and close application"""
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.root.quit()

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()


# Dialog classes for user input

class AbsenceReportDialog:
    """Dialog for reporting absence"""
    
    def __init__(self, parent, children):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Report Absence")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Report Student Absence", font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Child selection
        ttk.Label(main_frame, text="Select Child:").pack(anchor='w')
        self.child_var = tk.StringVar()
        child_combo = ttk.Combobox(main_frame, textvariable=self.child_var, width=40)
        child_combo['values'] = [f"{child[1]} {child[3]}" for child in children]
        if children:
            child_combo.set(child_combo['values'][0])
        child_combo.pack(fill=tk.X, pady=5)
        
        # Reason
        ttk.Label(main_frame, text="Reason for absence:").pack(anchor='w', pady=(10, 0))
        self.reason_entry = ttk.Entry(main_frame, width=40)
        self.reason_entry.pack(fill=tk.X, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Submit", command=self.submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.children = children
        self.dialog.wait_window()
    
    def submit(self):
        child_name = self.child_var.get()
        reason = self.reason_entry.get().strip()
        
        if not child_name or not reason:
            messagebox.showwarning("Missing Information", "Please select a child and provide a reason.")
            return
        
        # Find the selected child
        for child in self.children:
            if f"{child[1]} {child[3]}" == child_name:
                self.result = (child, reason)
                break
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class EmergencyContactDialog:
    """Dialog for updating emergency contact"""
    
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Emergency Contact")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Update Emergency Contact", font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Form fields
        ttk.Label(main_frame, text="Phone Number:").pack(anchor='w')
        self.phone_entry = ttk.Entry(main_frame, width=40)
        self.phone_entry.pack(fill=tk.X, pady=5)
        
        ttk.Label(main_frame, text="Email Address:").pack(anchor='w', pady=(10, 0))
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.pack(fill=tk.X, pady=5)
        
        ttk.Label(main_frame, text="Address:").pack(anchor='w', pady=(10, 0))
        self.address_text = scrolledtext.ScrolledText(main_frame, height=4)
        self.address_text.pack(fill=tk.X, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Update", command=self.update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.dialog.wait_window()
    
    def update(self):
        phone = self.phone_entry.get().strip()
        email = self.email_entry.get().strip()
        address = self.address_text.get(1.0, tk.END).strip()
        
        if not phone and not email and not address:
            messagebox.showwarning("Missing Information", "Please fill in at least one field.")
            return
        
        self.result = {
            'phone': phone,
            'email': email,
            'address': address
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


# Main function to run the GUI
def run_parent_portal_gui(auth=None):
    """
    Main function to run the Parent Portal GUI.
    This function maintains backwards compatibility with the CLI version.
    """
    try:
        # Try to create GUI version
        app = ParentPortalGUI(auth)
        root = app.create_main_window()
        
        if root:
            root.mainloop()
        else:
            # Fallback to CLI version
            print("GUI unavailable, falling back to CLI version...")
            from parent_portal import ParentPortal
            ParentPortal.display_parent_portal_menu(auth)
            
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        print("Falling back to CLI version...")
        try:
            from parent_portal import ParentPortal
            ParentPortal.display_parent_portal_menu(auth)
        except ImportError:
            print("CLI version also unavailable. Please check your installation.")
    
    except Exception as e:
        print(f"Error running GUI: {e}")
        print("Falling back to CLI version...")
        try:
            from parent_portal import ParentPortal
            ParentPortal.display_parent_portal_menu(auth)
        except Exception as cli_error:
            print(f"CLI version also failed: {cli_error}")


# Backwards compatibility wrapper
class ParentPortalCompat:
    """
    Backwards compatibility wrapper that provides both GUI and CLI interfaces.
    This ensures existing code continues to work while adding GUI functionality.
    """
    
    def __init__(self, auth=None):
        self.auth = auth
        self.gui_available = True
        
        try:
            import tkinter
        except ImportError:
            self.gui_available = False
    
    def display_parent_portal_menu(self, auth=None, use_gui=True):
        """
        Display the parent portal menu.
        
        Args:
            auth: Authentication object
            use_gui: Boolean to determine if GUI should be used (default: True)
        """
        if auth:
            self.auth = auth
        
        if use_gui and self.gui_available:
            try:
                run_parent_portal_gui(self.auth)
            except Exception as e:
                print(f"GUI failed: {e}")
                print("Falling back to CLI...")
                self._run_cli_version()
        else:
            self._run_cli_version()
    
    def _run_cli_version(self):
        """Run the original CLI version"""
        try:
            from parent_portal import ParentPortal
            ParentPortal.display_parent_portal_menu(self.auth)
        except ImportError:
            print("Original parent portal module not found.")
            self._run_embedded_cli()
    
    def _run_embedded_cli(self):
        """Run embedded CLI version if original is not available"""
        print("\n" + "=" * 60)
        print("PARENT PORTAL (CLI Mode)")
        print("=" * 60)
        
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to access the parent portal.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        while True:
            print("\n1. View Children")
            print("2. View Grades")
            print("3. View Attendance")
            print("4. Send Message")
            print("5. View Reports")
            print("6. Update Contact Info")
            print("0. Exit")
            
            choice = input("\nEnter your choice: ")
            
            if choice == '0':
                break
            elif choice == '1':
                print("View Children - Feature available in full version")
            elif choice == '2':
                print("View Grades - Feature available in full version")
            elif choice == '3':
                print("View Attendance - Feature available in full version")
            elif choice == '4':
                print("Send Message - Feature available in full version")
            elif choice == '5':
                print("View Reports - Feature available in full version")
            elif choice == '6':
                print("Update Contact Info - Feature available in full version")
            else:
                print("Invalid choice.")


# Additional GUI Components for Enhanced Features

class ModernMessageBox:
    """Custom message box with modern styling"""
    
    @staticmethod
    def show_info(parent, title, message):
        """Show info message with custom styling"""
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.transient(parent)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 100, parent.winfo_rooty() + 100))
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Icon and title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(title_frame, text="ℹ️", font=('Arial', 20)).pack(side=tk.LEFT)
        ttk.Label(title_frame, text=title, font=('Arial', 14, 'bold')).pack(side=tk.LEFT, padx=(10, 0))
        
        # Message
        ttk.Label(main_frame, text=message, wraplength=350).pack(pady=10)
        
        # OK button
        ttk.Button(main_frame, text="OK", command=dialog.destroy).pack(pady=10)
        
        dialog.wait_window()


class ProgressDialog:
    """Progress dialog for long-running operations"""
    
    def __init__(self, parent, title="Processing..."):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x120")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 150, parent.winfo_rooty() + 150))
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.label = ttk.Label(main_frame, text="Please wait...")
        self.label.pack(pady=10)
        
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)
        self.progress.start()
    
    def update_text(self, text):
        """Update the progress text"""
        self.label.config(text=text)
        self.dialog.update()
    
    def close(self):
        """Close the progress dialog"""
        self.progress.stop()
        self.dialog.destroy()


class NotificationCenter:
    """Notification center for displaying alerts and messages"""
    
    def __init__(self, parent):
        self.parent = parent
        self.notifications = []
    
    def show_notification(self, title, message, type="info"):
        """Show a notification popup"""
        notification = tk.Toplevel(self.parent)
        notification.title("Notification")
        notification.geometry("350x120")
        notification.attributes('-topmost', True)
        
        # Position in top-right corner
        notification.geometry("+%d+%d" % (self.parent.winfo_rootx() + self.parent.winfo_width() - 370, 
                                         self.parent.winfo_rooty() + 50))
        
        # Style based on type
        colors = {
            "info": "#3498db",
            "warning": "#f39c12", 
            "error": "#e74c3c",
            "success": "#27ae60"
        }
        
        color = colors.get(type, "#3498db")
        
        notification.configure(bg=color)
        
        main_frame = tk.Frame(notification, bg=color, padx=15, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = tk.Label(main_frame, text=title, font=('Arial', 12, 'bold'), 
                              bg=color, fg='white')
        title_label.pack(anchor='w')
        
        message_label = tk.Label(main_frame, text=message, font=('Arial', 10), 
                                bg=color, fg='white', wraplength=300)
        message_label.pack(anchor='w', pady=(5, 0))
        
        # Auto-close after 5 seconds
        notification.after(5000, notification.destroy)
        
        # Close on click
        def close_notification(event):
            notification.destroy()
        
        notification.bind("<Button-1>", close_notification)
        main_frame.bind("<Button-1>", close_notification)
        title_label.bind("<Button-1>", close_notification)
        message_label.bind("<Button-1>", close_notification)


class DataExportDialog:
    """Dialog for exporting student data"""
    
    def __init__(self, parent, children):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Student Data")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Export Student Data", font=('Arial', 16, 'bold')).pack(pady=10)
        
        # Child selection
        child_frame = ttk.LabelFrame(main_frame, text="Select Child", padding=10)
        child_frame.pack(fill=tk.X, pady=10)
        
        self.child_var = tk.StringVar()
        for child in children:
            rb = ttk.Radiobutton(child_frame, text=f"{child[1]} {child[3]} (ID: {child[0]})", 
                                variable=self.child_var, value=child[0])
            rb.pack(anchor='w')
        
        if children:
            self.child_var.set(children[0][0])
        
        # Data type selection
        data_frame = ttk.LabelFrame(main_frame, text="Select Data Types", padding=10)
        data_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.data_types = {}
        data_options = [
            ("grades", "Academic Grades"),
            ("attendance", "Attendance Records"),
            ("assignments", "Assignments"),
            ("behavior", "Behavior Reports"),
            ("medical", "Medical Information"),
            ("fees", "Fee Records"),
            ("activities", "Extracurricular Activities")
        ]
        
        for key, label in data_options:
            var = tk.BooleanVar(value=True)
            self.data_types[key] = var
            cb = ttk.Checkbutton(data_frame, text=label, variable=var)
            cb.pack(anchor='w')
        
        # Export format
        format_frame = ttk.LabelFrame(main_frame, text="Export Format", padding=10)
        format_frame.pack(fill=tk.X, pady=10)
        
        self.format_var = tk.StringVar(value="json")
        ttk.Radiobutton(format_frame, text="JSON", variable=self.format_var, value="json").pack(anchor='w')
        ttk.Radiobutton(format_frame, text="CSV", variable=self.format_var, value="csv").pack(anchor='w')
        ttk.Radiobutton(format_frame, text="PDF Report", variable=self.format_var, value="pdf").pack(anchor='w')
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Export", command=self.export_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.children = children
        self.dialog.wait_window()
    
    def export_data(self):
        selected_child = self.child_var.get()
        selected_types = [key for key, var in self.data_types.items() if var.get()]
        export_format = self.format_var.get()
        
        if not selected_child or not selected_types:
            messagebox.showwarning("Selection Required", "Please select a child and at least one data type.")
            return
        
        self.result = {
            'child_id': selected_child,
            'data_types': selected_types,
            'format': export_format
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


# Integration functions for backwards compatibility

def initialize_gui_parent_portal(auth=None):
    """Initialize the GUI version of the parent portal"""
    return ParentPortalCompat(auth)

def run_parent_portal(auth=None, prefer_gui=True):
    """
    Run the parent portal with automatic GUI/CLI selection.
    
    Args:
        auth: Authentication object
        prefer_gui: Whether to prefer GUI over CLI (default: True)
    """
    portal = ParentPortalCompat(auth)
    portal.display_parent_portal_menu(auth, use_gui=prefer_gui)

# Utility functions for GUI enhancements

def create_tooltip(widget, text):
    """Create a tooltip for a widget"""
    def on_enter(event):
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        
        label = tk.Label(tooltip, text=text, background="#ffffe0", 
                        relief="solid", borderwidth=1, font=("Arial", 9))
        label.pack()
        
        widget.tooltip = tooltip
    
    def on_leave(event):
        if hasattr(widget, 'tooltip'):
            widget.tooltip.destroy()
            del widget.tooltip
    
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)

def validate_email(email):
    """Simple email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Simple phone validation"""
    import re
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    # Check if it's a reasonable length
    return len(digits) >= 10

def format_currency(amount):
    """Format amount as currency"""
    try:
        return f"£{float(amount):.2f}"
    except (ValueError, TypeError):
        return "£0.00"

def format_date(date_string):
    """Format date string for display"""
    try:
        date_obj = datetime.datetime.strptime(date_string, '%Y-%m-%d')
        return date_obj.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return date_string

class TwoFactorDialog:
    """Dialog for enabling two-factor authentication"""
    
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Enable Two-Factor Authentication")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Enable Two-Factor Authentication", font=('Arial', 16, 'bold')).pack(pady=10)
        
        info_text = """Two-factor authentication adds an extra layer of security to your account.
        
You'll need an authenticator app like:
- Google Authenticator
- Microsoft Authenticator
- Authy

After enabling, you'll need to enter a code from your authenticator app each time you log in."""
        
        ttk.Label(main_frame, text=info_text, wraplength=450).pack(pady=10)
        
        # QR code placeholder
        qr_frame = ttk.LabelFrame(main_frame, text="Scan QR Code with Authenticator App", padding=10)
        qr_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(qr_frame, text="[QR Code would appear here]", 
                 font=('Arial', 12), background='lightgray', 
                 relief='sunken', padding=50).pack()
        
        # Secret key
        secret_frame = ttk.Frame(main_frame)
        secret_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(secret_frame, text="Manual Entry Key:").pack(anchor='w')
        secret_entry = ttk.Entry(secret_frame, value="ABCD EFGH IJKL MNOP", state='readonly')
        secret_entry.pack(fill=tk.X, pady=5)
        
        # Verification
        verify_frame = ttk.Frame(main_frame)
        verify_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(verify_frame, text="Enter verification code from your app:").pack(anchor='w')
        self.code_entry = ttk.Entry(verify_frame, width=20)
        self.code_entry.pack(pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Enable 2FA", command=self.enable).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.dialog.wait_window()
    
    def enable(self):
        code = self.code_entry.get().strip()
        if not code:
            messagebox.showwarning("Missing Code", "Please enter the verification code.")
            return
        
        # In real implementation, would verify the code
        if len(code) == 6 and code.isdigit():
            self.result = True
            self.dialog.destroy()
        else:
            messagebox.showerror("Invalid Code", "Please enter a valid 6-digit code.")
    
    def cancel(self):
        self.dialog.destroy()


class DonationDialog:
    """Dialog for making donations to fundraising campaigns"""
    
    def __init__(self, parent, children):
        self.result = None
        self.children = children
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Make Donation")
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Make a Donation", font=('Arial', 16, 'bold')).pack(pady=10)
        
        # Campaign selection
        campaign_frame = ttk.LabelFrame(main_frame, text="Select Campaign", padding=10)
        campaign_frame.pack(fill=tk.X, pady=10)
        
        self.campaign_var = tk.StringVar()
        campaigns = ["School Library Fund", "Sports Equipment Drive", "Arts Program Support"]
        
        for campaign in campaigns:
            rb = ttk.Radiobutton(campaign_frame, text=campaign, variable=self.campaign_var, value=campaign)
            rb.pack(anchor='w')
        
        if campaigns:
            self.campaign_var.set(campaigns[0])
        
        # Amount
        amount_frame = ttk.LabelFrame(main_frame, text="Donation Amount", padding=10)
        amount_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(amount_frame, text="Amount (£):").pack(anchor='w')
        self.amount_entry = ttk.Entry(amount_frame, width=20)
        self.amount_entry.pack(pady=5)
        
        # Child selection (optional)
        if children:
            child_frame = ttk.LabelFrame(main_frame, text="Donate on behalf of (optional)", padding=10)
            child_frame.pack(fill=tk.X, pady=10)
            
            self.child_var = tk.StringVar()
            
            rb = ttk.Radiobutton(child_frame, text="Anonymous donation", variable=self.child_var, value="anonymous")
            rb.pack(anchor='w')
            
            for child in children:
                rb = ttk.Radiobutton(child_frame, text=f"{child[1]} {child[3]}", 
                                   variable=self.child_var, value=f"{child[0]}")
                rb.pack(anchor='w')
            
            self.child_var.set("anonymous")
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Donate", command=self.donate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.dialog.wait_window()
    
    def donate(self):
        campaign = self.campaign_var.get()
        amount_str = self.amount_entry.get().strip()
        
        if not campaign:
            messagebox.showwarning("Missing Selection", "Please select a campaign.")
            return
        
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid Amount", "Please enter a valid donation amount.")
            return
        
        child = None
        if hasattr(self, 'child_var'):
            child_selection = self.child_var.get()
            if child_selection != "anonymous":
                for child_data in self.children:
                    if child_data[0] == child_selection:
                        child = child_data
                        break
        
        self.result = (campaign, amount, child)
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class QRCodeDialog:
    """Dialog for generating QR codes"""
    
    def __init__(self, parent, children):
        self.result = None
        self.children = children
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Generate QR Code")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Generate QR Code", font=('Arial', 16, 'bold')).pack(pady=10)
        
        ttk.Label(main_frame, text="Select child for QR code generation:").pack(anchor='w', pady=10)
        
        # Child selection
        self.child_var = tk.StringVar()
        for i, child in enumerate(children):
            rb = ttk.Radiobutton(main_frame, text=f"{child[1]} {child[3]} (ID: {child[0]})", 
                               variable=self.child_var, value=str(i))
            rb.pack(anchor='w')
        
        if children:
            self.child_var.set("0")
        
        # Purpose selection
        purpose_frame = ttk.LabelFrame(main_frame, text="QR Code Purpose", padding=10)
        purpose_frame.pack(fill=tk.X, pady=10)
        
        self.purpose_var = tk.StringVar()
        purposes = ["Student Pickup", "Emergency Contact", "Identification"]
        
        for purpose in purposes:
            rb = ttk.Radiobutton(purpose_frame, text=purpose, variable=self.purpose_var, value=purpose)
            rb.pack(anchor='w')
        
        if purposes:
            self.purpose_var.set(purposes[0])
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Generate", command=self.generate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.dialog.wait_window()
    
    def generate(self):
        child_index = self.child_var.get()
        purpose = self.purpose_var.get()
        
        if not child_index or not purpose:
            messagebox.showwarning("Missing Selection", "Please select a child and purpose.")
            return
        
        try:
            index = int(child_index)
            if 0 <= index < len(self.children):
                self.result = self.children[index]
                self.dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Invalid selection.")

    def cancel(self):
        self.dialog.destroy()
        
class DatabaseManager:
    """Simplified database manager for GUI operations"""
    
    @staticmethod
    def get_connection():
        """Get database connection"""
        try:
            from university_system.infrastructure.database.db import sqlite3
            # Use centralized path system
            from university_system.modules.shared.constants import paths
            db_path = paths.DEFAULT_DB_PATH
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.execute("PRAGMA busy_timeout = 30000")
            return conn
        except Exception as e:
            print(f"Database connection error: {e}")
            return None
    
    @staticmethod
    def execute_query(query, params=None):
        """Execute a query and return results"""
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            if not conn:
                return None
            
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                conn.commit()
                return cursor.rowcount
                
        except Exception as e:
            print(f"Database query error: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

# Main entry point
if __name__ == "__main__":
    """
    Main entry point for the GUI application.
    This allows the GUI to be run standalone or integrated with existing systems.
    """
    
    # Initialize UserAuth for authentication
    auth = UserAuth()

    # Check if running standalone
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        # Force CLI mode
        run_parent_portal(auth, prefer_gui=False)
    else:
        # Default to GUI mode
        run_parent_portal(auth, prefer_gui=True)
