from university_system.infrastructure.database.database_utils import DatabaseManager, cleanup_database_connections
from university_system.infrastructure.auth import UserAuth, display_auth_menu
from university_system.infrastructure.shared_context import get_auth
from university_system.infrastructure.database.data_backup import display_backup_menu, backup_before_operation
from university_system.infrastructure.email.admin import display_communication_dashboard
from university_system.infrastructure.email import send_permit_confirmation, send_update_confirmation
from university_system.infrastructure.database.db import sqlite3, get_connection
from university_system.modules.domain.mobility.services.trip_management import (
    display_trip_management_menu,
    view_trips,
    create_trip,
    register_for_trip,
    view_my_trip_registrations,
    manage_trip_participants
)
import random
import re
import os
import csv
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from datetime import datetime, timedelta
import logging
from university_system.utils.logging.log_config import configure_logging
from university_system.utils.logging.log_config import get_log_file
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
# Alias for convenience
_t = get_text
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

# Configure logging
log_path = get_log_file("permit_system.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

logger = configure_logging(name=__name__)

# Define parking zones
PARKING_ZONES = {
    'A': {'name': 'Faculty/Staff', 'hourly_rate': 0, 'annual_fee': 250},
    'B': {'name': 'Commuter Students', 'hourly_rate': 0, 'annual_fee': 180},
    'C': {'name': 'Resident Students', 'hourly_rate': 0, 'annual_fee': 220},
    'V': {'name': 'Visitor', 'hourly_rate': 2.50, 'annual_fee': 0},
    'H': {'name': 'Handicap Accessible', 'hourly_rate': 0, 'annual_fee': 150},
    'M': {'name': 'Metered', 'hourly_rate': 1.75, 'annual_fee': 0},
    'R': {'name': 'Reserved', 'hourly_rate': 0, 'annual_fee': 350},
}

# Define permit types
PERMIT_TYPES = ['Annual', 'Semester', 'Monthly', 'Daily', 'Temporary']

# Define vehicle types
VEHICLE_TYPES = ['Sedan', 'SUV', 'Truck', 'Motorcycle', 'Compact', 'Van']

class ParkingPermit:
    def __init__(self, permit_id, user_id, full_name, email, zone, permit_type, 
                start_date, end_date, active_status, vehicle_id, issue_date):
        self.permit_id = permit_id
        self.user_id = user_id
        self.full_name = full_name
        self.email = email
        self.zone = zone
        self.permit_type = permit_type
        self.start_date = start_date
        self.end_date = end_date
        self.active_status = active_status
        self.vehicle_id = vehicle_id
        self.issue_date = issue_date


class Vehicle:
    def __init__(self, vehicle_id, license_plate, make, model, year, color, 
                vehicle_type, owner_id, registration_state):
        self.vehicle_id = vehicle_id
        self.license_plate = license_plate
        self.make = make
        self.model = model
        self.year = year
        self.color = color
        self.vehicle_type = vehicle_type
        self.owner_id = owner_id
        self.registration_state = registration_state


class ParkingViolation:
    def __init__(self, violation_id, vehicle_id, license_plate, violation_type, 
                violation_date, fine_amount, payment_status, location, officer_id):
        self.violation_id = violation_id
        self.vehicle_id = vehicle_id
        self.license_plate = license_plate
        self.violation_type = violation_type
        self.violation_date = violation_date
        self.fine_amount = fine_amount
        self.payment_status = payment_status
        self.location = location
        self.officer_id = officer_id

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
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

def init_db():
    conn = None
    try:
        # 1) Open the single student_records database
        conn = get_connection()
        # 2) Turn on FK checks
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        # 3) Ensure users table exists (main.py should normally create it first)
        cursor.execute("PRAGMA table_info(users)")
        if not cursor.fetchall():
            logging.info("users table missing – creating it here")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    UNIQUE NOT NULL,
                first_name  TEXT    NOT NULL,
                last_name   TEXT    NOT NULL,
                email       TEXT    UNIQUE NOT NULL,
                role        TEXT    NOT NULL,
                student_id  TEXT,
                created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
            ''')

        # 4) Vehicles table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id         TEXT    PRIMARY KEY,
            license_plate      TEXT    NOT NULL,
            make               TEXT,
            model              TEXT,
            year               INTEGER,
            color              TEXT,
            vehicle_type       TEXT,
            owner_id           INTEGER,
            registration_state TEXT,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
        ''')

        # 5) Parking permits
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_permits (
            permit_id     TEXT    PRIMARY KEY,
            user_id       INTEGER,
            full_name     TEXT,
            email         TEXT,
            zone          TEXT,
            permit_type   TEXT,
            start_date    TEXT,
            end_date      TEXT,
            active_status TEXT,
            vehicle_id    TEXT,
            issue_date    TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
            FOREIGN KEY (user_id)    REFERENCES users(id)
        )
        ''')

        # 6) Parking lots
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_lots (
            lot_id              TEXT    PRIMARY KEY,
            lot_name            TEXT,
            location            TEXT,
            total_spaces        INTEGER,
            available_spaces    INTEGER,
            zone                TEXT,
            hours_of_operation  TEXT
        )
        ''')

        # 7) Parking spaces
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_spaces (
            space_id         TEXT    PRIMARY KEY,
            lot_id           TEXT,
            space_number     TEXT,
            space_type       TEXT,
            occupancy_status TEXT,
            reserved_for     TEXT,
            FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
        )
        ''')

        # 8) Violations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_violations (
            violation_id    TEXT    PRIMARY KEY,
            vehicle_id      TEXT,
            license_plate   TEXT,
            violation_type  TEXT,
            violation_date  TEXT,
            fine_amount     REAL,
            payment_status  TEXT,
            location        TEXT,
            officer_id      INTEGER,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
            FOREIGN KEY (officer_id) REFERENCES users(id)
        )
        ''')

        # 9) (Optional) Seed default lots if needed
        cursor.execute('SELECT COUNT(*) FROM parking_lots')
        if cursor.fetchone()[0] == 0:
            lot_data = [
                ('L001','North Campus Lot','North Campus',200,200,'A','24/7'),
                ('L002','South Campus Lot','South Campus',150,150,'B','24/7'),
                ('L003','East Campus Lot','East Campus',100,100,'C','24/7'),
                ('L004','West Campus Lot','West Campus',80,80,'V','07:00-22:00'),
                ('L005','Central Campus Lot','Central Campus',50,50,'H','24/7')
            ]
            cursor.executemany(
                'INSERT INTO parking_lots VALUES (?,?,?,?,?,?,?)',
                lot_data
            )
            logging.info("Default parking lots created")

        conn.commit()
        logging.info("Parking DB initialized in student_records.db")
        return True

    except sqlite3.Error as e:
        logging.error(f"Parking init_db() error: {e}")
        print(_t("parking.error.init_db") + f": {e}")
        return False

    finally:
        if conn:
            conn.close()

