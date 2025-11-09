from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import datetime
import os
import random
import string
# Use logging helpers from the refactored utils module
from university_system.modules.shared.utils.simple_activity_logger import (
    log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_menu_navigation,
)
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.finance_integration import record_payment_to_finance

# Global variable to store the auth instance
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

# Database initialization
def init_housing_db():
    """Initialize the housing accommodation database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create housing_buildings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_buildings (
            building_id TEXT PRIMARY KEY,
            building_name TEXT NOT NULL,
            address TEXT NOT NULL,
            campus_location TEXT NOT NULL,
            total_rooms INTEGER NOT NULL,
            available_rooms INTEGER NOT NULL,
            has_elevator BOOLEAN DEFAULT 0,
            has_accessible_rooms BOOLEAN DEFAULT 0,
            has_kitchen BOOLEAN DEFAULT 0,
            has_laundry BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        
        # Create housing_rooms table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_rooms (
            room_id TEXT PRIMARY KEY,
            building_id TEXT NOT NULL,
            room_number TEXT NOT NULL,
            floor_number INTEGER NOT NULL,
            room_type TEXT NOT NULL,
            max_occupants INTEGER NOT NULL,
            current_occupants INTEGER DEFAULT 0,
            is_accessible BOOLEAN DEFAULT 0,
            status TEXT NOT NULL,
            monthly_rent REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (building_id) REFERENCES housing_buildings (building_id)
        )
        ''')
        
        # Create housing_applications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_applications (
            application_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            application_date TEXT NOT NULL,
            preferred_building_id TEXT,
            preferred_room_type TEXT NOT NULL,
            requested_move_in_date TEXT NOT NULL,
            requested_duration_months INTEGER NOT NULL,
            special_requirements TEXT,
            status TEXT NOT NULL,
            notes TEXT,
            reviewed_by TEXT,
            review_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (preferred_building_id) REFERENCES housing_buildings (building_id)
        )
        ''')
        
        # Create housing_assignments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_assignments (
            assignment_id TEXT PRIMARY KEY,
            application_id TEXT,
            student_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            move_in_date TEXT NOT NULL,
            planned_move_out_date TEXT NOT NULL,
            actual_move_out_date TEXT,
            contract_number TEXT UNIQUE,
            monthly_rent REAL NOT NULL,
            status TEXT NOT NULL,
            assigned_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (application_id) REFERENCES housing_applications (application_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        )
        ''')
        
        # Create housing_payments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_payments (
            payment_id TEXT PRIMARY KEY,
            assignment_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_reference TEXT,
            payment_period_start TEXT NOT NULL,
            payment_period_end TEXT NOT NULL,
            status TEXT NOT NULL,
            received_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (assignment_id) REFERENCES housing_assignments (assignment_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Create housing_maintenance_requests table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_maintenance_requests (
            request_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            request_date TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            assigned_to TEXT,
            scheduled_date TEXT,
            completion_date TEXT,
            feedback TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Create inspections table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_inspections (
            inspection_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            inspector TEXT NOT NULL,
            inspection_date TEXT NOT NULL,
            inspection_type TEXT NOT NULL,
            status TEXT NOT NULL,
            findings TEXT,
            action_required TEXT,
            follow_up_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        )
        ''')
        
        # Create inventory items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_inventory (
            item_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            condition TEXT NOT NULL,
            acquisition_date TEXT,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        )
        ''')
        
        # Fetch the count of buildings to check if we need to create sample data
        cursor.execute('SELECT COUNT(*) FROM housing_buildings')
        building_count = cursor.fetchone()[0]
        
        # If no buildings exist, create sample data
        if building_count == 0:
            # Add sample buildings
            sample_buildings = [
                ('B001', 'University Residence Hall', '123 Campus Drive', 'North Campus', 100, 35, 1, 1, 1, 1),
                ('B002', 'Graduate Housing Complex', '456 Scholar Avenue', 'South Campus', 80, 20, 1, 1, 1, 1),
                ('B003', 'Freshman Dormitory', '789 College Road', 'East Campus', 150, 50, 0, 1, 0, 1),
                ('B004', 'International House', '321 Global Street', 'West Campus', 60, 15, 1, 1, 1, 1)
            ]
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for building in sample_buildings:
                cursor.execute('''
                INSERT INTO housing_buildings 
                (building_id, building_name, address, campus_location, total_rooms, available_rooms, 
                has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (building[0], building[1], building[2], building[3], building[4], building[5], 
                      building[6], building[7], building[8], building[9], timestamp, timestamp))
            
            # Add sample rooms for each building
            room_types = ['Single', 'Double', 'Triple', 'Suite', 'Studio', 'Apartment']
            statuses = ['Available', 'Occupied', 'Maintenance', 'Reserved']
            
            for building_id in ['B001', 'B002', 'B003', 'B004']:
                # Define how many rooms to create for this building
                if building_id == 'B001':
                    floors = 4
                    rooms_per_floor = 10
                elif building_id == 'B002':
                    floors = 3
                    rooms_per_floor = 8
                elif building_id == 'B003':
                    floors = 5
                    rooms_per_floor = 15
                else:  # B004
                    floors = 2
                    rooms_per_floor = 10
                
                for floor in range(1, floors + 1):
                    for room_num in range(1, rooms_per_floor + 1):
                        room_number = f"{floor}{str(room_num).zfill(2)}"
                        room_id = f"{building_id}-{room_number}"
                        room_type = random.choice(room_types)
                        max_occupants = 1 if room_type == 'Single' else 2 if room_type == 'Double' else 3 if room_type == 'Triple' else 2 if room_type == 'Studio' else 4
                        current_occupants = random.randint(0, max_occupants)
                        is_accessible = random.choice([0, 1]) if floor == 1 else 0
                        status = 'Occupied' if current_occupants > 0 else random.choice(statuses)
                        monthly_rent = random.randint(400, 1200)
                        
                        cursor.execute('''
                        INSERT INTO housing_rooms 
                        (room_id, building_id, room_number, floor_number, room_type, max_occupants, current_occupants, 
                        is_accessible, status, monthly_rent, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (room_id, building_id, room_number, floor, room_type, max_occupants, current_occupants,
                             is_accessible, status, monthly_rent, timestamp, timestamp))
            
            # Create a test application and assignment for student S12345
            application_id = generate_id('APP')
            cursor.execute('''
            INSERT INTO housing_applications 
            (application_id, student_id, application_date, preferred_building_id, preferred_room_type, 
            requested_move_in_date, requested_duration_months, special_requirements, status, 
            created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (application_id, 'S12345', timestamp, 'B001', 'Single', 
                 (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d'), 
                 9, None, 'Approved', timestamp, timestamp))
            
            # Find an available room for assignment
            cursor.execute('''
            SELECT room_id, monthly_rent FROM housing_rooms 
            WHERE building_id = 'B001' AND room_type = 'Single' AND status = 'Available'
            LIMIT 1
            ''')
            room_data = cursor.fetchone()
            
            if room_data:
                room_id, monthly_rent = room_data
                assignment_id = generate_id('ASG')
                move_in_date = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
                move_out_date = (datetime.datetime.now() + datetime.timedelta(days=30 + 9*30)).strftime('%Y-%m-%d')
                contract_number = generate_id('CNT')
                
                cursor.execute('''
                INSERT INTO housing_assignments 
                (assignment_id, application_id, student_id, room_id, move_in_date, planned_move_out_date, 
                contract_number, monthly_rent, status, assigned_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (assignment_id, application_id, 'S12345', room_id, move_in_date, move_out_date, 
                     contract_number, monthly_rent, 'Active', 'system', timestamp, timestamp))
                
                # Update room status and occupancy
                cursor.execute('''
                UPDATE housing_rooms 
                SET current_occupants = current_occupants + 1, status = 'Occupied'
                WHERE room_id = ?
                ''', (room_id,))
                
                # Create a test maintenance request
                request_id = generate_id('REQ')
                cursor.execute('''
                INSERT INTO housing_maintenance_requests 
                (request_id, room_id, student_id, request_date, issue_type, description, priority, status, 
                created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (request_id, room_id, 'S12345', timestamp, 'Plumbing', 
                     'Leaking faucet in bathroom', 'Medium', 'Open', timestamp, timestamp))
        
        conn.commit()
        conn.close()
        print("Housing database initialized successfully!")
        return True
    
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error initializing housing database: {e}")
        return False

def generate_id(prefix):
    """Generate a unique ID with a given prefix"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_chars}"

