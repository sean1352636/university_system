from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.simpledialog import Dialog
from university_system.infrastructure.database.db import sqlite3
import logging
import time
import os
from datetime import datetime, timedelta
import re
import traceback
from threading import Thread
import queue
from typing import Optional

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import all original functions and classes
try:
    from university_system.infrastructure.database.db import sqlite3, DatabaseManager
    from university_system.modules.shared.utils.simple_activity_logger import (
        log_create, log_read, log_update, log_delete, log_menu_navigation,
    )
    from university_system.infrastructure.auth import UserAuth
except ImportError as e:
    logging.error(f"Required module import failed: {e}")
    raise

# Academic calendar is optional - may not be available if dependencies missing
try:
    from university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
    from university_system.modules.domain.academics.services.academic_calendar.config import CalendarConfig
    CALENDAR_AVAILABLE = True
except ImportError as e:
    CALENDAR_AVAILABLE = False
    # Use debug level since this is expected when optional dependencies are missing
    logging.debug(f"Academic calendar module not available (optional): {e}")

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("ReportLab not available. PDF generation will be disabled.")

try:
    from university_system.modules.domain.mobility.services.trip_management import (
        TripReportGenerator,
        safe_db_operation as domain_safe_db_operation,
    )
    TRIP_REPORTS_AVAILABLE = True
except Exception as exc:  # pragma: no cover - optional dependency
    TripReportGenerator = None  # type: ignore
    domain_safe_db_operation = None  # type: ignore
    TRIP_REPORTS_AVAILABLE = False
    logging.warning("Trip report generator module not available: %s", exc)

try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except Exception as exc:
    send_email = None  # type: ignore
    EMAIL_SERVICE_AVAILABLE = False
    logging.warning("Email service not available: %s", exc)

# Import email template utilities
try:
    from university_system.infrastructure.email.template_utils import render_template
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False

# Configure logger for this module
logger = logging.getLogger(__name__)

# Provide a module-level safe_db_operation helper so dialogs can reuse CLI logic.
def safe_db_operation(operation_func, *args, **kwargs):
    """
    Execute a database operation safely.

    Prefer the domain implementation when available; otherwise fall back to a
    lightweight local implementation.
    """
    if domain_safe_db_operation:
        return domain_safe_db_operation(operation_func, *args, **kwargs)

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        result = operation_func(conn, *args, **kwargs)
        conn.commit()
        return result
    except Exception as exc:  # pragma: no cover - best effort fallback
        logging.error("Database operation failed: %s", exc)
        if conn:
            try:
                conn.rollback()
            except Exception as e:
                logger.debug(f"Failed to rollback transaction: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Failed to close database connection: {e}")

# Import all original helper functions from trip_management.py
# Note: In a real implementation, you would import these from the original file
# For this example, I'll include the essential ones

