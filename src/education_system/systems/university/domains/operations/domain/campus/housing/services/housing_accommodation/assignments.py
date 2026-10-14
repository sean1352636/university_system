import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection, generate_id,
    log_create, log_read, log_update,
)
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.applications import select_student


# Housing Assignment Functions
@log_read(module="housing", description="Viewing housing assignment")
def view_assignment():
    """View housing assignments"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.assignment.view")))
        return

    current_role = auth.current_user.get('role', '')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if current_role == 'student':
            # Students can only view their own assignments
            if not auth.check_permission('view_own_record'):
                print(get_text("housing.auth.permission_denied", action=get_text("housing.assignment.view")))
                conn.close()
                return

            # Get the student ID associated with this user
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))

            result = cursor.fetchone()
            if not result or not result[0]:
                print(get_text("housing.assignment.no_student_id"))
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
                print(get_text("housing.assignment.no_own_assignments"))
                conn.close()
                return

            print("\n" + get_text("housing.assignment.your_assignments_title") + ":")
            print("=" * 24)

            for i, asn in enumerate(assignments, 1):
                print(f"{i}. " + get_text("housing.assignment.room_in_building", room=asn[2], building=asn[3], type=asn[4]))
                print("   " + get_text("housing.assignment.move_dates", **{"in": asn[5], "out": asn[6]}))
                print("   " + get_text("housing.assignment.rent_status", rent=asn[7], status=asn[8]))
                print()

            # Select assignment to view details
            while True:
                try:
                    choice = int(input("\n" + get_text("housing.assignment.select_to_view") + ": "))
                    if 1 <= choice <= len(assignments):
                        assignment_id = assignments[choice - 1][0]
                        break
                    else:
                        print(get_text("housing.assignment.enter_range", max=len(assignments)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

        else:
            # Admin/staff can view any assignment
            if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
                print(get_text("housing.assignment.view_permission_denied"))
                conn.close()
                return

            # Allow filtering options
            print("\n" + get_text("housing.assignment.view_title") + ":")
            print("1. " + get_text("housing.assignment.view_all"))
            print("2. " + get_text("housing.assignment.view_by_status"))
            print("3. " + get_text("housing.assignment.view_by_student"))
            print("4. " + get_text("housing.assignment.view_by_building"))
            print("5. " + get_text("housing.assignment.view_by_room"))

            filter_choice = input("\n" + get_text("housing.assignment.enter_choice") + ": ")

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
                print("\n" + get_text("housing.assignment.select_status_title") + ":")
                print("1. " + get_text("housing.assignment.status_active"))
                print("2. " + get_text("housing.assignment.status_pending"))
                print("3. " + get_text("housing.assignment.status_terminated"))
                print("4. " + get_text("housing.assignment.status_expired"))

                status_choice = input("\n" + get_text("housing.assignment.enter_status_choice") + ": ")
                status_map = {
                    '1': 'Active',
                    '2': 'Pending',
                    '3': 'Terminated',
                    '4': 'Expired'
                }

                if status_choice not in status_map:
                    print(get_text("housing.common.invalid_choice", default="Invalid Choice."))
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
                    print(get_text("housing.building.no_buildings"))
                    conn.close()
                    return

                print("\n" + get_text("housing.assignment.select_building_title") + ":")
                for i, (bid, bname) in enumerate(buildings, 1):
                    print(f"{i}. {bname}")

                while True:
                    try:
                        choice = int(input("\n" + get_text("housing.building.select") + ": "))
                        if 1 <= choice <= len(buildings):
                            building_id = buildings[choice - 1][0]
                            break
                        else:
                            print(get_text("housing.assignment.enter_range", max=len(buildings)))
                    except ValueError:
                        print(get_text("housing.common.error_valid_number"))

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
                    print(get_text("housing.building.no_buildings"))
                    conn.close()
                    return

                print("\n" + get_text("housing.assignment.select_building_title") + ":")
                for i, (bid, bname) in enumerate(buildings, 1):
                    print(f"{i}. {bname}")

                while True:
                    try:
                        choice = int(input("\n" + get_text("housing.building.select") + ": "))
                        if 1 <= choice <= len(buildings):
                            building_id = buildings[choice - 1][0]
                            break
                        else:
                            print(get_text("housing.assignment.enter_range", max=len(buildings)))
                    except ValueError:
                        print(get_text("housing.common.error_valid_number"))

                cursor.execute('''
                SELECT room_id, room_number, floor_number
                FROM housing_rooms
                WHERE building_id = ?
                ORDER BY floor_number, room_number
                ''', (building_id,))

                rooms = cursor.fetchall()

                if not rooms:
                    print(get_text("housing.room.no_rooms"))
                    conn.close()
                    return

                print("\n" + get_text("housing.assignment.select_room_title") + ":")
                for i, room in enumerate(rooms, 1):
                    print(f"{i}. " + get_text("housing.room.room_label", number=room[1]) + f" ({get_text('housing.room.floor_label')}: {room[2]})")

                while True:
                    try:
                        choice = int(input("\n" + get_text("housing.room.select") + ": "))
                        if 1 <= choice <= len(rooms):
                            room_id = rooms[choice - 1][0]
                            break
                        else:
                            print(get_text("housing.assignment.enter_range", max=len(rooms)))
                    except ValueError:
                        print(get_text("housing.common.error_valid_number"))

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
                print(get_text("housing.common.invalid_choice", default="Invalid Choice."))
                conn.close()
                return

            assignments = cursor.fetchall()

            if not assignments:
                print(get_text("housing.assignment.no_matching"))
                conn.close()
                return

            print("\n" + get_text("housing.assignment.assignment_list_title") + ":")
            print("=" * 19)

            for i, asn in enumerate(assignments, 1):
                print(f"{i}. {asn[2]} {asn[3]} ({asn[1]}) | " + get_text("housing.room.room_label", number=asn[4]) + f" {get_text('housing.common.in', default='In')} {asn[5]}")
                print(f"   {get_text('housing.assignment.move_in_label')}: {asn[6]} | {get_text('housing.assignment.status_label')}: {asn[7]}")
                print()

            # Select assignment to view details
            while True:
                try:
                    choice = int(input("\n" + get_text("housing.assignment.select_to_view") + ": "))
                    if 1 <= choice <= len(assignments):
                        assignment_id = assignments[choice - 1][0]
                        break
                    else:
                        print(get_text("housing.assignment.enter_range", max=len(assignments)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

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
            print(get_text("housing.assignment.not_found"))
            conn.close()
            return

        print("\n" + get_text("housing.assignment.details_section_title") + ":")
        print("=" * 18)
        print(f"{get_text('housing.assignment.id_label')}: {assignment[0]}")
        if assignment[1]:
            print(f"{get_text('housing.assignment.application_label')}: {assignment[1]}")
        print(get_text("housing.assignment.student_info", first=assignment[3], last=assignment[4], id=assignment[2]))
        print(f"{get_text('housing.assignment.email_label')}: {assignment[5]}")
        print(f"{get_text('housing.room.title')}: " + get_text("housing.assignment.room_info", room=assignment[7], floor=assignment[8], building=assignment[10]))
        print(f"{get_text('housing.room.type_label')}: {assignment[9]}")
        print(f"{get_text('housing.assignment.building_address_label')}: {assignment[11]}")
        print(f"{get_text('housing.assignment.move_in_label')}: {assignment[12]}")
        print(f"{get_text('housing.assignment.move_out_label')}: {assignment[13]}")
        if assignment[14]:
            print(f"{get_text('housing.assignment.actual_move_out_label')}: {assignment[14]}")
        print(f"{get_text('housing.assignment.contract_label')}: {assignment[15]}")
        print(f"{get_text('housing.assignment.rent_label')}: £{assignment[16]}")
        print(f"{get_text('housing.assignment.status_label')}: {assignment[17]}")
        print(f"{get_text('housing.assignment.assigned_by_label')}: {assignment[18]}")
        print(f"{get_text('housing.assignment.date_label')}: {assignment[19]}")

        # Get payment information
        cursor.execute('''
        SELECT source_payment_id, amount, payment_date, payment_method, payment_period_start,
               payment_period_end, status, COALESCE(payment_type, 'Rent')
        FROM payments
        WHERE source_type = 'housing' AND reference_id = ?
        ORDER BY payment_date DESC
        ''', (assignment_id,))

        payments = cursor.fetchall()

        if payments:
            print("\n" + get_text("housing.assignment.payment_history_title") + ":")
            print("=" * 15)

            for i, payment in enumerate(payments, 1):
                print(f"{i}. [{payment[7]}] " + get_text("housing.assignment.payment_item", amount=payment[1], date=payment[2], method=payment[3]))
                if payment[4] and payment[5]:
                    print("   " + get_text("housing.assignment.payment_period", start=payment[4], end=payment[5], status=payment[6]))
                else:
                    print(f"   Status: {payment[6]}")
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
            print("\n" + get_text("housing.assignment.maintenance_title") + ":")
            print("=" * 33)

            for i, request in enumerate(maintenance_requests, 1):
                print(f"{i}. " + get_text("housing.assignment.maintenance_item", type=request[2], date=request[1], priority=request[3], status=request[4]))

        # If staff/admin and assignment is active, ask if they want to update status
        if (auth.check_permission('manage_accommodations') and assignment[17] == 'Active'):
            update_now = input("\n" + get_text("housing.assignment.update_status_prompt") + " " + get_text("common.yes_no_prompt") + ": ").lower()

            if update_now == get_text("common.yes"):
                conn.close()  # Close current connection before updating
                update_assignment_status(assignment_id)
                return

        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.assignment.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.assignment.error_viewing", error=str(e)))

@log_update(module="housing", description="Updating assignment status")
def update_assignment_status(assignment_id=None):
    """Update the status of a housing assignment"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.assignment.update_login_required"))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.assignment.update_permission_denied"))
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
                print(get_text("housing.assignment.no_active_assignments"))
                conn.close()
                return

            print("\n" + get_text("housing.assignment.select_update_title") + ":")
            print("=" * 27)

            for i, asn in enumerate(assignments, 1):
                print(f"{i}. " + get_text("housing.assignment.assignment_item", first=asn[2], last=asn[3], id=asn[1], room=asn[4], building=asn[5], status=asn[6]))

            while True:
                try:
                    choice = int(input("\n" + get_text("housing.assignment.select_assignment") + ": "))
                    if 1 <= choice <= len(assignments):
                        assignment_id = assignments[choice - 1][0]
                        break
                    else:
                        print(get_text("housing.assignment.enter_range", max=len(assignments)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

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
            print(get_text("housing.assignment.not_found"))
            conn.close()
            return

        print("\n" + get_text("housing.assignment.current_info_title") + ":")
        print(f"{get_text('housing.assignment.id_label')}: {assignment[0]}")
        print(get_text("housing.assignment.student_info", first=assignment[2], last=assignment[3], id=assignment[1]))
        print(f"{get_text('housing.room.title')}: {assignment[5]} {get_text('housing.common.in', default='In')} {assignment[6]}")
        print(f"{get_text('housing.assignment.current_status')}: {assignment[7]}")

        print("\n" + get_text("housing.assignment.update_to_title") + ":")
        print("1. " + get_text("housing.assignment.status_active"))
        print("2. " + get_text("housing.assignment.status_terminated"))
        print("3. " + get_text("housing.assignment.status_expired"))
        print("4. " + get_text("housing.assignment.cancel_update"))

        status_choice = input("\n" + get_text("housing.assignment.enter_update_choice") + ": ")

        if status_choice == '4':
            print(get_text("housing.assignment.update_cancelled"))
            conn.close()
            return

        status_map = {
            '1': 'Active',
            '2': 'Terminated',
            '3': 'Expired'
        }

        if status_choice not in status_map:
            print(get_text("housing.common.invalid_choice", default="Invalid Choice."))
            conn.close()
            return

        new_status = status_map[status_choice]

        # If terminating or expiring, need move-out date
        actual_move_out_date = None
        if new_status in ('Terminated', 'Expired'):
            while True:
                move_out_date = input(get_text("housing.assignment.enter_move_out_date") + ": ").strip()

                if not move_out_date:
                    actual_move_out_date = datetime.datetime.now().strftime('%Y-%m-%d')
                    break

                try:
                    # Validate date format
                    datetime.datetime.strptime(move_out_date, '%Y-%m-%d')
                    actual_move_out_date = move_out_date
                    break
                except ValueError:
                    print(get_text("housing.assignment.invalid_date_format"))

        # Confirm update
        confirm = input("\n" + get_text("housing.assignment.confirm_status_change", status=new_status) + " " + get_text("common.yes_no_prompt") + ": ").lower()

        if confirm != get_text("common.yes"):
            print(get_text("housing.assignment.update_cancelled"))
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

        if new_status in ('Terminated', 'Expired') and actual_move_out_date:
            try:
                from education_system.systems.university.services.bus.integration_bus import (
                    publish_housing_move_out,
                )
                publish_housing_move_out(
                    assignment_id=int(assignment_id),
                    student_id=str(assignment[1]),
                    room_id=str(assignment[4]),
                    actual_move_out_date=actual_move_out_date,
                    new_status=new_status,
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        print("\n" + get_text("housing.assignment.updated_success", status=new_status))
        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.assignment.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.assignment.error_updating", error=str(e)))


# ---------------------------------------------------------------------------
# Automatic relocation when a building or room is removed
# ---------------------------------------------------------------------------
# Deleting a building or a room used to be refused outright while anyone was
# living in it, which left the operator to move every resident by hand before
# they could delete anything. Instead we now find each resident a room in a
# *different* building, move their live assignment across, and email them the
# new building, room number and floor number through the university email
# system.
#
# Both the CLI (buildings.py) and the GUI (building_manager / room_manager)
# call these, so the rules — and the email the student receives — are the same
# either way.

# An assignment is "live" (and so needs relocating) in these states. Defined
# in common so the email helpers there can share it.
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.common import (  # noqa: E402
    LIVE_ASSIGNMENT_STATUSES,
)

# A room can take another resident in these states.
_VACANT_ROOM_STATUSES = ('Available', 'Reserved')


def _room_row(cursor, room_id):
    """Full room + building detail for one room, or None."""
    cursor.execute('''
    SELECT r.room_id, r.building_id, r.room_number, r.floor_number, r.room_type,
           r.max_occupants, r.current_occupants, r.is_accessible, r.status,
           r.monthly_rent, b.building_name, b.address, b.campus_location
    FROM housing_rooms r
    JOIN housing_buildings b ON r.building_id = b.building_id
    WHERE r.room_id = ?
    ''', (room_id,))
    return cursor.fetchone()


def find_vacant_rooms(cursor, exclude_building_ids=None, exclude_room_ids=None):
    """Rooms with spare capacity, outside the excluded buildings/rooms.

    Ordered so the best candidates come first: the caller pops from the
    front and re-checks capacity, because several residents may be placed
    in the same multi-occupancy room in one pass.
    """
    excluded_buildings = tuple(exclude_building_ids or ())
    excluded_rooms = tuple(exclude_room_ids or ())

    sql = '''
    SELECT r.room_id, r.building_id, r.room_number, r.floor_number, r.room_type,
           r.max_occupants, r.current_occupants, r.is_accessible, r.status,
           r.monthly_rent, b.building_name, b.address, b.campus_location
    FROM housing_rooms r
    JOIN housing_buildings b ON r.building_id = b.building_id
    WHERE r.current_occupants < r.max_occupants
      AND r.status IN ({vacant})
    '''.format(vacant=','.join('?' * len(_VACANT_ROOM_STATUSES)))
    params = list(_VACANT_ROOM_STATUSES)

    if excluded_buildings:
        sql += ' AND r.building_id NOT IN ({})'.format(','.join('?' * len(excluded_buildings)))
        params.extend(excluded_buildings)
    if excluded_rooms:
        sql += ' AND r.room_id NOT IN ({})'.format(','.join('?' * len(excluded_rooms)))
        params.extend(excluded_rooms)

    # Emptier rooms first so we spread residents out rather than filling one
    # room to capacity, then cheaper rooms so nobody is moved somewhere that
    # would have cost them more had the rent followed the room.
    sql += ' ORDER BY (r.max_occupants - r.current_occupants) DESC, r.monthly_rent ASC, r.building_id, r.floor_number, r.room_number'

    cursor.execute(sql, params)
    return [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()]


def _score_candidate(candidate, old_room):
    """Lower is better. Prefers a like-for-like room over any spare bed."""
    score = 0
    if candidate['room_type'] != old_room['room_type']:
        score += 2
    # Never move an accessible-room resident into a non-accessible room if a
    # accessible one is free; the reverse is harmless.
    if old_room['is_accessible'] and not candidate['is_accessible']:
        score += 8
    if candidate['floor_number'] != old_room['floor_number']:
        score += 1
    return score


def plan_relocations(cursor, room_ids, exclude_building_ids=None):
    """Work out where every resident of *room_ids* would go.

    Returns ``(moves, unplaced)``. Nothing is written — the caller decides
    whether to go ahead. ``unplaced`` being non-empty means there is not
    enough room left in the other buildings, and the caller should abandon
    the deletion rather than evict anyone.
    """
    room_ids = list(room_ids)
    if not room_ids:
        return [], []

    placeholders = ','.join('?' * len(room_ids))
    status_placeholders = ','.join('?' * len(LIVE_ASSIGNMENT_STATUSES))
    cursor.execute('''
    SELECT a.assignment_id, a.student_id, a.room_id, a.contract_number,
           a.monthly_rent, a.move_in_date, a.planned_move_out_date, a.status,
           s.first_name, s.last_name, s.email_address
    FROM housing_assignments a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.room_id IN ({rooms})
      AND a.status IN ({statuses})
    ORDER BY a.move_in_date
    '''.format(rooms=placeholders, statuses=status_placeholders),
        room_ids + list(LIVE_ASSIGNMENT_STATUSES))
    residents = cursor.fetchall()

    if not residents:
        return [], []

    candidates = find_vacant_rooms(
        cursor,
        exclude_building_ids=exclude_building_ids,
        exclude_room_ids=room_ids,
    )
    # Track capacity as we allocate so two residents are never handed the
    # last bed in the same room.
    remaining = {c['room_id']: c['max_occupants'] - c['current_occupants']
                 for c in candidates}
    by_id = {c['room_id']: c for c in candidates}

    moves = []
    unplaced = []

    for row in residents:
        (assignment_id, student_id, old_room_id, contract_number, monthly_rent,
         move_in_date, planned_move_out_date, assignment_status,
         first_name, last_name, email_address) = row

        old_room = _room_row(cursor, old_room_id)
        old = dict(zip([c[0] for c in cursor.description], old_room)) if old_room else {}

        available = [by_id[rid] for rid, left in remaining.items() if left > 0]
        if not available:
            unplaced.append({
                'assignment_id': assignment_id,
                'student_id': student_id,
                'student_name': f"{first_name or ''} {last_name or ''}".strip() or student_id,
                'old_building_name': old.get('building_name', ''),
                'old_room_number': old.get('room_number', ''),
            })
            continue

        best = min(available, key=lambda c: (_score_candidate(c, old or c), c['room_id']))
        remaining[best['room_id']] -= 1

        moves.append({
            'assignment_id': assignment_id,
            'student_id': student_id,
            'student_name': f"{first_name or ''} {last_name or ''}".strip() or student_id,
            'email_address': email_address,
            'assignment_status': assignment_status,
            'contract_number': contract_number,
            'monthly_rent': monthly_rent,
            'move_in_date': move_in_date,
            'planned_move_out_date': planned_move_out_date,
            'old_room_id': old_room_id,
            'old_building_id': old.get('building_id', ''),
            'old_building_name': old.get('building_name', ''),
            'old_room_number': old.get('room_number', ''),
            'old_floor_number': old.get('floor_number', ''),
            'new_room_id': best['room_id'],
            'new_building_id': best['building_id'],
            'new_building_name': best['building_name'],
            'new_building_address': best['address'],
            'new_campus_location': best['campus_location'],
            'new_room_number': best['room_number'],
            'new_floor_number': best['floor_number'],
            'new_room_type': best['room_type'],
        })

    return moves, unplaced


def apply_relocations(cursor, moves, reason, actor, timestamp=None):
    """Repoint each assignment in *moves* at its new room.

    Runs inside the caller's transaction so the moves and the deletion that
    prompted them commit or roll back together. The rent on the contract is
    deliberately left alone: the student did not choose to move, so they are
    not re-priced onto the new room's rate, and no finance charge is raised.
    """
    timestamp = timestamp or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for move in moves:
        cursor.execute('''
        UPDATE housing_assignments
        SET room_id = ?, updated_at = ?
        WHERE assignment_id = ?
        ''', (move['new_room_id'], timestamp, move['assignment_id']))

        # Vacate the old room. It is about to be deleted, but the counters
        # keep the building totals honest if the caller bails out.
        cursor.execute('''
        UPDATE housing_rooms
        SET current_occupants = MAX(current_occupants - 1, 0), updated_at = ?
        WHERE room_id = ?
        ''', (timestamp, move['old_room_id']))

        # Fill the new room, and mark it Occupied once it is at capacity so
        # it stops being offered to the next resident in this same pass.
        cursor.execute('''
        UPDATE housing_rooms
        SET current_occupants = current_occupants + 1,
            status = CASE WHEN current_occupants + 1 >= max_occupants
                          THEN 'Occupied' ELSE status END,
            updated_at = ?
        WHERE room_id = ?
        ''', (timestamp, move['new_room_id']))

        move['relocated_at'] = timestamp
        move['reason'] = reason
        move['relocated_by'] = actor

    # Rebuild available_rooms from the rooms themselves for every building
    # touched, rather than nudging it by hand in two directions at once.
    touched = {m['old_building_id'] for m in moves} | {m['new_building_id'] for m in moves}
    for building_id in touched:
        if not building_id:
            continue
        cursor.execute('''
        UPDATE housing_buildings
        SET available_rooms = (
                SELECT COUNT(*) FROM housing_rooms
                WHERE building_id = ? AND status = 'Available'
            ),
            updated_at = ?
        WHERE building_id = ?
        ''', (building_id, timestamp, building_id))

    return moves


def notify_relocated_residents(moves):
    """Email every relocated student. Returns ``(sent, failed)`` counts."""
    sent = 0
    failed = 0
    for move in moves:
        if _common.send_relocation_email(move):
            move['email_sent'] = True
            sent += 1
        else:
            move['email_sent'] = False
            failed += 1
    return sent, failed


def relocate_residents(conn, room_ids, reason, actor, exclude_building_ids=None):
    """Plan, apply and notify in one call.

    Returns ``(moves, unplaced)``. When *unplaced* is non-empty nothing has
    been written and no email has been sent — the caller must abandon the
    deletion. The caller owns the transaction and must commit.
    """
    cursor = conn.cursor()
    moves, unplaced = plan_relocations(cursor, room_ids,
                                       exclude_building_ids=exclude_building_ids)
    if unplaced:
        return moves, unplaced
    if moves:
        apply_relocations(cursor, moves, reason, actor)
    return moves, unplaced


def describe_move(move):
    """One-line summary of a move, for CLI output and GUI summaries."""
    return (f"{move['student_name']} ({move['student_id']}): "
            f"{move['old_building_name']} room {move['old_room_number']} "
            f"-> {move['new_building_name']} room {move['new_room_number']} "
            f"(floor {move['new_floor_number']}, {move['new_room_type']})")


# ---------------------------------------------------------------------------
# Creating an assignment directly
# ---------------------------------------------------------------------------
# Until now a room could only be assigned as a side effect of approving an
# application, so housing staff had no way to place a student who walked in,
# transferred, or whose application predated the system. This is that missing
# path — and once the assignment exists, everyone sharing the room is told who
# they are now living with.

def notify_room_of_assignment(cursor, assignment):
    """Email the new resident and their room-mates about an assignment.

    Reads the room's roster *after* the assignment is written, so the new
    student is included and the occupant list each person receives is the
    real one. Returns ``(sent, failed)``.
    """
    occupants = _common.room_occupants(cursor, assignment['room_id'])
    if not occupants:
        return 0, 0
    return _common.send_assignment_created_emails(assignment, occupants)


@log_create(module="housing", description="Creating housing assignment")
def create_assignment():
    """Assign a student to a room without going through an application."""
    auth = _common.auth

    if not auth or not auth.current_user:
        print(_common.housing_text(
            "housing.auth.login_required_assign",
            default="You must be logged in to create an assignment."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(_common.housing_text(
            "housing.auth.permission_denied_assign",
            default="You don't have permission to create assignments."))
        return

    from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.applications import (
        prompt_choice, prompt_required, _validate_date, _validate_positive_int,
    )

    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = select_student()
        if not student_id:
            return

        # Refuse to double-book a student who already lives somewhere.
        placeholders = ','.join('?' * len(LIVE_ASSIGNMENT_STATUSES))
        cursor.execute('''
        SELECT a.assignment_id, r.room_number, b.building_name, a.status
        FROM housing_assignments a
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.student_id = ? AND a.status IN ({statuses})
        '''.format(statuses=placeholders), [student_id] + list(LIVE_ASSIGNMENT_STATUSES))
        existing = cursor.fetchone()
        if existing:
            print("\n" + _common.housing_text(
                "housing.assignment.already_housed",
                default=("{student} already has a {status} assignment "
                         "({id}) in {building} room {room}."),
                student=student_id, status=existing[3], id=existing[0],
                building=existing[2], room=existing[1]))
            print(_common.housing_text(
                "housing.assignment.end_existing_first",
                default="End that assignment first (Update Assignment Status), then assign the new room."))
            conn.close()
            return

        # Only offer rooms that can actually take another person.
        cursor.execute('''
        SELECT r.room_id, b.building_name, r.room_number, r.floor_number, r.room_type,
               r.max_occupants, r.current_occupants, r.monthly_rent, r.is_accessible
        FROM housing_rooms r
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE r.current_occupants < r.max_occupants
          AND r.status IN ('Available', 'Reserved')
        ORDER BY b.building_name, r.floor_number, r.room_number
        ''')
        rooms = cursor.fetchall()

        if not rooms:
            print(_common.housing_text(
                "housing.assignment.no_rooms_with_space",
                default="There are no rooms with space available."))
            conn.close()
            return

        labels = [
            f"{room[1]} room {room[2]} (floor {room[3]}, {room[4]}) - "
            f"{room[6]}/{room[5]} occupied, £{room[7]:.2f}/month"
            + (" - accessible" if room[8] else "")
            for room in rooms
        ]
        index = prompt_choice(_common.housing_text(
            "housing.assignment.select_room_to_assign",
            default="Select a room to assign"), labels)
        if index is None:
            print(_common.housing_text("housing.common.operation_cancelled",
                                       default="Operation cancelled."))
            conn.close()
            return

        room = rooms[index]
        room_id, building_name, room_number = room[0], room[1], room[2]
        floor_number, room_type, monthly_rent = room[3], room[4], room[7]

        move_in_date = prompt_required(_common.housing_text(
            "housing.assignment.move_in_prompt",
            default="Move-in date (YYYY-MM-DD)"), _validate_date)
        if move_in_date is None:
            print(_common.housing_text("housing.common.operation_cancelled",
                                       default="Operation cancelled."))
            conn.close()
            return

        duration = prompt_required(_common.housing_text(
            "housing.assignment.duration_prompt",
            default="Contract length in months"), _validate_positive_int)
        if duration is None:
            print(_common.housing_text("housing.common.operation_cancelled",
                                       default="Operation cancelled."))
            conn.close()
            return

        move_out_date = (datetime.datetime.strptime(move_in_date, '%Y-%m-%d')
                         + datetime.timedelta(days=30 * duration)).strftime('%Y-%m-%d')

        rent_input = input(_common.housing_text(
            "housing.assignment.rent_prompt",
            default="Monthly rent [£{rent}] (blank to use the room rate): £",
            rent=f"{monthly_rent:.2f}")).strip()
        if rent_input:
            try:
                monthly_rent = float(rent_input)
            except ValueError:
                print(_common.housing_text(
                    "housing.assignment.rent_fallback",
                    default="Not a valid amount - using the room rate of £{rent}.",
                    rent=f"{monthly_rent:.2f}"))

        # Cross-domain: the same finance-hold gate the application approval
        # path applies, so a walk-in cannot bypass an arrears block.
        try:
            from education_system.systems.university.services.bus import housing_finance
            allowed, reason = housing_finance.can_assign_room(student_id)
            if not allowed:
                print("\n" + _common.housing_text(
                    "housing.assignment.finance_hold_blocks",
                    default=("Cannot assign a room to {student}: {reason}. "
                             "Clear the hold in Finance first."),
                    student=student_id, reason=reason))
                conn.close()
                return
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        assignment_id = generate_id('ASG')
        contract_number = generate_id('CNT')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        actor = auth.current_user.get('username', 'housing')

        print("\n" + _common.housing_text(
            "housing.assignment.confirm_title", default="Confirm this assignment:"))
        print(f"  Student:   {student_id}")
        print(f"  Room:      {building_name} room {room_number} "
              f"(floor {floor_number}, {room_type})")
        print(f"  Move in:   {move_in_date}")
        print(f"  Move out:  {move_out_date} ({duration} months)")
        print(f"  Rent:      £{monthly_rent:.2f}/month")

        if input("\n" + _common.housing_text(
                "housing.assignment.confirm_prompt",
                default="Create this assignment?") + " (y/n): ").strip().lower() != 'y':
            print(_common.housing_text("housing.common.operation_cancelled",
                                       default="Operation cancelled."))
            conn.close()
            return

        cursor.execute('''
        INSERT INTO housing_assignments (
            assignment_id, application_id, student_id, room_id, move_in_date,
            planned_move_out_date, contract_number, monthly_rent, status,
            assigned_by, created_at, updated_at
        ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, 'Active', ?, ?, ?)
        ''', (assignment_id, student_id, room_id, move_in_date, move_out_date,
              contract_number, monthly_rent, actor, timestamp, timestamp))

        cursor.execute('''
        UPDATE housing_rooms
        SET current_occupants = current_occupants + 1,
            status = CASE WHEN current_occupants + 1 >= max_occupants
                          THEN 'Occupied' ELSE 'Reserved' END,
            updated_at = ?
        WHERE room_id = ?
        ''', (timestamp, room_id))

        cursor.execute('''
        UPDATE housing_buildings
        SET available_rooms = (
                SELECT COUNT(*) FROM housing_rooms
                WHERE building_id = housing_buildings.building_id AND status = 'Available'
            ),
            updated_at = ?
        WHERE building_id = (SELECT building_id FROM housing_rooms WHERE room_id = ?)
        ''', (timestamp, room_id))

        # Gather everything the emails need while the connection is open.
        cursor.execute('''
        SELECT b.building_name, r.room_number, r.floor_number, r.room_type,
               b.address, b.campus_location, r.current_occupants, r.max_occupants
        FROM housing_rooms r
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE r.room_id = ?
        ''', (room_id,))
        detail = cursor.fetchone()

        cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?',
                       (student_id,))
        name_row = cursor.fetchone()

        assignment = {
            'assignment_id': assignment_id,
            'contract_number': contract_number,
            'student_id': student_id,
            'student_name': (f"{name_row[0] or ''} {name_row[1] or ''}".strip()
                             if name_row else student_id),
            'room_id': room_id,
            'building_name': detail[0], 'room_number': detail[1],
            'floor_number': detail[2], 'room_type': detail[3],
            'building_address': detail[4], 'campus_location': detail[5],
            'current_occupants': detail[6], 'max_occupants': detail[7],
            'monthly_rent': monthly_rent,
            'move_in_date': move_in_date,
            'planned_move_out_date': move_out_date,
            'assigned_by': actor,
            'assigned_date': timestamp,
        }
        occupants = _common.room_occupants(cursor, room_id)

        conn.commit()
        # The locale's create_success carries a {contract} placeholder, so
        # supply it alongside our own — housing_text falls back to the
        # unformatted string if any placeholder is missing, which would print
        # a literal "{contract}" to the operator.
        print("\n" + _common.housing_text(
            "housing.assignment.create_success",
            default="Assignment {id} created: {student} is in {building} room {room}.",
            id=assignment_id, student=student_id, contract=contract_number,
            building=building_name, room=room_number))
        print(f"  {student_id} -> {building_name} room {room_number} "
              f"(floor {floor_number}, {room_type}), contract {contract_number}")
        conn.close()

        # Notify the whole room after the commit, so nobody is told about an
        # assignment that rolled back.
        sent, failed = _common.send_assignment_created_emails(assignment, occupants)
        print(_common.housing_text(
            "housing.assignment.emails_sent",
            default="Notified the room: {sent} email(s) sent, {failed} failed.",
            sent=sent, failed=failed))

    except sqlite3.Error as e:
        print(get_text("housing.assignment.database_error", error=str(e)))
    except Exception as e:
        print(_common.housing_text("housing.assignment.error_creating",
                                   default="Error creating assignment: {error}",
                                   error=str(e)))
