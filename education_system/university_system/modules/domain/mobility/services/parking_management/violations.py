import logging
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.domain.mobility.services.parking_management import core

_t = get_text
logger = configure_logging(name=__name__)


def record_violation():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in record_violation: {e}")
        print(f"An unexpected error occurred: {e}")


def view_violations():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in view_violations: {e}")
        print(f"An unexpected error occurred: {e}")


def update_violation():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_violation: {e}")
        print(f"An unexpected error occurred: {e}")


def delete_violation():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in delete_violation: {e}")
        print(f"An unexpected error occurred: {e}")


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
