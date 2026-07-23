from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection, generate_id,
    log_create, log_read, log_update,
)


# Housing Application Functions
@log_create(module="housing", description="Creating housing application")
def create_application():
    """Create a new housing application"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.application.create")))
        return

    current_role = auth.current_user.get('role', '')

    # Different permissions based on role
    if current_role == 'student':
        # Students can only apply for themselves
        if not auth.check_permission('view_own_record'):
            print(get_text("housing.auth.permission_denied", action=get_text("housing.application.create")))
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
                print(get_text("housing.application.no_student_id"))
                conn.close()
                return

            student_id = result[0]
            conn.close()

        except sqlite3.Error as e:
            print(get_text("housing.common.database_error", error=str(e)))
            return

    else:
        # Staff/admin can create applications for any student
        if not auth.check_permission('manage_accommodations'):
            print(get_text("housing.auth.permission_denied", action=get_text("housing.application.create")))
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
            print("\n" + get_text("housing.application.already_active", id=existing_application[0]))
            print(get_text("housing.application.update_or_cancel"))
            conn.close()
            return

        # Check if student already has active housing
        cursor.execute('''
        SELECT assignment_id FROM housing_assignments
        WHERE student_id = ? AND status = 'Active'
        ''', (student_id,))

        existing_assignment = cursor.fetchone()

        if existing_assignment:
            print("\n" + get_text("housing.application.has_active_housing", id=existing_assignment[0]))
            proceed = input(get_text("housing.application.proceed_anyway") + " (y/n): ").lower()
            if proceed != 'y':
                conn.close()
                return

        print("\n" + get_text("housing.application.new_title"))
        print("=" * 22)

        # Fetch available buildings
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()

        if not buildings:
            print(get_text("housing.building.no_buildings_create_first"))
            conn.close()
            return

        print("\n" + get_text("housing.application.select_preferred_building") + ":")
        print("=" * 25)
        print("0. " + get_text("housing.application.no_preference"))

        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")

        while True:
            try:
                choice = int(input("\n" + get_text("housing.common.select_prompt") + " "))
                if choice == 0:
                    preferred_building_id = None
                    break
                elif 1 <= choice <= len(buildings):
                    preferred_building_id = buildings[choice - 1][0]
                    break
                else:
                    print(get_text("housing.common.error_range", min=0, max=len(buildings)))
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        print("\n" + get_text("housing.application.select_room_type") + ":")
        print("=" * 16)
        room_types = ["Single", "Double", "Triple", "Suite", "Studio", "Apartment"]

        for i, room_type in enumerate(room_types, 1):
            print(f"{i}. {get_text('housing.room.type_' + room_type.lower())}")

        while True:
            try:
                choice = int(input("\n" + get_text("housing.common.select_prompt") + " "))
                if 1 <= choice <= len(room_types):
                    preferred_room_type = room_types[choice - 1]
                    break
                else:
                    print(get_text("housing.common.error_range", min=1, max=len(room_types)))
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        # Get preferred move-in date
        while True:
            move_in_date = input(get_text("housing.application.move_in_date_prompt") + ": ")
            try:
                # Validate date format
                datetime.datetime.strptime(move_in_date, '%Y-%m-%d')
                break
            except ValueError:
                print(get_text("housing.application.invalid_date_format"))

        # Get duration
        while True:
            try:
                duration = int(input(get_text("housing.application.duration_prompt") + ": "))
                if duration <= 0:
                    print(get_text("housing.application.error_duration_positive"))
                    continue
                break
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        # Get special requirements
        special_requirements = input(get_text("housing.application.special_requirements_prompt") + ": ").strip() or None

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
        print("\n" + get_text("housing.application.create_success", id=application_id))

        # If staff/admin is creating, ask if they want to approve immediately
        if auth.check_permission('approve_accommodations'):
            approve_now = input("\n" + get_text("housing.application.approve_now_prompt") + " (y/n): ").lower() == 'y'

            if approve_now:
                process_application(application_id)

        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.application.error_creating", error=str(e)))

def select_student():
    """Helper function to select a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Ask for student ID or search criteria
        search_type = input("\n" + get_text("housing.student.search_by") + ":\n1. " + get_text("housing.student.student_id") + "\n2. " + get_text("housing.student.name") + "\n" + get_text("housing.student.enter_choice") + ": ")

        if search_type == '1':
            # Search by student ID
            student_id = input(get_text("housing.student.enter_id") + ": ")

            cursor.execute('''
            SELECT student_id, first_name, last_name, email_address
            FROM students
            WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()

            if not student:
                print(get_text("housing.student.not_found"))
                conn.close()
                return None

            print(f"\n{get_text('housing.student.found')}: {student[1]} {student[2]} ({student[0]}) - {student[3]}")
            confirm = input(get_text("housing.student.confirm_correct") + " (y/n): ").lower()

            if confirm != 'y':
                conn.close()
                return None

            return student[0]

        elif search_type == '2':
            # Search by name
            name = input(get_text("housing.student.enter_name") + ": ")

            cursor.execute('''
            SELECT student_id, first_name, last_name, email_address
            FROM students
            WHERE first_name LIKE ? OR last_name LIKE ?
            ORDER BY last_name, first_name
            ''', (f'%{name}%', f'%{name}%'))

            students = cursor.fetchall()

            if not students:
                print(get_text("housing.student.no_students_found"))
                conn.close()
                return None

            print("\n" + get_text("housing.student.found") + ":")
            for i, student in enumerate(students, 1):
                print(f"{i}. {student[1]} {student[2]} ({student[0]}) - {student[3]}")

            while True:
                try:
                    choice = int(input("\n" + get_text("housing.student.select_prompt") + ": "))
                    if 1 <= choice <= len(students):
                        return students[choice - 1][0]
                    else:
                        print(get_text("housing.common.error_range", min=1, max=len(students)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))
        else:
            print(get_text("housing.student.invalid_option"))
            conn.close()
            return None

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
        return None
    except Exception as e:
        print(get_text("housing.student.error_selecting", error=str(e)))
        return None
    finally:
        if 'conn' in locals():
            conn.close()

@log_update(module="housing", description="Processing housing application")
def process_application(application_id=None):
    """Process a housing application (approve/reject)"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.application.process")))
        return

    if not auth.check_permission('approve_accommodations'):
        print(get_text("housing.auth.permission_denied", action=get_text("housing.application.process")))
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
                print(get_text("housing.application.no_pending"))
                conn.close()
                return

            print("\n" + get_text("housing.application.pending_title") + ":")
            print("=" * 19)

            for i, app in enumerate(applications, 1):
                print(f"{i}. {app[2]} {app[3]} ({app[1]}) - {get_text('housing.application.applied_on')} {app[4]}")

            while True:
                try:
                    choice = int(input("\n" + get_text("housing.application.select_to_process") + ": "))
                    if 1 <= choice <= len(applications):
                        application_id = applications[choice - 1][0]
                        break
                    else:
                        print(get_text("housing.common.error_range", min=1, max=len(applications)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

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
            print(get_text("housing.application.not_found"))
            conn.close()
            return

        print("\n" + get_text("housing.application.details_title") + ":")
        print("=" * 19)
        print(f"{get_text('housing.application.id_label')}: {application[0]}")
        print(f"{get_text('housing.application.student_label')}: {application[2]} {application[3]} ({application[1]})")
        print(f"{get_text('housing.application.date_label')}: {application[4]}")
        print(f"{get_text('housing.application.building_label')}: {application[6] or get_text('housing.application.no_preference')}")
        print(f"{get_text('housing.application.room_type_label')}: {application[7]}")
        print(f"{get_text('housing.application.move_in_label')}: {application[8]}")
        print(f"{get_text('housing.application.duration_label')}: {application[9]} {get_text('housing.application.months')}")
        print(f"{get_text('housing.application.requirements_label')}: {application[10] or get_text('housing.common.none')}")

        # Ask for decision
        print("\n" + get_text("housing.application.process_title") + ":")
        print("1. " + get_text("housing.application.approve_action"))
        print("2. " + get_text("housing.application.reject_action"))
        print("3. " + get_text("housing.application.waitlist_action"))
        print("4. " + get_text("housing.application.request_info_action"))
        print("5. " + get_text("housing.common.cancel"))

        decision = input("\n" + get_text("housing.application.enter_decision") + ": ")

        if decision == '5':
            print(get_text("housing.common.operation_cancelled"))
            conn.close()
            return

        notes = input(get_text("housing.application.notes_prompt") + ": ").strip() or None
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
                print("\n" + get_text("housing.application.no_suitable_rooms"))
                print(get_text("housing.application.would_you_like") + ":")
                print("1. " + get_text("housing.application.select_different_type"))
                print("2. " + get_text("housing.application.put_on_waitlist"))
                print("3. " + get_text("housing.application.cancel_processing"))

                alt_choice = input("\n" + get_text("housing.application.enter_choice") + ": ")

                if alt_choice == '1':
                    cursor.execute('''
                    SELECT DISTINCT room_type
                    FROM housing_rooms
                    WHERE status = 'Available'
                    ORDER BY room_type
                    ''')

                    available_types = cursor.fetchall()

                    if not available_types:
                        print(get_text("housing.application.no_rooms_waitlist"))
                        cursor.execute('''
                        UPDATE housing_applications
                        SET status = 'Waiting List', notes = ?, reviewed_by = ?, review_date = ?, updated_at = ?
                        WHERE application_id = ?
                        ''', (notes, auth.current_user['username'], timestamp, timestamp, application_id))

                        conn.commit()
                        print(get_text("housing.application.waitlisted_success"))
                        conn.close()
                        return

                    print("\n" + get_text("housing.application.available_room_types") + ":")
                    for i, room_type in enumerate(available_types, 1):
                        print(f"{i}. {room_type[0]}")

                    while True:
                        try:
                            type_choice = int(input("\n" + get_text("housing.common.select_prompt") + " "))
                            if 1 <= type_choice <= len(available_types):
                                alt_room_type = available_types[type_choice - 1][0]
                                break
                            else:
                                print(get_text("housing.common.error_range", min=1, max=len(available_types)))
                        except ValueError:
                            print(get_text("housing.common.error_valid_number"))

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
                        print(get_text("housing.application.no_suitable_waitlist"))
                        cursor.execute('''
                        UPDATE housing_applications
                        SET status = 'Waiting List', notes = ?, reviewed_by = ?, review_date = ?, updated_at = ?
                        WHERE application_id = ?
                        ''', (notes, auth.current_user['username'], timestamp, timestamp, application_id))

                        conn.commit()
                        print(get_text("housing.application.waitlisted_success"))
                        conn.close()
                        return

                elif alt_choice == '2':
                    cursor.execute('''
                    UPDATE housing_applications
                    SET status = 'Waiting List', notes = ?, reviewed_by = ?, review_date = ?, updated_at = ?
                    WHERE application_id = ?
                    ''', (notes, auth.current_user['username'], timestamp, timestamp, application_id))

                    conn.commit()
                    print(get_text("housing.application.waitlisted_success"))
                    conn.close()
                    return

                else:
                    print(get_text("housing.common.operation_cancelled"))
                    conn.close()
                    return

            # Display available rooms
            print("\n" + get_text("housing.room.available_rooms") + ":")
            print("=" * 15)

            for i, room in enumerate(available_rooms, 1):
                building_id = room[1]
                cursor.execute('SELECT building_name FROM housing_buildings WHERE building_id = ?', (building_id,))
                building_name = cursor.fetchone()[0]

                print(f"{i}. {get_text('housing.building.name_label')}: {building_name}, {get_text('housing.room.number_label')}: {room[2]}, {get_text('housing.room.floor_label')}: {room[3]}, {get_text('housing.room.type_label')}: {room[4]}, {get_text('housing.room.rent_label')}: £{room[5]}/{get_text('housing.common.month')}")

            while True:
                try:
                    room_choice = int(input("\n" + get_text("housing.room.select_to_assign") + ": "))
                    if 1 <= room_choice <= len(available_rooms):
                        selected_room = available_rooms[room_choice - 1]
                        break
                    else:
                        print(get_text("housing.common.error_range", min=1, max=len(available_rooms)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

            # Create housing assignment
            room_id = selected_room[0]
            monthly_rent = selected_room[5]
            move_in_date = application[8]
            duration_months = application[9]
            move_out_date = (datetime.datetime.strptime(move_in_date, '%Y-%m-%d') +
                            datetime.timedelta(days=30 * duration_months)).strftime('%Y-%m-%d')

            # Cross-domain: refuse to assign a room to a student who
            # has any active finance hold (rent arrears from a previous
            # tenancy, unpaid SU fees, etc.). Operator can override by
            # clearing the hold in the Finance GUI first.
            try:
                from education_system.post_18.university_system.modules.services import (
                    housing_finance,
                )
                allowed, reason = housing_finance.can_assign_room(
                    application[1]
                )
                if not allowed:
                    print(
                        f"\nCannot assign room to {application[1]}: {reason}.\n"
                        "Clear the hold in Finance first, then re-process "
                        "this application."
                    )
                    conn.close()
                    return
            except Exception:
                pass

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

            # Cross-domain: post the first month's rent through finance_bus
            # so the Finance GUI's account view, holds and bus events all
            # reflect the new tenancy.
            try:
                from education_system.post_18.university_system.modules.services import (
                    housing_finance,
                )
                housing_finance.post_rent_charge(
                    application[1], assignment_id, monthly_rent,
                    period_start=move_in_date,
                    period_end=(datetime.datetime.strptime(move_in_date,
                                                            '%Y-%m-%d')
                                + datetime.timedelta(days=30)
                                ).strftime('%Y-%m-%d'),
                    processed_by=auth.current_user.get('username')
                                 if auth and auth.current_user else None,
                )
            except Exception as _hf_exc:
                pass

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
        print("\n" + get_text("housing.application.status_updated", status=status.lower()))

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

            print("\n" + get_text("housing.assignment.details_title") + ":")
            print("=" * 17)
            print(f"{get_text('housing.assignment.id_label')}: {assignment[0]}")
            print(f"{get_text('housing.assignment.contract_label')}: {assignment[1]}")
            print(f"{get_text('housing.room.number_label')}: {assignment[2]} {get_text('housing.common.in')} {assignment[3]}")
            print(f"{get_text('housing.assignment.move_in_label')}: {assignment[4]}")
            print(f"{get_text('housing.assignment.move_out_label')}: {assignment[5]}")
            print(f"{get_text('housing.assignment.rent_label')}: £{assignment[6]}")

        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.application.error_processing", error=str(e)))

@log_read(module="housing", description="Viewing housing application")
def view_application():
    """View housing applications"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.application.view")))
        return

    current_role = auth.current_user.get('role', '')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if current_role == 'student':
            # Students can only view their own applications
            if not auth.check_permission('view_own_record'):
                print(get_text("housing.auth.permission_denied", action=get_text("housing.application.view")))
                conn.close()
                return

            # Get the student ID associated with this user
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))

            result = cursor.fetchone()
            if not result or not result[0]:
                print(get_text("housing.application.no_student_id"))
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
                print(get_text("housing.application.no_own_applications"))
                conn.close()
                return

            print("\n" + get_text("housing.application.your_applications") + ":")
            print("=" * 25)

            for i, app in enumerate(applications, 1):
                print(f"{i}. {get_text('housing.application.id_label')}: {app[0]}")
                print(f"   {get_text('housing.application.applied_on')}: {app[1]}")
                print(f"   {get_text('housing.application.room_type_label')}: {app[2]}")
                print(f"   {get_text('housing.application.move_in_label')}: {app[3]}")
                print(f"   {get_text('housing.application.duration_label')}: {app[4]} {get_text('housing.application.months')}")
                print(f"   {get_text('housing.application.status_label')}: {app[5]}")
                if app[6]:
                    print(f"   {get_text('housing.application.reviewed_on')}: {app[6]}")
                print()

            # Select application to view details
            while True:
                try:
                    choice = int(input("\n" + get_text("housing.application.select_to_view") + ": "))
                    if 1 <= choice <= len(applications):
                        application_id = applications[choice - 1][0]
                        break
                    else:
                        print(get_text("housing.common.error_range", min=1, max=len(applications)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

        else:
            # Admin/staff can view any application
            if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
                print(get_text("housing.auth.permission_denied", action=get_text("housing.application.view")))
                conn.close()
                return

            # Allow filtering options
            print("\n" + get_text("housing.application.view_title") + ":")
            print("1. " + get_text("housing.application.view_all"))
            print("2. " + get_text("housing.application.view_by_status"))
            print("3. " + get_text("housing.application.view_by_student"))

            filter_choice = input("\n" + get_text("housing.application.enter_choice") + ": ")

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
                print("\n" + get_text("housing.application.select_status") + ":")
                print("1. " + get_text("housing.application.status_pending"))
                print("2. " + get_text("housing.application.status_approved"))
                print("3. " + get_text("housing.application.status_rejected"))
                print("4. " + get_text("housing.application.status_waitlisted"))
                print("5. " + get_text("housing.application.status_more_info"))

                status_choice = input("\n" + get_text("housing.application.enter_choice") + ": ")
                status_map = {
                    '1': 'Pending',
                    '2': 'Approved',
                    '3': 'Rejected',
                    '4': 'Waiting List',
                    '5': 'More Info Needed'
                }

                if status_choice not in status_map:
                    print(get_text("housing.common.invalid_choice"))
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
                print(get_text("housing.common.invalid_choice"))
                conn.close()
                return

            applications = cursor.fetchall()

            if not applications:
                print(get_text("housing.application.no_matching"))
                conn.close()
                return

            print("\n" + get_text("housing.application.title") + ":")
            print("=" * 20)

            for i, app in enumerate(applications, 1):
                print(f"{i}. {get_text('housing.application.id_label')}: {app[0]} | {get_text('housing.application.student_label')}: {app[2]} {app[3]} ({app[1]})")
                print(f"   {get_text('housing.application.applied_on')}: {app[4]} | {get_text('housing.application.status_label')}: {app[5]}")
                if app[6]:
                    print(f"   {get_text('housing.application.reviewed_on')}: {app[6]}")
                print()

            # Select application to view details
            while True:
                try:
                    choice = int(input("\n" + get_text("housing.application.select_to_view") + ": "))
                    if 1 <= choice <= len(applications):
                        application_id = applications[choice - 1][0]
                        break
                    else:
                        print(get_text("housing.common.error_range", min=1, max=len(applications)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

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
            print(get_text("housing.application.not_found"))
            conn.close()
            return

        print("\n" + get_text("housing.application.details_title") + ":")
        print("=" * 19)
        print(f"{get_text('housing.application.id_label')}: {application[0]}")
        print(f"{get_text('housing.application.student_label')}: {application[2]} {application[3]} ({application[1]})")
        print(f"{get_text('housing.student.email')}: {application[4]}")
        print(f"{get_text('housing.application.date_label')}: {application[5]}")
        print(f"{get_text('housing.application.building_label')}: {application[7] or get_text('housing.application.no_preference')}")
        print(f"{get_text('housing.application.room_type_label')}: {application[8]}")
        print(f"{get_text('housing.application.move_in_label')}: {application[9]}")
        print(f"{get_text('housing.application.duration_label')}: {application[10]} {get_text('housing.application.months')}")
        print(f"{get_text('housing.application.requirements_label')}: {application[11] or get_text('housing.common.none')}")
        print(f"{get_text('housing.application.status_label')}: {application[12]}")
        if application[13]:
            print(f"{get_text('housing.application.notes_label')}: {application[13]}")
        if application[14]:
            print(f"{get_text('housing.application.reviewed_by_label')}: {application[14]}")
        if application[15]:
            print(f"{get_text('housing.application.review_date_label')}: {application[15]}")

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
            print("\n" + get_text("housing.assignment.associated_title") + ":")
            print("=" * 28)
            print(f"{get_text('housing.assignment.id_label')}: {assignment[0]}")
            print(f"{get_text('housing.assignment.contract_label')}: {assignment[9]}")
            print(f"{get_text('housing.room.number_label')}: {assignment[2]} {get_text('housing.common.in')} {assignment[3]}")
            print(f"{get_text('housing.assignment.move_in_label')}: {assignment[4]}")
            print(f"{get_text('housing.assignment.move_out_label')}: {assignment[5]}")
            if assignment[6]:
                print(f"{get_text('housing.assignment.actual_move_out_label')}: {assignment[6]}")
            print(f"{get_text('housing.assignment.rent_label')}: £{assignment[7]}")
            print(f"{get_text('housing.assignment.status_label')}: {assignment[8]}")
            print(f"{get_text('housing.assignment.assigned_by_label')}: {assignment[10]}")
            print(f"{get_text('housing.assignment.date_label')}: {assignment[11]}")

        # If staff/admin is viewing and application is pending, ask if they want to process it
        if (auth.check_permission('approve_accommodations') and application[12] == 'Pending'):
            process_now = input("\n" + get_text("housing.application.process_now_prompt") + " (y/n): ").lower() == 'y'

            if process_now:
                conn.close()  # Close current connection before processing
                process_application(application_id)
                return

        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.application.error_viewing", error=str(e)))
