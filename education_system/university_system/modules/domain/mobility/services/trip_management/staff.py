from . import _common
from ._common import sqlite3, get_text, logging, datetime, log_create
from .database import safe_db_operation


@log_create(module="trips", description="Assigning staff to trip")
def assign_trip_staff():
    """Assign staff members to trips"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_assign_staff", "You must be logged in to assign trip staff."))
        return False

    if not auth.check_permission('manage_trips'):
        print(get_text("mobility.trip_management.auth.no_permission_assign_staff", "You don't have permission to assign trip staff."))
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
            print(get_text("mobility.trip_management.staff.no_trips_available", "No trips available for staff assignment."))
            return False

        print("\n" + get_text("mobility.trip_management.staff.trips_available", "Trips Available for Staff Assignment:"))
        print("=" * 80)
        print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.status', 'Status'):<10}")
        print("-" * 80)

        for trip in trips:
            print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[4].title():<10}")

        print("=" * 80)

        try:
            trip_id = int(input(get_text("mobility.trip_management.staff.enter_trip_id", "\nEnter Trip ID to assign staff: ")))

            # Verify trip exists
            cursor.execute('SELECT trip_name FROM trips WHERE id = ?', (trip_id,))
            trip_result = cursor.fetchone()

            if not trip_result:
                print(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
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
                print(get_text("mobility.trip_management.staff.no_available_staff", "No available staff members to assign."))
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

            print(get_text("mobility.trip_management.staff.assigning_to", "\nAssigning staff to: {trip_name}").format(trip_name=trip_name))

            if current_staff:
                print("\n" + get_text("mobility.trip_management.staff.currently_assigned", "Currently Assigned Staff:"))
                for staff in current_staff:
                    role, name = staff
                    print(get_text("mobility.trip_management.staff.staff_line", "- {name} - {role}").format(name=name, role=role.title()))

            print("\n" + get_text("mobility.trip_management.staff.available_members", "Available Staff Members:"))
            print("-" * 70)
            print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.username', 'Username'):<20} {get_text('mobility.trip_management.headers.role', 'Role'):<15}")
            print("-" * 70)

            for staff in available_staff:
                user_id, first_name, last_name, username, role = staff
                full_name = f"{first_name} {last_name}"
                print(f"{user_id:<5} {full_name[:24]:<25} {username[:19]:<20} {role.title():<15}")

            print("-" * 70)

            staff_id = int(input(get_text("mobility.trip_management.staff.enter_staff_id", "\nEnter Staff User ID to assign: ")))

            # Verify staff selection
            selected_staff = None
            for staff in available_staff:
                if staff[0] == staff_id:
                    selected_staff = staff
                    break

            if not selected_staff:
                print(get_text("mobility.trip_management.staff.invalid_selection", "Invalid staff selection."))
                return False

            user_id, first_name, last_name, username, role = selected_staff
            staff_name = f"{first_name} {last_name}"

            # Select staff role for trip
            staff_roles = ['supervisor', 'coordinator', 'medical', 'transport']
            print(get_text("mobility.trip_management.staff.select_role", "\nAssigning {staff_name} to trip. Select role:").format(staff_name=staff_name))
            for i, role_option in enumerate(staff_roles, 1):
                print(f"{i}. {role_option.title()}")

            while True:
                try:
                    role_choice = int(input(get_text("mobility.trip_management.staff.select_role_prompt", "Select role (1-4): "))) - 1
                    if 0 <= role_choice < len(staff_roles):
                        selected_role = staff_roles[role_choice]
                        break
                    print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
                except ValueError:
                    print(get_text("mobility.trip_management.validation.enter_number", "Please enter a number."))

            # Assign staff to trip
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO trip_staff (trip_id, staff_user_id, role, assigned_date)
            VALUES (?, ?, ?, ?)
            ''', (trip_id, staff_id, selected_role, timestamp))

            print(get_text("mobility.trip_management.staff.assigned", "{staff_name} assigned to '{trip_name}' as {role}").format(staff_name=staff_name, trip_name=trip_name, role=selected_role.title()))
            return True

        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_input", "Invalid input."))
            return False
        except sqlite3.IntegrityError:
            print(get_text("mobility.trip_management.staff.already_assigned", "Staff member is already assigned to this trip."))
            return False
        except Exception as e:
            print(get_text("mobility.trip_management.errors.assigning_staff", "Error assigning staff: {error}").format(error=e))
            logging.error(get_text("mobility.trip_management.errors.in_assign_staff", "Error in assign_trip_staff: {error}").format(error=e))
            return False

    return safe_db_operation(assign_staff_operation)
