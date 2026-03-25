from education_system.university_system.modules.domain.housing.services.housing_accommodation import common as _common
from education_system.university_system.modules.domain.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection,
    log_read, log_update,
)
from education_system.university_system.modules.domain.housing.services.housing_accommodation.applications import select_student


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
                    print(get_text("housing.common.invalid_choice"))
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
                print(get_text("housing.common.invalid_choice"))
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
                print(f"{i}. {asn[2]} {asn[3]} ({asn[1]}) | " + get_text("housing.room.room_label", number=asn[4]) + f" {get_text('housing.common.in')} {asn[5]}")
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
        print(f"{get_text('housing.assignment.rent_label')}: ${assignment[16]}")
        print(f"{get_text('housing.assignment.status_label')}: {assignment[17]}")
        print(f"{get_text('housing.assignment.assigned_by_label')}: {assignment[18]}")
        print(f"{get_text('housing.assignment.date_label')}: {assignment[19]}")

        # Get payment information
        cursor.execute('''
        SELECT source_payment_id, amount, payment_date, payment_method, payment_period_start,
               payment_period_end, status
        FROM payments
        WHERE source_type = 'housing' AND reference_id = ?
        ORDER BY payment_date DESC
        ''', (assignment_id,))

        payments = cursor.fetchall()

        if payments:
            print("\n" + get_text("housing.assignment.payment_history_title") + ":")
            print("=" * 15)

            for i, payment in enumerate(payments, 1):
                print(f"{i}. " + get_text("housing.assignment.payment_item", amount=payment[1], date=payment[2], method=payment[3]))
                print("   " + get_text("housing.assignment.payment_period", start=payment[4], end=payment[5], status=payment[6]))
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
        print(f"{get_text('housing.room.title')}: {assignment[5]} {get_text('housing.common.in')} {assignment[6]}")
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
            print(get_text("housing.common.invalid_choice"))
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
        print("\n" + get_text("housing.assignment.updated_success", status=new_status))
        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.assignment.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.assignment.error_updating", error=str(e)))