class TripManagementGUI:
    def __init__(self, auth_instance=None, root=None):
        # Initialize i18n for language support
        init_i18n()

        self.auth = auth_instance
        self.root = root          # may be provided by caller
        self._owns_root = self.root is None  # track if we created the root
        self.main_frame = None
        self.notebook = None
        self.status_bar = None
        self.calendar_manager = None
        self.setup_gui()

        # Calendar integration
        if CALENDAR_AVAILABLE and self.auth:
            try:
                config = CalendarConfig()
                self.calendar_manager = AcademicCalendarManager(config=config, auth_manager=self.auth)
            except Exception as e:
                logging.warning(f"Could not initialize calendar system: {e}")
    
    def setup_gui(self):
        """Initialize the main GUI window"""
        if self.root is None:
            self.root = tk.Tk()
        # It's fine to set title/geometry on a Toplevel as well
        self.root.title(_t("trip.title"))
        self.root.geometry("1200x800")

        # Configure styles
        style = ttk.Style()
        style.theme_use('clam')

        # Create main menu
        self.create_menu()

        # Create main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Provide a top-corner button for returning to the main menu
        self.create_main_menu_button()

        # Create status bar
        self.status_bar = ttk.Label(self.root, text=_t("common.ready"), relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Check authentication - user must log in through main GUI
        if self.auth and self.auth.current_user:
            self.show_main_interface()
        else:
            messagebox.showerror(
                "Authentication Required",
                "Please log in through the main University System GUI before accessing Trip Management."
            )
            self.root.destroy()
    
    def create_menu(self):
        """Create the application menu bar with role-based filtering"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Get user role for filtering
        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file"), menu=file_menu)

        # Admin/Staff can export data
        if is_admin or is_staff:
            file_menu.add_command(label=_t("trip.menu.export_data"), command=self.export_data)
            file_menu.add_separator()

        file_menu.add_command(label=_t("common.exit"), command=self.root.quit)

        # Trip menu
        trip_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("trip.menu.trips"), menu=trip_menu)
        trip_menu.add_command(label=_t("trip.menu.view_all_trips"), command=self.show_trips_view)

        # Admin/Staff can create trips
        if is_admin or is_staff:
            trip_menu.add_command(label=_t("trip.menu.create_new_trip"), command=self.show_create_trip)

        trip_menu.add_separator()
        trip_menu.add_command(label=_t("trip.menu.my_registrations"), command=self.show_my_registrations)

        if self.auth.check_permission('cancel_trip_registration'):
            trip_menu.add_command(label=_t("trip.menu.cancel_registration"), command=self.cancel_selected_registration)

        # Itinerary submenu
        if self.auth.check_permission('view_trips'):
            itinerary_menu = tk.Menu(trip_menu, tearoff=0)
            trip_menu.add_cascade(label=_t("trip.menu.itinerary"), menu=itinerary_menu)
            itinerary_menu.add_command(label=_t("trip.menu.view_trip_itinerary"), command=self.view_trip_itinerary)

            # Admin/Staff can manage itinerary
            if (is_admin or is_staff) and (self.auth.check_permission('manage_trips') or self.auth.check_permission('create_trips')):
                itinerary_menu.add_command(label=_t("trip.menu.manage_itinerary"), command=self.add_trip_itinerary)

        # Reports menu (Admin/Staff only)
        if is_admin or is_staff:
            reports_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t("trip.menu.reports"), menu=reports_menu)
            reports_menu.add_command(label=_t("trip.menu.trip_summary"), command=self.generate_trip_summary_report)
            reports_menu.add_command(label=_t("trip.menu.participant_list"), command=self.generate_participant_report)
            reports_menu.add_command(label=_t("trip.menu.financial_report"), command=self.generate_financial_report)

        # Admin menu (Admin only)
        if is_admin and self.auth and self.auth.current_user and self.auth.check_permission('manage_trips'):
            admin_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t("trip.menu.admin"), menu=admin_menu)
            admin_menu.add_command(label=_t("trip.menu.manage_participants"), command=self.show_manage_participants)
            admin_menu.add_command(label=_t("trip.menu.assign_staff"), command=self.show_assign_staff)
            admin_menu.add_command(label=_t("trip.menu.manage_expenses"), command=self.show_manage_expenses)
            admin_menu.add_separator()
            admin_menu.add_command(label=_t("trip.menu.assign_trip_staff"), command=self.assign_trip_staff)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("trip.menu.about"), command=self.show_about)

    def create_main_menu_button(self):
        """Place a persistent main-menu button in the top-right corner"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception as e:
            logger.debug(f"Error checking main_menu_button existence: {e}")

        self.main_menu_button = ttk.Button(
            self.root,
            text=_t("common.return_to_main_menu"),
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def show_main_interface(self):
        """Show the main trip management interface"""
        self.clear_main_frame()

        # Header
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text=_t("trip.header_title"),
                 font=('Arial', 18, 'bold')).pack(side=tk.LEFT)
        
        if self.auth and self.auth.current_user:
            user_info = f"Logged in as: {self.auth.current_user['username']} ({self.auth.current_user['role']})"
            ttk.Label(header_frame, text=user_info).pack(side=tk.RIGHT)
        
        # Main content notebook
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Add tabs based on permissions
        self.add_trips_tab()
        
        if self.auth.check_permission('register_for_trips'):
            self.add_registration_tab()
        
        if self.auth.check_permission('view_own_trip_registrations'):
            self.add_my_trips_tab()
        
        if self.auth.check_permission('manage_trips'):
            self.add_admin_tab()
        
        if self.auth.check_permission('view_trip_reports'):
            self.add_reports_tab()
        
        # Calendar integration tab
        if CALENDAR_AVAILABLE and self.calendar_manager:
            self.add_calendar_tab()
    
    def add_trips_tab(self):
        """Add the trips overview tab"""
        trips_frame = ttk.Frame(self.notebook)
        self.notebook.add(trips_frame, text=_t("trip.tabs.all_trips"))

        # Toolbar
        toolbar = ttk.Frame(trips_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_trips).pack(side=tk.LEFT, padx=(0, 5))

        if self.auth.check_permission('create_trips'):
            ttk.Button(toolbar, text=_t("trip.btn.create_trip"), command=self.show_create_trip).pack(side=tk.LEFT, padx=5)
        
        # Search frame
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_trips)
        ttk.Entry(search_frame, textvariable=self.search_var, width=20).pack(side=tk.LEFT)
        
        # Trips treeview
        self.trips_tree = ttk.Treeview(trips_frame, columns=('name', 'destination', 'start_date', 'participants', 'cost', 'status'), show='tree headings')
        
        # Configure columns
        self.trips_tree.heading('#0', text='ID')
        self.trips_tree.heading('name', text='Trip Name')
        self.trips_tree.heading('destination', text='Destination')
        self.trips_tree.heading('start_date', text='Start Date')
        self.trips_tree.heading('participants', text='Participants')
        self.trips_tree.heading('cost', text='Cost')
        self.trips_tree.heading('status', text='Status')
        
        self.trips_tree.column('#0', width=50)
        self.trips_tree.column('name', width=200)
        self.trips_tree.column('destination', width=150)
        self.trips_tree.column('start_date', width=100)
        self.trips_tree.column('participants', width=100)
        self.trips_tree.column('cost', width=80)
        self.trips_tree.column('status', width=100)
        
        # Scrollbars
        trips_scrollbar_v = ttk.Scrollbar(trips_frame, orient=tk.VERTICAL, command=self.trips_tree.yview)
        trips_scrollbar_h = ttk.Scrollbar(trips_frame, orient=tk.HORIZONTAL, command=self.trips_tree.xview)
        self.trips_tree.configure(yscrollcommand=trips_scrollbar_v.set, xscrollcommand=trips_scrollbar_h.set)
        
        # Pack treeview and scrollbars
        self.trips_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        trips_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        trips_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind double-click to view details
        self.trips_tree.bind('<Double-1>', self.on_trip_double_click)
        
        # Context menu
        self.create_trips_context_menu()
        
        # Load trips data
        self.refresh_trips()
    
    def add_registration_tab(self):
        """Add the trip registration tab"""
        reg_frame = ttk.Frame(self.notebook)
        self.notebook.add(reg_frame, text="Register for Trip")
        
        # Available trips for registration
        ttk.Label(reg_frame, text="Available Trips for Registration", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        
        # Registration treeview
        self.reg_tree = ttk.Treeview(reg_frame, columns=('name', 'destination', 'start_date', 'cost', 'spaces'), show='tree headings')
        
        self.reg_tree.heading('#0', text='ID')
        self.reg_tree.heading('name', text='Trip Name')
        self.reg_tree.heading('destination', text='Destination')
        self.reg_tree.heading('start_date', text='Start Date')
        self.reg_tree.heading('cost', text='Cost')
        self.reg_tree.heading('spaces', text='Spaces Left')
        
        self.reg_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Registration button
        ttk.Button(reg_frame, text="Register for Selected Trip", 
                  command=self.register_for_trip).pack(pady=10)
        
        self.load_available_trips()
    
    def add_my_trips_tab(self):
        """Add the my trips tab"""
        my_trips_frame = ttk.Frame(self.notebook)
        self.notebook.add(my_trips_frame, text="My Trips")
        
        ttk.Label(my_trips_frame, text="My Trip Registrations", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        
        # My trips treeview
        self.my_trips_tree = ttk.Treeview(my_trips_frame, columns=('name', 'destination', 'start_date', 'cost', 'payment', 'status'), show='tree headings')
        
        self.my_trips_tree.heading('#0', text='ID')
        self.my_trips_tree.heading('name', text='Trip Name')
        self.my_trips_tree.heading('destination', text='Destination')
        self.my_trips_tree.heading('start_date', text='Start Date')
        self.my_trips_tree.heading('cost', text='Cost')
        self.my_trips_tree.heading('payment', text='Payment')
        self.my_trips_tree.heading('status', text='Status')
        
        self.my_trips_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Cancel registration button
        ttk.Button(my_trips_frame, text="Cancel Selected Registration", 
                  command=self.cancel_registration).pack(pady=10)
        
        self.load_my_trips()
    
    def add_admin_tab(self):
        admin_frame = ttk.Frame(self.notebook)
        self.notebook.add(admin_frame, text="Administration")

        # store notebook so menu actions can select subtabs later
        self.admin_notebook = ttk.Notebook(admin_frame)
        self.admin_notebook.pack(fill=tk.BOTH, expand=True)

        participants_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(participants_frame, text="Manage Participants")
        self.setup_participants_management(participants_frame)

        staff_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(staff_frame, text="Assign Staff")
        self.setup_staff_assignment(staff_frame)

        expenses_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(expenses_frame, text="Manage Expenses")
        self.setup_expenses_management(expenses_frame)

        trip_mgmt_frame = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(trip_mgmt_frame, text="Trip Management")
        self.setup_trip_management(trip_mgmt_frame)
        
    def add_reports_tab(self):
        """Add the reports tab"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="Reports")
        
        ttk.Label(reports_frame, text="Trip Reports", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Report buttons
        reports_buttons_frame = ttk.Frame(reports_frame)
        reports_buttons_frame.pack(pady=20)
        
        ttk.Button(reports_buttons_frame, text="Trip Summary Report", 
                  command=self.generate_trip_summary_report).pack(pady=5, fill=tk.X)
        
        ttk.Button(reports_buttons_frame, text="Participant List Report", 
                  command=self.generate_participant_report).pack(pady=5, fill=tk.X)
        
        if self.auth.check_permission('view_financial_reports'):
            ttk.Button(reports_buttons_frame, text="Financial Report", 
                      command=self.generate_financial_report).pack(pady=5, fill=tk.X)
        
        # Report output area
        ttk.Label(reports_frame, text="Report Generation Log").pack(anchor=tk.W, pady=(20, 5))
        self.report_log = scrolledtext.ScrolledText(reports_frame, height=15, width=80)
        self.report_log.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    def add_calendar_tab(self):
        """Add the calendar integration tab"""
        calendar_frame = ttk.Frame(self.notebook)
        self.notebook.add(calendar_frame, text="Calendar")
        
        ttk.Label(calendar_frame, text="Calendar Integration", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Calendar buttons
        cal_buttons_frame = ttk.Frame(calendar_frame)
        cal_buttons_frame.pack(pady=20)
        
        ttk.Button(cal_buttons_frame, text="View Trips with Calendar Events",
                  command=self.show_trips_with_calendar).pack(pady=5, fill=tk.X)

        ttk.Button(cal_buttons_frame, text="View Trip Events in Calendar",
                  command=self.view_trip_events_in_calendar).pack(pady=5, fill=tk.X)

        if self.auth.check_permission('manage_schedules'):
            ttk.Button(cal_buttons_frame, text="Create Calendar Event for Trip", 
                      command=self.create_trip_calendar_event).pack(pady=5, fill=tk.X)
        
        # Calendar view area
        self.calendar_tree = ttk.Treeview(calendar_frame, columns=('trip', 'event', 'start_date', 'status'), show='tree headings')
        
        self.calendar_tree.heading('#0', text='ID')
        self.calendar_tree.heading('trip', text='Trip Name')
        self.calendar_tree.heading('event', text='Calendar Event')
        self.calendar_tree.heading('start_date', text='Start Date')
        self.calendar_tree.heading('status', text='Status')
        
        self.calendar_tree.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
    
    def clear_main_frame(self):
        """Clear the main frame"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
    
    def update_status(self, message):
        """Update the status bar"""
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                role = self.auth.current_user.get('role', '').lower()
                return role
            return None
        except Exception as e:
            logging.error(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff"""
        role = self.get_user_role()
        return role in ['staff', 'trip_coordinator', 'instructor']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def _show_admin_subtab(self, subtab_label):
        self._ensure_main_ui()
        # ensure Admin tab exists / allowed
        if not any(self.notebook.tab(i, 'text') == 'Administration'
                   for i in range(self.notebook.index('end'))):
            if self.auth and self.auth.check_permission('manage_trips'):
                self.add_admin_tab()
            else:
                messagebox.showerror("Permission Denied", "You don't have access to Administration.")
                return
        # select Admin
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Administration':
                self.notebook.select(i)
                break
        # select inner subtab
        if hasattr(self, 'admin_notebook'):
            for j in range(self.admin_notebook.index('end')):
                if self.admin_notebook.tab(j, 'text') == subtab_label:
                    self.admin_notebook.select(j)
                    break

    def cancel_trip_registration(self):
        """Cancel selected registration - enhanced version"""
        selection = self.my_trips_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a registration to cancel.")
            return
        
        trip_id = self.my_trips_tree.item(selection[0])['text']
        trip_name = self.my_trips_tree.item(selection[0])['values'][0]
        payment_status = self.my_trips_tree.item(selection[0])['values'][4]
        
        # Enhanced cancellation dialog
        CancelRegistrationDialog(self.root, self.auth, trip_id, trip_name, payment_status, self.load_my_trips)

    def view_trip_itinerary(self):
        """View itinerary for selected trip"""
        selection = self.trips_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip to view itinerary.")
            return
        
        trip_id = self.trips_tree.item(selection[0])['text']
        ViewItineraryDialog(self.root, trip_id)

    def add_trip_itinerary(self):
        """Add itinerary to selected trip"""
        selection = self.trips_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip to add itinerary.")
            return
        
        trip_id = self.trips_tree.item(selection[0])['text']
        ItineraryDialog(self.root, self.auth, trip_id)

    def assign_trip_staff(self):
        """Assign staff to trip - calls existing dialog"""
        self._show_admin_subtab('Assign Staff')

    def show_manage_participants(self):
        self._show_admin_subtab('Manage Participants')

    def show_assign_staff(self):
        self._show_admin_subtab('Assign Staff')

    def show_manage_expenses(self):
        self._show_admin_subtab('Manage Expenses')

    def cancel_selected_registration(self):
        """Menu action to cancel registration from My Trips"""
        if self._select_tab('My Trips'):
            # Wait a moment for tab to load, then check selection
            self.root.after(100, self._check_and_cancel_registration)

    def _check_and_cancel_registration(self):
        """Helper to cancel registration after tab loads"""
        if hasattr(self, 'my_trips_tree'):
            selection = self.my_trips_tree.selection()
            if selection:
                self.cancel_trip_registration()
            else:
                messagebox.showinfo("No Selection", "Please select a registration from the My Trips tab first.")
        else:
            messagebox.showinfo("Tab Not Available", "Please go to the My Trips tab and select a registration to cancel.")
    
    def refresh_trips(self):
        """Refresh the trips display"""
        self.update_status("Loading trips...")
        
        # Clear existing items
        for item in self.trips_tree.get_children():
            self.trips_tree.delete(item)
        
        # Load trips from database
        def load_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(tp.id) as current_participants,
                   u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            LEFT JOIN users u ON t.created_by = u.id
            GROUP BY t.id
            ORDER BY t.start_date ASC
            ''')
            
            trips = cursor.fetchall()
            return trips
        
        trips = self.safe_db_operation(load_trips_operation)
        
        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, created_by = trip
                participants_info = f"{current_parts}/{max_parts}"
                
                cost_str = f"£{cost:.2f}" if cost is not None else "£0.00"
                status_str = status.title() if status else "Unknown"
                self.trips_tree.insert('', 'end', text=str(trip_id), values=(
                    name, destination, start_date, participants_info, cost_str, status_str
                ))
        
        self.update_status(f"Loaded {len(trips) if trips else 0} trips")
    
    def filter_trips(self, *args):
        """Filter trips based on search criteria"""
        search_raw = (self.search_var.get() or "").strip()
        if not search_raw:
            self.refresh_trips()
            return

        search_term = search_raw.lower()
        like_term = f"%{search_term}%"

        def filter_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                       t.max_participants, t.cost, t.status,
                       COUNT(tp.id) as current_participants,
                       u.first_name || ' ' || u.last_name as created_by_name
                FROM trips t
                LEFT JOIN trip_participants tp
                       ON t.id = tp.trip_id AND tp.status = 'registered'
                LEFT JOIN users u ON t.created_by = u.id
                WHERE (
                    LOWER(t.trip_name) LIKE ?
                    OR LOWER(t.destination) LIKE ?
                    OR LOWER(COALESCE(t.status, '')) LIKE ?
                    OR LOWER(COALESCE(u.first_name || ' ' || u.last_name, '')) LIKE ?
                    OR t.start_date LIKE ?
                    OR t.end_date LIKE ?
                    OR CAST(t.cost AS TEXT) LIKE ?
                )
                GROUP BY t.id
                ORDER BY t.start_date ASC
                ''',
                (
                    like_term,
                    like_term,
                    like_term,
                    like_term,
                    f"%{search_raw}%",
                    f"%{search_raw}%",
                    f"%{search_raw}%",
                ),
            )
            return cursor.fetchall()

        trips = self.safe_db_operation(filter_trips_operation) or []

        for item in self.trips_tree.get_children():
            self.trips_tree.delete(item)

        for trip in trips:
            (trip_id, name, destination, start_date, end_date, max_parts,
             cost, status, current_parts, created_by) = trip
            participants_info = f"{current_parts}/{max_parts}"
            cost_str = f"£{cost:.2f}" if cost is not None else "£0.00"
            status_str = status.title() if status else "Unknown"
            self.trips_tree.insert(
                '',
                'end',
                text=str(trip_id),
                values=(name, destination, start_date, participants_info, cost_str, status_str)
            )

        match_count = len(trips)
        self.update_status(f"Found {match_count} trip(s) matching '{search_raw}'")
    
    def on_trip_double_click(self, event):
        """Handle double-click on trip item"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            self.show_trip_details(trip_id)
    
    def show_trip_details(self, trip_id):
        """Show detailed trip information"""
        def get_trip_details_operation(conn):
            cursor = conn.cursor()
            
            # Get trip details
            cursor.execute('''
            SELECT t.*, u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN users u ON t.created_by = u.id
            WHERE t.id = ?
            ''', (trip_id,))
            
            trip = cursor.fetchone()
            
            if not trip:
                return None
            
            # Get participants
            cursor.execute('''
            SELECT tp.*, s.first_name || ' ' || s.last_name as student_name, s.email_address
            FROM trip_participants tp
            LEFT JOIN students s ON tp.student_id = s.student_id
            WHERE tp.trip_id = ? AND tp.status = 'registered'
            ORDER BY tp.registration_date
            ''', (trip_id,))
            
            participants = cursor.fetchall()
            
            return {'trip': trip, 'participants': participants}
        
        result = self.safe_db_operation(get_trip_details_operation)
        
        if result:
            TripDetailsDialog(self.root, result['trip'], result['participants'])
    
    def show_create_trip(self):
        """Show create trip dialog"""
        if not self.auth.check_permission('create_trips'):
            messagebox.showerror("Permission Denied", "You don't have permission to create trips.")
            return
        
        CreateTripDialog(self.root, self.auth, self.refresh_trips)
    
    def register_for_trip(self):
        """Register for selected trip"""
        selection = self.reg_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip to register for.")
            return
        
        trip_id = self.reg_tree.item(selection[0])['text']
        RegisterForTripDialog(self.root, self.auth, trip_id, self.load_available_trips, self.load_my_trips)
    
    def cancel_registration(self):
        """Cancel selected registration"""
        selection = self.my_trips_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a registration to cancel.")
            return
        
        trip_id = self.my_trips_tree.item(selection[0])['text']
        values = self.my_trips_tree.item(selection[0])['values']
        trip_name = values[0] if values else f"Trip {trip_id}"
        payment_status = values[4] if len(values) > 4 else "unknown"

        CancelRegistrationDialog(
            self.root,
            self.auth,
            trip_id,
            trip_name,
            payment_status,
            self.load_my_trips
        )
    
    def load_available_trips(self):
        """Load available trips for registration"""
        # Clear existing items
        for item in self.reg_tree.get_children():
            self.reg_tree.delete(item)
        
        def load_available_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(tp.id) as current_participants
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            WHERE t.status IN ('open', 'planning')
            GROUP BY t.id
            HAVING current_participants < t.max_participants
            ORDER BY t.start_date ASC
            ''')
            
            return cursor.fetchall()
        
        trips = self.safe_db_operation(load_available_trips_operation)
        
        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts = trip
                spaces_left = max_parts - current_parts
                
                cost_str = f"£{cost:.2f}" if cost is not None else "£0.00"
                self.reg_tree.insert('', 'end', text=str(trip_id), values=(
                    name, destination, start_date, cost_str, str(spaces_left)
                ))
    
    def load_my_trips(self):
        """Load user's trip registrations"""
        if not self.auth.current_user:
            return
        
        # Clear existing items
        for item in self.my_trips_tree.get_children():
            self.my_trips_tree.delete(item)
        
        def load_my_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.cost, tp.registration_date, tp.payment_status, tp.status
            FROM trip_participants tp
            JOIN trips t ON tp.trip_id = t.id
            WHERE tp.user_id = ?
            ORDER BY t.start_date ASC
            ''', (self.auth.current_user['id'],))
            
            return cursor.fetchall()
        
        registrations = self.safe_db_operation(load_my_trips_operation)
        
        if registrations:
            for reg in registrations:
                trip_id, name, destination, start_date, end_date, cost, reg_date, payment_status, status = reg
                
                cost_str = f"£{cost:.2f}" if cost is not None else "£0.00"
                payment_str = payment_status.title() if payment_status else "Unknown"
                status_str = status.title() if status else "Unknown"
                self.my_trips_tree.insert('', 'end', text=str(trip_id), values=(
                    name, destination, start_date, cost_str, payment_str, status_str
                ))
    
    def setup_participants_management(self, parent):
        """Setup participants management interface"""
        # Trip selection
        trip_select_frame = ttk.Frame(parent)
        trip_select_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(trip_select_frame, text="Select Trip:").pack(side=tk.LEFT, padx=(0, 5))
        self.participant_trip_var = tk.StringVar()
        self.participant_trip_combo = ttk.Combobox(trip_select_frame, textvariable=self.participant_trip_var)
        self.participant_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(trip_select_frame, text="Load Participants", 
                  command=self.load_trip_participants).pack(side=tk.LEFT)
        
        # Participants list
        self.participants_tree = ttk.Treeview(parent, columns=('name', 'email', 'registration', 'payment', 'status'), show='tree headings')
        
        self.participants_tree.heading('#0', text='ID')
        self.participants_tree.heading('name', text='Name')
        self.participants_tree.heading('email', text='Email')
        self.participants_tree.heading('registration', text='Registration Date')
        self.participants_tree.heading('payment', text='Payment Status')
        self.participants_tree.heading('status', text='Status')
        
        self.participants_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Management buttons
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill=tk.X)
        
        ttk.Button(buttons_frame, text="Update Payment", 
                  command=self.update_payment_status).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Update Status", 
                  command=self.update_participant_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Remove Participant", 
                  command=self.remove_participant).pack(side=tk.LEFT, padx=5)
        
        # Load trips for selection
        self.load_trips_for_management()
    
    def setup_staff_assignment(self, parent):
        """Setup staff assignment interface"""
        ttk.Label(parent, text="Staff Assignment", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Trip selection for staff assignment
        staff_trip_frame = ttk.Frame(parent)
        staff_trip_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(staff_trip_frame, text="Select Trip:").pack(side=tk.LEFT, padx=(0, 5))
        self.staff_trip_var = tk.StringVar()
        self.staff_trip_combo = ttk.Combobox(
            staff_trip_frame,
            textvariable=self.staff_trip_var,
            state='readonly'
        )
        self.staff_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.staff_trip_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_trip_staff())
        
        # Staff assignment tree
        self.staff_tree = ttk.Treeview(parent, columns=('staff_name', 'role', 'assigned_date'), show='tree headings')
        
        self.staff_tree.heading('#0', text='ID')
        self.staff_tree.heading('staff_name', text='Staff Name')
        self.staff_tree.heading('role', text='Role')
        self.staff_tree.heading('assigned_date', text='Assigned Date')
        
        self.staff_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Assignment buttons
        staff_buttons_frame = ttk.Frame(parent)
        staff_buttons_frame.pack(fill=tk.X)
        
        ttk.Button(staff_buttons_frame, text="Assign Staff", 
                  command=self.assign_staff).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(staff_buttons_frame, text="Remove Staff", 
                  command=self.remove_staff).pack(side=tk.LEFT)

        self.load_staff_trip_options()
    
    def setup_expenses_management(self, parent):
        """Setup expenses management interface"""
        ttk.Label(parent, text="Expense Management", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Trip selection for expenses
        expense_trip_frame = ttk.Frame(parent)
        expense_trip_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(expense_trip_frame, text="Select Trip:").pack(side=tk.LEFT, padx=(0, 5))
        self.expense_trip_var = tk.StringVar()
        self.expense_trip_combo = ttk.Combobox(expense_trip_frame, textvariable=self.expense_trip_var)
        self.expense_trip_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(expense_trip_frame, text="Load Expenses", 
                  command=self.load_trip_expenses).pack(side=tk.LEFT)
        
        # Expenses tree
        self.expenses_tree = ttk.Treeview(parent, columns=('category', 'description', 'amount', 'date', 'recorded_by'), show='tree headings')
        
        self.expenses_tree.heading('#0', text='ID')
        self.expenses_tree.heading('category', text='Category')
        self.expenses_tree.heading('description', text='Description')
        self.expenses_tree.heading('amount', text='Amount')
        self.expenses_tree.heading('date', text='Date')
        self.expenses_tree.heading('recorded_by', text='Recorded By')
        
        self.expenses_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Expense buttons
        expense_buttons_frame = ttk.Frame(parent)
        expense_buttons_frame.pack(fill=tk.X)
        
        ttk.Button(expense_buttons_frame, text="Add Expense", 
                  command=self.add_expense).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(expense_buttons_frame, text="Edit Expense", 
                  command=self.edit_expense).pack(side=tk.LEFT, padx=5)
        ttk.Button(expense_buttons_frame, text="Delete Expense", 
                  command=self.delete_expense).pack(side=tk.LEFT, padx=5)
    
    def setup_trip_management(self, parent):
        """Setup trip management interface"""
        ttk.Label(parent, text="Trip Management", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Trip actions
        actions_frame = ttk.Frame(parent)
        actions_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(actions_frame, text="Update Trip", 
                  command=self.update_trip).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(actions_frame, text="Delete Trip", 
                  command=self.delete_trip).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Manage Itinerary", 
                  command=self.manage_itinerary).pack(side=tk.LEFT, padx=5)
        
        # Trip status summary
        summary_frame = ttk.LabelFrame(parent, text="Trip Summary", padding=10)
        summary_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.trip_summary_text = scrolledtext.ScrolledText(summary_frame, height=15)
        self.trip_summary_text.pack(fill=tk.BOTH, expand=True)
        
        self.load_trip_summary()
    
    def create_trips_context_menu(self):
        """Create context menu for trips treeview - enhanced"""
        self.trips_context_menu = tk.Menu(self.root, tearoff=0)
        self.trips_context_menu.add_command(label="View Details", command=self.view_selected_trip_details)
        self.trips_context_menu.add_command(label="View Itinerary", command=self.view_trip_itinerary)
        
        if self.auth.check_permission('register_for_trips'):
            self.trips_context_menu.add_command(label="Register for Trip", command=self.register_for_selected_trip)
        
        if self.auth.check_permission('manage_trips') or self.auth.check_permission('create_trips'):
            self.trips_context_menu.add_separator()
            self.trips_context_menu.add_command(label="Add/Edit Itinerary", command=self.add_trip_itinerary)
            self.trips_context_menu.add_command(label="Edit Trip", command=self.edit_selected_trip)
            
        if self.auth.check_permission('manage_trips'):
            self.trips_context_menu.add_command(label="Assign Staff", command=self.assign_trip_staff)
            self.trips_context_menu.add_command(label="Delete Trip", command=self.delete_selected_trip)
        
        self.trips_tree.bind("<Button-3>", self.show_trips_context_menu)
    
    def show_trips_context_menu(self, event):
        """Show context menu for trips"""
        selection = self.trips_tree.selection()
        if selection:
            self.trips_context_menu.post(event.x_root, event.y_root)
    
    def view_selected_trip_details(self):
        """View details of selected trip"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            self.show_trip_details(trip_id)
    
    def register_for_selected_trip(self):
        """Register for selected trip"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            RegisterForTripDialog(self.root, self.auth, trip_id, self.refresh_trips, self.load_my_trips)
    
    def edit_selected_trip(self):
        """Edit selected trip"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            UpdateTripDialog(self.root, self.auth, trip_id, self.refresh_trips)
    
    def delete_selected_trip(self):
        """Delete selected trip"""
        selection = self.trips_tree.selection()
        if selection:
            trip_id = self.trips_tree.item(selection[0])['text']
            trip_name = self.trips_tree.item(selection[0])['values'][0]
            
            if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete trip '{trip_name}'?"):
                def delete_trip_operation(conn):
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM trips WHERE id = ?', (trip_id,))
                    return True
                
                if self.safe_db_operation(delete_trip_operation):
                    messagebox.showinfo("Success", "Trip deleted successfully")
                    self.refresh_trips()
                else:
                    messagebox.showerror("Error", "Failed to delete trip")
    
    def load_trips_for_management(self):
        """Load trips for management dropdowns"""
        def load_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT id, trip_name FROM trips ORDER BY trip_name')
            return cursor.fetchall()
        
        trips = self.safe_db_operation(load_trips_operation)
        
        if trips:
            trip_list = [f"{trip[0]} - {trip[1]}" for trip in trips]
            
            # Update all trip selection comboboxes
            if hasattr(self, 'participant_trip_combo'):
                self.participant_trip_combo['values'] = trip_list
            if hasattr(self, 'staff_trip_combo'):
                self.staff_trip_combo['values'] = trip_list
            if hasattr(self, 'expense_trip_combo'):
                self.expense_trip_combo['values'] = trip_list

    # --- Add this helper anywhere in the class ---
    def _ensure_main_ui(self):
        """Ensure the main notebook exists."""
        if not hasattr(self, 'notebook'):
            self.show_main_interface()

    def _select_tab(self, label_text):
        """Select a top-level tab by its text label."""
        self._ensure_main_ui()
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == label_text:
                self.notebook.select(i)
                return True
        return False

    # --- ADD: implement the missing menu target ---
    def show_trips_view(self):
        """Menu action: go to the All Trips tab and refresh."""
        if self._select_tab('All Trips'):
            try:
                self.refresh_trips()
            except Exception as e:
                logger.warning(f"Failed to refresh trips view: {e}")

    def show_my_registrations(self):
        """Menu action: go to My Trips; create it if permissions allow."""
        self._ensure_main_ui()
        # If the tab isn't present yet but user can view their regs, add it.
        if not any(self.notebook.tab(i, 'text') == 'My Trips'
                   for i in range(self.notebook.index('end'))):
            if self.auth and self.auth.check_permission('view_own_trip_registrations'):
                self.add_my_trips_tab()
        self._select_tab('My Trips')
    
    def load_trip_participants(self):
        """Load participants for selected trip"""
        trip_selection = self.participant_trip_var.get()
        if not trip_selection:
            return
        
        trip_id = trip_selection.split(' - ')[0]
        
        # Clear existing items
        for item in self.participants_tree.get_children():
            self.participants_tree.delete(item)
        
        def load_participants_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT tp.id, tp.student_id, 
                   s.first_name || ' ' || s.last_name as student_name,
                   s.email_address, tp.registration_date, tp.payment_status, tp.status
            FROM trip_participants tp
            LEFT JOIN students s ON tp.student_id = s.student_id
            WHERE tp.trip_id = ?
            ORDER BY tp.registration_date
            ''', (trip_id,))
            
            return cursor.fetchall()
        
        participants = self.safe_db_operation(load_participants_operation)
        
        if participants:
            for participant in participants:
                p_id, student_id, student_name, email, reg_date, payment_status, status = participant
                name = student_name if student_name else f"Student {student_id}"
                email = email if email else "N/A"
                
                self.participants_tree.insert('', 'end', text=str(p_id), values=(
                    name, email, reg_date, payment_status.title(), status.title()
                ))
    
    def load_trip_expenses(self):
        """Load expenses for selected trip"""
        trip_selection = self.expense_trip_var.get()
        if not trip_selection:
            return
        
        trip_id = trip_selection.split(' - ')[0]
        
        # Clear existing items
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)
        
        def load_expenses_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT te.id, te.category, te.description, te.amount, te.date,
                   u.first_name || ' ' || u.last_name as recorded_by
            FROM trip_expenses te
            LEFT JOIN users u ON te.recorded_by = u.id
            WHERE te.trip_id = ?
            ORDER BY te.date DESC
            ''', (trip_id,))
            
            return cursor.fetchall()
        
        expenses = self.safe_db_operation(load_expenses_operation)
        
        if expenses:
            for expense in expenses:
                exp_id, category, description, amount, date, recorded_by = expense
                recorded_by = recorded_by if recorded_by else "Unknown"
                
                amount_str = f"£{amount:.2f}" if amount is not None else "£0.00"
                self.expenses_tree.insert('', 'end', text=str(exp_id), values=(
                    category, description, amount_str, date, recorded_by
                ))
    
    def load_trip_summary(self):
        """Load trip summary statistics"""
        def get_summary_operation(conn):
            cursor = conn.cursor()
            
            # Get basic trip statistics
            cursor.execute('''
            SELECT 
                COUNT(*) as total_trips,
                COUNT(CASE WHEN status = 'planning' THEN 1 END) as planning_trips,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_trips,
                COUNT(CASE WHEN status = 'full' THEN 1 END) as full_trips,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_trips,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_trips,
                SUM(cost) as total_revenue_potential,
                AVG(cost) as average_cost
            FROM trips
            ''')
            
            summary_stats = cursor.fetchone()
            
            # Get participant statistics
            cursor.execute('''
            SELECT 
                COUNT(*) as total_registrations,
                COUNT(CASE WHEN status = 'registered' THEN 1 END) as active_registrations,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_registrations,
                COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_registrations,
                COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending_payments
            FROM trip_participants
            ''')
            
            participant_stats = cursor.fetchone()
            
            return {'summary': summary_stats, 'participants': participant_stats}
        
        data = self.safe_db_operation(get_summary_operation)
        
        if data:
            summary_text = "TRIP MANAGEMENT SUMMARY\n"
            summary_text += "=" * 50 + "\n\n"
            
            summary_text += "TRIP STATISTICS:\n"
            summary_text += f"Total Trips: {data['summary'][0]}\n"
            summary_text += f"Planning: {data['summary'][1]}\n"
            summary_text += f"Open for Registration: {data['summary'][2]}\n"
            summary_text += f"Full: {data['summary'][3]}\n"
            summary_text += f"Completed: {data['summary'][4]}\n"
            summary_text += f"Cancelled: {data['summary'][5]}\n"
            revenue = data['summary'][6] if data['summary'][6] is not None else 0
            avg_cost = data['summary'][7] if data['summary'][7] is not None else 0
            summary_text += f"Total Revenue Potential: £{revenue:.2f}\n"
            summary_text += f"Average Trip Cost: £{avg_cost:.2f}\n\n"
            
            summary_text += "PARTICIPANT STATISTICS:\n"
            summary_text += f"Total Registrations: {data['participants'][0]}\n"
            summary_text += f"Active Registrations: {data['participants'][1]}\n"
            summary_text += f"Cancelled Registrations: {data['participants'][2]}\n"
            summary_text += f"Paid Registrations: {data['participants'][3]}\n"
            summary_text += f"Pending Payments: {data['participants'][4]}\n"
            
            self.trip_summary_text.delete(1.0, tk.END)
            self.trip_summary_text.insert(1.0, summary_text)
    
    def generate_trip_summary_report(self):
        """Generate trip summary report"""
        if not self.auth.check_permission('view_trip_reports'):
            messagebox.showerror("Permission Denied", "You don't have permission to generate reports.")
            return

        ReportGeneratorDialog(self.root, self.auth, 'TRIP_SUMMARY', self.report_log)
    
    def generate_participant_report(self):
        """Generate participant report"""
        if not self.auth.check_permission('view_trip_reports'):
            messagebox.showerror("Permission Denied", "You don't have permission to generate reports.")
            return

        ReportGeneratorDialog(self.root, self.auth, 'PARTICIPANT_LIST', self.report_log)
    
    def generate_financial_report(self):
        """Generate financial report"""
        if not self.auth.check_permission('view_financial_reports'):
            messagebox.showerror("Permission Denied", "You don't have permission to view financial reports.")
            return
        
        ReportGeneratorDialog(self.root, self.auth, 'FINANCIAL_REPORT', self.report_log)
    
    def update_payment_status(self):
        """Update payment status for selected participant"""
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a participant.")
            return
        
        participant_id = self.participants_tree.item(selection[0])['text']
        PaymentStatusDialog(self.root, participant_id, self.load_trip_participants)
    
    def update_participant_status(self):
        """Update status for selected participant"""
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a participant.")
            return
        
        participant_id = self.participants_tree.item(selection[0])['text']
        ParticipantStatusDialog(self.root, participant_id, self.load_trip_participants)
    
    def remove_participant(self):
        """Remove selected participant"""
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a participant.")
            return
        
        participant_id = self.participants_tree.item(selection[0])['text']
        participant_name = self.participants_tree.item(selection[0])['values'][0]
        
        if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove '{participant_name}' from this trip?"):
            def remove_participant_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_participants WHERE id = ?', (participant_id,))
                return True
            
            if self.safe_db_operation(remove_participant_operation):
                messagebox.showinfo("Success", "Participant removed successfully")
                self.load_trip_participants()
            else:
                messagebox.showerror("Error", "Failed to remove participant")
    
    def assign_staff(self):
        """Assign staff to trip"""
        trip_selection = self.staff_trip_var.get()
        if not trip_selection:
            messagebox.showwarning("No Trip Selected", "Please select a trip first.")
            return
        
        try:
            trip_id = int(trip_selection.split(' - ')[0].strip())
        except (ValueError, IndexError):
            messagebox.showerror("Invalid Selection", "Could not determine the selected trip.")
            return

        AssignStaffDialog(self.root, self.auth, trip_id, self.load_trip_staff)
    
    def remove_staff(self):
        """Remove staff from trip"""
        selection = self.staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member.")
            return
        
        staff_assignment_id = self.staff_tree.item(selection[0])['text']
        staff_name = self.staff_tree.item(selection[0])['values'][0]
        
        if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove '{staff_name}' from this trip?"):
            def remove_staff_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_staff WHERE id = ?', (staff_assignment_id,))
                return True
            
            if self.safe_db_operation(remove_staff_operation):
                messagebox.showinfo("Success", "Staff member removed successfully")
                self.load_trip_staff()
            else:
                messagebox.showerror("Error", "Failed to remove staff member")
    
    def load_trip_staff(self):
        """Load staff for selected trip"""
        trip_selection = self.staff_trip_var.get()
        if not trip_selection:
            return
        
        try:
            trip_id = int(trip_selection.split(' - ')[0].strip())
        except (ValueError, IndexError):
            return
        
        # Clear existing items
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)
        
        def load_staff_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT ts.id, ts.role, u.first_name || ' ' || u.last_name as staff_name, ts.assigned_date
            FROM trip_staff ts
            JOIN users u ON ts.staff_user_id = u.id
            WHERE ts.trip_id = ?
            ORDER BY ts.role, staff_name
            ''', (trip_id,))
            
            return cursor.fetchall()
        
        staff = self.safe_db_operation(load_staff_operation) or []
        
        for staff_member in staff:
            staff_id, role, name, assigned_date = staff_member
            
            self.staff_tree.insert('', 'end', text=str(staff_id), values=(
                name, role.title(), assigned_date
            ))

    def load_staff_trip_options(self):
        """Populate trip selector for staff assignment"""
        def fetch_trips(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, trip_name, destination, start_date
            FROM trips
            ORDER BY start_date DESC
            ''')
            return cursor.fetchall()

        trips = self.safe_db_operation(fetch_trips) or []
        display_values = [
            f"{trip_id} - {name} ({destination}) [{start_date}]"
            for trip_id, name, destination, start_date in trips
        ]
        self.staff_trip_combo['values'] = display_values
        if display_values:
            self.staff_trip_combo.set(display_values[0])
            self.load_trip_staff()
        trip_selection = self.staff_trip_var.get()
        if not trip_selection:
            return
        
        trip_id = trip_selection.split(' - ')[0]
        
        # Clear existing items
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)
        
        def load_staff_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT ts.id, ts.role, u.first_name || ' ' || u.last_name as staff_name, ts.assigned_date
            FROM trip_staff ts
            JOIN users u ON ts.staff_user_id = u.id
            WHERE ts.trip_id = ?
            ORDER BY ts.role
            ''', (trip_id,))
            
            return cursor.fetchall()
        
        staff = self.safe_db_operation(load_staff_operation)
        
        if staff:
            for staff_member in staff:
                staff_id, role, name, assigned_date = staff_member
                
                self.staff_tree.insert('', 'end', text=str(staff_id), values=(
                    name, role.title(), assigned_date
                ))
    
    def add_expense(self):
        """Add new expense"""
        trip_selection = self.expense_trip_var.get()
        if not trip_selection:
            messagebox.showwarning("No Trip Selected", "Please select a trip first.")
            return
        
        trip_id = trip_selection.split(' - ')[0]
        AddExpenseDialog(self.root, self.auth, trip_id, self.load_trip_expenses)
    
    def edit_expense(self):
        """Edit selected expense"""
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an expense.")
            return
        
        expense_id = self.expenses_tree.item(selection[0])['text']
        EditExpenseDialog(self.root, expense_id, self.load_trip_expenses)
    
    def delete_expense(self):
        """Delete selected expense"""
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an expense.")
            return
        
        expense_id = self.expenses_tree.item(selection[0])['text']
        expense_desc = self.expenses_tree.item(selection[0])['values'][1]
        
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete expense '{expense_desc}'?"):
            def delete_expense_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_expenses WHERE id = ?', (expense_id,))
                return True
            
            if self.safe_db_operation(delete_expense_operation):
                messagebox.showinfo("Success", "Expense deleted successfully")
                self.load_trip_expenses()
            else:
                messagebox.showerror("Error", "Failed to delete expense")
    
    def update_trip(self):
        """Update trip information"""
        # Show trip selection dialog first
        TripSelectionDialog(self.root, self.auth, self.open_update_trip_dialog)
    
    def open_update_trip_dialog(self, trip_id):
        """Open update trip dialog for specific trip"""
        UpdateTripDialog(self.root, self.auth, trip_id, self.refresh_trips)
    
    def delete_trip(self):
        """Delete trip"""
        TripSelectionDialog(self.root, self.auth, self.confirm_delete_trip)
    
    def confirm_delete_trip(self, trip_id):
        """Confirm and delete trip"""
        def get_trip_info_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT trip_name FROM trips WHERE id = ?', (trip_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        
        trip_name = self.safe_db_operation(get_trip_info_operation)
        
        if trip_name and messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete trip '{trip_name}'?"):
            def delete_trip_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trips WHERE id = ?', (trip_id,))
                return True
            
            if self.safe_db_operation(delete_trip_operation):
                messagebox.showinfo("Success", "Trip deleted successfully")
                self.refresh_trips()
                self.load_trip_summary()
            else:
                messagebox.showerror("Error", "Failed to delete trip")
    
    def manage_itinerary(self):
        """Manage trip itinerary"""
        TripSelectionDialog(self.root, self.auth, self.open_itinerary_dialog)
    
    def open_itinerary_dialog(self, trip_id):
        """Open itinerary management dialog"""
        ItineraryDialog(self.root, self.auth, trip_id)
    
    def show_trips_with_calendar(self):
        """Show trips with calendar integration"""
        if not self.calendar_manager:
            messagebox.showerror("Calendar Unavailable", "Calendar integration is not available.")
            return
        
        # Clear existing items
        for item in self.calendar_tree.get_children():
            self.calendar_tree.delete(item)
        
        def load_calendar_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status,
                   e.name as calendar_event_name,
                   e.id as calendar_event_id
            FROM trips t
            LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
            LEFT JOIN events e ON tce.event_id = e.id
            ORDER BY t.start_date ASC
            ''')
            
            return cursor.fetchall()
        
        trips = self.safe_db_operation(load_calendar_trips_operation)
        
        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, end_date, status, cal_event_name, cal_event_id = trip
                calendar_info = cal_event_name if cal_event_name else "No Event"
                
                self.calendar_tree.insert('', 'end', text=str(trip_id), values=(
                    name, calendar_info, start_date, status.title()
                ))

    def view_trip_events_in_calendar(self):
        """View trip events in the calendar (calendar-centric view)"""
        if not CALENDAR_AVAILABLE or not self.calendar_manager:
            messagebox.showwarning("Calendar Not Available",
                                 "Calendar system is not available.")
            return

        try:
            # Get trip events from calendar for next 365 days
            current_date = datetime.now().strftime('%Y-%m-%d')
            future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')

            events = self.calendar_manager.get_events_by_date_range(
                current_date, future_date, 'Trip'
            )

            if not events:
                messagebox.showinfo("No Events", "No trip events found in calendar for the next year.")
                return

            # Create dialog to display events
            dialog = tk.Toplevel(self.root)
            dialog.title("Trip Events in Calendar")
            dialog.geometry("900x600")
            dialog.transient(self.root)

            # Title
            ttk.Label(dialog, text="Trip Events in Calendar",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            ttk.Label(dialog, text=f"Showing trip events for next 365 days ({len(events)} events found)",
                     font=('Arial', 9)).pack(pady=(0, 10))

            # Create treeview for events
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            columns = ('event_name', 'start_date', 'end_date', 'description')
            tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)

            tree.heading('event_name', text='Event Name')
            tree.heading('start_date', text='Start Date')
            tree.heading('end_date', text='End Date')
            tree.heading('description', text='Description')

            tree.column('event_name', width=250)
            tree.column('start_date', width=120)
            tree.column('end_date', width=120)
            tree.column('description', width=350)

            # Add scrollbar
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Populate with events
            for event in events:
                start_date = event.get('date_start') or event.get('date', 'TBD')
                end_date = event.get('date_end') or event.get('date', 'TBD')
                description = (event.get('description') or 'No description')[:80]

                tree.insert('', tk.END, values=(
                    event.get('name', 'Unnamed Event'),
                    start_date,
                    end_date,
                    description
                ))

            # Close button
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

            # Log activity
            log_read('trip_calendar_events', f"Viewed {len(events)} trip events in calendar")
            self.update_status(f"Showing {len(events)} trip events from calendar")

        except Exception as e:
            logging.error(f"Error viewing trip events in calendar: {e}")
            messagebox.showerror("Error", f"Failed to view trip events: {str(e)}")

    def create_trip_calendar_event(self):
        """Create calendar event for trip"""
        if not self.calendar_manager:
            messagebox.showerror("Calendar Unavailable", "Calendar integration is not available.")
            return
        
        CreateCalendarEventDialog(self.root, self.auth, self.calendar_manager, self.show_trips_with_calendar)
    
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
                from university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def export_data(self):
        """Export trip data"""
        ExportDataDialog(self.root, self.auth)

    def show_about(self):
        """Show about dialog"""
        AboutDialog(self.root)
    
    def safe_db_operation(self, operation_func, *args, max_retries=3, **kwargs):
        """Safely execute a database operation with retry logic - integrated from original"""
        retry_delay = 0.1
        last_error = None
        
        for attempt in range(max_retries):
            conn = None
            try:
                conn = self.get_db_connection(timeout=30.0)
                if not conn:
                    last_error = "Failed to establish database connection"
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    return False
                
                result = operation_func(conn, *args, **kwargs)
                conn.commit()
                return result
                
            except sqlite3.OperationalError as e:
                last_error = e
                if conn:
                    try:
                        conn.rollback()
                    except Exception as rollback_err:
                        logger.debug(f"Failed to rollback after database locked error: {rollback_err}")
                
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    return False
                    
            except Exception as e:
                last_error = e
                if conn:
                    try:
                        conn.rollback()
                    except Exception as rollback_err:
                        logger.debug(f"Failed to rollback transaction: {rollback_err}")
                return False

            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception as close_err:
                        logger.debug(f"Failed to close database connection: {close_err}")
        
        return False
    
    def get_db_connection(self, timeout=30.0, max_retries=3):
        """Get a database connection - uses centralized thread-safe connection.

        Uses the centralized get_connection() function which maintains thread safety
        by keeping check_same_thread=True (SQLite default). Each thread gets its own
        connection to prevent cross-thread data corruption.
        """
        from university_system.infrastructure.database.db import get_connection

        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                # Use centralized get_connection which is thread-safe
                # check_same_thread=True is maintained (the safe default)
                conn = get_connection(db_path=DEFAULT_DB_PATH, timeout=timeout)

                # Additional PRAGMA settings for this module's needs
                conn.execute("PRAGMA temp_store = MEMORY")
                conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
                conn.execute("PRAGMA cache_size = 10000")
                return conn

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    return None
            except sqlite3.Error:
                return None
    
    def run(self):
        if getattr(self, "_owns_root", False):
            self.root.mainloop()

class CancelRegistrationDialog(Dialog):
    def __init__(self, parent, auth, trip_id, trip_name, payment_status, refresh_callback):
        self.auth = auth
        self.trip_id = trip_id
        self.trip_name = trip_name
        self.payment_status = payment_status
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Cancel Trip Registration")
    
    def body(self, master):
        """Create the dialog body"""
        # Trip information
        info_frame = ttk.LabelFrame(master, text="Registration Details", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Trip: {self.trip_name}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Payment Status: {self.payment_status.title()}").pack(anchor=tk.W)
        
        if self.payment_status.lower() in ['paid', 'partial']:
            ttk.Label(info_frame, text="⚠️ Warning: You have made payment(s) for this trip.", 
                     foreground="orange", font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=5)
            ttk.Label(info_frame, text="Cancellation may involve refund processing.").pack(anchor=tk.W)
        
        # Cancellation reason
        ttk.Label(master, text="Reason for cancellation (optional):").pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.reason_text = tk.Text(master, width=50, height=3)
        self.reason_text.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        return self.reason_text
    
    def apply(self):
        """Apply the cancellation"""
        def cancel_operation(conn):
            cursor = conn.cursor()
            
            # Check if registration exists and belongs to user
            cursor.execute('''
            SELECT id FROM trip_participants 
            WHERE trip_id = ? AND user_id = ? AND status = 'registered'
            ''', (self.trip_id, self.auth.current_user['id']))
            
            if not cursor.fetchone():
                return "not_found"
            
            # Update registration status to cancelled
            reason = self.reason_text.get(1.0, tk.END).strip()
            cursor.execute('''
            UPDATE trip_participants 
            SET status = 'cancelled', 
                cancellation_reason = ?,
                cancellation_date = ?
            WHERE trip_id = ? AND user_id = ?
            ''', (reason, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                  self.trip_id, self.auth.current_user['id']))
            
            return "success"
        
        result = self.safe_db_operation(cancel_operation)
        
        if result == "not_found":
            messagebox.showerror("Error", "Registration not found or already cancelled.")
        elif result == "success":
            messagebox.showinfo("Success", f"Registration for '{self.trip_name}' has been cancelled.")
            if self.payment_status.lower() in ['paid', 'partial']:
                messagebox.showinfo("Refund Information", 
                                   "Please contact administration regarding refund processing.")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to cancel registration.")
    
    def safe_db_operation(self, operation_func):
        """Use the same safe_db_operation as the main GUI"""
        return safe_db_operation(operation_func)


class ViewItineraryDialog(Dialog):
    def __init__(self, parent, trip_id):
        self.trip_id = trip_id
        self.trip_info = None
        self.load_trip_info()
        super().__init__(parent, "View Trip Itinerary")
    
    def load_trip_info(self):
        """Load trip information and itinerary"""
        def get_trip_itinerary_operation(conn):
            cursor = conn.cursor()
            
            # Get trip details
            cursor.execute('''
            SELECT trip_name, destination, start_date, end_date 
            FROM trips WHERE id = ?
            ''', (self.trip_id,))
            
            trip_info = cursor.fetchone()
            
            if not trip_info:
                return None
            
            # Get itinerary items
            cursor.execute('''
            SELECT day_number, activity, location, start_time, end_time, notes
            FROM trip_itinerary
            WHERE trip_id = ?
            ORDER BY day_number, start_time
            ''', (self.trip_id,))
            
            itinerary_items = cursor.fetchall()
            
            return {'trip_info': trip_info, 'itinerary': itinerary_items}
        
        self.trip_data = safe_db_operation(get_trip_itinerary_operation)
    
    def body(self, master):
        """Create the dialog body"""
        if not self.trip_data:
            ttk.Label(master, text="Trip not found or no itinerary available.").pack(pady=20)
            return None
        
        trip_info = self.trip_data['trip_info']
        itinerary_items = self.trip_data['itinerary']
        
        trip_name, destination, start_date, end_date = trip_info
        
        # Trip information header
        info_frame = ttk.LabelFrame(master, text="Trip Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Trip: {trip_name}", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Destination: {destination}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Dates: {start_date} to {end_date}").pack(anchor=tk.W)
        
        # Itinerary display
        itinerary_frame = ttk.LabelFrame(master, text="Itinerary", padding=10)
        itinerary_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        if not itinerary_items:
            ttk.Label(itinerary_frame, text="No itinerary items found for this trip.").pack(pady=20)
            return None
        
        # Create scrolled text widget for itinerary
        itinerary_text = scrolledtext.ScrolledText(itinerary_frame, width=70, height=20, 
                                                  wrap=tk.WORD, state=tk.DISABLED)
        itinerary_text.pack(fill=tk.BOTH, expand=True)
        
        # Populate itinerary
        itinerary_text.config(state=tk.NORMAL)
        
        current_day = None
        for item in itinerary_items:
            day_number, activity, location, start_time, end_time, notes = item
            
            if current_day != day_number:
                if current_day is not None:
                    itinerary_text.insert(tk.END, "\n")
                itinerary_text.insert(tk.END, f"DAY {day_number}:\n", "day_header")
                itinerary_text.insert(tk.END, "-" * 20 + "\n")
                current_day = day_number
            
            # Format time information
            if start_time and end_time:
                time_info = f"({start_time} - {end_time})"
            elif start_time:
                time_info = f"(from {start_time})"
            else:
                time_info = ""
            
            # Format location information
            location_info = f" at {location}" if location else ""
            
            itinerary_text.insert(tk.END, f"• {activity}{location_info} {time_info}\n")
            
            if notes:
                itinerary_text.insert(tk.END, f"  Notes: {notes}\n")
            
            itinerary_text.insert(tk.END, "\n")
        
        # Configure text tags for styling
        itinerary_text.tag_configure("day_header", font=('Arial', 10, 'bold'))
        itinerary_text.config(state=tk.DISABLED)
        
        return None
    
    def buttonbox(self):
        """Create button box"""
        box = ttk.Frame(self)
        ttk.Button(box, text="Close", command=self.ok).pack()
        box.pack(pady=10)

class TripDetailsDialog(Dialog):
    def __init__(self, parent, trip_data, participants_data):
        self.trip_data = trip_data
        self.participants_data = participants_data
        super().__init__(parent, "Trip Details")
    
    def body(self, master):
        """Create the dialog body"""
        # Trip information
        info_frame = ttk.LabelFrame(master, text="Trip Information", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        trip = self.trip_data
        row = 0
        
        fields = [
            ("ID:", str(trip[0])),
            ("Name:", trip[1]),
            ("Description:", trip[2] or "None"),
            ("Destination:", trip[3]),
            ("Start Date:", trip[4]),
            ("End Date:", trip[5]),
            ("Max Participants:", str(trip[6])),
            ("Cost:", f"£{trip[7]:.2f}" if trip[7] is not None else "£0.00"),
            ("Status:", trip[8].title()),
            ("Created By:", trip[11] if trip[11] else "Unknown"),
            ("Created:", trip[9]),
            ("Updated:", trip[10])
        ]
        
        for label, value in fields:
            ttk.Label(info_frame, text=label, font=('Arial', 9, 'bold')).grid(row=row, column=0, sticky=tk.W, padx=(0, 10), pady=2)
            ttk.Label(info_frame, text=value).grid(row=row, column=1, sticky=tk.W, pady=2)
            row += 1
        
        # Participants information
        participants_frame = ttk.LabelFrame(master, text=f"Participants ({len(self.participants_data)})", padding=10)
        participants_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        if self.participants_data:
            # Create treeview for participants
            participants_tree = ttk.Treeview(participants_frame, columns=('name', 'email', 'registration', 'payment'), show='headings', height=8)
            
            participants_tree.heading('name', text='Name')
            participants_tree.heading('email', text='Email')
            participants_tree.heading('registration', text='Registration Date')
            participants_tree.heading('payment', text='Payment Status')
            
            for participant in self.participants_data:
                name = participant[9] if participant[9] else "Unknown"
                email = participant[10] if participant[10] else "N/A"
                reg_date = participant[3]
                payment = participant[4].title()
                
                participants_tree.insert('', 'end', values=(name, email, reg_date, payment))
            
            participants_tree.pack(fill=tk.BOTH, expand=True)
        else:
            ttk.Label(participants_frame, text="No participants registered yet.").pack()
        
        return None  # No initial focus
    
    def buttonbox(self):
        """Create button box"""
        box = ttk.Frame(self)
        ttk.Button(box, text="Close", command=self.ok).pack(side=tk.RIGHT, padx=5)
        box.pack(pady=5)

class CreateTripDialog(Dialog):
    def __init__(self, parent, auth, refresh_callback):
        self.auth = auth
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Create New Trip")
    
    def body(self, master):
        """Create the dialog body"""
        # Trip name
        ttk.Label(master, text="Trip Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Description
        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.description_text = tk.Text(master, width=40, height=3)
        self.description_text.grid(row=1, column=1, padx=5, pady=5)
        
        # Destination
        ttk.Label(master, text="Destination:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.destination_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.destination_var, width=40).grid(row=2, column=1, padx=5, pady=5)
        
        # Start date
        ttk.Label(master, text="Start Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_date_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.start_date_var, width=40).grid(row=3, column=1, padx=5, pady=5)
        
        # End date
        ttk.Label(master, text="End Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_date_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.end_date_var, width=40).grid(row=4, column=1, padx=5, pady=5)
        
        # Max participants
        ttk.Label(master, text="Max Participants:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_participants_var = tk.StringVar(value="50")
        ttk.Entry(master, textvariable=self.max_participants_var, width=40).grid(row=5, column=1, padx=5, pady=5)
        
        # Cost
        ttk.Label(master, text="Cost per person (£):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.cost_var = tk.StringVar(value="0.0")
        ttk.Entry(master, textvariable=self.cost_var, width=40).grid(row=6, column=1, padx=5, pady=5)
        
        # Status
        ttk.Label(master, text="Status:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.status_var = tk.StringVar(value="planning")
        status_combo = ttk.Combobox(master, textvariable=self.status_var,
                                   values=["planning", "open"], state="readonly", width=37)
        status_combo.grid(row=7, column=1, padx=5, pady=5)

        return self.name_entry  # Initial focus
    
    def validate(self):
        """Validate form data"""
        try:
            # Validate required fields
            if len(self.name_var.get().strip()) < 3:
                messagebox.showerror("Validation Error", "Trip name must be at least 3 characters long.")
                return False
            
            if len(self.destination_var.get().strip()) < 3:
                messagebox.showerror("Validation Error", "Destination must be at least 3 characters long.")
                return False
            
            # Validate dates
            start_date = datetime.strptime(self.start_date_var.get(), '%Y-%m-%d')
            end_date = datetime.strptime(self.end_date_var.get(), '%Y-%m-%d')
            
            if start_date.date() <= datetime.now().date():
                messagebox.showerror("Validation Error", "Start date must be in the future.")
                return False
            
            if end_date.date() <= start_date.date():
                messagebox.showerror("Validation Error", "End date must be after start date.")
                return False
            
            # Validate numbers
            max_participants = int(self.max_participants_var.get())
            if max_participants <= 0:
                messagebox.showerror("Validation Error", "Maximum participants must be greater than 0.")
                return False
            
            cost = float(self.cost_var.get())
            if cost < 0:
                messagebox.showerror("Validation Error", "Cost cannot be negative.")
                return False
            
            return True
            
        except ValueError as e:
            messagebox.showerror("Validation Error", f"Invalid input: {e}")
            return False
    
    def apply(self):
        """Apply the changes"""
        def create_trip_operation(conn):
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO trips (
                trip_name, description, destination, start_date, end_date,
                max_participants, cost, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.name_var.get().strip(),
                self.description_text.get(1.0, tk.END).strip(),
                self.destination_var.get().strip(),
                self.start_date_var.get(),
                self.end_date_var.get(),
                int(self.max_participants_var.get()),
                float(self.cost_var.get()),
                self.status_var.get(),
                self.auth.current_user['id'],
                timestamp,
                timestamp
            ))
            
            return cursor.lastrowid
        
        # Use the safe_db_operation method (we'll need to pass this from the main class)
        
        trip_id = safe_db_operation(create_trip_operation)
        
        if trip_id:
            messagebox.showinfo("Success", f"Trip '{self.name_var.get()}' created successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to create trip.")


class RegisterForTripDialog(Dialog):
    def __init__(self, parent, auth, trip_id, refresh_callback1, refresh_callback2):
        self.auth = auth
        self.trip_id = trip_id
        self.refresh_callback1 = refresh_callback1
        self.refresh_callback2 = refresh_callback2
        self.trip_info = None
        
        # Get trip information first
        self.load_trip_info()
        
        super().__init__(parent, "Register for Trip")
    
    def load_trip_info(self):
        """Load trip information"""
        def get_trip_info_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT trip_name, destination, start_date, cost, max_participants,
                   (SELECT COUNT(*) FROM trip_participants WHERE trip_id = ? AND status = 'registered') as current_participants
            FROM trips WHERE id = ?
            ''', (self.trip_id, self.trip_id))
            
            return cursor.fetchone()
        
        self.trip_info = safe_db_operation(get_trip_info_operation)
    
    def body(self, master):
        """Create the dialog body"""
        if not self.trip_info:
            ttk.Label(master, text="Trip not found.").pack(pady=20)
            return None
        
        trip_name, destination, start_date, cost, max_participants, current_participants = self.trip_info
        
        # Trip information
        info_frame = ttk.LabelFrame(master, text="Trip Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Trip: {trip_name}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Destination: {destination}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Start Date: {start_date}").pack(anchor=tk.W)
        cost_str = f"£{cost:.2f}" if cost is not None else "£0.00"
        ttk.Label(info_frame, text=f"Cost: {cost_str}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Participants: {current_participants}/{max_participants}").pack(anchor=tk.W)
        
        # Registration form
        reg_frame = ttk.LabelFrame(master, text="Registration Details", padding=10)
        reg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Emergency contact
        ttk.Label(reg_frame, text="Emergency Contact (Name and Phone):").pack(anchor=tk.W)
        self.emergency_var = tk.StringVar()
        self.emergency_entry = ttk.Entry(reg_frame, textvariable=self.emergency_var, width=50)
        self.emergency_entry.pack(fill=tk.X, pady=(0, 10))

        # Medical information
        ttk.Label(reg_frame, text="Medical Information (optional):").pack(anchor=tk.W)
        self.medical_text = tk.Text(reg_frame, width=50, height=3)
        self.medical_text.pack(fill=tk.X, pady=(0, 10))

        # Dietary requirements
        ttk.Label(reg_frame, text="Dietary Requirements (optional):").pack(anchor=tk.W)
        self.dietary_text = tk.Text(reg_frame, width=50, height=2)
        self.dietary_text.pack(fill=tk.X)

        return self.emergency_entry  # Initial focus - return widget, not StringVar
    
    def validate(self):
        """Validate registration data"""
        if not self.emergency_var.get().strip():
            messagebox.showerror("Validation Error", "Emergency contact information is required.")
            return False
        return True
    
    def apply(self):
        """Apply the registration"""
        def register_operation(conn):
            cursor = conn.cursor()
            
            # Check if already registered
            cursor.execute('''
            SELECT id FROM trip_participants 
            WHERE trip_id = ? AND user_id = ?
            ''', (self.trip_id, self.auth.current_user['id']))
            
            if cursor.fetchone():
                return "already_registered"
            
            # Get student ID if user is a student
            student_id = None
            if self.auth.current_user['role'] == 'student':
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                result = cursor.fetchone()
                if result:
                    student_id = result[0]
            
            # Register for trip
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO trip_participants (
                trip_id, student_id, user_id, registration_date,
                emergency_contact, medical_info, dietary_requirements
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.trip_id, student_id, self.auth.current_user['id'], timestamp,
                self.emergency_var.get().strip(),
                self.medical_text.get(1.0, tk.END).strip(),
                self.dietary_text.get(1.0, tk.END).strip()
            ))
            
            return "success"
        
        result = safe_db_operation(register_operation)
        
        if result == "already_registered":
            messagebox.showwarning("Already Registered", "You are already registered for this trip.")
        elif result == "success":
            messagebox.showinfo("Success", "Successfully registered for the trip!")
            if self.refresh_callback1:
                self.refresh_callback1()
            if self.refresh_callback2:
                self.refresh_callback2()
        else:
            messagebox.showerror("Error", "Failed to register for trip.")


class UpdateTripDialog(Dialog):
    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = trip_id
        self.refresh_callback = refresh_callback
        self.trip_data = None
        
        # Load trip data
        self.load_trip_data()
        
        super().__init__(parent, "Update Trip")
    
    def load_trip_data(self):
        """Load existing trip data"""
        def get_trip_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trips WHERE id = ?', (self.trip_id,))
            return cursor.fetchone()
        
        self.trip_data = safe_db_operation(get_trip_operation)
    
    def body(self, master):
        """Create the dialog body"""
        if not self.trip_data:
            ttk.Label(master, text="Trip not found.").pack(pady=20)
            return None
        
        # Pre-populate fields with existing data
        trip = self.trip_data
        
        # Trip name
        ttk.Label(master, text="Trip Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.name_var = tk.StringVar(value=trip[1])
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Description
        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.description_text = tk.Text(master, width=40, height=3)
        self.description_text.insert(1.0, trip[2] or "")
        self.description_text.grid(row=1, column=1, padx=5, pady=5)
        
        # Destination
        ttk.Label(master, text="Destination:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.destination_var = tk.StringVar(value=trip[3])
        ttk.Entry(master, textvariable=self.destination_var, width=40).grid(row=2, column=1, padx=5, pady=5)
        
        # Start date
        ttk.Label(master, text="Start Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_date_var = tk.StringVar(value=trip[4])
        ttk.Entry(master, textvariable=self.start_date_var, width=40).grid(row=3, column=1, padx=5, pady=5)
        
        # End date
        ttk.Label(master, text="End Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_date_var = tk.StringVar(value=trip[5])
        ttk.Entry(master, textvariable=self.end_date_var, width=40).grid(row=4, column=1, padx=5, pady=5)
        
        # Max participants
        ttk.Label(master, text="Max Participants:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_participants_var = tk.StringVar(value=str(trip[6]))
        ttk.Entry(master, textvariable=self.max_participants_var, width=40).grid(row=5, column=1, padx=5, pady=5)
        
        # Cost
        ttk.Label(master, text="Cost per person (£):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.cost_var = tk.StringVar(value=str(trip[7]))
        ttk.Entry(master, textvariable=self.cost_var, width=40).grid(row=6, column=1, padx=5, pady=5)
        
        # Status
        ttk.Label(master, text="Status:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.status_var = tk.StringVar(value=trip[8])
        status_combo = ttk.Combobox(master, textvariable=self.status_var,
                                   values=["planning", "open", "full", "cancelled", "completed"],
                                   state="readonly", width=37)
        status_combo.grid(row=7, column=1, padx=5, pady=5)

        return self.name_entry  # Initial focus
    
    def validate(self):
        """Validate form data"""
        try:
            # Validate required fields
            if len(self.name_var.get().strip()) < 3:
                messagebox.showerror("Validation Error", "Trip name must be at least 3 characters long.")
                return False
            
            if len(self.destination_var.get().strip()) < 3:
                messagebox.showerror("Validation Error", "Destination must be at least 3 characters long.")
                return False
            
            # Validate dates
            datetime.strptime(self.start_date_var.get(), '%Y-%m-%d')
            datetime.strptime(self.end_date_var.get(), '%Y-%m-%d')
            
            # Validate numbers
            max_participants = int(self.max_participants_var.get())
            if max_participants <= 0:
                messagebox.showerror("Validation Error", "Maximum participants must be greater than 0.")
                return False
            
            cost = float(self.cost_var.get())
            if cost < 0:
                messagebox.showerror("Validation Error", "Cost cannot be negative.")
                return False
            
            return True
            
        except ValueError as e:
            messagebox.showerror("Validation Error", f"Invalid input: {e}")
            return False
    
    def apply(self):
        """Apply the changes"""
        def update_trip_operation(conn):
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            UPDATE trips SET 
                trip_name = ?, description = ?, destination = ?, 
                start_date = ?, end_date = ?, max_participants = ?, 
                cost = ?, status = ?, updated_at = ?
            WHERE id = ?
            ''', (
                self.name_var.get().strip(),
                self.description_text.get(1.0, tk.END).strip(),
                self.destination_var.get().strip(),
                self.start_date_var.get(),
                self.end_date_var.get(),
                int(self.max_participants_var.get()),
                float(self.cost_var.get()),
                self.status_var.get(),
                timestamp,
                self.trip_id
            ))
            
            return True
        
        
        if safe_db_operation(update_trip_operation):
            messagebox.showinfo("Success", "Trip updated successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to update trip.")


class TripSelectionDialog(Dialog):
    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback
        self.selected_trip_id = None
        super().__init__(parent, "Select Trip")
    
    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text="Select a trip:", font=('Arial', 10, 'bold')).pack(pady=(0, 10))
        
        # Trip selection listbox
        self.trip_listbox = tk.Listbox(master, width=60, height=15)
        self.trip_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Load trips
        self.load_trips()
        
        return self.trip_listbox  # Initial focus
    
    def load_trips(self):
        """Load trips into listbox"""
        def get_trips_operation(conn):
            cursor = conn.cursor()
            
            if self.auth.check_permission('manage_trips'):
                cursor.execute('''
                SELECT id, trip_name, destination, start_date, status
                FROM trips
                ORDER BY start_date DESC
                ''')
            else:
                cursor.execute('''
                SELECT id, trip_name, destination, start_date, status
                FROM trips
                WHERE created_by = ?
                ORDER BY start_date DESC
                ''', (self.auth.current_user['id'],))
            
            return cursor.fetchall()
        
        trips = safe_db_operation(get_trips_operation)
        
        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, status = trip
                display_text = f"{trip_id}: {name} - {destination} ({start_date}) [{status.title()}]"
                self.trip_listbox.insert(tk.END, display_text)
    
    def validate(self):
        """Validate selection"""
        selection = self.trip_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip.")
            return False
        
        # Extract trip ID from selection
        selected_text = self.trip_listbox.get(selection[0])
        self.selected_trip_id = int(selected_text.split(':')[0])
        return True
    
    def apply(self):
        """Apply the selection"""
        if self.callback and self.selected_trip_id:
            self.callback(self.selected_trip_id)


class PaymentStatusDialog(Dialog):
    def __init__(self, parent, participant_id, refresh_callback):
        self.participant_id = participant_id
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Update Payment Status")
    
    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text="Select new payment status:").pack(pady=10)
        
        self.payment_var = tk.StringVar(value="pending")
        
        payment_options = ['pending', 'partial', 'paid', 'refunded']
        for option in payment_options:
            ttk.Radiobutton(master, text=option.title(), variable=self.payment_var, 
                           value=option).pack(anchor=tk.W, padx=20)
        
        return None
    
    def apply(self):
        """Apply the payment status update"""
        def update_payment_operation(conn):
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE trip_participants SET payment_status = ? WHERE id = ?',
                (self.payment_var.get(), self.participant_id)
            )
            return True
        
        
        if safe_db_operation(update_payment_operation):
            messagebox.showinfo("Success", "Payment status updated successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to update payment status.")


class ParticipantStatusDialog(Dialog):
    def __init__(self, parent, participant_id, refresh_callback):
        self.participant_id = participant_id
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Update Participant Status")
    
    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text="Select new participant status:").pack(pady=10)
        
        self.status_var = tk.StringVar(value="registered")
        
        status_options = ['registered', 'waitlist', 'cancelled', 'attended']
        for option in status_options:
            ttk.Radiobutton(master, text=option.title(), variable=self.status_var, 
                           value=option).pack(anchor=tk.W, padx=20)
        
        return None
    
    def apply(self):
        """Apply the status update"""
        def update_status_operation(conn):
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE trip_participants SET status = ? WHERE id = ?',
                (self.status_var.get(), self.participant_id)
            )
            return True
        
        
        if safe_db_operation(update_status_operation):
            messagebox.showinfo("Success", "Participant status updated successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to update participant status.")


class ReportGeneratorDialog(Dialog):
    def __init__(self, parent, auth, report_type, log_widget):
        self.auth = auth
        self.report_type = report_type
        self.log_widget = log_widget
        super().__init__(parent, f"Generate {report_type.replace('_', ' ').title()} Report")
    
    def body(self, master):
        """Create the dialog body"""
        # Report type display
        ttk.Label(master, text=f"Report Type: {self.report_type.replace('_', ' ').title()}", 
                 font=('Arial', 10, 'bold')).pack(pady=(0, 10))
        
        # Format selection
        ttk.Label(master, text="Select format:").pack(anchor=tk.W)
        self.format_var = tk.StringVar(value="TXT")
        
        format_frame = ttk.Frame(master)
        format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(format_frame, text="Text (TXT)", variable=self.format_var, 
                       value="TXT").pack(side=tk.LEFT, padx=(0, 20))
        
        if PDF_AVAILABLE:
            ttk.Radiobutton(format_frame, text="PDF", variable=self.format_var, 
                           value="PDF").pack(side=tk.LEFT)
        
        # Specific options for participant reports
        if self.report_type == "PARTICIPANT_LIST":
            ttk.Label(master, text="Options:").pack(anchor=tk.W, pady=(20, 5))
            
            self.specific_trip_var = tk.BooleanVar()
            ttk.Checkbutton(master, text="Generate for specific trip only", 
                           variable=self.specific_trip_var,
                           command=self.toggle_trip_selection).pack(anchor=tk.W)
            
            self.trip_selection_frame = ttk.Frame(master)
            self.trip_selection_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(self.trip_selection_frame, text="Select trip:").pack(side=tk.LEFT)
            self.trip_var = tk.StringVar()
            self.trip_combo = ttk.Combobox(self.trip_selection_frame, textvariable=self.trip_var, 
                                          state="disabled", width=40)
            self.trip_combo.pack(side=tk.LEFT, padx=(5, 0))
            
            self.load_trips_for_selection()
        
        return None
    
    def toggle_trip_selection(self):
        """Toggle trip selection availability"""
        if self.specific_trip_var.get():
            self.trip_combo.config(state="readonly")
        else:
            self.trip_combo.config(state="disabled")
    
    def load_trips_for_selection(self):
        """Load trips for selection"""
        def get_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT id, trip_name FROM trips ORDER BY trip_name')
            return cursor.fetchall()
        
        trips = safe_db_operation(get_trips_operation)
        
        if trips:
            trip_list = [f"{trip[0]} - {trip[1]}" for trip in trips]
            self.trip_combo['values'] = trip_list
    
    def apply(self):
        """Generate the report"""
        try:
            # Determine trip ID for participant reports
            trip_id = None
            if (self.report_type == "PARTICIPANT_LIST" and 
                hasattr(self, 'specific_trip_var') and 
                self.specific_trip_var.get()):
                
                trip_selection = self.trip_var.get()
                if trip_selection:
                    trip_id = int(trip_selection.split(' - ')[0])
            
            format_type = self.format_var.get()
            parent_widget = getattr(self, "parent", None) or self.log_widget

            def log_async(message):
                if parent_widget:
                    try:
                        parent_widget.after(0, lambda m=message: self.log_message(m))
                    except Exception as e:
                        logger.debug(f"Failed to schedule async log message: {e}")
                else:
                    self.log_message(message)

            if not TRIP_REPORTS_AVAILABLE or TripReportGenerator is None:
                log_async("Trip report generator module is not available in this environment.")
                messagebox.showerror("Reports Unavailable",
                                     "Trip report generation support is not installed.")
                return

            if not self.auth or not self.auth.current_user:
                log_async("You must be logged in to generate reports.")
                messagebox.showerror("Authentication Required",
                                     "You must be logged in to generate reports.")
                return

            if not self.auth.check_permission('view_trip_reports'):
                log_async("You do not have permission to generate reports.")
                messagebox.showerror("Permission Denied",
                                     "You do not have permission to generate trip reports.")
                return

            if (self.report_type == "FINANCIAL_REPORT"
                    and not self.auth.check_permission('view_financial_reports')):
                log_async("Financial reports require additional permissions.")
                messagebox.showerror("Permission Denied",
                                     "You do not have permission to generate financial reports.")
                return

            log_async("Starting report generation...")

            def generate_report_thread():
                def show_viewer(report_content, report_data):
                    if parent_widget:
                        try:
                            parent_widget.after(0, lambda: ReportViewerDialog(
                                parent_widget,
                                self.auth,
                                report_content,
                                report_data,
                                self.report_type
                            ))
                        except Exception as e:
                            logger.debug(f"Failed to show report preview dialog: {e}")

                def notify_error(message):
                    if parent_widget:
                        try:
                            parent_widget.after(0, lambda: messagebox.showerror("Report Error", message))
                        except Exception as e:
                            logger.debug(f"Failed to show error dialog: {e}")

                def log_message(message):
                    if parent_widget:
                        try:
                            parent_widget.after(0, lambda m=message: self.log_message(m))
                        except Exception as e:
                            logger.debug(f"Failed to schedule async log message: {e}")

                try:
                    report_generator = TripReportGenerator(self.auth)

                    def generate_operation(conn):
                        # Get report data
                        if self.report_type == "TRIP_SUMMARY":
                            data = report_generator.get_trip_summary_data(conn)
                        elif self.report_type == "PARTICIPANT_LIST":
                            data = report_generator.get_participant_report_data(conn, trip_id)
                        elif self.report_type == "FINANCIAL_REPORT":
                            data = report_generator.get_financial_report_data(conn)
                        else:
                            raise ValueError(f"Unknown report type: {self.report_type}")

                        # Generate report content as string for viewing
                        report_content = report_generator.generate_report_content_as_string(
                            data, self.report_type
                        )

                        return report_content, data

                    result = safe_db_operation(generate_operation)

                    if not result:
                        log_message("✗ Failed to generate report.")
                        notify_error("Report generation failed. Please check the logs for details.")
                        return

                    report_content, report_data = result
                    log_message(f"✓ Report generated successfully")

                    # Show report viewer dialog
                    show_viewer(report_content, report_data)

                except Exception as e:
                    error_msg = f"Error generating report: {e}"
                    logging.error(error_msg)
                    log_message(f"✗ {error_msg}")
                    notify_error(error_msg)
            
            # Run in background thread
            Thread(target=generate_report_thread, daemon=True).start()
            
        except Exception as e:
            error_msg = f"Error starting report generation: {e}"
            self.log_message(f"✗ {error_msg}")
            messagebox.showerror("Error", error_msg)
    
    def log_message(self, message):
        """Log message to the report log widget"""
        if self.log_widget:
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.log_widget.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_widget.see(tk.END)
            self.log_widget.update_idletasks()


class ReportViewerDialog(tk.Toplevel):
    """Dialog to view and export trip reports"""

    def __init__(self, parent, auth, report_content, report_data, report_type):
        super().__init__(parent)
        self.auth = auth
        self.report_content = report_content
        self.report_data = report_data
        self.report_type = report_type

        self.title(f"{report_type.replace('_', ' ').title()} Report")
        self.geometry("900x700")

        # Make dialog modal
        self.transient(parent)
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
                 text=f"{self.report_type.replace('_', ' ').title()} Report",
                 font=('Arial', 14, 'bold')).pack()

        ttk.Label(header_frame,
                 text=f"Generated: {self.report_data['generated_at']} by {self.report_data['generated_by']}",
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

        # Export buttons
        ttk.Button(button_frame, text="Export as TXT", command=self.export_as_txt).pack(side=tk.LEFT, padx=5)

        if PDF_AVAILABLE:
            ttk.Button(button_frame, text="Export as PDF", command=self.export_as_pdf).pack(side=tk.LEFT, padx=5)

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
                initialfile=f"{self.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.report_content)

                messagebox.showinfo("Success", f"Report exported successfully to:\n{filename}")
                logging.info(f"Report exported as TXT: {filename}")

        except Exception as e:
            error_msg = f"Error exporting report as TXT: {e}"
            logging.error(error_msg)
            messagebox.showerror("Export Error", error_msg)

    def export_as_pdf(self):
        """Export report as PDF file"""
        if not PDF_AVAILABLE:
            messagebox.showerror("PDF Not Available",
                               "PDF export is not available. ReportLab library is required.")
            return

        try:
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"{self.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )

            if filename:
                # Generate PDF using TripReportGenerator
                report_generator = TripReportGenerator(self.auth)
                report_generator.generate_pdf_report(self.report_data, self.report_type, filename)

                messagebox.showinfo("Success", f"Report exported successfully to:\n{filename}")
                logging.info(f"Report exported as PDF: {filename}")

        except Exception as e:
            error_msg = f"Error exporting report as PDF: {e}"
            logging.error(error_msg)
            messagebox.showerror("Export Error", error_msg)

    def send_to_admin(self):
        """Send report to admin users via email"""
        if not EMAIL_SERVICE_AVAILABLE:
            messagebox.showerror("Email Not Available",
                               "Email service is not available. Please contact support.")
            return

        try:
            # Get admin emails
            report_generator = TripReportGenerator(self.auth)
            admins = report_generator.get_admin_emails()

            if not admins:
                messagebox.showerror("No Admins Found",
                                   "No admin users with email addresses found.")
                return

            # Create admin selection dialog
            admin_dialog = tk.Toplevel(self)
            admin_dialog.title("Select Admin Recipients")
            admin_dialog.geometry("400x300")
            admin_dialog.transient(self)
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
                            # Try to use template first, fall back to hardcoded email
                            try:
                                if TEMPLATE_AVAILABLE:
                                    subject, body = render_template('trip_management_report', {
                                        'admin_name': admin['name'],
                                        'report_title': self.report_type.replace('_', ' ').title(),
                                        'generated_at': self.report_data['generated_at'],
                                        'report_content': self.report_content,
                                        'separator': '=' * 80
                                    })
                                else:
                                    raise Exception("Template not available")
                            except Exception as template_error:
                                logger.warning(f"Failed to render template: {template_error}. Using fallback email.")
                                subject = f"Trip Management Report: {self.report_type.replace('_', ' ').title()}"
                                body = f"""Dear {admin['name']},

Please find attached the {self.report_type.replace('_', ' ').title()} report.

Report Details:
- Type: {self.report_type.replace('_', ' ').title()}
- Generated: {self.report_data['generated_at']}
- Generated by: {self.report_data['generated_by']}

This is an automatically generated report from the Trip Management System.

Best regards,
Trip Management System
"""

                            # Create temporary file for attachment
                            from university_system.modules.shared.constants.paths import TEMP_DIR
                            temp_file = TEMP_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
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
                            except Exception as e:
                                logger.debug(f"Failed to delete temporary file {temp_file}: {e}")

                            success_count += 1
                            logging.info(f"Report sent to {admin['email']}")

                        except Exception as e:
                            logging.error(f"Error sending email to {admin['email']}: {e}")

                    # Show result
                    self.after(0, lambda: messagebox.showinfo(
                        "Email Sent",
                        f"Report sent successfully to {success_count} of {len(selected_admins)} admin(s)."
                    ))

                Thread(target=send_email_thread, daemon=True).start()

            ttk.Button(button_frame, text="Send", command=send_emails).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=admin_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            error_msg = f"Error sending report to admin: {e}"
            logging.error(error_msg)
            messagebox.showerror("Email Error", error_msg)


class AddExpenseDialog(Dialog):
    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = trip_id
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Add Expense")
    
    def body(self, master):
        """Create the dialog body"""
        # Category selection
        ttk.Label(master, text="Category:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.category_var = tk.StringVar()
        categories = ['Transportation', 'Accommodation', 'Food', 'Activities', 'Equipment', 'Insurance', 'Miscellaneous']
        self.category_combo = ttk.Combobox(master, textvariable=self.category_var, values=categories, state="readonly")
        self.category_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W+tk.E)

        # Description
        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.description_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.description_var, width=40).grid(row=1, column=1, padx=5, pady=5)

        # Amount
        ttk.Label(master, text="Amount (£):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.amount_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.amount_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # Date
        ttk.Label(master, text="Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(master, textvariable=self.date_var, width=40).grid(row=3, column=1, padx=5, pady=5)

        return self.category_combo  # Return widget, not StringVar
    
    def validate(self):
        """Validate expense data"""
        if not self.category_var.get():
            messagebox.showerror("Validation Error", "Please select a category.")
            return False
        
        if not self.description_var.get().strip():
            messagebox.showerror("Validation Error", "Description is required.")
            return False
        
        try:
            amount = float(self.amount_var.get())
            if amount < 0:
                messagebox.showerror("Validation Error", "Amount cannot be negative.")
                return False
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid amount.")
            return False
        
        try:
            datetime.strptime(self.date_var.get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid date (YYYY-MM-DD).")
            return False
        
        return True
    
    def apply(self):
        """Add the expense"""
        def add_expense_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO trip_expenses (trip_id, category, description, amount, date, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.trip_id,
                self.category_var.get(),
                self.description_var.get().strip(),
                float(self.amount_var.get()),
                self.date_var.get(),
                self.auth.current_user['id']
            ))
            return True
        
        
        if safe_db_operation(add_expense_operation):
            messagebox.showinfo("Success", "Expense added successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to add expense.")


class EditExpenseDialog(Dialog):
    def __init__(self, parent, expense_id, refresh_callback):
        self.expense_id = expense_id
        self.refresh_callback = refresh_callback
        self.expense_data = None
        
        # Load expense data
        self.load_expense_data()
        
        super().__init__(parent, "Edit Expense")
    
    def load_expense_data(self):
        """Load existing expense data"""
        def get_expense_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trip_expenses WHERE id = ?', (self.expense_id,))
            return cursor.fetchone()
        
        self.expense_data = safe_db_operation(get_expense_operation)
    
    def body(self, master):
        """Create the dialog body"""
        if not self.expense_data:
            ttk.Label(master, text="Expense not found.").pack(pady=20)
            return None
        
        expense = self.expense_data
        
        # Description
        ttk.Label(master, text="Description:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.description_var = tk.StringVar(value=expense[3])
        ttk.Entry(master, textvariable=self.description_var, width=40).grid(row=0, column=1, padx=5, pady=5)
        
        # Amount
        ttk.Label(master, text="Amount (£):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.amount_var = tk.StringVar(value=str(expense[4]))
        ttk.Entry(master, textvariable=self.amount_var, width=40).grid(row=1, column=1, padx=5, pady=5)
        
        # Date
        ttk.Label(master, text="Date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_var = tk.StringVar(value=expense[5])
        ttk.Entry(master, textvariable=self.date_var, width=40).grid(row=2, column=1, padx=5, pady=5)
        
        return self.description_var
    
    def validate(self):
        """Validate expense data"""
        if not self.description_var.get().strip():
            messagebox.showerror("Validation Error", "Description is required.")
            return False
        
        try:
            amount = float(self.amount_var.get())
            if amount < 0:
                messagebox.showerror("Validation Error", "Amount cannot be negative.")
                return False
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid amount.")
            return False
        
        try:
            datetime.strptime(self.date_var.get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid date (YYYY-MM-DD).")
            return False
        
        return True
    
    def apply(self):
        """Update the expense"""
        def update_expense_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE trip_expenses SET description = ?, amount = ?, date = ?
            WHERE id = ?
            ''', (
                self.description_var.get().strip(),
                float(self.amount_var.get()),
                self.date_var.get(),
                self.expense_id
            ))
            return True
        
        
        if safe_db_operation(update_expense_operation):
            messagebox.showinfo("Success", "Expense updated successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to update expense.")


class AssignStaffDialog(Dialog):
    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = trip_id
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Assign Staff to Trip")
    
    def body(self, master):
        """Create the dialog body"""
        # Available staff
        ttk.Label(master, text="Available Staff:").pack(anchor=tk.W)
        
        self.staff_listbox = tk.Listbox(master, width=60, height=10)
        self.staff_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Role selection
        ttk.Label(master, text="Role:").pack(anchor=tk.W)
        self.role_var = tk.StringVar(value="supervisor")
        
        role_frame = ttk.Frame(master)
        role_frame.pack(fill=tk.X, pady=5)
        
        roles = ['supervisor', 'coordinator', 'medical', 'transport']
        for role in roles:
            ttk.Radiobutton(role_frame, text=role.title(), variable=self.role_var, 
                           value=role).pack(side=tk.LEFT, padx=(0, 20))
        
        # Load available staff
        self.load_available_staff()
        
        return self.staff_listbox
    
    def load_available_staff(self):
        """Load available staff members"""
        def get_available_staff_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT u.id, u.first_name, u.last_name, u.username, r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE r.role_name IN ('admin', 'staff', 'instructor')
            AND u.id NOT IN (
                SELECT staff_user_id FROM trip_staff WHERE trip_id = ?
            )
            ORDER BY r.role_name, u.last_name
            ''', (self.trip_id,))
            
            return cursor.fetchall()
        
        staff = safe_db_operation(get_available_staff_operation)
        
        if staff:
            for staff_member in staff:
                user_id, first_name, last_name, username, role = staff_member
                display_text = f"{user_id}: {first_name} {last_name} ({username}) - {role.title()}"
                self.staff_listbox.insert(tk.END, display_text)
    
    def validate(self):
        """Validate staff selection"""
        selection = self.staff_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member.")
            return False
        return True
    
    def apply(self):
        """Assign the staff member"""
        selection = self.staff_listbox.curselection()
        if not selection:
            return
        
        # Extract staff ID from selection
        selected_text = self.staff_listbox.get(selection[0])
        staff_id = int(selected_text.split(':')[0])
        
        def assign_staff_operation(conn):
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO trip_staff (trip_id, staff_user_id, role, assigned_date)
            VALUES (?, ?, ?, ?)
            ''', (self.trip_id, staff_id, self.role_var.get(), timestamp))
            
            return True
        
        
        try:
            if safe_db_operation(assign_staff_operation):
                messagebox.showinfo("Success", "Staff member assigned successfully!")
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error", "Failed to assign staff member.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Staff member is already assigned to this trip.")


class ItineraryDialog(Dialog):
    def __init__(self, parent, auth, trip_id):
        self.auth = auth
        self.trip_id = trip_id
        self.trip_info = None
        
        # Load trip info
        self.load_trip_info()
        
        super().__init__(parent, "Manage Itinerary")
    
    def load_trip_info(self):
        """Load trip information"""
        def get_trip_info_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT trip_name, start_date, end_date 
            FROM trips WHERE id = ?
            ''', (self.trip_id,))
            
            return cursor.fetchone()
        
        self.trip_info = safe_db_operation(get_trip_info_operation)
    
    def body(self, master):
        """Create the dialog body"""
        if not self.trip_info:
            ttk.Label(master, text="Trip not found.").pack(pady=20)
            return None
        
        trip_name, start_date, end_date = self.trip_info
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        trip_days = (end_date_obj - start_date_obj).days + 1
        
        # Trip info
        info_frame = ttk.LabelFrame(master, text="Trip Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Trip: {trip_name}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Duration: {trip_days} days ({start_date} to {end_date})").pack(anchor=tk.W)
        
        # Existing itinerary
        existing_frame = ttk.LabelFrame(master, text="Existing Itinerary", padding=10)
        existing_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.itinerary_tree = ttk.Treeview(existing_frame, columns=('day', 'activity', 'location', 'time'), show='headings', height=10)
        
        self.itinerary_tree.heading('day', text='Day')
        self.itinerary_tree.heading('activity', text='Activity')
        self.itinerary_tree.heading('location', text='Location')
        self.itinerary_tree.heading('time', text='Time')
        
        self.itinerary_tree.column('day', width=50)
        self.itinerary_tree.column('activity', width=200)
        self.itinerary_tree.column('location', width=150)
        self.itinerary_tree.column('time', width=100)
        
        self.itinerary_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Buttons
        buttons_frame = ttk.Frame(existing_frame)
        buttons_frame.pack(fill=tk.X)
        
        ttk.Button(buttons_frame, text="Add Item", command=self.add_itinerary_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Edit Item", command=self.edit_itinerary_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Delete Item", command=self.delete_itinerary_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Refresh", command=self.load_itinerary).pack(side=tk.LEFT, padx=5)
        
        # Load existing itinerary
        self.load_itinerary()
        
        return None
    
    def load_itinerary(self):
        """Load existing itinerary items"""
        # Clear existing items
        for item in self.itinerary_tree.get_children():
            self.itinerary_tree.delete(item)
        
        def get_itinerary_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, day_number, activity, location, start_time, end_time, notes
            FROM trip_itinerary
            WHERE trip_id = ?
            ORDER BY day_number, start_time
            ''', (self.trip_id,))
            
            return cursor.fetchall()
        
        items = safe_db_operation(get_itinerary_operation)
        
        if items:
            for item in items:
                item_id, day, activity, location, start_time, end_time, notes = item
                
                # Format time information
                if start_time and end_time:
                    time_info = f"{start_time}-{end_time}"
                elif start_time:
                    time_info = f"from {start_time}"
                else:
                    time_info = "All day"
                
                location_info = location if location else ""
                
                self.itinerary_tree.insert('', 'end', text=str(item_id), values=(
                    f"Day {day}", activity, location_info, time_info
                ))
    
    def add_itinerary_item(self):
        """Add new itinerary item"""
        if not self.trip_info:
            return
        
        trip_name, start_date, end_date = self.trip_info
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        trip_days = (end_date_obj - start_date_obj).days + 1
        
        AddItineraryItemDialog(self.parent, self.trip_id, trip_days, self.load_itinerary)
    
    def edit_itinerary_item(self):
        """Edit selected itinerary item"""
        selection = self.itinerary_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an itinerary item.")
            return
        
        item_id = self.itinerary_tree.item(selection[0])['text']
        EditItineraryItemDialog(self.parent, item_id, self.load_itinerary)
    
    def delete_itinerary_item(self):
        """Delete selected itinerary item"""
        selection = self.itinerary_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an itinerary item.")
            return
        
        item_id = self.itinerary_tree.item(selection[0])['text']
        activity = self.itinerary_tree.item(selection[0])['values'][1]
        
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete '{activity}'?"):
            def delete_item_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_itinerary WHERE id = ?', (item_id,))
                return True
            
                
            if safe_db_operation(delete_item_operation):
                messagebox.showinfo("Success", "Itinerary item deleted successfully!")
                self.load_itinerary()
            else:
                messagebox.showerror("Error", "Failed to delete itinerary item.")
    
    def buttonbox(self):
        """Create button box"""
        box = ttk.Frame(self)
        ttk.Button(box, text="Close", command=self.ok).pack(side=tk.RIGHT, padx=5)
        box.pack(pady=5)


class AddItineraryItemDialog(Dialog):
    def __init__(self, parent, trip_id, trip_days, refresh_callback):
        self.trip_id = trip_id
        self.trip_days = trip_days
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Add Itinerary Item")
    
    def body(self, master):
        """Create the dialog body"""
        # Day number
        ttk.Label(master, text=f"Day number (1-{self.trip_days}):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.day_var = tk.StringVar(value="1")
        day_combo = ttk.Combobox(master, textvariable=self.day_var, 
                                values=[str(i) for i in range(1, self.trip_days + 1)], 
                                state="readonly", width=37)
        day_combo.grid(row=0, column=1, padx=5, pady=5)
        
        # Activity
        ttk.Label(master, text="Activity description:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.activity_var = tk.StringVar()
        self.activity_entry = ttk.Entry(master, textvariable=self.activity_var, width=40)
        self.activity_entry.grid(row=1, column=1, padx=5, pady=5)

        # Location
        ttk.Label(master, text="Location (optional):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.location_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # Start time
        ttk.Label(master, text="Start time (HH:MM, optional):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_time_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.start_time_var, width=40).grid(row=3, column=1, padx=5, pady=5)

        # End time
        ttk.Label(master, text="End time (HH:MM, optional):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_time_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.end_time_var, width=40).grid(row=4, column=1, padx=5, pady=5)

        # Notes
        ttk.Label(master, text="Notes (optional):").grid(row=5, column=0, sticky=tk.NW, padx=5, pady=5)
        self.notes_text = tk.Text(master, width=40, height=3)
        self.notes_text.grid(row=5, column=1, padx=5, pady=5)

        return self.activity_entry  # Return widget, not StringVar
    
    def validate(self):
        """Validate itinerary item data"""
        if not self.activity_var.get().strip():
            messagebox.showerror("Validation Error", "Activity description is required.")
            return False
        
        # Validate time formats if provided
        for time_var, label in [(self.start_time_var, "start time"), (self.end_time_var, "end time")]:
            time_value = time_var.get().strip()
            if time_value:
                try:
                    datetime.strptime(time_value, '%H:%M')
                except ValueError:
                    messagebox.showerror("Validation Error", f"Invalid {label} format. Please use HH:MM.")
                    return False
        
        return True
    
    def apply(self):
        """Add the itinerary item"""
        def add_item_operation(conn):
            cursor = conn.cursor()
            
            start_time = self.start_time_var.get().strip() or None
            end_time = self.end_time_var.get().strip() or None
            location = self.location_var.get().strip() or None
            notes = self.notes_text.get(1.0, tk.END).strip() or None
            
            cursor.execute('''
            INSERT INTO trip_itinerary (
                trip_id, day_number, activity, location, 
                start_time, end_time, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.trip_id,
                int(self.day_var.get()),
                self.activity_var.get().strip(),
                location,
                start_time,
                end_time,
                notes
            ))
            
            return True
        
        
        try:
            if safe_db_operation(add_item_operation):
                messagebox.showinfo("Success", "Itinerary item added successfully!")
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error", "Failed to add itinerary item.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Conflicting itinerary item (same day and time). Please use different time.")


class EditItineraryItemDialog(Dialog):
    def __init__(self, parent, item_id, refresh_callback):
        self.item_id = item_id
        self.refresh_callback = refresh_callback
        self.item_data = None
        
        # Load item data
        self.load_item_data()
        
        super().__init__(parent, "Edit Itinerary Item")
    
    def load_item_data(self):
        """Load existing item data"""
        def get_item_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trip_itinerary WHERE id = ?', (self.item_id,))
            return cursor.fetchone()
        
        self.item_data = safe_db_operation(get_item_operation)
    
    def body(self, master):
        """Create the dialog body"""
        if not self.item_data:
            ttk.Label(master, text="Itinerary item not found.").pack(pady=20)
            return None
        
        item = self.item_data
        
        # Activity
        ttk.Label(master, text="Activity description:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.activity_var = tk.StringVar(value=item[3])
        ttk.Entry(master, textvariable=self.activity_var, width=40).grid(row=0, column=1, padx=5, pady=5)
        
        # Location
        ttk.Label(master, text="Location (optional):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.location_var = tk.StringVar(value=item[4] or "")
        ttk.Entry(master, textvariable=self.location_var, width=40).grid(row=1, column=1, padx=5, pady=5)
        
        # Start time
        ttk.Label(master, text="Start time (HH:MM, optional):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_time_var = tk.StringVar(value=item[5] or "")
        ttk.Entry(master, textvariable=self.start_time_var, width=40).grid(row=2, column=1, padx=5, pady=5)
        
        # End time
        ttk.Label(master, text="End time (HH:MM, optional):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_time_var = tk.StringVar(value=item[6] or "")
        ttk.Entry(master, textvariable=self.end_time_var, width=40).grid(row=3, column=1, padx=5, pady=5)
        
        # Notes
        ttk.Label(master, text="Notes (optional):").grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        self.notes_text = tk.Text(master, width=40, height=3)
        self.notes_text.insert(1.0, item[7] or "")
        self.notes_text.grid(row=4, column=1, padx=5, pady=5)
        
        return self.activity_var
    
    def validate(self):
        """Validate itinerary item data"""
        if not self.activity_var.get().strip():
            messagebox.showerror("Validation Error", "Activity description is required.")
            return False
        
        # Validate time formats if provided
        for time_var, label in [(self.start_time_var, "start time"), (self.end_time_var, "end time")]:
            time_value = time_var.get().strip()
            if time_value:
                try:
                    datetime.strptime(time_value, '%H:%M')
                except ValueError:
                    messagebox.showerror("Validation Error", f"Invalid {label} format. Please use HH:MM.")
                    return False
        
        return True
    
    def apply(self):
        """Update the itinerary item"""
        def update_item_operation(conn):
            cursor = conn.cursor()
            
            start_time = self.start_time_var.get().strip() or None
            end_time = self.end_time_var.get().strip() or None
            location = self.location_var.get().strip() or None
            notes = self.notes_text.get(1.0, tk.END).strip() or None
            
            cursor.execute('''
            UPDATE trip_itinerary SET 
                activity = ?, location = ?, start_time = ?, end_time = ?, notes = ?
            WHERE id = ?
            ''', (
                self.activity_var.get().strip(),
                location,
                start_time,
                end_time,
                notes,
                self.item_id
            ))
            
            return True
        
        
        if safe_db_operation(update_item_operation):
            messagebox.showinfo("Success", "Itinerary item updated successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to update itinerary item.")


class CreateCalendarEventDialog(Dialog):
    def __init__(self, parent, auth, calendar_manager, refresh_callback):
        self.auth = auth
        self.calendar_manager = calendar_manager
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Create Calendar Event for Trip")
    
    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text="Select trip to create calendar event:").pack(anchor=tk.W, pady=(0, 10))
        
        # Trip selection
        self.trip_listbox = tk.Listbox(master, width=60, height=12)
        self.trip_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Load trips without calendar events
        self.load_trips_without_events()
        
        return self.trip_listbox
    
    def load_trips_without_events(self):
        """Load trips that don't have calendar events"""
        def get_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
            FROM trips t
            LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
            WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open')
            ORDER BY t.start_date
            ''')
            
            return cursor.fetchall()
        
        trips = safe_db_operation(get_trips_operation)
        
        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, end_date, status = trip
                display_text = f"{trip_id}: {name} to {destination} ({start_date} - {end_date}) [{status.title()}]"
                self.trip_listbox.insert(tk.END, display_text)
        else:
            self.trip_listbox.insert(tk.END, "No trips available for calendar event creation")
    
    def validate(self):
        """Validate trip selection"""
        selection = self.trip_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip.")
            return False
        
        selected_text = self.trip_listbox.get(selection[0])
        if "No trips available" in selected_text:
            messagebox.showwarning("No Trips", "No trips available for calendar event creation.")
            return False
        
        return True
    
    def apply(self):
        """Create the calendar event"""
        selection = self.trip_listbox.curselection()
        if not selection:
            return
        
        # Extract trip ID from selection
        selected_text = self.trip_listbox.get(selection[0])
        trip_id = int(selected_text.split(':')[0])
        
        try:
            # Create calendar event using the calendar manager
            result = self.calendar_manager.create_trip_event(trip_id)
            
            if result['success']:
                messagebox.showinfo("Success", f"✓ Calendar event created successfully!\nEvent ID: {result['event_id']}")
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error", f"✗ Failed to create calendar event: {result['message']}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error creating calendar event: {e}")


class ExportDataDialog(Dialog):
    def __init__(self, parent, auth):
        self.auth = auth
        super().__init__(parent, "Export Trip Data")
    
    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text="Select data to export:", font=('Arial', 10, 'bold')).pack(pady=(0, 10))
        
        # Export options
        self.export_trips_var = tk.BooleanVar(value=True)
        self.export_participants_var = tk.BooleanVar(value=True)
        self.export_expenses_var = tk.BooleanVar()
        self.export_staff_var = tk.BooleanVar()
        
        ttk.Checkbutton(master, text="Trip Information", variable=self.export_trips_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(master, text="Participant Data", variable=self.export_participants_var).pack(anchor=tk.W, pady=2)
        
        if self.auth.check_permission('view_financial_reports'):
            ttk.Checkbutton(master, text="Expense Data", variable=self.export_expenses_var).pack(anchor=tk.W, pady=2)
        
        if self.auth.check_permission('manage_trips'):
            ttk.Checkbutton(master, text="Staff Assignments", variable=self.export_staff_var).pack(anchor=tk.W, pady=2)
        
        # Format selection
        ttk.Label(master, text="Export format:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(20, 5))
        
        self.format_var = tk.StringVar(value="CSV")
        ttk.Radiobutton(master, text="CSV (Comma Separated Values)", variable=self.format_var, value="CSV").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(master, text="TSV (Tab Separated Values)", variable=self.format_var, value="TSV").pack(anchor=tk.W, pady=2)
        
        return None
    
    def validate(self):
        """Validate export options"""
        if not any([self.export_trips_var.get(), self.export_participants_var.get(), 
                   self.export_expenses_var.get(), self.export_staff_var.get()]):
            messagebox.showerror("Validation Error", "Please select at least one data type to export.")
            return False
        return True
    
    def apply(self):
        """Export the data"""
        try:
            # Ask for save location
            file_extension = "csv" if self.format_var.get() == "CSV" else "tsv"
            delimiter = "," if self.format_var.get() == "CSV" else "\t"
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"trip_data_export_{timestamp}.{file_extension}"
            
            filename = filedialog.asksaveasfilename(
                defaultextension=f".{file_extension}",
                filetypes=[(f"{self.format_var.get()} files", f"*.{file_extension}"), ("All files", "*.*")],
                initialvalue=default_filename
            )
            
            if not filename:
                return
            
            # Export selected data
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                import csv
                writer = csv.writer(csvfile, delimiter=delimiter)
                
                # Export trips
                if self.export_trips_var.get():
                    self.export_trips_data(writer)
                
                # Export participants
                if self.export_participants_var.get():
                    self.export_participants_data(writer)
                
                # Export expenses
                if self.export_expenses_var.get() and self.auth.check_permission('view_financial_reports'):
                    self.export_expenses_data(writer)
                
                # Export staff
                if self.export_staff_var.get() and self.auth.check_permission('manage_trips'):
                    self.export_staff_data(writer)
            
            messagebox.showinfo("Success", f"Data exported successfully to:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {e}")
    
    def export_trips_data(self, writer):
        """Export trips data"""
        def get_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.description, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status, t.created_at, t.updated_at,
                   u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN users u ON t.created_by = u.id
            ORDER BY t.start_date
            ''')
            return cursor.fetchall()
        
        trips = safe_db_operation(get_trips_operation)
        
        if trips:
            # Write header
            writer.writerow(['=== TRIPS DATA ==='])
            writer.writerow(['Trip ID', 'Name', 'Description', 'Destination', 'Start Date', 'End Date',
                           'Max Participants', 'Cost', 'Status', 'Created At', 'Updated At', 'Created By'])
            
            # Write data
            for trip in trips:
                writer.writerow(trip)
            
            writer.writerow([])  # Empty row separator
    
    def export_participants_data(self, writer):
        """Export participants data"""
        def get_participants_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT tp.id, t.trip_name, tp.student_id,
                   s.first_name || ' ' || s.last_name as student_name,
                   s.email_address, tp.registration_date, tp.payment_status, tp.status,
                   tp.emergency_contact, tp.medical_info, tp.dietary_requirements
            FROM trip_participants tp
            JOIN trips t ON tp.trip_id = t.id
            LEFT JOIN students s ON tp.student_id = s.student_id
            ORDER BY t.trip_name, tp.registration_date
            ''')
            return cursor.fetchall()
        
        participants = safe_db_operation(get_participants_operation)
        
        if participants:
            # Write header
            writer.writerow(['=== PARTICIPANTS DATA ==='])
            writer.writerow(['Participant ID', 'Trip Name', 'Student ID', 'Student Name', 'Email',
                           'Registration Date', 'Payment Status', 'Status', 'Emergency Contact',
                           'Medical Info', 'Dietary Requirements'])
            
            # Write data
            for participant in participants:
                writer.writerow(participant)
            
            writer.writerow([])  # Empty row separator
    
    def export_expenses_data(self, writer):
        """Export expenses data"""
        def get_expenses_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT te.id, t.trip_name, te.category, te.description, te.amount, te.date,
                   u.first_name || ' ' || u.last_name as recorded_by
            FROM trip_expenses te
            JOIN trips t ON te.trip_id = t.id
            LEFT JOIN users u ON te.recorded_by = u.id
            ORDER BY t.trip_name, te.date
            ''')
            return cursor.fetchall()
        
        expenses = safe_db_operation(get_expenses_operation)
        
        if expenses:
            # Write header
            writer.writerow(['=== EXPENSES DATA ==='])
            writer.writerow(['Expense ID', 'Trip Name', 'Category', 'Description', 'Amount', 'Date', 'Recorded By'])
            
            # Write data
            for expense in expenses:
                writer.writerow(expense)
            
            writer.writerow([])  # Empty row separator
    
    def export_staff_data(self, writer):
        """Export staff assignments data"""
        def get_staff_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT ts.id, t.trip_name, u.first_name || ' ' || u.last_name as staff_name,
                   ts.role, ts.assigned_date
            FROM trip_staff ts
            JOIN trips t ON ts.trip_id = t.id
            JOIN users u ON ts.staff_user_id = u.id
            ORDER BY t.trip_name, ts.role
            ''')
            return cursor.fetchall()
        
        staff = safe_db_operation(get_staff_operation)
        
        if staff:
            # Write header
            writer.writerow(['=== STAFF ASSIGNMENTS DATA ==='])
            writer.writerow(['Assignment ID', 'Trip Name', 'Staff Name', 'Role', 'Assigned Date'])
            
            # Write data
            for assignment in staff:
                writer.writerow(assignment)


class AboutDialog(Dialog):
    def __init__(self, parent):
        super().__init__(parent, "About Trip Management System")
    
    def body(self, master):
        """Create the dialog body"""
        # Logo/Icon placeholder
        ttk.Label(master, text="🎒", font=('Arial', 48)).pack(pady=10)
        
        # Title
        ttk.Label(master, text="Trip Management System", 
                 font=('Arial', 16, 'bold')).pack(pady=5)
        
        # Version info
        ttk.Label(master, text="Version 2.0 - GUI Edition").pack(pady=2)
        
        # Description
        description = """
A comprehensive system for managing educational trips and excursions.

Features:
• Trip creation and management
• Student registration and tracking
• Staff assignment and coordination
• Expense tracking and reporting
• Calendar integration
• Comprehensive reporting system

Built with backwards compatibility to the original command-line system.
        """
        
        ttk.Label(master, text=description, justify=tk.LEFT).pack(pady=20, padx=20)
        
        # Copyright
        ttk.Label(master, text="© 2024 Educational Trip Management System", 
                 font=('Arial', 8)).pack(pady=5)
        
        return None
    
    def buttonbox(self):
        """Create button box"""
        box = ttk.Frame(self)
        ttk.Button(box, text="Close", command=self.ok).pack()
        box.pack(pady=10)


# Backwards compatibility functions
def create_trip_gui(auth_instance):
    """Create and return a GUI instance - backwards compatible function"""
    return TripManagementGUI(auth_instance)

def run_trip_management_gui(auth_instance=None):
    """Run the trip management GUI - main entry point"""
    try:
        # Import original functions to ensure they're available
        from university_system.modules.domain.mobility.services import trip_management
        
        # Validate authentication
        if not auth_instance or not auth_instance.current_user:
            print("Error: Authentication required for Trip Management GUI")
            return False
        
        if not auth_instance.check_permission('view_trips'):
            print("Error: Insufficient permissions to access Trip Management")
            return False
        
        # Create and run GUI
        gui = TripManagementGUI(auth_instance)
        gui.run()
        
        return True
        
    except ImportError as e:
        print(f"Error: Missing required modules: {e}")
        return False
    except Exception as e:
        print(f"Error starting Trip Management GUI: {e}")
        logging.error(f"Trip Management GUI error: {e}")
        return False

# Integration function for backwards compatibility
def integrate_with_existing_system():
    """Integrate GUI with existing trip management system"""
    try:
        # Import original functions
        
        print("Trip Management GUI integrated successfully!")
        print("Use run_trip_management_gui(auth_instance) to start the GUI")
        
        return True
        
    except ImportError as e:
        print(f"Warning: Could not import original trip_management module: {e}")
        print("GUI will work independently but some features may be limited")
        return False

# Command-line interface compatibility
def display_trip_management_menu_gui(auth_instance):
    """GUI version of the original menu function - backwards compatible"""
    return run_trip_management_gui(auth_instance)

if __name__ == "__main__":
    # For testing purposes
    print("Trip Management GUI System")
    print("This module provides a graphical interface for the trip management system.")
    print("To use with authentication, call: run_trip_management_gui(auth_instance)")
    
    # Test integration
    integrate_with_existing_system()
