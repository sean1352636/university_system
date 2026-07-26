import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domain.pastoral.student_life.student_union.administration.student_union_core import init_student_union_db
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
    """Open Student Union Events Calendar showing all union_events from the database"""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection

        cal_win = tk.Toplevel(self.root)
        cal_win.title("Student Union Events Calendar")
        cal_win.geometry("1050x550")
        cal_win.transient(self.root)
        cal_win.grab_set()

        header = tk.Label(
            cal_win, text="Student Union Events Calendar",
            font=("Helvetica", 16, "bold"), pady=10
        )
        header.pack(fill=tk.X)

        columns = (
            "event_name", "event_date", "start_time", "end_time",
            "location", "organizer", "status", "attendees"
        )
        col_headings = {
            "event_name": "Event Name",
            "event_date": "Date",
            "start_time": "Start Time",
            "end_time": "End Time",
            "location": "Location",
            "organizer": "Organizer",
            "status": "Status",
            "attendees": "Attendees",
        }

        tree_frame = tk.Frame(cal_win)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings",
            yscrollcommand=vsb.set, xscrollcommand=hsb.set
        )
        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)

        for col in columns:
            tree.heading(col, text=col_headings[col])
            tree.column(col, width=120, minwidth=80)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        def refresh_events():
            for item in tree.get_children():
                tree.delete(item)
            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT event_name, event_date, start_time, end_time, "
                    "location, organizer_id, status, current_attendees "
                    "FROM union_events ORDER BY event_date DESC"
                )
                rows = cursor.fetchall()
                # Try to resolve organizer names from student_clubs
                organizer_map = {}
                try:
                    cursor.execute("SELECT club_id, club_name FROM student_clubs")
                    for cid, cname in cursor.fetchall():
                        organizer_map[cid] = cname
                except Exception:
                    pass
                for row in rows:
                    organizer_name = organizer_map.get(row[5], str(row[5]) if row[5] else "")
                    tree.insert("", tk.END, values=(
                        row[0], row[1], row[2] or "", row[3] or "",
                        row[4] or "", organizer_name,
                        row[6] or "", row[7] if row[7] is not None else ""
                    ))
                if not rows:
                    tree.insert("", tk.END, values=("No events found", "", "", "", "", "", "", ""))
            except Exception as e:
                messagebox.showerror("Database Error", f"Could not load events: {e}", parent=cal_win)
            finally:
                if conn:
                    conn.close()

        btn_frame = tk.Frame(cal_win)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Refresh", command=refresh_events).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=cal_win.destroy).pack(side=tk.RIGHT, padx=5)

        refresh_events()

    except Exception as e:
        messagebox.showerror("Error", f"Could not open events calendar: {e}")


def _add_club_events_to_calendar(self, calendar_gui, club_name=None):
    """Add club events to calendar"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        # Check if student_events table exists
        if club_name:
            # Get events for specific club
            cursor.execute('''
                SELECT title AS event_name, start_datetime AS event_date, description AS event_description, location AS event_location
                FROM unified_events ue
                JOIN student_clubs sc ON ue.club_id = sc.club_id
                WHERE ue.source_type = 'student'
                AND sc.club_name = ?
            ''', (club_name,))
        else:
            # Get all student union events
            cursor.execute('''
                SELECT title AS event_name, start_datetime AS event_date, description AS event_description, location AS event_location
                FROM unified_events
                WHERE source_type = 'student'
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
        from education_system.systems.university.interfaces.gui.operations.commerce.shop_management_gui.main_gui import UniversityShopGUI
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
        from education_system.systems.university.interfaces.gui.operations.commerce.shop_management_gui.main_gui import UniversityShopGUI
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
        from education_system.systems.university.interfaces.gui.operations.commerce.restaurant_management_gui import RestaurantManagementGUI
        # Pass parent root — show_restaurant_management() creates its own Toplevel
        restaurant_gui = RestaurantManagementGUI(self.root, auth=self.auth_manager)
        restaurant_gui.show_restaurant_management()
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
        from education_system.systems.university.interfaces.gui.operations.campus.mobility.trip_management_gui import TripManagementGUI
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
        from education_system.systems.university.interfaces.gui.operations.campus.mobility.trip_management_gui import TripManagementGUI
        trip_window = tk.Toplevel(self.root)
        trip_window.title(f"Trip Management - {club_name}")
        trip_window.geometry("1200x800")
        # TripManagementGUI uses auth_instance and root parameters
        trip_gui = TripManagementGUI(auth_instance=self.auth_manager, root=trip_window)
    except ImportError:
        messagebox.showerror("Error", "Trip management system is not available")
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not open trip management: {e}")