def create_parking_permit():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to create parking permit")
        print(_t("parking.auth.login_required"))
        return

    if not auth.check_permission('create_permit'):
        logging.warning(f"User {auth.current_user['username']} attempted to create permit without permission")
        print(_t("parking.auth.no_permission_create"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get user information
        if auth.current_user['role'] == 'admin' or auth.current_user['role'] == 'staff':
            # Admin/staff can create permits for existing users or visitors
            print("\n" + _t("parking.permit.create_for"))
            print("1. " + _t("parking.permit.existing_user"))
            print("2. " + _t("parking.permit.visitor"))
            choice = input(_t("common.enter_choice") + " (1-2): ")
            
            user_id = None
            full_name = None
            email = None
            
            if choice == '1':
                # Find existing user
                search_term = input(_t("parking.permit.search_user_prompt") + ": ")
                cursor.execute('''
                SELECT id, first_name, last_name, email FROM users
                WHERE id = ? OR username = ? OR email = ? OR student_id = ?
                ''', (search_term, search_term, search_term, search_term))

                user = cursor.fetchone()
                if not user:
                    print(_t("parking.error.user_not_found"))
                    print(_t("parking.error.user_not_found_note"))
                    conn.close()
                    return
                
                user_id = user[0]
                full_name = f"{user[1]} {user[2]}"
                email = user[3]
                
                print(f"Creating permit for: {full_name} ({email})")
                
            elif choice == '2':
                # Visitor - no user account needed
                print("\n" + _t("parking.visitor.info_header"))
                first_name = input(_t("parking.visitor.enter_first_name") + ": ")
                if not first_name:
                    print(_t("parking.error.first_name_required"))
                    conn.close()
                    return

                last_name = input(_t("parking.visitor.enter_last_name") + ": ")
                if not last_name:
                    print(_t("parking.error.last_name_required"))
                    conn.close()
                    return

                email = input(_t("parking.visitor.enter_email") + ": ")
                if not email or '@' not in email:
                    print(_t("parking.error.valid_email_required"))
                    conn.close()
                    return
                
                # For visitors, we don't create a user account
                user_id = None  # No user account
                full_name = f"{first_name} {last_name}"
                
                print(f"Creating visitor permit for: {full_name}")
                
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return
        else:
            # Regular users can only create permits for themselves
            user_id = auth.current_user['id']
            cursor.execute('''
            SELECT first_name, last_name, email FROM users WHERE id = ?
            ''', (user_id,))
            
            user = cursor.fetchone()
            if not user:
                print(_t("parking.error.user_profile_not_found"))
                conn.close()
                return
            
            full_name = f"{user[0]} {user[1]}"
            email = user[2]
        
        # Ask for vehicle information
        print("\n" + _t("parking.vehicle.info_header"))
        print("1. " + _t("parking.vehicle.use_existing"))
        print("2. " + _t("parking.vehicle.register_new"))
        
        vehicle_choice = input("Enter your choice (1-2): ")
        vehicle_id = None
        
        if vehicle_choice == '1' and user_id:
            # Find existing vehicle for this user (only if user has an account)
            cursor.execute('''
            SELECT vehicle_id, license_plate, make, model FROM vehicles WHERE owner_id = ?
            ''', (user_id,))
            
            vehicles = cursor.fetchall()
            if not vehicles:
                print(_t("parking.msg.no_vehicles_for_user"))
                vehicle_choice = '2'  # Switch to new vehicle registration
            else:
                print("\n" + _t("parking.section.available_vehicles") + ":")
                for i, v in enumerate(vehicles):
                    print(f"{i+1}. {v[1]} - {v[2]} {v[3]}")
                
                try:
                    idx = int(input("Select a vehicle (number): ")) - 1
                    if idx < 0 or idx >= len(vehicles):
                        raise ValueError
                    vehicle_id = vehicles[idx][0]
                except (ValueError, IndexError):
                    print(_t("common.invalid_selection_retry"))
                    conn.close()
                    return
        
        if vehicle_choice == '2' or vehicle_choice == '1' and not user_id:
            # Register new vehicle
            try:
                license_plate = input("Enter license plate: ").upper()
                if not license_plate:
                    print(_t("parking.error.license_plate_required"))
                    conn.close()
                    return
                
                # Check if license plate already exists
                cursor.execute('SELECT COUNT(*) FROM vehicles WHERE license_plate = ?', (license_plate,))
                if cursor.fetchone()[0] > 0:
                    print(_t("parking.error.license_plate_exists"))
                    conn.close()
                    return
                
                make = input("Enter vehicle make: ")
                if not make:
                    print(_t("parking.error.make_required"))
                    conn.close()
                    return
                
                model = input("Enter vehicle model: ")
                if not model:
                    print(_t("parking.error.model_required"))
                    conn.close()
                    return
                
                # Ask for vehicle year with validation
                year = None
                while not year:
                    try:
                        year_input = input("Enter vehicle year (YYYY): ")
                        year = int(year_input)
                        current_year = datetime.now().year
                        if year < 1900 or year > current_year + 1:
                            print(_t("parking.error.year_range").format(max_year=current_year + 1))
                            year = None
                    except ValueError:
                        print(_t("parking.error.year_must_be_number"))
                
                color = input("Enter vehicle color: ")
                
                # Ask for vehicle type with validation
                print(_t("parking.vehicle.types_available") + ":", ", ".join(VEHICLE_TYPES))
                while True:
                    vehicle_type = input("Enter vehicle type: ")
                    if not vehicle_type:
                        vehicle_type = "Sedan"  # Default
                        break
                    if vehicle_type in VEHICLE_TYPES:
                        break
                    print(f"Invalid vehicle type. Please choose from {', '.join(VEHICLE_TYPES)}")
                
                registration_state = input("Enter registration state (e.g., NY): ").upper()
                if not registration_state:
                    print(_t("parking.error.registration_state_required"))
                    conn.close()
                    return
                
                # Generate vehicle ID
                cursor.execute('SELECT COUNT(*) FROM vehicles')
                count = cursor.fetchone()[0] + 1
                vehicle_id = f"V{str(count).zfill(6)}"
                
                # Insert vehicle (owner_id can be NULL for visitors)
                cursor.execute(
                    'INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (vehicle_id, license_plate, make, model, year, color, vehicle_type, user_id, registration_state)
                )
                
                conn.commit()
                print(f"\nVehicle registered successfully with ID: {vehicle_id}")
                
            except Exception as e:
                logging.error(f"Error registering vehicle: {e}")
                print(_t("parking.error.registering_vehicle") + f": {e}")
                conn.close()
                return
        
        # Ask for permit details
        print("\n" + _t("parking.section.permit_info") + ":")
        
        # Show available zones - restrict visitor zones
        print("\n" + _t("parking.section.available_zones") + ":")
        if user_id is None:  # Visitor
            # Visitors can only use Visitor and Metered zones
            visitor_zones = {'V': PARKING_ZONES['V'], 'M': PARKING_ZONES['M']}
            for zone_code, zone_info in visitor_zones.items():
                print(f"{zone_code}: {zone_info['name']} - Hourly Rate: ${zone_info['hourly_rate']}")
        else:
            # Regular users can use any zone
            for zone_code, zone_info in PARKING_ZONES.items():
                print(f"{zone_code}: {zone_info['name']} - Annual Fee: ${zone_info['annual_fee']}, Hourly Rate: ${zone_info['hourly_rate']}")
        
        # Get zone with validation
        while True:
            zone = input("Enter zone code: ").upper()
            if user_id is None:  # Visitor
                if zone in ['V', 'M']:
                    break
                print(_t("parking.msg.visitors_zones_only"))
            else:
                if zone in PARKING_ZONES:
                    break
                print(f"Invalid zone code. Please enter one of: {', '.join(PARKING_ZONES.keys())}")
        
        # Show permit types - restrict for visitors
        if user_id is None:  # Visitor
            visitor_permit_types = ['Daily', 'Temporary']
            print("\n" + _t("parking.section.visitor_permit_types") + ":", ", ".join(visitor_permit_types))
        else:
            print("\n" + _t("parking.permit.types_available") + ":", ", ".join(PERMIT_TYPES))
        
        # Get permit type with validation
        while True:
            permit_type = input("Enter permit type: ")
            if user_id is None:  # Visitor
                if permit_type in ['Daily', 'Temporary']:
                    break
                print(_t("parking.msg.visitors_permits_only"))
            else:
                if permit_type in PERMIT_TYPES:
                    break
                print(f"Invalid permit type. Please choose from {', '.join(PERMIT_TYPES)}")
        
        # Set start and end dates based on permit type
        start_date = datetime.now()
        
        if permit_type == 'Annual':
            end_date = start_date.replace(year=start_date.year + 1)
        elif permit_type == 'Semester':
            end_date = start_date + timedelta(days=120)
        elif permit_type == 'Monthly':
            end_date = start_date + timedelta(days=30)
        elif permit_type == 'Daily':
            end_date = start_date + timedelta(days=1)
        elif permit_type == 'Temporary':
            days = None
            while not days:
                try:
                    days = int(input("Enter number of days for temporary permit: "))
                    if days <= 0 or days > 30:
                        print(_t("parking.error.days_range"))
                        days = None
                except ValueError:
                    print(_t("parking.error.enter_valid_number"))
            end_date = start_date + timedelta(days=days)
        
        # Format dates for database
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        issue_date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Generate permit ID
        cursor.execute('SELECT COUNT(*) FROM parking_permits')
        count = cursor.fetchone()[0] + 1
        permit_id = f"P{zone}{start_date.year % 100}{str(count).zfill(4)}"
        
        # Insert permit
        try:
            cursor.execute(
                'INSERT INTO parking_permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (permit_id, user_id, full_name, email, zone, permit_type, 
                 start_date_str, end_date_str, 'Active', vehicle_id, issue_date_str)
            )
            
            conn.commit()
            
            # Send confirmation email (simulated)
            send_permit_confirmation(permit_id, email, zone, permit_type, start_date_str, end_date_str)
            
            # Print permit details
            print("\n" + "="*50)
            print(_t("parking.permit.created_success"))
            print("="*50)
            print(f"Permit ID: {permit_id}")
            print(f"Holder: {full_name}")
            print(f"Email: {email}")
            print(f"Zone: {zone} - {PARKING_ZONES[zone]['name']}")
            print(f"Type: {permit_type}")
            print(f"Valid From: {start_date_str} to {end_date_str}")
            print(f"Status: Active")
            
            # Calculate fee
            if permit_type == 'Annual':
                fee = PARKING_ZONES[zone]['annual_fee']
            elif permit_type == 'Semester':
                fee = PARKING_ZONES[zone]['annual_fee'] * 0.6
            elif permit_type == 'Monthly':
                fee = PARKING_ZONES[zone]['annual_fee'] * 0.15
            elif permit_type == 'Daily':
                fee = PARKING_ZONES[zone]['hourly_rate'] * 8 if PARKING_ZONES[zone]['hourly_rate'] > 0 else 10
            elif permit_type == 'Temporary':
                fee = PARKING_ZONES[zone]['hourly_rate'] * 8 * days if PARKING_ZONES[zone]['hourly_rate'] > 0 else 10 * days
            
            print(f"Fee: ${fee:.2f}")
            
            if user_id is None:
                print("\n" + _t("parking.msg.visitor_permit_note"))
                print(_t("parking.msg.visitor_permit_ready"))
            else:
                print(f"\nNote: Permit linked to user account ID: {user_id}")
            
            print("="*50)
            
            logging.info(f"Parking permit {permit_id} created for {full_name} ({'visitor' if user_id is None else f'user {user_id}'})")
            
        except sqlite3.Error as e:
            logging.error(f"Database error creating permit: {e}")
            print(_t("parking.error.creating_permit") + f": {e}")
            conn.rollback()
        
        conn.close()
        
    except Exception as e:
        logging.error(f"Unexpected error in create_parking_permit: {e}")
        print(f"An unexpected error occurred: {e}")
        print(_t("common.try_again_or_contact_admin"))

def view_parking_permit():
    global auth

    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to view parking permits")
        print(_t("parking.auth.login_required"))
        return

    # Different behavior based on role/permissions
    if not (auth.check_permission('view_any_permit') or auth.check_permission('view_own_permit')):
        logging.warning(f"User {auth.current_user['username']} attempted to view permits without permission")
        print(_t("parking.auth.no_permission_view"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # First, check what columns exist in the parking_permits table
        cursor.execute("PRAGMA table_info(parking_permits)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Adjust query based on available columns
        has_user_id = 'user_id' in column_names
        
        if auth.check_permission('view_any_permit'):
            # Admin or staff - can view any permit
            print("\n" + _t("parking.menu.view_permits") + ":")
            print("1. " + _t("parking.menu.view_all_permits"))
            print("2. " + _t("parking.menu.search_by_permit_id"))
            if has_user_id:
                print("3. " + _t("parking.menu.search_by_user_id"))
                print("4. " + _t("parking.menu.search_by_license_plate"))
                max_choice = 4
            else:
                print("3. " + _t("parking.menu.search_by_license_plate"))
                max_choice = 3
            
            choice = input(f"Enter your choice (1-{max_choice}): ")
            
            if choice == '1':
                # View all permits
                if has_user_id:
                    cursor.execute('''
                    SELECT p.*, v.license_plate, v.make, v.model 
                    FROM parking_permits p
                    LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                    ORDER BY p.issue_date DESC
                    ''')
                else:
                    cursor.execute('''
                    SELECT p.*, v.license_plate, v.make, v.model 
                    FROM parking_permits p
                    LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                    ORDER BY p.issue_date DESC
                    ''')
                
                permits = cursor.fetchall()
                
                if not permits:
                    print(_t("parking.msg.no_permits_found"))
                    conn.close()
                    return
                
                print("\n" + _t("parking.menu.all_permits") + ":")
                print("=" * 100)
                for permit in permits:
                    display_permit_details(permit)
                    print("-" * 100)
                
            elif choice == '2':
                # Search by permit ID
                permit_id = input("Enter permit ID: ")
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.permit_id = ?
                ''', (permit_id,))
                
                permit = cursor.fetchone()
                
                if not permit:
                    print(f"No permit found with ID: {permit_id}")
                else:
                    display_permit_details(permit)
                
            elif choice == '3' and has_user_id:
                # Search by user ID (only if user_id column exists)
                user_id = input("Enter user ID: ")
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.user_id = ?
                ORDER BY p.issue_date DESC
                ''', (user_id,))
                
                permits = cursor.fetchall()
                
                if not permits:
                    print(f"No permits found for user ID: {user_id}")
                else:
                    print(f"\nPermits for User ID: {user_id}")
                    print("=" * 100)
                    for permit in permits:
                        display_permit_details(permit)
                        print("-" * 100)
                
            elif (choice == '4' and has_user_id) or (choice == '3' and not has_user_id):
                # Search by license plate
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE v.license_plate = ?
                ORDER BY p.issue_date DESC
                ''', (license_plate,))
                
                permits = cursor.fetchall()
                
                if not permits:
                    print(f"No permits found for license plate: {license_plate}")
                else:
                    print(f"\nPermits for License Plate: {license_plate}")
                    print("=" * 100)
                    for permit in permits:
                        display_permit_details(permit)
                        print("-" * 100)
            
            else:
                print(_t("common.invalid_choice"))
            
        elif auth.check_permission('view_own_permit'):
            # User - can only view their own permits
            if has_user_id:
                user_id = auth.current_user['id']
                
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.user_id = ?
                ORDER BY p.issue_date DESC
                ''', (user_id,))
                
                permits = cursor.fetchall()
                
                if not permits:
                    print(_t("parking.msg.no_your_permits"))
                else:
                    print("\n" + _t("parking.section.your_permits") + ":")
                    print("=" * 100)
                    for permit in permits:
                        display_permit_details(permit)
                        print("-" * 100)
            else:
                # If no user_id column, search by email or name
                user_email = auth.current_user.get('email', '')
                user_name = f"{auth.current_user.get('first_name', '')} {auth.current_user.get('last_name', '')}"
                
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.email = ? OR p.full_name = ?
                ORDER BY p.issue_date DESC
                ''', (user_email, user_name.strip()))
                
                permits = cursor.fetchall()
                
                if not permits:
                    print(_t("parking.msg.no_your_permits"))
                else:
                    print("\n" + _t("parking.section.your_permits") + ":")
                    print("=" * 100)
                    for permit in permits:
                        display_permit_details(permit)
                        print("-" * 100)
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in view_parking_permit: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in view_parking_permit: {e}")
        print(f"An unexpected error occurred: {e}")

def update_parking_permit():
    global auth

    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to update parking permit")
        print(_t("parking.auth.login_required"))
        return

    if not (auth.check_permission('update_any_permit') or auth.check_permission('update_own_permit')):
        logging.warning(f"User {auth.current_user['username']} attempted to update permit without permission")
        print(_t("parking.auth.no_permission_update"))
        return
    
    # Backup before making changes
    backup_before_operation('update_permit')
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()
        
        # Check if parking_permits table has user_id column
        cursor.execute("PRAGMA table_info(parking_permits)")
        permit_columns = [col[1] for col in cursor.fetchall()]
        has_user_id = 'user_id' in permit_columns
        
        # Identify permit to update
        if auth.check_permission('update_any_permit'):
            # Admin/staff can update any permit
            print("\n" + _t("parking.section.search_permit_update") + ":")
            print("1. " + _t("parking.menu.search_by_permit_id"))
            if has_user_id:
                print("2. " + _t("parking.menu.search_by_user_id"))
                print("3. " + _t("parking.menu.search_by_license_plate"))
                max_choice = 3
            else:
                print("2. " + _t("parking.menu.search_by_license_plate"))
                max_choice = 2
            
            choice = input(f"Enter your choice (1-{max_choice}): ")
            
            permits = []
            
            if choice == '1':
                permit_id = input("Enter permit ID: ")
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.permit_id = ?
                ''', (permit_id,))
                
                permit = cursor.fetchone()
                if permit:
                    permits = [permit]
                
            elif choice == '2' and has_user_id:
                user_id = input("Enter user ID: ")
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.user_id = ?
                ORDER BY p.issue_date DESC
                ''', (user_id,))
                
                permits = cursor.fetchall()
                
            elif (choice == '3' and has_user_id) or (choice == '2' and not has_user_id):
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE v.license_plate = ?
                ORDER BY p.issue_date DESC
                ''', (license_plate,))
                
                permits = cursor.fetchall()
                
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return
            
            if not permits:
                print(_t("parking.msg.no_permits_criteria"))
                conn.close()
                return
            
            # If multiple permits found, let user choose
            selected_permit = None
            if len(permits) == 1:
                selected_permit = permits[0]
            else:
                print("\n" + _t("parking.section.multiple_permits_found") + ":")
                for i, permit in enumerate(permits):
                    if has_user_id and permit['user_id']:
                        print(f"{i+1}. Permit ID: {permit['permit_id']} - {permit['full_name']} (User ID: {permit['user_id']}) - Zone: {permit['zone']}")
                    else:
                        print(f"{i+1}. Permit ID: {permit['permit_id']} - {permit['full_name']} - Zone: {permit['zone']}")
                
                try:
                    idx = int(input("Select a permit (number): ")) - 1
                    if idx < 0 or idx >= len(permits):
                        raise ValueError
                    selected_permit = permits[idx]
                except (ValueError, IndexError):
                    print(_t("common.invalid_selection"))
                    conn.close()
                    return
        
        else:
            # Regular user can only update their own permits
            if has_user_id:
                user_id = auth.current_user['id']
                
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.user_id = ?
                ORDER BY p.issue_date DESC
                ''', (user_id,))
            else:
                # Search by email/name for user's permits
                user_email = auth.current_user.get('email', '')
                user_name = f"{auth.current_user.get('first_name', '')} {auth.current_user.get('last_name', '')}"
                
                cursor.execute('''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.email = ? OR p.full_name = ?
                ORDER BY p.issue_date DESC
                ''', (user_email, user_name.strip()))
            
            permits = cursor.fetchall()
            
            if not permits:
                print(_t("parking.msg.no_permits_to_update"))
                conn.close()
                return
            
            # Let user choose which permit to update
            print("\n" + _t("parking.section.your_permits") + ":")
            for i, permit in enumerate(permits):
                print(f"{i+1}. Permit ID: {permit['permit_id']} - Zone: {permit['zone']} - Status: {permit['active_status']}")
            
            try:
                idx = int(input("Select a permit to update (number): ")) - 1
                if idx < 0 or idx >= len(permits):
                    raise ValueError
                selected_permit = permits[idx]
            except (ValueError, IndexError):
                print(_t("common.invalid_selection"))
                conn.close()
                return
        
        # Display current permit details
        print("\n" + _t("parking.section.current_permit_details") + ":")
        display_permit_details(selected_permit)
        
        # Ask what field to update
        print("\n" + _t("parking.section.what_to_update") + "?")
        
        # Different options based on user role
        if auth.check_permission('update_any_permit'):
            print("1. " + _t("parking.menu.zone"))
            print("2. " + _t("parking.menu.permit_type"))
            print("3. " + _t("parking.menu.end_date"))
            print("4. " + _t("parking.menu.status_active_inactive"))
            print("5. " + _t("parking.menu.vehicle"))
            max_option = 5
        else:
            print("1. " + _t("parking.menu.vehicle"))
            max_option = 1
        
        try:
            option = int(input(f"Enter your choice (1-{max_option}): "))
            if option < 1 or option > max_option:
                raise ValueError
        except ValueError:
            print(_t("common.invalid_option"))
            conn.close()
            return
        
        # Update based on selection
        if option == 1 and auth.check_permission('update_any_permit'):
            # Update zone
            print("\n" + _t("parking.section.available_zones") + ":")
            for zone_code, zone_info in PARKING_ZONES.items():
                print(f"{zone_code}: {zone_info['name']}")
            
            while True:
                new_zone = input("Enter new zone code: ").upper()
                if new_zone in PARKING_ZONES:
                    break
                print(f"Invalid zone. Please enter one of: {', '.join(PARKING_ZONES.keys())}")
            
            cursor.execute(
                'UPDATE parking_permits SET zone = ? WHERE permit_id = ?',
                (new_zone, selected_permit['permit_id'])
            )
            
            updated_fields = {"Zone": new_zone}
            
        elif option == 2 and auth.check_permission('update_any_permit'):
            # Update permit type
            print("\n" + _t("parking.permit.types_available") + ":", ", ".join(PERMIT_TYPES))
            
            while True:
                new_type = input("Enter new permit type: ")
                if new_type in PERMIT_TYPES:
                    break
                print(f"Invalid type. Please enter one of: {', '.join(PERMIT_TYPES)}")
            
            # Adjust end date based on new permit type
            start_date = datetime.strptime(selected_permit['start_date'], '%Y-%m-%d')
            
            if new_type == 'Annual':
                end_date = start_date.replace(year=start_date.year + 1)
            elif new_type == 'Semester':
                end_date = start_date + timedelta(days=120)
            elif new_type == 'Monthly':
                end_date = start_date + timedelta(days=30)
            elif new_type == 'Daily':
                end_date = start_date + timedelta(days=1)
            elif new_type == 'Temporary':
                days = None
                while not days:
                    try:
                        days = int(input("Enter number of days for temporary permit: "))
                        if days <= 0 or days > 30:
                            print(_t("parking.error.days_range"))
                            days = None
                    except ValueError:
                        print(_t("parking.error.enter_valid_number"))
                end_date = start_date + timedelta(days=days)
            
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            cursor.execute(
                'UPDATE parking_permits SET permit_type = ?, end_date = ? WHERE permit_id = ?',
                (new_type, end_date_str, selected_permit['permit_id'])
            )
            
            updated_fields = {"Permit Type": new_type, "End Date": end_date_str}
            
        elif option == 3 and auth.check_permission('update_any_permit'):
            # Update end date
            while True:
                try:
                    new_end_date = input("Enter new end date (YYYY-MM-DD): ")
                    # Validate date format
                    datetime.strptime(new_end_date, '%Y-%m-%d')
                    
                    # Check if end date is after start date
                    start_date = datetime.strptime(selected_permit['start_date'], '%Y-%m-%d')
                    end_date = datetime.strptime(new_end_date, '%Y-%m-%d')
                    
                    if end_date <= start_date:
                        print(_t("parking.error.end_date_after_start"))
                        continue
                    
                    break
                except ValueError:
                    print(_t("parking.error.invalid_date_format"))
            
            cursor.execute(
                'UPDATE parking_permits SET end_date = ? WHERE permit_id = ?',
                (new_end_date, selected_permit['permit_id'])
            )
            
            updated_fields = {"End Date": new_end_date}
            
        elif option == 4 and auth.check_permission('update_any_permit'):
            # Update status
            while True:
                new_status = input("Enter new status (Active/Inactive): ")
                if new_status in ['Active', 'Inactive']:
                    break
                print(_t("parking.error.invalid_status"))
            
            cursor.execute(
                'UPDATE parking_permits SET active_status = ? WHERE permit_id = ?',
                (new_status, selected_permit['permit_id'])
            )
            
            updated_fields = {"Status": new_status}
            
        elif (option == 5 and auth.check_permission('update_any_permit')) or \
             (option == 1 and auth.check_permission('update_own_permit')):
            # Update vehicle
            if has_user_id and selected_permit['user_id']:
                owner_id = selected_permit['user_id']
            else:
                # For visitors or when user_id doesn't exist, we can't easily find their vehicles
                # So we'll allow manual vehicle selection
                owner_id = None
            
            if owner_id:
                # Get vehicles for this user
                cursor.execute('''
                SELECT vehicle_id, license_plate, make, model FROM vehicles WHERE owner_id = ?
                ''', (owner_id,))
                
                vehicles = cursor.fetchall()
                
                if not vehicles:
                    print(_t("parking.msg.no_vehicles_for_user_short"))
                    conn.close()
                    return
                else:
                    print("\n" + _t("parking.section.available_vehicles") + ":")
                    for i, v in enumerate(vehicles):
                        print(f"{i+1}. {v[1]} - {v[2]} {v[3]}")
                    
                    try:
                        idx = int(input("Select a vehicle (number): ")) - 1
                        if idx < 0 or idx >= len(vehicles):
                            raise ValueError
                        new_vehicle_id = vehicles[idx][0]
                        
                        cursor.execute(
                            'UPDATE parking_permits SET vehicle_id = ? WHERE permit_id = ?',
                            (new_vehicle_id, selected_permit['permit_id'])
                        )
                        
                        updated_fields = {"Vehicle": f"{vehicles[idx][2]} {vehicles[idx][3]} ({vehicles[idx][1]})"}
                        
                    except (ValueError, IndexError):
                        print(_t("common.invalid_selection"))
                        conn.close()
                        return
            else:
                # For visitors or when we can't identify the owner, allow manual vehicle ID entry
                print("\n" + _t("parking.section.options") + ":")
                print("1. " + _t("parking.menu.enter_vehicle_id"))
                print("2. " + _t("parking.menu.search_by_license_plate"))
                
                choice = input("Enter choice (1-2): ")
                
                if choice == '1':
                    new_vehicle_id = input("Enter vehicle ID: ")
                    
                    # Verify vehicle exists
                    cursor.execute('SELECT license_plate, make, model FROM vehicles WHERE vehicle_id = ?', (new_vehicle_id,))
                    vehicle = cursor.fetchone()
                    
                    if not vehicle:
                        print(_t("parking.msg.vehicle_not_found"))
                        conn.close()
                        return
                    
                    cursor.execute(
                        'UPDATE parking_permits SET vehicle_id = ? WHERE permit_id = ?',
                        (new_vehicle_id, selected_permit['permit_id'])
                    )
                    
                    updated_fields = {"Vehicle": f"{vehicle[1]} {vehicle[2]} ({vehicle[0]})"}
                    
                elif choice == '2':
                    license_plate = input("Enter license plate: ").upper()
                    
                    cursor.execute('SELECT vehicle_id, make, model FROM vehicles WHERE license_plate = ?', (license_plate,))
                    vehicle = cursor.fetchone()
                    
                    if not vehicle:
                        print(_t("parking.msg.vehicle_not_found"))
                        conn.close()
                        return
                    
                    cursor.execute(
                        'UPDATE parking_permits SET vehicle_id = ? WHERE permit_id = ?',
                        (vehicle[0], selected_permit['permit_id'])
                    )
                    
                    updated_fields = {"Vehicle": f"{vehicle[1]} {vehicle[2]} ({license_plate})"}
                    
                else:
                    print(_t("common.invalid_choice"))
                    conn.close()
                    return
        
        # Commit changes and display updated permit
        conn.commit()
        
        print("\n" + _t("parking.msg.permit_updated") + "!")
        
        # Get updated permit details
        cursor.execute('''
        SELECT p.*, v.license_plate, v.make, v.model 
        FROM parking_permits p
        LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
        WHERE p.permit_id = ?
        ''', (selected_permit['permit_id'],))
        
        updated_permit = cursor.fetchone()
        
        if updated_permit:
            print("\n" + _t("parking.section.updated_permit_details") + ":")
            display_permit_details(updated_permit)
        
        # Send confirmation email (simulated)
        send_update_confirmation(selected_permit['permit_id'], selected_permit['email'], updated_fields)
        
        conn.close()
        logging.info(f"Permit {selected_permit['permit_id']} updated by {auth.current_user['username']}")
        
    except sqlite3.Error as e:
        logging.error(f"Database error in update_parking_permit: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_parking_permit: {e}")
        print(f"An unexpected error occurred: {e}")

def delete_parking_permit():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to delete parking permit")
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('delete_any_permit'):
        logging.warning(f"User {auth.current_user['username']} attempted to delete permit without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    # Backup before making changes
    backup_before_operation('delete_permit')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ask for permit ID to delete
        permit_id = input("Enter the permit ID to delete: ")
        
        # Check if permit exists
        cursor.execute('SELECT * FROM parking_permits WHERE permit_id = ?', (permit_id,))
        permit = cursor.fetchone()
        
        if not permit:
            print(f"No permit found with ID: {permit_id}")
            conn.close()
            return
        
        # Confirm deletion
        print("\n" + _t("parking.section.permit_details") + ":")
        print(f"Permit ID: {permit[0]}")
        print(f"User: {permit[2]} ({permit[1]})")
        print(f"Zone: {permit[4]}")
        print(f"Type: {permit[5]}")
        print(f"Valid: {permit[6]} to {permit[7]}")
        print(f"Status: {permit[8]}")
        
        confirm = input("\nAre you sure you want to delete this permit? (y/n): ")
        
        if confirm.lower() != 'y':
            print(_t("common.deletion_cancelled"))
            conn.close()
            return
        
        # Delete the permit
        cursor.execute('DELETE FROM parking_permits WHERE permit_id = ?', (permit_id,))
        
        conn.commit()
        print(f"Permit {permit_id} has been deleted successfully.")
        logging.info(f"Permit {permit_id} deleted by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in delete_parking_permit: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in delete_parking_permit: {e}")
        print(f"An unexpected error occurred: {e}")


def register_vehicle():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to register vehicle")
        print(_t("parking.auth.login_required"))
        return
    
    if not (auth.check_permission('register_vehicle') or auth.check_permission('register_own_vehicle')):
        logging.warning(f"User {auth.current_user['username']} attempted to register vehicle without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Determine owner ID based on role
        owner_id = None
        
        if auth.check_permission('register_vehicle'):
            # Admin/staff can register for any user
            print("\n" + _t("parking.section.register_vehicle_for") + ":")
            print("1. " + _t("parking.menu.self"))
            print("2. " + _t("parking.menu.another_user"))
            
            choice = input("Enter your choice (1-2): ")
            
            if choice == '1':
                owner_id = auth.current_user['id']
            elif choice == '2':
                search_term = input("Enter user ID, username, or email to search: ")
                cursor.execute('''
                SELECT id, first_name, last_name, email FROM users 
                WHERE id = ? OR username = ? OR email = ?
                ''', (search_term, search_term, search_term))
                
                user = cursor.fetchone()
                if not user:
                    print(_t("parking.error.user_not_found"))
                    conn.close()
                    return
                
                owner_id = user[0]
                print(f"Registering vehicle for: {user[1]} {user[2]} ({user[0]})")
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return
        else:
            # Regular users can only register for themselves
            owner_id = auth.current_user['id']
        
        # Get vehicle details
        try:
            license_plate = input("Enter license plate: ").upper()
            if not license_plate:
                print(_t("parking.error.license_plate_required"))
                conn.close()
                return
            
            # Check if license plate already exists
            cursor.execute('SELECT COUNT(*) FROM vehicles WHERE license_plate = ?', (license_plate,))
            if cursor.fetchone()[0] > 0:
                print(_t("parking.error.license_plate_exists"))
                conn.close()
                return
            
            make = input("Enter vehicle make: ")
            if not make:
                print(_t("parking.error.make_required"))
                conn.close()
                return
            
            model = input("Enter vehicle model: ")
            if not model:
                print(_t("parking.error.model_required"))
                conn.close()
                return
            
            # Ask for vehicle year with validation
            year = None
            while not year:
                try:
                    year_input = input("Enter vehicle year (YYYY): ")
                    year = int(year_input)
                    current_year = datetime.now().year
                    if year < 1900 or year > current_year + 1:
                        print(_t("parking.error.year_range").format(max_year=current_year + 1))
                        year = None
                except ValueError:
                    print(_t("parking.error.year_must_be_number"))
            
            color = input("Enter vehicle color: ")
            
            # Ask for vehicle type with validation
            print(_t("parking.vehicle.types_available") + ":", ", ".join(VEHICLE_TYPES))
            while True:
                vehicle_type = input("Enter vehicle type: ")
                if not vehicle_type:
                    vehicle_type = "Sedan"  # Default
                    break
                if vehicle_type in VEHICLE_TYPES:
                    break
                print(f"Invalid vehicle type. Please choose from {', '.join(VEHICLE_TYPES)}")
            
            registration_state = input("Enter registration state (e.g., NY): ").upper()
            if not registration_state:
                print(_t("parking.error.registration_state_required"))
                conn.close()
                return
            
            # Generate vehicle ID
            cursor.execute('SELECT COUNT(*) FROM vehicles')
            count = cursor.fetchone()[0] + 1
            vehicle_id = f"V{str(count).zfill(6)}"
            
            # Insert vehicle
            cursor.execute(
                'INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (vehicle_id, license_plate, make, model, year, color, vehicle_type, owner_id, registration_state)
            )
            
            conn.commit()
            
            print(f"\nVehicle registered successfully!")
            print(f"Vehicle ID: {vehicle_id}")
            print(f"License Plate: {license_plate}")
            print(f"Make/Model: {make} {model}")
            print(f"Year: {year}")
            print(f"Color: {color}")
            print(f"Type: {vehicle_type}")
            print(f"Registration State: {registration_state}")
            
            logging.info(f"Vehicle {vehicle_id} registered for user {owner_id}")
            
        except Exception as e:
            logging.error(f"Error registering vehicle: {e}")
            print(_t("parking.error.registering_vehicle") + f": {e}")
            conn.rollback()
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in register_vehicle: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in register_vehicle: {e}")
        print(f"An unexpected error occurred: {e}")


def view_vehicle():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to view vehicles")
        print(_t("parking.auth.login_required"))
        return
    
    if not (auth.check_permission('view_any_vehicle') or auth.check_permission('view_own_vehicle')):
        logging.warning(f"User {auth.current_user['username']} attempted to view vehicles without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if auth.check_permission('view_any_vehicle'):
            # Admin or staff - can view any vehicle
            print("\n" + _t("parking.section.view_vehicles") + ":")
            print("1. " + _t("parking.menu.view_all_vehicles"))
            print("2. " + _t("parking.menu.search_by_vehicle_id"))
            print("3. " + _t("parking.menu.search_by_license_plate"))
            print("4. " + _t("parking.menu.search_by_owner_id"))
            
            choice = input("Enter your choice (1-4): ")
            
            if choice == '1':
                # View all vehicles
                cursor.execute('''
                SELECT v.*, u.first_name, u.last_name 
                FROM vehicles v
                LEFT JOIN users u ON v.owner_id = u.id
                ORDER BY v.vehicle_id
                ''')
                
                vehicles = cursor.fetchall()
                
                if not vehicles:
                    print(_t("parking.msg.no_vehicles_found"))
                    conn.close()
                    return
                
                print("\n" + _t("parking.section.all_vehicles") + ":")
                print("=" * 100)
                for vehicle in vehicles:
                    display_vehicle_details(vehicle)
                    print("-" * 100)
                
            elif choice == '2':
                # Search by vehicle ID
                vehicle_id = input("Enter vehicle ID: ")
                cursor.execute('''
                SELECT v.*, u.first_name, u.last_name 
                FROM vehicles v
                LEFT JOIN users u ON v.owner_id = u.id
                WHERE v.vehicle_id = ?
                ''', (vehicle_id,))
                
                vehicle = cursor.fetchone()
                
                if not vehicle:
                    print(f"No vehicle found with ID: {vehicle_id}")
                else:
                    display_vehicle_details(vehicle)
                
            elif choice == '3':
                # Search by license plate
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('''
                SELECT v.*, u.first_name, u.last_name 
                FROM vehicles v
                LEFT JOIN users u ON v.owner_id = u.id
                WHERE v.license_plate = ?
                ''', (license_plate,))
                
                vehicle = cursor.fetchone()
                
                if not vehicle:
                    print(f"No vehicle found with license plate: {license_plate}")
                else:
                    display_vehicle_details(vehicle)
                
            elif choice == '4':
                # Search by owner ID
                owner_id = input("Enter owner ID: ")
                cursor.execute('''
                SELECT v.*, u.first_name, u.last_name 
                FROM vehicles v
                LEFT JOIN users u ON v.owner_id = u.id
                WHERE v.owner_id = ?
                ORDER BY v.vehicle_id
                ''', (owner_id,))
                
                vehicles = cursor.fetchall()
                
                if not vehicles:
                    print(f"No vehicles found for owner ID: {owner_id}")
                else:
                    print(f"\nVehicles for Owner ID: {owner_id}")
                    print("=" * 100)
                    for vehicle in vehicles:
                        display_vehicle_details(vehicle)
                        print("-" * 100)
            
            else:
                print(_t("common.invalid_choice"))
            
        elif auth.check_permission('view_own_vehicle'):
            # User - can only view their own vehicles
            owner_id = auth.current_user['id']
            
            cursor.execute('''
            SELECT v.*, u.first_name, u.last_name 
            FROM vehicles v
            LEFT JOIN users u ON v.owner_id = u.id
            WHERE v.owner_id = ?
            ORDER BY v.vehicle_id
            ''', (owner_id,))
            
            vehicles = cursor.fetchall()
            
            if not vehicles:
                print(_t("parking.msg.no_your_vehicles"))
            else:
                print("\n" + _t("parking.section.your_vehicles") + ":")
                print("=" * 100)
                for vehicle in vehicles:
                    display_vehicle_details(vehicle)
                    print("-" * 100)
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in view_vehicle: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in view_vehicle: {e}")
        print(f"An unexpected error occurred: {e}")


def update_vehicle():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to update vehicle")
        print(_t("parking.auth.login_required"))
        return
    
    if not (auth.check_permission('update_any_vehicle') or auth.check_permission('update_own_vehicle')):
        logging.warning(f"User {auth.current_user['username']} attempted to update vehicle without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    # Backup before making changes
    backup_before_operation('update_vehicle')
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()
        
        # Identify vehicle to update
        if auth.check_permission('update_any_vehicle'):
            # Admin/staff can update any vehicle
            print("\n" + _t("parking.section.search_vehicle_update") + ":")
            print("1. " + _t("parking.menu.search_by_vehicle_id"))
            print("2. " + _t("parking.menu.search_by_license_plate"))
            
            choice = input("Enter your choice (1-2): ")
            
            vehicle = None
            
            if choice == '1':
                vehicle_id = input("Enter vehicle ID: ")
                cursor.execute('SELECT * FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
                vehicle = cursor.fetchone()
                
            elif choice == '2':
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('SELECT * FROM vehicles WHERE license_plate = ?', (license_plate,))
                vehicle = cursor.fetchone()
                
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return
            
            if not vehicle:
                print(_t("parking.msg.no_vehicle_criteria"))
                conn.close()
                return
            
        else:
            # Regular user can only update their own vehicles
            owner_id = auth.current_user['id']
            
            cursor.execute('SELECT * FROM vehicles WHERE owner_id = ?', (owner_id,))
            
            vehicles = cursor.fetchall()
            
            if not vehicles:
                print(_t("parking.msg.no_vehicles_to_update"))
                conn.close()
                return
            
            # Let user choose which vehicle to update
            print("\n" + _t("parking.section.your_vehicles") + ":")
            for i, v in enumerate(vehicles):
                print(f"{i+1}. {v['license_plate']} - {v['make']} {v['model']}")
            
            try:
                idx = int(input("Select a vehicle to update (number): ")) - 1
                if idx < 0 or idx >= len(vehicles):
                    raise ValueError
                vehicle = vehicles[idx]
            except (ValueError, IndexError):
                print(_t("common.invalid_selection"))
                conn.close()
                return
        
        # Display current vehicle details
        print("\n" + _t("parking.section.current_vehicle_details") + ":")
        print(f"Vehicle ID: {vehicle['vehicle_id']}")
        print(f"License Plate: {vehicle['license_plate']}")
        print(f"Make: {vehicle['make']}")
        print(f"Model: {vehicle['model']}")
        print(f"Year: {vehicle['year']}")
        print(f"Color: {vehicle['color']}")
        print(f"Type: {vehicle['vehicle_type']}")
        print(f"Registration State: {vehicle['registration_state']}")
        
        # Ask what field to update
        print("\n" + _t("parking.section.what_to_update") + "?")
        print("1. " + _t("parking.menu.license_plate"))
        print("2. " + _t("parking.menu.make"))
        print("3. " + _t("parking.menu.model"))
        print("4. " + _t("parking.menu.year"))
        print("5. " + _t("parking.menu.color"))
        print("6. " + _t("parking.menu.vehicle_type"))
        print("7. " + _t("parking.menu.registration_state"))
        
        if auth.check_permission('update_any_vehicle'):
            print("8. " + _t("parking.menu.owner"))
            max_option = 8
        else:
            max_option = 7
        
        try:
            option = int(input(f"Enter your choice (1-{max_option}): "))
            if option < 1 or option > max_option:
                raise ValueError
        except ValueError:
            print(_t("common.invalid_option"))
            conn.close()
            return
        
        # Update based on selection
        if option == 1:
            # Update license plate
            new_plate = input("Enter new license plate: ").upper()
            if not new_plate:
                print(_t("parking.error.license_plate_empty"))
                conn.close()
                return
            
            # Check if the new plate already exists (and is not this vehicle)
            cursor.execute(
                'SELECT COUNT(*) FROM vehicles WHERE license_plate = ? AND vehicle_id != ?', 
                (new_plate, vehicle['vehicle_id'])
            )
            if cursor.fetchone()[0] > 0:
                print(_t("parking.error.license_plate_other_vehicle"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE vehicles SET license_plate = ? WHERE vehicle_id = ?',
                (new_plate, vehicle['vehicle_id'])
            )
            
            # Also update any violations that reference this license plate
            cursor.execute(
                'UPDATE parking_violations SET license_plate = ? WHERE vehicle_id = ?',
                (new_plate, vehicle['vehicle_id'])
            )
            
            print(f"License plate updated to: {new_plate}")
            
        elif option == 2:
            # Update make
            new_make = input("Enter new make: ")
            if not new_make:
                print(_t("parking.error.make_empty"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE vehicles SET make = ? WHERE vehicle_id = ?',
                (new_make, vehicle['vehicle_id'])
            )
            
            print(f"Make updated to: {new_make}")
            
        elif option == 3:
            # Update model
            new_model = input("Enter new model: ")
            if not new_model:
                print(_t("parking.error.model_empty"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE vehicles SET model = ? WHERE vehicle_id = ?',
                (new_model, vehicle['vehicle_id'])
            )
            
            print(f"Model updated to: {new_model}")
            
        elif option == 4:
            # Update year
            try:
                new_year = int(input("Enter new year: "))
                current_year = datetime.now().year
                if new_year < 1900 or new_year > current_year + 1:
                    print(_t("parking.error.year_range").format(max_year=current_year + 1))
                    conn.close()
                    return
                
                cursor.execute(
                    'UPDATE vehicles SET year = ? WHERE vehicle_id = ?',
                    (new_year, vehicle['vehicle_id'])
                )
                
                print(f"Year updated to: {new_year}")
                
            except ValueError:
                print(_t("parking.error.year_must_be_number"))
                conn.close()
                return
            
        elif option == 5:
            # Update color
            new_color = input("Enter new color: ")
            if not new_color:
                print(_t("parking.error.color_empty"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE vehicles SET color = ? WHERE vehicle_id = ?',
                (new_color, vehicle['vehicle_id'])
            )
            
            print(f"Color updated to: {new_color}")
            
        elif option == 6:
            # Update vehicle type
            print(_t("parking.vehicle.types_available") + ":", ", ".join(VEHICLE_TYPES))
            while True:
                new_type = input("Enter new vehicle type: ")
                if not new_type:
                    new_type = "Sedan"  # Default
                    break
                if new_type in VEHICLE_TYPES:
                    break
                print(f"Invalid vehicle type. Please choose from {', '.join(VEHICLE_TYPES)}")
            
            cursor.execute(
                'UPDATE vehicles SET vehicle_type = ? WHERE vehicle_id = ?',
                (new_type, vehicle['vehicle_id'])
            )
            
            print(f"Vehicle type updated to: {new_type}")
            
        elif option == 7:
            # Update registration state
            new_state = input("Enter new registration state: ").upper()
            if not new_state:
                print(_t("parking.error.registration_state_empty"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE vehicles SET registration_state = ? WHERE vehicle_id = ?',
                (new_state, vehicle['vehicle_id'])
            )
            
            print(f"Registration state updated to: {new_state}")
            
        elif option == 8 and auth.check_permission('update_any_vehicle'):
            # Update owner (admin only)
            new_owner_id = input("Enter new owner ID: ")
            
            # Verify owner exists
            cursor.execute('SELECT id FROM users WHERE id = ?', (new_owner_id,))
            if not cursor.fetchone():
                print(f"Error: User with ID {new_owner_id} does not exist.")
                conn.close()
                return
            
            cursor.execute(
                'UPDATE vehicles SET owner_id = ? WHERE vehicle_id = ?',
                (new_owner_id, vehicle['vehicle_id'])
            )
            
            print(f"Owner updated to ID: {new_owner_id}")
        
        # Commit changes
        conn.commit()
        
        # Display updated vehicle
        cursor.execute('''
        SELECT v.*, u.first_name, u.last_name 
        FROM vehicles v
        LEFT JOIN users u ON v.owner_id = u.id
        WHERE v.vehicle_id = ?
        ''', (vehicle['vehicle_id'],))
        
        updated_vehicle = cursor.fetchone()
        
        print("\n" + _t("parking.msg.vehicle_updated") + "!")
        print("\n" + _t("parking.section.updated_vehicle_details") + ":")
        display_vehicle_details(updated_vehicle)
        
        logging.info(f"Vehicle {vehicle['vehicle_id']} updated by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in update_vehicle: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_vehicle: {e}")
        print(f"An unexpected error occurred: {e}")


def delete_vehicle():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to delete vehicle")
        print(_t("parking.auth.login_required"))
        return
    
    if not (auth.check_permission('delete_any_vehicle') or auth.check_permission('delete_own_vehicle')):
        logging.warning(f"User {auth.current_user['username']} attempted to delete vehicle without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    # Backup before making changes
    backup_before_operation('delete_vehicle')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        vehicle_id = None
        
        if auth.check_permission('delete_any_vehicle'):
            # Admin/staff can delete any vehicle
            print("\n" + _t("parking.section.search_vehicle_delete") + ":")
            print("1. " + _t("parking.menu.by_vehicle_id"))
            print("2. " + _t("parking.menu.by_license_plate"))
            
            choice = input("Enter your choice (1-2): ")
            
            if choice == '1':
                vehicle_id = input("Enter vehicle ID: ")
            elif choice == '2':
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('SELECT vehicle_id FROM vehicles WHERE license_plate = ?', (license_plate,))
                result = cursor.fetchone()
                if result:
                    vehicle_id = result[0]
                else:
                    print(f"No vehicle found with license plate: {license_plate}")
                    conn.close()
                    return
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return
            
        else:
            # Regular user can only delete their own vehicles
            owner_id = auth.current_user['id']
            
            cursor.execute('SELECT vehicle_id, license_plate, make, model FROM vehicles WHERE owner_id = ?', (owner_id,))
            
            vehicles = cursor.fetchall()
            
            if not vehicles:
                print(_t("parking.msg.no_vehicles_to_delete"))
                conn.close()
                return
            
            # Let user choose which vehicle to delete
            print("\n" + _t("parking.section.your_vehicles") + ":")
            for i, v in enumerate(vehicles):
                print(f"{i+1}. {v[1]} - {v[2]} {v[3]}")
            
            try:
                idx = int(input("Select a vehicle to delete (number): ")) - 1
                if idx < 0 or idx >= len(vehicles):
                    raise ValueError
                vehicle_id = vehicles[idx][0]
            except (ValueError, IndexError):
                print(_t("common.invalid_selection"))
                conn.close()
                return
        
        # Check if vehicle exists
        cursor.execute('''
        SELECT v.*, u.first_name, u.last_name 
        FROM vehicles v
        LEFT JOIN users u ON v.owner_id = u.id
        WHERE v.vehicle_id = ?
        ''', (vehicle_id,))
        
        vehicle = cursor.fetchone()
        
        if not vehicle:
            print(f"No vehicle found with ID: {vehicle_id}")
            conn.close()
            return
        
        # Check if the vehicle is associated with any active permits
        cursor.execute('''
        SELECT permit_id FROM parking_permits 
        WHERE vehicle_id = ? AND active_status = 'Active'
        ''', (vehicle_id,))
        
        active_permits = cursor.fetchall()
        
        if active_permits:
            permit_ids = ", ".join([p[0] for p in active_permits])
            print(f"Error: Vehicle is associated with active permits: {permit_ids}")
            print(_t("parking.msg.delete_permits_first"))
            conn.close()
            return
        
        # Display vehicle details and confirm deletion
        print("\n" + _t("parking.section.vehicle_details") + ":")
        print(f"Vehicle ID: {vehicle[0]}")
        print(f"License Plate: {vehicle[1]}")
        print(f"Make/Model: {vehicle[2]} {vehicle[3]}")
        print(f"Year: {vehicle[4]}")
        print(f"Owner: {vehicle[9]} {vehicle[10]}")
        
        confirm = input("\nAre you sure you want to delete this vehicle? (y/n): ")
        
        if confirm.lower() != 'y':
            print(_t("common.deletion_cancelled"))
            conn.close()
            return
        
        # Update any permits to remove this vehicle
        cursor.execute(
            'UPDATE parking_permits SET vehicle_id = NULL WHERE vehicle_id = ?',
            (vehicle_id,)
        )
        
        # Delete the vehicle
        cursor.execute('DELETE FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
        
        conn.commit()
        print(f"Vehicle {vehicle_id} has been deleted successfully.")
        logging.info(f"Vehicle {vehicle_id} deleted by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in delete_vehicle: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in delete_vehicle: {e}")
        print(f"An unexpected error occurred: {e}")


def record_violation():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to record violation")
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('record_violation'):
        logging.warning(f"User {auth.current_user['username']} attempted to record violation without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get violation details
        print("\n" + _t("parking.section.enter_violation_details") + ":")
        
        # Get license plate
        license_plate = input("Enter vehicle license plate: ").upper()
        if not license_plate:
            print(_t("parking.error.license_plate_required"))
            conn.close()
            return
        
        # Check if the vehicle exists in the system
        cursor.execute('SELECT vehicle_id FROM vehicles WHERE license_plate = ?', (license_plate,))
        vehicle = cursor.fetchone()
        vehicle_id = vehicle[0] if vehicle else None
        
        # Get violation type
        print("\n" + _t("parking.section.violation_types") + ":")
        print("1. " + _t("parking.violation_types.no_permit"))
        print("2. " + _t("parking.violation_types.expired_permit"))
        print("3. " + _t("parking.violation_types.wrong_zone"))
        print("4. " + _t("parking.violation_types.improper_parking"))
        print("5. " + _t("parking.violation_types.blocking_access"))
        print("6. " + _t("parking.violation_types.fire_lane"))
        print("7. " + _t("parking.violation_types.handicap_zone"))
        print("8. " + _t("parking.violation_types.other"))
        
        try:
            type_choice = int(input("Select violation type (1-8): "))
            if type_choice < 1 or type_choice > 8:
                raise ValueError
        except ValueError:
            print(_t("parking.error.invalid_choice_using_other"))
            type_choice = 8
        
        violation_types = [
            "No Permit", "Expired Permit", "Wrong Zone", "Improper Parking",
            "Blocking Access", "Fire Lane", "Handicap Zone", "Other"
        ]
        
        violation_type = violation_types[type_choice - 1]
        
        if type_choice == 8:
            # If "Other", get specific details
            specific_type = input("Specify the violation type: ")
            if specific_type:
                violation_type = specific_type
        
        # Get location
        location = input("Enter violation location: ")
        if not location:
            print(_t("parking.error.location_required"))
            conn.close()
            return
        
        # Set fine amount based on violation type
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
        
        fine_amount = fine_amounts.get(violation_type, 50.00)
        
        # Allow officer to override the fine amount
        override = input(f"Default fine amount is ${fine_amount:.2f}. Override? (y/n): ")
        if override.lower() == 'y':
            try:
                new_amount = float(input("Enter new fine amount: $"))
                if new_amount < 0:
                    print(_t("parking.error.fine_negative_using_default"))
                else:
                    fine_amount = new_amount
            except ValueError:
                print(_t("parking.error.invalid_amount_using_default"))
        
        # Set violation date to current date and time
        violation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Set payment status to "Unpaid"
        payment_status = "Unpaid"
        
        # Set officer ID to the current user's ID
        officer_id = auth.current_user['id']
        
        # Generate violation ID
        cursor.execute('SELECT COUNT(*) FROM parking_violations')
        count = cursor.fetchone()[0] + 1
        violation_id = f"VIO{str(count).zfill(6)}"
        
        # Insert violation record
        cursor.execute(
            'INSERT INTO parking_violations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (violation_id, vehicle_id, license_plate, violation_type, violation_date, 
             fine_amount, payment_status, location, officer_id)
        )
        
        conn.commit()
        
        print("\n" + _t("parking.msg.violation_recorded") + ":")
        print(f"Violation ID: {violation_id}")
        print(f"License Plate: {license_plate}")
        print(f"Type: {violation_type}")
        print(f"Location: {location}")
        print(f"Date/Time: {violation_date}")
        print(f"Fine Amount: ${fine_amount:.2f}")
        print(f"Status: {payment_status}")
        
        logging.info(f"Violation {violation_id} recorded for license plate {license_plate} by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in record_violation: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in record_violation: {e}")
        print(f"An unexpected error occurred: {e}")


def view_violations():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to view violations")
        print(_t("parking.auth.login_required"))
        return
    
    if not (auth.check_permission('view_any_violation') or auth.check_permission('view_own_violation')):
        logging.warning(f"User {auth.current_user['username']} attempted to view violations without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if auth.check_permission('view_any_violation'):
            # Admin or staff - can view any violation
            print("\n" + _t("parking.section.view_violations") + ":")
            print("1. " + _t("parking.menu.view_all_violations"))
            print("2. " + _t("parking.menu.search_by_violation_id"))
            print("3. " + _t("parking.menu.search_by_license_plate"))
            print("4. " + _t("parking.menu.search_by_date"))
            print("5. " + _t("parking.menu.search_by_payment_status"))
            
            choice = input("Enter your choice (1-5): ")
            
            if choice == '1':
                # View all violations
                cursor.execute('''
                SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
                FROM parking_violations v
                LEFT JOIN users u ON v.officer_id = u.id
                ORDER BY v.violation_date DESC
                ''')
                
                violations = cursor.fetchall()
                
                if not violations:
                    print(_t("parking.msg.no_violations_found"))
                    conn.close()
                    return
                
                print("\n" + _t("parking.section.all_violations") + ":")
                print("=" * 100)
                for violation in violations:
                    display_violation_details(violation)
                    print("-" * 100)
                
            elif choice == '2':
                # Search by violation ID
                violation_id = input("Enter violation ID: ")
                cursor.execute('''
                SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
                FROM parking_violations v
                LEFT JOIN users u ON v.officer_id = u.id
                WHERE v.violation_id = ?
                ''', (violation_id,))
                
                violation = cursor.fetchone()
                
                if not violation:
                    print(f"No violation found with ID: {violation_id}")
                else:
                    display_violation_details(violation)
                
            elif choice == '3':
                # Search by license plate
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('''
                SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
                FROM parking_violations v
                LEFT JOIN users u ON v.officer_id = u.id
                WHERE v.license_plate = ?
                ORDER BY v.violation_date DESC
                ''', (license_plate,))
                
                violations = cursor.fetchall()
                
                if not violations:
                    print(f"No violations found for license plate: {license_plate}")
                else:
                    print(f"\nViolations for License Plate: {license_plate}")
                    print("=" * 100)
                    for violation in violations:
                        display_violation_details(violation)
                        print("-" * 100)
                
            elif choice == '4':
                # Search by date
                date = input("Enter date (YYYY-MM-DD): ")
                try:
                    # Validate date format
                    datetime.strptime(date, '%Y-%m-%d')
                    
                    cursor.execute('''
                    SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
                    FROM parking_violations v
                    LEFT JOIN users u ON v.officer_id = u.id
                    WHERE v.violation_date LIKE ?
                    ORDER BY v.violation_date DESC
                    ''', (f'{date}%',))
                    
                    violations = cursor.fetchall()
                    
                    if not violations:
                        print(f"No violations found for date: {date}")
                    else:
                        print(f"\nViolations for Date: {date}")
                        print("=" * 100)
                        for violation in violations:
                            display_violation_details(violation)
                            print("-" * 100)
                
                except ValueError:
                    print(_t("parking.error.invalid_date_format"))
                
            elif choice == '5':
                # Search by payment status
                print(_t("parking.violation.payment_statuses"))
                status = input("Enter payment status: ")
                
                if status not in ['Paid', 'Unpaid', 'Appealed', 'Waived']:
                    print(_t("parking.error.invalid_status_using_unpaid"))
                    status = "Unpaid"
                
                cursor.execute('''
                SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
                FROM parking_violations v
                LEFT JOIN users u ON v.officer_id = u.id
                WHERE v.payment_status = ?
                ORDER BY v.violation_date DESC
                ''', (status,))
                
                violations = cursor.fetchall()
                
                if not violations:
                    print(f"No violations found with status: {status}")
                else:
                    print(f"\nViolations with Status: {status}")
                    print("=" * 100)
                    for violation in violations:
                        display_violation_details(violation)
                        print("-" * 100)
            
            else:
                print(_t("common.invalid_choice"))
            
        elif auth.check_permission('view_own_violation'):
            # User - can only view their own violations
            # First get user's vehicles
            user_id = auth.current_user['id']
            
            cursor.execute('SELECT vehicle_id, license_plate FROM vehicles WHERE owner_id = ?', (user_id,))
            
            vehicles = cursor.fetchall()
            
            if not vehicles:
                print(_t("parking.msg.no_your_vehicles"))
                conn.close()
                return
            
            # Get violations for all user's vehicles
            vehicle_ids = [v[0] for v in vehicles if v[0]]  # Filter out None values
            license_plates = [v[1] for v in vehicles]
            
            # Build query based on available data
            query_parts = []
            params = []
            
            if vehicle_ids:
                placeholders = ','.join(['?'] * len(vehicle_ids))
                query_parts.append(f'v.vehicle_id IN ({placeholders})')
                params.extend(vehicle_ids)
            
            if license_plates:
                placeholders = ','.join(['?'] * len(license_plates))
                query_parts.append(f'v.license_plate IN ({placeholders})')
                params.extend(license_plates)
            
            if query_parts:
                query = f'''
                SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
                FROM parking_violations v
                LEFT JOIN users u ON v.officer_id = u.id
                WHERE {' OR '.join(query_parts)}
                ORDER BY v.violation_date DESC
                '''
                
                cursor.execute(query, params)
                violations = cursor.fetchall()
                
                if not violations:
                    print(_t("parking.msg.no_your_violations"))
                else:
                    print("\n" + _t("parking.section.your_violations") + ":")
                    print("=" * 100)
                    for violation in violations:
                        display_violation_details(violation)
                        print("-" * 100)
            else:
                print(_t("parking.error.unable_to_retrieve_violations"))
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in view_violations: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in view_violations: {e}")
        print(f"An unexpected error occurred: {e}")


def update_violation():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to update violation")
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('update_violation'):
        logging.warning(f"User {auth.current_user['username']} attempted to update violation without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    # Backup before making changes
    backup_before_operation('update_violation')
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()
        
        # Identify violation to update
        violation_id = input("Enter violation ID to update: ")
        
        cursor.execute('''
        SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
        FROM parking_violations v
        LEFT JOIN users u ON v.officer_id = u.id
        WHERE v.violation_id = ?
        ''', (violation_id,))
        
        violation = cursor.fetchone()
        
        if not violation:
            print(f"No violation found with ID: {violation_id}")
            conn.close()
            return
        
        # Display current violation details
        print("\n" + _t("parking.section.current_violation_details") + ":")
        display_violation_details(violation)
        
        # Ask what field to update
        print("\n" + _t("parking.section.what_to_update") + "?")
        print("1. " + _t("parking.menu.violation_type"))
        print("2. " + _t("parking.menu.fine_amount"))
        print("3. " + _t("parking.menu.payment_status"))
        print("4. " + _t("parking.menu.location"))
        
        try:
            option = int(input("Enter your choice (1-4): "))
            if option < 1 or option > 4:
                raise ValueError
        except ValueError:
            print(_t("common.invalid_option"))
            conn.close()
            return
        
        # Update based on selection
        if option == 1:
            # Update violation type
            print("\n" + _t("parking.section.violation_types") + ":")
            print("1. " + _t("parking.violation_types.no_permit"))
            print("2. " + _t("parking.violation_types.expired_permit"))
            print("3. " + _t("parking.violation_types.wrong_zone"))
            print("4. " + _t("parking.violation_types.improper_parking"))
            print("5. " + _t("parking.violation_types.blocking_access"))
            print("6. " + _t("parking.violation_types.fire_lane"))
            print("7. " + _t("parking.violation_types.handicap_zone"))
            print("8. " + _t("parking.violation_types.other"))
            
            try:
                type_choice = int(input("Select new violation type (1-8): "))
                if type_choice < 1 or type_choice > 8:
                    raise ValueError
            except ValueError:
                print(_t("parking.error.invalid_choice_no_changes"))
                conn.close()
                return
            
            violation_types = [
                "No Permit", "Expired Permit", "Wrong Zone", "Improper Parking",
                "Blocking Access", "Fire Lane", "Handicap Zone", "Other"
            ]
            
            new_violation_type = violation_types[type_choice - 1]
            
            if type_choice == 8:
                # If "Other", get specific details
                specific_type = input("Specify the violation type: ")
                if specific_type:
                    new_violation_type = specific_type
            
            cursor.execute(
                'UPDATE parking_violations SET violation_type = ? WHERE violation_id = ?',
                (new_violation_type, violation_id)
            )
            
            print(f"Violation type updated to: {new_violation_type}")
            
        elif option == 2:
            # Update fine amount
            try:
                new_amount = float(input("Enter new fine amount: $"))
                if new_amount < 0:
                    print(_t("parking.error.fine_negative_no_changes"))
                    conn.close()
                    return
                
                cursor.execute(
                    'UPDATE parking_violations SET fine_amount = ? WHERE violation_id = ?',
                    (new_amount, violation_id)
                )
                
                print(f"Fine amount updated to: ${new_amount:.2f}")
                
            except ValueError:
                print(_t("parking.error.invalid_amount_no_changes"))
                conn.close()
                return
            
        elif option == 3:
            # Update payment status
            print(_t("parking.violation.payment_statuses"))
            new_status = input("Enter new payment status: ")
            
            if new_status not in ['Paid', 'Unpaid', 'Appealed', 'Waived']:
                print(_t("parking.error.invalid_status_no_changes"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE parking_violations SET payment_status = ? WHERE violation_id = ?',
                (new_status, violation_id)
            )
            
            print(f"Payment status updated to: {new_status}")
            
        elif option == 4:
            # Update location
            new_location = input("Enter new location: ")
            if not new_location:
                print(_t("parking.error.location_empty"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE parking_violations SET location = ? WHERE violation_id = ?',
                (new_location, violation_id)
            )
            
            print(f"Location updated to: {new_location}")
        
        # Commit changes
        conn.commit()
        
        # Display updated violation
        cursor.execute('''
        SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
        FROM parking_violations v
        LEFT JOIN users u ON v.officer_id = u.id
        WHERE v.violation_id = ?
        ''', (violation_id,))
        
        updated_violation = cursor.fetchone()
        
        print("\n" + _t("parking.msg.violation_updated") + "!")
        print("\n" + _t("parking.section.updated_violation_details") + ":")
        display_violation_details(updated_violation)
        
        logging.info(f"Violation {violation_id} updated by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in update_violation: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_violation: {e}")
        print(f"An unexpected error occurred: {e}")


def delete_violation():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to delete violation")
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('delete_violation'):
        logging.warning(f"User {auth.current_user['username']} attempted to delete violation without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    # Backup before making changes
    backup_before_operation('delete_violation')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ask for violation ID to delete
        violation_id = input("Enter the violation ID to delete: ")
        
        # Check if violation exists
        cursor.execute('''
        SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
        FROM parking_violations v
        LEFT JOIN users u ON v.officer_id = u.id
        WHERE v.violation_id = ?
        ''', (violation_id,))
        
        violation = cursor.fetchone()
        
        if not violation:
            print(f"No violation found with ID: {violation_id}")
            conn.close()
            return
        
        # Display violation details and confirm deletion
        print("\n" + _t("parking.section.violation_details") + ":")
        display_violation_details(violation)
        
        confirm = input("\nAre you sure you want to delete this violation? (y/n): ")
        
        if confirm.lower() != 'y':
            print(_t("common.deletion_cancelled"))
            conn.close()
            return
        
        # Delete the violation
        cursor.execute('DELETE FROM parking_violations WHERE violation_id = ?', (violation_id,))
        
        conn.commit()
        print(f"Violation {violation_id} has been deleted successfully.")
        logging.info(f"Violation {violation_id} deleted by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in delete_violation: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in delete_violation: {e}")
        print(f"An unexpected error occurred: {e}")


def view_parking_lots():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM parking_lots ORDER BY lot_id
        ''')
        
        lots = cursor.fetchall()
        
        if not lots:
            print(_t("parking.msg.no_lots_found"))
            conn.close()
            return
        
        print("\n" + _t("parking.section.all_parking_lots") + ":")
        print("=" * 100)
        
        # Print table header
        print(f"{'Lot ID':<8} {'Lot Name':<25} {'Location':<20} {'Total Spaces':<15} {'Available':<10} {'Zone':<6} {'Hours':<15}")
        print("-" * 100)
        
        for lot in lots:
            print(f"{lot[0]:<8} {lot[1]:<25} {lot[2]:<20} {lot[3]:<15} {lot[4]:<10} {lot[5]:<6} {lot[6]:<15}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in view_parking_lots: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in view_parking_lots: {e}")
        print(f"An unexpected error occurred: {e}")


