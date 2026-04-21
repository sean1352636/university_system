import logging
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.domain.mobility.services.parking_management.constants import PARKING_ZONES
from education_system.university_system.modules.domain.mobility.services.parking_management import core

_t = get_text
logger = configure_logging(name=__name__)


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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in view_parking_lots: {e}")
        print(f"An unexpected error occurred: {e}")


def add_parking_lot():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in add_parking_lot: {e}")
        print(f"An unexpected error occurred: {e}")


def update_parking_lot():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_parking_lot: {e}")
        print(f"An unexpected error occurred: {e}")


def delete_parking_lot():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in delete_parking_lot: {e}")
        print(f"An unexpected error occurred: {e}")


def update_available_spaces():
    auth = core.auth

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
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_available_spaces: {e}")
        print(f"An unexpected error occurred: {e}")
