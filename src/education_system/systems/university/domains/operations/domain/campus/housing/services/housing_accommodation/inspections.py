from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection, generate_id,
    log_create, log_read, log_update, log_delete,
)
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.maintenance import create_maintenance_request


# An inspection starts life booked, not judged: the outcome is recorded later
# through update_inspection_status.
#
# This is the single vocabulary for inspection status across the CLI, the GUI
# and the database. The GUI had drifted onto its own set — Completed / Issues
# Found / Follow-up Required — so the same inspection read differently
# depending on which interface you opened it in, and status filters silently
# missed rows written by the other one. The names below are the original ones
# the schema and reports were built around; the GUI now imports them from
# here rather than repeating string literals.
SCHEDULED_STATUS = "Scheduled"
OUTCOME_STATUSES = ["Passed", "Failed", "Needs Follow-up", "Incomplete"]
ALL_STATUSES = [SCHEDULED_STATUS] + OUTCOME_STATUSES

# Statuses the GUI used to write, mapped onto the canonical set. Kept so rows
# already in the database keep their meaning, and so anything still passing an
# old name lands on the right value instead of creating a sixth status.
LEGACY_STATUS_MAP = {
    "Completed": "Passed",
    "Issues Found": "Failed",
    "Follow-up Required": "Needs Follow-up",
    "Pending": SCHEDULED_STATUS,
    "In Progress": SCHEDULED_STATUS,
}


def normalise_status(status):
    """Map any legacy inspection status onto the canonical vocabulary."""
    if not status:
        return status
    if status in ALL_STATUSES:
        return status
    return LEGACY_STATUS_MAP.get(status, status)


def is_outcome(status):
    """True when *status* records a finished inspection rather than a booking."""
    return normalise_status(status) in OUTCOME_STATUSES


def _inspection_email_context(cursor, inspection_id):
    """Everything the inspection emails need, plus the room's residents.

    Returns ``None`` if the inspection has gone. The residents list can be
    empty — an inspection of an empty room is perfectly normal, and the
    caller reports that rather than treating it as a failure.
    """
    cursor.execute("""
    SELECT i.inspection_id, i.room_id, i.inspector, i.inspection_date,
           i.inspection_type, i.status, i.findings, i.action_required,
           i.follow_up_date, b.building_name, r.room_number, r.floor_number
    FROM housing_inspections i
    JOIN housing_rooms r ON i.room_id = r.room_id
    JOIN housing_buildings b ON r.building_id = b.building_id
    WHERE i.inspection_id = ?
    """, (inspection_id,))
    row = cursor.fetchone()
    if not row:
        return None

    context = {
        'inspection_id': row[0], 'room_id': row[1], 'inspector': row[2],
        'inspection_date': row[3], 'inspection_type': row[4], 'status': row[5],
        'findings': row[6], 'action_required': row[7], 'follow_up_date': row[8],
        'building_name': row[9], 'room_number': row[10], 'floor_number': row[11],
    }
    context['residents'] = _common.room_occupants(cursor, row[1])
    return context


def _notify_residents(context, send_fn, label):
    """Send one inspection email per resident of the room. Prints a summary."""
    residents = context.get('residents') or []
    if not residents:
        print(f"{label}: nobody is currently assigned to this room, so no email was sent.")
        return 0, 0

    sent = failed = 0
    for person in residents:
        payload = dict(context)
        payload['student_name'] = person['student_name']
        payload['student_id'] = person['student_id']
        payload['student_email'] = person['email_address']
        if send_fn(payload):
            sent += 1
        else:
            failed += 1
    print(f"{label}: {sent} email(s) sent, {failed} failed.")
    return sent, failed


def _select_inspection(cursor, prompt="Select inspection"):
    """Pick a recent inspection. Returns its id, or None."""
    cursor.execute("""
    SELECT i.inspection_id, b.building_name, r.room_number, i.inspection_date,
           i.inspection_type, i.status
    FROM housing_inspections i
    JOIN housing_rooms r ON i.room_id = r.room_id
    JOIN housing_buildings b ON r.building_id = b.building_id
    ORDER BY i.created_at DESC
    LIMIT 50
    """)
    rows = cursor.fetchall()
    if not rows:
        print("No inspections found.")
        return None

    print(f"\n{prompt}:")
    print("=" * 60)
    for i, row in enumerate(rows, 1):
        print(f"{i}. {row[1]} room {row[2]} - {row[3]} - {row[4]} [{row[5]}]")

    while True:
        raw = input(f"\nSelect inspection (1-{len(rows)}, or 'q' to cancel): ").strip()
        if raw.lower() in ('q', 'quit', 'cancel', 'back', 'exit'):
            return None
        if not raw:
            print("This field cannot be left blank. Please try again.")
            continue
        try:
            choice = int(raw)
        except ValueError:
            print("Please enter a valid number.")
            continue
        if 1 <= choice <= len(rows):
            return rows[choice - 1][0]
        print(f"Please enter a number between 1 and {len(rows)}.")


