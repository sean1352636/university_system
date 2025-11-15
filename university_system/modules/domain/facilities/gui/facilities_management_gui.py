"""
Facilities & Space Management GUI

Comprehensive interface for managing buildings, rooms, bookings, maintenance,
work orders, assets, and space utilization.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import traceback

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.modules.domain.facilities.services.facilities_management_core import (
    BuildingManager, RoomManager, RoomBookingManager,
    MaintenanceRequestManager, WorkOrderManager, AssetManager
)


class FacilitiesManagementGUI:
    """Main GUI for Facilities & Space Management"""

    def __init__(self, root, auth: Optional[UserAuth] = None):
        self.root = root
        self.auth = auth
        self.window = None
        self.status_bar = None  # Initialize status_bar early
        self.current_user = auth.current_user if auth and auth.current_user else None

        # Permission check
        if not self.current_user:
            messagebox.showerror("Error", "You must be logged in to access Facilities Management.")
            return

        # Check if user has appropriate permissions
        if self.current_user.get('role') not in ['admin', 'staff', 'instructor']:
            messagebox.showwarning("Access Restricted",
                                 "Some features may be limited based on your role.")

        # Initialize database tables
        self._init_database()

        self.create_main_window()

    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            from university_system.infrastructure.database.schemas import init_facilities_management_system_db
            init_facilities_management_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")

    def create_main_window(self):
        """Create the main facilities management window"""
        try:
            self.window = tk.Toplevel(self.root)
            self.window.title("Facilities & Space Management")
            self.window.geometry("1400x900")
            self.window.minsize(1200, 700)

            # Configure style
            style = ttk.Style()
            style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
            style.configure('Section.TLabel', font=('Arial', 12, 'bold'))

            # Header frame with return button
            header_frame = ttk.Frame(self.window)
            header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

            ttk.Label(header_frame, text="Facilities & Space Management",
                     style='Header.TLabel').pack(side=tk.LEFT)

            ttk.Button(header_frame, text="← Return to Main Menu",
                      command=self.return_to_main_menu).pack(side=tk.RIGHT, padx=5)

            # Main container with tabs
            self.notebook = ttk.Notebook(self.window)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Create tabs
            self.create_buildings_tab()
            self.create_rooms_tab()
            self.create_bookings_tab()
            self.create_maintenance_tab()
            self.create_work_orders_tab()
            self.create_assets_tab()
            self.create_reports_tab()

            # Status bar
            self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

            log_activity('Accessed Facilities Management',
                        user=self.current_user.get('username'))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create window: {str(e)}")
            traceback.print_exc()

    def create_buildings_tab(self):
        """Create the buildings management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Buildings")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Building Management",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text="Add New Building",
                  command=self.add_building).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.load_buildings).pack(side=tk.RIGHT, padx=5)

        # Buildings list with treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        # Treeview
        self.buildings_tree = ttk.Treeview(tree_frame,
                                          columns=('ID', 'Name', 'Code', 'Address',
                                                  'Floors', 'Type', 'Active'),
                                          show='tree headings',
                                          yscrollcommand=v_scroll.set,
                                          xscrollcommand=h_scroll.set)

        v_scroll.config(command=self.buildings_tree.yview)
        h_scroll.config(command=self.buildings_tree.xview)

        # Configure columns
        self.buildings_tree.heading('#0', text='')
        self.buildings_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60), ('Name', 200), ('Code', 100), ('Address', 250),
            ('Floors', 80), ('Type', 150), ('Active', 80)
        ]

        for col, width in columns_config:
            self.buildings_tree.heading(col, text=col)
            self.buildings_tree.column(col, width=width)

        # Pack treeview and scrollbars
        self.buildings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Context menu
        self.buildings_tree.bind('<Button-3>', self.show_building_context_menu)
        self.buildings_tree.bind('<Double-1>', self.edit_building)

        # Load data
        self.load_buildings()

    def create_rooms_tab(self):
        """Create the rooms management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Rooms")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Room Management",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        # Filter by building
        ttk.Label(control_frame, text="Building:").pack(side=tk.LEFT, padx=(20, 5))
        self.room_building_filter = ttk.Combobox(control_frame, width=20, state='readonly')
        self.room_building_filter.pack(side=tk.LEFT, padx=5)
        self.room_building_filter.bind('<<ComboboxSelected>>', lambda e: self.load_rooms())

        ttk.Button(control_frame, text="Add New Room",
                  command=self.add_room).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.load_rooms).pack(side=tk.RIGHT, padx=5)

        # Rooms list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        self.rooms_tree = ttk.Treeview(tree_frame,
                                      columns=('ID', 'Building', 'Number', 'Name',
                                              'Floor', 'Type', 'Capacity', 'Status'),
                                      show='tree headings',
                                      yscrollcommand=v_scroll.set,
                                      xscrollcommand=h_scroll.set)

        v_scroll.config(command=self.rooms_tree.yview)
        h_scroll.config(command=self.rooms_tree.xview)

        # Configure columns
        self.rooms_tree.heading('#0', text='')
        self.rooms_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60), ('Building', 150), ('Number', 100), ('Name', 150),
            ('Floor', 80), ('Type', 120), ('Capacity', 90), ('Status', 100)
        ]

        for col, width in columns_config:
            self.rooms_tree.heading(col, text=col)
            self.rooms_tree.column(col, width=width)

        self.rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.rooms_tree.bind('<Double-1>', self.edit_room)

        # Load data
        self.load_building_filters()
        self.load_rooms()

    def create_bookings_tab(self):
        """Create the room bookings tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Room Bookings")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Room Bookings",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text="New Booking",
                  command=self.create_booking).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.load_bookings).pack(side=tk.RIGHT, padx=5)

        # Bookings list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.bookings_tree = ttk.Treeview(tree_frame,
                                         columns=('ID', 'Room', 'Booked By', 'Type',
                                                 'Start', 'End', 'Purpose', 'Status'),
                                         show='tree headings',
                                         yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.bookings_tree.yview)

        self.bookings_tree.heading('#0', text='')
        self.bookings_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60), ('Room', 150), ('Booked By', 150), ('Type', 120),
            ('Start', 150), ('End', 150), ('Purpose', 200), ('Status', 100)
        ]

        for col, width in columns_config:
            self.bookings_tree.heading(col, text=col)
            self.bookings_tree.column(col, width=width)

        self.bookings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.bookings_tree.bind('<Double-1>', self.view_booking_details)

        self.load_bookings()

    def create_maintenance_tab(self):
        """Create the maintenance requests tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Maintenance")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Maintenance Requests",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text="New Request",
                  command=self.create_maintenance_request).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.load_maintenance_requests).pack(side=tk.RIGHT, padx=5)

        # Requests list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.maintenance_tree = ttk.Treeview(tree_frame,
                                            columns=('ID', 'Type', 'Priority', 'Location',
                                                    'Reported By', 'Date', 'Status'),
                                            show='tree headings',
                                            yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.maintenance_tree.yview)

        self.maintenance_tree.heading('#0', text='')
        self.maintenance_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60), ('Type', 150), ('Priority', 100), ('Location', 200),
            ('Reported By', 150), ('Date', 150), ('Status', 100)
        ]

        for col, width in columns_config:
            self.maintenance_tree.heading(col, text=col)
            self.maintenance_tree.column(col, width=width)

        self.maintenance_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.maintenance_tree.bind('<Double-1>', self.view_maintenance_details)

        self.load_maintenance_requests()

    def create_work_orders_tab(self):
        """Create the work orders tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Work Orders")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Work Orders",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text="Create Work Order",
                  command=self.create_work_order).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.load_work_orders).pack(side=tk.RIGHT, padx=5)

        # Work orders list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.work_orders_tree = ttk.Treeview(tree_frame,
                                            columns=('ID', 'Type', 'Request', 'Technician',
                                                    'Status', 'Start', 'Completion'),
                                            show='tree headings',
                                            yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.work_orders_tree.yview)

        self.work_orders_tree.heading('#0', text='')
        self.work_orders_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60), ('Type', 150), ('Request', 100), ('Technician', 150),
            ('Status', 100), ('Start', 150), ('Completion', 150)
        ]

        for col, width in columns_config:
            self.work_orders_tree.heading(col, text=col)
            self.work_orders_tree.column(col, width=width)

        self.work_orders_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.work_orders_tree.bind('<Double-1>', self.view_work_order_details)

        self.load_work_orders()

    def create_assets_tab(self):
        """Create the asset inventory tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Asset Inventory")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Asset Inventory",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text="Add Asset",
                  command=self.add_asset).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.load_assets).pack(side=tk.RIGHT, padx=5)

        # Assets list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.assets_tree = ttk.Treeview(tree_frame,
                                       columns=('ID', 'Name', 'Type', 'Tag', 'Location',
                                               'Condition', 'Status'),
                                       show='tree headings',
                                       yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.assets_tree.yview)

        self.assets_tree.heading('#0', text='')
        self.assets_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60), ('Name', 200), ('Type', 150), ('Tag', 120),
            ('Location', 200), ('Condition', 100), ('Status', 100)
        ]

        for col, width in columns_config:
            self.assets_tree.heading(col, text=col)
            self.assets_tree.column(col, width=width)

        self.assets_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.assets_tree.bind('<Double-1>', self.edit_asset)

        self.load_assets()

    def create_reports_tab(self):
        """Create the reports and analytics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports & Analytics")

        ttk.Label(tab, text="Space Utilization & Analytics",
                 style='Header.TLabel').pack(pady=20)

        # Report options
        reports_frame = ttk.LabelFrame(tab, text="Available Reports", padding="20")
        reports_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        reports = [
            ("Building Occupancy Report", self.generate_occupancy_report),
            ("Room Utilization Report", self.generate_utilization_report),
            ("Maintenance Summary", self.generate_maintenance_report),
            ("Asset Inventory Report", self.generate_asset_report),
            ("Energy Usage Report", self.generate_energy_report),
            ("Booking Statistics", self.generate_booking_stats),
        ]

        for report_name, command in reports:
            btn_frame = ttk.Frame(reports_frame)
            btn_frame.pack(fill=tk.X, pady=5)
            ttk.Label(btn_frame, text=report_name, width=35, anchor=tk.W).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text="Generate", command=command, width=15).pack(side=tk.RIGHT, padx=10)

    # Data loading methods
    def load_buildings(self):
        """Load buildings from database"""
        try:
            self.buildings_tree.delete(*self.buildings_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT building_id, building_name, building_code, address,
                           total_floors, building_type, is_active
                    FROM buildings
                    ORDER BY building_name
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['building_id'],
                        row['building_name'],
                        row['building_code'],
                        row['address'] or 'N/A',
                        row['total_floors'] or 0,
                        row['building_type'] or 'N/A',
                        'Yes' if row['is_active'] else 'No'
                    )
                    self.buildings_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.buildings_tree.get_children())} buildings")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load buildings: {str(e)}")
            traceback.print_exc()

    def load_rooms(self):
        """Load rooms from database"""
        try:
            self.rooms_tree.delete(*self.rooms_tree.get_children())

            # Get selected building filter
            building_filter = self.room_building_filter.get()

            with get_connection() as conn:
                cursor = conn.cursor()

                if building_filter and building_filter != "All Buildings":
                    cursor.execute('''
                        SELECT r.id as room_id, r.building as building_name, r.room_number, '' as room_name,
                               0 as floor_number, r.room_type, r.capacity, 'available' as status
                        FROM rooms r
                        WHERE r.building = ? AND r.is_active = 1
                        ORDER BY r.room_number
                    ''', (building_filter,))
                else:
                    cursor.execute('''
                        SELECT r.id as room_id, r.building as building_name, r.room_number, '' as room_name,
                               0 as floor_number, r.room_type, r.capacity, 'available' as status
                        FROM rooms r
                        WHERE r.is_active = 1
                        ORDER BY r.building, r.room_number
                    ''')

                for row in cursor.fetchall():
                    values = (
                        row['room_id'],
                        row['building_name'],
                        row['room_number'],
                        row['room_name'] or 'N/A',
                        row['floor_number'] or 0,
                        row['room_type'],
                        row['capacity'] or 0,
                        row['status']
                    )
                    self.rooms_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.rooms_tree.get_children())} rooms")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load rooms: {str(e)}")
            traceback.print_exc()

    def load_bookings(self):
        """Load room bookings"""
        try:
            self.bookings_tree.delete(*self.bookings_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT rb.booking_id, r.building || ' - ' || r.room_number as room,
                           rb.booked_by, rb.booking_type, rb.start_datetime, rb.end_datetime,
                           rb.purpose, rb.booking_status
                    FROM room_bookings rb
                    JOIN rooms r ON rb.room_id = r.id
                    WHERE rb.start_datetime >= date('now', '-7 days')
                    ORDER BY rb.start_datetime DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['booking_id'],
                        row['room'],
                        row['booked_by'],
                        row['booking_type'],
                        row['start_datetime'],
                        row['end_datetime'],
                        row['purpose'] or 'N/A',
                        row['booking_status']
                    )
                    self.bookings_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.bookings_tree.get_children())} bookings")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load bookings: {str(e)}")
            traceback.print_exc()

    def load_maintenance_requests(self):
        """Load maintenance requests"""
        try:
            self.maintenance_tree.delete(*self.maintenance_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT mr.request_id, mr.request_type, mr.priority,
                           CASE
                               WHEN mr.location_type = 'room' THEN
                                   b.building_name || ' - Room ' || r.room_number
                               ELSE
                                   b.building_name
                           END as location,
                           mr.reported_by, mr.reported_date, mr.status
                    FROM maintenance_requests mr
                    LEFT JOIN buildings b ON mr.building_id = b.building_id
                    LEFT JOIN rooms r ON mr.room_id = r.id
                    ORDER BY mr.reported_date DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    # Color code by priority
                    values = (
                        row['request_id'],
                        row['request_type'],
                        row['priority'],
                        row['location'] or 'N/A',
                        row['reported_by'],
                        row['reported_date'],
                        row['status']
                    )
                    item = self.maintenance_tree.insert('', 'end', values=values)

                    # Tag by priority for coloring
                    if row['priority'] == 'high':
                        self.maintenance_tree.item(item, tags=('high_priority',))

            # Configure tag colors
            self.maintenance_tree.tag_configure('high_priority', background='#ffcccc')

            self.update_status(f"Loaded {len(self.maintenance_tree.get_children())} maintenance requests")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load maintenance requests: {str(e)}")
            traceback.print_exc()

    def load_work_orders(self):
        """Load work orders"""
        try:
            self.work_orders_tree.delete(*self.work_orders_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT work_order_id, work_order_type, request_id,
                           assigned_technician, status, start_date, completion_date
                    FROM work_orders
                    ORDER BY work_order_id DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['work_order_id'],
                        row['work_order_type'],
                        row['request_id'] or 'N/A',
                        row['assigned_technician'] or 'Unassigned',
                        row['status'],
                        row['start_date'] or 'Not started',
                        row['completion_date'] or 'In progress'
                    )
                    self.work_orders_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.work_orders_tree.get_children())} work orders")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load work orders: {str(e)}")
            traceback.print_exc()

    def load_assets(self):
        """Load facility assets"""
        try:
            self.assets_tree.delete(*self.assets_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT fa.asset_id, fa.asset_name, fa.asset_type, fa.asset_tag,
                           CASE
                               WHEN fa.room_id IS NOT NULL THEN
                                   b.building_name || ' - Room ' || r.room_number
                               WHEN fa.building_id IS NOT NULL THEN
                                   b.building_name
                               ELSE 'Unassigned'
                           END as location,
                           fa.condition, fa.status
                    FROM facility_assets fa
                    LEFT JOIN buildings b ON fa.building_id = b.building_id
                    LEFT JOIN rooms r ON fa.room_id = r.id
                    ORDER BY fa.asset_name
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['asset_id'],
                        row['asset_name'],
                        row['asset_type'],
                        row['asset_tag'] or 'N/A',
                        row['location'],
                        row['condition'],
                        row['status']
                    )
                    self.assets_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.assets_tree.get_children())} assets")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assets: {str(e)}")
            traceback.print_exc()

    def load_building_filters(self):
        """Load buildings for filter dropdown"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT building_id, building_name, building_code
                    FROM buildings
                    WHERE is_active = 1
                    ORDER BY building_name
                ''')

                buildings = ['All Buildings']
                for row in cursor.fetchall():
                    buildings.append(f"{row['building_id']} - {row['building_name']} ({row['building_code']})")

                self.room_building_filter['values'] = buildings
                self.room_building_filter.current(0)

        except Exception as e:
            print(f"Error loading building filters: {e}")

    # Action methods - Building Management
    def add_building(self):
        """Add a new building"""
        dialog = tk.Toplevel(self.window)
        dialog.title("Add New Building")
        dialog.geometry("500x450")
        dialog.transient(self.window)
        dialog.grab_set()

        # Form fields
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add New Building", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Building Name
        ttk.Label(main_frame, text="Building Name:*").pack(anchor=tk.W, pady=(5, 2))
        name_entry = ttk.Entry(main_frame, width=40)
        name_entry.pack(fill=tk.X, pady=(0, 10))

        # Building Code
        ttk.Label(main_frame, text="Building Code:*").pack(anchor=tk.W, pady=(5, 2))
        code_entry = ttk.Entry(main_frame, width=40)
        code_entry.pack(fill=tk.X, pady=(0, 10))

        # Address
        ttk.Label(main_frame, text="Address:").pack(anchor=tk.W, pady=(5, 2))
        address_entry = ttk.Entry(main_frame, width=40)
        address_entry.pack(fill=tk.X, pady=(0, 10))

        # Total Floors
        ttk.Label(main_frame, text="Total Floors:").pack(anchor=tk.W, pady=(5, 2))
        floors_entry = ttk.Spinbox(main_frame, from_=1, to=100, width=38)
        floors_entry.set(1)
        floors_entry.pack(fill=tk.X, pady=(0, 10))

        # Building Type
        ttk.Label(main_frame, text="Building Type:").pack(anchor=tk.W, pady=(5, 2))
        type_combo = ttk.Combobox(main_frame, values=[
            'Academic', 'Administrative', 'Residential', 'Athletic',
            'Research', 'Library', 'Student Center', 'Mixed Use'
        ], state='readonly', width=38)
        type_combo.current(0)
        type_combo.pack(fill=tk.X, pady=(0, 20))

        def save_building():
            name = name_entry.get().strip()
            code = code_entry.get().strip()

            if not name or not code:
                messagebox.showwarning("Missing Information", "Please enter building name and code.")
                return

            try:
                building_id = BuildingManager.register_building(
                    building_name=name,
                    building_code=code,
                    address=address_entry.get().strip(),
                    total_floors=int(floors_entry.get()),
                    building_type=type_combo.get()
                )

                log_activity('Added building', building_id=building_id,
                           details={'name': name}, user=self.current_user.get('username'))

                messagebox.showinfo("Success", f"Building '{name}' added successfully!")
                dialog.destroy()
                self.load_buildings()
                self.load_building_filters()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add building: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="Save", command=save_building).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def edit_building(self, event=None):
        """Edit selected building"""
        selection = self.buildings_tree.selection()
        if not selection:
            return

        # Get building data
        item = self.buildings_tree.item(selection[0])
        values = item['values']
        building_id = values[0]

        # Load current data from database
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM buildings WHERE building_id = ?', (building_id,))
                building = cursor.fetchone()

                if not building:
                    messagebox.showerror("Error", "Building not found")
                    return

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load building data: {str(e)}")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.window)
        dialog.title(f"Edit Building - {building['building_name']}")
        dialog.geometry("500x450")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Edit Building - {building['building_name']}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Building Name
        ttk.Label(main_frame, text="Building Name:*").pack(anchor=tk.W, pady=(5, 2))
        name_entry = ttk.Entry(main_frame, width=40)
        name_entry.insert(0, building['building_name'])
        name_entry.pack(fill=tk.X, pady=(0, 10))

        # Building Code
        ttk.Label(main_frame, text="Building Code:*").pack(anchor=tk.W, pady=(5, 2))
        code_entry = ttk.Entry(main_frame, width=40)
        code_entry.insert(0, building['building_code'])
        code_entry.pack(fill=tk.X, pady=(0, 10))

        # Address
        ttk.Label(main_frame, text="Address:").pack(anchor=tk.W, pady=(5, 2))
        address_entry = ttk.Entry(main_frame, width=40)
        address_entry.insert(0, building['address'] or '')
        address_entry.pack(fill=tk.X, pady=(0, 10))

        # Total Floors
        ttk.Label(main_frame, text="Total Floors:").pack(anchor=tk.W, pady=(5, 2))
        floors_entry = ttk.Spinbox(main_frame, from_=1, to=100, width=38)
        floors_entry.set(building['total_floors'] or 1)
        floors_entry.pack(fill=tk.X, pady=(0, 10))

        # Building Type
        ttk.Label(main_frame, text="Building Type:").pack(anchor=tk.W, pady=(5, 2))
        type_combo = ttk.Combobox(main_frame, values=[
            'Academic', 'Administrative', 'Residential', 'Athletic',
            'Research', 'Library', 'Student Center', 'Mixed Use'
        ], state='readonly', width=38)

        # Set current value
        current_type = building['building_type'] or 'Academic'
        if current_type in type_combo['values']:
            type_combo.set(current_type)
        else:
            type_combo.current(0)
        type_combo.pack(fill=tk.X, pady=(0, 10))

        # Active status
        is_active_var = tk.BooleanVar(value=bool(building['is_active']))
        ttk.Checkbutton(main_frame, text="Building is active", variable=is_active_var).pack(anchor=tk.W, pady=(10, 20))

        def update_building():
            name = name_entry.get().strip()
            code = code_entry.get().strip()

            if not name or not code:
                messagebox.showwarning("Missing Information", "Please enter building name and code.")
                return

            try:
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE buildings
                        SET building_name = ?, building_code = ?, address = ?,
                            total_floors = ?, building_type = ?, is_active = ?
                        WHERE building_id = ?
                    ''', (name, code, address_entry.get().strip(), int(floors_entry.get()),
                          type_combo.get(), 1 if is_active_var.get() else 0, building_id))

                log_activity('Updated building', building_id=building_id,
                           details={'name': name}, user=self.current_user.get('username'))

                messagebox.showinfo("Success", f"Building '{name}' updated successfully!")
                dialog.destroy()
                self.load_buildings()
                self.load_building_filters()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update building: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="Update", command=update_building).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def add_room(self):
        """Add a new room"""
        # Get list of buildings for dropdown
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT building_id, building_name, building_code FROM buildings WHERE is_active = 1 ORDER BY building_name')
                buildings = cursor.fetchall()

            if not buildings:
                messagebox.showwarning("No Buildings", "Please add a building first before adding rooms.")
                return

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load buildings: {str(e)}")
            return

        dialog = tk.Toplevel(self.window)
        dialog.title("Add New Room")
        dialog.geometry("500x550")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add New Room", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Building selection
        ttk.Label(main_frame, text="Building:*").pack(anchor=tk.W, pady=(5, 2))
        building_combo = ttk.Combobox(main_frame, values=[
            f"{b['building_id']} - {b['building_name']} ({b['building_code']})" for b in buildings
        ], state='readonly', width=38)
        building_combo.current(0)
        building_combo.pack(fill=tk.X, pady=(0, 10))

        # Room Number
        ttk.Label(main_frame, text="Room Number:*").pack(anchor=tk.W, pady=(5, 2))
        room_num_entry = ttk.Entry(main_frame, width=40)
        room_num_entry.pack(fill=tk.X, pady=(0, 10))

        # Floor Number
        ttk.Label(main_frame, text="Floor Number:*").pack(anchor=tk.W, pady=(5, 2))
        floor_entry = ttk.Spinbox(main_frame, from_=0, to=100, width=38)
        floor_entry.set(1)
        floor_entry.pack(fill=tk.X, pady=(0, 10))

        # Room Type
        ttk.Label(main_frame, text="Room Type:*").pack(anchor=tk.W, pady=(5, 2))
        room_type_combo = ttk.Combobox(main_frame, values=[
            'Classroom', 'Lecture Hall', 'Laboratory', 'Computer Lab',
            'Office', 'Conference Room', 'Study Room', 'Auditorium',
            'Library', 'Storage', 'Other'
        ], state='readonly', width=38)
        room_type_combo.current(0)
        room_type_combo.pack(fill=tk.X, pady=(0, 10))

        # Capacity
        ttk.Label(main_frame, text="Capacity:").pack(anchor=tk.W, pady=(5, 2))
        capacity_entry = ttk.Spinbox(main_frame, from_=0, to=500, width=38)
        capacity_entry.set(30)
        capacity_entry.pack(fill=tk.X, pady=(0, 20))

        def save_room():
            building_str = building_combo.get()
            room_number = room_num_entry.get().strip()
            room_type = room_type_combo.get()

            if not building_str or not room_number or not room_type:
                messagebox.showwarning("Missing Information", "Please fill in all required fields (*)")
                return

            # Extract building_id from combo selection
            building_id = int(building_str.split(' - ')[0])

            try:
                room_id = RoomManager.register_room(
                    building_id=building_id,
                    room_number=room_number,
                    room_type=room_type,
                    capacity=int(capacity_entry.get()),
                    floor_number=int(floor_entry.get())
                )

                log_activity('Added room', room_id=room_id,
                           details={'room_number': room_number}, user=self.current_user.get('username'))

                messagebox.showinfo("Success", f"Room {room_number} added successfully!")
                dialog.destroy()
                self.load_rooms()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add room: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="Save", command=save_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def edit_room(self, event=None):
        """Edit selected room"""
        selection = self.rooms_tree.selection()
        if not selection:
            return

        item = self.rooms_tree.item(selection[0])
        values = item['values']
        room_id = values[0]

        # Load current room data
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM rooms WHERE id = ?', (room_id,))
                room = cursor.fetchone()

                if not room:
                    messagebox.showerror("Error", "Room not found")
                    return

                cursor.execute('SELECT building_id, building_name, building_code FROM buildings WHERE is_active = 1 ORDER BY building_name')
                buildings = cursor.fetchall()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load room data: {str(e)}")
            return

        dialog = tk.Toplevel(self.window)
        dialog.title(f"Edit Room - {room['room_number']}")
        dialog.geometry("500x550")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Edit Room - {room['room_number']}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Building selection
        ttk.Label(main_frame, text="Building:*").pack(anchor=tk.W, pady=(5, 2))
        building_combo = ttk.Combobox(main_frame, values=[
            f"{b['building_id']} - {b['building_name']} ({b['building_code']})" for b in buildings
        ], state='readonly', width=38)

        # Set current building
        for idx, b in enumerate(buildings):
            if b['building_id'] == room['building_id']:
                building_combo.current(idx)
                break
        building_combo.pack(fill=tk.X, pady=(0, 10))

        # Room Number
        ttk.Label(main_frame, text="Room Number:*").pack(anchor=tk.W, pady=(5, 2))
        room_num_entry = ttk.Entry(main_frame, width=40)
        room_num_entry.insert(0, room['room_number'])
        room_num_entry.pack(fill=tk.X, pady=(0, 10))

        # Floor Number
        ttk.Label(main_frame, text="Floor Number:*").pack(anchor=tk.W, pady=(5, 2))
        floor_entry = ttk.Spinbox(main_frame, from_=0, to=100, width=38)
        floor_entry.set(room['floor_number'] or 1)
        floor_entry.pack(fill=tk.X, pady=(0, 10))

        # Room Type
        ttk.Label(main_frame, text="Room Type:*").pack(anchor=tk.W, pady=(5, 2))
        room_type_combo = ttk.Combobox(main_frame, values=[
            'Classroom', 'Lecture Hall', 'Laboratory', 'Computer Lab',
            'Office', 'Conference Room', 'Study Room', 'Auditorium',
            'Library', 'Storage', 'Other'
        ], state='readonly', width=38)
        room_type_combo.set(room['room_type'])
        room_type_combo.pack(fill=tk.X, pady=(0, 10))

        # Capacity
        ttk.Label(main_frame, text="Capacity:").pack(anchor=tk.W, pady=(5, 2))
        capacity_entry = ttk.Spinbox(main_frame, from_=0, to=500, width=38)
        capacity_entry.set(room['capacity'] or 30)
        capacity_entry.pack(fill=tk.X, pady=(0, 10))

        # Active status
        is_active_var = tk.BooleanVar(value=bool(room['is_active']))
        ttk.Checkbutton(main_frame, text="Room is active", variable=is_active_var).pack(anchor=tk.W, pady=(10, 20))

        def update_room():
            building_str = building_combo.get()
            room_number = room_num_entry.get().strip()
            room_type = room_type_combo.get()

            if not building_str or not room_number or not room_type:
                messagebox.showwarning("Missing Information", "Please fill in all required fields (*)")
                return

            building_id = int(building_str.split(' - ')[0])

            try:
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE rooms
                        SET building_id = ?, room_number = ?, room_type = ?,
                            capacity = ?, floor_number = ?, is_active = ?
                        WHERE id = ?
                    ''', (building_id, room_number, room_type, int(capacity_entry.get()),
                          int(floor_entry.get()), 1 if is_active_var.get() else 0, room_id))

                log_activity('Updated room', room_id=room_id,
                           details={'room_number': room_number}, user=self.current_user.get('username'))

                messagebox.showinfo("Success", f"Room {room_number} updated successfully!")
                dialog.destroy()
                self.load_rooms()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update room: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="Update", command=update_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def create_booking(self):
        """Create a new room booking"""
        messagebox.showinfo("New Booking", "Room booking dialog would open here.")

    def view_booking_details(self, event=None):
        """View booking details"""
        selection = self.bookings_tree.selection()
        if not selection:
            return
        messagebox.showinfo("Booking Details", "Booking details dialog would open here.")

    def create_maintenance_request(self):
        """Create a maintenance request"""
        messagebox.showinfo("New Request", "Maintenance request dialog would open here.")

    def view_maintenance_details(self, event=None):
        """View maintenance request details"""
        selection = self.maintenance_tree.selection()
        if not selection:
            return
        messagebox.showinfo("Maintenance Details", "Maintenance details dialog would open here.")

    def create_work_order(self):
        """Create a work order"""
        messagebox.showinfo("New Work Order", "Work order dialog would open here.")

    def view_work_order_details(self, event=None):
        """View work order details"""
        selection = self.work_orders_tree.selection()
        if not selection:
            return
        messagebox.showinfo("Work Order Details", "Work order details dialog would open here.")

    def add_asset(self):
        """Add a new asset"""
        messagebox.showinfo("Add Asset", "Asset add dialog would open here.")

    def edit_asset(self, event=None):
        """Edit selected asset"""
        selection = self.assets_tree.selection()
        if not selection:
            return
        messagebox.showinfo("Edit Asset", "Asset edit dialog would open here.")

    def show_building_context_menu(self, event):
        """Show context menu for buildings"""
        # Would implement context menu here
        pass

    # Report generation methods
    def generate_occupancy_report(self):
        """Generate building occupancy report"""
        messagebox.showinfo("Report", "Building occupancy report would be generated here.")

    def generate_utilization_report(self):
        """Generate room utilization report"""
        messagebox.showinfo("Report", "Room utilization report would be generated here.")

    def generate_maintenance_report(self):
        """Generate maintenance summary report"""
        messagebox.showinfo("Report", "Maintenance summary report would be generated here.")

    def generate_asset_report(self):
        """Generate asset inventory report"""
        messagebox.showinfo("Report", "Asset inventory report would be generated here.")

    def generate_energy_report(self):
        """Generate energy usage report"""
        messagebox.showinfo("Report", "Energy usage report would be generated here.")

    def generate_booking_stats(self):
        """Generate booking statistics"""
        messagebox.showinfo("Report", "Booking statistics would be generated here.")

    def update_status(self, message):
        """Update status bar message"""
        if self.status_bar:
            self.status_bar.config(text=message)

    def return_to_main_menu(self):
        """Return to main menu by closing the facilities management window"""
        if messagebox.askyesno("Confirm", "Return to main menu?"):
            if self.window:
                self.window.destroy()
            log_activity('Closed Facilities Management',
                        user=self.current_user.get('username') if self.current_user else 'Unknown')


def launch_facilities_management_gui(root, auth):
    """Launch the Facilities Management GUI"""
    try:
        gui = FacilitiesManagementGUI(root, auth)
        print("✅ Facilities & Space Management GUI opened successfully")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Facilities Management: {str(e)}")
        traceback.print_exc()


__all__ = ['FacilitiesManagementGUI', 'launch_facilities_management_gui']