def add_parking_lot():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('manage_parking_lots'):
        print(_t("parking.auth.no_permission"))
        return
    
    # Backup before making changes
    backup_before_operation('add_lot')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n" + _t("parking.section.enter_lot_details") + ":")
        
        # Generate lot ID
        cursor.execute('SELECT COUNT(*) FROM parking_lots')
        count = cursor.fetchone()[0] + 1
        lot_id = f"L{str(count).zfill(3)}"
        
        # Get lot details
        lot_name = input("Enter lot name: ")
        if not lot_name:
            print(_t("parking.error.lot_name_required"))
            conn.close()
            return
        
        location = input("Enter location: ")
        if not location:
            print(_t("parking.error.location_required"))
            conn.close()
            return
        
        # Get total spaces with validation
        total_spaces = None
        while total_spaces is None:
            try:
                total_spaces = int(input("Enter total number of spaces: "))
                if total_spaces <= 0:
                    print(_t("parking.error.total_spaces_positive"))
                    total_spaces = None
            except ValueError:
                print(_t("parking.error.enter_valid_number"))
        
        # Initialize available spaces to total spaces
        available_spaces = total_spaces
        
        # Get zone with validation
        print("\n" + _t("parking.section.available_zones") + ":")
        for zone_code, zone_info in PARKING_ZONES.items():
            print(f"{zone_code}: {zone_info['name']}")
        
        while True:
            zone = input("Enter zone code: ").upper()
            if zone in PARKING_ZONES:
                break
            print(f"Invalid zone code. Please enter one of: {', '.join(PARKING_ZONES.keys())}")
        
        # Get hours of operation
        hours = input("Enter hours of operation (e.g., '24/7' or '7:00-22:00'): ")
        if not hours:
            hours = "24/7"  # Default
        
        # Insert new lot
        cursor.execute(
            'INSERT INTO parking_lots VALUES (?, ?, ?, ?, ?, ?, ?)',
            (lot_id, lot_name, location, total_spaces, available_spaces, zone, hours)
        )
        
        conn.commit()
        
        print(f"\nParking lot {lot_id} added successfully!")
        print(f"Lot Name: {lot_name}")
        print(f"Location: {location}")
        print(f"Total Spaces: {total_spaces}")
        print(f"Available Spaces: {available_spaces}")
        print(f"Zone: {zone}")
        print(f"Hours: {hours}")
        
        logging.info(f"Parking lot {lot_id} added by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in add_parking_lot: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in add_parking_lot: {e}")
        print(f"An unexpected error occurred: {e}")