# Building Management Functions
@log_create(module="housing", description="Creating new building")
def create_building():
    """Create a new housing building"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create building records.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to create building records.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCreate New Housing Building")
        print("===========================")
        
        # Get building details
        building_id = generate_id('BLD')
        
        building_name = input("Enter building name: ").strip()
        if not building_name:
            print("Error: Building name cannot be empty.")
            conn.close()
            return
        
        address = input("Enter address: ").strip()
        if not address:
            print("Error: Address cannot be empty.")
            conn.close()
            return
        
        campus_location = input("Enter campus location (e.g., North Campus): ").strip()
        if not campus_location:
            print("Error: Campus location cannot be empty.")
            conn.close()
            return
        
        while True:
            try:
                total_rooms = int(input("Enter total number of rooms: "))
                if total_rooms <= 0:
                    print("Error: Total rooms must be greater than 0.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid number.")
        
        while True:
            try:
                available_rooms = int(input("Enter number of available rooms: "))
                if available_rooms < 0 or available_rooms > total_rooms:
                    print(f"Error: Available rooms must be between 0 and {total_rooms}.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid number.")
        
        has_elevator = input("Does the building have an elevator? (y/n): ").lower() == 'y'
        has_accessible_rooms = input("Does the building have accessible rooms? (y/n): ").lower() == 'y'
        has_kitchen = input("Does the building have kitchens? (y/n): ").lower() == 'y'
        has_laundry = input("Does the building have laundry facilities? (y/n): ").lower() == 'y'
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert building record
        cursor.execute('''
        INSERT INTO housing_buildings (
            building_id, building_name, address, campus_location, total_rooms, available_rooms,
            has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            building_id, building_name, address, campus_location, total_rooms, available_rooms,
            1 if has_elevator else 0, 1 if has_accessible_rooms else 0,
            1 if has_kitchen else 0, 1 if has_laundry else 0,
            timestamp, timestamp
        ))
        
        conn.commit()
        print(f"\nBuilding '{building_name}' created successfully with ID: {building_id}")
        
        # Ask if user wants to add rooms now
        add_rooms = input("\nDo you want to add rooms to this building now? (y/n): ").lower() == 'y'
        
        if add_rooms:
            create_rooms_for_building(building_id, building_name)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error creating building: {e}")

@log_create(module="housing", description="Creating new rooms")
def create_rooms_for_building(building_id=None, building_name=None):
    """Create new rooms for a housing building"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create room records.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to create room records.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # If building_id not provided, get it from user
        if building_id is None:
            print("\nSelect Building:")
            print("================")
            
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            
            if not buildings:
                print("No buildings found. Please create a building first.")
                conn.close()
                return
            
            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")
            
            while True:
                try:
                    choice = int(input("\nSelect building (enter number): "))
                    if 1 <= choice <= len(buildings):
                        building_id = buildings[choice - 1][0]
                        building_name = buildings[choice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(buildings)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        print(f"\nAdding Rooms to Building: {building_name}")
        print("=" * 40)
        
        while True:
            try:
                floor_count = int(input("How many floors does the building have? "))
                if floor_count <= 0:
                    print("Error: Number of floors must be greater than 0.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid number.")
        
        for floor in range(1, floor_count + 1):
            print(f"\nAdding rooms to Floor {floor}:")
            
            while True:
                try:
                    room_count = int(input(f"How many rooms on Floor {floor}? "))
                    if room_count <= 0:
                        print("Error: Number of rooms must be greater than 0.")
                        continue
                    break
                except ValueError:
                    print("Error: Please enter a valid number.")
            
            print("\nRoom Types:")
            print("1. Single")
            print("2. Double")
            print("3. Triple")
            print("4. Suite")
            print("5. Studio")
            print("6. Apartment")
            
            # Batch process room creation
            for room_num in range(1, room_count + 1):
                room_number = f"{floor}{str(room_num).zfill(2)}"
                room_id = f"{building_id}-{room_number}"
                
                print(f"\nRoom {room_number}:")
                
                while True:
                    try:
                        room_type_choice = int(input("Room type (1-6): "))
                        if 1 <= room_type_choice <= 6:
                            room_types = ['Single', 'Double', 'Triple', 'Suite', 'Studio', 'Apartment']
                            room_type = room_types[room_type_choice - 1]
                            break
                        else:
                            print("Please enter a number between 1 and 6.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                while True:
                    try:
                        max_occupants = int(input(f"Maximum occupants for {room_type} room: "))
                        if max_occupants <= 0:
                            print("Error: Maximum occupants must be greater than 0.")
                            continue
                        break
                    except ValueError:
                        print("Error: Please enter a valid number.")
                
                is_accessible = input("Is this room accessible? (y/n): ").lower() == 'y'
                
                while True:
                    try:
                        monthly_rent = float(input("Monthly rent amount: $"))
                        if monthly_rent <= 0:
                            print("Error: Rent must be greater than 0.")
                            continue
                        break
                    except ValueError:
                        print("Error: Please enter a valid amount.")
                
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Insert room record
                cursor.execute('''
                INSERT INTO housing_rooms (
                    room_id, building_id, room_number, floor_number, room_type, max_occupants, 
                    current_occupants, is_accessible, status, monthly_rent, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    room_id, building_id, room_number, floor, room_type, max_occupants, 
                    0, 1 if is_accessible else 0, 'Available', monthly_rent, timestamp, timestamp
                ))
            
            print(f"\nAdded {room_count} rooms to Floor {floor}!")
        
        # Update available rooms count
        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE building_id = ? AND status = "Available"', (building_id,))
        available_count = cursor.fetchone()[0]
        
        cursor.execute('UPDATE housing_buildings SET available_rooms = ? WHERE building_id = ?', (available_count, building_id))
        
        conn.commit()
        print(f"\nSuccessfully added rooms to building {building_name}!")
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error creating rooms: {e}")

@log_read(module="housing", description="Viewing building details")
def view_building():
    """View details of a housing building"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view building records.")
        return
    
    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to view building records.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Fetch all buildings
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        
        if not buildings:
            print("No buildings found in the system.")
            conn.close()
            return
        
        print("\nSelect Building to View:")
        print("======================")
        
        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")
        
        while True:
            try:
                choice = int(input("\nSelect building (enter number): "))
                if 1 <= choice <= len(buildings):
                    building_id = buildings[choice - 1][0]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(buildings)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Fetch building details
        cursor.execute('''
        SELECT building_id, building_name, address, campus_location, total_rooms, available_rooms,
               has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at, updated_at
        FROM housing_buildings
        WHERE building_id = ?
        ''', (building_id,))
        
        building = cursor.fetchone()
        
        if not building:
            print("Building not found.")
            conn.close()
            return
        
        print("\nBuilding Details:")
        print("================")
        print(f"Building ID: {building[0]}")
        print(f"Name: {building[1]}")
        print(f"Address: {building[2]}")
        print(f"Campus Location: {building[3]}")
        print(f"Total Rooms: {building[4]}")
        print(f"Available Rooms: {building[5]}")
        print(f"Has Elevator: {'Yes' if building[6] else 'No'}")
        print(f"Has Accessible Rooms: {'Yes' if building[7] else 'No'}")
        print(f"Has Kitchen: {'Yes' if building[8] else 'No'}")
        print(f"Has Laundry: {'Yes' if building[9] else 'No'}")
        print(f"Created: {building[10]}")
        print(f"Last Updated: {building[11]}")
        
        # Get room statistics
        cursor.execute('''
        SELECT room_type, COUNT(*), SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END)
        FROM housing_rooms
        WHERE building_id = ?
        GROUP BY room_type
        ''', (building_id,))
        
        room_stats = cursor.fetchall()
        
        print("\nRoom Statistics:")
        print("===============")
        print(f"{'Type':<10} {'Total':<10} {'Available':<10}")
        print("-" * 30)
        
        for room_type, total, available in room_stats:
            print(f"{room_type:<10} {total:<10} {available:<10}")
        
        # Ask if user wants to view rooms
        view_rooms = input("\nDo you want to view rooms in this building? (y/n): ").lower() == 'y'
        
        if view_rooms:
            cursor.execute('''
            SELECT room_id, room_number, floor_number, room_type, max_occupants,
                   current_occupants, is_accessible, status, monthly_rent
            FROM housing_rooms
            WHERE building_id = ?
            ORDER BY floor_number, room_number
            ''', (building_id,))
            
            rooms = cursor.fetchall()
            
            print("\nRooms in Building:")
            print("=================")
            print(f"{'Room #':<8} {'Floor':<8} {'Type':<10} {'Max Occ.':<10} {'Current':<10} {'Accessible':<12} {'Status':<12} {'Rent':<8}")
            print("-" * 80)
            
            for room in rooms:
                print(f"{room[1]:<8} {room[2]:<8} {room[3]:<10} {room[4]:<10} {room[5]:<10} {'Yes' if room[6] else 'No':<12} {room[7]:<12} ${room[8]:<7.2f}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing building: {e}")

@log_update(module="housing", description="Updating building details")
def update_building():
    """Update details of a housing building"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to update building records.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to update building records.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Fetch all buildings
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        
        if not buildings:
            print("No buildings found in the system.")
            conn.close()
            return
        
        print("\nSelect Building to Update:")
        print("========================")
        
        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")
        
        while True:
            try:
                choice = int(input("\nSelect building (enter number): "))
                if 1 <= choice <= len(buildings):
                    building_id = buildings[choice - 1][0]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(buildings)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Fetch building details
        cursor.execute('''
        SELECT building_name, address, campus_location, total_rooms, available_rooms,
               has_elevator, has_accessible_rooms, has_kitchen, has_laundry
        FROM housing_buildings
        WHERE building_id = ?
        ''', (building_id,))
        
        building = cursor.fetchone()
        
        if not building:
            print("Building not found.")
            conn.close()
            return
        
        print("\nUpdate Building Information:")
        print(f"Current Building Name: {building[0]}")
        print(f"Current Address: {building[1]}")
        print(f"Current Campus Location: {building[2]}")
        print(f"Current Total Rooms: {building[3]}")
        print(f"Current Available Rooms: {building[4]}")
        print(f"Has Elevator: {'Yes' if building[5] else 'No'}")
        print(f"Has Accessible Rooms: {'Yes' if building[6] else 'No'}")
        print(f"Has Kitchen: {'Yes' if building[7] else 'No'}")
        print(f"Has Laundry: {'Yes' if building[8] else 'No'}")
        
        print("\nEnter new values (leave blank to keep current):")
        
        new_name = input("New Building Name: ").strip()
        if not new_name:
            new_name = building[0]
        
        new_address = input("New Address: ").strip()
        if not new_address:
            new_address = building[1]
        
        new_campus = input("New Campus Location: ").strip()
        if not new_campus:
            new_campus = building[2]
        
        new_total_rooms = None
        while True:
            try:
                rooms_input = input(f"New Total Rooms [{building[3]}]: ").strip()
                if not rooms_input:
                    new_total_rooms = building[3]
                    break
                
                new_total_rooms = int(rooms_input)
                if new_total_rooms <= 0:
                    print("Error: Total rooms must be greater than 0.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid number.")
        
        new_available_rooms = None
        while True:
            try:
                rooms_input = input(f"New Available Rooms [{building[4]}]: ").strip()
                if not rooms_input:
                    new_available_rooms = building[4]
                    break
                
                new_available_rooms = int(rooms_input)
                if new_available_rooms < 0 or new_available_rooms > new_total_rooms:
                    print(f"Error: Available rooms must be between 0 and {new_total_rooms}.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid number.")
        
        has_elevator = input(f"Has Elevator (y/n) [{'y' if building[5] else 'n'}]: ").strip().lower()
        if not has_elevator:
            has_elevator = 1 if building[5] else 0
        else:
            has_elevator = 1 if has_elevator == 'y' else 0
        
        has_accessible = input(f"Has Accessible Rooms (y/n) [{'y' if building[6] else 'n'}]: ").strip().lower()
        if not has_accessible:
            has_accessible = 1 if building[6] else 0
        else:
            has_accessible = 1 if has_accessible == 'y' else 0
        
        has_kitchen = input(f"Has Kitchen (y/n) [{'y' if building[7] else 'n'}]: ").strip().lower()
        if not has_kitchen:
            has_kitchen = 1 if building[7] else 0
        else:
            has_kitchen = 1 if has_kitchen == 'y' else 0
        
        has_laundry = input(f"Has Laundry (y/n) [{'y' if building[8] else 'n'}]: ").strip().lower()
        if not has_laundry:
            has_laundry = 1 if building[8] else 0
        else:
            has_laundry = 1 if has_laundry == 'y' else 0
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update building record
        cursor.execute('''
        UPDATE housing_buildings
        SET building_name = ?, address = ?, campus_location = ?, total_rooms = ?, available_rooms = ?,
            has_elevator = ?, has_accessible_rooms = ?, has_kitchen = ?, has_laundry = ?, updated_at = ?
        WHERE building_id = ?
        ''', (
            new_name, new_address, new_campus, new_total_rooms, new_available_rooms,
            has_elevator, has_accessible, has_kitchen, has_laundry, timestamp, building_id
        ))
        
        conn.commit()
        print(f"\nBuilding '{new_name}' updated successfully!")
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error updating building: {e}")

@log_delete(module="housing", description="Deleting building")
def delete_building():
    """Delete a housing building"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to delete building records.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to delete building records.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Fetch all buildings
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        
        if not buildings:
            print("No buildings found in the system.")
            conn.close()
            return
        
        print("\nSelect Building to Delete:")
        print("========================")
        
        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")
        
        while True:
            try:
                choice = int(input("\nSelect building (enter number): "))
                if 1 <= choice <= len(buildings):
                    building_id = buildings[choice - 1][0]
                    building_name = buildings[choice - 1][1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(buildings)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Check for any assigned rooms
        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE building_id = ? AND status != "Available"', (building_id,))
        occupied_count = cursor.fetchone()[0]
        
        if occupied_count > 0:
            print(f"\nCannot delete building '{building_name}' because it has {occupied_count} occupied or reserved rooms.")
            print("Please reassign all occupants before deleting this building.")
            conn.close()
            return
        
        # Confirm deletion
        confirm = input(f"\nAre you sure you want to delete building '{building_name}'? This will delete all associated rooms. (y/n): ").lower()
        
        if confirm != 'y':
            print("Deletion cancelled.")
            conn.close()
            return
        
        # Delete all rooms in this building
        cursor.execute('DELETE FROM housing_rooms WHERE building_id = ?', (building_id,))
        
        # Delete the building
        cursor.execute('DELETE FROM housing_buildings WHERE building_id = ?', (building_id,))
        
        conn.commit()
        print(f"\nBuilding '{building_name}' and all associated rooms have been deleted successfully!")
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error deleting building: {e}")

# Housing Application Functions
@log_create(module="housing", description="Creating housing application")
def create_application():
    """Create a new housing application"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create housing applications.")
        return
    
    current_role = auth.current_user.get('role', '')
    
    # Different permissions based on role
    if current_role == 'student':
        # Students can only apply for themselves
        if not auth.check_permission('view_own_record'):
            print("You don't have permission to create housing applications.")
            return
        
        # Get the student ID associated with this user
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))
            
            result = cursor.fetchone()
            if not result or not result[0]:
                print("No student ID associated with your account.")
                conn.close()
                return
                
            student_id = result[0]
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return
        
    else:
        # Staff/admin can create applications for any student
        if not auth.check_permission('manage_accommodations'):
            print("You don't have permission to create housing applications.")
            return
        
        # Let staff/admin select a student
        student_id = select_student()
        if not student_id:
            return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if student already has an active application
        cursor.execute('''
        SELECT application_id FROM housing_applications 
        WHERE student_id = ? AND status IN ('Pending', 'Under Review')
        ''', (student_id,))
        
        existing_application = cursor.fetchone()
        
        if existing_application:
            print(f"\nStudent already has an active application (ID: {existing_application[0]}).")
            print("Please update the existing application or cancel it before creating a new one.")
            conn.close()
            return
        
        # Check if student already has active housing
        cursor.execute('''
        SELECT assignment_id FROM housing_assignments 
        WHERE student_id = ? AND status = 'Active'
        ''', (student_id,))
        
        existing_assignment = cursor.fetchone()
        
        if existing_assignment:
            print(f"\nStudent already has active housing (Assignment ID: {existing_assignment[0]}).")
            proceed = input("Do you still want to proceed with a new application? (y/n): ").lower()
            if proceed != 'y':
                conn.close()
                return
        
        print("\nNew Housing Application")
        print("======================")
        
        # Fetch available buildings
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        
        if not buildings:
            print("No buildings found in the system. Please create a building first.")
            conn.close()
            return
        
        print("\nSelect Preferred Building:")
        print("=========================")
        print("0. No preference")
        
        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")
        
        while True:
            try:
                choice = int(input("\nSelect building (enter number): "))
                if choice == 0:
                    preferred_building_id = None
                    break
                elif 1 <= choice <= len(buildings):
                    preferred_building_id = buildings[choice - 1][0]
                    break
                else:
                    print(f"Please enter a number between 0 and {len(buildings)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        print("\nSelect Room Type:")
        print("================")
        room_types = ["Single", "Double", "Triple", "Suite", "Studio", "Apartment"]
        
        for i, room_type in enumerate(room_types, 1):
            print(f"{i}. {room_type}")
        
        while True:
            try:
                choice = int(input("\nSelect room type (enter number): "))
                if 1 <= choice <= len(room_types):
                    preferred_room_type = room_types[choice - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(room_types)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get preferred move-in date
        while True:
            move_in_date = input("Requested move-in date (YYYY-MM-DD): ")
            try:
                # Validate date format
                datetime.datetime.strptime(move_in_date, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        # Get duration
        while True:
            try:
                duration = int(input("Requested duration (in months): "))
                if duration <= 0:
                    print("Duration must be greater than 0.")
                    continue
                break
            except ValueError:
                print("Please enter a valid number.")
        
        # Get special requirements
        special_requirements = input("Any special requirements or notes (leave blank if none): ").strip() or None
        
        # Create application
        application_id = generate_id('APP')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO housing_applications (
            application_id, student_id, application_date, preferred_building_id, preferred_room_type,
            requested_move_in_date, requested_duration_months, special_requirements, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            application_id, student_id, timestamp, preferred_building_id, preferred_room_type,
            move_in_date, duration, special_requirements, 'Pending', timestamp, timestamp
        ))
        
        conn.commit()
        print(f"\nHousing application created successfully with ID: {application_id}")
        
        # If staff/admin is creating, ask if they want to approve immediately
        if auth.check_permission('approve_accommodations'):
            approve_now = input("\nDo you want to approve this application now? (y/n): ").lower() == 'y'
            
            if approve_now:
                process_application(application_id)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error creating application: {e}")

def select_student():
    """Helper function to select a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ask for student ID or search criteria
        search_type = input("\nSearch for student by:\n1. Student ID\n2. Name\nEnter choice (1-2): ")
        
        if search_type == '1':
            # Search by student ID
            student_id = input("Enter student ID: ")
            
            cursor.execute('''
            SELECT student_id, first_name, last_name, email_address
            FROM students
            WHERE student_id = ?
            ''', (student_id,))
            
            student = cursor.fetchone()
            
            if not student:
                print("Student not found.")
                conn.close()
                return None
            
            print(f"\nFound: {student[1]} {student[2]} ({student[0]}) - {student[3]}")
            confirm = input("Is this the correct student? (y/n): ").lower()
            
            if confirm != 'y':
                conn.close()
                return None
            
            return student[0]
            
        elif search_type == '2':
            # Search by name
            name = input("Enter student name (or part of name): ")
            
            cursor.execute('''
            SELECT student_id, first_name, last_name, email_address
            FROM students
            WHERE first_name LIKE ? OR last_name LIKE ?
            ORDER BY last_name, first_name
            ''', (f'%{name}%', f'%{name}%'))
            
            students = cursor.fetchall()
            
            if not students:
                print("No students found matching that name.")
                conn.close()
                return None
            
            print("\nFound students:")
            for i, student in enumerate(students, 1):
                print(f"{i}. {student[1]} {student[2]} ({student[0]}) - {student[3]}")
            
            while True:
                try:
                    choice = int(input("\nSelect student (enter number): "))
                    if 1 <= choice <= len(students):
                        return students[choice - 1][0]
                    else:
                        print(f"Please enter a number between 1 and {len(students)}.")
                except ValueError:
                    print("Please enter a valid number.")
        else:
            print("Invalid choice.")
            conn.close()
            return None
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    except Exception as e:
        print(f"Error selecting student: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

@log_update(module="housing", description="Processing housing application")
def process_application(application_id=None):
    """Process a housing application (approve/reject)"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to process housing applications.")
        return
    
    if not auth.check_permission('approve_accommodations'):
        print("You don't have permission to process housing applications.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # If application_id not provided, let user select an application
        if application_id is None:
            cursor.execute('''
            SELECT a.application_id, a.student_id, s.first_name, s.last_name, a.application_date, a.status
            FROM housing_applications a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.status = 'Pending'
            ORDER BY a.application_date
            ''')
            
            applications = cursor.fetchall()
            
            if not applications:
                print("No pending applications found.")
                conn.close()
                return
            
            print("\nPending Applications:")
            print("===================")
            
            for i, app in enumerate(applications, 1):
                print(f"{i}. {app[2]} {app[3]} ({app[1]}) - Applied on {app[4]}")
            
            while True:
                try:
                    choice = int(input("\nSelect application to process (enter number): "))
                    if 1 <= choice <= len(applications):
                        application_id = applications[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(applications)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # Fetch application details
        cursor.execute('''
        SELECT a.application_id, a.student_id, s.first_name, s.last_name, a.application_date,
               a.preferred_building_id, b.building_name, a.preferred_room_type,
               a.requested_move_in_date, a.requested_duration_months, a.special_requirements
        FROM housing_applications a
        JOIN students s ON a.student_id = s.student_id
        LEFT JOIN housing_buildings b ON a.preferred_building_id = b.building_id
        WHERE a.application_id = ?
        ''', (application_id,))
        
        application = cursor.fetchone()
        
        if not application:
            print("Application not found.")
            conn.close()
            return
        
        print("\nApplication Details:")
        print("===================")
        print(f"Application ID: {application[0]}")
        print(f"Student: {application[2]} {application[3]} ({application[1]})")
        print(f"Application Date: {application[4]}")
        print(f"Preferred Building: {application[6] or 'No preference'}")
        print(f"Preferred Room Type: {application[7]}")
        print(f"Requested Move-in Date: {application[8]}")
        print(f"Requested Duration: {application[9]} months")
        print(f"Special Requirements: {application[10] or 'None'}")
        
        # Ask for decision
        print("\nProcess Application:")
        print("1. Approve")
        print("2. Reject")
        print("3. Put on Waiting List")
        print("4. Request More Information")
        print("5. Cancel")
        
        decision = input("\nEnter your decision (1-5): ")
        
        if decision == '5':
            print("Processing cancelled.")
            conn.close()
            return
        
        notes = input("Enter any notes regarding this decision: ").strip() or None
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if decision == '1':
            # Approve application
            status = 'Approved'
            
            # Find a suitable room
            preferred_building_id = application[5]
            preferred_room_type = application[7]
            
            if preferred_building_id:
                cursor.execute('''
                SELECT room_id, building_id, room_number, floor_number, room_type, monthly_rent
                FROM housing_rooms
                WHERE building_id = ? AND room_type = ? AND status = 'Available'
                ORDER BY floor_number, room_number
                ''', (preferred_building_id, preferred_room_type))
            else:
                cursor.execute('''
                SELECT room_id, building_id, room_number, floor_number, room_type, monthly_rent
                FROM housing_rooms
                WHERE room_type = ? AND status = 'Available'
                ORDER BY building_id, floor_number, room_number
                ''', (preferred_room_type,))
            
            available_rooms = cursor.fetchall()
            
            if not available_rooms:
                print("\nNo suitable rooms available matching the preferences.")
                print("Would you like to:")
                print("1. Select a different room type")
                print("2. Put application on waiting list")
                print("3. Cancel processing")
                
                alt_choice = input("\nEnter choice (1-3): ")
                
                if alt_choice == '1':
                    cursor.execute('''
                    SELECT DISTINCT room_type
                    FROM housing_rooms
                    WHERE status = 'Available'
                    ORDER BY room_type
                    ''')
                    
                    available_types = cursor.fetchall()
                    
                    if not available_types:
                        print("No rooms available at all. Application will be put on waiting list.")
                        cursor.execute('''
                        UPDATE housing_applications
                        SET status = 'Waiting List', notes = ?, reviewed_by = ?, review_date = ?, updated_at = ?
                        WHERE application_id = ?
                        ''', (notes, auth.current_user['username'], timestamp, timestamp, application_id))
                        
                        conn.commit()
                        print("Application has been put on waiting list.")
                        conn.close()
                        return
                    
                    print("\nAvailable Room Types:")
                    for i, room_type in enumerate(available_types, 1):
                        print(f"{i}. {room_type[0]}")
                    
                    while True:
                        try:
                            type_choice = int(input("\nSelect room type (enter number): "))
                            if 1 <= type_choice <= len(available_types):
                                alt_room_type = available_types[type_choice - 1][0]
                                break
                            else:
                                print(f"Please enter a number between 1 and {len(available_types)}.")
                        except ValueError:
                            print("Please enter a valid number.")
                    
                    if preferred_building_id:
                        cursor.execute('''
                        SELECT room_id, building_id, room_number, floor_number, room_type, monthly_rent
                        FROM housing_rooms
                        WHERE building_id = ? AND room_type = ? AND status = 'Available'
                        ORDER BY floor_number, room_number
                        ''', (preferred_building_id, alt_room_type))
                    else:
                        cursor.execute('''
                        SELECT room_id, building_id, room_number, floor_number, room_type, monthly_rent
                        FROM housing_rooms
                        WHERE room_type = ? AND status = 'Available'
                        ORDER BY building_id, floor_number, room_number
                        ''', (alt_room_type,))
                    
                    available_rooms = cursor.fetchall()
                    
                    if not available_rooms:
                        print("No suitable rooms available. Application will be put on waiting list.")
                        cursor.execute('''
                        UPDATE housing_applications
                        SET status = 'Waiting List', notes = ?, reviewed_by = ?, review_date = ?, updated_at = ?
                        WHERE application_id = ?
                        ''', (notes, auth.current_user['username'], timestamp, timestamp, application_id))
                        
                        conn.commit()
                        print("Application has been put on waiting list.")
                        conn.close()
                        return
                    
                elif alt_choice == '2':
                    cursor.execute('''
                    UPDATE housing_applications
                    SET status = 'Waiting List', notes = ?, reviewed_by = ?, review_date = ?, updated_at = ?
                    WHERE application_id = ?
                    ''', (notes, auth.current_user['username'], timestamp, timestamp, application_id))
                    
                    conn.commit()
                    print("Application has been put on waiting list.")
                    conn.close()
                    return
                    
                else:
                    print("Processing cancelled.")
                    conn.close()
                    return
            
            # Display available rooms
            print("\nAvailable Rooms:")
            print("===============")
            
            for i, room in enumerate(available_rooms, 1):
                building_id = room[1]
                cursor.execute('SELECT building_name FROM housing_buildings WHERE building_id = ?', (building_id,))
                building_name = cursor.fetchone()[0]
                
                print(f"{i}. Building: {building_name}, Room: {room[2]}, Floor: {room[3]}, Type: {room[4]}, Rent: ${room[5]}/month")
            
            while True:
                try:
                    room_choice = int(input("\nSelect room to assign (enter number): "))
                    if 1 <= room_choice <= len(available_rooms):
                        selected_room = available_rooms[room_choice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(available_rooms)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            # Create housing assignment
            room_id = selected_room[0]
            monthly_rent = selected_room[5]
            move_in_date = application[8]
            duration_months = application[9]
            move_out_date = (datetime.datetime.strptime(move_in_date, '%Y-%m-%d') + 
                            datetime.timedelta(days=30 * duration_months)).strftime('%Y-%m-%d')
            
            assignment_id = generate_id('ASG')
            contract_number = generate_id('CNT')
            
            cursor.execute('''
            INSERT INTO housing_assignments (
                assignment_id, application_id, student_id, room_id, move_in_date, planned_move_out_date,
                contract_number, monthly_rent, status, assigned_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                assignment_id, application_id, application[1], room_id, move_in_date, move_out_date,
                contract_number, monthly_rent, 'Active', auth.current_user['username'], timestamp, timestamp
            ))
            
            # Update room status
            cursor.execute('''
            UPDATE housing_rooms
            SET status = 'Reserved', current_occupants = current_occupants + 1, updated_at = ?
            WHERE room_id = ?
            ''', (timestamp, room_id))
            
            # Update building available rooms
            cursor.execute('''
            UPDATE housing_buildings
            SET available_rooms = available_rooms - 1, updated_at = ?
            WHERE building_id = ?
            ''', (timestamp, selected_room[1]))
            
        elif decision == '2':
            # Reject application
            status = 'Rejected'
            
        elif decision == '3':
            # Put on waiting list
            status = 'Waiting List'
            
        elif decision == '4':
            # Request more information
            status = 'More Info Needed'
        
        # Update application status
        cursor.execute('''
        UPDATE housing_applications
        SET status = ?, notes = ?, reviewed_by = ?, review_date = ?, updated_at = ?
        WHERE application_id = ?
        ''', (status, notes, auth.current_user['username'], timestamp, timestamp, application_id))
        
        conn.commit()
        print(f"\nApplication has been {status.lower()}.")
        
        # If approved, show assignment details
        if status == 'Approved':
            cursor.execute('''
            SELECT a.assignment_id, a.contract_number, r.room_number, b.building_name,
                   a.move_in_date, a.planned_move_out_date, a.monthly_rent
            FROM housing_assignments a
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.application_id = ?
            ''', (application_id,))
            
            assignment = cursor.fetchone()
            
            print("\nAssignment Details:")
            print("=================")
            print(f"Assignment ID: {assignment[0]}")
            print(f"Contract Number: {assignment[1]}")
            print(f"Room: {assignment[2]} in {assignment[3]}")
            print(f"Move-in Date: {assignment[4]}")
            print(f"Planned Move-out Date: {assignment[5]}")
            print(f"Monthly Rent: ${assignment[6]}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error processing application: {e}")

@log_read(module="housing", description="Viewing housing application")
def view_application():
    """View housing applications"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view housing applications.")
        return
    
    current_role = auth.current_user.get('role', '')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if current_role == 'student':
            # Students can only view their own applications
            if not auth.check_permission('view_own_record'):
                print("You don't have permission to view housing applications.")
                conn.close()
                return
            
            # Get the student ID associated with this user
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))
            
            result = cursor.fetchone()
            if not result or not result[0]:
                print("No student ID associated with your account.")
                conn.close()
                return
                
            student_id = result[0]
            
            # Fetch student's applications
            cursor.execute('''
            SELECT application_id, application_date, preferred_room_type, requested_move_in_date,
                   requested_duration_months, status, review_date
            FROM housing_applications
            WHERE student_id = ?
            ORDER BY application_date DESC
            ''', (student_id,))
            
            applications = cursor.fetchall()
            
            if not applications:
                print("You don't have any housing applications.")
                conn.close()
                return
            
            print("\nYour Housing Applications:")
            print("=========================")
            
            for i, app in enumerate(applications, 1):
                print(f"{i}. Application ID: {app[0]}")
                print(f"   Applied on: {app[1]}")
                print(f"   Room Type: {app[2]}")
                print(f"   Move-in Date: {app[3]}")
                print(f"   Duration: {app[4]} months")
                print(f"   Status: {app[5]}")
                if app[6]:
                    print(f"   Reviewed on: {app[6]}")
                print()
            
            # Select application to view details
            while True:
                try:
                    choice = int(input("\nSelect application to view (enter number): "))
                    if 1 <= choice <= len(applications):
                        application_id = applications[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(applications)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
        else:
            # Admin/staff can view any application
            if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
                print("You don't have permission to view housing applications.")
                conn.close()
                return
            
            # Allow filtering options
            print("\nView Applications:")
            print("1. View all applications")
            print("2. View by status")
            print("3. View by student")
            
            filter_choice = input("\nEnter choice (1-3): ")
            
            if filter_choice == '1':
                # View all applications
                cursor.execute('''
                SELECT a.application_id, a.student_id, s.first_name, s.last_name, a.application_date,
                       a.status, a.review_date
                FROM housing_applications a
                JOIN students s ON a.student_id = s.student_id
                ORDER BY a.application_date DESC
                ''')
                
            elif filter_choice == '2':
                # View by status
                print("\nSelect Status:")
                print("1. Pending")
                print("2. Approved")
                print("3. Rejected")
                print("4. Waiting List")
                print("5. More Info Needed")
                
                status_choice = input("\nEnter choice (1-5): ")
                status_map = {
                    '1': 'Pending',
                    '2': 'Approved',
                    '3': 'Rejected',
                    '4': 'Waiting List',
                    '5': 'More Info Needed'
                }
                
                if status_choice not in status_map:
                    print("Invalid choice.")
                    conn.close()
                    return
                
                cursor.execute('''
                SELECT a.application_id, a.student_id, s.first_name, s.last_name, a.application_date,
                       a.status, a.review_date
                FROM housing_applications a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.status = ?
                ORDER BY a.application_date DESC
                ''', (status_map[status_choice],))
                
            elif filter_choice == '3':
                # View by student
                student_id = select_student()
                if not student_id:
                    conn.close()
                    return
                
                cursor.execute('''
                SELECT a.application_id, a.student_id, s.first_name, s.last_name, a.application_date,
                       a.status, a.review_date
                FROM housing_applications a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.student_id = ?
                ORDER BY a.application_date DESC
                ''', (student_id,))
                
            else:
                print("Invalid choice.")
                conn.close()
                return
            
            applications = cursor.fetchall()
            
            if not applications:
                print("No applications found matching the criteria.")
                conn.close()
                return
            
            print("\nHousing Applications:")
            print("====================")
            
            for i, app in enumerate(applications, 1):
                print(f"{i}. ID: {app[0]} | Student: {app[2]} {app[3]} ({app[1]})")
                print(f"   Applied: {app[4]} | Status: {app[5]}")
                if app[6]:
                    print(f"   Reviewed: {app[6]}")
                print()
            
            # Select application to view details
            while True:
                try:
                    choice = int(input("\nSelect application to view (enter number): "))
                    if 1 <= choice <= len(applications):
                        application_id = applications[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(applications)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # View application details
        cursor.execute('''
        SELECT a.application_id, a.student_id, s.first_name, s.last_name, s.email_address,
               a.application_date, a.preferred_building_id, b.building_name, a.preferred_room_type,
               a.requested_move_in_date, a.requested_duration_months, a.special_requirements,
               a.status, a.notes, a.reviewed_by, a.review_date
        FROM housing_applications a
        JOIN students s ON a.student_id = s.student_id
        LEFT JOIN housing_buildings b ON a.preferred_building_id = b.building_id
        WHERE a.application_id = ?
        ''', (application_id,))
        
        application = cursor.fetchone()
        
        if not application:
            print("Application not found.")
            conn.close()
            return
        
        print("\nApplication Details:")
        print("===================")
        print(f"Application ID: {application[0]}")
        print(f"Student: {application[2]} {application[3]} ({application[1]})")
        print(f"Email: {application[4]}")
        print(f"Application Date: {application[5]}")
        print(f"Preferred Building: {application[7] or 'No preference'}")
        print(f"Preferred Room Type: {application[8]}")
        print(f"Requested Move-in Date: {application[9]}")
        print(f"Requested Duration: {application[10]} months")
        print(f"Special Requirements: {application[11] or 'None'}")
        print(f"Status: {application[12]}")
        if application[13]:
            print(f"Notes: {application[13]}")
        if application[14]:
            print(f"Reviewed by: {application[14]}")
        if application[15]:
            print(f"Review Date: {application[15]}")
        
        # Check if this application has an associated assignment
        cursor.execute('''
        SELECT a.assignment_id, a.room_id, r.room_number, b.building_name, a.move_in_date,
               a.planned_move_out_date, a.actual_move_out_date, a.monthly_rent, a.status,
               a.contract_number, a.assigned_by, a.created_at
        FROM housing_assignments a
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.application_id = ?
        ''', (application_id,))
        
        assignment = cursor.fetchone()
        
        if assignment:
            print("\nAssociated Housing Assignment:")
            print("============================")
            print(f"Assignment ID: {assignment[0]}")
            print(f"Contract Number: {assignment[9]}")
            print(f"Room: {assignment[2]} in {assignment[3]}")
            print(f"Move-in Date: {assignment[4]}")
            print(f"Planned Move-out Date: {assignment[5]}")
            if assignment[6]:
                print(f"Actual Move-out Date: {assignment[6]}")
            print(f"Monthly Rent: ${assignment[7]}")
            print(f"Status: {assignment[8]}")
            print(f"Assigned by: {assignment[10]}")
            print(f"Assignment Date: {assignment[11]}")
        
        # If staff/admin is viewing and application is pending, ask if they want to process it
        if (auth.check_permission('approve_accommodations') and application[12] == 'Pending'):
            process_now = input("\nDo you want to process this application now? (y/n): ").lower() == 'y'
            
            if process_now:
                conn.close()  # Close current connection before processing
                process_application(application_id)
                return
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing application: {e}")

# Housing Assignment Functions
@log_read(module="housing", description="Viewing housing assignment")
def view_assignment():
    """View housing assignments"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view housing assignments.")
        return
    
    current_role = auth.current_user.get('role', '')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if current_role == 'student':
            # Students can only view their own assignments
            if not auth.check_permission('view_own_record'):
                print("You don't have permission to view housing assignments.")
                conn.close()
                return
            
            # Get the student ID associated with this user
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))
            
            result = cursor.fetchone()
            if not result or not result[0]:
                print("No student ID associated with your account.")
                conn.close()
                return
                
            student_id = result[0]
            
            # Fetch student's assignments
            cursor.execute('''
            SELECT a.assignment_id, a.room_id, r.room_number, b.building_name, r.room_type,
                   a.move_in_date, a.planned_move_out_date, a.monthly_rent, a.status
            FROM housing_assignments a
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.student_id = ?
            ORDER BY a.created_at DESC
            ''', (student_id,))
            
            assignments = cursor.fetchall()
            
            if not assignments:
                print("You don't have any housing assignments.")
                conn.close()
                return
            
            print("\nYour Housing Assignments:")
            print("========================")
            
            for i, asn in enumerate(assignments, 1):
                print(f"{i}. Room {asn[2]} in {asn[3]} ({asn[4]})")
                print(f"   Move-in: {asn[5]} | Move-out: {asn[6]}")
                print(f"   Rent: ${asn[7]}/month | Status: {asn[8]}")
                print()
            
            # Select assignment to view details
            while True:
                try:
                    choice = int(input("\nSelect assignment to view (enter number): "))
                    if 1 <= choice <= len(assignments):
                        assignment_id = assignments[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(assignments)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
        else:
            # Admin/staff can view any assignment
            if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
                print("You don't have permission to view housing assignments.")
                conn.close()
                return
            
            # Allow filtering options
            print("\nView Assignments:")
            print("1. View all assignments")
            print("2. View by status")
            print("3. View by student")
            print("4. View by building")
            print("5. View by room")
            
            filter_choice = input("\nEnter choice (1-5): ")
            
            if filter_choice == '1':
                # View all assignments
                cursor.execute('''
                SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, r.room_number,
                       b.building_name, a.move_in_date, a.status
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                ORDER BY a.created_at DESC
                LIMIT 50  -- Limit to prevent too many results
                ''')
                
            elif filter_choice == '2':
                # View by status
                print("\nSelect Status:")
                print("1. Active")
                print("2. Pending")
                print("3. Terminated")
                print("4. Expired")
                
                status_choice = input("\nEnter choice (1-4): ")
                status_map = {
                    '1': 'Active',
                    '2': 'Pending',
                    '3': 'Terminated',
                    '4': 'Expired'
                }
                
                if status_choice not in status_map:
                    print("Invalid choice.")
                    conn.close()
                    return
                
                cursor.execute('''
                SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, r.room_number,
                       b.building_name, a.move_in_date, a.status
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE a.status = ?
                ORDER BY a.created_at DESC
                ''', (status_map[status_choice],))
                
            elif filter_choice == '3':
                # View by student
                student_id = select_student()
                if not student_id:
                    conn.close()
                    return
                
                cursor.execute('''
                SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, r.room_number,
                       b.building_name, a.move_in_date, a.status
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE a.student_id = ?
                ORDER BY a.created_at DESC
                ''', (student_id,))
                
            elif filter_choice == '4':
                # View by building
                cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
                buildings = cursor.fetchall()
                
                if not buildings:
                    print("No buildings found in the system.")
                    conn.close()
                    return
                
                print("\nSelect Building:")
                for i, (bid, bname) in enumerate(buildings, 1):
                    print(f"{i}. {bname}")
                
                while True:
                    try:
                        choice = int(input("\nSelect building (enter number): "))
                        if 1 <= choice <= len(buildings):
                            building_id = buildings[choice - 1][0]
                            break
                        else:
                            print(f"Please enter a number between 1 and {len(buildings)}.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                cursor.execute('''
                SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, r.room_number,
                       b.building_name, a.move_in_date, a.status
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE r.building_id = ?
                ORDER BY r.room_number
                ''', (building_id,))
                
            elif filter_choice == '5':
                # View by room
                cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
                buildings = cursor.fetchall()
                
                if not buildings:
                    print("No buildings found in the system.")
                    conn.close()
                    return
                
                print("\nSelect Building:")
                for i, (bid, bname) in enumerate(buildings, 1):
                    print(f"{i}. {bname}")
                
                while True:
                    try:
                        choice = int(input("\nSelect building (enter number): "))
                        if 1 <= choice <= len(buildings):
                            building_id = buildings[choice - 1][0]
                            break
                        else:
                            print(f"Please enter a number between 1 and {len(buildings)}.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                cursor.execute('''
                SELECT room_id, room_number, floor_number 
                FROM housing_rooms 
                WHERE building_id = ? 
                ORDER BY floor_number, room_number
                ''', (building_id,))
                
                rooms = cursor.fetchall()
                
                if not rooms:
                    print("No rooms found in this building.")
                    conn.close()
                    return
                
                print("\nSelect Room:")
                for i, room in enumerate(rooms, 1):
                    print(f"{i}. Room {room[1]} (Floor {room[2]})")
                
                while True:
                    try:
                        choice = int(input("\nSelect room (enter number): "))
                        if 1 <= choice <= len(rooms):
                            room_id = rooms[choice - 1][0]
                            break
                        else:
                            print(f"Please enter a number between 1 and {len(rooms)}.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                cursor.execute('''
                SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, r.room_number,
                       b.building_name, a.move_in_date, a.status
                FROM housing_assignments a
                JOIN students s ON a.student_id = s.student_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE a.room_id = ?
                ORDER BY a.created_at DESC
                ''', (room_id,))
                
            else:
                print("Invalid choice.")
                conn.close()
                return
            
            assignments = cursor.fetchall()
            
            if not assignments:
                print("No assignments found matching the criteria.")
                conn.close()
                return
            
            print("\nHousing Assignments:")
            print("===================")
            
            for i, asn in enumerate(assignments, 1):
                print(f"{i}. {asn[2]} {asn[3]} ({asn[1]}) | Room {asn[4]} in {asn[5]}")
                print(f"   Move-in: {asn[6]} | Status: {asn[7]}")
                print()
            
            # Select assignment to view details
            while True:
                try:
                    choice = int(input("\nSelect assignment to view (enter number): "))
                    if 1 <= choice <= len(assignments):
                        assignment_id = assignments[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(assignments)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # View assignment details
        cursor.execute('''
        SELECT a.assignment_id, a.application_id, a.student_id, s.first_name, s.last_name, s.email_address,
               a.room_id, r.room_number, r.floor_number, r.room_type, b.building_name, b.address,
               a.move_in_date, a.planned_move_out_date, a.actual_move_out_date, a.contract_number,
               a.monthly_rent, a.status, a.assigned_by, a.created_at
        FROM housing_assignments a
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.assignment_id = ?
        ''', (assignment_id,))
        
        assignment = cursor.fetchone()
        
        if not assignment:
            print("Assignment not found.")
            conn.close()
            return
        
        print("\nAssignment Details:")
        print("==================")
        print(f"Assignment ID: {assignment[0]}")
        if assignment[1]:
            print(f"Application ID: {assignment[1]}")
        print(f"Student: {assignment[3]} {assignment[4]} ({assignment[2]})")
        print(f"Email: {assignment[5]}")
        print(f"Room: {assignment[7]} (Floor {assignment[8]}) in {assignment[10]}")
        print(f"Room Type: {assignment[9]}")
        print(f"Building Address: {assignment[11]}")
        print(f"Move-in Date: {assignment[12]}")
        print(f"Planned Move-out Date: {assignment[13]}")
        if assignment[14]:
            print(f"Actual Move-out Date: {assignment[14]}")
        print(f"Contract Number: {assignment[15]}")
        print(f"Monthly Rent: ${assignment[16]}")
        print(f"Status: {assignment[17]}")
        print(f"Assigned by: {assignment[18]}")
        print(f"Assignment Date: {assignment[19]}")
        
        # Get payment information
        cursor.execute('''
        SELECT payment_id, amount, payment_date, payment_method, payment_period_start,
               payment_period_end, status
        FROM housing_payments
        WHERE assignment_id = ?
        ORDER BY payment_date DESC
        ''', (assignment_id,))
        
        payments = cursor.fetchall()
        
        if payments:
            print("\nPayment History:")
            print("===============")
            
            for i, payment in enumerate(payments, 1):
                print(f"{i}. ${payment[1]} - Paid on {payment[2]} via {payment[3]}")
                print(f"   Period: {payment[4]} to {payment[5]} | Status: {payment[6]}")
                print()
        
        # Get maintenance requests for this room
        cursor.execute('''
        SELECT request_id, request_date, issue_type, priority, status
        FROM housing_maintenance_requests
        WHERE room_id = ?
        ORDER BY request_date DESC
        ''', (assignment[6],))
        
        maintenance_requests = cursor.fetchall()
        
        if maintenance_requests:
            print("\nMaintenance Requests for this Room:")
            print("=================================")
            
            for i, request in enumerate(maintenance_requests, 1):
                print(f"{i}. {request[2]} - {request[1]} | Priority: {request[3]} | Status: {request[4]}")
        
        # If staff/admin and assignment is active, ask if they want to update status
        if (auth.check_permission('manage_accommodations') and assignment[17] == 'Active'):
            update_now = input("\nDo you want to update this assignment's status? (y/n): ").lower()
            
            if update_now == 'y':
                conn.close()  # Close current connection before updating
                update_assignment_status(assignment_id)
                return
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing assignment: {e}")

@log_update(module="housing", description="Updating assignment status")
def update_assignment_status(assignment_id=None):
    """Update the status of a housing assignment"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to update housing assignments.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to update housing assignments.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # If assignment_id not provided, let user select an assignment
        if assignment_id is None:
            cursor.execute('''
            SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, r.room_number,
                   b.building_name, a.status
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.status != 'Terminated' AND a.status != 'Expired'
            ORDER BY a.created_at DESC
            ''')
            
            assignments = cursor.fetchall()
            
            if not assignments:
                print("No active assignments found.")
                conn.close()
                return
            
            print("\nSelect Assignment to Update:")
            print("===========================")
            
            for i, asn in enumerate(assignments, 1):
                print(f"{i}. {asn[2]} {asn[3]} ({asn[1]}) | Room {asn[4]} in {asn[5]} | Status: {asn[6]}")
            
            while True:
                try:
                    choice = int(input("\nSelect assignment (enter number): "))
                    if 1 <= choice <= len(assignments):
                        assignment_id = assignments[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(assignments)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # Fetch assignment details
        cursor.execute('''
        SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, a.room_id, r.room_number,
               b.building_name, a.status
        FROM housing_assignments a
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.assignment_id = ?
        ''', (assignment_id,))
        
        assignment = cursor.fetchone()
        
        if not assignment:
            print("Assignment not found.")
            conn.close()
            return
        
        print("\nCurrent Assignment Information:")
        print(f"Assignment ID: {assignment[0]}")
        print(f"Student: {assignment[2]} {assignment[3]} ({assignment[1]})")
        print(f"Room: {assignment[5]} in {assignment[6]}")
        print(f"Current Status: {assignment[7]}")
        
        print("\nUpdate Status To:")
        print("1. Active")
        print("2. Terminated")
        print("3. Expired")
        print("4. Cancel update")
        
        status_choice = input("\nEnter choice (1-4): ")
        
        if status_choice == '4':
            print("Update cancelled.")
            conn.close()
            return
        
        status_map = {
            '1': 'Active',
            '2': 'Terminated',
            '3': 'Expired'
        }
        
        if status_choice not in status_map:
            print("Invalid choice.")
            conn.close()
            return
        
        new_status = status_map[status_choice]
        
        # If terminating or expiring, need move-out date
        actual_move_out_date = None
        if new_status in ('Terminated', 'Expired'):
            while True:
                move_out_date = input("Enter actual move-out date (YYYY-MM-DD, leave blank for today): ").strip()
                
                if not move_out_date:
                    actual_move_out_date = datetime.datetime.now().strftime('%Y-%m-%d')
                    break
                
                try:
                    # Validate date format
                    datetime.datetime.strptime(move_out_date, '%Y-%m-%d')
                    actual_move_out_date = move_out_date
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
        
        # Confirm update
        confirm = input(f"\nAre you sure you want to change status to {new_status}? (y/n): ").lower()
        
        if confirm != 'y':
            print("Update cancelled.")
            conn.close()
            return
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update assignment status
        if actual_move_out_date:
            cursor.execute('''
            UPDATE housing_assignments
            SET status = ?, actual_move_out_date = ?, updated_at = ?
            WHERE assignment_id = ?
            ''', (new_status, actual_move_out_date, timestamp, assignment_id))
        else:
            cursor.execute('''
            UPDATE housing_assignments
            SET status = ?, updated_at = ?
            WHERE assignment_id = ?
            ''', (new_status, timestamp, assignment_id))
        
        # If terminated or expired, update room status and building count
        if new_status in ('Terminated', 'Expired'):
            room_id = assignment[4]
            
            # Update room status
            cursor.execute('''
            UPDATE housing_rooms
            SET status = 'Available', current_occupants = current_occupants - 1, updated_at = ?
            WHERE room_id = ?
            ''', (timestamp, room_id))
            
            # Get building_id for the room
            cursor.execute('SELECT building_id FROM housing_rooms WHERE room_id = ?', (room_id,))
            building_id = cursor.fetchone()[0]
            
            # Update building available rooms
            cursor.execute('''
            UPDATE housing_buildings
            SET available_rooms = available_rooms + 1, updated_at = ?
            WHERE building_id = ?
            ''', (timestamp, building_id))
        
        conn.commit()
        print(f"\nAssignment status updated to {new_status} successfully!")
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error updating assignment: {e}")

# Maintenance Request Functions
@log_create(module="housing", description="Creating maintenance request")
def create_maintenance_request():
    """Create a new maintenance request"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create maintenance requests.")
        return
    
    current_role = auth.current_user.get('role', '')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if current_role == 'student':
            # Students can only create requests for their own room
            if not auth.check_permission('view_own_record'):
                print("You don't have permission to create maintenance requests.")
                conn.close()
                return
            
            # Get the student ID associated with this user
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))
            
            result = cursor.fetchone()
            if not result or not result[0]:
                print("No student ID associated with your account.")
                conn.close()
                return
                
            student_id = result[0]
            
            # Check if student has an active housing assignment
            cursor.execute('''
            SELECT a.assignment_id, a.room_id, r.room_number, b.building_name
            FROM housing_assignments a
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE a.student_id = ? AND a.status = 'Active'
            ''', (student_id,))
            
            assignment = cursor.fetchone()
            
            if not assignment:
                print("You do not have an active housing assignment.")
                conn.close()
                return
            
            assignment_id, room_id, room_number, building_name = assignment
            
            print(f"\nCreating Maintenance Request for Room {room_number} in {building_name}")
            
        else:
            # Staff/admin can create requests for any room
            if not auth.check_permission('manage_accommodations'):
                print("You don't have permission to create maintenance requests.")
                conn.close()
                return
            
            # Let staff/admin select a room
            print("\nSelect Building:")
            
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            
            if not buildings:
                print("No buildings found in the system.")
                conn.close()
                return
            
            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")
            
            while True:
                try:
                    choice = int(input("\nSelect building (enter number): "))
                    if 1 <= choice <= len(buildings):
                        building_id = buildings[choice - 1][0]
                        building_name = buildings[choice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(buildings)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT room_id, room_number, floor_number
            FROM housing_rooms
            WHERE building_id = ?
            ORDER BY floor_number, room_number
            ''', (building_id,))
            
            rooms = cursor.fetchall()
            
            if not rooms:
                print("No rooms found in this building.")
                conn.close()
                return
            
            print("\nSelect Room:")
            for i, room in enumerate(rooms, 1):
                print(f"{i}. Room {room[1]} (Floor {room[2]})")
            
            while True:
                try:
                    choice = int(input("\nSelect room (enter number): "))
                    if 1 <= choice <= len(rooms):
                        room_id = rooms[choice - 1][0]
                        room_number = rooms[choice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(rooms)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            # Check if room has an active occupant
            cursor.execute('''
            SELECT a.student_id, s.first_name, s.last_name
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.room_id = ? AND a.status = 'Active'
            ''', (room_id,))
            
            occupant = cursor.fetchone()
            
            if occupant:
                student_id = occupant[0]
                print(f"\nRoom occupied by: {occupant[1]} {occupant[2]} ({student_id})")
            else:
                # For empty rooms, staff can still create a request but need to select a student as "reporter"
                student_id = select_student()
                if not student_id:
                    conn.close()
                    return
            
            print(f"\nCreating Maintenance Request for Room {room_number} in {building_name}")
        
        # Get issue details
        print("\nSelect Issue Type:")
        issue_types = [
            "Plumbing", "Electrical", "HVAC", "Appliance", "Furniture",
            "Pest Control", "Structural", "Lock/Key", "Cleaning", "Other"
        ]
        
        for i, issue in enumerate(issue_types, 1):
            print(f"{i}. {issue}")
        
        while True:
            try:
                choice = int(input("\nSelect issue type (enter number): "))
                if 1 <= choice <= len(issue_types):
                    issue_type = issue_types[choice - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(issue_types)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        description = input("Detailed description of the issue: ").strip()
        if not description:
            print("Description cannot be empty.")
            conn.close()
            return
        
        print("\nSelect Priority:")
        print("1. Low")
        print("2. Medium")
        print("3. High")
        print("4. Emergency")
        
        while True:
            priority_choice = input("\nSelect priority (1-4): ")
            if priority_choice == '1':
                priority = 'Low'
                break
            elif priority_choice == '2':
                priority = 'Medium'
                break
            elif priority_choice == '3':
                priority = 'High'
                break
            elif priority_choice == '4':
                priority = 'Emergency'
                break
            else:
                print("Invalid choice. Please select 1-4.")
        
        # Create request
        request_id = generate_id('REQ')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO housing_maintenance_requests (
            request_id, room_id, student_id, request_date, issue_type, description, priority, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request_id, room_id, student_id, timestamp, issue_type, description, priority, 'Open',
            timestamp, timestamp
        ))
        
        conn.commit()
        print(f"\nMaintenance request created successfully with ID: {request_id}")
        
        # If emergency, display special message
        if priority == 'Emergency':
            print("\nEMERGENCY REQUEST FILED - Maintenance staff will be notified immediately.")
            print("For life-threatening emergencies, please also call campus security at 555-1234.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error creating maintenance request: {e}")

@log_read(module="housing", description="Viewing maintenance requests")
def view_maintenance_requests():
    """View maintenance requests"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view maintenance requests.")
        return
    
    current_role = auth.current_user.get('role', '')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if current_role == 'student':
            # Students can only view their own requests
            if not auth.check_permission('view_own_record'):
                print("You don't have permission to view maintenance requests.")
                conn.close()
                return
            
            # Get the student ID associated with this user
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))
            
            result = cursor.fetchone()
            if not result or not result[0]:
                print("No student ID associated with your account.")
                conn.close()
                return
                
            student_id = result[0]
            
            # Fetch student's maintenance requests
            cursor.execute('''
            SELECT m.request_id, m.room_id, r.room_number, b.building_name, m.request_date,
                   m.issue_type, m.status
            FROM housing_maintenance_requests m
            JOIN housing_rooms r ON m.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE m.student_id = ?
            ORDER BY m.request_date DESC
            ''', (student_id,))
            
            requests = cursor.fetchall()
            
            if not requests:
                print("You don't have any maintenance requests.")
                conn.close()
                return
            
            print("\nYour Maintenance Requests:")
            print("=========================")
            
            for i, req in enumerate(requests, 1):
                print(f"{i}. {req[5]} issue in {req[2]} ({req[3]}) - {req[4]}")
                print(f"   Status: {req[6]}")
                print()
            
            # Select request to view details
            while True:
                try:
                    choice = int(input("\nSelect request to view (enter number): "))
                    if 1 <= choice <= len(requests):
                        request_id = requests[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(requests)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
        else:
            # Admin/staff can view any request
            if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
                print("You don't have permission to view maintenance requests.")
                conn.close()
                return
            
            # Allow filtering options
            print("\nView Maintenance Requests:")
            print("1. View all requests")
            print("2. View by status")
            print("3. View by building")
            print("4. View by priority")
            print("5. View by student")
            
            filter_choice = input("\nEnter choice (1-5): ")
            
            if filter_choice == '1':
                # View all requests - limit to prevent too many results
                cursor.execute('''
                SELECT m.request_id, m.room_id, r.room_number, b.building_name, m.request_date,
                       m.issue_type, m.priority, m.status, m.student_id, s.first_name, s.last_name
                FROM housing_maintenance_requests m
                JOIN housing_rooms r ON m.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                JOIN students s ON m.student_id = s.student_id
                ORDER BY 
                    CASE m.status
                        WHEN 'Open' THEN 1
                        WHEN 'In Progress' THEN 2
                        WHEN 'Pending Parts' THEN 3
                        WHEN 'Complete' THEN 4
                        ELSE 5
                    END,
                    CASE m.priority
                        WHEN 'Emergency' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 4
                        ELSE 5
                    END,
                    m.request_date DESC
                LIMIT 50  -- Limit to prevent too many results
                ''')
                
            elif filter_choice == '2':
                # View by status
                print("\nSelect Status:")
                print("1. Open")
                print("2. In Progress")
                print("3. Pending Parts")
                print("4. Complete")
                
                status_choice = input("\nEnter choice (1-4): ")
                status_map = {
                    '1': 'Open',
                    '2': 'In Progress',
                    '3': 'Pending Parts',
                    '4': 'Complete'
                }
                
                if status_choice not in status_map:
                    print("Invalid choice.")
                    conn.close()
                    return
                
                cursor.execute('''
                SELECT m.request_id, m.room_id, r.room_number, b.building_name, m.request_date,
                       m.issue_type, m.priority, m.status, m.student_id, s.first_name, s.last_name
                FROM housing_maintenance_requests m
                JOIN housing_rooms r ON m.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                JOIN students s ON m.student_id = s.student_id
                WHERE m.status = ?
                ORDER BY 
                    CASE m.priority
                        WHEN 'Emergency' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 4
                        ELSE 5
                    END,
                    m.request_date DESC
                ''', (status_map[status_choice],))
                
            elif filter_choice == '3':
                # View by building
                cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
                buildings = cursor.fetchall()
                
                if not buildings:
                    print("No buildings found in the system.")
                    conn.close()
                    return
                
                print("\nSelect Building:")
                for i, (bid, bname) in enumerate(buildings, 1):
                    print(f"{i}. {bname}")
                
                while True:
                    try:
                        choice = int(input("\nSelect building (enter number): "))
                        if 1 <= choice <= len(buildings):
                            building_id = buildings[choice - 1][0]
                            break
                        else:
                            print(f"Please enter a number between 1 and {len(buildings)}.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                cursor.execute('''
                SELECT m.request_id, m.room_id, r.room_number, b.building_name, m.request_date,
                       m.issue_type, m.priority, m.status, m.student_id, s.first_name, s.last_name
                FROM housing_maintenance_requests m
                JOIN housing_rooms r ON m.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                JOIN students s ON m.student_id = s.student_id
                WHERE r.building_id = ?
                ORDER BY 
                    CASE m.status
                        WHEN 'Open' THEN 1
                        WHEN 'In Progress' THEN 2
                        WHEN 'Pending Parts' THEN 3
                        WHEN 'Complete' THEN 4
                        ELSE 5
                    END,
                    CASE m.priority
                        WHEN 'Emergency' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 4
                        ELSE 5
                    END,
                    m.request_date DESC
                ''', (building_id,))
                
            elif filter_choice == '4':
                # View by priority
                print("\nSelect Priority:")
                print("1. Emergency")
                print("2. High")
                print("3. Medium")
                print("4. Low")
                
                priority_choice = input("\nEnter choice (1-4): ")
                priority_map = {
                    '1': 'Emergency',
                    '2': 'High',
                    '3': 'Medium',
                    '4': 'Low'
                }
                
                if priority_choice not in priority_map:
                    print("Invalid choice.")
                    conn.close()
                    return
                
                cursor.execute('''
                SELECT m.request_id, m.room_id, r.room_number, b.building_name, m.request_date,
                       m.issue_type, m.priority, m.status, m.student_id, s.first_name, s.last_name
                FROM housing_maintenance_requests m
                JOIN housing_rooms r ON m.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                JOIN students s ON m.student_id = s.student_id
                WHERE m.priority = ?
                ORDER BY 
                    CASE m.status
                        WHEN 'Open' THEN 1
                        WHEN 'In Progress' THEN 2
                        WHEN 'Pending Parts' THEN 3
                        WHEN 'Complete' THEN 4
                        ELSE 5
                    END,
                    m.request_date DESC
                ''', (priority_map[priority_choice],))
                
            elif filter_choice == '5':
                # View by student
                student_id = select_student()
                if not student_id:
                    conn.close()
                    return
                
                cursor.execute('''
                SELECT m.request_id, m.room_id, r.room_number, b.building_name, m.request_date,
                       m.issue_type, m.priority, m.status, m.student_id, s.first_name, s.last_name
                FROM housing_maintenance_requests m
                JOIN housing_rooms r ON m.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                JOIN students s ON m.student_id = s.student_id
                WHERE m.student_id = ?
                ORDER BY 
                    CASE m.status
                        WHEN 'Open' THEN 1
                        WHEN 'In Progress' THEN 2
                        WHEN 'Pending Parts' THEN 3
                        WHEN 'Complete' THEN 4
                        ELSE 5
                    END,
                    CASE m.priority
                        WHEN 'Emergency' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 4
                        ELSE 5
                    END,
                    m.request_date DESC
                ''', (student_id,))
                
            else:
                print("Invalid choice.")
                conn.close()
                return
            
            requests = cursor.fetchall()
            
            if not requests:
                print("No maintenance requests found matching the criteria.")
                conn.close()
                return
            
            print("\nMaintenance Requests:")
            print("====================")
            
            for i, req in enumerate(requests, 1):
                print(f"{i}. {req[5]} issue - {req[2]} in {req[3]} | {req[4]}")
                print(f"   Reported by: {req[9]} {req[10]} | Priority: {req[6]} | Status: {req[7]}")
                print()
            
            # Select request to view details
            while True:
                try:
                    choice = int(input("\nSelect request to view (enter number): "))
                    if 1 <= choice <= len(requests):
                        request_id = requests[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(requests)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # View request details
        cursor.execute('''
        SELECT m.request_id, m.student_id, s.first_name, s.last_name, s.email_address,
               m.room_id, r.room_number, b.building_name, r.floor_number,
               m.request_date, m.issue_type, m.description, m.priority, m.status,
               m.assigned_to, m.scheduled_date, m.completion_date, m.feedback
        FROM housing_maintenance_requests m
        JOIN students s ON m.student_id = s.student_id
        JOIN housing_rooms r ON m.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE m.request_id = ?
        ''', (request_id,))
        
        request = cursor.fetchone()
        
        if not request:
            print("Request not found.")
            conn.close()
            return
        
        print("\nMaintenance Request Details:")
        print("===========================")
        print(f"Request ID: {request[0]}")
        print(f"Reported by: {request[2]} {request[3]} ({request[1]})")
        print(f"Email: {request[4]}")
        print(f"Room: {request[6]} (Floor {request[8]}) in {request[7]}")
        print(f"Request Date: {request[9]}")
        print(f"Issue Type: {request[10]}")
        print(f"Description: {request[11]}")
        print(f"Priority: {request[12]}")
        print(f"Status: {request[13]}")
        
        if request[14]:
            print(f"Assigned to: {request[14]}")
        if request[15]:
            print(f"Scheduled Date: {request[15]}")
        if request[16]:
            print(f"Completion Date: {request[16]}")
        if request[17]:
            print(f"Feedback: {request[17]}")
        
        # If staff/admin, ask if they want to update the request
        if auth.check_permission('manage_accommodations') and request[13] != 'Complete':
            update_now = input("\nDo you want to update this request? (y/n): ").lower()
            
            if update_now == 'y':
                conn.close()  # Close current connection before updating
                update_maintenance_request(request_id)
                return
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing maintenance requests: {e}")

@log_update(module="housing", description="Updating maintenance request")
def update_maintenance_request(request_id=None):
    """Update a maintenance request"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to update maintenance requests.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to update maintenance requests.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # If request_id not provided, let user select a request
        if request_id is None:
            cursor.execute('''
            SELECT m.request_id, r.room_number, b.building_name, m.issue_type,
                   m.priority, m.status, m.request_date
            FROM housing_maintenance_requests m
            JOIN housing_rooms r ON m.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE m.status != 'Complete'
            ORDER BY 
                CASE m.priority
                    WHEN 'Emergency' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    WHEN 'Low' THEN 4
                    ELSE 5
                END,
                m.request_date
            ''')
            
            requests = cursor.fetchall()
            
            if not requests:
                print("No open maintenance requests found.")
                conn.close()
                return
            
            print("\nSelect Request to Update:")
            print("========================")
            
            for i, req in enumerate(requests, 1):
                print(f"{i}. {req[3]} issue in {req[1]} ({req[2]}) - {req[6]}")
                print(f"   Priority: {req[4]} | Status: {req[5]}")
                print()
            
            while True:
                try:
                    choice = int(input("\nSelect request (enter number): "))
                    if 1 <= choice <= len(requests):
                        request_id = requests[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(requests)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # Fetch request details
        cursor.execute('''
        SELECT m.request_id, m.student_id, s.first_name, s.last_name,
               m.room_id, r.room_number, b.building_name,
               m.issue_type, m.description, m.priority, m.status,
               m.assigned_to, m.scheduled_date
        FROM housing_maintenance_requests m
        JOIN students s ON m.student_id = s.student_id
        JOIN housing_rooms r ON m.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE m.request_id = ?
        ''', (request_id,))
        
        request = cursor.fetchone()
        
        if not request:
            print("Request not found.")
            conn.close()
            return
        
        print("\nCurrent Request Information:")
        print(f"Request ID: {request[0]}")
        print(f"Student: {request[2]} {request[3]} ({request[1]})")
        print(f"Room: {request[5]} in {request[6]}")
        print(f"Issue Type: {request[7]}")
        print(f"Description: {request[8]}")
        print(f"Priority: {request[9]}")
        print(f"Current Status: {request[10]}")
        if request[11]:
            print(f"Assigned to: {request[11]}")
        if request[12]:
            print(f"Scheduled Date: {request[12]}")
        
        print("\nUpdate Options:")
        print("1. Update Status")
        print("2. Update Priority")
        print("3. Update Assignment")
        print("4. Update Scheduled Date")
        print("5. Mark as Complete")
        print("6. Cancel update")
        
        update_choice = input("\nEnter choice (1-6): ")
        
        if update_choice == '6':
            print("Update cancelled.")
            conn.close()
            return
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if update_choice == '1':
            # Update status
            print("\nSelect New Status:")
            print("1. Open")
            print("2. In Progress")
            print("3. Pending Parts")
            print("4. Complete")
            
            status_choice = input("\nEnter choice (1-4): ")
            status_map = {
                '1': 'Open',
                '2': 'In Progress',
                '3': 'Pending Parts',
                '4': 'Complete'
            }
            
            if status_choice not in status_map:
                print("Invalid choice.")
                conn.close()
                return
            
            new_status = status_map[status_choice]
            completion_date = None
            feedback = None
            
            if new_status == 'Complete':
                completion_date = timestamp
                feedback = input("Enter completion notes/feedback: ").strip() or None
                
                cursor.execute('''
                UPDATE housing_maintenance_requests
                SET status = ?, completion_date = ?, feedback = ?, updated_at = ?
                WHERE request_id = ?
                ''', (new_status, completion_date, feedback, timestamp, request_id))
            else:
                cursor.execute('''
                UPDATE housing_maintenance_requests
                SET status = ?, updated_at = ?
                WHERE request_id = ?
                ''', (new_status, timestamp, request_id))
            
        elif update_choice == '2':
            # Update priority
            print("\nSelect New Priority:")
            print("1. Low")
            print("2. Medium")
            print("3. High")
            print("4. Emergency")
            
            priority_choice = input("\nEnter choice (1-4): ")
            priority_map = {
                '1': 'Low',
                '2': 'Medium',
                '3': 'High',
                '4': 'Emergency'
            }
            
            if priority_choice not in priority_map:
                print("Invalid choice.")
                conn.close()
                return
            
            new_priority = priority_map[priority_choice]
            
            cursor.execute('''
            UPDATE housing_maintenance_requests
            SET priority = ?, updated_at = ?
            WHERE request_id = ?
            ''', (new_priority, timestamp, request_id))
            
        elif update_choice == '3':
            # Update assigned technician
            new_assigned = input("Enter name of assigned maintenance technician: ").strip()
            
            if not new_assigned:
                print("Assignment cannot be empty.")
                conn.close()
                return
            
            cursor.execute('''
            UPDATE housing_maintenance_requests
            SET assigned_to = ?, updated_at = ?
            WHERE request_id = ?
            ''', (new_assigned, timestamp, request_id))
            
        elif update_choice == '4':
            # Update scheduled date
            while True:
                scheduled_date = input("Enter scheduled maintenance date (YYYY-MM-DD): ")
                try:
                    # Validate date format
                    datetime.datetime.strptime(scheduled_date, '%Y-%m-%d')
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
            
            cursor.execute('''
            UPDATE housing_maintenance_requests
            SET scheduled_date = ?, updated_at = ?
            WHERE request_id = ?
            ''', (scheduled_date, timestamp, request_id))
            
        elif update_choice == '5':
            # Mark as complete
            completion_date = timestamp
            feedback = input("Enter completion notes/feedback: ").strip() or None
            
            cursor.execute('''
            UPDATE housing_maintenance_requests
            SET status = 'Complete', completion_date = ?, feedback = ?, updated_at = ?
            WHERE request_id = ?
            ''', ('Complete', completion_date, feedback, timestamp, request_id))
            
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        conn.commit()
        print("\nMaintenance request updated successfully!")
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error updating maintenance request: {e}")

# Payment Functions
@log_create(module="housing", description="Recording housing payment")
def record_payment():
    """Record a housing payment"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to record payments.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to record payments.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Select an active assignment for payment
        cursor.execute('''
        SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, r.room_number,
               b.building_name, a.monthly_rent
        FROM housing_assignments a
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.status = 'Active'
        ORDER BY s.last_name, s.first_name
        ''')
        
        assignments = cursor.fetchall()
        
        if not assignments:
            print("No active housing assignments found.")
            conn.close()
            return
        
        print("\nSelect Assignment for Payment:")
        print("============================")
        
        for i, asn in enumerate(assignments, 1):
            print(f"{i}. {asn[2]} {asn[3]} ({asn[1]}) - Room {asn[4]} in {asn[5]}")
            print(f"   Monthly Rent: ${asn[6]}")
            print()
        
        while True:
            try:
                choice = int(input("\nSelect assignment (enter number): "))
                if 1 <= choice <= len(assignments):
                    assignment = assignments[choice - 1]
                    assignment_id = assignment[0]
                    student_id = assignment[1]
                    student_name = f"{assignment[2]} {assignment[3]}"
                    monthly_rent = assignment[6]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(assignments)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get payment details
        print(f"\nRecording Payment for {student_name}")
        print(f"Regular Monthly Rent: ${monthly_rent}")
        
        while True:
            try:
                payment_amount = float(input("\nPayment Amount: $"))
                if payment_amount <= 0:
                    print("Payment amount must be greater than 0.")
                    continue
                break
            except ValueError:
                print("Please enter a valid amount.")
        
        # Payment method
        print("\nSelect Payment Method:")
        print("1. Credit Card")
        print("2. Bank Transfer")
        print("3. Cash")
        print("4. Check")
        print("5. Other")
        
        while True:
            method_choice = input("\nSelect method (1-5): ")
            if method_choice == '1':
                payment_method = 'Credit Card'
                break
            elif method_choice == '2':
                payment_method = 'Bank Transfer'
                break
            elif method_choice == '3':
                payment_method = 'Cash'
                break
            elif method_choice == '4':
                payment_method = 'Check'
                break
            elif method_choice == '5':
                payment_method = input("Specify payment method: ").strip()
                if not payment_method:
                    print("Payment method cannot be empty.")
                    continue
                break
            else:
                print("Invalid choice. Please select 1-5.")
        
        # Get transaction reference
        transaction_ref = input("Transaction Reference (optional): ").strip() or None
        
        # Payment period
        while True:
            try:
                period_start = input("Payment Period Start Date (YYYY-MM-DD): ")
                # Validate date format
                datetime.datetime.strptime(period_start, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        while True:
            try:
                period_end = input("Payment Period End Date (YYYY-MM-DD): ")
                # Validate date format
                datetime.datetime.strptime(period_end, '%Y-%m-%d')
                # Check that end date is after start date
                if datetime.datetime.strptime(period_end, '%Y-%m-%d') <= datetime.datetime.strptime(period_start, '%Y-%m-%d'):
                    print("End date must be after start date.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        # Create payment record
        payment_id = generate_id('PAY')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO housing_payments (
            payment_id, assignment_id, student_id, amount, payment_date, payment_method,
            transaction_reference, payment_period_start, payment_period_end, status,
            received_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            payment_id, assignment_id, student_id, payment_amount, timestamp, payment_method,
            transaction_ref, period_start, period_end, 'Completed',
            auth.current_user['username'], timestamp, timestamp
        ))
        
        conn.commit()

        # Record payment to central finance system
        finance_payment_id = record_payment_to_finance(
            student_id=student_id,
            amount=payment_amount,
            payment_method=payment_method,
            transaction_source='Housing',
            transaction_ref=payment_id,
            notes=f'Housing rent payment for period {period_start} to {period_end}',
            created_by=auth.current_user['username'] if auth and auth.current_user else None
        )

        print(f"\nPayment recorded successfully with ID: {payment_id}")
        print(f"Amount: ${payment_amount} | Method: {payment_method}")
        print(f"Period: {period_start} to {period_end}")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")

        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error recording payment: {e}")

@log_read(module="housing", description="Viewing payment history")
def view_payment_history():
    """View payment history"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view payment history.")
        return
    
    current_role = auth.current_user.get('role', '')
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if current_role == 'student':
            # Students can only view their own payment history
            if not auth.check_permission('view_own_record'):
                print("You don't have permission to view payment history.")
                conn.close()
                return
            
            # Get the student ID associated with this user
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))
            
            result = cursor.fetchone()
            if not result or not result[0]:
                print("No student ID associated with your account.")
                conn.close()
                return
                
            student_id = result[0]
            
            # Fetch student's payments
            cursor.execute('''
            SELECT p.payment_id, p.assignment_id, p.amount, p.payment_date, p.payment_method,
                   p.payment_period_start, p.payment_period_end, p.status,
                   r.room_number, b.building_name
            FROM housing_payments p
            JOIN housing_assignments a ON p.assignment_id = a.assignment_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE p.student_id = ?
            ORDER BY p.payment_date DESC
            ''', (student_id,))
            
            payments = cursor.fetchall()
            
            if not payments:
                print("You don't have any housing payment records.")
                conn.close()
                return
            
            print("\nYour Housing Payment History:")
            print("============================")
            
            for i, payment in enumerate(payments, 1):
                print(f"{i}. ${payment[2]} - Paid on {payment[3]} via {payment[4]}")
                print(f"   Room {payment[8]} in {payment[9]}")
                print(f"   Period: {payment[5]} to {payment[6]} | Status: {payment[7]}")
                print()
            
            # Display payment summary
            cursor.execute('''
            SELECT SUM(amount), COUNT(payment_id)
            FROM housing_payments
            WHERE student_id = ?
            ''', (student_id,))
            
            total = cursor.fetchone()
            
            print("\nPayment Summary:")
            print(f"Total Payments: {total[1]}")
            print(f"Total Amount Paid: ${total[0]}")
            
        else:
            # Admin/staff can view any payment history
            if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
                print("You don't have permission to view payment history.")
                conn.close()
                return
            
            # Allow filtering options
            print("\nView Payment History:")
            print("1. View by student")
            print("2. View by building")
            print("3. View by date range")
            print("4. View recent payments")
            
            filter_choice = input("\nEnter choice (1-4): ")
            
            if filter_choice == '1':
                # View by student
                student_id = select_student()
                if not student_id:
                    conn.close()
                    return
                
                cursor.execute('''
                SELECT p.payment_id, p.assignment_id, p.amount, p.payment_date, p.payment_method,
                       p.payment_period_start, p.payment_period_end, p.status,
                       r.room_number, b.building_name
                FROM housing_payments p
                JOIN housing_assignments a ON p.assignment_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE p.student_id = ?
                ORDER BY p.payment_date DESC
                ''', (student_id,))
                
                payments = cursor.fetchall()
                
                if not payments:
                    print("No payment records found for this student.")
                    conn.close()
                    return
                
                cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()
                
                print(f"\nPayment History for {student[0]} {student[1]} ({student_id}):")
                print("=" * 60)
                
                for i, payment in enumerate(payments, 1):
                    print(f"{i}. ${payment[2]} - Paid on {payment[3]} via {payment[4]}")
                    print(f"   Room {payment[8]} in {payment[9]}")
                    print(f"   Period: {payment[5]} to {payment[6]} | Status: {payment[7]}")
                    print()
                
                # Display payment summary
                cursor.execute('''
                SELECT SUM(amount), COUNT(payment_id)
                FROM housing_payments
                WHERE student_id = ?
                ''', (student_id,))
                
                total = cursor.fetchone()
                
                print("\nPayment Summary:")
                print(f"Total Payments: {total[1]}")
                print(f"Total Amount Paid: ${total[0]}")
                
            elif filter_choice == '2':
                # View by building
                cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
                buildings = cursor.fetchall()
                
                if not buildings:
                    print("No buildings found in the system.")
                    conn.close()
                    return
                
                print("\nSelect Building:")
                for i, (bid, bname) in enumerate(buildings, 1):
                    print(f"{i}. {bname}")
                
                while True:
                    try:
                        choice = int(input("\nSelect building (enter number): "))
                        if 1 <= choice <= len(buildings):
                            building_id = buildings[choice - 1][0]
                            building_name = buildings[choice - 1][1]
                            break
                        else:
                            print(f"Please enter a number between 1 and {len(buildings)}.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                cursor.execute('''
                SELECT p.payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_date, p.payment_method,
                       p.payment_period_start, p.payment_period_end, p.status,
                       r.room_number
                FROM housing_payments p
                JOIN students s ON p.student_id = s.student_id
                JOIN housing_assignments a ON p.assignment_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                WHERE r.building_id = ?
                ORDER BY p.payment_date DESC
                LIMIT 50  -- Limit to prevent too many results
                ''', (building_id,))
                
                payments = cursor.fetchall()
                
                if not payments:
                    print(f"No payment records found for {building_name}.")
                    conn.close()
                    return
                
                print(f"\nPayment History for {building_name}:")
                print("=" * 60)
                
                for i, payment in enumerate(payments, 1):
                    print(f"{i}. {payment[2]} {payment[3]} ({payment[1]}) - ${payment[4]}")
                    print(f"   Room: {payment[10]} | Paid on: {payment[5]} via {payment[6]}")
                    print(f"   Period: {payment[7]} to {payment[8]} | Status: {payment[9]}")
                    print()
                
                # Display payment summary
                cursor.execute('''
                SELECT SUM(p.amount), COUNT(p.payment_id)
                FROM housing_payments p
                JOIN housing_assignments a ON p.assignment_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                WHERE r.building_id = ?
                ''', (building_id,))
                
                total = cursor.fetchone()
                
                print("\nPayment Summary:")
                print(f"Total Payments: {total[1]}")
                print(f"Total Amount Paid: ${total[0]}")
                
            elif filter_choice == '3':
                # View by date range
                while True:
                    try:
                        start_date = input("Start Date (YYYY-MM-DD): ")
                        # Validate date format
                        datetime.datetime.strptime(start_date, '%Y-%m-%d')
                        break
                    except ValueError:
                        print("Invalid date format. Please use YYYY-MM-DD.")
                
                while True:
                    try:
                        end_date = input("End Date (YYYY-MM-DD): ")
                        # Validate date format
                        datetime.datetime.strptime(end_date, '%Y-%m-%d')
                        break
                    except ValueError:
                        print("Invalid date format. Please use YYYY-MM-DD.")
                
                cursor.execute('''
                SELECT p.payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_date, p.payment_method,
                       r.room_number, b.building_name, p.status
                FROM housing_payments p
                JOIN students s ON p.student_id = s.student_id
                JOIN housing_assignments a ON p.assignment_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE p.payment_date BETWEEN ? AND ?
                ORDER BY p.payment_date DESC
                ''', (start_date, end_date + ' 23:59:59'))
                
                payments = cursor.fetchall()
                
                if not payments:
                    print(f"No payment records found between {start_date} and {end_date}.")
                    conn.close()
                    return
                
                print(f"\nPayment History ({start_date} to {end_date}):")
                print("=" * 60)
                
                for i, payment in enumerate(payments, 1):
                    print(f"{i}. {payment[2]} {payment[3]} ({payment[1]}) - ${payment[4]}")
                    print(f"   Paid on: {payment[5]} via {payment[6]}")
                    print(f"   Room: {payment[7]} in {payment[8]} | Status: {payment[9]}")
                    print()
                
                # Display payment summary
                cursor.execute('''
                SELECT SUM(amount), COUNT(payment_id)
                FROM housing_payments
                WHERE payment_date BETWEEN ? AND ?
                ''', (start_date, end_date + ' 23:59:59'))
                
                total = cursor.fetchone()
                
                print("\nPayment Summary:")
                print(f"Total Payments: {total[1]}")
                print(f"Total Amount Paid: ${total[0]}")
                
            elif filter_choice == '4':
                # View recent payments (last 30 days)
                thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute('''
                SELECT p.payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_date, p.payment_method,
                       r.room_number, b.building_name, p.status
                FROM housing_payments p
                JOIN students s ON p.student_id = s.student_id
                JOIN housing_assignments a ON p.assignment_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE p.payment_date BETWEEN ? AND ?
                ORDER BY p.payment_date DESC
                ''', (thirty_days_ago, today + ' 23:59:59'))
                
                payments = cursor.fetchall()
                
                if not payments:
                    print("No payment records found in the last 30 days.")
                    conn.close()
                    return
                
                print(f"\nRecent Payments (Last 30 Days):")
                print("=" * 60)
                
                for i, payment in enumerate(payments, 1):
                    print(f"{i}. {payment[2]} {payment[3]} ({payment[1]}) - ${payment[4]}")
                    print(f"   Paid on: {payment[5]} via {payment[6]}")
                    print(f"   Room: {payment[7]} in {payment[8]} | Status: {payment[9]}")
                    print()
                
                # Display payment summary
                cursor.execute('''
                SELECT SUM(amount), COUNT(payment_id)
                FROM housing_payments
                WHERE payment_date BETWEEN ? AND ?
                ''', (thirty_days_ago, today + ' 23:59:59'))
                
                total = cursor.fetchone()
                
                print("\nPayment Summary:")
                print(f"Total Payments: {total[1]}")
                print(f"Total Amount Paid: ${total[0]}")
                
            else:
                print("Invalid choice.")
                conn.close()
                return
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing payment history: {e}")

# Inventory Management
@log_create(module="housing", description="Managing room inventory")
def manage_inventory():
    """Manage room inventory"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to manage inventory.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to manage inventory.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nInventory Management:")
        print("1. Add Inventory Item")
        print("2. View Room Inventory")
        print("3. Update Item Condition")
        print("4. Remove Item")
        print("5. Return to Housing Menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '5':
            conn.close()
            return
        
        # For all options except returning, we need to select a room
        if choice in ['1', '2', '3', '4']:
            print("\nSelect Building:")
            
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            
            if not buildings:
                print("No buildings found in the system.")
                conn.close()
                return
            
            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")
            
            while True:
                try:
                    bchoice = int(input("\nSelect building (enter number): "))
                    if 1 <= bchoice <= len(buildings):
                        building_id = buildings[bchoice - 1][0]
                        building_name = buildings[bchoice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(buildings)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT room_id, room_number, floor_number, room_type
            FROM housing_rooms
            WHERE building_id = ?
            ORDER BY floor_number, room_number
            ''', (building_id,))
            
            rooms = cursor.fetchall()
            
            if not rooms:
                print(f"No rooms found in {building_name}.")
                conn.close()
                return
            
            print(f"\nSelect Room in {building_name}:")
            for i, room in enumerate(rooms, 1):
                print(f"{i}. Room {room[1]} (Floor {room[2]}, {room[3]})")
            
            while True:
                try:
                    rchoice = int(input("\nSelect room (enter number): "))
                    if 1 <= rchoice <= len(rooms):
                        room_id = rooms[rchoice - 1][0]
                        room_number = rooms[rchoice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(rooms)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # Process the selected choice
        if choice == '1':
            # Add inventory item
            print(f"\nAdding Inventory Item to Room {room_number} in {building_name}")
            
            item_name = input("Item Name: ").strip()
            if not item_name:
                print("Item name cannot be empty.")
                conn.close()
                return
            
            print("\nSelect Item Type:")
            item_types = ["Furniture", "Appliance", "Electronic", "Kitchen", "Bathroom", "Decor", "Safety", "Other"]
            
            for i, itype in enumerate(item_types, 1):
                print(f"{i}. {itype}")
            
            while True:
                try:
                    tchoice = int(input("\nSelect item type (enter number): "))
                    if 1 <= tchoice <= len(item_types):
                        item_type = item_types[tchoice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(item_types)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            print("\nSelect Condition:")
            conditions = ["New", "Excellent", "Good", "Fair", "Poor", "Damaged"]
            
            for i, cond in enumerate(conditions, 1):
                print(f"{i}. {cond}")
            
            while True:
                try:
                    cchoice = int(input("\nSelect condition (enter number): "))
                    if 1 <= cchoice <= len(conditions):
                        condition = conditions[cchoice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(conditions)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            acquisition_date = input("Acquisition Date (YYYY-MM-DD, leave blank for today): ").strip()
            if not acquisition_date:
                acquisition_date = datetime.datetime.now().strftime('%Y-%m-%d')
            else:
                try:
                    # Validate date format
                    datetime.datetime.strptime(acquisition_date, '%Y-%m-%d')
                except ValueError:
                    print("Invalid date format. Using today's date instead.")
                    acquisition_date = datetime.datetime.now().strftime('%Y-%m-%d')
            
            notes = input("Additional Notes: ").strip() or None
            
            # Create inventory item
            item_id = generate_id('INV')
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO housing_inventory (
                item_id, room_id, item_name, item_type, condition, acquisition_date,
                status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item_id, room_id, item_name, item_type, condition, acquisition_date,
                'In Room', notes, timestamp, timestamp
            ))
            
            conn.commit()
            print(f"\nInventory item '{item_name}' added successfully with ID: {item_id}")
            
        elif choice == '2':
            # View room inventory
            cursor.execute('''
            SELECT item_id, item_name, item_type, condition, acquisition_date, status, notes
            FROM housing_inventory
            WHERE room_id = ?
            ORDER BY item_type, item_name
            ''', (room_id,))
            
            items = cursor.fetchall()
            
            if not items:
                print(f"\nNo inventory items found for Room {room_number} in {building_name}.")
                conn.close()
                return
            
            print(f"\nInventory for Room {room_number} in {building_name}:")
            print("=" * 80)
            print(f"{'Item':<20} {'Type':<15} {'Condition':<10} {'Acquired':<12} {'Status':<12}")
            print("-" * 80)
            
            for item in items:
                print(f"{item[1]:<20} {item[2]:<15} {item[3]:<10} {item[4]:<12} {item[5]:<12}")
                if item[6]:
                    print(f"   Notes: {item[6]}")
            
            print("=" * 80)
            
        elif choice == '3':
            # Update item condition
            cursor.execute('''
            SELECT item_id, item_name, item_type, condition
            FROM housing_inventory
            WHERE room_id = ?
            ORDER BY item_type, item_name
            ''', (room_id,))
            
            items = cursor.fetchall()
            
            if not items:
                print(f"\nNo inventory items found for Room {room_number} in {building_name}.")
                conn.close()
                return
            
            print(f"\nSelect Item to Update Condition:")
            for i, item in enumerate(items, 1):
                print(f"{i}. {item[1]} ({item[2]}) - Current Condition: {item[3]}")
            
            while True:
                try:
                    ichoice = int(input("\nSelect item (enter number): "))
                    if 1 <= ichoice <= len(items):
                        item_id = items[ichoice - 1][0]
                        item_name = items[ichoice - 1][1]
                        current_condition = items[ichoice - 1][3]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(items)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            print(f"\nCurrent Condition: {current_condition}")
            print("\nSelect New Condition:")
            conditions = ["New", "Excellent", "Good", "Fair", "Poor", "Damaged"]
            
            for i, cond in enumerate(conditions, 1):
                print(f"{i}. {cond}")
            
            while True:
                try:
                    cchoice = int(input("\nSelect condition (enter number): "))
                    if 1 <= cchoice <= len(conditions):
                        new_condition = conditions[cchoice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(conditions)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            notes = input("Additional Notes: ").strip() or None
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            UPDATE housing_inventory
            SET condition = ?, notes = ?, updated_at = ?
            WHERE item_id = ?
            ''', (new_condition, notes, timestamp, item_id))
            
            conn.commit()
            print(f"\nCondition for '{item_name}' updated from '{current_condition}' to '{new_condition}'")
            
        elif choice == '4':
            # Remove item
            cursor.execute('''
            SELECT item_id, item_name, item_type, condition
            FROM housing_inventory
            WHERE room_id = ?
            ORDER BY item_type, item_name
            ''', (room_id,))
            
            items = cursor.fetchall()
            
            if not items:
                print(f"\nNo inventory items found for Room {room_number} in {building_name}.")
                conn.close()
                return
            
            print(f"\nSelect Item to Remove:")
            for i, item in enumerate(items, 1):
                print(f"{i}. {item[1]} ({item[2]}) - Condition: {item[3]}")
            
            while True:
                try:
                    ichoice = int(input("\nSelect item (enter number): "))
                    if 1 <= ichoice <= len(items):
                        item_id = items[ichoice - 1][0]
                        item_name = items[ichoice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(items)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            print("\nRemoval Reason:")
            print("1. Damaged Beyond Repair")
            print("2. Replaced")
            print("3. Moved to Another Room")
            print("4. Lost/Stolen")
            print("5. Other")
            
            reason_choice = input("\nSelect reason (1-5): ")
            reason_map = {
                '1': 'Damaged Beyond Repair',
                '2': 'Replaced',
                '3': 'Moved to Another Room',
                '4': 'Lost/Stolen',
                '5': 'Other'
            }
            
            if reason_choice in reason_map:
                reason = reason_map[reason_choice]
            else:
                reason = "Other"
            
            additional_notes = input("Additional Notes: ").strip() or None
            
            confirm = input(f"\nAre you sure you want to remove '{item_name}'? (y/n): ").lower()
            
            if confirm == 'y':
                # Option to mark as removed instead of deleting
                mark_choice = input("Mark as removed (r) or permanently delete (d)? (r/d): ").lower()
                
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if mark_choice == 'd':
                    # Delete completely
                    cursor.execute('DELETE FROM housing_inventory WHERE item_id = ?', (item_id,))
                    print(f"\nItem '{item_name}' has been permanently deleted.")
                else:
                    # Mark as removed
                    notes_with_reason = f"Removed: {reason}"
                    if additional_notes:
                        notes_with_reason += f" - {additional_notes}"
                    
                    cursor.execute('''
                    UPDATE housing_inventory
                    SET status = 'Removed', notes = ?, updated_at = ?
                    WHERE item_id = ?
                    ''', (notes_with_reason, timestamp, item_id))
                    
                    print(f"\nItem '{item_name}' marked as removed with reason: {reason}")
                
                conn.commit()
            else:
                print("Removal cancelled.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error managing inventory: {e}")

# Room Inspections
@log_create(module="housing", description="Creating room inspection")
def create_inspection():
    """Create a new room inspection"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create inspections.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to create inspections.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Select a building
        print("\nSelect Building:")
        
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()
        
        if not buildings:
            print("No buildings found in the system.")
            conn.close()
            return
        
        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")
        
        while True:
            try:
                choice = int(input("\nSelect building (enter number): "))
                if 1 <= choice <= len(buildings):
                    building_id = buildings[choice - 1][0]
                    building_name = buildings[choice - 1][1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(buildings)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Select a room
        cursor.execute('''
        SELECT room_id, room_number, floor_number, room_type
        FROM housing_rooms
        WHERE building_id = ?
        ORDER BY floor_number, room_number
        ''', (building_id,))
        
        rooms = cursor.fetchall()
        
        if not rooms:
            print(f"No rooms found in {building_name}.")
            conn.close()
            return
        
        print(f"\nSelect Room in {building_name}:")
        for i, room in enumerate(rooms, 1):
            print(f"{i}. Room {room[1]} (Floor {room[2]}, {room[3]})")
        
        while True:
            try:
                choice = int(input("\nSelect room (enter number): "))
                if 1 <= choice <= len(rooms):
                    room_id = rooms[choice - 1][0]
                    room_number = rooms[choice - 1][1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(rooms)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get inspection details
        print(f"\nCreating Inspection for Room {room_number} in {building_name}")
        
        inspector_name = input("Inspector Name: ").strip()
        if not inspector_name:
            inspector_name = auth.current_user['username']
        
        inspection_date = input("Inspection Date (YYYY-MM-DD, leave blank for today): ").strip()
        if not inspection_date:
            inspection_date = datetime.datetime.now().strftime('%Y-%m-%d')
        else:
            try:
                # Validate date format
                datetime.datetime.strptime(inspection_date, '%Y-%m-%d')
            except ValueError:
                print("Invalid date format. Using today's date instead.")
                inspection_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        print("\nSelect Inspection Type:")
        inspection_types = ["Move-in", "Monthly", "Quarterly", "Annual", "Move-out", "Complaint", "Maintenance Follow-up"]
        
        for i, itype in enumerate(inspection_types, 1):
            print(f"{i}. {itype}")
        
        while True:
            try:
                choice = int(input("\nSelect inspection type (enter number): "))
                if 1 <= choice <= len(inspection_types):
                    inspection_type = inspection_types[choice - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(inspection_types)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        print("\nSelect Inspection Status:")
        status_types = ["Passed", "Failed", "Needs Follow-up", "Incomplete"]
        
        for i, status in enumerate(status_types, 1):
            print(f"{i}. {status}")
        
        while True:
            try:
                choice = int(input("\nSelect status (enter number): "))
                if 1 <= choice <= len(status_types):
                    inspection_status = status_types[choice - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(status_types)}.")
            except ValueError:
                print("Please enter a valid number.")
        
        findings = input("Findings/Notes: ").strip() or None
        
        action_required = None
        if inspection_status in ["Failed", "Needs Follow-up"]:
            action_required = input("Action Required: ").strip() or None
        
        follow_up_date = None
        if inspection_status == "Needs Follow-up":
            while True:
                follow_up = input("Follow-up Date (YYYY-MM-DD): ").strip()
                if not follow_up:
                    break
                
                try:
                    # Validate date format
                    datetime.datetime.strptime(follow_up, '%Y-%m-%d')
                    follow_up_date = follow_up
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
        
        # Create inspection record
        inspection_id = generate_id('INS')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO housing_inspections (
            inspection_id, room_id, inspector, inspection_date, inspection_type,
            status, findings, action_required, follow_up_date, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            inspection_id, room_id, inspector_name, inspection_date, inspection_type,
            inspection_status, findings, action_required, follow_up_date, timestamp, timestamp
        ))
        
        conn.commit()
        print(f"\nInspection created successfully with ID: {inspection_id}")
        
        # If inspection failed and action is required, ask if they want to create a maintenance request
        if inspection_status in ["Failed", "Needs Follow-up"] and action_required:
            create_maint = input("\nDo you want to create a maintenance request based on this inspection? (y/n): ").lower()
            
            if create_maint == 'y':
                conn.close()  # Close current connection before creating maintenance request
                
                # Pass state to maintenance request function if implemented
                # For now, just call the function and let the user select the room again
                create_maintenance_request()
                return
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error creating inspection: {e}")

@log_read(module="housing", description="Viewing room inspections")
def view_inspections():
    """View room inspections"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view inspections.")
        return
    
    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to view inspections.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Allow filtering options
        print("\nView Inspections:")
        print("1. View by building")
        print("2. View by room")
        print("3. View by date range")
        print("4. View by status")
        print("5. View all recent inspections")
        
        filter_choice = input("\nEnter choice (1-5): ")
        
        if filter_choice == '1':
            # View by building
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            
            if not buildings:
                print("No buildings found in the system.")
                conn.close()
                return
            
            print("\nSelect Building:")
            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")
            
            while True:
                try:
                    choice = int(input("\nSelect building (enter number): "))
                    if 1 <= choice <= len(buildings):
                        building_id = buildings[choice - 1][0]
                        building_name = buildings[choice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(buildings)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT i.inspection_id, i.room_id, r.room_number, r.floor_number, r.room_type,
                   i.inspection_date, i.inspection_type, i.status, i.inspector
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            WHERE r.building_id = ?
            ORDER BY i.inspection_date DESC
            ''', (building_id,))
            
            inspections = cursor.fetchall()
            
            if not inspections:
                print(f"No inspections found for {building_name}.")
                conn.close()
                return
            
            print(f"\nInspections for {building_name}:")
            print("=" * 80)
            
            for i, insp in enumerate(inspections, 1):
                print(f"{i}. Room {insp[2]} (Floor {insp[3]}, {insp[4]}) - {insp[5]}")
                print(f"   Type: {insp[6]} | Status: {insp[7]} | Inspector: {insp[8]}")
                print()
            
        elif filter_choice == '2':
            # View by room
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            
            if not buildings:
                print("No buildings found in the system.")
                conn.close()
                return
            
            print("\nSelect Building:")
            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")
            
            while True:
                try:
                    choice = int(input("\nSelect building (enter number): "))
                    if 1 <= choice <= len(buildings):
                        building_id = buildings[choice - 1][0]
                        building_name = buildings[choice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(buildings)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT room_id, room_number, floor_number, room_type
            FROM housing_rooms
            WHERE building_id = ?
            ORDER BY floor_number, room_number
            ''', (building_id,))
            
            rooms = cursor.fetchall()
            
            if not rooms:
                print(f"No rooms found in {building_name}.")
                conn.close()
                return
            
            print(f"\nSelect Room in {building_name}:")
            for i, room in enumerate(rooms, 1):
                print(f"{i}. Room {room[1]} (Floor {room[2]}, {room[3]})")
            
            while True:
                try:
                    choice = int(input("\nSelect room (enter number): "))
                    if 1 <= choice <= len(rooms):
                        room_id = rooms[choice - 1][0]
                        room_number = rooms[choice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(rooms)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT inspection_id, inspection_date, inspection_type, status, inspector,
                   findings, action_required, follow_up_date
            FROM housing_inspections
            WHERE room_id = ?
            ORDER BY inspection_date DESC
            ''', (room_id,))
            
            inspections = cursor.fetchall()
            
            if not inspections:
                print(f"No inspections found for Room {room_number} in {building_name}.")
                conn.close()
                return
            
            print(f"\nInspections for Room {room_number} in {building_name}:")
            print("=" * 80)
            
            for i, insp in enumerate(inspections, 1):
                print(f"{i}. {insp[1]} - {insp[2]}")
                print(f"   Status: {insp[3]} | Inspector: {insp[4]}")
                if insp[5]:
                    print(f"   Findings: {insp[5]}")
                if insp[6]:
                    print(f"   Action Required: {insp[6]}")
                if insp[7]:
                    print(f"   Follow-up Date: {insp[7]}")
                print()
            
        elif filter_choice == '3':
            # View by date range
            while True:
                try:
                    start_date = input("Start Date (YYYY-MM-DD): ")
                    # Validate date format
                    datetime.datetime.strptime(start_date, '%Y-%m-%d')
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
            
            while True:
                try:
                    end_date = input("End Date (YYYY-MM-DD): ")
                    # Validate date format
                    datetime.datetime.strptime(end_date, '%Y-%m-%d')
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
            
            cursor.execute('''
            SELECT i.inspection_id, i.room_id, r.room_number, b.building_name,
                   i.inspection_date, i.inspection_type, i.status, i.inspector
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE i.inspection_date BETWEEN ? AND ?
            ORDER BY i.inspection_date DESC
            ''', (start_date, end_date))
            
            inspections = cursor.fetchall()
            
            if not inspections:
                print(f"No inspections found between {start_date} and {end_date}.")
                conn.close()
                return
            
            print(f"\nInspections from {start_date} to {end_date}:")
            print("=" * 80)
            
            for i, insp in enumerate(inspections, 1):
                print(f"{i}. Room {insp[2]} in {insp[3]} - {insp[4]}")
                print(f"   Type: {insp[5]} | Status: {insp[6]} | Inspector: {insp[7]}")
                print()
            
        elif filter_choice == '4':
            # View by status
            print("\nSelect Status:")
            status_types = ["Passed", "Failed", "Needs Follow-up", "Incomplete"]
            
            for i, status in enumerate(status_types, 1):
                print(f"{i}. {status}")
            
            while True:
                try:
                    choice = int(input("\nSelect status (enter number): "))
                    if 1 <= choice <= len(status_types):
                        status = status_types[choice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(status_types)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT i.inspection_id, i.room_id, r.room_number, b.building_name,
                   i.inspection_date, i.inspection_type, i.inspector
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE i.status = ?
            ORDER BY i.inspection_date DESC
            ''', (status,))
            
            inspections = cursor.fetchall()
            
            if not inspections:
                print(f"No inspections found with status '{status}'.")
                conn.close()
                return
            
            print(f"\nInspections with Status '{status}':")
            print("=" * 80)
            
            for i, insp in enumerate(inspections, 1):
                print(f"{i}. Room {insp[2]} in {insp[3]} - {insp[4]}")
                print(f"   Type: {insp[5]} | Inspector: {insp[6]}")
                print()
            
        elif filter_choice == '5':
            # View all recent inspections (last 30 days)
            thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
            
            cursor.execute('''
            SELECT i.inspection_id, i.room_id, r.room_number, b.building_name,
                   i.inspection_date, i.inspection_type, i.status, i.inspector
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE i.inspection_date >= ?
            ORDER BY i.inspection_date DESC
            ''', (thirty_days_ago,))
            
            inspections = cursor.fetchall()
            
            if not inspections:
                print("No inspections found in the last 30 days.")
                conn.close()
                return
            
            print("\nRecent Inspections (Last 30 Days):")
            print("=" * 80)
            
            for i, insp in enumerate(inspections, 1):
                print(f"{i}. Room {insp[2]} in {insp[3]} - {insp[4]}")
                print(f"   Type: {insp[5]} | Status: {insp[6]} | Inspector: {insp[7]}")
                print()
            
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        # Select inspection to view details
        if inspections:
            while True:
                try:
                    choice = int(input("\nSelect inspection to view details (enter number): "))
                    if 1 <= choice <= len(inspections):
                        inspection_id = inspections[choice - 1][0]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(inspections)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT i.inspection_id, i.room_id, r.room_number, b.building_name,
                   i.inspector, i.inspection_date, i.inspection_type, i.status,
                   i.findings, i.action_required, i.follow_up_date, i.created_at
            FROM housing_inspections i
            JOIN housing_rooms r ON i.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE i.inspection_id = ?
            ''', (inspection_id,))
            
            inspection = cursor.fetchone()
            
            if inspection:
                print("\nInspection Details:")
                print("=" * 80)
                print(f"Inspection ID: {inspection[0]}")
                print(f"Room: {inspection[2]} in {inspection[3]}")
                print(f"Inspector: {inspection[4]}")
                print(f"Date: {inspection[5]}")
                print(f"Type: {inspection[6]}")
                print(f"Status: {inspection[7]}")
                
                if inspection[8]:
                    print(f"Findings: {inspection[8]}")
                if inspection[9]:
                    print(f"Action Required: {inspection[9]}")
                if inspection[10]:
                    print(f"Follow-up Date: {inspection[10]}")
                
                print(f"Created: {inspection[11]}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing inspections: {e}")

# Additional utility functions for housing accommodation management

@log_read(module="housing", description="Generating housing occupancy report")
def generate_occupancy_report():
    """Generate a comprehensive occupancy report"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to generate reports.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nHousing Occupancy Report")
        print("=" * 50)
        
        # Overall statistics
        cursor.execute('SELECT COUNT(*) FROM housing_buildings')
        total_buildings = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM housing_rooms')
        total_rooms = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Occupied"')
        occupied_rooms = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Available"')
        available_rooms = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM housing_assignments WHERE status = "Active"')
        active_assignments = cursor.fetchone()[0]
        
        occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
        
        print(f"Total Buildings: {total_buildings}")
        print(f"Total Rooms: {total_rooms}")
        print(f"Occupied Rooms: {occupied_rooms}")
        print(f"Available Rooms: {available_rooms}")
        print(f"Active Assignments: {active_assignments}")
        print(f"Occupancy Rate: {occupancy_rate:.1f}%")
        print()
        
        # Building breakdown
        cursor.execute('''
        SELECT b.building_name, b.total_rooms, b.available_rooms,
               (b.total_rooms - b.available_rooms) as occupied_rooms,
               ROUND((CAST(b.total_rooms - b.available_rooms AS FLOAT) / b.total_rooms) * 100, 1) as occupancy_rate
        FROM housing_buildings b
        ORDER BY b.building_name
        ''')
        
        buildings = cursor.fetchall()
        
        print("Building Breakdown:")
        print("-" * 80)
        print(f"{'Building':<25} {'Total':<8} {'Occupied':<10} {'Available':<10} {'Rate':<8}")
        print("-" * 80)
        
        for building in buildings:
            print(f"{building[0]:<25} {building[1]:<8} {building[3]:<10} {building[2]:<10} {building[4]:.1f}%")
        
        # Room type breakdown
        print("\nRoom Type Distribution:")
        print("-" * 50)
        
        cursor.execute('''
        SELECT room_type, COUNT(*) as total,
               SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occupied,
               SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available
        FROM housing_rooms
        GROUP BY room_type
        ORDER BY room_type
        ''')
        
        room_types = cursor.fetchall()
        
        print(f"{'Type':<12} {'Total':<8} {'Occupied':<10} {'Available':<10}")
        print("-" * 50)
        
        for room_type in room_types:
            print(f"{room_type[0]:<12} {room_type[1]:<8} {room_type[2]:<10} {room_type[3]:<10}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error generating report: {e}")

@log_read(module="housing", description="Generating financial report")
def generate_financial_report():
    """Generate a financial report for housing"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to generate financial reports.")
        return
    
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to generate financial reports.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nHousing Financial Report")
        print("=" * 50)
        
        # Monthly revenue calculation
        cursor.execute('''
        SELECT SUM(monthly_rent) as monthly_revenue
        FROM housing_assignments
        WHERE status = 'Active'
        ''')
        
        monthly_revenue = cursor.fetchone()[0] or 0
        
        print(f"Current Monthly Revenue: ${monthly_revenue:,.2f}")
        print(f"Projected Annual Revenue: ${monthly_revenue * 12:,.2f}")
        print()
        
        # Payment statistics for current year
        current_year = datetime.datetime.now().year
        
        cursor.execute('''
        SELECT COUNT(*) as payment_count, SUM(amount) as total_amount
        FROM housing_payments
        WHERE strftime('%Y', payment_date) = ?
        ''', (str(current_year),))
        
        year_stats = cursor.fetchone()
        payment_count = year_stats[0] or 0
        total_collected = year_stats[1] or 0
        
        print(f"Payments Collected This Year ({current_year}):")
        print(f"Number of Payments: {payment_count}")
        print(f"Total Amount Collected: ${total_collected:,.2f}")
        print()
        
        # Revenue by building
        cursor.execute('''
        SELECT b.building_name, COUNT(a.assignment_id) as active_assignments,
               SUM(a.monthly_rent) as monthly_revenue
        FROM housing_buildings b
        LEFT JOIN housing_rooms r ON b.building_id = r.building_id
        LEFT JOIN housing_assignments a ON r.room_id = a.room_id AND a.status = 'Active'
        GROUP BY b.building_id, b.building_name
        ORDER BY monthly_revenue DESC
        ''')
        
        building_revenue = cursor.fetchall()
        
        print("Revenue by Building:")
        print("-" * 60)
        print(f"{'Building':<25} {'Assignments':<12} {'Monthly Revenue':<15}")
        print("-" * 60)
        
        for building in building_revenue:
            assignments = building[1] or 0
            revenue = building[2] or 0
            print(f"{building[0]:<25} {assignments:<12} ${revenue:,.2f}")
        
        # Outstanding payments (simplified - would need more complex logic for real implementation)
        print("\nPayment Status Summary:")
        print("-" * 40)
        
        cursor.execute('''
        SELECT COUNT(*) as active_assignments
        FROM housing_assignments
        WHERE status = 'Active'
        ''')
        
        active_count = cursor.fetchone()[0] or 0
        
        # This is a simplified view - in a real system you'd track payment due dates
        print(f"Active Housing Assignments: {active_count}")
        print(f"Expected Monthly Collections: ${monthly_revenue:,.2f}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error generating financial report: {e}")

@log_export(module="housing", description="Exporting housing data")
def export_housing_data():
    """Export housing data to CSV format"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export data.")
        return
    
    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to export data.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nHousing Data Export")
        print("=" * 30)
        print("1. Export Building Data")
        print("2. Export Room Data")
        print("3. Export Assignment Data")
        print("4. Export Application Data")
        print("5. Export Payment Data")
        print("6. Export Maintenance Requests")
        print("7. Cancel")
        
        choice = input("\nSelect data to export (1-7): ")
        
        if choice == '7':
            conn.close()
            return
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if choice == '1':
            # Export building data
            cursor.execute('''
            SELECT building_id, building_name, address, campus_location, total_rooms, available_rooms,
                   has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at
            FROM housing_buildings
            ORDER BY building_name
            ''')
            
            data = cursor.fetchall()
            filename = f"housing_buildings_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Building ID', 'Building Name', 'Address', 'Campus Location', 
                               'Total Rooms', 'Available Rooms', 'Has Elevator', 'Has Accessible Rooms',
                               'Has Kitchen', 'Has Laundry', 'Created At'])
                writer.writerows(data)
            
            print(f"Building data exported to {filename}")
            
        elif choice == '2':
            # Export room data
            cursor.execute('''
            SELECT r.room_id, b.building_name, r.room_number, r.floor_number, r.room_type,
                   r.max_occupants, r.current_occupants, r.is_accessible, r.status, r.monthly_rent
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''')
            
            data = cursor.fetchall()
            filename = f"housing_rooms_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Room ID', 'Building', 'Room Number', 'Floor', 'Type',
                               'Max Occupants', 'Current Occupants', 'Accessible', 'Status', 'Monthly Rent'])
                writer.writerows(data)
            
            print(f"Room data exported to {filename}")
            
        elif choice == '3':
            # Export assignment data
            cursor.execute('''
            SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, 
                   b.building_name, r.room_number, a.move_in_date, a.planned_move_out_date,
                   a.monthly_rent, a.status, a.assigned_by
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY a.created_at DESC
            ''')
            
            data = cursor.fetchall()
            filename = f"housing_assignments_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Assignment ID', 'Student ID', 'First Name', 'Last Name',
                               'Building', 'Room', 'Move In Date', 'Planned Move Out', 
                               'Monthly Rent', 'Status', 'Assigned By'])
                writer.writerows(data)
            
            print(f"Assignment data exported to {filename}")
            
        elif choice == '4':
            # Export application data
            cursor.execute('''
            SELECT app.application_id, app.student_id, s.first_name, s.last_name,
                   app.application_date, b.building_name, app.preferred_room_type,
                   app.requested_move_in_date, app.requested_duration_months, app.status
            FROM housing_applications app
            JOIN students s ON app.student_id = s.student_id
            LEFT JOIN housing_buildings b ON app.preferred_building_id = b.building_id
            ORDER BY app.application_date DESC
            ''')
            
            data = cursor.fetchall()
            filename = f"housing_applications_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Application ID', 'Student ID', 'First Name', 'Last Name',
                               'Application Date', 'Preferred Building', 'Preferred Room Type',
                               'Requested Move In', 'Duration (Months)', 'Status'])
                writer.writerows(data)
            
            print(f"Application data exported to {filename}")
            
        elif choice == '5':
            # Export payment data
            cursor.execute('''
            SELECT p.payment_id, p.student_id, s.first_name, s.last_name,
                   p.amount, p.payment_date, p.payment_method, p.payment_period_start,
                   p.payment_period_end, p.status, b.building_name, r.room_number
            FROM housing_payments p
            JOIN students s ON p.student_id = s.student_id
            JOIN housing_assignments a ON p.assignment_id = a.assignment_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY p.payment_date DESC
            ''')
            
            data = cursor.fetchall()
            filename = f"housing_payments_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Payment ID', 'Student ID', 'First Name', 'Last Name',
                               'Amount', 'Payment Date', 'Payment Method', 'Period Start',
                               'Period End', 'Status', 'Building', 'Room'])
                writer.writerows(data)
            
            print(f"Payment data exported to {filename}")
            
        elif choice == '6':
            # Export maintenance requests
            cursor.execute('''
            SELECT m.request_id, m.student_id, s.first_name, s.last_name,
                   b.building_name, r.room_number, m.request_date, m.issue_type,
                   m.description, m.priority, m.status, m.assigned_to, m.completion_date
            FROM housing_maintenance_requests m
            JOIN students s ON m.student_id = s.student_id
            JOIN housing_rooms r ON m.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY m.request_date DESC
            ''')
            
            data = cursor.fetchall()
            filename = f"maintenance_requests_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Request ID', 'Student ID', 'First Name', 'Last Name',
                               'Building', 'Room', 'Request Date', 'Issue Type',
                               'Description', 'Priority', 'Status', 'Assigned To', 'Completion Date'])
                writer.writerows(data)
            
            print(f"Maintenance requests exported to {filename}")
            
        else:
            print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error exporting data: {e}")

@log_read(module="housing", description="Searching housing records")
def search_housing_records():
    """Search across housing records"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search records.")
        return
    
    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to search records.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nHousing Records Search")
        print("=" * 30)
        print("1. Search by Student Name/ID")
        print("2. Search by Room Number")
        print("3. Search by Building")
        print("4. Search Maintenance Requests")
        print("5. Cancel")
        
        choice = input("\nSelect search type (1-5): ")
        
        if choice == '5':
            conn.close()
            return
        
        if choice == '1':
            # Search by student
            search_term = input("Enter student name or ID: ").strip()
            
            cursor.execute('''
            SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address,
                   a.assignment_id, b.building_name, r.room_number, a.status
            FROM students s
            LEFT JOIN housing_assignments a ON s.student_id = a.student_id
            LEFT JOIN housing_rooms r ON a.room_id = r.room_id
            LEFT JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE s.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
            ORDER BY s.last_name, s.first_name
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            
            results = cursor.fetchall()
            
            if results:
                print(f"\nSearch Results for '{search_term}':")
                print("-" * 80)
                
                for result in results:
                    print(f"Student: {result[1]} {result[2]} ({result[0]})")
                    print(f"Email: {result[3]}")
                    if result[4]:  # Has assignment
                        print(f"Housing: Room {result[6]} in {result[5]} - Status: {result[7]}")
                    else:
                        print("Housing: No current assignment")
                    print()
            else:
                print(f"No results found for '{search_term}'")
                
        elif choice == '2':
            # Search by room number
            room_search = input("Enter room number: ").strip()
            
            cursor.execute('''
            SELECT r.room_id, r.room_number, b.building_name, r.room_type, r.status,
                   r.monthly_rent, a.student_id, s.first_name, s.last_name
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            LEFT JOIN housing_assignments a ON r.room_id = a.room_id AND a.status = 'Active'
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE r.room_number LIKE ?
            ORDER BY b.building_name, r.room_number
            ''', (f'%{room_search}%',))
            
            results = cursor.fetchall()
            
            if results:
                print(f"\nRoom Search Results for '{room_search}':")
                print("-" * 80)
                
                for result in results:
                    print(f"Room {result[1]} in {result[2]}")
                    print(f"Type: {result[3]} | Status: {result[4]} | Rent: ${result[5]}")
                    if result[6]:  # Has occupant
                        print(f"Occupant: {result[7]} {result[8]} ({result[6]})")
                    else:
                        print("Occupant: None")
                    print()
            else:
                print(f"No rooms found matching '{room_search}'")
                
        elif choice == '3':
            # Search by building
            building_search = input("Enter building name: ").strip()
            
            cursor.execute('''
            SELECT b.building_name, b.address, b.total_rooms, b.available_rooms,
                   COUNT(a.assignment_id) as active_assignments
            FROM housing_buildings b
            LEFT JOIN housing_rooms r ON b.building_id = r.building_id
            LEFT JOIN housing_assignments a ON r.room_id = a.room_id AND a.status = 'Active'
            WHERE b.building_name LIKE ?
            GROUP BY b.building_id, b.building_name, b.address, b.total_rooms, b.available_rooms
            ORDER BY b.building_name
            ''', (f'%{building_search}%',))
            
            results = cursor.fetchall()
            
            if results:
                print(f"\nBuilding Search Results for '{building_search}':")
                print("-" * 80)
                
                for result in results:
                    print(f"Building: {result[0]}")
                    print(f"Address: {result[1]}")
                    print(f"Total Rooms: {result[2]} | Available: {result[3]} | Active Assignments: {result[4]}")
                    print()
            else:
                print(f"No buildings found matching '{building_search}'")
                
        elif choice == '4':
            # Search maintenance requests
            search_term = input("Enter search term (issue type, description, or student name): ").strip()
            
            cursor.execute('''
            SELECT m.request_id, m.request_date, m.issue_type, m.description, m.priority, m.status,
                   s.first_name, s.last_name, b.building_name, r.room_number
            FROM housing_maintenance_requests m
            JOIN students s ON m.student_id = s.student_id
            JOIN housing_rooms r ON m.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE m.issue_type LIKE ? OR m.description LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
            ORDER BY m.request_date DESC
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            
            results = cursor.fetchall()
            
            if results:
                print(f"\nMaintenance Request Search Results for '{search_term}':")
                print("-" * 80)
                
                for result in results:
                    print(f"Request ID: {result[0]} | Date: {result[1]}")
                    print(f"Issue: {result[2]} | Priority: {result[4]} | Status: {result[5]}")
                    print(f"Student: {result[6]} {result[7]} | Room: {result[9]} in {result[8]}")
                    print(f"Description: {result[3]}")
                    print()
            else:
                print(f"No maintenance requests found matching '{search_term}'")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error searching records: {e}")

@log_read(module="housing", description="Checking room availability")
def check_room_availability():
    """Check room availability and generate availability report"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to check room availability.")
        return
    
    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to check room availability.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nRoom Availability Check")
        print("=" * 30)
        print("1. Check by Building")
        print("2. Check by Room Type")
        print("3. Check All Available Rooms")
        print("4. Check Accessible Rooms")
        print("5. Cancel")
        
        choice = input("\nSelect option (1-5): ")
        
        if choice == '5':
            conn.close()
            return
        
        if choice == '1':
            # Check by building
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()
            
            if not buildings:
                print("No buildings found.")
                conn.close()
                return
            
            print("\nSelect Building:")
            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")
            
            while True:
                try:
                    bchoice = int(input("\nSelect building (enter number): "))
                    if 1 <= bchoice <= len(buildings):
                        building_id = buildings[bchoice - 1][0]
                        building_name = buildings[bchoice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(buildings)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT room_number, floor_number, room_type, max_occupants, monthly_rent, is_accessible
            FROM housing_rooms
            WHERE building_id = ? AND status = 'Available'
            ORDER BY floor_number, room_number
            ''', (building_id,))
            
            available_rooms = cursor.fetchall()
            
            if available_rooms:
                print(f"\nAvailable Rooms in {building_name}:")
                print("-" * 70)
                print(f"{'Room':<8} {'Floor':<8} {'Type':<12} {'Max Occ.':<10} {'Rent':<10} {'Accessible':<12}")
                print("-" * 70)
                
                for room in available_rooms:
                    accessible = "Yes" if room[5] else "No"
                    print(f"{room[0]:<8} {room[1]:<8} {room[2]:<12} {room[3]:<10} ${room[4]:<9.2f} {accessible:<12}")
                
                print(f"\nTotal Available Rooms: {len(available_rooms)}")
            else:
                print(f"\nNo available rooms in {building_name}")
                
        elif choice == '2':
            # Check by room type
            room_types = ["Single", "Double", "Triple", "Suite", "Studio", "Apartment"]
            
            print("\nSelect Room Type:")
            for i, rtype in enumerate(room_types, 1):
                print(f"{i}. {rtype}")
            
            while True:
                try:
                    tchoice = int(input("\nSelect room type (enter number): "))
                    if 1 <= tchoice <= len(room_types):
                        room_type = room_types[tchoice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(room_types)}.")
                except ValueError:
                    print("Please enter a valid number.")
            
            cursor.execute('''
            SELECT r.room_number, b.building_name, r.floor_number, r.max_occupants, 
                   r.monthly_rent, r.is_accessible
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.room_type = ? AND r.status = 'Available'
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''', (room_type,))
            
            available_rooms = cursor.fetchall()
            
            if available_rooms:
                print(f"\nAvailable {room_type} Rooms:")
                print("-" * 80)
                print(f"{'Room':<8} {'Building':<20} {'Floor':<8} {'Max Occ.':<10} {'Rent':<10} {'Accessible':<12}")
                print("-" * 80)
                
                for room in available_rooms:
                    accessible = "Yes" if room[5] else "No"
                    print(f"{room[0]:<8} {room[1]:<20} {room[2]:<8} {room[3]:<10} ${room[4]:<9.2f} {accessible:<12}")
                
                print(f"\nTotal Available {room_type} Rooms: {len(available_rooms)}")
            else:
                print(f"\nNo available {room_type} rooms found")
                
        elif choice == '3':
            # Check all available rooms
            cursor.execute('''
            SELECT r.room_number, b.building_name, r.floor_number, r.room_type, 
                   r.max_occupants, r.monthly_rent, r.is_accessible
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.status = 'Available'
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''')
            
            available_rooms = cursor.fetchall()
            
            if available_rooms:
                print(f"\nAll Available Rooms:")
                print("-" * 90)
                print(f"{'Room':<8} {'Building':<20} {'Floor':<8} {'Type':<12} {'Max Occ.':<10} {'Rent':<10} {'Accessible':<12}")
                print("-" * 90)
                
                for room in available_rooms:
                    accessible = "Yes" if room[6] else "No"
                    print(f"{room[0]:<8} {room[1]:<20} {room[2]:<8} {room[3]:<12} {room[4]:<10} ${room[5]:<9.2f} {accessible:<12}")
                
                print(f"\nTotal Available Rooms: {len(available_rooms)}")
                
                # Summary by type
                cursor.execute('''
                SELECT room_type, COUNT(*) as count
                FROM housing_rooms
                WHERE status = 'Available'
                GROUP BY room_type
                ORDER BY room_type
                ''')
                
                type_summary = cursor.fetchall()
                
                print("\nAvailability Summary by Type:")
                print("-" * 30)
                for room_type, count in type_summary:
                    print(f"{room_type}: {count} rooms")
                    
            else:
                print("\nNo available rooms found")
                
        elif choice == '4':
            # Check accessible rooms
            cursor.execute('''
            SELECT r.room_number, b.building_name, r.floor_number, r.room_type, 
                   r.max_occupants, r.monthly_rent, r.status
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.is_accessible = 1
            ORDER BY r.status, b.building_name, r.floor_number, r.room_number
            ''')
            
            accessible_rooms = cursor.fetchall()
            
            if accessible_rooms:
                print(f"\nAccessible Rooms:")
                print("-" * 90)
                print(f"{'Room':<8} {'Building':<20} {'Floor':<8} {'Type':<12} {'Max Occ.':<10} {'Rent':<10} {'Status':<12}")
                print("-" * 90)
                
                available_count = 0
                for room in accessible_rooms:
                    if room[6] == 'Available':
                        available_count += 1
                    print(f"{room[0]:<8} {room[1]:<20} {room[2]:<8} {room[3]:<12} {room[4]:<10} ${room[5]:<9.2f} {room[6]:<12}")
                
                print(f"\nTotal Accessible Rooms: {len(accessible_rooms)}")
                print(f"Available Accessible Rooms: {available_count}")
                
            else:
                print("\nNo accessible rooms found")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error checking availability: {e}")

@log_read(module="housing", description="Generating maintenance summary")
def maintenance_summary():
    """Generate a summary of maintenance requests"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view maintenance summary.")
        return
    
    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to view maintenance summary.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nMaintenance Requests Summary")
        print("=" * 40)
        
        # Overall statistics
        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests')
        total_requests = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Open"')
        open_requests = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "In Progress"')
        in_progress = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Complete"')
        completed = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE priority = "Emergency"')
        emergency_requests = cursor.fetchone()[0]
        
        print(f"Total Requests: {total_requests}")
        print(f"Open Requests: {open_requests}")
        print(f"In Progress: {in_progress}")
        print(f"Completed: {completed}")
        print(f"Emergency Priority: {emergency_requests}")
        print()
        
        # Requests by status
        cursor.execute('''
        SELECT status, COUNT(*) as count
        FROM housing_maintenance_requests
        GROUP BY status
        ORDER BY 
            CASE status
                WHEN 'Open' THEN 1
                WHEN 'In Progress' THEN 2
                WHEN 'Pending Parts' THEN 3
                WHEN 'Complete' THEN 4
                ELSE 5
            END
        ''')
        
        status_breakdown = cursor.fetchall()
        
        print("Requests by Status:")
        print("-" * 25)
        for status, count in status_breakdown:
            print(f"{status}: {count}")
        print()
        
        # Requests by priority
        cursor.execute('''
        SELECT priority, COUNT(*) as count
        FROM housing_maintenance_requests
        GROUP BY priority
        ORDER BY 
            CASE priority
                WHEN 'Emergency' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END
        ''')
        
        priority_breakdown = cursor.fetchall()
        
        print("Requests by Priority:")
        print("-" * 25)
        for priority, count in priority_breakdown:
            print(f"{priority}: {count}")
        print()
        
        # Requests by issue type
        cursor.execute('''
        SELECT issue_type, COUNT(*) as count
        FROM housing_maintenance_requests
        GROUP BY issue_type
        ORDER BY count DESC
        ''')
        
        issue_breakdown = cursor.fetchall()
        
        print("Requests by Issue Type:")
        print("-" * 30)
        for issue_type, count in issue_breakdown:
            print(f"{issue_type}: {count}")
        print()
        
        # Recent requests (last 7 days)
        seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        
        cursor.execute('''
        SELECT COUNT(*) FROM housing_maintenance_requests
        WHERE request_date >= ?
        ''', (seven_days_ago,))
        
        recent_requests = cursor.fetchone()[0]
        
        print(f"New Requests (Last 7 Days): {recent_requests}")
        
        # Outstanding emergency requests
        cursor.execute('''
        SELECT COUNT(*) FROM housing_maintenance_requests
        WHERE priority = 'Emergency' AND status != 'Complete'
        ''')
        
        outstanding_emergency = cursor.fetchone()[0]
        
        if outstanding_emergency > 0:
            print(f"\n⚠️  URGENT: {outstanding_emergency} outstanding emergency request(s)")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error generating maintenance summary: {e}")