def _prompt_date(label, allow_blank=True):
    """Ask for a YYYY-MM-DD date, re-asking until it parses."""
    while True:
        raw = input(f"{label}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("This field cannot be left blank. Please try again.")
            continue
        try:
            datetime.datetime.strptime(raw, '%Y-%m-%d')
            return raw
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")


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
            from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation import deposit_state
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

        # A brand-new inspection has not happened yet, so it starts as
        # Scheduled. The outcome is recorded later through Update Inspection
        # Status, which is also what emails the student their results — asking
        # for a Passed/Failed verdict at creation time meant booking an
        # inspection and judging it in the same breath.
        inspection_status = SCHEDULED_STATUS

        inspection_time = input("Inspection Time (e.g. 10:00, optional): ").strip() or None

        findings = input("Notes for the resident (optional): ").strip() or None
        action_required = None
        follow_up_date = None

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

        context = _inspection_email_context(cursor, inspection_id)

        conn.commit()
        print(f"\nInspection created successfully with ID: {inspection_id}")
        print(f"Status: {inspection_status} — record the outcome later via "
              f"'Update Inspection Status'.")

        # Move-out inspections feed the deposit refund: capture proposed
        # deductions now so they're already itemised when the refund is processed.
        if inspection_type == "Move-out":
            _capture_proposed_deductions(
                cursor, conn, inspection_id, room_id,
                created_by=auth.current_user['username'],
            )

        conn.close()

        # Tell whoever lives in the room that an inspection is booked. After
        # the commit, so nothing is announced that rolled back.
        if context:
            context['inspection_time'] = inspection_time
            _notify_residents(context, _common.send_inspection_scheduled_email,
                              "Inspection notice")

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


@log_update(module="housing", description="Updating room inspection")
def update_inspection():
    """Edit an inspection's details (date, type, inspector, notes)."""
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to update inspections.")
        return
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to update inspections.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        inspection_id = _select_inspection(cursor, "Select inspection to update")
        if not inspection_id:
            conn.close()
            return

        cursor.execute('''
        SELECT inspector, inspection_date, inspection_type, findings, action_required
        FROM housing_inspections WHERE inspection_id = ?
        ''', (inspection_id,))
        current = cursor.fetchone()
        if not current:
            print("Inspection not found.")
            conn.close()
            return

        print("\nLeave a field blank to keep its current value.")
        inspector = input(f"Inspector [{current[0]}]: ").strip() or current[0]

        new_date = _prompt_date(f"Inspection Date (YYYY-MM-DD) [{current[1]}]")
        inspection_date = new_date or current[1]
        date_changed = new_date is not None and new_date != current[1]

        print("\nInspection Type:")
        inspection_types = ["Move-in", "Monthly", "Quarterly", "Annual",
                            "Move-out", "Complaint", "Maintenance Follow-up"]
        for i, itype in enumerate(inspection_types, 1):
            print(f"{i}. {itype}")
        raw = input(f"Select type (1-{len(inspection_types)}) [{current[2]}]: ").strip()
        inspection_type = current[2]
        if raw:
            try:
                choice = int(raw)
                if 1 <= choice <= len(inspection_types):
                    inspection_type = inspection_types[choice - 1]
                else:
                    print(f"Out of range — keeping '{current[2]}'.")
            except ValueError:
                print(f"Not a number — keeping '{current[2]}'.")

        findings = input(f"Notes/Findings [{current[3] or 'none'}]: ").strip() or current[3]
        action_required = input(
            f"Action Required [{current[4] or 'none'}]: ").strip() or current[4]

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        UPDATE housing_inspections
        SET inspector = ?, inspection_date = ?, inspection_type = ?,
            findings = ?, action_required = ?, updated_at = ?
        WHERE inspection_id = ?
        ''', (inspector, inspection_date, inspection_type, findings,
              action_required, timestamp, inspection_id))

        context = _inspection_email_context(cursor, inspection_id)
        conn.commit()
        print(f"\nInspection {inspection_id} updated.")
        conn.close()

        # Only bother the resident when the date moved — an inspector name or
        # a note correction is not something they need an email about.
        if date_changed and context:
            print("The inspection date changed, so the resident(s) will be re-notified.")
            _notify_residents(context, _common.send_inspection_scheduled_email,
                              "Updated inspection notice")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error updating inspection: {e}")


@log_update(module="housing", description="Updating inspection status")
def update_inspection_status():
    """Record the outcome of an inspection and tell the resident.

    This is where a Scheduled inspection becomes Passed / Failed /
    Needs Follow-up / Incomplete. Choosing 'Needs Follow-up' asks for the new
    date and the reason, and the resident is emailed both.
    """
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to update inspections.")
        return
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to update inspections.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        inspection_id = _select_inspection(cursor, "Select inspection to update the status of")
        if not inspection_id:
            conn.close()
            return

        cursor.execute('''
        SELECT status, findings, action_required, follow_up_date
        FROM housing_inspections WHERE inspection_id = ?
        ''', (inspection_id,))
        current = cursor.fetchone()
        if not current:
            print("Inspection not found.")
            conn.close()
            return

        print(f"\nCurrent status: {current[0]}")
        print("\nSelect Inspection Status:")
        for i, status in enumerate(ALL_STATUSES, 1):
            print(f"{i}. {status}")

        new_status = None
        while new_status is None:
            raw = input(f"\nSelect status (1-{len(ALL_STATUSES)}, or 'q' to cancel): ").strip()
            if raw.lower() in ('q', 'quit', 'cancel', 'back', 'exit'):
                print("Operation cancelled.")
                conn.close()
                return
            if not raw:
                print("This field cannot be left blank. Please try again.")
                continue
            try:
                choice = int(raw)
            except ValueError:
                print("Please enter a valid number.")
                continue
            if 1 <= choice <= len(ALL_STATUSES):
                new_status = ALL_STATUSES[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(ALL_STATUSES)}.")

        findings = input(f"Findings [{current[1] or 'none'}]: ").strip() or current[1]

        action_required = current[2]
        follow_up_date = current[3]
        follow_up_reason = None

        if new_status in ("Failed", "Needs Follow-up"):
            action_required = input(
                f"Action Required [{current[2] or 'none'}]: ").strip() or current[2]

        if new_status == "Needs Follow-up":
            # A follow-up without a date is the thing that leaves a resident
            # with no idea when someone is coming back, so insist on one.
            follow_up_date = _prompt_date("Follow-up Date (YYYY-MM-DD)", allow_blank=False)
            while True:
                follow_up_reason = input("Reason a follow-up is needed: ").strip()
                if follow_up_reason:
                    break
                print("This field cannot be left blank. Please try again.")
        elif new_status == "Passed":
            follow_up_date = None

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        UPDATE housing_inspections
        SET status = ?, findings = ?, action_required = ?, follow_up_date = ?, updated_at = ?
        WHERE inspection_id = ?
        ''', (new_status, findings, action_required, follow_up_date,
              timestamp, inspection_id))

        context = _inspection_email_context(cursor, inspection_id)
        conn.commit()
        print(f"\nInspection {inspection_id} is now '{new_status}'.")
        conn.close()

        if context:
            context['follow_up_reason'] = follow_up_reason
            if new_status == "Needs Follow-up":
                _notify_residents(context, _common.send_inspection_follow_up_email,
                                  "Follow-up notice")
            elif new_status == SCHEDULED_STATUS:
                _notify_residents(context, _common.send_inspection_scheduled_email,
                                  "Inspection notice")
            else:
                # Passed / Failed / Incomplete are all completed outcomes the
                # resident is entitled to see.
                _notify_residents(context, _common.send_inspection_completed_email,
                                  "Inspection results")

        # A failed inspection with an action is the usual trigger for a repair.
        if new_status in ("Failed", "Needs Follow-up") and action_required:
            if input("\nCreate a maintenance request for this? (y/n): ").strip().lower() == 'y':
                create_maintenance_request()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error updating inspection status: {e}")