def update_parking_lot():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('manage_parking_lots'):
        print(_t("parking.auth.no_permission"))
        return
    
    # Backup before making changes
    backup_before_operation('update_lot')
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()
        
        # View all lots first
        view_parking_lots()
        
        # Get lot ID to update
        lot_id = input("\nEnter lot ID to update: ")
        
        # Check if lot exists
        cursor.execute('SELECT * FROM parking_lots WHERE lot_id = ?', (lot_id,))
        lot = cursor.fetchone()
        
        if not lot:
            print(f"No parking lot found with ID: {lot_id}")
            conn.close()
            return
        
        # Display current lot details
        print("\n" + _t("parking.section.current_lot_details") + ":")
        print(f"Lot ID: {lot['lot_id']}")
        print(f"Lot Name: {lot['lot_name']}")
        print(f"Location: {lot['location']}")
        print(f"Total Spaces: {lot['total_spaces']}")
        print(f"Available Spaces: {lot['available_spaces']}")
        print(f"Zone: {lot['zone']}")
        print(f"Hours: {lot['hours_of_operation']}")
        
        # Ask what field to update
        print("\n" + _t("parking.section.what_to_update") + "?")
        print("1. " + _t("parking.menu.lot_name"))
        print("2. " + _t("parking.menu.location"))
        print("3. " + _t("parking.menu.total_spaces"))
        print("4. " + _t("parking.menu.zone"))
        print("5. " + _t("parking.menu.hours_of_operation"))
        
        try:
            option = int(input("Enter your choice (1-5): "))
            if option < 1 or option > 5:
                raise ValueError
        except ValueError:
            print(_t("common.invalid_option"))
            conn.close()
            return
        
        # Update based on selection
        if option == 1:
            # Update lot name
            new_name = input("Enter new lot name: ")
            if not new_name:
                print(_t("parking.error.lot_name_empty"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE parking_lots SET lot_name = ? WHERE lot_id = ?',
                (new_name, lot_id)
            )
            
            print(f"Lot name updated to: {new_name}")
            
        elif option == 2:
            # Update location
            new_location = input("Enter new location: ")
            if not new_location:
                print(_t("parking.error.location_empty"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE parking_lots SET location = ? WHERE lot_id = ?',
                (new_location, lot_id)
            )
            
            print(f"Location updated to: {new_location}")
            
        elif option == 3:
            # Update total spaces
            try:
                new_total = int(input("Enter new total spaces: "))
                if new_total <= 0:
                    print(_t("parking.error.total_spaces_positive"))
                    conn.close()
                    return
                
                current_available = lot['available_spaces']
                
                # Calculate new available spaces
                if new_total < lot['total_spaces']:
                    # If reducing total spaces, also reduce available spaces if needed
                    occupied = lot['total_spaces'] - current_available
                    new_available = max(0, new_total - occupied)
                else:
                    # If increasing total spaces, add to available spaces
                    new_available = current_available + (new_total - lot['total_spaces'])
                
                cursor.execute(
                    'UPDATE parking_lots SET total_spaces = ?, available_spaces = ? WHERE lot_id = ?',
                    (new_total, new_available, lot_id)
                )
                
                print(f"Total spaces updated to: {new_total}")
                print(f"Available spaces adjusted to: {new_available}")
                
            except ValueError:
                print(_t("parking.error.enter_valid_number"))
                conn.close()
                return
            
        elif option == 4:
            # Update zone
            print("\n" + _t("parking.section.available_zones") + ":")
            for zone_code, zone_info in PARKING_ZONES.items():
                print(f"{zone_code}: {zone_info['name']}")
            
            while True:
                new_zone = input("Enter new zone code: ").upper()
                if new_zone in PARKING_ZONES:
                    break
                print(f"Invalid zone code. Please enter one of: {', '.join(PARKING_ZONES.keys())}")
            
            cursor.execute(
                'UPDATE parking_lots SET zone = ? WHERE lot_id = ?',
                (new_zone, lot_id)
            )
            
            print(f"Zone updated to: {new_zone}")
            
        elif option == 5:
            # Update hours
            new_hours = input("Enter new hours of operation: ")
            if not new_hours:
                print(_t("parking.error.hours_empty"))
                conn.close()
                return
            
            cursor.execute(
                'UPDATE parking_lots SET hours_of_operation = ? WHERE lot_id = ?',
                (new_hours, lot_id)
            )
            
            print(f"Hours updated to: {new_hours}")
        
        # Commit changes
        conn.commit()
        
        logging.info(f"Parking lot {lot_id} updated by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in update_parking_lot: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_parking_lot: {e}")
        print(f"An unexpected error occurred: {e}")


def delete_parking_lot():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('manage_parking_lots'):
        print(_t("parking.auth.no_permission"))
        return
    
    # Backup before making changes
    backup_before_operation('delete_lot')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # View all lots first
        view_parking_lots()
        
        # Get lot ID to delete
        lot_id = input("\nEnter lot ID to delete: ")
        
        # Check if lot exists
        cursor.execute('SELECT * FROM parking_lots WHERE lot_id = ?', (lot_id,))
        lot = cursor.fetchone()
        
        if not lot:
            print(f"No parking lot found with ID: {lot_id}")
            conn.close()
            return
        
        # Check if there are any spaces in this lot
        cursor.execute('SELECT COUNT(*) FROM parking_spaces WHERE lot_id = ?', (lot_id,))
        space_count = cursor.fetchone()[0]
        
        if space_count > 0:
            print(f"Error: Cannot delete lot. There are {space_count} parking spaces associated with this lot.")
            print(_t("parking.error.delete_spaces_first"))
            conn.close()
            return
        
        # Confirm deletion
        confirm = input(f"\nAre you sure you want to delete parking lot {lot_id} ({lot[1]})? (y/n): ")
        
        if confirm.lower() != 'y':
            print(_t("common.deletion_cancelled"))
            conn.close()
            return
        
        # Delete the lot
        cursor.execute('DELETE FROM parking_lots WHERE lot_id = ?', (lot_id,))
        
        conn.commit()
        print(f"Parking lot {lot_id} has been deleted successfully.")
        logging.info(f"Parking lot {lot_id} deleted by {auth.current_user['username']}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in delete_parking_lot: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in delete_parking_lot: {e}")
        print(f"An unexpected error occurred: {e}")


def update_available_spaces():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('manage_parking_lots'):
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # View all lots first
        view_parking_lots()
        
        # Get lot ID to update
        lot_id = input("\nEnter lot ID to update available spaces: ")
        
        # Check if lot exists
        cursor.execute('SELECT * FROM parking_lots WHERE lot_id = ?', (lot_id,))
        lot = cursor.fetchone()
        
        if not lot:
            print(f"No parking lot found with ID: {lot_id}")
            conn.close()
            return
        
        print(f"\nLot: {lot[1]} ({lot[0]})")
        print(f"Total Spaces: {lot[3]}")
        print(f"Currently Available: {lot[4]}")
        
        # Get new available spaces count
        try:
            new_available = int(input("Enter new available spaces count: "))
            if new_available < 0:
                print(_t("parking.error.available_spaces_negative"))
                conn.close()
                return
            
            if new_available > lot[3]:
                print(f"Error: Available spaces cannot exceed total spaces ({lot[3]}).")
                conn.close()
                return
            
            cursor.execute(
                'UPDATE parking_lots SET available_spaces = ? WHERE lot_id = ?',
                (new_available, lot_id)
            )
            
            conn.commit()
            
            print(f"Available spaces updated to {new_available} for lot {lot_id}.")
            logging.info(f"Available spaces for lot {lot_id} updated to {new_available} by {auth.current_user['username']}")
            
        except ValueError:
            print(_t("parking.error.enter_valid_number"))
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in update_available_spaces: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_available_spaces: {e}")
        print(f"An unexpected error occurred: {e}")


def generate_permit_report():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n" + _t("parking.section.permit_status_report") + ":")
        print("1. " + _t("parking.menu.active_permits"))
        print("2. " + _t("parking.menu.expired_permits"))
        print("3. " + _t("parking.menu.permits_by_zone"))
        print("4. " + _t("parking.menu.permits_by_type"))
        print("5. " + _t("parking.menu.all_permits"))
        
        choice = input("Enter your choice (1-5): ")
        
        report_title = ""
        query = ""
        params = ()
        
        if choice == '1':
            report_title = "Active Permits Report"
            query = '''
            SELECT p.*, v.license_plate, v.make, v.model 
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            WHERE p.active_status = 'Active' AND p.end_date >= date('now')
            ORDER BY p.zone, p.end_date
            '''
        elif choice == '2':
            report_title = "Expired Permits Report"
            query = '''
            SELECT p.*, v.license_plate, v.make, v.model 
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            WHERE p.end_date < date('now')
            ORDER BY p.end_date DESC
            '''
        elif choice == '3':
            report_title = "Permits by Zone Report"
            zone = input("Enter zone code (leave blank for all zones): ").upper()
            
            if zone:
                if zone not in PARKING_ZONES:
                    print(f"Invalid zone code. Please enter one of: {', '.join(PARKING_ZONES.keys())}")
                    conn.close()
                    return
                
                report_title = f"Permits for Zone {zone} Report"
                query = '''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.zone = ?
                ORDER BY p.issue_date DESC
                '''
                params = (zone,)
            else:
                query = '''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                ORDER BY p.zone, p.issue_date DESC
                '''
        elif choice == '4':
            report_title = "Permits by Type Report"
            print(_t("parking.permit.types_available") + ":", ", ".join(PERMIT_TYPES))
            permit_type = input("Enter permit type (leave blank for all types): ")
            
            if permit_type:
                if permit_type not in PERMIT_TYPES:
                    print(f"Invalid permit type. Please choose from {', '.join(PERMIT_TYPES)}")
                    conn.close()
                    return
                
                report_title = f"{permit_type} Permits Report"
                query = '''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.permit_type = ?
                ORDER BY p.issue_date DESC
                '''
                params = (permit_type,)
            else:
                query = '''
                SELECT p.*, v.license_plate, v.make, v.model 
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                ORDER BY p.permit_type, p.issue_date DESC
                '''
        elif choice == '5':
            report_title = "All Permits Report"
            query = '''
            SELECT p.*, v.license_plate, v.make, v.model 
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            ORDER BY p.issue_date DESC
            '''
        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return
        
        # Execute query
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        permits = cursor.fetchall()
        
        if not permits:
            print(_t("parking.report.no_permits_found"))
            conn.close()
            return
        
        # Ask for report format
        print("\n" + _t("parking.section.select_report_format") + ":")
        print("1. " + _t("parking.menu.display_on_screen"))
        print("2. " + _t("parking.menu.export_to_csv"))
        print("3. " + _t("parking.menu.export_to_pdf"))
        
        format_choice = input("Enter your choice (1-3): ")
        
        if format_choice == '1':
            # Display on screen
            print(f"\n{report_title}")
            print("=" * 100)
            
            for permit in permits:
                # Display permit details
                display_permit_details(permit)
                print("-" * 100)
                
        elif format_choice == '2':
            # Export to CSV
            filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
            file_path = get_file_path('CSV', filename)
            
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Permit ID', 'User ID', 'Name', 'Email', 'Zone', 'Type',
                    'Start Date', 'End Date', 'Status', 'Vehicle ID', 'Issue Date',
                    'License Plate', 'Vehicle Make', 'Vehicle Model'
                ])
                
                # Write data
                for permit in permits:
                    writer.writerow([
                        permit[0], permit[1], permit[2], permit[3], permit[4],
                        permit[5], permit[6], permit[7], permit[8], permit[9],
                        permit[10], permit[11] if len(permit) > 11 else '', 
                        permit[12] if len(permit) > 12 else '', 
                        permit[13] if len(permit) > 13 else ''
                    ])
            
            print(f"Report exported to {file_path}")
            
        elif format_choice == '3':
            # Export to PDF
            filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            file_path = get_file_path('PDF', filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph(report_title, styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))  # Add some space
            
            # Create table for data
            data = [['Permit ID', 'User', 'Zone', 'Type', 'Valid Period', 'Status', 'Vehicle']]
            
            for permit in permits:
                # Format data for table
                vehicle_info = f"{permit[12]} {permit[13]} ({permit[11]})" if len(permit) > 11 and permit[11] else "N/A"
                valid_period = f"{permit[6]} to {permit[7]}"
                
                data.append([
                    permit[0],  # Permit ID
                    permit[2],  # Name
                    permit[4],  # Zone
                    permit[5],  # Type
                    valid_period,  # Valid Period
                    permit[8],  # Status
                    vehicle_info  # Vehicle
                ])
            
            # Create table
            table = Table(data, colWidths=[60, 80, 40, 60, 100, 50, 120])
            
            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            
            elements.append(table)
            
            # Build the PDF
            doc.build(elements)
            
            print(f"Report exported to {file_path}")
            
        else:
            print(_t("common.invalid_choice"))
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in generate_permit_report: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_permit_report: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_violation_report():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n" + _t("parking.section.violation_summary_report") + ":")
        print("1. " + _t("parking.menu.all_violations"))
        print("2. " + _t("parking.menu.violations_by_type"))
        print("3. " + _t("parking.menu.violations_by_date_range"))
        print("4. " + _t("parking.menu.violations_by_payment_status"))
        print("5. " + _t("parking.menu.violations_by_location"))
        
        choice = input("Enter your choice (1-5): ")
        
        report_title = ""
        query = ""
        params = ()
        
        if choice == '1':
            report_title = "All Violations Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            ORDER BY v.violation_date DESC
            '''
        elif choice == '2':
            report_title = "Violations by Type Report"
            print("\n" + _t("parking.section.common_violation_types") + ":")
            print("1. " + _t("parking.violation_types.no_permit"))
            print("2. " + _t("parking.violation_types.expired_permit"))
            print("3. " + _t("parking.violation_types.wrong_zone"))
            print("4. " + _t("parking.violation_types.improper_parking"))
            print("5. " + _t("parking.violation_types.blocking_access"))
            print("6. " + _t("parking.violation_types.fire_lane"))
            print("7. " + _t("parking.violation_types.handicap_zone"))
            print("8. " + _t("parking.violation_types.other"))
            print("9. " + _t("parking.violation_types.custom"))
            
            type_choice = input("Select violation type (1-9): ")
            
            violation_types = [
                "No Permit", "Expired Permit", "Wrong Zone", "Improper Parking",
                "Blocking Access", "Fire Lane", "Handicap Zone", "Other"
            ]
            
            if type_choice in ['1', '2', '3', '4', '5', '6', '7', '8']:
                violation_type = violation_types[int(type_choice) - 1]
            elif type_choice == '9':
                violation_type = input("Enter specific violation type: ")
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return
            
            report_title = f"{violation_type} Violations Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            WHERE v.violation_type = ?
            ORDER BY v.violation_date DESC
            '''
            params = (violation_type,)
            
        elif choice == '3':
            report_title = "Violations by Date Range Report"
            
            start_date = input("Enter start date (YYYY-MM-DD): ")
            try:
                # Validate date format
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                print(_t("parking.error.invalid_date_format"))
                conn.close()
                return
            
            end_date = input("Enter end date (YYYY-MM-DD): ")
            try:
                # Validate date format
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                print(_t("parking.error.invalid_date_format"))
                conn.close()
                return
            
            report_title = f"Violations from {start_date} to {end_date} Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            WHERE date(v.violation_date) BETWEEN date(?) AND date(?)
            ORDER BY v.violation_date DESC
            '''
            params = (start_date, end_date)
            
        elif choice == '4':
            report_title = "Violations by Payment Status Report"
            print(_t("parking.violation.payment_statuses"))
            status = input("Enter payment status: ")
            
            if status not in ['Paid', 'Unpaid', 'Appealed', 'Waived']:
                print(_t("parking.error.invalid_status_using_unpaid"))
                status = "Unpaid"
            
            report_title = f"{status} Violations Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            WHERE v.payment_status = ?
            ORDER BY v.violation_date DESC
            '''
            params = (status,)
            
        elif choice == '5':
            report_title = "Violations by Location Report"
            location = input("Enter location: ")
            
            report_title = f"Violations at {location} Report"
            query = '''
            SELECT v.*, u.first_name || ' ' || u.last_name as officer_name
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            WHERE v.location LIKE ?
            ORDER BY v.violation_date DESC
            '''
            params = (f"%{location}%",)
            
        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return
        
        # Execute query
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        violations = cursor.fetchall()
        
        if not violations:
            print(_t("parking.report.no_violations_found"))
            conn.close()
            return
        
        # Ask for report format
        print("\n" + _t("parking.section.select_report_format") + ":")
        print("1. " + _t("parking.menu.display_on_screen"))
        print("2. " + _t("parking.menu.export_to_csv"))
        print("3. " + _t("parking.menu.export_to_pdf"))
        
        format_choice = input("Enter your choice (1-3): ")
        
        if format_choice == '1':
            # Display on screen
            print(f"\n{report_title}")
            print("=" * 100)
            
            for violation in violations:
                # Display violation details
                display_violation_details(violation)
                print("-" * 100)
                
        elif format_choice == '2':
            # Export to CSV
            filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
            file_path = get_file_path('CSV', filename)
            
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Violation ID', 'Vehicle ID', 'License Plate', 'Violation Type',
                    'Violation Date', 'Fine Amount', 'Payment Status', 'Location', 'Officer'
                ])
                
                # Write data
                for violation in violations:
                    writer.writerow([
                        violation[0], violation[1], violation[2], violation[3],
                        violation[4], violation[5], violation[6], violation[7], 
                        violation[9] if len(violation) > 9 else violation[8]
                    ])
            
            print(f"Report exported to {file_path}")
            
        elif format_choice == '3':
            # Export to PDF
            filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            file_path = get_file_path('PDF', filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph(report_title, styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))  # Add some space
            
            # Create table for data
            data = [['Violation ID', 'License Plate', 'Type', 'Date', 'Fine', 'Status', 'Location', 'Officer']]
            
            for violation in violations:
                # Format data for table
                fine = f"${violation[5]:.2f}"
                
                data.append([
                    violation[0],  # Violation ID
                    violation[2],  # License Plate
                    violation[3],  # Type
                    violation[4],  # Date
                    fine,  # Fine
                    violation[6],  # Status
                    violation[7],  # Location
                    violation[9] if len(violation) > 9 else 'N/A'   # Officer
                ])
            
            # Create table
            table = Table(data, colWidths=[60, 60, 60, 70, 40, 50, 80, 80])
            
            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (4, 1), (4, -1), 'RIGHT')  # Align fine amount to right
            ]))
            
            elements.append(table)
            
            # Add summary
            elements.append(Paragraph(" ", styles['Normal']))  # Add space
            elements.append(Paragraph("Summary", styles['Heading2']))
            
            # Calculate totals
            total_violations = len(violations)
            total_fines = sum(v[5] for v in violations)
            paid_violations = sum(1 for v in violations if v[6] == 'Paid')
            unpaid_violations = sum(1 for v in violations if v[6] == 'Unpaid')
            
            elements.append(Paragraph(f"Total Violations: {total_violations}", styles['Normal']))
            elements.append(Paragraph(f"Total Fines: ${total_fines:.2f}", styles['Normal']))
            elements.append(Paragraph(f"Paid Violations: {paid_violations}", styles['Normal']))
            elements.append(Paragraph(f"Unpaid Violations: {unpaid_violations}", styles['Normal']))
            
            # Build the PDF
            doc.build(elements)
            
            print(f"Report exported to {file_path}")
            
        else:
            print(_t("common.invalid_choice"))
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in generate_violation_report: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_violation_report: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_compliance_report():
    """Generate a compliance and audit report"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n" + "="*80)
        print(_t("parking.report.compliance_header"))
        print("="*80)
        print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. Permit Compliance
        print("📋 PERMIT COMPLIANCE")
        print("-" * 40)
        
        # Expired permits
        cursor.execute('''
        SELECT COUNT(*) 
        FROM parking_permits 
        WHERE date(end_date) < date('now') AND active_status = 'Active'
        ''')
        expired_active = cursor.fetchone()[0]
        
        # Permits expiring soon (within 30 days)
        cursor.execute('''
        SELECT COUNT(*) 
        FROM parking_permits 
        WHERE date(end_date) BETWEEN date('now') AND date('now', '+30 days')
        AND active_status = 'Active'
        ''')
        expiring_soon = cursor.fetchone()[0]
        
        # Permits without vehicles
        cursor.execute('''
        SELECT COUNT(*) 
        FROM parking_permits 
        WHERE vehicle_id IS NULL AND active_status = 'Active'
        ''')
        no_vehicle = cursor.fetchone()[0]
        
        print(f"⚠️  Expired but Active Permits: {expired_active}")
        print(f"📅 Expiring in 30 Days: {expiring_soon}")
        print(f"🚗 Permits Without Vehicles: {no_vehicle}")
        
        if expired_active > 0:
            print("\n" + _t("parking.section.expired_active_permits") + ":")
            cursor.execute('''
            SELECT permit_id, full_name, zone, end_date
            FROM parking_permits 
            WHERE date(end_date) < date('now') AND active_status = 'Active'
            ORDER BY end_date
            LIMIT 10
            ''')
            
            expired_permits = cursor.fetchall()
            for permit in expired_permits:
                print(f"  • {permit[0]} - {permit[1]} - Zone {permit[2]} - Expired: {permit[3]}")
        print()
        
        # 2. Vehicle Registration Compliance
        print("🚗 VEHICLE REGISTRATION COMPLIANCE")
        print("-" * 40)
        
        # Vehicles without permits
        cursor.execute('''
        SELECT COUNT(DISTINCT v.vehicle_id)
        FROM vehicles v
        LEFT JOIN parking_permits p ON v.vehicle_id = p.vehicle_id AND p.active_status = 'Active'
        WHERE p.vehicle_id IS NULL
        ''')
        vehicles_no_permits = cursor.fetchone()[0]
        
        # Duplicate license plates
        cursor.execute('''
        SELECT license_plate, COUNT(*) as count
        FROM vehicles
        GROUP BY license_plate
        HAVING count > 1
        ''')
        duplicate_plates = cursor.fetchall()
        
        print(f"🎫 Vehicles Without Active Permits: {vehicles_no_permits}")
        print(f"🔄 Duplicate License Plates: {len(duplicate_plates)}")
        
        if duplicate_plates:
            print("\n" + _t("parking.section.duplicate_plates") + ":")
            for plate, count in duplicate_plates:
                print(f"  • {plate}: {count} vehicles")
        print()
        
        # 3. Violation Compliance
        print("🚫 VIOLATION COMPLIANCE")
        print("-" * 40)
        
        # Old unpaid violations
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_violations
        WHERE payment_status = 'Unpaid' 
        AND date(violation_date) < date('now', '-90 days')
        ''')
        old_unpaid = cursor.fetchone()[0]
        
        # High-value unpaid violations
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_violations
        WHERE payment_status = 'Unpaid' AND fine_amount >= 100
        ''')
        high_value_unpaid = cursor.fetchone()[0]
        
        # Repeat offenders
        cursor.execute('''
        SELECT license_plate, COUNT(*) as violation_count
        FROM parking_violations
        WHERE violation_date >= date('now', '-365 days')
        GROUP BY license_plate
        HAVING violation_count >= 5
        ORDER BY violation_count DESC
        ''')
        repeat_offenders = cursor.fetchall()
        
        print(f"⏰ Old Unpaid Violations (90+ days): {old_unpaid}")
        print(f"💰 High-Value Unpaid ($100+): {high_value_unpaid}")
        print(f"🔄 Repeat Offenders (5+ violations): {len(repeat_offenders)}")
        
        if repeat_offenders:
            print("\n" + _t("parking.section.top_repeat_offenders") + ":")
            for plate, count in repeat_offenders[:5]:
                print(f"  • {plate}: {count} violations")
        print()
        
        # 4. Data Integrity Issues
        print("🔍 DATA INTEGRITY ISSUES")
        print("-" * 40)
        
        # Permits with invalid zones
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_permits
        WHERE zone NOT IN ('A', 'B', 'C', 'V', 'H', 'M', 'R')
        ''')
        invalid_zones = cursor.fetchone()[0]
        
        # Violations without corresponding vehicles
        cursor.execute('''
        SELECT COUNT(*)
        FROM parking_violations v
        LEFT JOIN vehicles vh ON v.license_plate = vh.license_plate
        WHERE vh.license_plate IS NULL
        ''')
        violations_no_vehicles = cursor.fetchone()[0]
        
        # Users with missing information
        cursor.execute('''
        SELECT COUNT(*)
        FROM users
        WHERE email IS NULL OR email = '' OR first_name IS NULL OR first_name = ''
        ''')
        incomplete_users = cursor.fetchone()[0]
        
        print(f"🎯 Invalid Permit Zones: {invalid_zones}")
        print(f"🚗 Violations for Unregistered Vehicles: {violations_no_vehicles}")
        print(f"👤 Users with Missing Info: {incomplete_users}")
        print()
        
        # 5. Financial Compliance
        print("💰 FINANCIAL COMPLIANCE")
        print("-" * 40)
        
        # Total outstanding debt
        cursor.execute('''
        SELECT SUM(fine_amount)
        FROM parking_violations
        WHERE payment_status = 'Unpaid'
        ''')
        total_debt = cursor.fetchone()[0] or 0
        
        # Outstanding debt by age
        cursor.execute('''
        SELECT 
            CASE 
                WHEN date(violation_date) >= date('now', '-30 days') THEN '0-30 days'
                WHEN date(violation_date) >= date('now', '-90 days') THEN '31-90 days'
                WHEN date(violation_date) >= date('now', '-365 days') THEN '91-365 days'
                ELSE '365+ days'
            END as age_group,
            COUNT(*) as count,
            SUM(fine_amount) as amount
        FROM parking_violations
        WHERE payment_status = 'Unpaid'
        GROUP BY age_group
        ''')
        
        debt_aging = cursor.fetchall()
        
        print(f"💸 Total Outstanding Debt: ${total_debt:,.2f}")
        print("\n" + _t("parking.section.debt_aging_analysis") + ":")
        print(f"{'Age Group':<15} {'Count':<8} {'Amount':<15}")
        print("-" * 40)
        
        for age, count, amount in debt_aging:
            print(f"{age:<15} {count:<8} ${amount:<14.2f}")
        print()
        
        # 6. Audit Trail
        print("📊 AUDIT SUMMARY")
        print("-" * 40)
        
        # Activity in last 30 days
        cursor.execute('''
        SELECT COUNT(*) FROM parking_permits 
        WHERE date(issue_date) >= date('now', '-30 days')
        ''')
        recent_permits = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) FROM parking_violations 
        WHERE date(violation_date) >= date('now', '-30 days')
        ''')
        recent_violations = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) FROM vehicles 
        WHERE vehicle_id IN (
            SELECT vehicle_id FROM parking_permits 
            WHERE date(issue_date) >= date('now', '-30 days')
        )
        ''')
        recent_vehicles = cursor.fetchone()[0]
        
        print(f"📋 New Permits (30 days): {recent_permits}")
        print(f"🚫 New Violations (30 days): {recent_violations}")
        print(f"🚗 New Vehicles (30 days): {recent_vehicles}")
        print()
        
        # 7. Compliance Score
        print("📈 OVERALL COMPLIANCE SCORE")
        print("-" * 40)
        
        # Calculate compliance score (0-100)
        score = 100
        
        # Deduct points for issues
        if expired_active > 0:
            score -= min(expired_active * 2, 20)  # Max 20 points
        if old_unpaid > 0:
            score -= min(old_unpaid * 1, 15)  # Max 15 points
        if len(repeat_offenders) > 0:
            score -= min(len(repeat_offenders) * 3, 15)  # Max 15 points
        if duplicate_plates:
            score -= min(len(duplicate_plates) * 5, 10)  # Max 10 points
        if violations_no_vehicles > 0:
            score -= min(violations_no_vehicles * 2, 10)  # Max 10 points
        
        score = max(score, 0)  # Ensure score doesn't go below 0
        
        # Determine grade
        if score >= 90:
            grade = "A (Excellent)"
            status = "✅"
        elif score >= 80:
            grade = "B (Good)"
            status = "✅"
        elif score >= 70:
            grade = "C (Fair)"
            status = "⚠️"
        elif score >= 60:
            grade = "D (Poor)"
            status = "❌"
        else:
            grade = "F (Critical)"
            status = "🚨"
        
        print(f"{status} Compliance Score: {score}/100")
        print(f"Grade: {grade}")
        print()
        
        # 8. Action Items
        print("✅ RECOMMENDED ACTIONS")
        print("-" * 40)
        
        actions = []
        
        if expired_active > 0:
            actions.append(f"1. Deactivate {expired_active} expired permits")
        if old_unpaid > 0:
            actions.append(f"2. Follow up on {old_unpaid} old unpaid violations")
        if len(repeat_offenders) > 0:
            actions.append(f"3. Review {len(repeat_offenders)} repeat offenders for escalation")
        if duplicate_plates:
            actions.append(f"4. Resolve {len(duplicate_plates)} duplicate license plate entries")
        if violations_no_vehicles > 0:
            actions.append(f"5. Register {violations_no_vehicles} vehicles with violations")
        if incomplete_users > 0:
            actions.append(f"6. Complete information for {incomplete_users} user records")
        
        if actions:
            for action in actions:
                print(action)
        else:
            print(_t("parking.report.system_compliant"))
        
        print("\n" + "="*80)
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in generate_compliance_report: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_compliance_report: {e}")
        try:
            cursor.execute("SELECT * FROM parking_permits WHERE active_status = 'Active'")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            active_permits = cursor.fetchone()[0]
            
            # Unpaid violations
            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]
            
            # Total unpaid fines
            cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_fines = cursor.fetchone()[0] or 0
            
            print("\n" + _t("parking.section.current_status") + ":")
            print("-" * 50)
            print(f"Active Permits: {active_permits}")
            print(f"Unpaid Violations: {unpaid_violations}")
            print(f"Total Unpaid Fines: ${unpaid_fines:.2f}")
            
            # Usage by role
            cursor.execute('''
            SELECT role, COUNT(*) 
            FROM users 
            GROUP BY role 
            ORDER BY COUNT(*) DESC
            ''')
            
            roles = cursor.fetchall()
            
            print("\n" + _t("parking.section.users_by_role") + ":")
            print("-" * 50)
            for role, count in roles:
                print(f"{role}: {count}")
            
            # Permits by zone
            cursor.execute('''
            SELECT zone, COUNT(*) 
            FROM parking_permits 
            GROUP BY zone 
            ORDER BY COUNT(*) DESC
            ''')
            
            zones = cursor.fetchall()
            
            print("\n" + _t("parking.section.permits_by_zone") + ":")
            print("-" * 50)
            for zone, count in zones:
                zone_name = PARKING_ZONES.get(zone, {}).get('name', 'Unknown')
                print(f"Zone {zone} ({zone_name}): {count}")
        
        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return
        
        # Ask if user wants to export the report
        export = input("\nExport this report? (y/n): ")
        if export.lower() == 'y':
            print("\n" + _t("parking.section.export_format") + ":")
            print("1. " + _t("parking.menu.csv"))
            print("2. " + _t("parking.menu.pdf"))
            
            format_choice = input("Enter your choice (1-2): ")
            
            if format_choice == '1':
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
                file_path = get_file_path('CSV', filename)
                print(f"Report exported to {file_path}")
            elif format_choice == '2':
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                file_path = get_file_path('PDF', filename)
                print(f"Report exported to {file_path}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in generate_user_activity_report: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_user_activity_report: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_analytics_dashboard():
    """Generate a comprehensive analytics dashboard"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if parking_permits table has user_id column
        cursor.execute("PRAGMA table_info(parking_permits)")
        permit_columns = [col[1] for col in cursor.fetchall()]
        has_user_id = 'user_id' in permit_columns
        
        print("\n" + "="*80)
        print(_t("parking.report.analytics_header"))
        print("="*80)
        print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. Key Performance Indicators
        print("📊 KEY PERFORMANCE INDICATORS")
        print("-" * 40)
        
        # Total revenue
        cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Paid'")
        violation_revenue = cursor.fetchone()[0] or 0
        
        # Estimate permit revenue (simplified calculation)
        cursor.execute("SELECT COUNT(*), permit_type, zone FROM parking_permits GROUP BY permit_type, zone")
        permit_revenue = 0
        for count, permit_type, zone in cursor.fetchall():
            if zone in PARKING_ZONES:
                if permit_type == 'Annual':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * count
                elif permit_type == 'Semester':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * 0.6 * count
                else:
                    permit_revenue += 10 * count  # Default
        
        total_revenue = violation_revenue + permit_revenue
        
        cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
        active_permits = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
        unpaid_violations = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Unpaid'")
        unpaid_fines = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(total_spaces), SUM(available_spaces) FROM parking_lots")
        space_data = cursor.fetchone()
        total_spaces = space_data[0] or 0
        available_spaces = space_data[1] or 0
        occupancy_rate = ((total_spaces - available_spaces) / total_spaces * 100) if total_spaces > 0 else 0
        
        print(f"💰 Total Revenue: ${total_revenue:,.2f}")
        print(f"🎫 Active Permits: {active_permits:,}")
        print(f"⚠️  Unpaid Violations: {unpaid_violations:,}")
        print(f"💸 Outstanding Fines: ${unpaid_fines:,.2f}")
        print(f"🏠 Parking Occupancy: {occupancy_rate:.1f}%")
        print()
        
        # 2. Recent Activity (Last 7 Days)
        print("🕒 RECENT ACTIVITY (Last 7 Days)")
        print("-" * 40)
        
        cursor.execute('''
        SELECT COUNT(*) 
        FROM parking_permits 
        WHERE date(issue_date) >= date('now', '-7 days')
        ''')
        new_permits = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) 
        FROM parking_violations 
        WHERE date(violation_date) >= date('now', '-7 days')
        ''')
        new_violations = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) 
        FROM vehicles 
        WHERE vehicle_id IN (
            SELECT DISTINCT vehicle_id FROM parking_permits 
            WHERE date(issue_date) >= date('now', '-7 days')
            AND vehicle_id IS NOT NULL
        )
        ''')
        new_vehicles = cursor.fetchone()[0]
        
        print(f"📋 New Permits Issued: {new_permits}")
        print(f"🚗 New Vehicles Registered: {new_vehicles}")
        print(f"🚫 New Violations Recorded: {new_violations}")
        print()
        
        # 3. Top Violation Types
        print("🚫 TOP VIOLATION TYPES")
        print("-" * 40)
        
        cursor.execute('''
        SELECT violation_type, COUNT(*) as count, SUM(fine_amount) as total_fines
        FROM parking_violations
        GROUP BY violation_type
        ORDER BY count DESC
        LIMIT 5
        ''')
        
        top_violations = cursor.fetchall()
        
        if top_violations:
            print(f"{'Violation Type':<20} {'Count':<8} {'Total Fines':<15}")
            print("-" * 45)
            for vtype, count, fines in top_violations:
                print(f"{vtype:<20} {count:<8} ${fines:<14.2f}")
        else:
            print(_t("parking.report.no_violation_data"))
        print()
        
        # 4. Zone Analysis
        print("🅿️  PARKING ZONE ANALYSIS")
        print("-" * 40)
        
        cursor.execute('''
        SELECT zone, COUNT(*) as permits
        FROM parking_permits
        WHERE active_status = 'Active'
        GROUP BY zone
        ORDER BY permits DESC
        ''')
        
        zone_permits = cursor.fetchall()
        
        if zone_permits:
            print(f"{'Zone':<6} {'Name':<20} {'Active Permits':<15}")
            print("-" * 45)
            for zone, permits in zone_permits:
                zone_name = PARKING_ZONES.get(zone, {}).get('name', 'Unknown')
                print(f"{zone:<6} {zone_name:<20} {permits:<15}")
        else:
            print(_t("parking.report.no_permit_data"))
        print()
        
        # 5. System Health Check
        print("🔍 SYSTEM HEALTH CHECK")
        print("-" * 40)
        
        # Check for expired permits
        cursor.execute('''
        SELECT COUNT(*) 
        FROM parking_permits 
        WHERE date(end_date) < date('now') AND active_status = 'Active'
        ''')
        expired_active = cursor.fetchone()[0]
        
        # Check for duplicate license plates
        cursor.execute('''
        SELECT COUNT(*) FROM (
            SELECT license_plate
            FROM vehicles
            GROUP BY license_plate
            HAVING COUNT(*) > 1
        )
        ''')
        duplicate_plates = cursor.fetchone()[0]
        
        # Check for permits without vehicles
        cursor.execute('''
        SELECT COUNT(*) 
        FROM parking_permits 
        WHERE vehicle_id IS NULL AND active_status = 'Active'
        ''')
        permits_no_vehicle = cursor.fetchone()[0]
        
        issues = []
        if expired_active > 0:
            issues.append(f"⚠️  {expired_active} expired permits still active")
        if duplicate_plates > 0:
            issues.append(f"⚠️  {duplicate_plates} duplicate license plates")
        if permits_no_vehicle > 0:
            issues.append(f"⚠️  {permits_no_vehicle} permits without vehicles")
        
        if issues:
            for issue in issues:
                print(issue)
        else:
            print("✅ No system issues detected")
        
        print("\n" + "="*80)
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in generate_analytics_dashboard: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_analytics_dashboard: {e}")
        print(f"An unexpected error occurred: {e}")
        
