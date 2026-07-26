from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import common as _common
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection, generate_id,
    log_create, log_read,
)
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.maintenance import create_maintenance_request


def _capture_proposed_deductions(cursor, conn, inspection_id, room_id, *, created_by):
    """Prompt the inspector to itemise proposed deductions for a move-out inspection.

    Rows are written with status='Proposed' and linked to the inspection and the
    room's most-recent assignment. They remain proposed until process_deposit_refund
    commits them against the held deposit.
    """
    cursor.execute('''
        SELECT assignment_id, student_id
        FROM housing_assignments
        WHERE room_id = ?
        ORDER BY CASE WHEN status = 'Active' THEN 0 ELSE 1 END, created_at DESC
        LIMIT 1
    ''', (room_id,))
    row = cursor.fetchone()
    if not row:
        print("No assignment found for this room — skipping deduction capture.")
        return
    assignment_id, student_id = row

    raise_now = input(
        "\nCapture itemised deductions against the held deposit now? (y/n): "
    ).strip().lower()
    if raise_now != 'y':
        print("You can capture deductions later via Process Deposit Refund.")
        return

    print("\nEnter each deduction (blank description to finish).")
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    while True:
        desc = input("  Description: ").strip()
        if not desc:
            break
        while True:
            try:
                amt = float(input(f"  Amount for '{desc}': £"))
                if amt <= 0:
                    print("  Amount must be greater than 0.")
                    continue
                break
            except ValueError:
                print("  Enter a valid amount.")
        cursor.execute('''
            INSERT INTO housing_deposit_deductions
            (deduction_id, assignment_id, deposit_payment_id, inspection_id,
             description, amount, status, created_by, created_at)
            VALUES (?, ?, NULL, ?, ?, ?, 'Proposed', ?, ?)
        ''', (generate_id('DED'), assignment_id, inspection_id, desc, amt,
              created_by, timestamp))
        count += 1

    if count:
        try:
            from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import deposit_state
            deposit_state.reconcile_from_deductions(
                cursor, assignment_id, actor=created_by,
            )
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("state reconcile failed: %s", _e)
        conn.commit()
        print(f"Recorded {count} proposed deduction(s) for assignment {assignment_id}.")
        print(f"Process Deposit Refund (Payment Menu) to apply them against {student_id}'s deposit.")


# Room Inspections
@log_create(module="housing", description="Creating room inspection")
def create_inspection():
    """Create a new room inspection"""
    auth = _common.auth

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

        # Move-out inspections feed the deposit refund: capture proposed
        # deductions now so they're already itemised when the refund is processed.
        if inspection_type == "Move-out":
            _capture_proposed_deductions(
                cursor, conn, inspection_id, room_id,
                created_by=auth.current_user['username'],
            )

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
    auth = _common.auth

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
