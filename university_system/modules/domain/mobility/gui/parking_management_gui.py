from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import logging
import threading
import os
import sys

# Import compatibility layer first
try:
    from university_system.modules.domain.mobility.services.parking_compatibility import (
        set_gui_mode, get_function_output, validate_gui_data,
        get_user_permissions, format_console_output_for_gui,
        execute_console_function_with_params, cleanup_compatibility_layer
    )
    COMPATIBILITY_AVAILABLE = True
except ImportError:
    COMPATIBILITY_AVAILABLE = False

# Import the existing parking management functions
try:
    from university_system.modules.domain.mobility.services.parking_management import (
        init_db, set_auth, PARKING_ZONES, PERMIT_TYPES, VEHICLE_TYPES,
        create_parking_permit, view_parking_permit, update_parking_permit, delete_parking_permit,
        register_vehicle, view_vehicle, update_vehicle, delete_vehicle,
        record_violation, generate_compliance_report, generate_revenue_report,
        generate_user_activity_report, export_users,
        view_violations, update_violation, delete_violation,
        view_parking_lots, add_parking_lot, update_parking_lot, delete_parking_lot,
        generate_permit_report, generate_violation_report, generate_analytics_dashboard,
        export_permits, export_vehicles, export_violations, export_parking_lots
    )
    from university_system.infrastructure.auth.user_authentication import UserAuth
    from university_system.infrastructure.database.db import get_connection
    PARKING_MANAGEMENT_AVAILABLE = True
except ImportError as e:
    PARKING_MANAGEMENT_AVAILABLE = False
    print(f"Warning: Could not import parking management modules: {e}")
    # Define fallback constants
    PARKING_ZONES = {
        'A': {'name': 'Faculty/Staff', 'hourly_rate': 0, 'annual_fee': 250},
        'B': {'name': 'Commuter Students', 'hourly_rate': 0, 'annual_fee': 180},
        'C': {'name': 'Resident Students', 'hourly_rate': 0, 'annual_fee': 220},
        'V': {'name': 'Visitor', 'hourly_rate': 2.50, 'annual_fee': 0},
        'H': {'name': 'Handicap Accessible', 'hourly_rate': 0, 'annual_fee': 150},
        'M': {'name': 'Metered', 'hourly_rate': 1.75, 'annual_fee': 0},
        'R': {'name': 'Reserved', 'hourly_rate': 0, 'annual_fee': 350},
    }
    PERMIT_TYPES = ['Annual', 'Semester', 'Monthly', 'Daily', 'Temporary']
    VEHICLE_TYPES = ['Sedan', 'SUV', 'Truck', 'Motorcycle', 'Compact', 'Van']