def display_permit_details(permit):
    """Display the details of a parking permit - updated to handle missing user_id"""
    # Check if this is a row object or tuple
    if hasattr(permit, 'keys'):  # Row object with column access
        print(f"Permit ID: {permit['permit_id']}")
        
        # Handle user_id if it exists
        if 'user_id' in permit.keys() and permit['user_id']:
            print(f"User: {permit['full_name']} ({permit['user_id']})")
        else:
            print(f"User: {permit['full_name']}")
            
        print(f"Email: {permit['email']}")
        print(f"Zone: {permit['zone']} - {PARKING_ZONES[permit['zone']]['name']}")
        print(f"Type: {permit['permit_type']}")
        print(f"Valid: {permit['start_date']} to {permit['end_date']}")
        print(f"Status: {permit['active_status']}")
        
        # Check if vehicle info is available
        if 'license_plate' in permit.keys() and permit['license_plate']:
            print(f"Vehicle: {permit['make']} {permit['model']} ({permit['license_plate']})")
        elif permit['vehicle_id']:
            print(f"Vehicle ID: {permit['vehicle_id']}")
        else:
            print(_t("parking.vehicle.not_assigned"))
        
        print(f"Issued: {permit['issue_date']}")
    else:  # Tuple access
        print(f"Permit ID: {permit[0]}")
        
        # Try to determine if user_id exists based on tuple length and content
        # Standard format: permit_id, user_id, full_name, email, zone, permit_type, start_date, end_date, active_status, vehicle_id, issue_date
        if len(permit) >= 11:  # Has user_id
            if permit[1] and str(permit[1]).isdigit():  # user_id is numeric
                print(f"User: {permit[2]} ({permit[1]})")
                user_id_offset = 0
            else:  # no user_id, full_name is at position 1
                print(f"User: {permit[1]}")
                user_id_offset = -1
        else:
            print(f"User: {permit[1] if len(permit) > 1 else 'Unknown'}")
            user_id_offset = -1
        
        email_idx = 3 + user_id_offset
        zone_idx = 4 + user_id_offset
        type_idx = 5 + user_id_offset
        start_idx = 6 + user_id_offset
        end_idx = 7 + user_id_offset
        status_idx = 8 + user_id_offset
        vehicle_idx = 9 + user_id_offset
        issue_idx = 10 + user_id_offset
        
        if len(permit) > email_idx:
            print(f"Email: {permit[email_idx]}")
        if len(permit) > zone_idx:
            print(f"Zone: {permit[zone_idx]} - {PARKING_ZONES.get(permit[zone_idx], {}).get('name', 'Unknown')}")
        if len(permit) > type_idx:
            print(f"Type: {permit[type_idx]}")
        if len(permit) > start_idx and len(permit) > end_idx:
            print(f"Valid: {permit[start_idx]} to {permit[end_idx]}")
        if len(permit) > status_idx:
            print(f"Status: {permit[status_idx]}")
        
        # Check if vehicle info is available
        vehicle_info_start = len(permit) - 3  # Last 3 should be license_plate, make, model
        if len(permit) > vehicle_info_start and permit[vehicle_info_start]:
            print(f"Vehicle: {permit[vehicle_info_start + 1]} {permit[vehicle_info_start + 2]} ({permit[vehicle_info_start]})")
        elif len(permit) > vehicle_idx and permit[vehicle_idx]:
            print(f"Vehicle ID: {permit[vehicle_idx]}")
        else:
            print(_t("parking.vehicle.not_assigned"))
        
        if len(permit) > issue_idx:
            print(f"Issued: {permit[issue_idx]}")

