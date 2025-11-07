from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
import logging
import time
import os
from datetime import datetime, timedelta
# Import logging helpers from the refactored utils module
from university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
    log_update,
    log_delete,
    log_menu_navigation,
)
import re
import traceback
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
    
# Academic calendar is optional - may not be available if dependencies missing
try:
    from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager, CalendarConfig
    CALENDAR_AVAILABLE = True
except ImportError as e:
    CALENDAR_AVAILABLE = False
    # Use debug level since this is expected when optional dependencies (numpy) are missing
    logging.debug(f"Academic calendar module not available (optional): {e}")

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

def get_db_connection(timeout=30.0, max_retries=3):
    """Get a database connection with proper timeout and retry logic"""
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(
                str(DEFAULT_DB_PATH), 
                timeout=timeout,
                check_same_thread=False
            )
            # Configure for better concurrency
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")  
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
            conn.execute("PRAGMA cache_size = 10000")
            return conn
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logging.warning(f"Database locked, retrying... (attempt {attempt + 1})")
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue
            else:
                logging.error(f"Database connection error after {attempt + 1} attempts: {e}")
                return None
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            return None

def safe_db_operation(operation_func, *args, max_retries=3, **kwargs):
    """Safely execute a database operation with retry logic"""
    retry_delay = 0.1
    last_error = None
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_db_connection(timeout=30.0)
            if not conn:
                last_error = "Failed to establish database connection"
                if attempt < max_retries - 1:
                    logging.warning(f"Database connection failed, retrying... (attempt {attempt + 1})")
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                logging.error(f"Database connection failed after {max_retries} attempts")
                return False
            
            result = operation_func(conn, *args, **kwargs)
            conn.commit()
            return result
            
        except sqlite3.OperationalError as e:
            last_error = e
            if conn:
                try:
                    conn.rollback()
                    logging.debug(f"Successfully rolled back transaction after operational error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after operational error: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Unexpected error during rollback after operational error: {type(rollback_error).__name__}: {rollback_error}")
            
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(f"Database locked, retrying in {wait_time:.2f}s... (attempt {attempt + 1})")
                time.sleep(wait_time)
                continue
            else:
                logging.error(f"Database operational error: {e}")
                return False
                
        except sqlite3.Error as e:
            last_error = e
            if conn:
                try:
                    conn.rollback()
                    logging.debug(f"Successfully rolled back transaction after database error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after database error: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Unexpected error during rollback after database error: {type(rollback_error).__name__}: {rollback_error}")
            logging.error(f"Database error: {e}")
            return False
            
        except Exception as e:
            last_error = e
            if conn:
                try:
                    conn.rollback()
                    logging.debug(f"Successfully rolled back transaction after unexpected error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after unexpected error: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Critical: Multiple errors during rollback - original: {type(e).__name__}: {e}, rollback: {type(rollback_error).__name__}: {rollback_error}")
            logging.error(f"Unexpected error: {type(e).__name__}: {e}")
            logging.debug(f"Unexpected error traceback: {traceback.format_exc()}")
            return False
            
        finally:
            if conn:
                try:
                    conn.close()
                    logging.debug(f"Database connection closed successfully")
                except sqlite3.Error as close_error:
                    logging.warning(f"SQLite error closing database connection: {close_error}")
                except Exception as close_error:
                    logging.error(f"Unexpected error closing database connection: {type(close_error).__name__}: {close_error}")
    
    logging.error(f"Operation failed after {max_retries} attempts. Last error: {type(last_error).__name__}: {last_error}")
    return False

def init_trip_db():
    """Initialize trip management database tables"""
    def create_tables(conn):
        cursor = conn.cursor()
        
        try:
            # Create trips table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_name TEXT NOT NULL,
                description TEXT,
                destination TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                max_participants INTEGER DEFAULT 50,
                cost REAL DEFAULT 0.0,
                status TEXT DEFAULT 'planning',
                created_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (created_by) REFERENCES users (id),
                CHECK (status IN ('planning', 'open', 'full', 'cancelled', 'completed'))
            )
            ''')
            
            # Create trip_participants table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                student_id TEXT,
                user_id INTEGER,
                registration_date TEXT NOT NULL,
                payment_status TEXT DEFAULT 'pending',
                emergency_contact TEXT,
                medical_info TEXT,
                dietary_requirements TEXT,
                status TEXT DEFAULT 'registered',
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE (trip_id, student_id),
                CHECK (payment_status IN ('pending', 'partial', 'paid', 'refunded')),
                CHECK (status IN ('registered', 'waitlist', 'cancelled', 'attended'))
            )
            ''')
            
            # Create trip_staff table  
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                staff_user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'supervisor',
                assigned_date TEXT NOT NULL,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (staff_user_id) REFERENCES users (id),
                UNIQUE (trip_id, staff_user_id),
                CHECK (role IN ('supervisor', 'coordinator', 'medical', 'transport'))
            )
            ''')
            
            # Create trip_expenses table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                recorded_by INTEGER,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (recorded_by) REFERENCES users (id)
            )
            ''')
            
            # Create trip_itinerary table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_itinerary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                activity TEXT NOT NULL,
                location TEXT,
                start_time TEXT,
                end_time TEXT,
                notes TEXT,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                UNIQUE (trip_id, day_number, start_time)
            )
            ''')
            
            logging.info("Trip management tables created successfully")
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Error creating trip tables: {e}")
            raise e
    
    return safe_db_operation(create_tables)

def setup_trip_permissions():
    """Setup trip management permissions"""
    try:
        # Import auth functions from the refactored authentication module
        from university_system.infrastructure.auth.user_authentication import UserAuth
        
        trip_permissions = [
            ('manage_trips', 'Manage all trip operations'),
            ('create_trips', 'Create new trips'),
            ('view_trips', 'View trip information'),
            ('register_for_trips', 'Register for trips'),
            ('view_own_trip_registrations', 'View own trip registrations'),
            ('cancel_trip_registration', 'Cancel trip registration'),
            ('manage_trip_participants', 'Manage trip participants'),
            ('view_trip_reports', 'View trip reports'),
            ('manage_trip_expenses', 'Manage trip expenses'),
            ('approve_trip_registrations', 'Approve trip registrations')
        ]
        
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        created_permissions = []
        for perm_name, perm_desc in trip_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                created_permissions.append(perm_name)
        
        # Assign permissions to roles
        role_permissions = {
            'admin': [
                'manage_trips', 'create_trips', 'view_trips', 'register_for_trips',
                'view_own_trip_registrations', 'cancel_trip_registration',
                'manage_trip_participants', 'view_trip_reports', 'manage_trip_expenses',
                'approve_trip_registrations'
            ],
            'staff': [
                'create_trips', 'view_trips', 'manage_trip_participants',
                'view_trip_reports', 'manage_trip_expenses', 'approve_trip_registrations'
            ],
            'instructor': [
                'view_trips', 'register_for_trips', 'view_own_trip_registrations',
                'cancel_trip_registration'
            ],
            'student': [
                'view_trips', 'register_for_trips', 'view_own_trip_registrations',
                'cancel_trip_registration'
            ]
        }
        
        for role_name, permissions in role_permissions.items():
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if role_result:
                role_id = role_result[0]
                
                for perm_name in permissions:
                    cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                    perm_result = cursor.fetchone()
                    if perm_result:
                        perm_id = perm_result[0]
                        cursor.execute(
                            'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                            (role_id, perm_id)
                        )
        
        conn.commit()
        conn.close()
        
        if created_permissions:
            print(f"Created trip permissions: {', '.join(created_permissions)}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error setting up trip permissions: {e}")
        return False

def view_trips_with_calendar():
    """View trips with calendar event information"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view trips.")
        return False
    
    if not auth.check_permission('view_trips'):
        print("You don't have permission to view trips.")
        return False
    
    def view_trips_calendar_operation(conn):
        cursor = conn.cursor()
        
        try:
            # Get trips with calendar event info
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(tp.id) as current_participants,
                   e.name as calendar_event_name,
                   e.id as calendar_event_id
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
            LEFT JOIN events e ON tce.event_id = e.id
            GROUP BY t.id
            ORDER BY t.start_date ASC
            ''')
            
            trips = cursor.fetchall()
            
            if not trips:
                print("No trips found.")
                return True
            
            print("\nTrips with Calendar Integration")
            print("=" * 130)
            print(f"{'ID':<5} {'Name':<20} {'Destination':<15} {'Start Date':<12} {'Participants':<12} {'Cost':<10} {'Status':<10} {'Calendar Event':<20}")
            print("-" * 130)
            
            for trip in trips:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, cal_event_name, cal_event_id = trip
                participants_info = f"{current_parts}/{max_parts}"
                calendar_info = cal_event_name[:19] if cal_event_name else "No Event"
                
                print(f"{trip_id:<5} {name[:19]:<20} {destination[:14]:<15} {start_date:<12} {participants_info:<12} £{cost:<9.2f} {status.title():<10} {calendar_info:<20}")
            
            print("=" * 130)
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Database error viewing trips with calendar: {e}")
            print("Error retrieving trips from database.")
            return False
    
    return safe_db_operation(view_trips_calendar_operation)

@log_create(module="trips", description="Creating new trip")
def create_trip():
    """Create a new trip with comprehensive validation"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create trips.")
        return False
    
    if not auth.check_permission('create_trips'):
        print("You don't have permission to create trips.")
        return False
    
    def create_trip_operation(conn):
        cursor = conn.cursor()
        
        print("\nCreate New Trip")
        print("=" * 30)
        
        # Get trip details with validation
        while True:
            trip_name = input("Trip Name: ").strip()
            if len(trip_name) >= 3:
                break
            print("Trip name must be at least 3 characters long.")
        
        description = input("Description (optional): ").strip()
        
        while True:
            destination = input("Destination: ").strip()
            if len(destination) >= 3:
                break
            print("Destination must be at least 3 characters long.")
        
        # Date validation
        while True:
            start_date_str = input("Start Date (YYYY-MM-DD): ").strip()
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                if start_date.date() <= datetime.now().date():
                    print("Start date must be in the future.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        while True:
            end_date_str = input("End Date (YYYY-MM-DD): ").strip()
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                if end_date.date() <= start_date.date():
                    print("End date must be after start date.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        # Max participants validation
        while True:
            try:
                max_participants = int(input("Maximum Participants (default 50): ") or "50")
                if max_participants > 0:
                    break
                print("Maximum participants must be greater than 0.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Cost validation
        while True:
            try:
                cost = float(input("Cost per person (default 0.0): ") or "0.0")
                if cost >= 0:
                    break
                print("Cost cannot be negative.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Status selection
        status_options = ['planning', 'open']
        print("\nTrip Status:")
        for i, status in enumerate(status_options, 1):
            print(f"{i}. {status.title()}")
        
        while True:
            try:
                status_choice = int(input("Select status (1-2): ")) - 1
                if 0 <= status_choice < len(status_options):
                    status = status_options[status_choice]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")
        
        # Insert trip
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO trips (
            trip_name, description, destination, start_date, end_date,
            max_participants, cost, status, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trip_name, description, destination, start_date_str, end_date_str,
            max_participants, cost, status, auth.current_user['id'],
            timestamp, timestamp
        ))
        
        trip_id = cursor.lastrowid
        
        print(f"\nTrip '{trip_name}' created successfully!")
        print(f"Trip ID: {trip_id}")
        print(f"Destination: {destination}")
        print(f"Dates: {start_date_str} to {end_date_str}")
        print(f"Max Participants: {max_participants}")
        print(f"Cost: £{cost:.2f}")
        print(f"Status: {status.title()}")
        
        return True
    
    return safe_db_operation(create_trip_operation)

@log_read(module="trips", description="Viewing trips")
def view_trips():
    """View trips based on user permissions"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view trips.")
        return False
    
    if not auth.check_permission('view_trips'):
        print("You don't have permission to view trips.")
        return False
    
    def view_trips_operation(conn):
        cursor = conn.cursor()
        
        try:
            # Get all trips with participant count
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
            
            if not trips:
                print("No trips found.")
                return True
            
            print("\nAll Trips")
            print("=" * 120)
            print(f"{'ID':<5} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'End Date':<12} {'Participants':<12} {'Cost':<10} {'Status':<12} {'Created By':<15}")
            print("-" * 120)
            
            for trip in trips:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, created_by = trip
                participants_info = f"{current_parts}/{max_parts}"
                
                print(f"{trip_id:<5} {name[:24]:<25} {destination[:19]:<20} {start_date:<12} {end_date:<12} {participants_info:<12} £{cost:<9.2f} {status.title():<12} {created_by[:14] if created_by else 'N/A':<15}")
            
            print("=" * 120)
            
            # Option to view detailed trip information
            while True:
                choice = input("\nEnter trip ID to view details (or 'back' to return): ").strip()
                if choice.lower() == 'back':
                    break
                
                try:
                    trip_id = int(choice)
                    view_trip_details(trip_id)
                except ValueError:
                    print("Invalid trip ID. Please enter a number.")
                except Exception as e:
                    print(f"Error viewing trip details: {e}")
            
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Database error viewing trips: {e}")
            print("Error retrieving trips from database.")
            return False
    
    return safe_db_operation(view_trips_operation)