@log_delete(module="housing", description="Deleting room inspection")
def delete_inspection():
    """Delete an inspection record."""
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to delete inspections.")
        return
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to delete inspections.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        inspection_id = _select_inspection(cursor, "Select inspection to delete")
        if not inspection_id:
            conn.close()
            return

        cursor.execute('''
        SELECT i.inspection_date, i.inspection_type, i.status, b.building_name, r.room_number
        FROM housing_inspections i
        JOIN housing_rooms r ON i.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE i.inspection_id = ?
        ''', (inspection_id,))
        detail = cursor.fetchone()
        if not detail:
            print("Inspection not found.")
            conn.close()
            return

        # Move-out inspections justify money taken off a deposit. Deleting one
        # out from under its deductions would leave those charges unevidenced,
        # so say so before anything is removed.
        cursor.execute('''
        SELECT COUNT(*) FROM housing_deposit_deductions WHERE inspection_id = ?
        ''', (inspection_id,))
        deduction_count = cursor.fetchone()[0]

        print(f"\nAbout to delete inspection {inspection_id}:")
        print(f"  {detail[3]} room {detail[4]} - {detail[0]} - {detail[1]} [{detail[2]}]")
        if deduction_count:
            print(f"\n  WARNING: {deduction_count} deposit deduction(s) cite this "
                  f"inspection as their evidence.")
            print("  Deleting it leaves those charges unevidenced. Resolve them in "
                  "Process Deposit Refund first if that is not what you want.")

        if input("\nDelete this inspection? (y/n): ").strip().lower() != 'y':
            print("Operation cancelled.")
            conn.close()
            return

        cursor.execute('DELETE FROM housing_inspections WHERE inspection_id = ?',
                       (inspection_id,))
        conn.commit()
        print(f"\nInspection {inspection_id} deleted.")
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error deleting inspection: {e}")