class ParkingManagementGUI:
    def __init__(self, root, auth_system=None):
        self.root = root
        self.root.title("Parking Management System")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)

        # Initialize authentication - use provided auth system or create new one
        if auth_system:
            self.auth = auth_system
        else:
            self.auth = UserAuth()
        set_auth(self.auth)

        # Initialize database
        init_db()

        # Current user info
        self.current_user = None

        # Setup current user from existing authentication system
        self.setup_current_user()

        # Create the main interface
        self.setup_gui()

        # Show appropriate interface based on authentication status
        if self.current_user:
            self.update_user_status()
            self.update_status("Using authenticated user session")
            self.update_tab_access()
        else:
            # User must log in through main University System GUI
            messagebox.showerror(
                "Authentication Required",
                "Please log in through the main University System GUI before accessing Parking Management."
            )
            self.root.destroy()

    def setup_current_user(self):
        """Setup current user from existing authentication system"""
        try:
            # Check if auth system has a current authenticated user
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                auth_user = self.auth.current_user

                # auth_user is already a dictionary from UserAuth system
                if isinstance(auth_user, dict):
                    self.current_user = {
                        "username": auth_user.get('username', 'Unknown'),
                        "role": auth_user.get('role', 'user'),
                        "permissions": auth_user.get('permissions', []),
                        "first_name": auth_user.get('first_name', ''),
                        "last_name": auth_user.get('last_name', ''),
                        "id": auth_user.get('id', 0)
                    }
                else:
                    # Handle case where it might be an object
                    self.current_user = {
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', []),
                        "first_name": getattr(auth_user, 'first_name', ''),
                        "last_name": getattr(auth_user, 'last_name', ''),
                        "id": getattr(auth_user, 'id', 0)
                    }

                print(f"✓ Parking Management GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                self.current_user = None
                print("ℹ Parking Management GUI: No authenticated user - will show login screen")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            self.current_user = None

    def setup_gui(self):
        """Set up the main GUI interface"""
        # Create main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.create_status_bar()

        # Ensure a persistent top-corner main menu button is available
        self.create_main_menu_button()

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 30))
        
        # Create tabs
        self.create_tabs()
        
    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Data", command=self.show_export_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Reports", menu=reports_menu)
        reports_menu.add_command(label="Permit Report", command=self.generate_permit_report)
        reports_menu.add_command(label="Violation Report", command=self.generate_violation_report)
        reports_menu.add_command(label="Occupancy Report", command=self.generate_occupancy_report)
        reports_menu.add_command(label="Revenue Report", command=self.generate_revenue_report)
        reports_menu.add_command(label="User Activity Report", command=self.generate_user_activity_report)
        reports_menu.add_command(label="Compliance Report", command=self.generate_compliance_report)
        reports_menu.add_command(label="Analytics Dashboard", command=self.show_analytics)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Refresh All", command=self.refresh_all_data)
        tools_menu.add_command(label="Database Backup", command=self.backup_database)
        tools_menu.add_command(label="Update Available Spaces", command=self.update_available_spaces_dialog)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def create_main_menu_button(self):
        """Place a top-corner button to return to the main menu"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
        )
        # Place in the top-right corner with a slight margin
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def create_status_bar(self):
        """Create the status bar"""
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ttk.Label(self.status_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT)
        
        self.user_label = ttk.Label(self.status_frame, text="Not logged in")
        self.user_label.pack(side=tk.RIGHT)
    
    def create_tabs(self):
        """Create all the tabs"""
        # Permits tab
        self.permits_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.permits_frame, text="Permits")
        self.setup_permits_tab()
        
        # Vehicles tab
        self.vehicles_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.vehicles_frame, text="Vehicles")
        self.setup_vehicles_tab()
        
        # Violations tab
        self.violations_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.violations_frame, text="Violations")
        self.setup_violations_tab()
        
        # Parking Lots tab
        self.lots_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.lots_frame, text="Parking Lots")
        self.setup_lots_tab()
        
        # Dashboard tab
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="Dashboard")
        self.setup_dashboard_tab()
    
    def setup_permits_tab(self):
        """Setup the permits management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.permits_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Create Permit", command=self.create_permit_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self.edit_selected_permit).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_selected_permit).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_permits).pack(side=tk.LEFT, padx=2)
        
        # Search frame
        search_frame = ttk.Frame(self.permits_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.permit_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.permit_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_permits)
        
        # Create treeview for permits
        columns = ("ID", "User", "Zone", "Type", "Start Date", "End Date", "Status", "Vehicle")
        self.permits_tree = ttk.Treeview(self.permits_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            self.permits_tree.heading(col, text=col)
            self.permits_tree.column(col, width=100)
        
        # Add scrollbars
        permits_scrolly = ttk.Scrollbar(self.permits_frame, orient=tk.VERTICAL, command=self.permits_tree.yview)
        permits_scrollx = ttk.Scrollbar(self.permits_frame, orient=tk.HORIZONTAL, command=self.permits_tree.xview)
        self.permits_tree.configure(yscrollcommand=permits_scrolly.set, xscrollcommand=permits_scrollx.set)
        
        # Pack treeview and scrollbars
        self.permits_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        permits_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        permits_scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load permits data
        self.refresh_permits()
    
    def setup_vehicles_tab(self):
        """Setup the vehicles management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.vehicles_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Register Vehicle", command=self.register_vehicle_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self.edit_selected_vehicle).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_selected_vehicle).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_vehicles).pack(side=tk.LEFT, padx=2)
        
        # Search frame
        search_frame = ttk.Frame(self.vehicles_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.vehicle_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.vehicle_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_vehicles)
        
        # Create treeview for vehicles
        columns = ("ID", "License Plate", "Make", "Model", "Year", "Color", "Type", "Owner")
        self.vehicles_tree = ttk.Treeview(self.vehicles_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            self.vehicles_tree.heading(col, text=col)
            self.vehicles_tree.column(col, width=100)
        
        # Add scrollbars
        vehicles_scrolly = ttk.Scrollbar(self.vehicles_frame, orient=tk.VERTICAL, command=self.vehicles_tree.yview)
        vehicles_scrollx = ttk.Scrollbar(self.vehicles_frame, orient=tk.HORIZONTAL, command=self.vehicles_tree.xview)
        self.vehicles_tree.configure(yscrollcommand=vehicles_scrolly.set, xscrollcommand=vehicles_scrollx.set)
        
        # Pack treeview and scrollbars
        self.vehicles_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        vehicles_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        vehicles_scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load vehicles data
        self.refresh_vehicles()
    
    def setup_violations_tab(self):
        """Setup the violations management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.violations_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Record Violation", command=self.record_violation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self.edit_selected_violation).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_selected_violation).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_violations).pack(side=tk.LEFT, padx=2)
        
        # Search frame
        search_frame = ttk.Frame(self.violations_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.violation_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.violation_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_violations)
        
        # Create treeview for violations
        columns = ("ID", "License Plate", "Type", "Date", "Fine", "Status", "Location", "Officer")
        self.violations_tree = ttk.Treeview(self.violations_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            self.violations_tree.heading(col, text=col)
            self.violations_tree.column(col, width=100)
        
        # Add scrollbars
        violations_scrolly = ttk.Scrollbar(self.violations_frame, orient=tk.VERTICAL, command=self.violations_tree.yview)
        violations_scrollx = ttk.Scrollbar(self.violations_frame, orient=tk.HORIZONTAL, command=self.violations_tree.xview)
        self.violations_tree.configure(yscrollcommand=violations_scrolly.set, xscrollcommand=violations_scrollx.set)
        
        # Pack treeview and scrollbars
        self.violations_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        violations_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        violations_scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load violations data
        self.refresh_violations()
    
    def setup_lots_tab(self):
        """Setup the parking lots management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.lots_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add Lot", command=self.add_lot_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self.edit_selected_lot).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_selected_lot).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_lots).pack(side=tk.LEFT, padx=2)
        
        # Create treeview for lots
        columns = ("ID", "Name", "Location", "Total Spaces", "Available", "Zone", "Hours")
        self.lots_tree = ttk.Treeview(self.lots_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            self.lots_tree.heading(col, text=col)
            self.lots_tree.column(col, width=100)
        
        # Add scrollbars
        lots_scrolly = ttk.Scrollbar(self.lots_frame, orient=tk.VERTICAL, command=self.lots_tree.yview)
        lots_scrollx = ttk.Scrollbar(self.lots_frame, orient=tk.HORIZONTAL, command=self.lots_tree.xview)
        self.lots_tree.configure(yscrollcommand=lots_scrolly.set, xscrollcommand=lots_scrollx.set)
        
        # Pack treeview and scrollbars
        self.lots_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        lots_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        lots_scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load lots data
        self.refresh_lots()
    
    def setup_dashboard_tab(self):
        """Setup the dashboard tab"""
        # Create main dashboard frame
        dashboard_main = ttk.Frame(self.dashboard_frame)
        dashboard_main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(dashboard_main, text="Parking Management Dashboard", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Create stats frame
        stats_frame = ttk.LabelFrame(dashboard_main, text="Quick Statistics")
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Create stat labels
        self.stats_labels = {}
        stats = [
            ("Active Permits", "active_permits"),
            ("Total Vehicles", "total_vehicles"),
            ("Unpaid Violations", "unpaid_violations"),
            ("Available Spaces", "available_spaces")
        ]
        
        for i, (label, key) in enumerate(stats):
            row, col = i // 2, i % 2
            
            stat_frame = ttk.Frame(stats_grid)
            stat_frame.grid(row=row, column=col, padx=20, pady=10, sticky="w")
            
            ttk.Label(stat_frame, text=label + ":", font=("Arial", 10, "bold")).pack()
            self.stats_labels[key] = ttk.Label(stat_frame, text="Loading...", 
                                             font=("Arial", 12))
            self.stats_labels[key].pack()
        
        # Recent activity frame
        activity_frame = ttk.LabelFrame(dashboard_main, text="Recent Activity")
        activity_frame.pack(fill=tk.BOTH, expand=True)
        
        self.activity_text = ScrolledText(activity_frame, height=10, state=tk.DISABLED)
        self.activity_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Refresh dashboard
        self.refresh_dashboard()
    
    def update_user_status(self):
        """Update the user status in the status bar"""
        if self.current_user:
            self.user_label.config(text=f"User: {self.current_user['first_name']} {self.current_user['last_name']} ({self.current_user['role']})")
        else:
            self.user_label.config(text="Not logged in")
    
    def update_status(self, message):
        """Update the status bar message"""
        self.status_label.config(text=message)
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.status_label.config(text="Ready"))
    
    def update_tab_access(self):
        """Enable/disable tabs based on user permissions"""
        # This would check permissions and enable/disable tabs accordingly
        # For now, we'll enable all tabs for simplicity
        pass
    
    # Data refresh methods
    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        self.refresh_permits()
        self.refresh_vehicles()
        self.refresh_violations()
        self.refresh_lots()
        self.refresh_dashboard()
        self.update_status("All data refreshed")
    
    def refresh_permits(self):
        """Refresh permits data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT p.permit_id, p.full_name, p.zone, p.permit_type, 
                   p.start_date, p.end_date, p.active_status,
                   COALESCE(v.license_plate, 'N/A') as vehicle
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            ORDER BY p.issue_date DESC
            ''')
            
            permits = cursor.fetchall()
            
            # Clear existing data
            for item in self.permits_tree.get_children():
                self.permits_tree.delete(item)
            
            # Insert new data
            for permit in permits:
                self.permits_tree.insert("", tk.END, values=permit)
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh permits: {e}")
    
    def refresh_vehicles(self):
        """Refresh vehicles data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT v.vehicle_id, v.license_plate, v.make, v.model, v.year,
                   v.color, v.vehicle_type,
                   COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as owner
            FROM vehicles v
            LEFT JOIN users u ON v.owner_id = u.id
            ORDER BY v.vehicle_id
            ''')
            
            vehicles = cursor.fetchall()
            
            # Clear existing data
            for item in self.vehicles_tree.get_children():
                self.vehicles_tree.delete(item)
            
            # Insert new data
            for vehicle in vehicles:
                self.vehicles_tree.insert("", tk.END, values=vehicle)
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh vehicles: {e}")
    
    def refresh_violations(self):
        """Refresh violations data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT v.violation_id, v.license_plate, v.violation_type,
                   v.violation_date, v.fine_amount, v.payment_status,
                   v.location,
                   COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as officer
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            ORDER BY v.violation_date DESC
            ''')
            
            violations = cursor.fetchall()
            
            # Clear existing data
            for item in self.violations_tree.get_children():
                self.violations_tree.delete(item)
            
            # Insert new data
            for violation in violations:
                self.violations_tree.insert("", tk.END, values=violation)
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh violations: {e}")
    
    def refresh_lots(self):
        """Refresh parking lots data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM parking_lots ORDER BY lot_id')
            lots = cursor.fetchall()

            # Clear existing data
            for item in self.lots_tree.get_children():
                self.lots_tree.delete(item)

            # Insert new data - convert sqlite3.Row to tuple for display
            for lot in lots:
                # Convert sqlite3.Row object to tuple to avoid display issues
                lot_values = tuple(lot) if hasattr(lot, '__iter__') else lot
                self.lots_tree.insert("", tk.END, values=lot_values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh lots: {e}")
    
    def refresh_dashboard(self):
        """Refresh dashboard statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM vehicles")
            total_vehicles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(available_spaces) FROM parking_lots")
            available_spaces = cursor.fetchone()[0] or 0
            
            # Update stats labels
            self.stats_labels["active_permits"].config(text=str(active_permits))
            self.stats_labels["total_vehicles"].config(text=str(total_vehicles))
            self.stats_labels["unpaid_violations"].config(text=str(unpaid_violations))
            self.stats_labels["available_spaces"].config(text=str(available_spaces))
            
            # Get recent activity
            cursor.execute('''
            SELECT 'Permit' as type, permit_id as id, issue_date as date, full_name as details
            FROM parking_permits
            WHERE date(issue_date) >= date('now', '-7 days')
            UNION ALL
            SELECT 'Violation' as type, violation_id as id, violation_date as date, 
                   violation_type || ' - ' || license_plate as details
            FROM parking_violations
            WHERE date(violation_date) >= date('now', '-7 days')
            ORDER BY date DESC
            LIMIT 20
            ''')
            
            activities = cursor.fetchall()
            
            # Update activity text
            self.activity_text.config(state=tk.NORMAL)
            self.activity_text.delete(1.0, tk.END)
            
            if activities:
                for activity in activities:
                    self.activity_text.insert(tk.END, 
                        f"{activity[1]} - {activity[0]} - {activity[3]} ({activity[2]})\n")
            else:
                self.activity_text.insert(tk.END, "No recent activity")
            
            self.activity_text.config(state=tk.DISABLED)
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh dashboard: {e}")
    
    # Filter methods
    def filter_permits(self, event=None):
        """Filter permits based on search term"""
        search_term = self.permit_search_var.get().lower()
        
        # Get all items
        all_items = self.permits_tree.get_children()
        
        for item in all_items:
            values = self.permits_tree.item(item)['values']
            # Check if search term is in any of the values
            if any(search_term in str(value).lower() for value in values):
                self.permits_tree.item(item, tags=())
            else:
                self.permits_tree.item(item, tags=('hidden',))
        
        # Configure tags
        self.permits_tree.tag_configure('hidden', foreground='gray')
    
    def filter_vehicles(self, event=None):
        """Filter vehicles based on search term"""
        search_term = self.vehicle_search_var.get().lower()
        
        all_items = self.vehicles_tree.get_children()
        
        for item in all_items:
            values = self.vehicles_tree.item(item)['values']
            if any(search_term in str(value).lower() for value in values):
                self.vehicles_tree.item(item, tags=())
            else:
                self.vehicles_tree.item(item, tags=('hidden',))
        
        self.vehicles_tree.tag_configure('hidden', foreground='gray')
    
    def filter_violations(self, event=None):
        """Filter violations based on search term"""
        search_term = self.violation_search_var.get().lower()
        
        all_items = self.violations_tree.get_children()
        
        for item in all_items:
            values = self.violations_tree.item(item)['values']
            if any(search_term in str(value).lower() for value in values):
                self.violations_tree.item(item, tags=())
            else:
                self.violations_tree.item(item, tags=('hidden',))
        
        self.violations_tree.tag_configure('hidden', foreground='gray')
    
    # Dialog methods
    def create_permit_dialog(self):
        """Show create permit dialog"""
        dialog = PermitDialog(self.root, "Create New Permit")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            # Create permit with the provided data
            try:
                self.create_permit_from_data(dialog.result)
                self.refresh_permits()
                self.update_status("Permit created successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create permit: {e}")
    
    def register_vehicle_dialog(self):
        """Show register vehicle dialog"""
        dialog = VehicleDialog(self.root, "Register New Vehicle")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            try:
                self.register_vehicle_from_data(dialog.result)
                self.refresh_vehicles()
                self.update_status("Vehicle registered successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register vehicle: {e}")
    
    def record_violation_dialog(self):
        """Show record violation dialog"""
        dialog = ViolationDialog(self.root, "Record New Violation")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            try:
                self.record_violation_from_data(dialog.result)
                self.refresh_violations()
                self.update_status("Violation recorded successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to record violation: {e}")
    
    def add_lot_dialog(self):
        """Show add lot dialog"""
        dialog = LotDialog(self.root, "Add New Parking Lot")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            try:
                self.add_lot_from_data(dialog.result)
                self.refresh_lots()
                self.update_status("Parking lot added successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add parking lot: {e}")
    
    # Edit/Delete methods
    def edit_selected_permit(self):
        """Edit the selected permit"""
        selected = self.permits_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a permit to edit")
            return
        
        # Get permit data and show edit dialog
        permit_id = self.permits_tree.item(selected[0])['values'][0]
        
        try:
            # Get full permit data from database
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_permits WHERE permit_id = ?', (permit_id,))
            permit_data = cursor.fetchone()
            conn.close()
            
            if permit_data:
                dialog = PermitDialog(self.root, "Edit Permit", permit_data)
                self.root.wait_window(dialog.dialog)
                
                if dialog.result:
                    self.update_permit_from_data(permit_id, dialog.result)
                    self.refresh_permits()
                    self.update_status("Permit updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit permit: {e}")
    
    def delete_selected_permit(self):
        """Delete the selected permit"""
        selected = self.permits_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a permit to delete")
            return
        
        permit_id = self.permits_tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete permit {permit_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_permits WHERE permit_id = ?', (permit_id,))
                conn.commit()
                conn.close()
                
                self.refresh_permits()
                self.update_status("Permit deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete permit: {e}")
    
    def edit_selected_vehicle(self):
        """Edit the selected vehicle"""
        selected = self.vehicles_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a vehicle to edit")
            return
        
        vehicle_id = self.vehicles_tree.item(selected[0])['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
            vehicle_data = cursor.fetchone()
            conn.close()
            
            if vehicle_data:
                dialog = VehicleDialog(self.root, "Edit Vehicle", vehicle_data)
                self.root.wait_window(dialog.dialog)
                
                if dialog.result:
                    self.update_vehicle_from_data(vehicle_id, dialog.result)
                    self.refresh_vehicles()
                    self.update_status("Vehicle updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit vehicle: {e}")
    
    def delete_selected_vehicle(self):
        """Delete the selected vehicle"""
        selected = self.vehicles_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a vehicle to delete")
            return
        
        vehicle_id = self.vehicles_tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete vehicle {vehicle_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
                conn.commit()
                conn.close()
                
                self.refresh_vehicles()
                self.update_status("Vehicle deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete vehicle: {e}")
    
    def edit_selected_violation(self):
        """Edit the selected violation"""
        selected = self.violations_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a violation to edit")
            return
        
        violation_id = self.violations_tree.item(selected[0])['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_violations WHERE violation_id = ?', (violation_id,))
            violation_data = cursor.fetchone()
            conn.close()
            
            if violation_data:
                dialog = ViolationDialog(self.root, "Edit Violation", violation_data)
                self.root.wait_window(dialog.dialog)
                
                if dialog.result:
                    self.update_violation_from_data(violation_id, dialog.result)
                    self.refresh_violations()
                    self.update_status("Violation updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit violation: {e}")
    
    def delete_selected_violation(self):
        """Delete the selected violation"""
        selected = self.violations_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a violation to delete")
            return
        
        violation_id = self.violations_tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete violation {violation_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_violations WHERE violation_id = ?', (violation_id,))
                conn.commit()
                conn.close()
                
                self.refresh_violations()
                self.update_status("Violation deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete violation: {e}")
    
    def edit_selected_lot(self):
        """Edit the selected parking lot"""
        selected = self.lots_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a lot to edit")
            return
        
        lot_id = self.lots_tree.item(selected[0])['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_lots WHERE lot_id = ?', (lot_id,))
            lot_data = cursor.fetchone()
            conn.close()
            
            if lot_data:
                dialog = LotDialog(self.root, "Edit Parking Lot", lot_data)
                self.root.wait_window(dialog.dialog)
                
                if dialog.result:
                    self.update_lot_from_data(lot_id, dialog.result)
                    self.refresh_lots()
                    self.update_status("Parking lot updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit lot: {e}")
    
    def delete_selected_lot(self):
        """Delete the selected parking lot"""
        selected = self.lots_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a lot to delete")
            return
        
        lot_id = self.lots_tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete lot {lot_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_lots WHERE lot_id = ?', (lot_id,))
                conn.commit()
                conn.close()
                
                self.refresh_lots()
                self.update_status("Parking lot deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete lot: {e}")
    
    # Database operation methods
    def create_permit_from_data(self, data):
        """Create a permit from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generate permit ID
        cursor.execute('SELECT COUNT(*) FROM parking_permits')
        count = cursor.fetchone()[0] + 1
        permit_id = f"P{data['zone']}{datetime.now().year % 100}{str(count).zfill(4)}"
        
        # Insert permit
        cursor.execute('''
        INSERT INTO parking_permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            permit_id,
            data.get('user_id'),
            data['full_name'],
            data['email'],
            data['zone'],
            data['permit_type'],
            data['start_date'],
            data['end_date'],
            'Active',
            data.get('vehicle_id'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        conn.commit()
        conn.close()

        # Send permit confirmation email automatically
        try:
            from university_system.infrastructure.email.email_service import send_permit_confirmation
            send_permit_confirmation(
                permit_id,
                data['email'],
                data['zone'],
                data['permit_type'],
                data['start_date'],
                data['end_date']
            )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send permit confirmation email: {e}")

    def register_vehicle_from_data(self, data):
        """Register a vehicle from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generate vehicle ID
        cursor.execute('SELECT COUNT(*) FROM vehicles')
        count = cursor.fetchone()[0] + 1
        vehicle_id = f"V{str(count).zfill(6)}"
        
        # Insert vehicle
        cursor.execute('''
        INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            vehicle_id,
            data['license_plate'],
            data['make'],
            data['model'],
            data['year'],
            data['color'],
            data['vehicle_type'],
            data.get('owner_id'),
            data['registration_state']
        ))
        
        conn.commit()
        conn.close()
    
    def record_violation_from_data(self, data):
        """Record a violation from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generate violation ID
        cursor.execute('SELECT COUNT(*) FROM parking_violations')
        count = cursor.fetchone()[0] + 1
        violation_id = f"VIO{str(count).zfill(6)}"
        
        # Insert violation
        cursor.execute('''
        INSERT INTO parking_violations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            violation_id,
            data.get('vehicle_id'),
            data['license_plate'],
            data['violation_type'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            data['fine_amount'],
            'Unpaid',
            data['location'],
            self.current_user['id']
        ))
        
        conn.commit()
        conn.close()
    
    def add_lot_from_data(self, data):
        """Add a parking lot from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generate lot ID
        cursor.execute('SELECT COUNT(*) FROM parking_lots')
        count = cursor.fetchone()[0] + 1
        lot_id = f"L{str(count).zfill(3)}"
        
        # Insert lot
        cursor.execute('''
        INSERT INTO parking_lots VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            lot_id,
            data['lot_name'],
            data['location'],
            data['total_spaces'],
            data['total_spaces'],  # Initially all spaces are available
            data['zone'],
            data['hours']
        ))
        
        conn.commit()
        conn.close()
    
    def update_permit_from_data(self, permit_id, data):
        """Update a permit from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE parking_permits 
        SET full_name=?, email=?, zone=?, permit_type=?, 
            start_date=?, end_date=?, active_status=?, vehicle_id=?
        WHERE permit_id=?
        ''', (
            data['full_name'],
            data['email'],
            data['zone'],
            data['permit_type'],
            data['start_date'],
            data['end_date'],
            data.get('active_status', 'Active'),
            data.get('vehicle_id'),
            permit_id
        ))

        conn.commit()
        conn.close()

        # Send permit update confirmation email automatically
        try:
            from university_system.infrastructure.email.email_service import send_permit_update_confirmation
            # Identify which fields were updated
            updated_fields = []
            if 'full_name' in data:
                updated_fields.append(f"Full Name: {data['full_name']}")
            if 'zone' in data:
                updated_fields.append(f"Zone: {data['zone']}")
            if 'permit_type' in data:
                updated_fields.append(f"Permit Type: {data['permit_type']}")
            if 'start_date' in data:
                updated_fields.append(f"Start Date: {data['start_date']}")
            if 'end_date' in data:
                updated_fields.append(f"End Date: {data['end_date']}")
            if 'active_status' in data:
                updated_fields.append(f"Status: {data.get('active_status', 'Active')}")

            send_permit_update_confirmation(
                permit_id,
                data['email'],
                updated_fields
            )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send permit update confirmation email: {e}")

    def update_vehicle_from_data(self, vehicle_id, data):
        """Update a vehicle from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE vehicles 
        SET license_plate=?, make=?, model=?, year=?, color=?, 
            vehicle_type=?, registration_state=?
        WHERE vehicle_id=?
        ''', (
            data['license_plate'],
            data['make'],
            data['model'],
            data['year'],
            data['color'],
            data['vehicle_type'],
            data['registration_state'],
            vehicle_id
        ))
        
        conn.commit()
        conn.close()
    
    def update_violation_from_data(self, violation_id, data):
        """Update a violation from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE parking_violations 
        SET violation_type=?, fine_amount=?, payment_status=?, location=?
        WHERE violation_id=?
        ''', (
            data['violation_type'],
            data['fine_amount'],
            data['payment_status'],
            data['location'],
            violation_id
        ))
        
        conn.commit()
        conn.close()
    
    def update_lot_from_data(self, lot_id, data):
        """Update a parking lot from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE parking_lots 
        SET lot_name=?, location=?, total_spaces=?, zone=?, hours_of_operation=?
        WHERE lot_id=?
        ''', (
            data['lot_name'],
            data['location'],
            data['total_spaces'],
            data['zone'],
            data['hours'],
            lot_id
        ))
        
        conn.commit()
        conn.close()
    
    # Report methods
    def generate_permit_report(self):
        """Generate permit report"""
        try:
            # Use existing function but capture output
            import io
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            # Call existing function
            generate_permit_report()
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            
            # Show in dialog
            self.show_text_dialog("Permit Report", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def generate_violation_report(self):
        """Generate violation report"""
        try:
            import io
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            generate_violation_report()
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            
            self.show_text_dialog("Violation Report", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def show_analytics(self):
        """Show analytics dashboard"""
        try:
            import io
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            generate_analytics_dashboard()
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            
            self.show_text_dialog("Analytics Dashboard", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate analytics: {e}")
    
    def show_text_dialog(self, title, content):
        """Show a dialog with text content"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("800x600")
        
        text_widget = ScrolledText(dialog)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, content)
        text_widget.config(state=tk.DISABLED)
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=5)
    
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

    def show_export_dialog(self):
        """Show export dialog with multiple options"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Export Data")
        dialog.geometry("350x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Export Options", font=("Arial", 12, "bold")).pack(pady=(0, 20))
        
        # Quick export buttons
        ttk.Label(main_frame, text="Quick Export:").pack(anchor="w", pady=(0, 5))
        
        quick_frame = ttk.Frame(main_frame)
        quick_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Button(quick_frame, text="Export Permits (CSV)", 
                  command=lambda: export_permits('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Vehicles (CSV)", 
                  command=lambda: export_vehicles('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Violations (CSV)", 
                  command=lambda: export_violations('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Parking Lots (CSV)", 
                  command=lambda: export_parking_lots('csv')).pack(fill=tk.X, pady=2)
        
        # Advanced options
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Button(main_frame, text="Advanced Export Options", 
                  command=self.show_advanced_export_dialog).pack(fill=tk.X, pady=5)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
        
    def backup_database(self):
        """Backup the database"""
        try:
            import shutil
            
            # Get backup location
            backup_path = filedialog.asksaveasfilename(
                title="Save Database Backup",
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )
            
            if backup_path:
                # Copy current database
                current_db = str(DEFAULT_DB_PATH)  # Adjust as needed
                shutil.copy2(current_db, backup_path)
                
                self.update_status("Database backed up successfully")
                messagebox.showinfo("Success", f"Database backed up to {backup_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to backup database: {e}")

    def update_available_spaces_dialog(self):
        """Show dialog to update available spaces for parking lots"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get all lots
            cursor.execute('SELECT lot_id, lot_name, total_spaces, available_spaces FROM parking_lots ORDER BY lot_id')
            lots = cursor.fetchall()
            
            if not lots:
                messagebox.showinfo("Info", "No parking lots found.")
                conn.close()
                return
            
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Update Available Spaces")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Create frame with scrollbar
            main_frame = ttk.Frame(dialog)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Create canvas and scrollbar for lots list
            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add lot entries
            lot_vars = {}
            
            ttk.Label(scrollable_frame, text="Update Available Spaces", font=("Arial", 12, "bold")).pack(pady=(0, 10))
            
            for lot in lots:
                lot_frame = ttk.Frame(scrollable_frame)
                lot_frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(lot_frame, text=f"{lot[0]} - {lot[1]}:").pack(side=tk.LEFT)
                ttk.Label(lot_frame, text=f"(Total: {lot[2]})").pack(side=tk.LEFT, padx=(5, 10))
                
                var = tk.StringVar(value=str(lot[3]))
                lot_vars[lot[0]] = var
                
                entry = ttk.Entry(lot_frame, textvariable=var, width=10)
                entry.pack(side=tk.RIGHT)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            
            def save_changes():
                try:
                    for lot_id, var in lot_vars.items():
                        available = int(var.get())
                        if available < 0:
                            messagebox.showerror("Error", f"Available spaces for {lot_id} cannot be negative.")
                            return
                        
                        # Get total spaces for validation
                        cursor.execute('SELECT total_spaces FROM parking_lots WHERE lot_id = ?', (lot_id,))
                        total = cursor.fetchone()[0]
                        
                        if available > total:
                            messagebox.showerror("Error", f"Available spaces for {lot_id} cannot exceed total spaces ({total}).")
                            return
                        
                        # Update available spaces
                        cursor.execute('UPDATE parking_lots SET available_spaces = ? WHERE lot_id = ?', (available, lot_id))
                    
                    conn.commit()
                    self.refresh_lots()
                    self.update_status("Available spaces updated successfully")
                    dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numbers for available spaces.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update available spaces: {e}")
            
            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open update dialog: {e}")

    def show_advanced_export_dialog(self):
        """Show advanced export options dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Export Options")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Advanced Export Options", font=("Arial", 12, "bold")).pack(pady=(0, 20))
        
        # Export type
        ttk.Label(main_frame, text="Export Type:").pack(anchor="w")
        export_type_var = tk.StringVar()
        export_types = [
            ("All Data (Complete Export)", "all"),
            ("Permits Only", "permits"),
            ("Vehicles Only", "vehicles"),
            ("Violations Only", "violations"),
            ("Parking Lots Only", "lots"),
            ("Users Only", "users")
        ]
        
        for text, value in export_types:
            ttk.Radiobutton(main_frame, text=text, variable=export_type_var, value=value).pack(anchor="w")
        
        export_type_var.set("all")
        
        ttk.Label(main_frame, text="").pack()  # Spacer
        
        # Format type
        ttk.Label(main_frame, text="Format:").pack(anchor="w")
        format_var = tk.StringVar()
        formats = [("CSV", "csv"), ("Excel", "excel"), ("PDF", "pdf"), ("Text", "txt")]
        
        for text, value in formats:
            ttk.Radiobutton(main_frame, text=text, variable=format_var, value=value).pack(anchor="w")
        
        format_var.set("csv")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        def export_data():
            export_type = export_type_var.get()
            format_type = format_var.get()
            
            try:
                if export_type == "all":
                    # Export all data types
                    export_permits(format_type)
                    export_vehicles(format_type)
                    export_violations(format_type)
                    export_parking_lots(format_type)
                    messagebox.showinfo("Success", "All data exported successfully!")
                elif export_type == "permits":
                    export_permits(format_type)
                elif export_type == "vehicles":
                    export_vehicles(format_type)
                elif export_type == "violations":
                    export_violations(format_type)
                elif export_type == "lots":
                    export_parking_lots(format_type)
                elif export_type == "users":
                    export_users(format_type)
                
                dialog.destroy()
                self.update_status(f"{export_type.title()} exported successfully")
                
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")
        
        ttk.Button(button_frame, text="Export", command=export_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def generate_occupancy_report(self):
        """Generate parking lot occupancy report"""
        try:
            import io
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            # Generate occupancy report content
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT lot_id, lot_name, total_spaces, available_spaces, zone
            FROM parking_lots
            ORDER BY lot_id
            ''')
            
            lots = cursor.fetchall()
            
            print("PARKING LOT OCCUPANCY REPORT")
            print("=" * 60)
            print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            total_spaces = 0
            total_available = 0
            
            print(f"{'Lot ID':<8} {'Lot Name':<25} {'Total':<8} {'Available':<10} {'Occupied':<10} {'Rate':<8} {'Zone':<6}")
            print("-" * 75)
            
            for lot in lots:
                occupied = lot[2] - lot[3]
                rate = (occupied / lot[2] * 100) if lot[2] > 0 else 0
                
                print(f"{lot[0]:<8} {lot[1]:<25} {lot[2]:<8} {lot[3]:<10} {occupied:<10} {rate:<7.1f}% {lot[4]:<6}")
                
                total_spaces += lot[2]
                total_available += lot[3]
            
            print("-" * 75)
            total_occupied = total_spaces - total_available
            overall_rate = (total_occupied / total_spaces * 100) if total_spaces > 0 else 0
            print(f"{'TOTAL':<34} {total_spaces:<8} {total_available:<10} {total_occupied:<10} {overall_rate:<7.1f}%")
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            conn.close()
            
            self.show_text_dialog("Parking Lot Occupancy Report", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate occupancy report: {e}")

    def generate_compliance_report(self):
        """Generate compliance and audit report"""
        try:
            import io
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            generate_compliance_report()
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            
            self.show_text_dialog("Compliance & Audit Report", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate compliance report: {e}")

    def generate_revenue_report(self):
        """Generate revenue report"""
        try:
            import io
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            generate_revenue_report()
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            
            self.show_text_dialog("Revenue Report", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate revenue report: {e}")

    def generate_user_activity_report(self):
        """Generate user activity report"""
        try:
            import io
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            generate_user_activity_report()
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            
            self.show_text_dialog("User Activity Report", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate user activity report: {e}")
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
Parking Management System GUI

Version: 1.0
Author: System Administrator

This is a comprehensive parking management system
with both GUI and console interfaces.

Features:
- Permit Management
- Vehicle Registration
- Violation Tracking
- Parking Lot Management
- Reports and Analytics
- Data Export
        """
        messagebox.showinfo("About", about_text)


# Dialog classes
class PermitDialog:
    def __init__(self, parent, title, permit_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.permit_data = permit_data
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Student Lookup Section
        lookup_frame = ttk.LabelFrame(main_frame, text="Student Lookup", padding="5")
        lookup_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(lookup_frame, text="Student ID:").grid(row=0, column=0, sticky="w", padx=5)
        self.student_id_var = tk.StringVar()
        self.student_id_entry = ttk.Entry(lookup_frame, textvariable=self.student_id_var, width=20)
        self.student_id_entry.grid(row=0, column=1, padx=5)

        ttk.Button(lookup_frame, text="Lookup Student",
                  command=self.lookup_student).grid(row=0, column=2, padx=5)

        # User info
        ttk.Label(main_frame, text="Full Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Email:").grid(row=2, column=0, sticky="w", pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.email_var).grid(row=2, column=1, sticky="ew", pady=5)

        # Permit info
        ttk.Label(main_frame, text="Zone:").grid(row=3, column=0, sticky="w", pady=5)
        self.zone_var = tk.StringVar()
        zone_combo = ttk.Combobox(main_frame, textvariable=self.zone_var,
                                 values=list(PARKING_ZONES.keys()), state="readonly")
        zone_combo.grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Permit Type:").grid(row=4, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=PERMIT_TYPES, state="readonly")
        type_combo.grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Start Date:").grid(row=5, column=0, sticky="w", pady=5)
        self.start_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(main_frame, textvariable=self.start_var).grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="End Date:").grid(row=6, column=0, sticky="w", pady=5)
        self.end_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_var).grid(row=6, column=1, sticky="ew", pady=5)

        # Vehicle selection
        ttk.Label(main_frame, text="Vehicle (optional):").grid(row=7, column=0, sticky="w", pady=5)
        self.vehicle_var = tk.StringVar()
        self.vehicle_combo = ttk.Combobox(main_frame, textvariable=self.vehicle_var, state="readonly")
        self.vehicle_combo.grid(row=7, column=1, sticky="ew", pady=5)

        # Load vehicles
        self.load_vehicles()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Auto-calculate end date when type changes
        type_combo.bind('<<ComboboxSelected>>', self.calculate_end_date)
        
        # Load existing data if editing
        if self.permit_data:
            self.load_permit_data()
    
    def load_vehicles(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT vehicle_id, license_plate, make, model FROM vehicles')
            vehicles = cursor.fetchall()
            conn.close()

            vehicle_options = ["None"] + [f"{v[0]} - {v[1]} ({v[2]} {v[3]})" for v in vehicles]
            self.vehicle_combo['values'] = vehicle_options
            self.vehicle_combo.current(0)
        except Exception as e:
            print(f"Error loading vehicles: {e}")

    def lookup_student(self):
        """Lookup student in database and autofill form"""
        student_id = self.student_id_var.get().strip()

        if not student_id:
            messagebox.showwarning("Warning", "Please enter a Student ID")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Search for student by student_id
            cursor.execute('''
                SELECT student_id, first_name, last_name, email_address
                FROM students
                WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()

            if student:
                # Autofill the form with student information
                full_name = f"{student[1]} {student[2]}"  # first_name + last_name
                email = student[3] if student[3] else ""

                self.name_var.set(full_name)
                self.email_var.set(email)

                # Also load student's vehicles if any
                cursor.execute('''
                    SELECT vehicle_id, license_plate, make, model
                    FROM vehicles
                    WHERE owner_id = ?
                ''', (student_id,))

                vehicles = cursor.fetchall()

                if vehicles:
                    # Update vehicle combo with student's vehicles at the top
                    cursor.execute('SELECT vehicle_id, license_plate, make, model FROM vehicles')
                    all_vehicles = cursor.fetchall()

                    # Put student vehicles first
                    vehicle_options = ["None"]
                    for v in vehicles:
                        vehicle_options.append(f"{v[0]} - {v[1]} ({v[2]} {v[3]}) [Student's Vehicle]")

                    # Add other vehicles
                    for v in all_vehicles:
                        if v[0] not in [sv[0] for sv in vehicles]:
                            vehicle_options.append(f"{v[0]} - {v[1]} ({v[2]} {v[3]})")

                    self.vehicle_combo['values'] = vehicle_options

                    # Auto-select first student vehicle if available
                    if len(vehicles) > 0:
                        self.vehicle_combo.current(1)  # Select first student vehicle

                messagebox.showinfo("Success", f"Student found: {full_name}\nForm auto-filled with student information.")
            else:
                messagebox.showerror("Not Found", f"No student found with ID: {student_id}")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to lookup student: {e}")
            logging.error(f"Student lookup error: {e}")

    def calculate_end_date(self, event=None):
        permit_type = self.type_var.get()
        start_date = datetime.strptime(self.start_var.get(), '%Y-%m-%d')
        
        if permit_type == 'Annual':
            end_date = start_date.replace(year=start_date.year + 1)
        elif permit_type == 'Semester':
            end_date = start_date + timedelta(days=120)
        elif permit_type == 'Monthly':
            end_date = start_date + timedelta(days=30)
        elif permit_type == 'Daily':
            end_date = start_date + timedelta(days=1)
        else:  # Temporary
            end_date = start_date + timedelta(days=7)
        
        self.end_var.set(end_date.strftime('%Y-%m-%d'))
    
    def load_permit_data(self):
        # Load existing permit data for editing
        if self.permit_data:
            self.name_var.set(self.permit_data[2])  # full_name
            self.email_var.set(self.permit_data[3])  # email
            self.zone_var.set(self.permit_data[4])  # zone
            self.type_var.set(self.permit_data[5])  # permit_type
            self.start_var.set(self.permit_data[6])  # start_date
            self.end_var.set(self.permit_data[7])  # end_date
    
    def save(self):
        # Validate required fields
        if not all([self.name_var.get(), self.email_var.get(), 
                   self.zone_var.get(), self.type_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        # Get vehicle ID if selected
        vehicle_id = None
        if self.vehicle_var.get() and self.vehicle_var.get() != "None":
            vehicle_id = self.vehicle_var.get().split(" - ")[0]
        
        self.result = {
            'full_name': self.name_var.get(),
            'email': self.email_var.get(),
            'zone': self.zone_var.get(),
            'permit_type': self.type_var.get(),
            'start_date': self.start_var.get(),
            'end_date': self.end_var.get(),
            'vehicle_id': vehicle_id,
            'student_id': self.student_id_var.get().strip() if self.student_id_var.get().strip() else None
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class VehicleDialog:
    def __init__(self, parent, title, vehicle_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.vehicle_data = vehicle_data
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Student/Owner Lookup Section
        lookup_frame = ttk.LabelFrame(main_frame, text="Owner Lookup", padding="5")
        lookup_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(lookup_frame, text="Student ID:").grid(row=0, column=0, sticky="w", padx=5)
        self.owner_id_var = tk.StringVar()
        self.owner_id_entry = ttk.Entry(lookup_frame, textvariable=self.owner_id_var, width=20)
        self.owner_id_entry.grid(row=0, column=1, padx=5)

        ttk.Button(lookup_frame, text="Lookup Owner",
                  command=self.lookup_owner).grid(row=0, column=2, padx=5)

        # Owner name display (read-only)
        ttk.Label(main_frame, text="Owner Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.owner_name_var = tk.StringVar(value="Not linked")
        ttk.Entry(main_frame, textvariable=self.owner_name_var, state="readonly").grid(row=1, column=1, sticky="ew", pady=5)

        # Vehicle info
        ttk.Label(main_frame, text="License Plate:").grid(row=2, column=0, sticky="w", pady=5)
        self.plate_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.plate_var).grid(row=2, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Make:").grid(row=3, column=0, sticky="w", pady=5)
        self.make_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.make_var).grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Model:").grid(row=4, column=0, sticky="w", pady=5)
        self.model_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.model_var).grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Year:").grid(row=5, column=0, sticky="w", pady=5)
        self.year_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.year_var).grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Color:").grid(row=6, column=0, sticky="w", pady=5)
        self.color_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.color_var).grid(row=6, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Vehicle Type:").grid(row=7, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=VEHICLE_TYPES, state="readonly")
        type_combo.grid(row=7, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Registration State:").grid(row=8, column=0, sticky="w", pady=5)
        self.state_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.state_var).grid(row=8, column=1, sticky="ew", pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Load existing data if editing
        if self.vehicle_data:
            self.load_vehicle_data()
    
    def load_vehicle_data(self):
        if self.vehicle_data:
            self.plate_var.set(self.vehicle_data[1])  # license_plate
            self.make_var.set(self.vehicle_data[2])   # make
            self.model_var.set(self.vehicle_data[3])  # model
            self.year_var.set(str(self.vehicle_data[4]))  # year
            self.color_var.set(self.vehicle_data[5])  # color
            self.type_var.set(self.vehicle_data[6])   # vehicle_type
            self.state_var.set(self.vehicle_data[8])  # registration_state

            # Load owner info if available
            if self.vehicle_data[7]:  # owner_id
                self.owner_id_var.set(self.vehicle_data[7])
                self.lookup_owner()  # Auto-lookup to display owner name

    def lookup_owner(self):
        """Lookup vehicle owner (student) in database"""
        owner_id = self.owner_id_var.get().strip()

        if not owner_id:
            self.owner_name_var.set("Not linked")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Search for student
            cursor.execute('''
                SELECT first_name, last_name
                FROM students
                WHERE student_id = ?
            ''', (owner_id,))

            student = cursor.fetchone()

            if student:
                owner_name = f"{student[0]} {student[1]}"
                self.owner_name_var.set(owner_name)
                messagebox.showinfo("Success", f"Owner found: {owner_name}")
            else:
                self.owner_name_var.set("Not found")
                messagebox.showwarning("Not Found", f"No student found with ID: {owner_id}")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to lookup owner: {e}")
            logging.error(f"Owner lookup error: {e}")

    def save(self):
        # Validate required fields
        if not all([self.plate_var.get(), self.make_var.get(), 
                   self.model_var.get(), self.year_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        try:
            year = int(self.year_var.get())
            if year < 1900 or year > datetime.now().year + 1:
                raise ValueError("Invalid year")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid year")
            return
        
        self.result = {
            'license_plate': self.plate_var.get().upper(),
            'make': self.make_var.get(),
            'model': self.model_var.get(),
            'year': year,
            'color': self.color_var.get(),
            'vehicle_type': self.type_var.get() or 'Sedan',
            'registration_state': self.state_var.get().upper(),
            'owner_id': self.owner_id_var.get().strip() if self.owner_id_var.get().strip() else None
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class ViolationDialog:
    def __init__(self, parent, title, violation_data=None):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.violation_data = violation_data
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Violation info
        ttk.Label(main_frame, text="License Plate:").grid(row=0, column=0, sticky="w", pady=5)
        self.plate_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.plate_var).grid(row=0, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Violation Type:").grid(row=1, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        violation_types = ["No Permit", "Expired Permit", "Wrong Zone", "Improper Parking",
                          "Blocking Access", "Fire Lane", "Handicap Zone", "Other"]
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, 
                                 values=violation_types, state="readonly")
        type_combo.grid(row=1, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Location:").grid(row=2, column=0, sticky="w", pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var).grid(row=2, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Fine Amount:").grid(row=3, column=0, sticky="w", pady=5)
        self.fine_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.fine_var).grid(row=3, column=1, sticky="ew", pady=5)
        
        # Payment status (for editing)
        if self.violation_data:
            ttk.Label(main_frame, text="Payment Status:").grid(row=4, column=0, sticky="w", pady=5)
            self.status_var = tk.StringVar()
            status_combo = ttk.Combobox(main_frame, textvariable=self.status_var, 
                                       values=["Paid", "Unpaid", "Appealed", "Waived"], state="readonly")
            status_combo.grid(row=4, column=1, sticky="ew", pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Auto-set fine amount based on violation type
        type_combo.bind('<<ComboboxSelected>>', self.set_default_fine)
        
        # Load existing data if editing
        if self.violation_data:
            self.load_violation_data()
    
    def set_default_fine(self, event=None):
        violation_type = self.type_var.get()
        fine_amounts = {
            "No Permit": 50.00,
            "Expired Permit": 40.00,
            "Wrong Zone": 40.00,
            "Improper Parking": 30.00,
            "Blocking Access": 75.00,
            "Fire Lane": 100.00,
            "Handicap Zone": 250.00,
            "Other": 50.00
        }
        
        default_fine = fine_amounts.get(violation_type, 50.00)
        self.fine_var.set(str(default_fine))
    
    def load_violation_data(self):
        if self.violation_data:
            self.plate_var.set(self.violation_data[2])  # license_plate
            self.type_var.set(self.violation_data[3])   # violation_type
            self.location_var.set(self.violation_data[7])  # location
            self.fine_var.set(str(self.violation_data[5]))  # fine_amount
            if hasattr(self, 'status_var'):
                self.status_var.set(self.violation_data[6])  # payment_status
    
    def save(self):
        # Validate required fields
        if not all([self.plate_var.get(), self.type_var.get(), 
                   self.location_var.get(), self.fine_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        try:
            fine_amount = float(self.fine_var.get())
            if fine_amount < 0:
                raise ValueError("Fine amount cannot be negative")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid fine amount")
            return
        
        self.result = {
            'license_plate': self.plate_var.get().upper(),
            'violation_type': self.type_var.get(),
            'location': self.location_var.get(),
            'fine_amount': fine_amount,
            'payment_status': getattr(self, 'status_var', tk.StringVar(value='Unpaid')).get()
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class LotDialog:
    def __init__(self, parent, title, lot_data=None):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.lot_data = lot_data
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Lot info
        ttk.Label(main_frame, text="Lot Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Location:").grid(row=1, column=0, sticky="w", pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var).grid(row=1, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Total Spaces:").grid(row=2, column=0, sticky="w", pady=5)
        self.spaces_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.spaces_var).grid(row=2, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Zone:").grid(row=3, column=0, sticky="w", pady=5)
        self.zone_var = tk.StringVar()
        zone_combo = ttk.Combobox(main_frame, textvariable=self.zone_var, 
                                 values=list(PARKING_ZONES.keys()), state="readonly")
        zone_combo.grid(row=3, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Hours of Operation:").grid(row=4, column=0, sticky="w", pady=5)
        self.hours_var = tk.StringVar(value="24/7")
        ttk.Entry(main_frame, textvariable=self.hours_var).grid(row=4, column=1, sticky="ew", pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Load existing data if editing
        if self.lot_data:
            self.load_lot_data()
    
    def load_lot_data(self):
        if self.lot_data:
            self.name_var.set(self.lot_data[1])     # lot_name
            self.location_var.set(self.lot_data[2]) # location
            self.spaces_var.set(str(self.lot_data[3]))  # total_spaces
            self.zone_var.set(self.lot_data[5])     # zone
            self.hours_var.set(self.lot_data[6])    # hours_of_operation
    
    def save(self):
        # Validate required fields
        if not all([self.name_var.get(), self.location_var.get(), 
                   self.spaces_var.get(), self.zone_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        try:
            total_spaces = int(self.spaces_var.get())
            if total_spaces <= 0:
                raise ValueError("Total spaces must be positive")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number of spaces")
            return
        
        self.result = {
            'lot_name': self.name_var.get(),
            'location': self.location_var.get(),
            'total_spaces': total_spaces,
            'zone': self.zone_var.get(),
            'hours': self.hours_var.get() or "24/7"
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class ExportDialog:
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Data")
        self.dialog.geometry("300x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Export Type:").grid(row=0, column=0, sticky="w", pady=5)
        self.export_var = tk.StringVar()
        export_combo = ttk.Combobox(main_frame, textvariable=self.export_var, 
                                   values=["permits", "vehicles", "violations", "lots"], 
                                   state="readonly")
        export_combo.grid(row=0, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Format:").grid(row=1, column=0, sticky="w", pady=5)
        self.format_var = tk.StringVar()
        format_combo = ttk.Combobox(main_frame, textvariable=self.format_var, 
                                   values=["csv", "excel", "pdf", "txt"], 
                                   state="readonly")
        format_combo.grid(row=1, column=1, sticky="ew", pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Export", command=self.export).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def export(self):
        if not self.export_var.get() or not self.format_var.get():
            messagebox.showerror("Error", "Please select both export type and format")
            return
        
        self.result = (self.export_var.get(), self.format_var.get())
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


# Console compatibility function
def run_console_interface():
    """Run the original console interface"""
    try:
        # Import and run the original console interface
        from parking_management import display_parking_menu
        display_parking_menu()
    except ImportError:
        print("Console interface not available")


def main():
    """Main function to choose between GUI and console interface"""
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--console':
        # Run console interface
        run_console_interface()
    else:
        # Run GUI interface
        root = tk.Tk()
        app = ParkingManagementGUI(root)
        
        # Fix: Properly add console menu option
        try:
            # The menubar is already created in app.create_menu_bar()
            # We can access it through the root window
            existing_menubar = root.nametowidget(root['menu']) if root['menu'] else None
            if existing_menubar:
                console_menu = tk.Menu(existing_menubar, tearoff=0)
                console_menu.add_command(label="Switch to Console", command=run_console_interface)
                existing_menubar.add_cascade(label="Interface", menu=console_menu)
        except Exception as e:
            print(f"Warning: Could not add console menu: {e}")
        
        root.mainloop()

if __name__ == "__main__":
    main()