def display_vehicle_details(vehicle):
    """Display the details of a vehicle"""
    print(f"Vehicle ID: {vehicle[0]}")
    print(f"License Plate: {vehicle[1]}")
    print(f"Make/Model: {vehicle[2]} {vehicle[3]}")
    print(f"Year: {vehicle[4]}")
    print(f"Color: {vehicle[5]}")
    print(f"Type: {vehicle[6]}")
    print(f"Registration State: {vehicle[8]}")
    
    # Check if owner info is available (from join)
    if len(vehicle) > 9 and vehicle[9] and vehicle[10]:
        print(f"Owner: {vehicle[9]} {vehicle[10]} ({vehicle[7]})")
    else:
        print(f"Owner ID: {vehicle[7]}")


def display_violation_details(violation):
    """Display the details of a parking violation"""
    print(f"Violation ID: {violation[0]}")
    print(f"License Plate: {violation[2]}")
    print(f"Type: {violation[3]}")
    print(f"Date/Time: {violation[4]}")
    print(f"Fine Amount: ${violation[5]:.2f}")
    print(f"Status: {violation[6]}")
    print(f"Location: {violation[7]}")
    
    # Check if officer info is available (from join)
    if len(violation) > 9 and violation[9]:
        print(f"Officer: {violation[9]}")
    else:
        print(f"Officer ID: {violation[8]}")


def get_file_path(file_format, default_filename):
    """Helper function to get file path from user with error handling"""
    while True:
        location_choice = input(f"Where would you like to save the {file_format} file?\n1. Current directory\n2. Custom path\nEnter your choice (1-2): ")
        
        if location_choice == '1':
            # Use current directory
            return os.path.join(os.getcwd(), default_filename)
        elif location_choice == '2':
            # Custom directory
            while True:
                custom_path = input("Enter the full path (including filename): ")
                directory = os.path.dirname(custom_path)
                
                # Check if directory exists or can be created
                if not directory:  # If no directory specified, use current directory
                    return custom_path
                
                if not os.path.exists(directory):
                    try_create = input(f"Directory {directory} does not exist. Create it? (y/n): ")
                    if try_create.lower() == 'y':
                        try:
                            os.makedirs(directory, exist_ok=True)
                            return custom_path
                        except OSError as e:
                            print(_t("parking.error.creating_directory") + f": {e}")
                            continue
                    else:
                        continue
                return custom_path
        else:
            print(_t("parking.error.invalid_choice_1_or_2"))

# Menu Functions

def display_permit_menu():
    global auth
    
    while True:
        print("\n" + _t("parking.section.permit_menu") + ":")
        print("1. " + _t("parking.menu.create_permit"))
        print("2. " + _t("parking.menu.view_permits"))
        print("3. " + _t("parking.menu.update_permit"))
        print("4. " + _t("parking.menu.delete_permit"))
        print("5. " + _t("parking.menu.return_to_main"))
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1' and auth.check_permission('create_permit'):
            create_parking_permit()
        elif choice == '2' and (auth.check_permission('view_any_permit') or auth.check_permission('view_own_permit')):
            view_parking_permit()
        elif choice == '3' and (auth.check_permission('update_any_permit') or auth.check_permission('update_own_permit')):
            update_parking_permit()
        elif choice == '4' and auth.check_permission('delete_any_permit'):
            delete_parking_permit()
        elif choice == '5':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def display_vehicle_menu():
    global auth
    
    while True:
        print("\n" + _t("parking.section.vehicle_menu") + ":")
        print("1. " + _t("parking.menu.register_vehicle"))
        print("2. " + _t("parking.menu.view_vehicles"))
        print("3. " + _t("parking.menu.update_vehicle"))
        print("4. " + _t("parking.menu.delete_vehicle"))
        print("5. " + _t("parking.menu.return_to_main"))
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1' and (auth.check_permission('register_vehicle') or auth.check_permission('register_own_vehicle')):
            register_vehicle()
        elif choice == '2' and (auth.check_permission('view_any_vehicle') or auth.check_permission('view_own_vehicle')):
            view_vehicle()
        elif choice == '3' and (auth.check_permission('update_any_vehicle') or auth.check_permission('update_own_vehicle')):
            update_vehicle()
        elif choice == '4' and (auth.check_permission('delete_any_vehicle') or auth.check_permission('delete_own_vehicle')):
            delete_vehicle()
        elif choice == '5':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def display_violation_menu():
    global auth
    
    while True:
        print("\n" + _t("parking.section.violation_menu") + ":")
        print("1. " + _t("parking.menu.record_violation"))
        print("2. " + _t("parking.menu.view_violations"))
        print("3. " + _t("parking.menu.update_violation"))
        print("4. " + _t("parking.menu.delete_violation"))
        print("5. " + _t("parking.menu.return_to_main"))
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1' and auth.check_permission('record_violation'):
            record_violation()
        elif choice == '2' and (auth.check_permission('view_any_violation') or auth.check_permission('view_own_violation')):
            view_violations()
        elif choice == '3' and auth.check_permission('update_violation'):
            update_violation()
        elif choice == '4' and auth.check_permission('delete_violation'):
            delete_violation()
        elif choice == '5':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def display_lot_menu():
    global auth
    
    while True:
        print("\n" + _t("parking.section.lot_menu") + ":")
        print("1. " + _t("parking.menu.view_parking_lots"))
        print("2. " + _t("parking.menu.add_parking_lot"))
        print("3. " + _t("parking.menu.update_parking_lot"))
        print("4. " + _t("parking.menu.delete_parking_lot"))
        print("5. " + _t("parking.menu.update_available_spaces"))
        print("6. " + _t("parking.menu.return_to_main"))
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            view_parking_lots()
        elif choice == '2' and auth.check_permission('manage_parking_lots'):
            add_parking_lot()
        elif choice == '3' and auth.check_permission('manage_parking_lots'):
            update_parking_lot()
        elif choice == '4' and auth.check_permission('manage_parking_lots'):
            delete_parking_lot()
        elif choice == '5' and auth.check_permission('manage_parking_lots'):
            update_available_spaces()
        elif choice == '6':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))

# Add these functions to parking_management.py

def generate_revenue_report():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n" + _t("parking.section.revenue_report_options") + ":")
        print("1. " + _t("parking.menu.permit_revenue_report"))
        print("2. " + _t("parking.menu.violation_revenue_report"))
        print("3. " + _t("parking.menu.combined_revenue_report"))
        print("4. " + _t("parking.menu.revenue_by_zone"))
        print("5. " + _t("parking.menu.revenue_by_month"))
        
        choice = input("Enter your choice (1-5): ")
        
        report_title = ""
        
        if choice == '1':
            # Permit Revenue Report
            report_title = "Permit Revenue Report"
            
            # Get permits with calculated fees
            cursor.execute('''
            SELECT 
                p.permit_type,
                p.zone,
                COUNT(*) as count,
                p.start_date,
                p.end_date
            FROM parking_permits p
            GROUP BY p.permit_type, p.zone
            ORDER BY p.zone, p.permit_type
            ''')
            
            permit_data = cursor.fetchall()
            
            print(f"\n{report_title}")
            print("=" * 100)
            
            total_revenue = 0
            
            print(f"{'Zone':<6} {'Type':<10} {'Count':<8} {'Unit Fee':<10} {'Total':<15}")
            print("-" * 100)
            
            for permit_type, zone, count, start_date, end_date in permit_data:
                # Calculate fee based on permit type and zone
                if permit_type == 'Annual':
                    unit_fee = PARKING_ZONES[zone]['annual_fee']
                elif permit_type == 'Semester':
                    unit_fee = PARKING_ZONES[zone]['annual_fee'] * 0.6
                elif permit_type == 'Monthly':
                    unit_fee = PARKING_ZONES[zone]['annual_fee'] * 0.15
                elif permit_type == 'Daily':
                    unit_fee = PARKING_ZONES[zone]['hourly_rate'] * 8 if PARKING_ZONES[zone]['hourly_rate'] > 0 else 10
                else:  # Temporary
                    unit_fee = PARKING_ZONES[zone]['hourly_rate'] * 8 if PARKING_ZONES[zone]['hourly_rate'] > 0 else 10
                
                total_fee = unit_fee * count
                total_revenue += total_fee
                
                print(f"{zone:<6} {permit_type:<10} {count:<8} ${unit_fee:<9.2f} ${total_fee:<14.2f}")
            
            print("-" * 100)
            print(f"{'TOTAL REVENUE':<35} ${total_revenue:.2f}")
            
        elif choice == '2':
            # Violation Revenue Report
            report_title = "Violation Revenue Report"
            
            cursor.execute('''
            SELECT 
                violation_type,
                payment_status,
                COUNT(*) as count,
                SUM(fine_amount) as total_fines
            FROM parking_violations
            GROUP BY violation_type, payment_status
            ORDER BY violation_type, payment_status
            ''')
            
            violation_data = cursor.fetchall()
            
            print(f"\n{report_title}")
            print("=" * 100)
            
            total_fines = 0
            paid_fines = 0
            unpaid_fines = 0
            
            print(f"{'Violation Type':<20} {'Status':<10} {'Count':<8} {'Total Fines':<15}")
            print("-" * 100)
            
            for vtype, status, count, total in violation_data:
                print(f"{vtype:<20} {status:<10} {count:<8} ${total:<14.2f}")
                
                total_fines += total
                if status == 'Paid':
                    paid_fines += total
                else:
                    unpaid_fines += total
            
            print("-" * 100)
            print(f"{'Total Fines:':<40} ${total_fines:.2f}")
            print(f"{'Paid Fines:':<40} ${paid_fines:.2f}")
            print(f"{'Unpaid Fines:':<40} ${unpaid_fines:.2f}")
            print(f"{'Collection Rate:':<40} {(paid_fines/total_fines*100) if total_fines > 0 else 0:.1f}%")
            
        elif choice == '3':
            # Combined revenue report
            report_title = "Combined Revenue Report"
            
            print(f"\n{report_title}")
            print("=" * 100)
            
            # Get permit revenue
            cursor.execute('''
            SELECT COUNT(*) as count, permit_type, zone
            FROM parking_permits
            GROUP BY permit_type, zone
            ''')
            
            permit_revenue = 0
            for count, permit_type, zone in cursor.fetchall():
                if permit_type == 'Annual':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * count
                elif permit_type == 'Semester':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * 0.6 * count
                elif permit_type == 'Monthly':
                    permit_revenue += PARKING_ZONES[zone]['annual_fee'] * 0.15 * count
                else:
                    permit_revenue += 10 * count  # Default daily rate
            
            # Get violation revenue
            cursor.execute('''
            SELECT SUM(fine_amount) 
            FROM parking_violations 
            WHERE payment_status = 'Paid'
            ''')
            
            violation_revenue = cursor.fetchone()[0] or 0
            
            print(f"{'Revenue Source':<30} {'Amount':<15}")
            print("-" * 50)
            print(f"{'Parking Permits:':<30} ${permit_revenue:.2f}")
            print(f"{'Paid Violations:':<30} ${violation_revenue:.2f}")
            print("-" * 50)
            print(f"{'TOTAL REVENUE:':<30} ${permit_revenue + violation_revenue:.2f}")
            
        elif choice == '4':
            # Revenue by Zone
            report_title = "Revenue by Zone Report"
            
            print(f"\n{report_title}")
            print("=" * 100)
            
            zone_revenues = {}
            
            # Get permit revenue by zone
            cursor.execute('''
            SELECT zone, permit_type, COUNT(*) as count
            FROM parking_permits
            GROUP BY zone, permit_type
            ''')
            
            for zone, permit_type, count in cursor.fetchall():
                if zone not in zone_revenues:
                    zone_revenues[zone] = {'permits': 0, 'violations': 0}
                
                if permit_type == 'Annual':
                    zone_revenues[zone]['permits'] += PARKING_ZONES[zone]['annual_fee'] * count
                elif permit_type == 'Semester':
                    zone_revenues[zone]['permits'] += PARKING_ZONES[zone]['annual_fee'] * 0.6 * count
                else:
                    zone_revenues[zone]['permits'] += 10 * count
            
            # Get violation revenue by location/zone
            for zone in PARKING_ZONES:
                cursor.execute('''
                SELECT SUM(fine_amount) 
                FROM parking_violations 
                WHERE payment_status = 'Paid' 
                AND location LIKE ?
                ''', (f'%Zone {zone}%',))
                
                revenue = cursor.fetchone()[0] or 0
                if zone not in zone_revenues:
                    zone_revenues[zone] = {'permits': 0, 'violations': 0}
                zone_revenues[zone]['violations'] = revenue
            
            print(f"{'Zone':<6} {'Zone Name':<20} {'Permit Revenue':<15} {'Violation Revenue':<18} {'Total':<15}")
            print("-" * 80)
            
            total_permit_rev = 0
            total_violation_rev = 0
            
            for zone, zone_name in sorted(PARKING_ZONES.items()):
                permits = zone_revenues.get(zone, {}).get('permits', 0)
                violations = zone_revenues.get(zone, {}).get('violations', 0)
                total = permits + violations
                
                total_permit_rev += permits
                total_violation_rev += violations
                
                print(f"{zone:<6} {zone_name['name']:<20} ${permits:<14.2f} ${violations:<17.2f} ${total:<14.2f}")
            
            print("-" * 80)
            print(f"{'TOTAL':<27} ${total_permit_rev:<14.2f} ${total_violation_rev:<17.2f} ${total_permit_rev + total_violation_rev:<14.2f}")
            
        elif choice == '5':
            # Revenue by Month
            start_date = input("Enter start date (YYYY-MM-DD): ")
            end_date = input("Enter end date (YYYY-MM-DD): ")
            
            report_title = f"Revenue by Month Report ({start_date} to {end_date})"
            
            print(f"\n{report_title}")
            print("=" * 100)
            
            # Get monthly permit revenue
            cursor.execute('''
            SELECT 
                strftime('%Y-%m', issue_date) as month,
                permit_type,
                zone,
                COUNT(*) as count
            FROM parking_permits
            WHERE date(issue_date) BETWEEN date(?) AND date(?)
            GROUP BY month, permit_type, zone
            ORDER BY month
            ''', (start_date, end_date))
            
            monthly_data = {}
            
            for month, permit_type, zone, count in cursor.fetchall():
                if month not in monthly_data:
                    monthly_data[month] = {'permits': 0, 'violations': 0}
                
                if permit_type == 'Annual':
                    monthly_data[month]['permits'] += PARKING_ZONES[zone]['annual_fee'] * count
                elif permit_type == 'Semester':
                    monthly_data[month]['permits'] += PARKING_ZONES[zone]['annual_fee'] * 0.6 * count
                else:
                    monthly_data[month]['permits'] += 10 * count
            
            # Get monthly violation revenue
            cursor.execute('''
            SELECT 
                strftime('%Y-%m', violation_date) as month,
                SUM(fine_amount) as total
            FROM parking_violations
            WHERE payment_status = 'Paid'
            AND date(violation_date) BETWEEN date(?) AND date(?)
            GROUP BY month
            ORDER BY month
            ''', (start_date, end_date))
            
            for month, total in cursor.fetchall():
                if month not in monthly_data:
                    monthly_data[month] = {'permits': 0, 'violations': 0}
                monthly_data[month]['violations'] = total
            
            print(f"{'Month':<10} {'Permit Revenue':<15} {'Violation Revenue':<18} {'Total':<15}")
            print("-" * 60)
            
            total_permits = 0
            total_violations = 0
            
            for month in sorted(monthly_data.keys()):
                permits = monthly_data[month]['permits']
                violations = monthly_data[month]['violations']
                total = permits + violations
                
                total_permits += permits
                total_violations += violations
                
                print(f"{month:<10} ${permits:<14.2f} ${violations:<17.2f} ${total:<14.2f}")
            
            print("-" * 60)
            print(f"{'TOTAL':<10} ${total_permits:<14.2f} ${total_violations:<17.2f} ${total_permits + total_violations:<14.2f}")
        
        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return
        
        # Ask if user wants to export the report
        export = input("\nExport this report? (y/n): ")
        if export.lower() == 'y':
            print("\n" + _t("parking.section.export_format") + ":")
            print("1. " + _t("parking.menu.csv"))
            print("2. " + _t("parking.menu.pdf"))
            
            format_choice = input("Enter your choice (1-2): ")
            
            if format_choice == '1':
                # Export to CSV
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
                file_path = get_file_path('CSV', filename)
                print(f"Report exported to {file_path}")
            elif format_choice == '2':
                # Export to PDF
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                file_path = get_file_path('PDF', filename)
                print(f"Report exported to {file_path}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in generate_revenue_report: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_revenue_report: {e}")
        print(f"An unexpected error occurred: {e}")

