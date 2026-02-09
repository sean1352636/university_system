import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

def show_club_selection_for_merchandise(self):
    """Show dialog to select club for merchandise shopping"""
    try:
        # Get all active clubs
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT club_name FROM student_clubs WHERE status = "active" ORDER BY club_name')
        clubs = [row[0] for row in cursor.fetchall()]
        conn.close()
        if not clubs:
            messagebox.showinfo("No Clubs", "No active clubs found")
            return
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Club for Merchandise")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Select a club:", font=('Arial', 10, 'bold')).pack(pady=10)
        club_var = tk.StringVar()
        club_combo = ttk.Combobox(main_frame, textvariable=club_var, values=clubs, state="readonly")
        club_combo.pack(fill='x', pady=10)
        def open_merchandise_shop():
            selected_club = club_var.get()
            if selected_club:
                dialog.destroy()
                self.open_shop_for_club_merchandise(selected_club)
            else:
                messagebox.showwarning("No Selection", "Please select a club")
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="Open Shop", command=open_merchandise_shop).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not show club selection: {e}")


def show_club_selection_for_dining(self):
    """Show dialog to select club for dining reservation"""
    try:
        # Get all active clubs
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT club_name FROM student_clubs WHERE status = "active" ORDER BY club_name')
        clubs = [row[0] for row in cursor.fetchall()]
        conn.close()
        if not clubs:
            messagebox.showinfo("No Clubs", "No active clubs found")
            return
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Club for Dining Reservation")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Select a club:", font=('Arial', 10, 'bold')).pack(pady=10)
        club_var = tk.StringVar()
        club_combo = ttk.Combobox(main_frame, textvariable=club_var, values=clubs, state="readonly")
        club_combo.pack(fill='x', pady=10)
        def open_dining_booking():
            selected_club = club_var.get()
            if selected_club:
                dialog.destroy()
                self.book_club_dining_dialog(selected_club)
            else:
                messagebox.showwarning("No Selection", "Please select a club")
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="Book Dining", command=open_dining_booking).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not show club selection: {e}")


