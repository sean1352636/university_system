from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection, generate_id,
    log_create, log_read, log_update,
)
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation.applications import select_student


# Maintenance Request Functions
@log_create(module="housing", description="Creating maintenance request")
def create_maintenance_request():
    """Create a new maintenance request"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.maintenance.create")))
        return

    current_role = auth.current_user.get('role', '')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if current_role == 'student':
            # Students can only create requests for their own room
            if not auth.check_permission('view_own_record'):
                print(get_text("housing.maintenance.permission_denied"))
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
                print(get_text("housing.maintenance.no_active_assignment"))
                conn.close()
                return

            assignment_id, room_id, room_number, building_name = assignment

            print("\n" + get_text("housing.maintenance.creating_for_room", room=room_number, building=building_name))

        else:
            # Staff/admin can create requests for any room
            if not auth.check_permission('manage_accommodations'):
                print(get_text("housing.maintenance.permission_denied"))
                conn.close()
                return

            # Let staff/admin select a room
            print("\n" + get_text("housing.assignment.select_building_title") + ":")

            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()

            if not buildings:
                print(get_text("housing.building.no_buildings"))
                conn.close()
                return

            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")

            while True:
                try:
                    choice = int(input("\n" + get_text("housing.building.select") + ": "))
                    if 1 <= choice <= len(buildings):
                        building_id = buildings[choice - 1][0]
                        building_name = buildings[choice - 1][1]
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
                print(get_text("housing.maintenance.no_rooms_in_building"))
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
                        room_number = rooms[choice - 1][1]
                        break
                    else:
                        print(get_text("housing.assignment.enter_range", max=len(rooms)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

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
                print(f"\n{get_text('housing.room.current_occupants_label')}: {occupant[1]} {occupant[2]} ({student_id})")
            else:
                # For empty rooms, staff can still create a request but need to select a student as "reporter"
                print("\n" + get_text("housing.maintenance.room_no_occupant"))
                student_id = select_student()
                if not student_id:
                    conn.close()
                    return

            print("\n" + get_text("housing.maintenance.creating_for_room", room=room_number, building=building_name))

        # Get issue details
        print("\n" + get_text("housing.maintenance.select_issue_type") + ":")
        issue_types = [
            "Plumbing", "Electrical", "HVAC", "Appliance", "Furniture",
            "Pest Control", "Structural", "Lock/Key", "Cleaning", "Other"
        ]

        for i, issue in enumerate(issue_types, 1):
            print(f"{i}. {issue}")

        while True:
            try:
                choice = int(input("\n" + get_text("housing.maintenance.issue_type_prompt") + ": "))
                if 1 <= choice <= len(issue_types):
                    issue_type = issue_types[choice - 1]
                    break
                else:
                    print(get_text("housing.assignment.enter_range", max=len(issue_types)))
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        description = input(get_text("housing.maintenance.description_prompt") + ": ").strip()
        if not description:
            print(get_text("housing.maintenance.description_empty"))
            conn.close()
            return

        print("\n" + get_text("housing.maintenance.select_priority") + ":")
        print("1. " + get_text("housing.maintenance.priority_low"))
        print("2. " + get_text("housing.maintenance.priority_medium"))
        print("3. " + get_text("housing.maintenance.priority_high"))
        print("4. " + get_text("housing.maintenance.priority_emergency"))

        while True:
            priority_choice = input("\n" + get_text("housing.maintenance.priority_prompt") + " (1-4): ")
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
                print(get_text("housing.maintenance.invalid_priority"))

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
        print("\n" + get_text("housing.maintenance.request_created"))
        print(get_text("housing.maintenance.request_id_display", id=request_id))

        # If emergency, display special message
        if priority == 'Emergency':
            print("\n" + get_text("housing.maintenance.emergency_notice"))
            print(get_text("housing.maintenance.emergency_call"))

        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.maintenance.error_creating", error=str(e)))

@log_read(module="housing", description="Viewing maintenance requests")
def view_maintenance_requests():
    """View maintenance requests"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.maintenance.view_login_required"))
        return

    current_role = auth.current_user.get('role', '')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if current_role == 'student':
            # Students can only view their own requests
            if not auth.check_permission('view_own_record'):
                print(get_text("housing.maintenance.view_permission_denied"))
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
                print(get_text("housing.maintenance.no_own_requests"))
                conn.close()
                return

            print("\n" + get_text("housing.maintenance.your_requests_title") + ":")
            print("=" * 25)

            for i, req in enumerate(requests, 1):
                print(f"{i}. " + get_text("housing.maintenance.request_item", type=req[5], room=req[2], building=req[3], date=req[4]))
                print(f"   {get_text('housing.maintenance.status_label')}: {req[6]}")
                print()

            # Select request to view details
            while True:
                try:
                    choice = int(input("\n" + get_text("housing.maintenance.select_request") + ": "))
                    if 1 <= choice <= len(requests):
                        request_id = requests[choice - 1][0]
                        break
                    else:
                        print(get_text("housing.assignment.enter_range", max=len(requests)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

        else:
            # Admin/staff can view any request
            if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
                print(get_text("housing.maintenance.view_permission_denied"))
                conn.close()
                return

            # Allow filtering options
            print("\n" + get_text("housing.maintenance.view_title") + ":")
            print("1. " + get_text("housing.maintenance.view_all"))
            print("2. " + get_text("housing.maintenance.view_by_status"))
            print("3. " + get_text("housing.maintenance.view_by_building"))
            print("4. " + get_text("housing.maintenance.view_by_priority"))
            print("5. " + get_text("housing.maintenance.view_by_student"))

            filter_choice = input("\n" + get_text("housing.maintenance.enter_choice") + ": ")

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
                print("\n" + get_text("housing.maintenance.select_status") + ":")
                print("1. " + get_text("housing.maintenance.status_open"))
                print("2. " + get_text("housing.maintenance.status_in_progress"))
                print("3. " + get_text("housing.maintenance.status_pending_parts"))
                print("4. " + get_text("housing.maintenance.status_completed"))

                status_choice = input("\n" + get_text("housing.maintenance.enter_status_choice") + ": ")
                status_map = {
                    '1': 'Open',
                    '2': 'In Progress',
                    '3': 'Pending Parts',
                    '4': 'Complete'
                }

                if status_choice not in status_map:
                    print(get_text("housing.common.invalid_choice"))
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
                print("\n" + get_text("housing.maintenance.select_priority_filter") + ":")
                print("1. " + get_text("housing.maintenance.priority_emergency"))
                print("2. " + get_text("housing.maintenance.priority_high"))
                print("3. " + get_text("housing.maintenance.priority_medium"))
                print("4. " + get_text("housing.maintenance.priority_low"))

                priority_choice = input("\n" + get_text("housing.maintenance.enter_priority_choice") + ": ")
                priority_map = {
                    '1': 'Emergency',
                    '2': 'High',
                    '3': 'Medium',
                    '4': 'Low'
                }

                if priority_choice not in priority_map:
                    print(get_text("housing.common.invalid_choice"))
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
    auth = _common.auth

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