def generate_user_activity_report():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('generate_reports'):
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if parking_permits table has user_id column
        cursor.execute("PRAGMA table_info(parking_permits)")
        permit_columns = [col[1] for col in cursor.fetchall()]
        has_user_id = 'user_id' in permit_columns
        
        print("\n" + _t("parking.section.user_activity_options") + ":")
        print("1. " + _t("parking.menu.user_parking_history"))
        print("2. " + _t("parking.menu.officer_activity_report"))
        print("3. " + _t("parking.menu.most_active_users"))
        print("4. " + _t("parking.menu.user_violations_history"))
        print("5. " + _t("parking.menu.system_usage_stats"))
        
        choice = input("Enter your choice (1-5): ")
        
        report_title = ""
        
        if choice == '1':
            # User Parking History
            user_id = input("Enter user ID: ")
            
            report_title = f"User Parking History - User {user_id}"
            
            # Get user info
            cursor.execute('''
            SELECT first_name, last_name, email, role
            FROM users
            WHERE id = ?
            ''', (user_id,))
            
            user = cursor.fetchone()
            if not user:
                print(f"No user found with ID: {user_id}")
                conn.close()
                return
            
            print(f"\n{report_title}")
            print("=" * 100)
            print(f"Name: {user[0]} {user[1]}")
            print(f"Email: {user[2]}")
            print(f"Role: {user[3]}")
            print()
            
            # Get permits
            print(_t("parking.permit.permits_header"))
            print("-" * 50)
            
            if has_user_id:
                cursor.execute('''
                SELECT permit_id, zone, permit_type, start_date, end_date, active_status
                FROM parking_permits
                WHERE user_id = ?
                ORDER BY issue_date DESC
                ''', (user_id,))
            else:
                # Fallback to email/name matching
                user_email = user[2]
                user_name = f"{user[0]} {user[1]}"
                cursor.execute('''
                SELECT permit_id, zone, permit_type, start_date, end_date, active_status
                FROM parking_permits
                WHERE email = ? OR full_name = ?
                ORDER BY issue_date DESC
                ''', (user_email, user_name))
            
            permits = cursor.fetchall()
            if permits:
                for permit in permits:
                    print(f"Permit: {permit[0]} - Zone {permit[1]} - {permit[2]} - {permit[3]} to {permit[4]} - {permit[5]}")
            else:
                print(_t("parking.msg.no_permits_found"))
            
            # Get vehicles
            print("\n" + _t("parking.section.registered_vehicles") + ":")
            print("-" * 50)
            
            cursor.execute('''
            SELECT vehicle_id, license_plate, make, model, year
            FROM vehicles
            WHERE owner_id = ?
            ''', (user_id,))
            
            vehicles = cursor.fetchall()
            if vehicles:
                for vehicle in vehicles:
                    print(f"Vehicle: {vehicle[0]} - {vehicle[1]} - {vehicle[2]} {vehicle[3]} ({vehicle[4]})")
            else:
                print(_t("parking.msg.no_vehicles_found"))
            
            # Get violations
            print("\n" + _t("parking.section.violations") + ":")
            print("-" * 50)
            
            cursor.execute('''
            SELECT v.violation_id, v.license_plate, v.violation_type, 
                   v.violation_date, v.fine_amount, v.payment_status
            FROM parking_violations v
            JOIN vehicles vh ON v.license_plate = vh.license_plate
            WHERE vh.owner_id = ?
            ORDER BY v.violation_date DESC
            ''', (user_id,))
            
            violations = cursor.fetchall()
            if violations:
                for violation in violations:
                    print(f"Violation: {violation[0]} - {violation[1]} - {violation[2]} - {violation[3]} - ${violation[4]:.2f} - {violation[5]}")
            else:
                print(_t("parking.msg.no_violations_found"))
            
        elif choice == '2':
            # Officer Activity Report
            officer_id = input("Enter officer ID (leave blank for all officers): ")
            
            if officer_id:
                report_title = f"Officer Activity Report - Officer {officer_id}"
                
                cursor.execute('''
                SELECT 
                    u.first_name || ' ' || u.last_name as officer_name,
                    COUNT(v.violation_id) as total_violations,
                    SUM(v.fine_amount) as total_fines,
                    MIN(v.violation_date) as first_violation,
                    MAX(v.violation_date) as last_violation
                FROM parking_violations v
                JOIN users u ON v.officer_id = u.id
                WHERE v.officer_id = ?
                GROUP BY v.officer_id
                ''', (officer_id,))
            else:
                report_title = "All Officers Activity Report"
                
                cursor.execute('''
                SELECT 
                    u.first_name || ' ' || u.last_name as officer_name,
                    v.officer_id,
                    COUNT(v.violation_id) as total_violations,
                    SUM(v.fine_amount) as total_fines,
                    MIN(v.violation_date) as first_violation,
                    MAX(v.violation_date) as last_violation
                FROM parking_violations v
                JOIN users u ON v.officer_id = u.id
                GROUP BY v.officer_id
                ORDER BY total_violations DESC
                ''')
            
            officers = cursor.fetchall()
            
            print(f"\n{report_title}")
            print("=" * 100)
            
            if officer_id:
                print(f"{'Officer':<25} {'Violations':<12} {'Total Fines':<15} {'First':<12} {'Last':<12}")
                print("-" * 80)
                for officer in officers:
                    print(f"{officer[0]:<25} {officer[1]:<12} ${officer[2]:<14.2f} {officer[3]:<12} {officer[4]:<12}")
            else:
                print(f"{'Officer':<25} {'ID':<8} {'Violations':<12} {'Total Fines':<15} {'First':<12} {'Last':<12}")
                print("-" * 100)
                for officer in officers:
                    print(f"{officer[0]:<25} {officer[1]:<8} {officer[2]:<12} ${officer[3]:<14.2f} {officer[4]:<12} {officer[5]:<12}")
            
        elif choice == '3':
            # Most Active Users
            report_title = "Most Active Users Report"
            
            if has_user_id:
                cursor.execute('''
                SELECT 
                    u.id,
                    u.first_name || ' ' || u.last_name as name,
                    u.role,
                    COUNT(DISTINCT p.permit_id) as permit_count,
                    COUNT(DISTINCT v.vehicle_id) as vehicle_count,
                    COUNT(DISTINCT vl.violation_id) as violation_count
                FROM users u
                LEFT JOIN parking_permits p ON u.id = p.user_id
                LEFT JOIN vehicles v ON u.id = v.owner_id
                LEFT JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
                GROUP BY u.id
                HAVING (permit_count + vehicle_count + violation_count) > 0
                ORDER BY (permit_count + vehicle_count + violation_count) DESC
                LIMIT 20
                ''')
            else:
                # Alternative query without user_id
                cursor.execute('''
                SELECT 
                    u.id,
                    u.first_name || ' ' || u.last_name as name,
                    u.role,
                    COUNT(DISTINCT p.permit_id) as permit_count,
                    COUNT(DISTINCT v.vehicle_id) as vehicle_count,
                    COUNT(DISTINCT vl.violation_id) as violation_count
                FROM users u
                LEFT JOIN parking_permits p ON u.email = p.email OR (u.first_name || ' ' || u.last_name) = p.full_name
                LEFT JOIN vehicles v ON u.id = v.owner_id
                LEFT JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
                GROUP BY u.id
                HAVING (permit_count + vehicle_count + violation_count) > 0
                ORDER BY (permit_count + vehicle_count + violation_count) DESC
                LIMIT 20
                ''')
            
            users = cursor.fetchall()
            
            print(f"\n{report_title}")
            print("=" * 100)
            print(f"{'ID':<8} {'Name':<25} {'Role':<10} {'Permits':<10} {'Vehicles':<10} {'Violations':<12}")
            print("-" * 100)
            
            for user in users:
                print(f"{user[0]:<8} {user[1]:<25} {user[2]:<10} {user[3]:<10} {user[4]:<10} {user[5]:<12}")
            
        elif choice == '4':
            # User Violations History
            report_title = "User Violations History Report"
            
            print("\n" + _t("parking.section.options") + ":")
            print("1. " + _t("parking.menu.by_specific_user"))
            print("2. " + _t("parking.menu.all_users_with_violations"))
            
            sub_choice = input("Enter your choice (1-2): ")
            
            if sub_choice == '1':
                user_id = input("Enter user ID: ")
                
                cursor.execute('''
                SELECT 
                    u.first_name || ' ' || u.last_name as name,
                    vl.violation_id,
                    vl.license_plate,
                    vl.violation_type,
                    vl.violation_date,
                    vl.fine_amount,
                    vl.payment_status
                FROM users u
                JOIN vehicles v ON u.id = v.owner_id
                JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
                WHERE u.id = ?
                ORDER BY vl.violation_date DESC
                ''', (user_id,))
                
                violations = cursor.fetchall()
                
                if violations:
                    print(f"\nViolations for {violations[0][0]}")
                    print("=" * 100)
                    print(f"{'Violation ID':<15} {'License':<12} {'Type':<20} {'Date':<12} {'Fine':<10} {'Status':<10}")
                    print("-" * 100)
                    
                    for v in violations:
                        print(f"{v[1]:<15} {v[2]:<12} {v[3]:<20} {v[4]:<12} ${v[5]:<9.2f} {v[6]:<10}")
                else:
                    print(_t("parking.msg.no_violations_for_user"))
                    
            else:
                cursor.execute('''
                SELECT 
                    u.id,
                    u.first_name || ' ' || u.last_name as name,
                    COUNT(vl.violation_id) as violation_count,
                    SUM(vl.fine_amount) as total_fines,
                    SUM(CASE WHEN vl.payment_status = 'Paid' THEN vl.fine_amount ELSE 0 END) as paid_fines,
                    SUM(CASE WHEN vl.payment_status = 'Unpaid' THEN vl.fine_amount ELSE 0 END) as unpaid_fines
                FROM users u
                JOIN vehicles v ON u.id = v.owner_id
                JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
                GROUP BY u.id
                ORDER BY violation_count DESC
                ''')
                
                users = cursor.fetchall()
                
                print(f"\n{report_title}")
                print("=" * 100)
                print(f"{'ID':<8} {'Name':<25} {'Violations':<12} {'Total Fines':<12} {'Paid':<12} {'Unpaid':<12}")
                print("-" * 100)
                
                for user in users:
                    print(f"{user[0]:<8} {user[1]:<25} {user[2]:<12} ${user[3]:<11.2f} ${user[4]:<11.2f} ${user[5]:<11.2f}")
        
        elif choice == '5':
            # System Usage Statistics
            report_title = "System Usage Statistics"
            
            print(f"\n{report_title}")
            print("=" * 100)
            
            # Total counts
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM parking_permits')
            total_permits = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM vehicles')
            total_vehicles = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM parking_violations')
            total_violations = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM parking_lots')
            total_lots = cursor.fetchone()[0]
            
            print(_t("parking.report.overall_statistics"))
            print("-" * 50)
            print(f"Total Users: {total_users}")
            print(f"Total Permits: {total_permits}")
            print(f"Total Vehicles: {total_vehicles}")
            print(f"Total Violations: {total_violations}")
            print(f"Total Parking Lots: {total_lots}")
            
            # Active permits
            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]
            
            # Unpaid violations
            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]
            
            # Total unpaid fines
            cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_fines = cursor.fetchone()[0] or 0
            
            print("\n" + _t("parking.section.current_status") + ":")
            print("-" * 50)
            print(f"Active Permits: {active_permits}")
            print(f"Unpaid Violations: {unpaid_violations}")
            print(f"Total Unpaid Fines: ${unpaid_fines:.2f}")
            
            # Usage by role
            cursor.execute('''
            SELECT role, COUNT(*) 
            FROM users 
            GROUP BY role 
            ORDER BY COUNT(*) DESC
            ''')
            
            roles = cursor.fetchall()
            
            print("\n" + _t("parking.section.users_by_role") + ":")
            print("-" * 50)
            for role, count in roles:
                print(f"{role}: {count}")
            
            # Permits by zone
            cursor.execute('''
            SELECT zone, COUNT(*) 
            FROM parking_permits 
            GROUP BY zone 
            ORDER BY COUNT(*) DESC
            ''')
            
            zones = cursor.fetchall()
            
            print("\n" + _t("parking.section.permits_by_zone") + ":")
            print("-" * 50)
            for zone, count in zones:
                zone_name = PARKING_ZONES.get(zone, {}).get('name', 'Unknown')
                print(f"Zone {zone} ({zone_name}): {count}")
        
        else:
            print(_t("common.invalid_choice"))
            conn.close()
            return
        
        # Ask if user wants to export the report
        export = input("\nExport this report? (y/n): ")
        if export.lower() == 'y':
            print("\n" + _t("parking.section.export_format") + ":")
            print("1. " + _t("parking.menu.csv"))
            print("2. " + _t("parking.menu.pdf"))
            
            format_choice = input("Enter your choice (1-2): ")
            
            if format_choice == '1':
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
                file_path = get_file_path('CSV', filename)
                print(f"Report exported to {file_path}")
            elif format_choice == '2':
                filename = f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                file_path = get_file_path('PDF', filename)
                print(f"Report exported to {file_path}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in generate_user_activity_report: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in generate_user_activity_report: {e}")
        print(f"An unexpected error occurred: {e}")
        
def export_permits(format_type):
    global auth
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get permits with vehicle info
        cursor.execute('''
        SELECT 
            p.permit_id, p.user_id, p.full_name, p.email, 
            p.zone, p.permit_type, p.start_date, p.end_date, 
            p.active_status, p.issue_date,
            v.license_plate, v.make, v.model, v.year
        FROM parking_permits p
        LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
        ORDER BY p.issue_date DESC
        ''')
        
        permits = cursor.fetchall()
        
        if not permits:
            print(_t("parking.export.no_permits"))
            conn.close()
            return
        
        filename = f"parking_permits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)
        
        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Permit ID', 'User ID', 'Name', 'Email', 'Zone', 
                    'Permit Type', 'Start Date', 'End Date', 'Status', 
                    'Issue Date', 'License Plate', 'Vehicle Make', 'Vehicle Model', 'Year'
                ])
                
                # Write data
                for permit in permits:
                    writer.writerow(permit)
            
            print(f"Permits exported to {file_path}")
            
        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(permits, columns=[
                'Permit ID', 'User ID', 'Name', 'Email', 'Zone', 
                'Permit Type', 'Start Date', 'End Date', 'Status', 
                'Issue Date', 'License Plate', 'Vehicle Make', 'Vehicle Model', 'Year'
            ])
            
            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Permits', index=False)
                
                # Create summary sheet
                summary_df = df.groupby(['Zone', 'Permit Type']).size().reset_index(name='Count')
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            print(f"Permits exported to {file_path}")
            
        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Parking Permits Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))
            
            # Create table data
            data = [['Permit ID', 'Name', 'Zone', 'Type', 'Valid Period', 'Status', 'Vehicle']]
            
            for permit in permits:
                vehicle_info = f"{permit[11]} {permit[12]} ({permit[10]})" if permit[10] else "N/A"
                valid_period = f"{permit[6]} to {permit[7]}"
                
                data.append([
                    permit[0],  # Permit ID
                    permit[2],  # Name
                    permit[4],  # Zone
                    permit[5],  # Type
                    valid_period,
                    permit[8],  # Status
                    vehicle_info
                ])
            
            # Create table
            table = Table(data, colWidths=[60, 100, 40, 60, 100, 50, 100])
            
            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            
            elements.append(table)
            
            # Build the PDF
            doc.build(elements)
            
            print(f"Permits exported to {file_path}")
            
        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("PARKING PERMITS EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for permit in permits:
                    txtfile.write(f"Permit ID: {permit[0]}\n")
                    txtfile.write(f"User: {permit[2]} (ID: {permit[1]})\n")
                    txtfile.write(f"Email: {permit[3]}\n")
                    txtfile.write(f"Zone: {permit[4]} - {PARKING_ZONES[permit[4]]['name']}\n")
                    txtfile.write(f"Type: {permit[5]}\n")
                    txtfile.write(f"Valid: {permit[6]} to {permit[7]}\n")
                    txtfile.write(f"Status: {permit[8]}\n")
                    txtfile.write(f"Issued: {permit[9]}\n")
                    
                    if permit[10]:
                        txtfile.write(f"Vehicle: {permit[11]} {permit[12]} ({permit[10]})\n")
                    else:
                        txtfile.write("Vehicle: Not assigned\n")
                    
                    txtfile.write("-" * 60 + "\n")
            
            print(f"Permits exported to {file_path}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in export_permits: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_permits: {e}")
        print(_t("parking.error.exporting_permits") + f": {e}")


def export_vehicles(format_type):
    global auth
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get vehicles with owner info
        cursor.execute('''
        SELECT 
            v.vehicle_id, v.license_plate, v.make, v.model, 
            v.year, v.color, v.vehicle_type, v.registration_state,
            u.id as owner_id, u.first_name, u.last_name, u.email
        FROM vehicles v
        LEFT JOIN users u ON v.owner_id = u.id
        ORDER BY v.vehicle_id
        ''')
        
        vehicles = cursor.fetchall()
        
        if not vehicles:
            print(_t("parking.export.no_vehicles"))
            conn.close()
            return
        
        filename = f"vehicles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)
        
        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Vehicle ID', 'License Plate', 'Make', 'Model', 'Year', 
                    'Color', 'Type', 'Registration State', 'Owner ID', 
                    'Owner First Name', 'Owner Last Name', 'Owner Email'
                ])
                
                # Write data
                for vehicle in vehicles:
                    writer.writerow(vehicle)
            
            print(f"Vehicles exported to {file_path}")
            
        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(vehicles, columns=[
                'Vehicle ID', 'License Plate', 'Make', 'Model', 'Year', 
                'Color', 'Type', 'Registration State', 'Owner ID', 
                'Owner First Name', 'Owner Last Name', 'Owner Email'
            ])
            
            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Vehicles', index=False)
                
                # Create summary sheet
                summary_data = {
                    'Vehicle Type': df['Type'].value_counts(),
                    'Make': df['Make'].value_counts().head(10),
                    'Registration State': df['Registration State'].value_counts()
                }
                
                for sheet_name, data in summary_data.items():
                    summary_df = pd.DataFrame(data).reset_index()
                    summary_df.columns = [sheet_name, 'Count']
                    summary_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            print(f"Vehicles exported to {file_path}")
            
        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Vehicles Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))
            
            # Create table data
            data = [['Vehicle ID', 'License Plate', 'Make/Model', 'Year', 'Type', 'Owner']]
            
            for vehicle in vehicles:
                owner_info = f"{vehicle[9]} {vehicle[10]}" if vehicle[9] else "N/A"
                
                data.append([
                    vehicle[0],  # Vehicle ID
                    vehicle[1],  # License Plate
                    f"{vehicle[2]} {vehicle[3]}",  # Make/Model
                    vehicle[4],  # Year
                    vehicle[6],  # Type
                    owner_info
                ])
            
            # Create table
            table = Table(data, colWidths=[60, 80, 120, 50, 80, 120])
            
            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            
            elements.append(table)
            
            # Build the PDF
            doc.build(elements)
            
            print(f"Vehicles exported to {file_path}")
            
        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("VEHICLES EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for vehicle in vehicles:
                    txtfile.write(f"Vehicle ID: {vehicle[0]}\n")
                    txtfile.write(f"License Plate: {vehicle[1]}\n")
                    txtfile.write(f"Make/Model: {vehicle[2]} {vehicle[3]}\n")
                    txtfile.write(f"Year: {vehicle[4]}\n")
                    txtfile.write(f"Color: {vehicle[5]}\n")
                    txtfile.write(f"Type: {vehicle[6]}\n")
                    txtfile.write(f"Registration State: {vehicle[7]}\n")
                    
                    if vehicle[9]:
                        txtfile.write(f"Owner: {vehicle[9]} {vehicle[10]} (ID: {vehicle[8]})\n")
                        txtfile.write(f"Owner Email: {vehicle[11]}\n")
                    else:
                        txtfile.write("Owner: Not assigned\n")
                    
                    txtfile.write("-" * 60 + "\n")
            
            print(f"Vehicles exported to {file_path}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in export_vehicles: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_vehicles: {e}")
        print(_t("parking.error.exporting_vehicles") + f": {e}")


def export_violations(format_type):
    global auth
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get violations with officer info
        cursor.execute('''
        SELECT 
            v.violation_id, v.license_plate, v.violation_type,
            v.violation_date, v.fine_amount, v.payment_status,
            v.location, v.vehicle_id,
            u.first_name || ' ' || u.last_name as officer_name
        FROM parking_violations v
        LEFT JOIN users u ON v.officer_id = u.id
        ORDER BY v.violation_date DESC
        ''')
        
        violations = cursor.fetchall()
        
        if not violations:
            print(_t("parking.export.no_violations"))
            conn.close()
            return
        
        filename = f"parking_violations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)
        
        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Violation ID', 'License Plate', 'Violation Type',
                    'Date/Time', 'Fine Amount', 'Payment Status',
                    'Location', 'Vehicle ID', 'Officer'
                ])
                
                # Write data
                for violation in violations:
                    writer.writerow(violation)
            
            print(f"Violations exported to {file_path}")
            
        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(violations, columns=[
                'Violation ID', 'License Plate', 'Violation Type',
                'Date/Time', 'Fine Amount', 'Payment Status',
                'Location', 'Vehicle ID', 'Officer'
            ])
            
            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Violations', index=False)
                
                # Create summary sheets
                summary_data = {
                    'Violation Types': df.groupby('Violation Type')['Fine Amount'].agg(['count', 'sum']),
                    'Payment Status': df.groupby('Payment Status')['Fine Amount'].agg(['count', 'sum']),
                    'Officers': df.groupby('Officer')['Fine Amount'].agg(['count', 'sum'])
                }
                
                for sheet_name, data in summary_data.items():
                    summary_df = data.reset_index()
                    summary_df.columns = [sheet_name.rstrip('s'), 'Count', 'Total Fines']
                    summary_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            print(f"Violations exported to {file_path}")
            
        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Parking Violations Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))
            
            # Create table data
            data = [['Violation ID', 'License Plate', 'Type', 'Date', 'Fine', 'Status', 'Location']]
            
            for violation in violations:
                data.append([
                    violation[0],  # Violation ID
                    violation[1],  # License Plate
                    violation[2][:15] + '...' if len(violation[2]) > 15 else violation[2],  # Type (truncated)
                    violation[3][:10],  # Date only
                    f"${violation[4]:.2f}",  # Fine
                    violation[5],  # Status
                    violation[6][:20] + '...' if len(violation[6]) > 20 else violation[6]  # Location (truncated)
                ])
            
            # Create table
            table = Table(data, colWidths=[60, 70, 80, 60, 50, 60, 120])
            
            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (4, 1), (4, -1), 'RIGHT')  # Right-align fine amounts
            ]))
            
            elements.append(table)
            
            # Build the PDF
            doc.build(elements)
            
            print(f"Violations exported to {file_path}")
            
        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("PARKING VIOLATIONS EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                total_fines = 0
                paid_fines = 0
                unpaid_fines = 0
                
                for violation in violations:
                    txtfile.write(f"Violation ID: {violation[0]}\n")
                    txtfile.write(f"License Plate: {violation[1]}\n")
                    txtfile.write(f"Type: {violation[2]}\n")
                    txtfile.write(f"Date/Time: {violation[3]}\n")
                    txtfile.write(f"Fine Amount: ${violation[4]:.2f}\n")
                    txtfile.write(f"Payment Status: {violation[5]}\n")
                    txtfile.write(f"Location: {violation[6]}\n")
                    txtfile.write(f"Officer: {violation[8]}\n")
                    txtfile.write("-" * 60 + "\n")
                    
                    total_fines += violation[4]
                    if violation[5] == 'Paid':
                        paid_fines += violation[4]
                    else:
                        unpaid_fines += violation[4]
                
                # Add summary
                txtfile.write("\nSUMMARY\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Total Violations: {len(violations)}\n")
                txtfile.write(f"Total Fines: ${total_fines:.2f}\n")
                txtfile.write(f"Paid Fines: ${paid_fines:.2f}\n")
                txtfile.write(f"Unpaid Fines: ${unpaid_fines:.2f}\n")
            
            print(f"Violations exported to {file_path}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in export_violations: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_violations: {e}")
        print(_t("parking.error.exporting_violations") + f": {e}")


def export_parking_lots(format_type):
    global auth
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get parking lots
        cursor.execute('''
        SELECT * FROM parking_lots
        ORDER BY lot_id
        ''')
        
        lots = cursor.fetchall()
        
        if not lots:
            print(_t("parking.export.no_parking_lots"))
            conn.close()
            return
        
        filename = f"parking_lots_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)
        
        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Lot ID', 'Lot Name', 'Location', 'Total Spaces', 
                    'Available Spaces', 'Zone', 'Hours of Operation'
                ])
                
                # Write data
                for lot in lots:
                    writer.writerow(lot)
            
            print(f"Parking lots exported to {file_path}")
            
        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(lots, columns=[
                'Lot ID', 'Lot Name', 'Location', 'Total Spaces', 
                'Available Spaces', 'Zone', 'Hours of Operation'
            ])
            
            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Parking Lots', index=False)
                
                # Create occupancy summary
                df['Occupied Spaces'] = df['Total Spaces'] - df['Available Spaces']
                df['Occupancy %'] = (df['Occupied Spaces'] / df['Total Spaces'] * 100).round(1)
                
                summary_df = df[['Lot ID', 'Lot Name', 'Total Spaces', 'Occupied Spaces', 'Available Spaces', 'Occupancy %']]
                summary_df.to_excel(writer, sheet_name='Occupancy Summary', index=False)
                
                # Zone summary
                zone_summary = df.groupby('Zone').agg({
                    'Total Spaces': 'sum',
                    'Available Spaces': 'sum'
                }).reset_index()
                zone_summary['Occupied Spaces'] = zone_summary['Total Spaces'] - zone_summary['Available Spaces']
                zone_summary['Occupancy %'] = (zone_summary['Occupied Spaces'] / zone_summary['Total Spaces'] * 100).round(1)
                zone_summary.to_excel(writer, sheet_name='Zone Summary', index=False)
            
            print(f"Parking lots exported to {file_path}")
            
        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Parking Lots Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))
            
            # Create table data
            data = [['Lot ID', 'Lot Name', 'Location', 'Total', 'Available', 'Zone', 'Hours']]
            
            for lot in lots:
                data.append([
                    lot[0],  # Lot ID
                    lot[1],  # Lot Name
                    lot[2],  # Location
                    lot[3],  # Total Spaces
                    lot[4],  # Available Spaces
                    lot[5],  # Zone
                    lot[6]   # Hours
                ])
            
            # Create table
            table = Table(data, colWidths=[50, 100, 100, 50, 60, 40, 100])
            
            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (3, 1), (4, -1), 'CENTER')  # Center numeric columns
            ]))
            
            elements.append(table)
            
            # Add summary
            elements.append(Paragraph(" ", styles['Normal']))
            elements.append(Paragraph("Summary", styles['Heading2']))
            
            total_spaces = sum(lot[3] for lot in lots)
            total_available = sum(lot[4] for lot in lots)
            total_occupied = total_spaces - total_available
            occupancy_rate = (total_occupied / total_spaces * 100) if total_spaces > 0 else 0
            
            summary_text = f"""
            Total Parking Lots: {len(lots)}<br/>
            Total Spaces: {total_spaces}<br/>
            Occupied Spaces: {total_occupied}<br/>
            Available Spaces: {total_available}<br/>
            Overall Occupancy Rate: {occupancy_rate:.1f}%
            """
            
            elements.append(Paragraph(summary_text, styles['Normal']))
            
            # Build the PDF
            doc.build(elements)
            
            print(f"Parking lots exported to {file_path}")
            
        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("PARKING LOTS EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                total_spaces = 0
                total_available = 0
                
                for lot in lots:
                    txtfile.write(f"Lot ID: {lot[0]}\n")
                    txtfile.write(f"Lot Name: {lot[1]}\n")
                    txtfile.write(f"Location: {lot[2]}\n")
                    txtfile.write(f"Total Spaces: {lot[3]}\n")
                    txtfile.write(f"Available Spaces: {lot[4]}\n")
                    txtfile.write(f"Zone: {lot[5]} - {PARKING_ZONES[lot[5]]['name']}\n")
                    txtfile.write(f"Hours of Operation: {lot[6]}\n")
                    
                    occupancy = ((lot[3] - lot[4]) / lot[3] * 100) if lot[3] > 0 else 0
                    txtfile.write(f"Occupancy Rate: {occupancy:.1f}%\n")
                    txtfile.write("-" * 60 + "\n")
                    
                    total_spaces += lot[3]
                    total_available += lot[4]
                
                # Add summary
                txtfile.write("\nSUMMARY\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Total Parking Lots: {len(lots)}\n")
                txtfile.write(f"Total Spaces: {total_spaces}\n")
                txtfile.write(f"Total Available: {total_available}\n")
                txtfile.write(f"Total Occupied: {total_spaces - total_available}\n")
                
                overall_occupancy = ((total_spaces - total_available) / total_spaces * 100) if total_spaces > 0 else 0
                txtfile.write(f"Overall Occupancy Rate: {overall_occupancy:.1f}%\n")
            
            print(f"Parking lots exported to {file_path}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in export_parking_lots: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_parking_lots: {e}")
        print(_t("parking.error.exporting_lots") + f": {e}")


def export_users(format_type):
    global auth
    
    # Check permission
    if not auth or not auth.current_user:
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('export_data'):
        print(_t("parking.auth.no_permission"))
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if parking_permits table has user_id column
        cursor.execute("PRAGMA table_info(parking_permits)")
        permit_columns = [col[1] for col in cursor.fetchall()]
        has_user_id = 'user_id' in permit_columns
        
        # Get users with parking-related data
        if has_user_id:
            # Original query with user_id
            cursor.execute('''
            SELECT 
                u.id, u.username, u.first_name, u.last_name, u.email, u.role,
                COUNT(DISTINCT p.permit_id) as permit_count,
                COUNT(DISTINCT v.vehicle_id) as vehicle_count,
                COUNT(DISTINCT vl.violation_id) as violation_count,
                SUM(CASE WHEN vl.payment_status = 'Unpaid' THEN vl.fine_amount ELSE 0 END) as unpaid_fines
            FROM users u
            LEFT JOIN parking_permits p ON u.id = p.user_id
            LEFT JOIN vehicles v ON u.id = v.owner_id
            LEFT JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
            GROUP BY u.id
            ORDER BY u.last_name, u.first_name
            ''')
        else:
            # Alternative query without user_id - match by email/name
            cursor.execute('''
            SELECT 
                u.id, u.username, u.first_name, u.last_name, u.email, u.role,
                COUNT(DISTINCT p.permit_id) as permit_count,
                COUNT(DISTINCT v.vehicle_id) as vehicle_count,
                COUNT(DISTINCT vl.violation_id) as violation_count,
                SUM(CASE WHEN vl.payment_status = 'Unpaid' THEN vl.fine_amount ELSE 0 END) as unpaid_fines
            FROM users u
            LEFT JOIN parking_permits p ON u.email = p.email OR (u.first_name || ' ' || u.last_name) = p.full_name
            LEFT JOIN vehicles v ON u.id = v.owner_id
            LEFT JOIN parking_violations vl ON v.vehicle_id = vl.vehicle_id
            GROUP BY u.id
            ORDER BY u.last_name, u.first_name
            ''')
        
        users = cursor.fetchall()
        
        if not users:
            print(_t("parking.export.no_users"))
            conn.close()
            return
        
        filename = f"parking_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path = get_file_path(format_type.upper(), filename)
        
        if format_type == 'csv':
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'User ID', 'Username', 'First Name', 'Last Name', 'Email', 'Role',
                    'Permits', 'Vehicles', 'Violations', 'Unpaid Fines'
                ])
                
                # Write data
                for user in users:
                    writer.writerow(user)
            
            print(f"Users exported to {file_path}")
            
        elif format_type == 'excel':
            # Create DataFrame
            df = pd.DataFrame(users, columns=[
                'User ID', 'Username', 'First Name', 'Last Name', 'Email', 'Role',
                'Permits', 'Vehicles', 'Violations', 'Unpaid Fines'
            ])
            
            # Write to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Users', index=False)
                
                # Create role summary
                role_summary = df.groupby('Role').agg({
                    'User ID': 'count',
                    'Permits': 'sum',
                    'Vehicles': 'sum',
                    'Violations': 'sum',
                    'Unpaid Fines': 'sum'
                }).reset_index()
                role_summary.columns = ['Role', 'User Count', 'Total Permits', 'Total Vehicles', 'Total Violations', 'Total Unpaid Fines']
                role_summary.to_excel(writer, sheet_name='Role Summary', index=False)
            
            print(f"Users exported to {file_path}")
            
        elif format_type == 'pdf':
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Parking System Users Export", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Paragraph(" ", styles['Normal']))
            
            # Create table data
            data = [['ID', 'Name', 'Username', 'Role', 'Permits', 'Vehicles', 'Violations', 'Unpaid']]
            
            for user in users:
                data.append([
                    user[0],  # ID
                    f"{user[2]} {user[3]}",  # Name
                    user[1],  # Username
                    user[5],  # Role
                    user[6],  # Permits
                    user[7],  # Vehicles
                    user[8],  # Violations
                    f"${user[9]:.2f}" if user[9] else "$0.00"  # Unpaid fines
                ])
            
            # Create table
            table = Table(data, colWidths=[40, 100, 80, 60, 50, 50, 60, 60])
            
            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (4, 1), (7, -1), 'CENTER')  # Center numeric columns
            ]))
            
            elements.append(table)
            
            # Build the PDF
            doc.build(elements)
            
            print(f"Users exported to {file_path}")
            
        elif format_type == 'txt':
            with open(file_path, 'w') as txtfile:
                txtfile.write("PARKING SYSTEM USERS EXPORT\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                total_permits = 0
                total_vehicles = 0
                total_violations = 0
                total_unpaid = 0
                
                for user in users:
                    txtfile.write(f"User ID: {user[0]}\n")
                    txtfile.write(f"Username: {user[1]}\n")
                    txtfile.write(f"Name: {user[2]} {user[3]}\n")
                    txtfile.write(f"Email: {user[4]}\n")
                    txtfile.write(f"Role: {user[5]}\n")
                    txtfile.write(f"Active Permits: {user[6]}\n")
                    txtfile.write(f"Registered Vehicles: {user[7]}\n")
                    txtfile.write(f"Total Violations: {user[8]}\n")
                    txtfile.write(f"Unpaid Fines: ${user[9]:.2f}\n")
                    txtfile.write("-" * 60 + "\n")
                    
                    total_permits += user[6]
                    total_vehicles += user[7]
                    total_violations += user[8]
                    total_unpaid += user[9] if user[9] else 0
                
                # Add summary
                txtfile.write("\nSUMMARY\n")
                txtfile.write("=" * 60 + "\n")
                txtfile.write(f"Total Users: {len(users)}\n")
                txtfile.write(f"Total Permits: {total_permits}\n")
                txtfile.write(f"Total Vehicles: {total_vehicles}\n")
                txtfile.write(f"Total Violations: {total_violations}\n")
                txtfile.write(f"Total Unpaid Fines: ${total_unpaid:.2f}\n")
            
            print(f"Users exported to {file_path}")
        
        conn.close()
        
    except sqlite3.Error as e:
        logging.error(f"Database error in export_users: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in export_users: {e}")
        print(_t("parking.error.exporting_users") + f": {e}")
        
# Update the export_data function to call the new functions
def export_data(format_type):
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to export data")
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('export_data'):
        logging.warning(f"User {auth.current_user['username']} attempted to export data without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    print("\n" + _t("parking.section.export_options") + ":")
    print("1. " + _t("parking.menu.permits"))
    print("2. " + _t("parking.menu.vehicles"))
    print("3. " + _t("parking.menu.violations"))
    print("4. " + _t("parking.menu.parking_lots"))
    print("5. " + _t("parking.menu.users"))
    
    choice = input("Enter your choice (1-5): ")
    
    if choice == '1':
        export_permits(format_type)
    elif choice == '2':
        export_vehicles(format_type)
    elif choice == '3':
        export_violations(format_type)
    elif choice == '4':
        export_parking_lots(format_type)
    elif choice == '5':
        export_users(format_type)
    else:
        print(_t("common.invalid_choice"))


# Update the reports menu function
def display_reports_menu():
    global auth
    
    while True:
        print("\n" + _t("parking.section.reports_menu") + ":")
        print("1. " + _t("parking.menu.permit_status_report"))
        print("2. " + _t("parking.menu.violation_summary_report"))
        print("3. " + _t("parking.menu.parking_lot_occupancy_report"))
        print("4. " + _t("parking.menu.revenue_report"))
        print("5. " + _t("parking.menu.user_activity_report"))
        print("6. " + _t("parking.menu.return_to_main"))
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1' and auth.check_permission('generate_reports'):
            generate_permit_report()
        elif choice == '2' and auth.check_permission('generate_reports'):
            generate_violation_report()
        elif choice == '3' and auth.check_permission('generate_reports'):
            generate_occupancy_report()
        elif choice == '4' and auth.check_permission('generate_reports'):
            generate_revenue_report()
        elif choice == '5' and auth.check_permission('generate_reports'):
            generate_user_activity_report()
        elif choice == '6':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))