def view_trip_details(trip_id):
    """View detailed information about a specific trip"""
    def view_details_operation(conn):
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
            print("Trip not found.")
            return False
        
        # Get participants
        cursor.execute('''
        SELECT tp.*, s.first_name || ' ' || s.last_name as student_name, s.email_address
        FROM trip_participants tp
        LEFT JOIN students s ON tp.student_id = s.student_id
        WHERE tp.trip_id = ? AND tp.status = 'registered'
        ORDER BY tp.registration_date
        ''', (trip_id,))
        
        participants = cursor.fetchall()
        
        # Get staff assigned
        cursor.execute('''
        SELECT ts.role, u.first_name || ' ' || u.last_name as staff_name
        FROM trip_staff ts
        JOIN users u ON ts.staff_user_id = u.id
        WHERE ts.trip_id = ?
        ORDER BY ts.role
        ''', (trip_id,))
        
        staff = cursor.fetchall()
        
        # Display trip details
        print(f"\nTrip Details - ID: {trip[0]}")
        print("=" * 60)
        print(f"Name: {trip[1]}")
        print(f"Description: {trip[2] or 'None'}")
        print(f"Destination: {trip[3]}")
        print(f"Start Date: {trip[4]}")
        print(f"End Date: {trip[5]}")
        print(f"Max Participants: {trip[6]}")
        print(f"Cost: £{trip[7]:.2f}")
        print(f"Status: {trip[8].title()}")
        print(f"Created By: {trip[11] if trip[11] else 'Unknown'}")
        print(f"Created: {trip[9]}")
        print(f"Updated: {trip[10]}")
        
        # Display participants
        print(f"\nParticipants ({len(participants)}/{trip[6]}):")
        print("-" * 60)
        if participants:
            for participant in participants:
                name = participant[9] if participant[9] else "Unknown"
                email = participant[10] if participant[10] else "N/A"
                reg_date = participant[3]
                payment = participant[4].title()
                print(f"• {name} ({email}) - Registered: {reg_date} - Payment: {payment}")
        else:
            print("No participants registered yet.")
        
        # Display staff
        if staff:
            print(f"\nAssigned Staff:")
            print("-" * 30)
            for staff_member in staff:
                role, name = staff_member
                print(f"• {name} - {role.title()}")
        
        print("=" * 60)
        return True
    
    return safe_db_operation(view_details_operation)

@log_create(module="trips", description="Registering for trip")
def register_for_trip():
    """Register current user for a trip"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to register for trips.")
        return False
    
    if not auth.check_permission('register_for_trips'):
        print("You don't have permission to register for trips.")
        return False
    
    def register_operation(conn):
        cursor = conn.cursor()
        
        # Get available trips
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
        
        available_trips = cursor.fetchall()
        
        if not available_trips:
            print("No trips available for registration.")
            return False
        
        print("\nAvailable Trips:")
        print("=" * 100)
        print(f"{'ID':<5} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'Cost':<10} {'Spaces Left':<12}")
        print("-" * 100)
        
        for trip in available_trips:
            spaces_left = trip[5] - trip[8]  # max_participants - current_participants
            print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} £{trip[6]:<9.2f} {spaces_left:<12}")
        
        print("=" * 100)
        
        # Get trip selection
        while True:
            try:
                trip_id = int(input("\nEnter Trip ID to register for: "))
                
                # Verify trip exists and is available
                selected_trip = None
                for trip in available_trips:
                    if trip[0] == trip_id:
                        selected_trip = trip
                        break
                
                if not selected_trip:
                    print("Invalid trip ID or trip not available.")
                    continue
                
                break
            except ValueError:
                print("Please enter a valid trip ID.")
        
        # Check if user is already registered
        cursor.execute('''
        SELECT id FROM trip_participants 
        WHERE trip_id = ? AND user_id = ?
        ''', (trip_id, auth.current_user['id']))
        
        if cursor.fetchone():
            print("You are already registered for this trip.")
            return False
        
        # Get student ID if user is a student
        student_id = None
        if auth.current_user['role'] == 'student':
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
            result = cursor.fetchone()
            if result:
                student_id = result[0]
        
        # Get additional information
        print(f"\nRegistering for: {selected_trip[1]}")
        print(f"Cost: £{selected_trip[6]:.2f}")
        
        emergency_contact = input("Emergency Contact (Name and Phone): ").strip()
        medical_info = input("Medical Information (optional): ").strip()
        dietary_requirements = input("Dietary Requirements (optional): ").strip()
        
        # Register for trip
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO trip_participants (
            trip_id, student_id, user_id, registration_date,
            emergency_contact, medical_info, dietary_requirements
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            trip_id, student_id, auth.current_user['id'], timestamp,
            emergency_contact, medical_info, dietary_requirements
        ))
        
        print(f"\nSuccessfully registered for '{selected_trip[1]}'!")
        print("Registration Status: Pending")
        print("Payment Status: Pending")
        print("\nYou will receive further information about payment and trip details.")
        
        return True
    
    return safe_db_operation(register_operation)

@log_read(module="trips", description="Viewing own trip registrations")
def view_my_trip_registrations():
    """View current user's trip registrations"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view your registrations.")
        return False
    
    if not auth.check_permission('view_own_trip_registrations'):
        print("You don't have permission to view trip registrations.")
        return False
    
    def view_registrations_operation(conn):
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
               t.cost, tp.registration_date, tp.payment_status, tp.status
        FROM trip_participants tp
        JOIN trips t ON tp.trip_id = t.id
        WHERE tp.user_id = ?
        ORDER BY t.start_date ASC
        ''', (auth.current_user['id'],))
        
        registrations = cursor.fetchall()
        
        if not registrations:
            print("You are not registered for any trips.")
            return True
        
        print("\nYour Trip Registrations:")
        print("=" * 100)
        print(f"{'Trip ID':<8} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'Cost':<10} {'Payment':<10} {'Status':<10}")
        print("-" * 100)
        
        for reg in registrations:
            trip_id, name, destination, start_date, end_date, cost, reg_date, payment_status, status = reg
            print(f"{trip_id:<8} {name[:24]:<25} {destination[:19]:<20} {start_date:<12} £{cost:<9.2f} {payment_status.title():<10} {status.title():<10}")
        
        print("=" * 100)
        return True
    
    return safe_db_operation(view_registrations_operation)

@log_update(module="trips", description="Managing trip participants")
def manage_trip_participants():
    """Manage participants for trips (staff/admin only)"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage trip participants.")
        return False
    
    if not auth.check_permission('manage_trip_participants'):
        print("You don't have permission to manage trip participants.")
        return False
    
    def manage_participants_operation(conn):
        cursor = conn.cursor()
        
        # Get trips with participants
        cursor.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date,
               COUNT(tp.id) as participant_count
        FROM trips t
        LEFT JOIN trip_participants tp ON t.id = tp.trip_id
        GROUP BY t.id
        ORDER BY t.start_date DESC
        ''')
        
        trips = cursor.fetchall()
        
        if not trips:
            print("No trips found.")
            return False
        
        print("\nTrips with Participants:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<30} {'Destination':<20} {'Start Date':<12} {'Participants':<12}")
        print("-" * 80)
        
        for trip in trips:
            print(f"{trip[0]:<5} {trip[1][:29]:<30} {trip[2][:19]:<20} {trip[3]:<12} {trip[4]:<12}")
        
        print("=" * 80)
        
        while True:
            try:
                trip_id = int(input("\nEnter Trip ID to manage participants (0 to exit): "))
                if trip_id == 0:
                    break
                
                # Verify trip exists
                cursor.execute('SELECT trip_name FROM trips WHERE id = ?', (trip_id,))
                trip_result = cursor.fetchone()
                if not trip_result:
                    print("Trip not found.")
                    continue
                
                trip_name = trip_result[0]
                
                # Get participants for this trip
                cursor.execute('''
                SELECT tp.id, tp.student_id, tp.payment_status, tp.status,
                       tp.registration_date, tp.emergency_contact,
                       s.first_name || ' ' || s.last_name as student_name,
                       s.email_address
                FROM trip_participants tp
                LEFT JOIN students s ON tp.student_id = s.student_id
                WHERE tp.trip_id = ?
                ORDER BY tp.registration_date
                ''', (trip_id,))
                
                participants = cursor.fetchall()
                
                print(f"\nParticipants for '{trip_name}':")
                print("=" * 120)
                print(f"{'ID':<5} {'Name':<25} {'Email':<25} {'Payment':<10} {'Status':<10} {'Registration':<12} {'Emergency':<20}")
                print("-" * 120)
                
                for participant in participants:
                    p_id, student_id, payment, status, reg_date, emergency, name, email = participant
                    name = name if name else f"Student {student_id}"
                    email = email if email else "N/A"
                    emergency = emergency[:19] if emergency else "N/A"
                    
                    print(f"{p_id:<5} {name[:24]:<25} {email[:24]:<25} {payment.title():<10} {status.title():<10} {reg_date[:10]:<12} {emergency:<20}")
                
                print("=" * 120)
                
                if not participants:
                    print("No participants registered for this trip.")
                    continue
                
                # Participant management options
                print("\nManagement Options:")
                print("1. Update payment status")
                print("2. Update participant status")
                print("3. Remove participant")
                print("4. Back to trip selection")
                
                choice = input("Enter choice (1-4): ").strip()
                
                if choice == '1':
                    update_payment_status(conn, trip_id, participants)
                elif choice == '2':
                    update_participant_status(conn, trip_id, participants)
                elif choice == '3':
                    remove_participant(conn, trip_id, participants)
                elif choice == '4':
                    continue
                else:
                    print("Invalid choice.")
                
            except ValueError:
                print("Please enter a valid number.")
            except Exception as e:
                print(f"Error managing participants: {e}")
                logging.error(f"Error in manage_trip_participants: {e}")
        
        return True
    
    return safe_db_operation(manage_participants_operation)