@log_read(module="housing", description="Generating upcoming move-outs report")
def upcoming_moveouts_report():
    """Generate a report of upcoming move-outs"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view move-outs report.")
        return
    
    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to view move-outs report.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nUpcoming Move-Outs Report")
        print("=" * 35)
        
        # Get current date and dates for next 30, 60, 90 days
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        thirty_days = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        sixty_days = (datetime.datetime.now() + datetime.timedelta(days=60)).strftime('%Y-%m-%d')
        ninety_days = (datetime.datetime.now() + datetime.timedelta(days=90)).strftime('%Y-%m-%d')
        
        # Next 30 days
        cursor.execute('''
        SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, 
               b.building_name, r.room_number, a.planned_move_out_date
        FROM housing_assignments a
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.status = 'Active' AND a.planned_move_out_date BETWEEN ? AND ?
        ORDER BY a.planned_move_out_date
        ''', (today, thirty_days))
        
        next_30_days = cursor.fetchall()
        
        print(f"Move-outs in Next 30 Days ({len(next_30_days)} assignments):")
        print("-" * 80)
        
        if next_30_days:
            print(f"{'Student':<25} {'Room':<15} {'Building':<20} {'Move-out Date':<15}")
            print("-" * 80)
            
            for assignment in next_30_days:
                student_name = f"{assignment[2]} {assignment[3]}"
                room_info = f"{assignment[5]}"
                print(f"{student_name:<25} {room_info:<15} {assignment[4]:<20} {assignment[6]:<15}")
        else:
            print("No move-outs scheduled in the next 30 days.")
        
        print()
        
        # Next 31-60 days
        cursor.execute('''
        SELECT COUNT(*)
        FROM housing_assignments
        WHERE status = 'Active' AND planned_move_out_date BETWEEN ? AND ?
        ''', (thirty_days, sixty_days))
        
        next_31_60_days = cursor.fetchone()[0]
        
        # Next 61-90 days
        cursor.execute('''
        SELECT COUNT(*)
        FROM housing_assignments
        WHERE status = 'Active' AND planned_move_out_date BETWEEN ? AND ?
        ''', (sixty_days, ninety_days))
        
        next_61_90_days = cursor.fetchone()[0]
        
        print("Summary:")
        print(f"Next 30 days: {len(next_30_days)} move-outs")
        print(f"Days 31-60: {next_31_60_days} move-outs")
        print(f"Days 61-90: {next_61_90_days} move-outs")
        
        # Buildings affected
        cursor.execute('''
        SELECT b.building_name, COUNT(*) as moveouts
        FROM housing_assignments a
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.status = 'Active' AND a.planned_move_out_date BETWEEN ? AND ?
        GROUP BY b.building_id, b.building_name
        ORDER BY moveouts DESC
        ''', (today, ninety_days))
        
        buildings_affected = cursor.fetchall()
        
        if buildings_affected:
            print("\nBuildings Affected (Next 90 Days):")
            print("-" * 40)
            for building, count in buildings_affected:
                print(f"{building}: {count} move-outs")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error generating move-outs report: {e}")

def display_reports_menu():
    """Display the reports and analytics menu"""
    while True:
        print("\nHousing Reports & Analytics")
        print("==========================")
        print("1. Occupancy Report")
        print("2. Financial Report")
        print("3. Maintenance Summary")
        print("4. Upcoming Move-outs")
        print("5. Room Availability Check")
        print("6. Search Housing Records")
        print("7. Export Data")
        print("8. Back to Housing Menu")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '1':
            generate_occupancy_report()
        elif choice == '2':
            generate_financial_report()
        elif choice == '3':
            maintenance_summary()
        elif choice == '4':
            upcoming_moveouts_report()
        elif choice == '5':
            check_room_availability()
        elif choice == '6':
            search_housing_records()
        elif choice == '7':
            export_housing_data()
        elif choice == '8':
            return
        else:
            print("Invalid choice. Please try again.")

# Main Menu Function
@log_menu_navigation(description="Displaying housing accommodation menu")
def display_housing_accommodation_menu():
    """Display the housing accommodation management menu"""
    global auth
    
    # First, initialize the housing database if not already done
    init_housing_db()
    
    while True:
        print("\nHousing Accommodation Management")
        print("===============================")
        
        # Different menu options based on permissions
        if auth.check_permission('manage_accommodations'):
            # Administrator / Housing Staff Menu
            print("1. Building Management")
            print("   - View/Add/Edit/Delete Buildings")
            print("   - Manage Rooms and Room Types")
            print("2. Housing Applications")
            print("   - View/Process Applications")
            print("3. Housing Assignments")
            print("   - View/Create/Update Assignments")
            print("4. Maintenance Requests")
            print("   - View/Create/Update Maintenance Requests")
            print("5. Payment Management")
            print("   - Record Payments")
            print("   - View Payment History")
            print("6. Room Inventory")
            print("   - Manage Room Inventory Items")
            print("7. Room Inspections")
            print("   - Create/View Room Inspections")
            print("8. Reports & Analytics")
            print("   - Generate Reports and Search Records")
            print("9. Return to Main Menu")
            
            choice = input("\nEnter your choice (1-8): ")
            
            if choice == '1':
                display_building_menu()
            elif choice == '2':
                display_application_menu()
            elif choice == '3':
                display_assignment_menu()
            elif choice == '4':
                display_maintenance_menu()
            elif choice == '5':
                display_payment_menu()
            elif choice == '6':
                manage_inventory()
            elif choice == '7':
                display_inspection_menu()
            elif choice == '8':
                display_reports_menu()
            elif choice == '9':
                return
            else:
                print("Invalid choice. Please try again.")
                
        elif auth.check_permission('view_accommodations'):
            # View-only Staff Menu
            print("1. View Buildings and Rooms")
            print("2. View Housing Applications")
            print("3. View Housing Assignments")
            print("4. View Maintenance Requests")
            print("5. View Payment History")
            print("6. View Room Inspections")
            print("7. Return to Main Menu")
            
            choice = input("\nEnter your choice (1-7): ")
            
            if choice == '1':
                view_building()
            elif choice == '2':
                view_application()
            elif choice == '3':
                view_assignment()
            elif choice == '4':
                view_maintenance_requests()
            elif choice == '5':
                view_payment_history()
            elif choice == '6':
                view_inspections()
            elif choice == '7':
                return
            else:
                print("Invalid choice. Please try again.")
                
        elif auth.check_permission('view_own_record'):
            # Student Menu
            print("1. My Housing Application")
            print("   - Apply for Housing")
            print("   - View My Application Status")
            print("2. My Housing Assignment")
            print("   - View My Room Assignment")
            print("3. Maintenance Requests")
            print("   - Report Maintenance Issues")
            print("   - View My Maintenance Requests")
            print("4. Return to Main Menu")
            
            choice = input("\nEnter your choice (1-4): ")
            
            if choice == '1':
                # Display student application menu
                subChoiceValid = False
                while not subChoiceValid:
                    print("\nHousing Application Options:")
                    print("1. Apply for Housing")
                    print("2. View My Application Status")
                    print("3. Back")
                    
                    sub_choice = input("\nEnter your choice (1-3): ")
                    
                    if sub_choice == '1':
                        create_application()
                        subChoiceValid = True
                    elif sub_choice == '2':
                        view_application()
                        subChoiceValid = True
                    elif sub_choice == '3':
                        subChoiceValid = True
                    else:
                        print("Invalid choice. Please try again.")
                
            elif choice == '2':
                view_assignment()
            elif choice == '3':
                # Display student maintenance menu
                subChoiceValid = False
                while not subChoiceValid:
                    print("\nMaintenance Request Options:")
                    print("1. Report a Maintenance Issue")
                    print("2. View My Maintenance Requests")
                    print("3. Back")
                    
                    sub_choice = input("\nEnter your choice (1-3): ")
                    
                    if sub_choice == '1':
                        create_maintenance_request()
                        subChoiceValid = True
                    elif sub_choice == '2':
                        view_maintenance_requests()
                        subChoiceValid = True
                    elif sub_choice == '3':
                        subChoiceValid = True
                    else:
                        print("Invalid choice. Please try again.")
                
            elif choice == '4':
                return
            else:
                print("Invalid choice. Please try again.")
        else:
            print("You don't have permission to access housing accommodation management.")
            return

# Sub-menu Functions
@log_menu_navigation(description="Displaying building management menu")
def display_building_menu():
    """Display the building management menu"""
    while True:
        print("\nBuilding Management")
        print("==================")
        print("1. View Buildings")
        print("2. Add New Building")
        print("3. Update Building")
        print("4. Delete Building")
        print("5. Back to Housing Menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            view_building()
        elif choice == '2':
            create_building()
        elif choice == '3':
            update_building()
        elif choice == '4':
            delete_building()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying application management menu")
def display_application_menu():
    """Display the application management menu"""
    while True:
        print("\nHousing Application Management")
        print("=============================")
        print("1. View Applications")
        print("2. Create New Application")
        print("3. Process Application")
        print("4. Back to Housing Menu")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == '1':
            view_application()
        elif choice == '2':
            create_application()
        elif choice == '3':
            process_application()
        elif choice == '4':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying assignment management menu")
def display_assignment_menu():
    """Display the assignment management menu"""
    while True:
        print("\nHousing Assignment Management")
        print("============================")
        print("1. View Assignments")
        print("2. Update Assignment Status")
        print("3. Back to Housing Menu")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == '1':
            view_assignment()
        elif choice == '2':
            update_assignment_status()
        elif choice == '3':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying maintenance management menu")
def display_maintenance_menu():
    """Display the maintenance management menu"""
    while True:
        print("\nMaintenance Request Management")
        print("=============================")
        print("1. View Maintenance Requests")
        print("2. Create New Maintenance Request")
        print("3. Update Maintenance Request")
        print("4. Back to Housing Menu")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == '1':
            view_maintenance_requests()
        elif choice == '2':
            create_maintenance_request()
        elif choice == '3':
            update_maintenance_request()
        elif choice == '4':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying payment management menu")
def display_payment_menu():
    """Display the payment management menu"""
    while True:
        print("\nPayment Management")
        print("=================")
        print("1. Record New Payment")
        print("2. View Payment History")
        print("3. Back to Housing Menu")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == '1':
            record_payment()
        elif choice == '2':
            view_payment_history()
        elif choice == '3':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying inspection management menu")
def display_inspection_menu():
    """Display the inspection management menu"""
    while True:
        print("\nRoom Inspection Management")
        print("=========================")
        print("1. Create New Inspection")
        print("2. View Inspections")
        print("3. Back to Housing Menu")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == '1':
            create_inspection()
        elif choice == '2':
            view_inspections()
        elif choice == '3':
            return
        else:
            print("Invalid choice. Please try again.")

# If this module is run directly
if __name__ == "__main__":
    print("Housing Accommodation Management")
