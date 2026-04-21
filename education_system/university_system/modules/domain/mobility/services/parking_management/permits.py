import logging
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.infrastructure.email import send_permit_confirmation, send_update_confirmation
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.domain.mobility.services.parking_management.constants import PARKING_ZONES, PERMIT_TYPES, VEHICLE_TYPES
from education_system.university_system.modules.domain.mobility.services.parking_management import core

_t = get_text
logger = configure_logging(name=__name__)


def create_parking_permit():
    auth = core.auth

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
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in view_parking_permit: {e}")
        print(f"An unexpected error occurred: {e}")

def update_parking_permit():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_parking_permit: {e}")
        print(f"An unexpected error occurred: {e}")

def delete_parking_permit():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in delete_parking_permit: {e}")
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