def update_payment_status(conn, trip_id, participants):
    """Update payment status for a participant"""
    try:
        participant_id = int(input("Enter participant ID to update payment: "))
        
        # Find participant
        participant = None
        for p in participants:
            if p[0] == participant_id:
                participant = p
                break
        
        if not participant:
            print("Participant not found.")
            return
        
        payment_options = ['pending', 'partial', 'paid', 'refunded']
        print("\nPayment Status Options:")
        for i, status in enumerate(payment_options, 1):
            print(f"{i}. {status.title()}")
        
        choice = int(input("Select new payment status (1-4): ")) - 1
        if 0 <= choice < len(payment_options):
            new_status = payment_options[choice]
            
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE trip_participants SET payment_status = ? WHERE id = ?',
                (new_status, participant_id)
            )
            
            print(f"Payment status updated to '{new_status.title()}'")
        else:
            print("Invalid choice.")
            
    except ValueError:
        print("Please enter a valid number.")
    except Exception as e:
        print(f"Error updating payment status: {e}")

def update_participant_status(conn, trip_id, participants):
    """Update status for a participant"""
    try:
        participant_id = int(input("Enter participant ID to update status: "))
        
        # Find participant
        participant = None
        for p in participants:
            if p[0] == participant_id:
                participant = p
                break
        
        if not participant:
            print("Participant not found.")
            return
        
        status_options = ['registered', 'waitlist', 'cancelled', 'attended']
        print("\nParticipant Status Options:")
        for i, status in enumerate(status_options, 1):
            print(f"{i}. {status.title()}")
        
        choice = int(input("Select new status (1-4): ")) - 1
        if 0 <= choice < len(status_options):
            new_status = status_options[choice]
            
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE trip_participants SET status = ? WHERE id = ?',
                (new_status, participant_id)
            )
            
            print(f"Participant status updated to '{new_status.title()}'")
        else:
            print("Invalid choice.")
            
    except ValueError:
        print("Please enter a valid number.")
    except Exception as e:
        print(f"Error updating participant status: {e}")

def remove_participant(conn, trip_id, participants):
    """Remove a participant from a trip"""
    try:
        participant_id = int(input("Enter participant ID to remove: "))
        
        # Find participant
        participant = None
        for p in participants:
            if p[0] == participant_id:
                participant = p
                break
        
        if not participant:
            print("Participant not found.")
            return
        
        participant_name = participant[6] if participant[6] else f"Student {participant[1]}"
        
        confirm = input(f"Are you sure you want to remove '{participant_name}' from this trip? (y/n): ").lower()
        if confirm == 'y':
            cursor = conn.cursor()
            cursor.execute('DELETE FROM trip_participants WHERE id = ?', (participant_id,))
            print(f"Participant '{participant_name}' removed from trip.")
        else:
            print("Removal cancelled.")
            
    except ValueError:
        print("Please enter a valid number.")
    except Exception as e:
        print(f"Error removing participant: {e}")

@log_update(module="trips", description="Updating trip information")
def update_trip():
    """Update trip information"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to update trips.")
        return False
    
    if not (auth.check_permission('manage_trips') or auth.check_permission('create_trips')):
        print("You don't have permission to update trips.")
        return False
    
    def update_trip_operation(conn):
        cursor = conn.cursor()
        
        # Get user's trips or all trips for admins
        if auth.check_permission('manage_trips'):
            cursor.execute('''
            SELECT id, trip_name, destination, start_date, end_date, status
            FROM trips
            ORDER BY start_date DESC
            ''')
        else:
            cursor.execute('''
            SELECT id, trip_name, destination, start_date, end_date, status
            FROM trips
            WHERE created_by = ?
            ORDER BY start_date DESC
            ''', (auth.current_user['id'],))
        
        trips = cursor.fetchall()
        
        if not trips:
            print("No trips found that you can update.")
            return False
        
        print("\nTrips Available for Update:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'Status':<10}")
        print("-" * 80)
        
        for trip in trips:
            print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[5].title():<10}")
        
        print("=" * 80)
        
        try:
            trip_id = int(input("\nEnter Trip ID to update: "))
            
            # Verify trip exists and user can update it
            cursor.execute('''
            SELECT * FROM trips WHERE id = ? AND (created_by = ? OR ? = 1)
            ''', (trip_id, auth.current_user['id'], 1 if auth.check_permission('manage_trips') else 0))
            
            trip = cursor.fetchone()
            if not trip:
                print("Trip not found or you don't have permission to update it.")
                return False
            
            print(f"\nUpdating Trip: {trip[1]}")
            print("Leave fields blank to keep current values.")
            
            # Get updated values
            new_name = input(f"Trip Name (current: {trip[1]}): ").strip()
            new_description = input(f"Description (current: {trip[2] or 'None'}): ").strip()
            new_destination = input(f"Destination (current: {trip[3]}): ").strip()
            
            # Date updates with validation
            new_start_date = input(f"Start Date (current: {trip[4]}, format: YYYY-MM-DD): ").strip()
            if new_start_date:
                try:
                    datetime.strptime(new_start_date, '%Y-%m-%d')
                except ValueError:
                    print("Invalid start date format. Keeping current value.")
                    new_start_date = ""
            
            new_end_date = input(f"End Date (current: {trip[5]}, format: YYYY-MM-DD): ").strip()
            if new_end_date:
                try:
                    datetime.strptime(new_end_date, '%Y-%m-%d')
                except ValueError:
                    print("Invalid end date format. Keeping current value.")
                    new_end_date = ""
            
            new_max_participants = input(f"Max Participants (current: {trip[6]}): ").strip()
            if new_max_participants:
                try:
                    new_max_participants = int(new_max_participants)
                    if new_max_participants <= 0:
                        print("Max participants must be positive. Keeping current value.")
                        new_max_participants = ""
                except ValueError:
                    print("Invalid number. Keeping current value.")
                    new_max_participants = ""
            
            new_cost = input(f"Cost (current: £{trip[7]:.2f}): ").strip()
            if new_cost:
                try:
                    new_cost = float(new_cost)
                    if new_cost < 0:
                        print("Cost cannot be negative. Keeping current value.")
                        new_cost = ""
                except ValueError:
                    print("Invalid cost. Keeping current value.")
                    new_cost = ""
            
            # Status update
            status_options = ['planning', 'open', 'full', 'cancelled', 'completed']
            print(f"\nCurrent Status: {trip[8].title()}")
            print("Status Options:")
            for i, status in enumerate(status_options, 1):
                print(f"{i}. {status.title()}")
            
            new_status = input("Select new status (1-5, or blank to keep current): ").strip()
            if new_status:
                try:
                    status_choice = int(new_status) - 1
                    if 0 <= status_choice < len(status_options):
                        new_status = status_options[status_choice]
                    else:
                        print("Invalid status choice. Keeping current value.")
                        new_status = ""
                except ValueError:
                    print("Invalid input. Keeping current value.")
                    new_status = ""
            
            # Build update query
            updates = []
            values = []
            
            if new_name:
                updates.append("trip_name = ?")
                values.append(new_name)
            if new_description:
                updates.append("description = ?")
                values.append(new_description)
            if new_destination:
                updates.append("destination = ?")
                values.append(new_destination)
            if new_start_date:
                updates.append("start_date = ?")
                values.append(new_start_date)
            if new_end_date:
                updates.append("end_date = ?")
                values.append(new_end_date)
            if new_max_participants:
                updates.append("max_participants = ?")
                values.append(new_max_participants)
            if new_cost:
                updates.append("cost = ?")
                values.append(new_cost)
            if new_status:
                updates.append("status = ?")
                values.append(new_status)
            
            if not updates:
                print("No changes to update.")
                return True
            
            # Add updated_at timestamp
            updates.append("updated_at = ?")
            values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            values.append(trip_id)
            
            # Execute update
            cursor.execute(f'''
            UPDATE trips SET {', '.join(updates)}
            WHERE id = ?
            ''', values)
            
            print("Trip updated successfully!")
            return True
            
        except ValueError:
            print("Invalid trip ID.")
            return False
        except Exception as e:
            print(f"Error updating trip: {e}")
            logging.error(f"Error in update_trip: {e}")
            return False
    
    return safe_db_operation(update_trip_operation)

@log_delete(module="trips", description="Deleting trip")
def delete_trip():
    """Delete a trip (admin/creator only)"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to delete trips.")
        return False
    
    if not auth.check_permission('manage_trips'):
        print("You don't have permission to delete trips.")
        return False
    
    def delete_trip_operation(conn):
        cursor = conn.cursor()
        
        # Get trips that can be deleted
        cursor.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.status,
               COUNT(tp.id) as participant_count
        FROM trips t
        LEFT JOIN trip_participants tp ON t.id = tp.trip_id
        GROUP BY t.id
        ORDER BY t.start_date DESC
        ''')
        
        trips = cursor.fetchall()
        
        if not trips:
            print("No trips found.")
            return False
        
        print("\nTrips Available for Deletion:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'Status':<10} {'Participants':<12}")
        print("-" * 80)
        
        for trip in trips:
            print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[4].title():<10} {trip[5]:<12}")
        
        print("=" * 80)
        
        try:
            trip_id = int(input("\nEnter Trip ID to delete: "))
            
            # Get trip details
            cursor.execute('''
            SELECT trip_name, destination, start_date, 
                   (SELECT COUNT(*) FROM trip_participants WHERE trip_id = ?) as participant_count
            FROM trips WHERE id = ?
            ''', (trip_id, trip_id))
            
            trip = cursor.fetchone()
            if not trip:
                print("Trip not found.")
                return False
            
            trip_name, destination, start_date, participant_count = trip
            
            print(f"\nTrip to Delete:")
            print(f"Name: {trip_name}")
            print(f"Destination: {destination}")
            print(f"Start Date: {start_date}")
            print(f"Participants: {participant_count}")
            
            if participant_count > 0:
                print(f"\nWarning: This trip has {participant_count} registered participants.")
                print("Deleting this trip will remove all participant registrations.")
            
            confirm1 = input("\nAre you sure you want to delete this trip? (y/n): ").lower()
            if confirm1 != 'y':
                print("Trip deletion cancelled.")
                return True
            
            if participant_count > 0:
                confirm2 = input("Type 'DELETE' to confirm deletion with participants: ")
                if confirm2 != 'DELETE':
                    print("Trip deletion cancelled.")
                    return True
            
            # Delete trip (cascade will handle participants due to foreign keys)
            cursor.execute('DELETE FROM trips WHERE id = ?', (trip_id,))
            
            print(f"\nTrip '{trip_name}' has been deleted successfully.")
            if participant_count > 0:
                print(f"All {participant_count} participant registrations have been removed.")
            
            return True
            
        except ValueError:
            print("Invalid trip ID.")
            return False
        except Exception as e:
            print(f"Error deleting trip: {e}")
            logging.error(f"Error in delete_trip: {e}")
            return False
    
    return safe_db_operation(delete_trip_operation)

def create_trip_calendar_event(calendar_manager):
    """Create a calendar event for a trip"""
    def create_event_operation(conn):
        cursor = conn.cursor()
        
        # Get trips without calendar events
        cursor.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
        FROM trips t
        LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
        WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open')
        ORDER BY t.start_date
        ''')
        
        available_trips = cursor.fetchall()
        
        if not available_trips:
            print("No trips available for calendar event creation.")
            return False
        
        print("\nTrips without Calendar Events:")
        print("-" * 70)
        for trip in available_trips:
            print(f"{trip[0]}: {trip[1]} to {trip[2]} ({trip[3]} - {trip[4]}) - {trip[5].title()}")
        
        try:
            trip_id = int(input("\nEnter Trip ID: "))
            
            # Find selected trip
            selected_trip = None
            for trip in available_trips:
                if trip[0] == trip_id:
                    selected_trip = trip
                    break
            
            if not selected_trip:
                print("Invalid trip selection.")
                return False
            
            # Create calendar event using the calendar manager
            result = calendar_manager.create_trip_event(trip_id)
            
            if result['success']:
                print(f"✓ Calendar event created successfully!")
                print(f"Event ID: {result['event_id']}")
            else:
                print(f"✗ Failed to create calendar event: {result['message']}")
            
            return True
            
        except ValueError:
            print("Invalid trip ID.")
            return False
    
    return safe_db_operation(create_event_operation)