def show_club_selection_for_trips(self):
    """Show dialog to select club for trip management"""
    try:
        # Get all active clubs
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT club_name FROM student_clubs WHERE status = "active" ORDER BY club_name')
        clubs = [row[0] for row in cursor.fetchall()]
        conn.close()
        if not clubs:
            messagebox.showinfo("No Clubs", "No active clubs found")
            return
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Club for Trip Management")
        dialog.geometry("300x250")
        dialog.transient(self.root)
        dialog.grab_set()
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Select a club:", font=('Arial', 10, 'bold')).pack(pady=10)
        club_var = tk.StringVar()
        club_combo = ttk.Combobox(main_frame, textvariable=club_var, values=clubs, state="readonly")
        club_combo.pack(fill='x', pady=10)
        def create_trip():
            selected_club = club_var.get()
            if selected_club:
                dialog.destroy()
                self.create_club_trip_dialog(selected_club)
            else:
                messagebox.showwarning("No Selection", "Please select a club")
        def manage_trips():
            selected_club = club_var.get()
            if selected_club:
                dialog.destroy()
                self.open_trip_management_for_club(selected_club)
            else:
                messagebox.showwarning("No Selection", "Please select a club")
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="Create New Trip", command=create_trip).pack(pady=5)
        ttk.Button(button_frame, text="Manage Existing Trips", command=manage_trips).pack(pady=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(pady=5)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not show club selection: {e}")
# =========================================================================
# CALENDAR INTEGRATION METHODS
# =========================================================================


def open_calendar_with_club_events(self, club_name=None):
    """Open calendar GUI with club events"""
    try:
        from university_system.modules.domain.academics.gui.academic_calendar import CalendarGUI
        calendar_window = tk.Toplevel(self.root)
        calendar_window.title("Student Union Calendar" + (f" - {club_name}" if club_name else ""))
        calendar_window.geometry("900x700")
        calendar_gui = CalendarGUI(auth_manager=self.auth_manager, parent_window=calendar_window)
        # Add club events to calendar
        self._add_club_events_to_calendar(calendar_gui, club_name)
    except ImportError:
        messagebox.showerror("Error", "Calendar system is not available")
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not open calendar: {e}")


def _add_club_events_to_calendar(self, calendar_gui, club_name=None):
    """Add club events to calendar"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        # Check if student_events table exists
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='student_events'
        ''')
        table_exists = cursor.fetchone() is not None
        if not table_exists:
            # Create the table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    event_description TEXT,
                    event_location TEXT,
                    club_id INTEGER,
                    created_by INTEGER,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (club_id) REFERENCES student_clubs(club_id)
                )
            ''')
            conn.commit()
            print("Created student_events table")
        if club_name:
            # Get events for specific club
            cursor.execute('''
                SELECT event_name, event_date, event_description, event_location
                FROM student_events se
                JOIN student_clubs sc ON se.club_id = sc.club_id
                WHERE sc.club_name = ?
            ''', (club_name,))
        else:
            # Get all student union events
            cursor.execute('''
                SELECT event_name, event_date, event_description, event_location
                FROM student_events
            ''')
        events = cursor.fetchall()
        conn.close()
        # Add events to calendar
        for event_name, event_date, event_description, event_location in events:
            if hasattr(calendar_gui, 'add_student_union_event'):
                calendar_gui.add_student_union_event(
                    title=event_name,
                    date=event_date,
                    description=f"{event_description}\nLocation: {event_location}",
                    event_type="student_union"
                )
    except sqlite3.Error as e:
        print(f"Failed to add club events to calendar: {e}")
# =========================================================================
# SHOP INTEGRATION METHODS
# =========================================================================


def open_shop_gui_direct(self):
    """Open shop GUI directly without club selection dialog"""
    try:
        from university_system.modules.domain.commerce.gui.shop_management_gui.main_gui import UniversityShopGUI
        shop_window = tk.Toplevel(self.root)
        shop_window.title("University Shop Management")
        shop_window.geometry("1200x800")
        shop_gui = UniversityShopGUI(shop_window, auth=self.auth_manager)
    except ImportError:
        messagebox.showerror("Error", "Shop system is not available")
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not open shop system: {e}")


def open_shop_for_club_merchandise(self):
    """Open shop GUI with club merchandise selection page"""
    try:
        from university_system.modules.domain.commerce.gui.shop_management_gui.main_gui import UniversityShopGUI
        shop_window = tk.Toplevel(self.root)
        shop_window.title("University Shop - Club Merchandise")
        shop_window.geometry("1200x800")
        shop_gui = UniversityShopGUI(shop_window, auth=self.auth_manager)
        # Show club merchandise selection page directly
        if hasattr(shop_gui, 'show_club_merchandise_selection'):
            shop_gui.show_club_merchandise_selection()
        else:
            messagebox.showinfo("Shop Opened", "Browse the shop for club merchandise")
    except ImportError:
        messagebox.showerror("Error", "Shop system is not available")
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not open shop system: {e}")
# =========================================================================
# RESTAURANT INTEGRATION METHODS
# =========================================================================


def open_restaurant_for_club_booking(self, club_name, event_type="Club Event"):
    """Open full restaurant GUI"""
    try:
        from university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI
        restaurant_window = tk.Toplevel(self.root)
        restaurant_window.title("University Restaurant Management")
        restaurant_window.geometry("1200x800")
        # Initialize full restaurant GUI
        restaurant_gui = RestaurantManagementGUI(restaurant_window, auth=self.auth_manager)
    except ImportError:
        messagebox.showerror("Error", "Restaurant system is not available")
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not open restaurant system: {e}")
# =========================================================================
# TRIP INTEGRATION METHODS
# =========================================================================


def open_trip_gui_direct(self):
    """Open trip management GUI directly without club selection dialog"""
    try:
        from university_system.modules.domain.mobility.gui.trip_management_gui import TripManagementGUI
        trip_window = tk.Toplevel(self.root)
        trip_window.title("Trip Management")
        trip_window.geometry("1200x800")
        # TripManagementGUI uses auth_instance and root parameters
        trip_gui = TripManagementGUI(auth_instance=self.auth_manager, root=trip_window)
    except ImportError:
        messagebox.showerror("Error", "Trip management system is not available")
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not open trip management: {e}")


def create_club_trip_dialog(self, club_name):
    """Show dialog to create a new club trip"""
    try:
        from university_system.modules.domain.mobility.gui.trip_management_gui import TripManagementGUI
        trip_window = tk.Toplevel(self.root)
        trip_window.title(f"Trip Management - {club_name}")
        trip_window.geometry("1200x800")
        # TripManagementGUI uses auth_instance and root parameters
        trip_gui = TripManagementGUI(auth_instance=self.auth_manager, root=trip_window)
    except ImportError:
        messagebox.showerror("Error", "Trip management system is not available")
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not open trip management: {e}")


