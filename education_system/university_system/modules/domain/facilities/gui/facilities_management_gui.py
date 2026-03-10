"""
Facilities & Space Management GUI

Comprehensive interface for managing buildings, rooms, bookings, maintenance,
work orders, assets, and space utilization.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import traceback
from threading import Thread

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)
from education_system.university_system.modules.domain.facilities.services.facilities_management_core import (
    BuildingManager, RoomManager, RoomBookingManager,
    MaintenanceRequestManager, WorkOrderManager, AssetManager
)
from education_system.university_system.modules.shared.constants.paths import TEMP_DIR

try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except Exception:
    send_email = None
    EMAIL_SERVICE_AVAILABLE = False


class FacilitiesManagementGUI:
    """Main GUI for Facilities & Space Management"""

    def __init__(self, root, auth: Optional[UserAuth] = None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.auth = auth
        self.window = None
        self.status_bar = None  # Initialize status_bar early
        self.current_user = auth.current_user if auth and auth.current_user else None

        # Permission check
        if not self.current_user:
            messagebox.showerror(_t("common.error"), _t("facilities.error.login_required"))
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
            from education_system.university_system.infrastructure.database.schemas.facilities_housing_schemas import init_facilities_management_system_db
            init_facilities_management_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")

    def create_main_window(self):
        """Create the main facilities management window"""
        try:
            self.window = tk.Toplevel(self.root)
            self.window.title(_t("facilities.title"))
            self.window.geometry("1400x900")
            self.window.minsize(1200, 700)

            # Configure style
            style = ttk.Style()
            style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
            style.configure('Section.TLabel', font=('Arial', 12, 'bold'))

            # Header frame with return button
            header_frame = ttk.Frame(self.window)
            header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

            ttk.Label(header_frame, text=_t("facilities.header_title"),
                     style='Header.TLabel').pack(side=tk.LEFT)

            ttk.Button(header_frame, text=_t("common.return_to_main_menu"),
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
            self.status_bar = ttk.Label(self.window, text=_t("common.ready"), relief=tk.SUNKEN, anchor=tk.W)
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

            log_activity('view', 'facilities_management',
                        user=self.current_user.get('username'))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create window: {str(e)}")
            traceback.print_exc()

    def create_buildings_tab(self):
        """Create the buildings management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("facilities.tabs.buildings"))

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text=_t("facilities.building_management"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text=_t("facilities.btn.add_building"),
                  command=self.add_building).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text=_t("common.refresh"),
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
        self.notebook.add(tab, text=_t("facilities.tabs.rooms"))

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text=_t("facilities.room_management"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        # Filter by building
        ttk.Label(control_frame, text=_t("facilities.building") + ":").pack(side=tk.LEFT, padx=(20, 5))
        self.room_building_filter = ttk.Combobox(control_frame, width=20, state='readonly')
        self.room_building_filter.pack(side=tk.LEFT, padx=5)
        self.room_building_filter.bind('<<ComboboxSelected>>', lambda e: self.load_rooms())

        ttk.Button(control_frame, text=_t("facilities.btn.add_room"),
                  command=self.add_room).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text=_t("common.refresh"),
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
        self.notebook.add(tab, text=_t("facilities.tabs.bookings"))

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text=_t("facilities.room_bookings"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text=_t("facilities.btn.new_booking"),
                  command=self.create_booking).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text=_t("common.refresh"),
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
        self.notebook.add(tab, text=_t("facilities.tabs.maintenance"))

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text=_t("facilities.maintenance_requests"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(control_frame, text=_t("facilities.btn.new_request"),
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
                               0 as floor_number, r.room_type, r.capacity, 'Active' as status
                        FROM rooms r
                        WHERE r.building = ? AND r.is_active = 1
                        ORDER BY r.room_number
                    ''', (building_filter,))
                else:
                    cursor.execute('''
                        SELECT r.id as room_id, r.building as building_name, r.room_number, '' as room_name,
                               0 as floor_number, r.room_type, r.capacity, 'Active' as status
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
        dialog.wait_visibility()
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

                log_activity('create', 'building', user=self.current_user.get('username'),
                           details={'name': name, 'building_id': building_id})

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
        dialog.wait_visibility()
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

                log_activity('update', 'building', user=self.current_user.get('username'),
                           details={'name': name, 'building_id': building_id})

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
        dialog.wait_visibility()
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

                log_activity('create', 'room', user=self.current_user.get('username'),
                           details={'room_number': room_number, 'room_id': room_id})

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
        dialog.wait_visibility()
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

                log_activity('update', 'room', user=self.current_user.get('username'),
                           details={'room_number': room_number, 'room_id': room_id})

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
        try:
            rooms = RoomManager.get_available_rooms()
            if not rooms:
                messagebox.showwarning('No Rooms', 'No available rooms found.')
                return

            # Simple dialog approach
            room_list = '\n'.join([f"{r['id']}: {r['building']} Room {r['room_number']}" for r in rooms[:10]])
            room_id = simpledialog.askinteger("Room ID", f"Available Rooms:\n{room_list}\n\nEnter Room ID:")
            if not room_id:
                return

            start_time = simpledialog.askstring("Start Time", "Start (YYYY-MM-DD HH:MM):",
                                               initialvalue=datetime.now().strftime('%Y-%m-%d %H:00'))
            end_time = simpledialog.askstring("End Time", "End (YYYY-MM-DD HH:MM):",
                                             initialvalue=(datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:00'))
            purpose = simpledialog.askstring("Purpose", "Booking purpose:")

            if start_time and end_time:
                booking_id = RoomBookingManager.book_room(
                    room_id=room_id,
                    booked_by=self.current_user.get('username'),
                    booking_type='Meeting',
                    start_datetime=start_time,
                    end_datetime=end_time,
                    purpose=purpose or '',
                    expected_attendees=20
                )
                log_activity('create', 'room_booking', user=self.current_user.get('username'),
                           details={'booking_id': booking_id})
                messagebox.showinfo('Success', f'Booking created! ID: {booking_id}')
                self.load_bookings()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to create booking: {str(e)}')

    def view_booking_details(self, event=None):
        """View booking details"""
        selection = self.bookings_tree.selection()
        if not selection:
            return

        item = self.bookings_tree.item(selection[0])
        booking_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''SELECT rb.*, r.building as building, r.room_number
                                 FROM room_bookings rb
                                 JOIN rooms r ON rb.room_id = r.id
                                 WHERE rb.booking_id = ?''', (booking_id,))
                booking = cursor.fetchone()

                if booking:
                    details = f"""Booking ID: {booking_id}
Room: {booking['building']} - {booking['room_number']}
Booked By: {booking['booked_by']}
Type: {booking['booking_type']}
Start: {booking['start_datetime']}
End: {booking['end_datetime']}
Purpose: {booking['purpose'] or 'N/A'}
Status: {booking['booking_status']}"""
                    messagebox.showinfo('Booking Details', details)
                else:
                    messagebox.showerror('Error', 'Booking not found')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load booking: {str(e)}')

    def create_maintenance_request(self):
        """Create a maintenance request"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT building_id, building_name FROM buildings WHERE is_active = 1 LIMIT 10')
                buildings = cursor.fetchall()

            if not buildings:
                messagebox.showwarning('No Buildings', 'No active buildings found.')
                return

            building_list = '\n'.join([f"{b['building_id']}: {b['building_name']}" for b in buildings])
            building_id = simpledialog.askinteger("Building", f"Select Building:\n{building_list}\n\nEnter Building ID:")
            if not building_id:
                return

            req_type = simpledialog.askstring("Type", "Request Type (e.g., Plumbing, Electrical, HVAC):")
            description = simpledialog.askstring("Description", "Describe the issue:")
            priority = simpledialog.askstring("Priority", "Priority (low/medium/high):", initialvalue='medium')

            if req_type and description:
                request_id = MaintenanceRequestManager.submit_request(
                    request_type=req_type,
                    priority=priority or 'medium',
                    description=description,
                    reported_by=self.current_user.get('username'),
                    building_id=building_id
                )
                log_activity('create', 'maintenance_request', user=self.current_user.get('username'),
                           details={'request_id': request_id})
                messagebox.showinfo('Success', f'Maintenance request created! ID: {request_id}')
                self.load_maintenance_requests()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to create request: {str(e)}')

    def view_maintenance_details(self, event=None):
        """View maintenance request details"""
        selection = self.maintenance_tree.selection()
        if not selection:
            return

        item = self.maintenance_tree.item(selection[0])
        request_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM maintenance_requests WHERE request_id = ?', (request_id,))
                req = cursor.fetchone()

                if req:
                    details = f"""Request ID: {request_id}
Type: {req['request_type']}
Priority: {req['priority']}
Status: {req['status']}
Reported By: {req['reported_by']}
Date: {req['reported_date']}
Description: {req['description']}"""
                    messagebox.showinfo('Maintenance Details', details)
                else:
                    messagebox.showerror('Error', 'Request not found')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load request: {str(e)}')

    def create_work_order(self):
        """Create a work order"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT request_id, request_type FROM maintenance_requests WHERE status = 'open' LIMIT 10")
                requests = cursor.fetchall()

            if not requests:
                messagebox.showwarning('No Requests', 'No open maintenance requests found.')
                return

            req_list = '\n'.join([f"{r['request_id']}: {r['request_type']}" for r in requests])
            request_id = simpledialog.askinteger("Request", f"Open Requests:\n{req_list}\n\nEnter Request ID:")
            if not request_id:
                return

            work_type = simpledialog.askstring("Work Type", "Work Order Type:", initialvalue='Repair')
            description = simpledialog.askstring("Description", "Work description:")
            technician = simpledialog.askstring("Technician", "Assigned Technician:")

            if description:
                work_order_id = WorkOrderManager.create_work_order(
                    request_id=request_id,
                    work_order_type=work_type or 'Repair',
                    description=description,
                    assigned_technician=technician or ''
                )
                log_activity('create', 'work_order', user=self.current_user.get('username'),
                           details={'work_order_id': work_order_id})
                messagebox.showinfo('Success', f'Work order created! ID: {work_order_id}')
                self.load_work_orders()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to create work order: {str(e)}')

    def view_work_order_details(self, event=None):
        """View work order details"""
        selection = self.work_orders_tree.selection()
        if not selection:
            return

        item = self.work_orders_tree.item(selection[0])
        work_order_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM work_orders WHERE work_order_id = ?', (work_order_id,))
                wo = cursor.fetchone()

                if wo:
                    details = f"""Work Order ID: {work_order_id}
Type: {wo['work_order_type']}
Request ID: {wo['request_id']}
Technician: {wo['assigned_technician'] or 'Unassigned'}
Status: {wo['status']}
Start: {wo['start_date'] or 'Not started'}
Completion: {wo['completion_date'] or 'In progress'}
Description: {wo['description']}"""
                    messagebox.showinfo('Work Order Details', details)
                else:
                    messagebox.showerror('Error', 'Work order not found')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load work order: {str(e)}')

    def add_asset(self):
        """Add a new asset"""
        try:
            asset_name = simpledialog.askstring("Asset Name", "Enter asset name:")
            if not asset_name:
                return

            asset_type = simpledialog.askstring("Asset Type", "Enter asset type (e.g., Furniture, Equipment):")
            asset_tag = simpledialog.askstring("Asset Tag", "Enter asset tag/ID:")
            cost = simpledialog.askfloat("Cost", "Purchase cost:", initialvalue=0.0)

            if asset_name and asset_type and asset_tag:
                asset_id = AssetManager.register_asset(
                    asset_name=asset_name,
                    asset_type=asset_type,
                    asset_tag=asset_tag,
                    purchase_cost=cost or 0
                )
                log_activity('create', 'asset', user=self.current_user.get('username'),
                           details={'asset_id': asset_id})
                messagebox.showinfo('Success', f'Asset added! ID: {asset_id}')
                self.load_assets()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to add asset: {str(e)}')

    def edit_asset(self, event=None):
        """Edit selected asset"""
        selection = self.assets_tree.selection()
        if not selection:
            return

        item = self.assets_tree.item(selection[0])
        asset_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM facility_assets WHERE asset_id = ?', (asset_id,))
                asset = cursor.fetchone()

                if not asset:
                    messagebox.showerror('Error', 'Asset not found')
                    return

                new_name = simpledialog.askstring("Asset Name", "Asset name:", initialvalue=asset['asset_name'])
                new_condition = simpledialog.askstring("Condition", "Condition (new/good/fair/poor):",
                                                       initialvalue=asset['condition'] or 'good')

                if new_name and new_condition:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''UPDATE facility_assets SET asset_name = ?, condition = ?
                                         WHERE asset_id = ?''', (new_name, new_condition, asset_id))

                    log_activity('update', 'asset', user=self.current_user.get('username'),
                               details={'asset_id': asset_id})
                    messagebox.showinfo('Success', 'Asset updated!')
                    self.load_assets()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to update asset: {str(e)}')

    def show_building_context_menu(self, event):
        """Show context menu for buildings"""
        item = self.buildings_tree.identify_row(event.y)
        if not item:
            return

        self.buildings_tree.selection_set(item)

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Edit Building", command=self.edit_building)
        menu.add_command(label="View Rooms", command=lambda: (self.notebook.select(1), self.load_rooms()))
        menu.add_separator()
        menu.add_command(label="Delete Building", command=self.delete_building)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def delete_building(self):
        """Delete selected building"""
        selection = self.buildings_tree.selection()
        if not selection:
            return

        item = self.buildings_tree.item(selection[0])
        building_id = item['values'][0]
        building_name = item['values'][1]

        if messagebox.askyesno("Confirm Delete", f"Delete building '{building_name}'?\n\nThis will deactivate the building."):
            try:
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE buildings SET is_active = 0 WHERE building_id = ?', (building_id,))

                log_activity('delete', 'building', user=self.current_user.get('username'),
                           details={'building_id': building_id})
                messagebox.showinfo('Success', 'Building deactivated')
                self.load_buildings()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to delete building: {str(e)}')

    # Report generation methods
    def generate_occupancy_report(self):
        """Generate building occupancy report"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT b.building_name, COUNT(r.id) as room_count,
                           SUM(r.capacity) as total_capacity
                    FROM buildings b
                    LEFT JOIN rooms r ON b.building_id = r.building_id AND r.is_active = 1
                    WHERE b.is_active = 1
                    GROUP BY b.building_id, b.building_name
                ''')
                results = cursor.fetchall()

                report = "BUILDING OCCUPANCY REPORT\n" + "="*60 + "\n\n"
                for row in results:
                    report += f"{row['building_name']}:\n"
                    report += f"  Rooms: {row['room_count'] or 0}\n"
                    report += f"  Total Capacity: {row['total_capacity'] or 0}\n\n"

                self.show_report_window("Building Occupancy Report", report)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to generate report: {str(e)}')

    def generate_utilization_report(self):
        """Generate room utilization report"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COALESCE(b.building_name, r.building, 'Unknown') || ' - ' || r.room_number as room,
                           r.room_type, COUNT(rb.booking_id) as booking_count
                    FROM rooms r
                    LEFT JOIN buildings b ON r.building_id = b.building_id
                    LEFT JOIN room_bookings rb ON r.id = rb.room_id
                        AND rb.start_datetime >= date('now', '-30 days')
                    WHERE r.is_active = 1
                    GROUP BY r.id
                    ORDER BY booking_count DESC
                    LIMIT 20
                ''')
                results = cursor.fetchall()

                report = "ROOM UTILIZATION REPORT (Last 30 Days)\n" + "="*60 + "\n\n"
                for row in results:
                    report += f"{row['room']} ({row['room_type']}): {row['booking_count']} bookings\n"

                self.show_report_window("Room Utilization Report", report)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to generate report: {str(e)}')

    def generate_maintenance_report(self):
        """Generate maintenance summary report"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT status, COUNT(*) as count, priority
                    FROM maintenance_requests
                    GROUP BY status, priority
                    ORDER BY status, priority
                ''')
                results = cursor.fetchall()

                report = "MAINTENANCE SUMMARY REPORT\n" + "="*60 + "\n\n"
                current_status = None
                for row in results:
                    if row['status'] != current_status:
                        current_status = row['status']
                        report += f"\n{current_status.upper()}:\n"
                    report += f"  {row['priority']} priority: {row['count']} requests\n"

                self.show_report_window("Maintenance Summary", report)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to generate report: {str(e)}')

    def generate_asset_report(self):
        """Generate asset inventory report"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT asset_type, condition, COUNT(*) as count
                    FROM facility_assets
                    GROUP BY asset_type, condition
                    ORDER BY asset_type, condition
                ''')
                results = cursor.fetchall()

                report = "ASSET INVENTORY REPORT\n" + "="*60 + "\n\n"
                current_type = None
                for row in results:
                    if row['asset_type'] != current_type:
                        current_type = row['asset_type']
                        report += f"\n{current_type}:\n"
                    report += f"  {row['condition']}: {row['count']}\n"

                self.show_report_window("Asset Inventory", report)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to generate report: {str(e)}')

    def generate_energy_report(self):
        """Generate energy usage report based on building utilization"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get building utilization data as proxy for energy usage
                cursor.execute('''
                    SELECT b.building_name, b.building_type, b.total_floors,
                           COUNT(DISTINCT r.id) as room_count,
                           SUM(r.capacity) as total_capacity,
                           COUNT(rb.booking_id) as total_bookings,
                           SUM(CASE WHEN rb.booking_status = 'confirmed'
                               THEN CAST((julianday(rb.end_datetime) - julianday(rb.start_datetime)) * 24 AS REAL)
                               ELSE 0 END) as hours_utilized
                    FROM buildings b
                    LEFT JOIN rooms r ON b.building_id = r.building_id AND r.is_active = 1
                    LEFT JOIN room_bookings rb ON r.id = rb.room_id
                        AND rb.start_datetime >= date('now', '-30 days')
                    WHERE b.is_active = 1
                    GROUP BY b.building_id, b.building_name, b.building_type, b.total_floors
                    ORDER BY hours_utilized DESC
                ''')
                results = cursor.fetchall()

                report = "ENERGY USAGE & UTILIZATION REPORT (Last 30 Days)\n"
                report += "="*70 + "\n\n"
                report += "Estimated Energy Consumption Based on Building Utilization\n"
                report += "(Actual energy meters should be installed for precise tracking)\n\n"

                total_hours = 0
                for row in results:
                    hours = row['hours_utilized'] or 0
                    total_hours += hours

                    # Estimate energy based on building type and utilization
                    energy_factor = {
                        'Academic': 1.0,
                        'Research': 1.5,  # Labs use more energy
                        'Athletic': 1.3,
                        'Library': 0.8,
                        'Administrative': 0.7,
                        'Residential': 0.9,
                        'Student Center': 1.0,
                        'Mixed Use': 1.0
                    }.get(row['building_type'], 1.0)

                    estimated_kwh = hours * row['total_capacity'] * 0.05 * energy_factor if hours > 0 else 0
                    estimated_cost = estimated_kwh * 0.12  # $0.12 per kWh estimate

                    report += f"\n{row['building_name']} ({row['building_type']}):\n"
                    report += f"  Floors: {row['total_floors'] or 0}\n"
                    report += f"  Rooms: {row['room_count'] or 0}\n"
                    report += f"  Total Capacity: {row['total_capacity'] or 0}\n"
                    report += f"  Bookings (30 days): {row['total_bookings'] or 0}\n"
                    report += f"  Hours Utilized: {hours:.1f}\n"
                    report += f"  Est. Energy: {estimated_kwh:.1f} kWh\n"
                    report += f"  Est. Cost: ${estimated_cost:.2f}\n"

                total_estimated_kwh = total_hours * 10  # Simplified total estimate
                total_estimated_cost = total_estimated_kwh * 0.12

                report += "\n" + "="*70 + "\n"
                report += f"TOTAL ESTIMATED ENERGY (30 days): {total_estimated_kwh:.1f} kWh\n"
                report += f"TOTAL ESTIMATED COST: ${total_estimated_cost:.2f}\n\n"

                report += "\nRECOMMENDATIONS:\n"
                report += "• Install smart meters for accurate energy monitoring\n"
                report += "• Implement motion-sensor lighting in low-use areas\n"
                report += "• Schedule HVAC based on booking patterns\n"
                report += "• Consider solar panels for high-consumption buildings\n"
                report += "• Regular maintenance to improve HVAC efficiency\n"

                self.show_report_window("Energy Usage Report", report)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to generate report: {str(e)}')

    def generate_booking_stats(self):
        """Generate booking statistics"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT booking_type, COUNT(*) as count,
                           AVG(CAST((julianday(end_datetime) - julianday(start_datetime)) * 24 AS REAL)) as avg_hours
                    FROM room_bookings
                    WHERE start_datetime >= date('now', '-30 days')
                    GROUP BY booking_type
                    ORDER BY count DESC
                ''')
                results = cursor.fetchall()

                report = "BOOKING STATISTICS (Last 30 Days)\n" + "="*60 + "\n\n"
                total = sum(r['count'] for r in results)
                report += f"Total Bookings: {total}\n\n"

                for row in results:
                    report += f"{row['booking_type']}:\n"
                    report += f"  Count: {row['count']}\n"
                    report += f"  Avg Duration: {row['avg_hours']:.1f} hours\n\n"

                self.show_report_window("Booking Statistics", report)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to generate report: {str(e)}')

    def show_report_window(self, title, content):
        """Show report in a new window with export and email capabilities"""
        FacilitiesReportViewerDialog(self.window, self.auth, content, title)

    def update_status(self, message):
        """Update status bar message"""
        if self.status_bar:
            self.status_bar.config(text=message)

    def return_to_main_menu(self):
        """Return to main menu by closing the facilities management window"""
        if messagebox.askyesno("Confirm", "Return to main menu?"):
            if self.window:
                self.window.destroy()
            log_activity('close', 'facilities_management',
                        user=self.current_user.get('username') if self.current_user else 'Unknown')


class FacilitiesReportViewerDialog(tk.Toplevel):
    """Dialog to view and export facilities reports"""

    def __init__(self, parent, auth, report_content, report_title):
        super().__init__(parent)
        self.auth = auth
        self.report_content = report_content
        self.report_title = report_title

        self.title(f"{report_title}")
        self.geometry("900x700")

        # Make dialog modal
        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

        self.create_widgets()

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def create_widgets(self):
        """Create dialog widgets"""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame,
                 text=self.report_title,
                 font=('Arial', 14, 'bold')).pack()

        ttk.Label(header_frame,
                 text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 font=('Arial', 9)).pack()

        # Report content area
        content_frame = ttk.LabelFrame(self, text="Report Content")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Text widget with scrollbar
        text_scroll = ttk.Scrollbar(content_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.report_text = tk.Text(content_frame, wrap=tk.NONE, yscrollcommand=text_scroll.set,
                                   font=('Courier', 9))
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        text_scroll.config(command=self.report_text.yview)

        # Insert report content
        self.report_text.insert(1.0, self.report_content)
        self.report_text.config(state=tk.DISABLED)  # Make read-only

        # Horizontal scrollbar
        h_scroll = ttk.Scrollbar(content_frame, orient=tk.HORIZONTAL, command=self.report_text.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.report_text.config(xscrollcommand=h_scroll.set)

        # Buttons frame
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Export button
        ttk.Button(button_frame, text="Export as TXT", command=self.export_as_txt).pack(side=tk.LEFT, padx=5)

        # Send to admin button
        if EMAIL_SERVICE_AVAILABLE:
            ttk.Button(button_frame, text="Send to Admin", command=self.send_to_admin).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text="Close", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def export_as_txt(self):
        """Export report as TXT file"""
        try:
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"{self.report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.report_content)

                messagebox.showinfo("Success", f"Report exported successfully to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting report: {e}")

    def send_to_admin(self):
        """Send report to admin users via email"""
        if not EMAIL_SERVICE_AVAILABLE:
            messagebox.showerror("Email Not Available",
                               "Email service is not available. Please contact support.")
            return

        try:
            # Get admin emails
            admins = self.get_admin_emails()

            if not admins:
                messagebox.showerror("No Admins Found",
                                   "No admin users with email addresses found.")
                return

            # Create admin selection dialog
            admin_dialog = tk.Toplevel(self)
            admin_dialog.title("Select Admin Recipients")
            admin_dialog.geometry("400x300")
            admin_dialog.transient(self)
            admin_dialog.wait_visibility()
            admin_dialog.grab_set()

            ttk.Label(admin_dialog, text="Select admin recipients:",
                     font=('Arial', 10, 'bold')).pack(pady=10)

            # Listbox for admin selection
            list_frame = ttk.Frame(admin_dialog)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            admin_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE,
                                      yscrollcommand=scrollbar.set)
            admin_listbox.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=admin_listbox.yview)

            # Populate listbox
            for admin in admins:
                admin_listbox.insert(tk.END, f"{admin['name']} ({admin['email']})")

            # Select all by default
            admin_listbox.select_set(0, tk.END)

            # Buttons
            button_frame = ttk.Frame(admin_dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            def send_emails():
                selected_indices = admin_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("No Selection", "Please select at least one admin.")
                    return

                selected_admins = [admins[i] for i in selected_indices]

                # Close selection dialog
                admin_dialog.destroy()

                # Send emails in background thread
                def send_email_thread():
                    success_count = 0
                    for admin in selected_admins:
                        try:
                            # Use email template
                            try:
                                from education_system.university_system.infrastructure.email.template_utils import render_template
                                subject, body = render_template("facilities_management_report", {
                                    "admin_name": admin['name'],
                                    "report_title": self.report_title,
                                    "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                })
                            except Exception as template_error:
                                # Fallback to hardcoded email
                                subject = f"Facilities Management Report: {self.report_title}"
                                body = f"""Dear {admin['name']},

Please find attached the {self.report_title}.

Report Details:
- Type: {self.report_title}
- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automatically generated report from the Facilities Management System.

Best regards,
Facilities Management System
"""

                            # Create temporary file for attachment
                            temp_file = TEMP_DIR / f"facilities_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                            temp_file.parent.mkdir(parents=True, exist_ok=True)

                            with open(temp_file, 'w', encoding='utf-8') as f:
                                f.write(self.report_content)

                            # Send email
                            send_email(
                                recipient_email=admin['email'],
                                subject=subject,
                                body=body,
                                attachments=[str(temp_file)]
                            )

                            # Clean up temp file
                            try:
                                temp_file.unlink()
                            except (OSError, IOError):
                                pass

                            success_count += 1

                        except Exception as e:
                            print(f"Error sending email to {admin['email']}: {e}")

                    # Show result
                    self.after(0, lambda: messagebox.showinfo(
                        "Email Sent",
                        f"Report sent successfully to {success_count} of {len(selected_admins)} admin(s)."
                    ))

                Thread(target=send_email_thread, daemon=True).start()

            ttk.Button(button_frame, text="Send", command=send_emails).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=admin_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror("Email Error", f"Error sending report to admin: {e}")

    def get_admin_emails(self):
        """Get email addresses of all admin users"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT u.email, u.username, u.first_name, u.last_name
                    FROM users u
                    JOIN roles r ON u.role = r.role_name
                    WHERE r.role_name = 'admin' AND u.email IS NOT NULL AND u.email != ''
                    ORDER BY u.username
                ''')
                admins = cursor.fetchall()

                if not admins:
                    return []

                return [
                    {
                        'email': admin['email'],
                        'username': admin['username'],
                        'name': f"{admin['first_name']} {admin['last_name']}" if admin['first_name'] and admin['last_name'] else admin['username']
                    }
                    for admin in admins
                ]

        except Exception as e:
            print(f"Error getting admin emails: {e}")
            return []


def launch_facilities_management_gui(root, auth):
    """Launch the Facilities Management GUI"""
    try:
        gui = FacilitiesManagementGUI(root, auth)
        print("✅ Facilities & Space Management GUI opened successfully")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Facilities Management: {str(e)}")
        traceback.print_exc()


__all__ = ['FacilitiesManagementGUI', 'launch_facilities_management_gui']