def view_trip_events_in_calendar(calendar_manager):
    """View trip events in the calendar"""
    try:
        # Get current user's trip events
        current_date = datetime.now().strftime('%Y-%m-%d')
        future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        
        events = calendar_manager.get_events_by_date_range(current_date, future_date, 'Trip')
        
        if not events:
            print("No trip events found in calendar.")
            return
        
        print("\nTrip Events in Calendar:")
        print("=" * 80)
        print(f"{'Event Name':<30} {'Start Date':<12} {'End Date':<12} {'Description':<25}")
        print("-" * 80)
        
        for event in events:
            start_date = event.get('date_start') or event.get('date', 'TBD')
            end_date = event.get('date_end') or event.get('date', 'TBD')
            description = (event.get('description') or '')[:24]
            
            print(f"{event['name'][:29]:<30} {start_date:<12} {end_date:<12} {description:<25}")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"Error viewing trip events: {e}")

@log_menu_navigation(description="Displaying trip management menu")
def display_trip_management_menu():
    """Display the main trip management menu with calendar integration"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access trip management.")
        return
    
    # Initialize calendar system if available
    calendar_manager = None
    if CALENDAR_AVAILABLE:
        try:
            config = CalendarConfig()
            calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)
        except Exception as e:
            logging.warning(f"Could not initialize calendar system: {e}")
    
    while True:
        print(f"\nIntegrated Trip Management & Calendar System")
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")
        print("=" * 60)
        
        # Build menu based on permissions
        options = []
        option_num = 1
        
        # Trip management options
        print(f"🎒 TRIP MANAGEMENT:")
        if auth.check_permission('view_trips'):
            print(f"{option_num}. View All Trips")
            options.append(('view_trips', view_trips))
            option_num += 1
            
            if CALENDAR_AVAILABLE:
                print(f"{option_num}. View Trips with Calendar Info")
                options.append(('view_trips_calendar', view_trips_with_calendar))
                option_num += 1
        
        if auth.check_permission('create_trips'):
            print(f"{option_num}. Create New Trip")
            options.append(('create_trip', create_trip))
            option_num += 1
        
        if auth.check_permission('manage_trips'):
            print(f"{option_num}. Update Trip")
            options.append(('update_trip', update_trip))
            option_num += 1
            
            print(f"{option_num}. Delete Trip")
            options.append(('delete_trip', delete_trip))
            option_num += 1
        
        if auth.check_permission('register_for_trips'):
            print(f"{option_num}. Register for Trip")
            options.append(('register_trip', register_for_trip))
            option_num += 1
        
        if auth.check_permission('view_own_trip_registrations'):
            print(f"{option_num}. View My Registrations")
            options.append(('view_registrations', view_my_trip_registrations))
            option_num += 1
        
        if auth.check_permission('manage_trip_participants'):
            print(f"{option_num}. Manage Participants")
            options.append(('manage_participants', manage_trip_participants))
            option_num += 1
    
        if auth.check_permission('generate_trip_reports'):
            print(f"{option_num}. Generate Trip Report")
            options.append(('generate_report', generate_trip_report))
            option_num += 1
    
        # Calendar integration options
        if CALENDAR_AVAILABLE and calendar_manager:
            print(f"\n📅 CALENDAR INTEGRATION:")
            if auth.check_permission('manage_schedules'):
                print(f"{option_num}. Create Calendar Event for Trip")
                options.append(('create_trip_calendar_event', lambda: create_trip_calendar_event(calendar_manager)))
                option_num += 1
            
            if auth.check_permission('view_own_timetable'):
                print(f"{option_num}. View Trip Events in Calendar")
                options.append(('view_trip_events', lambda: view_trip_events_in_calendar(calendar_manager)))
                option_num += 1
        
        print(f"\n{option_num}. Return to Main Menu")
        
        try:
            choice = int(input(f"\nEnter your choice (1-{option_num}): "))
            
            if choice == option_num:  # Return to main menu
                break
            elif 1 <= choice <= len(options):
                action_name, action_func = options[choice - 1]
                try:
                    action_func()
                except Exception as e:
                    print(f"Error executing {action_name}: {e}")
                    logging.error(f"Error in {action_name}: {e}")
                
                input("\nPress Enter to continue...")
            else:
                print("Invalid choice. Please try again.")
                
        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            logging.error(f"Unexpected error in trip menu: {e}")

def setup_report_permissions():
    """Setup additional permissions for report generation"""
    try:
        from university_system.infrastructure.auth.user_authentication import UserAuth
        
        report_permissions = [
            ('generate_trip_reports', 'Generate trip reports'),
            ('view_financial_reports', 'View financial trip reports'),
            ('export_participant_data', 'Export participant data'),
            ('generate_comprehensive_reports', 'Generate comprehensive trip reports')
        ]
        
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        created_permissions = []
        for perm_name, perm_desc in report_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                created_permissions.append(perm_name)
        
        # Assign permissions to roles
        role_permissions = {
            'admin': [
                'generate_trip_reports', 'view_financial_reports', 
                'export_participant_data', 'generate_comprehensive_reports'
            ],
            'staff': [
                'generate_trip_reports', 'view_financial_reports', 
                'export_participant_data'
            ],
            'instructor': [
                'generate_trip_reports'
            ]
        }
        
        for role_name, permissions in role_permissions.items():
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if role_result:
                role_id = role_result[0]
                
                for perm_name in permissions:
                    cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                    perm_result = cursor.fetchone()
                    if perm_result:
                        perm_id = perm_result[0]
                        cursor.execute(
                            'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                            (role_id, perm_id)
                        )
        
        conn.commit()
        conn.close()
        
        if created_permissions:
            print(f"Created report permissions: {', '.join(created_permissions)}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error setting up report permissions: {e}")
        return False

class TripReportGenerator:
    """Class to handle trip report generation in multiple formats"""
    
    def __init__(self, auth_instance):
        self.auth = auth_instance
        self.reports_dir = "reports"
        self.ensure_reports_directory()
    
    def ensure_reports_directory(self):
        """Ensure the reports directory exists"""
        try:
            if not os.path.exists(self.reports_dir):
                os.makedirs(self.reports_dir)
                logging.info(f"Created reports directory: {self.reports_dir}")
        except OSError as e:
            logging.error(f"Failed to create reports directory: {e}")
            raise
    
    def generate_filename(self, report_type, format_type):
        """Generate a unique filename for the report"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            username = self.auth.current_user['username'] if self.auth.current_user else 'unknown'
            filename = f"{report_type}_{username}_{timestamp}.{format_type.lower()}"
            return os.path.join(self.reports_dir, filename)
        except Exception as e:
            logging.error(f"Error generating filename: {e}")
            return os.path.join(self.reports_dir, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type.lower()}")
    
    def get_trip_summary_data(self, conn):
        """Get comprehensive trip summary data"""
        try:
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
            
            # Get detailed trip information
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(tp.id) as current_participants,
                   SUM(CASE WHEN tp.payment_status = 'paid' THEN t.cost ELSE 0 END) as revenue_collected,
                   u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            LEFT JOIN users u ON t.created_by = u.id
            GROUP BY t.id
            ORDER BY t.start_date DESC
            ''')
            
            trip_details = cursor.fetchall()
            
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
            
            return {
                'summary_stats': summary_stats,
                'trip_details': trip_details,
                'participant_stats': participant_stats,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'generated_by': self.auth.current_user['username'] if self.auth.current_user else 'Unknown'
            }
            
        except sqlite3.Error as e:
            logging.error(f"Database error getting trip summary data: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error getting trip summary data: {e}")
            raise
    
    def get_participant_report_data(self, conn, trip_id=None):
        """Get participant report data"""
        try:
            cursor = conn.cursor()
            
            if trip_id:
                # Specific trip participants
                cursor.execute('''
                SELECT tp.id, t.trip_name, tp.student_id, 
                       s.first_name || ' ' || s.last_name as student_name,
                       s.email_address, tp.registration_date, tp.payment_status,
                       tp.status, tp.emergency_contact, tp.medical_info, tp.dietary_requirements
                FROM trip_participants tp
                JOIN trips t ON tp.trip_id = t.id
                LEFT JOIN students s ON tp.student_id = s.student_id
                WHERE tp.trip_id = ?
                ORDER BY tp.registration_date
                ''', (trip_id,))
            else:
                # All participants
                cursor.execute('''
                SELECT tp.id, t.trip_name, tp.student_id,
                       s.first_name || ' ' || s.last_name as student_name,
                       s.email_address, tp.registration_date, tp.payment_status,
                       tp.status, tp.emergency_contact, tp.medical_info, tp.dietary_requirements
                FROM trip_participants tp
                JOIN trips t ON tp.trip_id = t.id
                LEFT JOIN students s ON tp.student_id = s.student_id
                ORDER BY t.trip_name, tp.registration_date
                ''')
            
            participants = cursor.fetchall()
            
            return {
                'participants': participants,
                'trip_id': trip_id,
                'total_participants': len(participants),
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'generated_by': self.auth.current_user['username'] if self.auth.current_user else 'Unknown'
            }
            
        except sqlite3.Error as e:
            logging.error(f"Database error getting participant data: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error getting participant data: {e}")
            raise
    
    def get_financial_report_data(self, conn):
        """Get financial report data"""
        try:
            cursor = conn.cursor()
            
            # Revenue summary
            cursor.execute('''
            SELECT 
                t.id, t.trip_name, t.cost, t.max_participants,
                COUNT(tp.id) as registered_participants,
                SUM(CASE WHEN tp.payment_status = 'paid' THEN t.cost ELSE 0 END) as revenue_collected,
                SUM(CASE WHEN tp.payment_status = 'pending' THEN t.cost ELSE 0 END) as revenue_pending,
                t.cost * COUNT(tp.id) as revenue_potential
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            GROUP BY t.id
            HAVING registered_participants > 0
            ORDER BY revenue_collected DESC
            ''')
            
            revenue_data = cursor.fetchall()
            
            # Expense summary (if expenses table has data)
            cursor.execute('''
            SELECT t.trip_name, te.category, SUM(te.amount) as total_amount
            FROM trip_expenses te
            JOIN trips t ON te.trip_id = t.id
            GROUP BY t.id, te.category
            ORDER BY t.trip_name, te.category
            ''')
            
            expense_data = cursor.fetchall()
            
            # Overall financial summary
            cursor.execute('''
            SELECT 
                SUM(CASE WHEN tp.payment_status = 'paid' THEN t.cost ELSE 0 END) as total_revenue_collected,
                SUM(CASE WHEN tp.payment_status = 'pending' THEN t.cost ELSE 0 END) as total_revenue_pending,
                COUNT(DISTINCT t.id) as trips_with_revenue,
                COUNT(tp.id) as total_paid_participants
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
            ''')
            
            financial_summary = cursor.fetchone()
            
            return {
                'revenue_data': revenue_data,
                'expense_data': expense_data,
                'financial_summary': financial_summary,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'generated_by': self.auth.current_user['username'] if self.auth.current_user else 'Unknown'
            }
            
        except sqlite3.Error as e:
            logging.error(f"Database error getting financial data: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error getting financial data: {e}")
            raise
    
    def generate_txt_report(self, data, report_type, filename):
        """Generate a text format report"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 80 + "\n")
                f.write(f"TRIP MANAGEMENT SYSTEM - {report_type.upper()} REPORT\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated: {data['generated_at']}\n")
                f.write(f"Generated by: {data['generated_by']}\n")
                f.write("=" * 80 + "\n\n")
                
                if report_type == "TRIP_SUMMARY":
                    self._write_trip_summary_txt(f, data)
                elif report_type == "PARTICIPANT_LIST":
                    self._write_participant_list_txt(f, data)
                elif report_type == "FINANCIAL_REPORT":
                    self._write_financial_report_txt(f, data)
                
                # Footer
                f.write("\n" + "=" * 80 + "\n")
                f.write("End of Report\n")
                f.write("=" * 80 + "\n")
            
            logging.info(f"TXT report generated successfully: {filename}")
            return True
            
        except IOError as e:
            logging.error(f"IO error writing TXT report: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error generating TXT report: {e}")
            raise
    
    def _write_trip_summary_txt(self, f, data):
        """Write trip summary section for TXT report"""
        try:
            summary_stats = data['summary_stats']
            trip_details = data['trip_details']
            participant_stats = data['participant_stats']
            
            # Summary statistics
            f.write("TRIP SUMMARY STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Trips: {summary_stats[0]}\n")
            f.write(f"Planning: {summary_stats[1]}\n")
            f.write(f"Open for Registration: {summary_stats[2]}\n")
            f.write(f"Full: {summary_stats[3]}\n")
            f.write(f"Completed: {summary_stats[4]}\n")
            f.write(f"Cancelled: {summary_stats[5]}\n")
            f.write(f"Total Revenue Potential: £{summary_stats[6]:.2f}\n")
            f.write(f"Average Trip Cost: £{summary_stats[7]:.2f}\n\n")
            
            # Participant statistics
            f.write("PARTICIPANT STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Registrations: {participant_stats[0]}\n")
            f.write(f"Active Registrations: {participant_stats[1]}\n")
            f.write(f"Cancelled Registrations: {participant_stats[2]}\n")
            f.write(f"Paid Registrations: {participant_stats[3]}\n")
            f.write(f"Pending Payments: {participant_stats[4]}\n\n")
            
            # Detailed trip list
            f.write("DETAILED TRIP INFORMATION\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'ID':<5} {'Name':<20} {'Destination':<15} {'Start Date':<12} {'Participants':<12} {'Revenue':<12} {'Status':<10}\n")
            f.write("-" * 80 + "\n")
            
            for trip in trip_details:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, revenue, created_by = trip
                participants_info = f"{current_parts}/{max_parts}"
                revenue_info = f"£{revenue:.2f}" if revenue else "£0.00"
                
                f.write(f"{trip_id:<5} {name[:19]:<20} {destination[:14]:<15} {start_date:<12} {participants_info:<12} {revenue_info:<12} {status.title():<10}\n")
            
        except Exception as e:
            logging.error(f"Error writing trip summary TXT section: {e}")
            raise
    
    def _write_participant_list_txt(self, f, data):
        """Write participant list section for TXT report"""
        try:
            participants = data['participants']
            
            f.write(f"PARTICIPANT LIST REPORT\n")
            f.write(f"Total Participants: {data['total_participants']}\n")
            if data['trip_id']:
                f.write(f"Trip ID: {data['trip_id']}\n")
            f.write("-" * 100 + "\n")
            
            f.write(f"{'ID':<5} {'Trip':<20} {'Student Name':<25} {'Email':<25} {'Payment':<10} {'Status':<10}\n")
            f.write("-" * 100 + "\n")
            
            for participant in participants:
                p_id, trip_name, student_id, student_name, email, reg_date, payment_status, status, emergency, medical, dietary = participant
                name = student_name if student_name else f"Student {student_id}"
                email = email if email else "N/A"
                
                f.write(f"{p_id:<5} {trip_name[:19]:<20} {name[:24]:<25} {email[:24]:<25} {payment_status.title():<10} {status.title():<10}\n")
            
            # Additional details section
            f.write("\n" + "-" * 100 + "\n")
            f.write("DETAILED PARTICIPANT INFORMATION\n")
            f.write("-" * 100 + "\n")
            
            for participant in participants:
                p_id, trip_name, student_id, student_name, email, reg_date, payment_status, status, emergency, medical, dietary = participant
                name = student_name if student_name else f"Student {student_id}"
                
                f.write(f"\nParticipant ID: {p_id}\n")
                f.write(f"Name: {name}\n")
                f.write(f"Trip: {trip_name}\n")
                f.write(f"Registration Date: {reg_date}\n")
                f.write(f"Emergency Contact: {emergency if emergency else 'Not provided'}\n")
                f.write(f"Medical Info: {medical if medical else 'None'}\n")
                f.write(f"Dietary Requirements: {dietary if dietary else 'None'}\n")
                f.write("-" * 50 + "\n")
            
        except Exception as e:
            logging.error(f"Error writing participant list TXT section: {e}")
            raise
    
    def _write_financial_report_txt(self, f, data):
        """Write financial report section for TXT report"""
        try:
            revenue_data = data['revenue_data']
            expense_data = data['expense_data']
            financial_summary = data['financial_summary']
            
            # Financial summary
            f.write("FINANCIAL SUMMARY\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Revenue Collected: £{financial_summary[0]:.2f}\n")
            f.write(f"Total Revenue Pending: £{financial_summary[1]:.2f}\n")
            f.write(f"Trips with Revenue: {financial_summary[2]}\n")
            f.write(f"Total Paid Participants: {financial_summary[3]}\n\n")
            
            # Revenue by trip
            f.write("REVENUE BY TRIP\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'ID':<5} {'Trip Name':<25} {'Cost':<10} {'Participants':<12} {'Collected':<12} {'Pending':<12}\n")
            f.write("-" * 80 + "\n")
            
            for revenue in revenue_data:
                trip_id, trip_name, cost, max_parts, participants, collected, pending, potential = revenue
                f.write(f"{trip_id:<5} {trip_name[:24]:<25} £{cost:<9.2f} {participants:<12} £{collected:.2f:<11} £{pending:.2f:<11}\n")
            
            # Expenses by trip
            if expense_data:
                f.write("\nEXPENSES BY TRIP\n")
                f.write("-" * 60 + "\n")
                f.write(f"{'Trip Name':<30} {'Category':<20} {'Amount':<10}\n")
                f.write("-" * 60 + "\n")
                
                for expense in expense_data:
                    trip_name, category, amount = expense
                    f.write(f"{trip_name[:29]:<30} {category[:19]:<20} £{amount:.2f:<9}\n")
            else:
                f.write("\nNo expense data recorded.\n")
            
        except Exception as e:
            logging.error(f"Error writing financial report TXT section: {e}")
            raise
    
    def generate_pdf_report(self, data, report_type, filename):
        """Generate a PDF format report"""
        if not PDF_AVAILABLE:
            raise ImportError("ReportLab library not available. Cannot generate PDF reports.")
        
        try:
            doc = SimpleDocTemplate(filename, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=12,
                spaceAfter=12,
                spaceBefore=12
            )
            
            # Title
            story.append(Paragraph(f"Trip Management System - {report_type.replace('_', ' ').title()} Report", title_style))
            story.append(Spacer(1, 12))
            
            # Header info
            header_data = [
                ['Generated:', data['generated_at']],
                ['Generated by:', data['generated_by']]
            ]
            header_table = Table(header_data, colWidths=[1.5*inch, 4*inch])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
            ]))
            story.append(header_table)
            story.append(Spacer(1, 20))
            
            if report_type == "TRIP_SUMMARY":
                self._build_trip_summary_pdf(story, data, styles, heading_style)
            elif report_type == "PARTICIPANT_LIST":
                self._build_participant_list_pdf(story, data, styles, heading_style)
            elif report_type == "FINANCIAL_REPORT":
                self._build_financial_report_pdf(story, data, styles, heading_style)
            
            doc.build(story)
            logging.info(f"PDF report generated successfully: {filename}")
            return True
            
        except Exception as e:
            logging.error(f"Error generating PDF report: {e}")
            raise
    
    def _build_trip_summary_pdf(self, story, data, styles, heading_style):
        """Build trip summary section for PDF report"""
        try:
            summary_stats = data['summary_stats']
            trip_details = data['trip_details']
            participant_stats = data['participant_stats']
            
            # Summary statistics
            story.append(Paragraph("Trip Summary Statistics", heading_style))
            
            summary_data = [
                ['Metric', 'Value'],
                ['Total Trips', str(summary_stats[0])],
                ['Planning', str(summary_stats[1])],
                ['Open for Registration', str(summary_stats[2])],
                ['Full', str(summary_stats[3])],
                ['Completed', str(summary_stats[4])],
                ['Cancelled', str(summary_stats[5])],
                ['Total Revenue Potential', f'£{summary_stats[6]:.2f}'],
                ['Average Trip Cost', f'£{summary_stats[7]:.2f}']
            ]
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Participant statistics
            story.append(Paragraph("Participant Statistics", heading_style))
            
            participant_data = [
                ['Metric', 'Value'],
                ['Total Registrations', str(participant_stats[0])],
                ['Active Registrations', str(participant_stats[1])],
                ['Cancelled Registrations', str(participant_stats[2])],
                ['Paid Registrations', str(participant_stats[3])],
                ['Pending Payments', str(participant_stats[4])]
            ]
            
            participant_table = Table(participant_data, colWidths=[3*inch, 2*inch])
            participant_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(participant_table)
            story.append(Spacer(1, 20))
            
            # Trip details
            story.append(Paragraph("Detailed Trip Information", heading_style))
            
            trip_headers = ['ID', 'Name', 'Destination', 'Start Date', 'Participants', 'Revenue', 'Status']
            trip_data = [trip_headers]
            
            for trip in trip_details[:15]:  # Limit to first 15 trips for PDF
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, revenue, created_by = trip
                participants_info = f"{current_parts}/{max_parts}"
                revenue_info = f"£{revenue:.2f}" if revenue else "£0.00"
                
                trip_data.append([
                    str(trip_id),
                    name[:15] + "..." if len(name) > 15 else name,
                    destination[:10] + "..." if len(destination) > 10 else destination,
                    start_date,
                    participants_info,
                    revenue_info,
                    status.title()
                ])
            
            trip_table = Table(trip_data, colWidths=[0.5*inch, 1.5*inch, 1*inch, 1*inch, 0.8*inch, 0.8*inch, 0.8*inch])
            trip_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(trip_table)
            
            if len(trip_details) > 15:
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Note: Showing first 15 trips of {len(trip_details)} total trips.", styles['Normal']))
            
        except Exception as e:
            logging.error(f"Error building trip summary PDF section: {e}")
            raise
    
    def _build_participant_list_pdf(self, story, data, styles, heading_style):
        """Build participant list section for PDF report"""
        try:
            participants = data['participants']
            
            story.append(Paragraph(f"Participant List Report (Total: {data['total_participants']})", heading_style))
            
            if data['trip_id']:
                story.append(Paragraph(f"Trip ID: {data['trip_id']}", styles['Normal']))
                story.append(Spacer(1, 12))
            
            # Participant table
            headers = ['ID', 'Trip', 'Student Name', 'Email', 'Payment', 'Status']
            participant_data = [headers]
            
            for participant in participants[:20]:  # Limit for PDF
                p_id, trip_name, student_id, student_name, email, reg_date, payment_status, status, emergency, medical, dietary = participant
                name = student_name if student_name else f"Student {student_id}"
                email = email if email else "N/A"
                
                participant_data.append([
                    str(p_id),
                    trip_name[:12] + "..." if len(trip_name) > 12 else trip_name,
                    name[:15] + "..." if len(name) > 15 else name,
                    email[:18] + "..." if len(email) > 18 else email,
                    payment_status.title(),
                    status.title()
                ])
            
            participant_table = Table(participant_data, colWidths=[0.5*inch, 1.2*inch, 1.5*inch, 1.8*inch, 0.8*inch, 0.8*inch])
            participant_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(participant_table)
            
            if len(participants) > 20:
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Note: Showing first 20 participants of {len(participants)} total participants.", styles['Normal']))
            
        except Exception as e:
            logging.error(f"Error building participant list PDF section: {e}")
            raise
    
    def _build_financial_report_pdf(self, story, data, styles, heading_style):
        """Build financial report section for PDF report"""
        try:
            revenue_data = data['revenue_data']
            expense_data = data['expense_data']
            financial_summary = data['financial_summary']
            
            # Financial summary
            story.append(Paragraph("Financial Summary", heading_style))
            
            summary_data = [
                ['Metric', 'Value'],
                ['Total Revenue Collected', f'£{financial_summary[0]:.2f}'],
                ['Total Revenue Pending', f'£{financial_summary[1]:.2f}'],
                ['Trips with Revenue', str(financial_summary[2])],
                ['Total Paid Participants', str(financial_summary[3])]
            ]
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Revenue by trip
            story.append(Paragraph("Revenue by Trip", heading_style))
            
            revenue_headers = ['ID', 'Trip Name', 'Cost', 'Participants', 'Collected', 'Pending']
            revenue_table_data = [revenue_headers]
            
            for revenue in revenue_data[:15]:  # Limit for PDF
                trip_id, trip_name, cost, max_parts, participants, collected, pending, potential = revenue
                revenue_table_data.append([
                    str(trip_id),
                    trip_name[:15] + "..." if len(trip_name) > 15 else trip_name,
                    f'£{cost:.2f}',
                    str(participants),
                    f'£{collected:.2f}',
                    f'£{pending:.2f}'
                ])
            
            revenue_table = Table(revenue_table_data, colWidths=[0.5*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch])
            revenue_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(revenue_table)
            
            if len(revenue_data) > 15:
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Note: Showing first 15 trips of {len(revenue_data)} total trips with revenue.", styles['Normal']))
            
        except Exception as e:
            logging.error(f"Error building financial report PDF section: {e}")
            raise

    @log_create(module="trips", description="Generating trip report")
    def generate_trip_report():
        """Main function to generate trip reports"""
        global auth
        
        if not auth or not auth.current_user:
            print("You must be logged in to generate reports.")
            return False
        
        if not auth.check_permission('generate_trip_reports'):
            print("You don't have permission to generate trip reports.")
            return False
        
        try:
            # Initialize report generator
            report_generator = TripReportGenerator(auth)
            
            print("\nTrip Report Generator")
            print("=" * 50)
            
            # Report type selection
            report_types = [
                ("TRIP_SUMMARY", "Trip Summary Report"),
                ("PARTICIPANT_LIST", "Participant List Report"),
                ("FINANCIAL_REPORT", "Financial Report")
            ]
            
            print("Available Report Types:")
            for i, (code, description) in enumerate(report_types, 1):
                print(f"{i}. {description}")
            
            while True:
                try:
                    choice = int(input(f"\nSelect report type (1-{len(report_types)}): "))
                    if 1 <= choice <= len(report_types):
                        report_code, report_description = report_types[choice - 1]
                        break
                    print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")
            
            # Format selection
            format_types = ["TXT", "PDF"] if PDF_AVAILABLE else ["TXT"]
            
            print(f"\nAvailable Formats:")
            for i, fmt in enumerate(format_types, 1):
                print(f"{i}. {fmt}")
            
            while True:
                try:
                    format_choice = int(input(f"\nSelect format (1-{len(format_types)}): "))
                    if 1 <= format_choice <= len(format_types):
                        format_type = format_types[format_choice - 1]
                        break
                    print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")
            
            # Special handling for participant reports
            trip_id = None
            if report_code == "PARTICIPANT_LIST":
                choice = input("\nGenerate for specific trip? (y/n): ").lower()
                if choice == 'y':
                    try:
                        trip_id = int(input("Enter Trip ID: "))
                    except ValueError:
                        print("Invalid trip ID. Generating report for all trips.")
                        trip_id = None
            
            # Check financial report permissions
            if report_code == "FINANCIAL_REPORT" and not auth.check_permission('view_financial_reports'):
                print("You don't have permission to generate financial reports.")
                return False
            
            # Generate the report
            def generate_report_operation(conn):
                try:
                    print(f"\nGenerating {report_description} in {format_type} format...")
                    
                    # Get report data
                    if report_code == "TRIP_SUMMARY":
                        data = report_generator.get_trip_summary_data(conn)
                    elif report_code == "PARTICIPANT_LIST":
                        data = report_generator.get_participant_report_data(conn, trip_id)
                    elif report_code == "FINANCIAL_REPORT":
                        data = report_generator.get_financial_report_data(conn)
                    else:
                        raise ValueError(f"Unknown report type: {report_code}")
                    
                    # Generate filename
                    filename = report_generator.generate_filename(report_code, format_type)
                    
                    # Generate report based on format
                    if format_type == "TXT":
                        success = report_generator.generate_txt_report(data, report_code, filename)
                    elif format_type == "PDF":
                        success = report_generator.generate_pdf_report(data, report_code, filename)
                    else:
                        raise ValueError(f"Unknown format type: {format_type}")
                    
                    if success:
                        print(f"\n✓ Report generated successfully!")
                        print(f"File saved as: {filename}")
                        print(f"Report type: {report_description}")
                        print(f"Format: {format_type}")
                        print(f"Generated at: {data['generated_at']}")
                        
                        # Show file size
                        try:
                            file_size = os.path.getsize(filename)
                            print(f"File size: {file_size:,} bytes")
                        except OSError:
                            pass
                        
                        return True
                    else:
                        print("✗ Failed to generate report.")
                        return False
                    
                except Exception as e:
                    logging.error(f"Error in generate_report_operation: {e}")
                    print(f"Error generating report: {e}")
                    return False
            
            return safe_db_operation(generate_report_operation)
            
        except ImportError as e:
            print(f"Library error: {e}")
            return False
        except Exception as e:
            logging.error(f"Error in generate_trip_report: {e}")
            print(f"Unexpected error generating report: {e}")
            return False
    
    # Missing function definitions for trip_management.py
    
    @log_delete(module="trips", description="Cancelling trip registration")
    def cancel_trip_registration():
        """Cancel current user's trip registration"""
        global auth
        
        if not auth or not auth.current_user:
            print("You must be logged in to cancel trip registrations.")
            return False
        
        if not auth.check_permission('cancel_trip_registration'):
            print("You don't have permission to cancel trip registrations.")
            return False
        
        def cancel_registration_operation(conn):
            cursor = conn.cursor()
            
            # Get user's current registrations
            cursor.execute('''
            SELECT tp.id, t.id as trip_id, t.trip_name, t.destination, t.start_date, 
                   tp.registration_date, tp.payment_status, tp.status
            FROM trip_participants tp
            JOIN trips t ON tp.trip_id = t.id
            WHERE tp.user_id = ? AND tp.status = 'registered'
            ORDER BY t.start_date ASC
            ''', (auth.current_user['id'],))
            
            registrations = cursor.fetchall()
            
            if not registrations:
                print("You have no active trip registrations to cancel.")
                return True
            
            print("\nYour Active Trip Registrations:")
            print("=" * 100)
            print(f"{'ID':<5} {'Trip Name':<25} {'Destination':<20} {'Start Date':<12} {'Payment':<10} {'Reg Date':<12}")
            print("-" * 100)
            
            for reg in registrations:
                reg_id, trip_id, name, destination, start_date, reg_date, payment_status, status = reg
                print(f"{reg_id:<5} {name[:24]:<25} {destination[:19]:<20} {start_date:<12} {payment_status.title():<10} {reg_date[:10]:<12}")
            
            print("=" * 100)
            
            try:
                registration_id = int(input("\nEnter Registration ID to cancel (0 to exit): "))
                if registration_id == 0:
                    return True
                
                # Find the registration
                selected_reg = None
                for reg in registrations:
                    if reg[0] == registration_id:
                        selected_reg = reg
                        break
                
                if not selected_reg:
                    print("Invalid registration ID.")
                    return False
                
                reg_id, trip_id, trip_name, destination, start_date, reg_date, payment_status, status = selected_reg
                
                print(f"\nCancelling registration for: {trip_name}")
                print(f"Destination: {destination}")
                print(f"Start Date: {start_date}")
                print(f"Payment Status: {payment_status.title()}")
                
                if payment_status == 'paid':
                    print("\nWarning: You have paid for this trip. Cancellation may involve refund processing.")
                
                confirm = input("\nAre you sure you want to cancel this registration? (y/n): ").lower()
                if confirm != 'y':
                    print("Cancellation aborted.")
                    return True
                
                # Update registration status to cancelled
                cursor.execute('''
                UPDATE trip_participants 
                SET status = 'cancelled' 
                WHERE id = ?
                ''', (registration_id,))
                
                print(f"\nRegistration for '{trip_name}' has been cancelled successfully.")
                
                if payment_status in ['paid', 'partial']:
                    print("Please contact administration regarding refund processing.")
                
                return True
                
            except ValueError:
                print("Invalid registration ID.")
                return False
            except Exception as e:
                print(f"Error cancelling registration: {e}")
                logging.error(f"Error in cancel_trip_registration: {e}")
                return False
        
        return safe_db_operation(cancel_registration_operation)
    
    @log_create(module="trips", description="Adding trip itinerary")
    def add_trip_itinerary():
        """Add itinerary items to a trip"""
        global auth
        
        if not auth or not auth.current_user:
            print("You must be logged in to manage trip itineraries.")
            return False
        
        if not (auth.check_permission('manage_trips') or auth.check_permission('create_trips')):
            print("You don't have permission to manage trip itineraries.")
            return False
        
        def add_itinerary_operation(conn):
            cursor = conn.cursor()
            
            # Get trips that user can manage
            if auth.check_permission('manage_trips'):
                cursor.execute('''
                SELECT id, trip_name, destination, start_date, end_date, status
                FROM trips
                WHERE status IN ('planning', 'open')
                ORDER BY start_date ASC
                ''')
            else:
                cursor.execute('''
                SELECT id, trip_name, destination, start_date, end_date, status
                FROM trips
                WHERE created_by = ? AND status IN ('planning', 'open')
                ORDER BY start_date ASC
                ''', (auth.current_user['id'],))
            
            trips = cursor.fetchall()
            
            if not trips:
                print("No trips available for itinerary management.")
                return False
            
            print("\nTrips Available for Itinerary Management:")
            print("=" * 80)
            print(f"{'ID':<5} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'Status':<10}")
            print("-" * 80)
            
            for trip in trips:
                print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[5].title():<10}")
            
            print("=" * 80)
            
            try:
                trip_id = int(input("\nEnter Trip ID to add itinerary: "))
                
                # Verify trip exists and user can manage it
                selected_trip = None
                for trip in trips:
                    if trip[0] == trip_id:
                        selected_trip = trip
                        break
                
                if not selected_trip:
                    print("Invalid trip selection.")
                    return False
                
                trip_name = selected_trip[1]
                start_date = datetime.strptime(selected_trip[3], '%Y-%m-%d')
                end_date = datetime.strptime(selected_trip[4], '%Y-%m-%d')
                trip_days = (end_date - start_date).days + 1
                
                print(f"\nAdding itinerary for: {trip_name}")
                print(f"Trip duration: {trip_days} days")
                
                # Get existing itinerary
                cursor.execute('''
                SELECT day_number, activity, location, start_time, end_time
                FROM trip_itinerary
                WHERE trip_id = ?
                ORDER BY day_number, start_time
                ''', (trip_id,))
                
                existing_items = cursor.fetchall()
                
                if existing_items:
                    print(f"\nExisting Itinerary Items:")
                    print("-" * 60)
                    for item in existing_items:
                        day, activity, location, start_time, end_time = item
                        time_info = f"{start_time}-{end_time}" if start_time and end_time else "All day"
                        location_info = f" at {location}" if location else ""
                        print(f"Day {day}: {activity}{location_info} ({time_info})")
                
                # Add new itinerary items
                while True:
                    print(f"\nAdd New Itinerary Item:")
                    
                    while True:
                        try:
                            day_number = int(input(f"Day number (1-{trip_days}): "))
                            if 1 <= day_number <= trip_days:
                                break
                            print(f"Day number must be between 1 and {trip_days}.")
                        except ValueError:
                            print("Please enter a valid day number.")
                    
                    activity = input("Activity description: ").strip()
                    if not activity:
                        print("Activity description is required.")
                        continue
                    
                    location = input("Location (optional): ").strip()
                    start_time = input("Start time (HH:MM format, optional): ").strip()
                    end_time = input("End time (HH:MM format, optional): ").strip()
                    notes = input("Notes (optional): ").strip()
                    
                    # Validate time format if provided
                    if start_time:
                        try:
                            datetime.strptime(start_time, '%H:%M')
                        except ValueError:
                            print("Invalid start time format. Saving without time.")
                            start_time = None
                    
                    if end_time:
                        try:
                            datetime.strptime(end_time, '%H:%M')
                        except ValueError:
                            print("Invalid end time format. Saving without time.")
                            end_time = None
                    
                    # Insert itinerary item
                    try:
                        cursor.execute('''
                        INSERT INTO trip_itinerary (
                            trip_id, day_number, activity, location, 
                            start_time, end_time, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            trip_id, day_number, activity, location,
                            start_time, end_time, notes
                        ))
                        
                        print(f"✓ Itinerary item added for Day {day_number}: {activity}")
                        
                    except sqlite3.IntegrityError:
                        print("Error: Conflicting itinerary item (same day and time). Please try different time.")
                        continue
                    
                    # Ask if user wants to add more items
                    add_more = input("\nAdd another itinerary item? (y/n): ").lower()
                    if add_more != 'y':
                        break
                
                print(f"\nItinerary management completed for '{trip_name}'.")
                return True
                
            except ValueError:
                print("Invalid trip ID.")
                return False
            except Exception as e:
                print(f"Error managing itinerary: {e}")
                logging.error(f"Error in add_trip_itinerary: {e}")
                return False
        
        return safe_db_operation(add_itinerary_operation)

    @log_read(module="trips", description="Viewing trip itinerary")
    def view_trip_itinerary():
        """View itinerary for a specific trip"""
        global auth
        
        if not auth or not auth.current_user:
            print("You must be logged in to view trip itineraries.")
            return False
        
        if not auth.check_permission('view_trips'):
            print("You don't have permission to view trip itineraries.")
            return False
        
        def view_itinerary_operation(conn):
            cursor = conn.cursor()
            
            # Get trips with itineraries
            cursor.execute('''
            SELECT DISTINCT t.id, t.trip_name, t.destination, t.start_date, t.end_date
            FROM trips t
            JOIN trip_itinerary ti ON t.id = ti.trip_id
            ORDER BY t.start_date ASC
            ''')
            
            trips = cursor.fetchall()
            
            if not trips:
                print("No trips with itineraries found.")
                return True
            
            print("\nTrips with Itineraries:")
            print("=" * 80)
            print(f"{'ID':<5} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'End Date':<12}")
            print("-" * 80)
            
            for trip in trips:
                print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[4]:<12}")
            
            print("=" * 80)
            
            try:
                trip_id = int(input("\nEnter Trip ID to view itinerary: "))
                
                # Get trip details
                cursor.execute('SELECT trip_name, destination, start_date, end_date FROM trips WHERE id = ?', (trip_id,))
                trip_info = cursor.fetchone()
                
                if not trip_info:
                    print("Trip not found.")
                    return False
                
                trip_name, destination, start_date, end_date = trip_info
                
                # Get itinerary items
                cursor.execute('''
                SELECT day_number, activity, location, start_time, end_time, notes
                FROM trip_itinerary
                WHERE trip_id = ?
                ORDER BY day_number, start_time
                ''', (trip_id,))
                
                itinerary_items = cursor.fetchall()
                
                if not itinerary_items:
                    print(f"No itinerary found for '{trip_name}'.")
                    return True
                
                print(f"\nItinerary for: {trip_name}")
                print(f"Destination: {destination}")
                print(f"Dates: {start_date} to {end_date}")
                print("=" * 80)
                
                current_day = None
                for item in itinerary_items:
                    day_number, activity, location, start_time, end_time, notes = item
                    
                    if current_day != day_number:
                        print(f"\nDAY {day_number}:")
                        print("-" * 20)
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
                    
                    print(f"• {activity}{location_info} {time_info}")
                    
                    if notes:
                        print(f"  Notes: {notes}")
                
                print("=" * 80)
                return True
                
            except ValueError:
                print("Invalid trip ID.")
                return False
            except Exception as e:
                print(f"Error viewing itinerary: {e}")
                logging.error(f"Error in view_trip_itinerary: {e}")
                return False
        
        return safe_db_operation(view_itinerary_operation)
    
    @log_create(module="trips", description="Managing trip expenses")
    def manage_trip_expenses():
        """Manage expenses for trips"""
        global auth
        
        if not auth or not auth.current_user:
            print("You must be logged in to manage trip expenses.")
            return False
        
        if not auth.check_permission('manage_trip_expenses'):
            print("You don't have permission to manage trip expenses.")
            return False
        
        def manage_expenses_operation(conn):
            cursor = conn.cursor()
            
            # Get trips that user can manage expenses for
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.status,
                   COALESCE(SUM(te.amount), 0) as total_expenses
            FROM trips t
            LEFT JOIN trip_expenses te ON t.id = te.trip_id
            GROUP BY t.id
            ORDER BY t.start_date DESC
            ''')
            
            trips = cursor.fetchall()
            
            if not trips:
                print("No trips found.")
                return False
            
            print("\nTrips with Expense Information:")
            print("=" * 80)
            print(f"{'ID':<5} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'Total Expenses':<15}")
            print("-" * 80)
            
            for trip in trips:
                trip_id, name, destination, start_date, status, total_expenses = trip
                print(f"{trip_id:<5} {name[:24]:<25} {destination[:19]:<20} {start_date:<12} £{total_expenses:.2f:<14}")
            
            print("=" * 80)
            
            try:
                trip_id = int(input("\nEnter Trip ID to manage expenses: "))
                
                # Verify trip exists
                cursor.execute('SELECT trip_name FROM trips WHERE id = ?', (trip_id,))
                trip_result = cursor.fetchone()
                
                if not trip_result:
                    print("Trip not found.")
                    return False
                
                trip_name = trip_result[0]
                
                while True:
                    # Get existing expenses
                    cursor.execute('''
                    SELECT te.id, te.category, te.description, te.amount, te.date,
                           u.first_name || ' ' || u.last_name as recorded_by
                    FROM trip_expenses te
                    LEFT JOIN users u ON te.recorded_by = u.id
                    WHERE te.trip_id = ?
                    ORDER BY te.date DESC
                    ''', (trip_id,))
                    
                    expenses = cursor.fetchall()
                    
                    print(f"\nExpenses for '{trip_name}':")
                    print("=" * 100)
                    
                    if expenses:
                        print(f"{'ID':<5} {'Category':<15} {'Description':<25} {'Amount':<10} {'Date':<12} {'Recorded By':<15}")
                        print("-" * 100)
                        
                        total_amount = 0
                        for expense in expenses:
                            exp_id, category, description, amount, date, recorded_by = expense
                            total_amount += amount
                            recorded_by = recorded_by if recorded_by else "Unknown"
                            print(f"{exp_id:<5} {category[:14]:<15} {description[:24]:<25} £{amount:<9.2f} {date:<12} {recorded_by[:14]:<15}")
                        
                        print("-" * 100)
                        print(f"Total Expenses: £{total_amount:.2f}")
                    else:
                        print("No expenses recorded for this trip.")
                    
                    print("=" * 100)
                    
                    # Expense management options
                    print("\nExpense Management Options:")
                    print("1. Add New Expense")
                    print("2. Edit Expense")
                    print("3. Delete Expense")
                    print("4. Back to Trip Selection")
                    
                    choice = input("Enter choice (1-4): ").strip()
                    
                    if choice == '1':
                        add_expense(conn, trip_id)
                    elif choice == '2':
                        if expenses:
                            edit_expense(conn, trip_id, expenses)
                        else:
                            print("No expenses to edit.")
                    elif choice == '3':
                        if expenses:
                            delete_expense(conn, trip_id, expenses)
                        else:
                            print("No expenses to delete.")
                    elif choice == '4':
                        break
                    else:
                        print("Invalid choice.")
                
                return True
                
            except ValueError:
                print("Invalid trip ID.")
                return False
            except Exception as e:
                print(f"Error managing expenses: {e}")
                logging.error(f"Error in manage_trip_expenses: {e}")
                return False
        
        return safe_db_operation(manage_expenses_operation)
    
    def add_expense(conn, trip_id):
        """Add a new expense to a trip"""
        try:
            print("\nAdd New Expense:")
            
            # Expense categories
            categories = [
                'Transportation', 'Accommodation', 'Food', 'Activities', 
                'Equipment', 'Insurance', 'Miscellaneous'
            ]
            
            print("Expense Categories:")
            for i, category in enumerate(categories, 1):
                print(f"{i}. {category}")
            
            while True:
                try:
                    cat_choice = int(input("Select category (1-7): ")) - 1
                    if 0 <= cat_choice < len(categories):
                        category = categories[cat_choice]
                        break
                    print("Invalid choice.")
                except ValueError:
                    print("Please enter a number.")
            
            description = input("Description: ").strip()
            if not description:
                print("Description is required.")
                return
            
            while True:
                try:
                    amount = float(input("Amount (£): "))
                    if amount >= 0:
                        break
                    print("Amount cannot be negative.")
                except ValueError:
                    print("Please enter a valid amount.")
            
            while True:
                date_str = input("Date (YYYY-MM-DD, or press Enter for today): ").strip()
                if not date_str:
                    date_str = datetime.now().strftime('%Y-%m-%d')
                    break
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
            
            # Insert expense
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO trip_expenses (trip_id, category, description, amount, date, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (trip_id, category, description, amount, date_str, auth.current_user['id']))
            
            print(f"✓ Expense added: {category} - {description} (£{amount:.2f})")
            
        except Exception as e:
            print(f"Error adding expense: {e}")
    
    def edit_expense(conn, trip_id, expenses):
        """Edit an existing expense"""
        try:
            expense_id = int(input("Enter expense ID to edit: "))
            
            # Find expense
            selected_expense = None
            for expense in expenses:
                if expense[0] == expense_id:
                    selected_expense = expense
                    break
            
            if not selected_expense:
                print("Expense not found.")
                return
            
            exp_id, category, description, amount, date, recorded_by = selected_expense
            
            print(f"\nEditing expense: {category} - {description}")
            print("Leave fields blank to keep current values.")
            
            new_description = input(f"Description (current: {description}): ").strip()
            
            new_amount = input(f"Amount (current: £{amount:.2f}): ").strip()
            if new_amount:
                try:
                    new_amount = float(new_amount)
                    if new_amount < 0:
                        print("Amount cannot be negative. Keeping current value.")
                        new_amount = None
                except ValueError:
                    print("Invalid amount. Keeping current value.")
                    new_amount = None
            
            new_date = input(f"Date (current: {date}): ").strip()
            if new_date:
                try:
                    datetime.strptime(new_date, '%Y-%m-%d')
                except ValueError:
                    print("Invalid date format. Keeping current value.")
                    new_date = None
            
            # Build update query
            updates = []
            values = []
            
            if new_description:
                updates.append("description = ?")
                values.append(new_description)
            if new_amount is not None:
                updates.append("amount = ?")
                values.append(new_amount)
            if new_date:
                updates.append("date = ?")
                values.append(new_date)
            
            if not updates:
                print("No changes to update.")
                return
            
            values.append(expense_id)
            
            cursor = conn.cursor()
            cursor.execute(f'''
            UPDATE trip_expenses SET {', '.join(updates)}
            WHERE id = ?
            ''', values)
            
            print("✓ Expense updated successfully.")
            
        except ValueError:
            print("Invalid expense ID.")
        except Exception as e:
            print(f"Error editing expense: {e}")
    
    def delete_expense(conn, trip_id, expenses):
        """Delete an expense"""
        try:
            expense_id = int(input("Enter expense ID to delete: "))
            
            # Find expense
            selected_expense = None
            for expense in expenses:
                if expense[0] == expense_id:
                    selected_expense = expense
                    break
            
            if not selected_expense:
                print("Expense not found.")
                return
            
            exp_id, category, description, amount, date, recorded_by = selected_expense
            
            print(f"\nDelete expense: {category} - {description} (£{amount:.2f})")
            confirm = input("Are you sure? (y/n): ").lower()
            
            if confirm == 'y':
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_expenses WHERE id = ?', (expense_id,))
                print("✓ Expense deleted successfully.")
            else:
                print("Deletion cancelled.")
            
        except ValueError:
            print("Invalid expense ID.")
        except Exception as e:
            print(f"Error deleting expense: {e}")
    
    @log_create(module="trips", description="Assigning staff to trip")
    def assign_trip_staff():
        """Assign staff members to trips"""
        global auth
        
        if not auth or not auth.current_user:
            print("You must be logged in to assign trip staff.")
            return False
        
        if not auth.check_permission('manage_trips'):
            print("You don't have permission to assign trip staff.")
            return False
        
        def assign_staff_operation(conn):
            cursor = conn.cursor()
            
            # Get trips
            cursor.execute('''
            SELECT id, trip_name, destination, start_date, status
            FROM trips
            WHERE status IN ('planning', 'open')
            ORDER BY start_date ASC
            ''')
            
            trips = cursor.fetchall()
            
            if not trips:
                print("No trips available for staff assignment.")
                return False
            
            print("\nTrips Available for Staff Assignment:")
            print("=" * 80)
            print(f"{'ID':<5} {'Name':<25} {'Destination':<20} {'Start Date':<12} {'Status':<10}")
            print("-" * 80)
            
            for trip in trips:
                print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[4].title():<10}")
            
            print("=" * 80)
            
            try:
                trip_id = int(input("\nEnter Trip ID to assign staff: "))
                
                # Verify trip exists
                cursor.execute('SELECT trip_name FROM trips WHERE id = ?', (trip_id,))
                trip_result = cursor.fetchone()
                
                if not trip_result:
                    print("Trip not found.")
                    return False
                
                trip_name = trip_result[0]
                
                # Get available staff (users with staff or admin roles)
                cursor.execute('''
                SELECT u.id, u.first_name, u.last_name, u.username, r.role_name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE r.role_name IN ('admin', 'staff', 'instructor')
                AND u.id NOT IN (
                    SELECT staff_user_id FROM trip_staff WHERE trip_id = ?
                )
                ORDER BY r.role_name, u.last_name
                ''', (trip_id,))
                
                available_staff = cursor.fetchall()
                
                if not available_staff:
                    print("No available staff members to assign.")
                    return False
                
                # Show currently assigned staff
                cursor.execute('''
                SELECT ts.role, u.first_name || ' ' || u.last_name as staff_name
                FROM trip_staff ts
                JOIN users u ON ts.staff_user_id = u.id
                WHERE ts.trip_id = ?
                ORDER BY ts.role
                ''', (trip_id,))
                
                current_staff = cursor.fetchall()
                
                print(f"\nAssigning staff to: {trip_name}")
                
                if current_staff:
                    print("\nCurrently Assigned Staff:")
                    for staff in current_staff:
                        role, name = staff
                        print(f"• {name} - {role.title()}")
                
                print(f"\nAvailable Staff Members:")
                print("-" * 70)
                print(f"{'ID':<5} {'Name':<25} {'Username':<20} {'Role':<15}")
                print("-" * 70)
                
                for staff in available_staff:
                    user_id, first_name, last_name, username, role = staff
                    full_name = f"{first_name} {last_name}"
                    print(f"{user_id:<5} {full_name[:24]:<25} {username[:19]:<20} {role.title():<15}")
                
                print("-" * 70)
                
                staff_id = int(input("\nEnter Staff User ID to assign: "))
                
                # Verify staff selection
                selected_staff = None
                for staff in available_staff:
                    if staff[0] == staff_id:
                        selected_staff = staff
                        break
                
                if not selected_staff:
                    print("Invalid staff selection.")
                    return False
                
                user_id, first_name, last_name, username, role = selected_staff
                staff_name = f"{first_name} {last_name}"
                
                # Select staff role for trip
                staff_roles = ['supervisor', 'coordinator', 'medical', 'transport']
                print(f"\nAssigning {staff_name} to trip. Select role:")
                for i, role_option in enumerate(staff_roles, 1):
                    print(f"{i}. {role_option.title()}")
                
                while True:
                    try:
                        role_choice = int(input("Select role (1-4): ")) - 1
                        if 0 <= role_choice < len(staff_roles):
                            selected_role = staff_roles[role_choice]
                            break
                        print("Invalid choice.")
                    except ValueError:
                        print("Please enter a number.")
                
                # Assign staff to trip
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO trip_staff (trip_id, staff_user_id, role, assigned_date)
                VALUES (?, ?, ?, ?)
                ''', (trip_id, staff_id, selected_role, timestamp))
                
                print(f"✓ {staff_name} assigned to '{trip_name}' as {selected_role.title()}")
                return True
                
            except ValueError:
                print("Invalid input.")
                return False
            except sqlite3.IntegrityError:
                print("Staff member is already assigned to this trip.")
                return False
            except Exception as e:
                print(f"Error assigning staff: {e}")
                logging.error(f"Error in assign_trip_staff: {e}")
                return False
        
        return safe_db_operation(assign_staff_operation)