def display_export_menu():
    global auth
    
    while True:
        print("\n" + _t("parking.section.export_menu") + ":")
        print("1. " + _t("parking.menu.export_to_csv"))
        print("2. " + _t("parking.menu.export_to_excel"))
        print("3. " + _t("parking.menu.export_to_pdf"))
        print("4. " + _t("parking.menu.export_to_txt"))
        print("5. " + _t("parking.menu.return_to_main"))
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            export_data('csv')
        elif choice == '2':
            export_data('excel')
        elif choice == '3':
            export_data('pdf')
        elif choice == '4':
            export_data('txt')
        elif choice == '5':
            return
        else:
            print(_t("common.invalid_choice"))


def export_data(format_type):
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to export data")
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('export_data'):
        logging.warning(f"User {auth.current_user['username']} attempted to export data without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    print("\n" + _t("parking.section.export_options") + ":")
    print("1. " + _t("parking.menu.permits"))
    print("2. " + _t("parking.menu.vehicles"))
    print("3. " + _t("parking.menu.violations"))
    print("4. " + _t("parking.menu.parking_lots"))
    print("5. " + _t("parking.menu.users"))
    
    choice = input("Enter your choice (1-5): ")
    
    if choice == '1':
        export_permits(format_type)
    elif choice == '2':
        export_vehicles(format_type)
    elif choice == '3':
        export_violations(format_type)
    elif choice == '4':
        export_parking_lots(format_type)
    elif choice == '5':
        export_users(format_type)
    else:
        print(_t("common.invalid_choice"))

# Add these missing functions to parking_management.py

def display_export_menu():
    """Display the export menu for parking data"""
    global auth
    
    while True:
        print("\n" + _t("parking.section.export_menu") + ":")
        print("1. " + _t("parking.menu.export_to_csv"))
        print("2. " + _t("parking.menu.export_to_excel"))
        print("3. " + _t("parking.menu.export_to_pdf"))
        print("4. " + _t("parking.menu.export_to_txt"))
        print("5. " + _t("parking.menu.return_to_main"))
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            export_data('csv')
        elif choice == '2':
            export_data('excel')
        elif choice == '3':
            export_data('pdf')
        elif choice == '4':
            export_data('txt')
        elif choice == '5':
            return
        else:
            print(_t("common.invalid_choice"))


def display_reports_menu():
    """Display the reports menu for parking data"""
    global auth
    
    while True:
        print("\n" + _t("parking.section.reports_menu") + ":")
        print("1. " + _t("parking.menu.permit_status_report"))
        print("2. " + _t("parking.menu.violation_summary_report"))
        print("3. " + _t("parking.menu.parking_lot_occupancy_report"))
        print("4. " + _t("parking.menu.revenue_report"))
        print("5. " + _t("parking.menu.user_activity_report"))
        print("6. " + _t("parking.menu.return_to_main"))
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1' and auth.check_permission('generate_reports'):
            generate_permit_report()
        elif choice == '2' and auth.check_permission('generate_reports'):
            generate_violation_report()
        elif choice == '3' and auth.check_permission('generate_reports'):
            generate_occupancy_report()
        elif choice == '4' and auth.check_permission('generate_reports'):
            generate_revenue_report()
        elif choice == '5' and auth.check_permission('generate_reports'):
            generate_user_activity_report()
        elif choice == '6':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def export_data(format_type):
    """Export parking data in the specified format"""
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to export data")
        print(_t("parking.auth.login_required"))
        return
    
    if not auth.check_permission('export_data'):
        logging.warning(f"User {auth.current_user['username']} attempted to export data without permission")
        print(_t("parking.auth.no_permission"))
        return
    
    print("\n" + _t("parking.section.export_options") + ":")
    print("1. " + _t("parking.menu.permits"))
    print("2. " + _t("parking.menu.vehicles"))
    print("3. " + _t("parking.menu.violations"))
    print("4. " + _t("parking.menu.parking_lots"))
    print("5. " + _t("parking.menu.users"))
    
    choice = input("Enter your choice (1-5): ")
    
    if choice == '1':
        export_permits(format_type)
    elif choice == '2':
        export_vehicles(format_type)
    elif choice == '3':
        export_violations(format_type)
    elif choice == '4':
        export_parking_lots(format_type)
    elif choice == '5':
        export_users(format_type)
    else:
        print(_t("common.invalid_choice"))


def get_file_path(file_format, default_filename):
    """Helper function to get file path from user with error handling"""
    while True:
        location_choice = input(f"Where would you like to save the {file_format} file?\n1. Current directory\n2. Custom path\nEnter your choice (1-2): ")
        
        if location_choice == '1':
            # Use current directory
            return os.path.join(os.getcwd(), default_filename)
        elif location_choice == '2':
            # Custom directory
            while True:
                custom_path = input("Enter the full path (including filename): ")
                directory = os.path.dirname(custom_path)
                
                # Check if directory exists or can be created
                if not directory:  # If no directory specified, use current directory
                    return custom_path
                
                if not os.path.exists(directory):
                    try_create = input(f"Directory {directory} does not exist. Create it? (y/n): ")
                    if try_create.lower() == 'y':
                        try:
                            os.makedirs(directory, exist_ok=True)
                            return custom_path
                        except OSError as e:
                            print(_t("parking.error.creating_directory") + f": {e}")
                            continue
                    else:
                        continue
                return custom_path
        else:
            print(_t("parking.error.invalid_choice_1_or_2"))

# Create a function that can be called from main.py
def display_parking_menu():
    global auth

    # Initialize the database
    init_db()

    # Initialize authentication system if not already done
    if auth is None:
        auth = get_auth()
        if auth is None:
            auth = UserAuth()

    while True:
        print("\n" + "="*100)
        print(f"  {get_text('parking.title', default='PARKING & TRANSPORTATION MANAGEMENT SYSTEM')}")
        print("="*100)
        logged_in_msg = get_text('parking.logged_in', default='Logged in as: {user} ({role})').format(user=auth.current_user['username'], role=auth.current_user['role']) if auth.current_user else get_text('parking.not_logged_in', default='Not logged in')
        print(logged_in_msg)

        print(f"\n🅿️ {get_text('parking.section.permits', default='Parking Permits')}:")
        print(f"{'1.  ' + get_text('parking.menu.create_permit', default='Create Permit'):<25} {'2.  ' + get_text('parking.menu.view_permits', default='View Permits'):<25} {'3.  ' + get_text('parking.menu.update_permit', default='Update Permit'):<25} {'4.  ' + get_text('parking.menu.delete_permit', default='Delete Permit'):<25}")

        print(f"\n🚗 {get_text('parking.section.vehicles', default='Vehicle Management')}:")
        print(f"{'5.  ' + get_text('parking.menu.register_vehicle', default='Register Vehicle'):<25} {'6.  ' + get_text('parking.menu.view_vehicles', default='View Vehicles'):<25} {'7.  ' + get_text('parking.menu.update_vehicle', default='Update Vehicle'):<25} {'8.  ' + get_text('parking.menu.delete_vehicle', default='Delete Vehicle'):<25}")

        print(f"\n⚠️ {get_text('parking.section.violations', default='Parking Violations')}:")
        print(f"{'9.  ' + get_text('parking.menu.record_violation', default='Record Violation'):<25} {'10. ' + get_text('parking.menu.view_violations', default='View Violations'):<25} {'11. ' + get_text('parking.menu.update_status', default='Update Status'):<25} {'12. ' + get_text('parking.menu.pay_fine', default='Pay Fine'):<25}")

        print(f"\n🏢 {get_text('parking.section.lots', default='Parking Lots')}:")
        print(f"{'13. ' + get_text('parking.menu.create_lot', default='Create Lot'):<25} {'14. ' + get_text('parking.menu.view_lots', default='View Lots'):<25} {'15. ' + get_text('parking.menu.update_lot', default='Update Lot'):<25} {'16. ' + get_text('parking.menu.check_availability', default='Check Availability'):<25}")

        print(f"\n🚍 {get_text('parking.section.transport', default='Transportation & Trips')}:")
        print(f"{'17. ' + get_text('parking.menu.view_trips', default='View All Trips'):<25} {'18. ' + get_text('parking.menu.create_trip', default='Create Trip'):<25} {'19. ' + get_text('parking.menu.register_trip', default='Register for Trip'):<25} {'20. ' + get_text('parking.menu.my_registrations', default='My Registrations'):<25}")
        print(f"{'21. ' + get_text('parking.menu.manage_participants', default='Manage Participants'):<25}")

        print(f"\n📊 {get_text('parking.section.reports', default='Reports & Data')}:")
        print(f"{'22. ' + get_text('parking.menu.parking_reports', default='Parking Reports'):<25} {'23. ' + get_text('parking.menu.trip_reports', default='Trip Reports'):<25} {'24. ' + get_text('parking.menu.export_parking', default='Export Parking'):<25} {'25. ' + get_text('parking.menu.export_trip', default='Export Trip Data'):<25}")

        print(f"\n↩️ {get_text('parking.section.navigation', default='Navigation')}:")
        print(f"26. {get_text('parking.menu.language', default='Language')}")
        print(f"27. {get_text('parking.menu.return_main', default='Return to Main Menu')}")
        print("="*100)

        choice = input(f"\n{get_text('parking.prompt.choice', default='Enter your choice (1-27)')}: ")

        # Parking Permits (1-4)
        if choice == '1' and auth.check_permission('create_permit'):
            create_parking_permit()
        elif choice == '2' and (auth.check_permission('view_any_permit') or auth.check_permission('view_own_permit')):
            view_parking_permit()
        elif choice == '3' and (auth.check_permission('update_any_permit') or auth.check_permission('update_own_permit')):
            update_parking_permit()
        elif choice == '4' and auth.check_permission('delete_any_permit'):
            delete_parking_permit()

        # Vehicles (5-8)
        elif choice == '5' and auth.check_permission('register_vehicle'):
            add_vehicle()
        elif choice == '6' and (auth.check_permission('view_any_vehicle') or auth.check_permission('view_own_vehicle')):
            view_vehicle()
        elif choice == '7' and (auth.check_permission('update_any_vehicle') or auth.check_permission('update_own_vehicle')):
            update_vehicle()
        elif choice == '8' and auth.check_permission('delete_any_vehicle'):
            delete_vehicle()

        # Violations (9-12)
        elif choice == '9' and auth.check_permission('record_violation'):
            record_violation()
        elif choice == '10' and (auth.check_permission('view_any_violation') or auth.check_permission('view_own_violation')):
            view_violation()
        elif choice == '11' and auth.check_permission('update_violation'):
            update_violation_status()
        elif choice == '12' and auth.check_permission('view_own_violation'):
            pay_violation_fine()

        # Parking Lots (13-16)
        elif choice == '13' and auth.check_permission('manage_parking_lots'):
            create_parking_lot()
        elif choice == '14':
            view_parking_lot()
        elif choice == '15' and auth.check_permission('manage_parking_lots'):
            update_parking_lot()
        elif choice == '16':
            check_lot_availability()

        # Transportation & Trips (17-21)
        elif choice == '17' and auth.check_permission('view_trips'):
            view_trips()
        elif choice == '18' and auth.check_permission('create_trips'):
            create_trip()
        elif choice == '19' and auth.check_permission('register_for_trips'):
            register_for_trip()
        elif choice == '20' and auth.check_permission('view_own_trip_registrations'):
            view_my_trip_registrations()
        elif choice == '21' and auth.check_permission('manage_trip_participants'):
            manage_trip_participants()

        # Reports & Data (22-25)
        elif choice == '22':
            display_reports_menu()
        elif choice == '23' and auth.check_permission('generate_trip_reports'):
            # Trip report generation
            print("\n📊 Trip Report Generation")
            print("="*50)
            print(_t("parking.trip.generator_info"))
            print("  • Trip Summary Reports")
            print("  • Participant List Reports")
            print("  • Financial Reports")
            print("\n" + _t("parking.msg.access_via_trip_menu"))
            print(_t("parking.trip.import_hint"))
            input("\nPress Enter to continue...")
        elif choice == '24':
            display_export_menu()
        elif choice == '25' and auth.check_permission('generate_trip_reports'):
            print("\n📊 Trip data export functionality available via Reports menu")
            input("\nPress Enter to continue...")

        # Navigation (26-27)
        elif choice == '26':
            display_language_menu_option()
        elif choice == '27':
            print(get_text('parking.returning', default='Returning to main menu...'))
            return
        else:
            print(get_text('parking.invalid_choice', default='Invalid choice or insufficient permissions. Please try again.'))