def integrate_trip_management_with_main():
    """Initialize trip management system for integration with main system"""
    try:
        print("Initializing trip management system...")
        
        # Initialize database
        if not init_trip_db():
            print("Failed to initialize trip management database.")
            return False
        
        # Setup permissions
        if not setup_trip_permissions():
            print("Failed to setup trip management permissions.")
            return False
        
        print("Trip management system initialized successfully!")
        return True
        
    except Exception as e:
        logging.error(f"Failed to initialize trip management: {e}")
        print(f"Error initializing trip management: {e}")
        return False

def test_report_generation():
    """Test the report generation system"""
    print("Testing Trip Report Generation System...")
    
    try:
        # Test permission setup
        if setup_report_permissions():
            print("✓ Report permissions setup successful")
        else:
            print("✗ Report permissions setup failed")
            return
        
        print("✓ Report generation system test completed successfully!")
        print(f"PDF Generation Available: {PDF_AVAILABLE}")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        logging.error(f"Report generation test error: {e}")

# Test function
def test_trip_management():
    """Test the trip management system"""
    print("Testing Trip Management System...")
    
    try:
        # Test database initialization
        if init_trip_db():
            print("✓ Database initialization successful")
        else:
            print("✗ Database initialization failed")
            return
        
        # Test permission setup
        if setup_trip_permissions():
            print("✓ Permission setup successful")
        else:
            print("✗ Permission setup failed")
            return
        
        print("✓ Trip management system test completed successfully!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        logging.error(f"Trip management test error: {e}")

if __name__ == "__main__":
    test_report_generation()
    # Run tests
    test_trip_management()
