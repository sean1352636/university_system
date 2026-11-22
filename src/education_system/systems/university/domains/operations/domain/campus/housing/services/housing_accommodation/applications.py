import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, housing_text, get_connection, generate_id,
    log_create, log_read, log_update,
)


# An application in one of these states is still "open": the student is
# waiting on us, so a second application would compete with it rather than
# sit alongside it. 'Approved' is deliberately absent — a student with an
# approved application has a room and an assignment behind it, which the
# existing active-housing check handles.
OPEN_APPLICATION_STATUSES = ('Pending', 'Under Review', 'More Info Needed', 'Waiting List')

# Typing any of these at a prompt backs out to the menu instead of answering.
_CANCEL_TOKENS = ('q', 'quit', 'cancel', 'menu', 'back', 'exit')


def _cancel_hint():
    return get_text("housing.common.cancel_hint",
                    default="or 'q' to return to the menu")


def prompt_required(label, validate=None):
    """Ask for a value until we get a usable one, or the user backs out.

    A blank answer is never accepted silently: it prints an error and asks
    the same question again. Returns the value, or ``None`` when the user
    asked to go back to the menu — callers treat ``None`` as "return".

    *validate* is an optional ``value -> (ok, cleaned_or_error)`` callable.
    """
    while True:
        raw = input(f"{label} ({_cancel_hint()}): ").strip()

        if raw.lower() in _CANCEL_TOKENS:
            return None

        if not raw:
            print(housing_text("housing.common.error_field_blank",
                           default="This field cannot be left blank. Please try again.",
                           field=label))
            continue

        if validate is None:
            return raw

        ok, result = validate(raw)
        if ok:
            return result
        print(result)


def prompt_choice(label, options, allow_zero_label=None):
    """Numbered menu prompt with the same blank/cancel handling.

    *options* is a list of display strings. Returns the zero-based index,
    ``-1`` when *allow_zero_label* is offered and chosen, or ``None`` when
    the user backs out. The whole menu is reprinted after a bad answer, so
    the operator can always see what the valid options were.
    """
    low = 0 if allow_zero_label else 1

    while True:
        print("\n" + label + ":")
        print("=" * max(len(label) + 1, 16))
        if allow_zero_label:
            print(f"0. {allow_zero_label}")
        for i, option in enumerate(options, 1):
            print(f"{i}. {option}")

        raw = input(f"{get_text('housing.common.select_prompt', default='Select: ')} ({_cancel_hint()}): ").strip()

        if raw.lower() in _CANCEL_TOKENS:
            return None

        if not raw:
            print(housing_text("housing.common.error_field_blank",
                           default="This field cannot be left blank. Please try again.",
                           field=label))
            continue

        try:
            value = int(raw)
        except ValueError:
            print(get_text("housing.common.error_valid_number"))
            continue

        if low <= value <= len(options):
            return value - 1
        print(get_text("housing.common.error_range", min=low, max=len(options)))


def _validate_date(raw):
    try:
        datetime.datetime.strptime(raw, '%Y-%m-%d')
        return True, raw
    except ValueError:
        return False, get_text("housing.application.invalid_date_format")


def _validate_positive_int(raw):
    try:
        value = int(raw)
    except ValueError:
        return False, get_text("housing.common.error_valid_number")
    if value <= 0:
        return False, get_text("housing.application.error_duration_positive")
    return True, value


def _student_contact(cursor, student_id):
    """(name, email) for a student, both possibly empty."""
    cursor.execute('''
    SELECT first_name, last_name, email_address FROM students WHERE student_id = ?
    ''', (student_id,))
    row = cursor.fetchone()
    if not row:
        return '', ''
    return f"{row[0] or ''} {row[1] or ''}".strip(), (row[2] or '')


def find_open_applications(cursor, student_id):
    """Every still-open application for *student_id*, newest first."""
    placeholders = ','.join('?' * len(OPEN_APPLICATION_STATUSES))
    cursor.execute('''
    SELECT application_id, application_date, status, preferred_room_type,
           requested_move_in_date, requested_duration_months
    FROM housing_applications
    WHERE student_id = ? AND status IN ({statuses})
    ORDER BY application_date DESC
    '''.format(statuses=placeholders), [student_id] + list(OPEN_APPLICATION_STATUSES))
    return [
        {
            'application_id': row[0],
            'application_date': row[1],
            'status': row[2],
            'room_type': row[3],
            'move_in_date': row[4],
            'duration_months': row[5],
        }
        for row in cursor.fetchall()
    ]


def send_outcome_notification(application_id):
    """Email the student the outcome now recorded against *application_id*.

    Re-reads the application on its own connection, so it is safe to call
    only *after* the processing transaction has committed — which is the
    point: the student must never be told about a decision that rolled
    back. When a room was assigned, its building, number and floor are
    included. Returns True if the email went out.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT a.application_id, a.student_id, s.first_name, s.last_name, s.email_address,
               a.application_date, b.building_name, a.preferred_room_type,
               a.requested_move_in_date, a.requested_duration_months,
               a.special_requirements, a.status, a.notes, a.reviewed_by, a.review_date
        FROM housing_applications a
        JOIN students s ON a.student_id = s.student_id
        LEFT JOIN housing_buildings b ON a.preferred_building_id = b.building_id
        WHERE a.application_id = ?
        ''', (application_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        payload = {
            'application_id': row[0],
            'student_id': row[1],
            'student_name': f"{row[2] or ''} {row[3] or ''}".strip(),
            'email_address': row[4],
            'application_date': row[5],
            'preferred_building': row[6],
            'room_type': row[7],
            'move_in_date': row[8],
            'duration_months': row[9],
            'special_requirements': row[10],
            'status': row[11],
            'notes': row[12],
            'reviewed_by': row[13],
            'review_date': row[14],
        }

        cursor.execute('''
        SELECT b.building_name, r.room_number, r.floor_number, r.room_type,
               a.monthly_rent, a.move_in_date, a.planned_move_out_date, a.contract_number
        FROM housing_assignments a
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.application_id = ?
        ORDER BY a.created_at DESC
        ''', (application_id,))
        assignment = cursor.fetchone()
        if assignment:
            payload['assignment_details'] = _common.format_assignment_details(*assignment)

        conn.close()
        return _common.send_application_outcome_email(payload)
    except Exception as exc:
        # The decision is already committed; failing to email must not undo
        # it or crash the operator out of the menu.
        print(get_text("housing.application.email_failed",
                       default="Note: the outcome email could not be sent."))
        return False


def supersede_applications(cursor, applications, actor, timestamp=None):
    """Withdraw *applications* because a replacement is being submitted."""
    timestamp = timestamp or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for row in applications:
        cursor.execute('''
        UPDATE housing_applications
        SET status = 'Superseded',
            notes = COALESCE(notes || ' | ', '') || ?,
            reviewed_by = ?, review_date = ?, updated_at = ?
        WHERE application_id = ?
        ''', ('Replaced by a newer application submitted by the student.',
              actor, timestamp, timestamp, row['application_id']))


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

        # One open application per student. If any already exist, the operator
        # decides: keep what is there, or replace it with what they are about
        # to enter. Nothing is withdrawn until the new application is actually
        # written, so answering "no" — or backing out later — leaves the
        # existing application exactly as it was.
        existing_applications = find_open_applications(cursor, student_id)
        overriding = False

        if existing_applications:
            print("\n" + housing_text(
                "housing.application.already_open",
                default="{count} open application(s) already exist for {student}:",
                count=len(existing_applications), student=student_id,
            ))
            for row in existing_applications:
                print(f"  - {row['application_id']} ({row['status']}), "
                      f"submitted {row['application_date']}, "
                      f"{row['room_type']} from {row['move_in_date']} "
                      f"for {row['duration_months']} month(s)")

            answer = input("\n" + get_text(
                "housing.application.override_prompt",
                default="Replace the existing application with a new one?",
            ) + " (y/n): ").strip().lower()

            if answer != 'y':
                print(get_text(
                    "housing.application.override_declined",
                    default="Keeping the existing application. Nothing has been changed.",
                ))
                conn.close()
                return

            overriding = True

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

        # Every prompt below rejects a blank answer with an error and asks
        # again; 'q' at any of them abandons the whole application and goes
        # back to the menu without writing anything.
        index = prompt_choice(
            get_text("housing.application.select_preferred_building"),
            [bname for _bid, bname in buildings],
            allow_zero_label=get_text("housing.application.no_preference"),
        )
        if index is None:
            print(housing_text("housing.common.operation_cancelled", default="Operation cancelled."))
            conn.close()
            return
        preferred_building_id = None if index == -1 else buildings[index][0]
        preferred_building_name = (get_text("housing.application.no_preference")
                                   if index == -1 else buildings[index][1])

        room_types = ["Single", "Double", "Triple", "Suite", "Studio", "Apartment"]
        index = prompt_choice(
            get_text("housing.application.select_room_type"),
            [get_text('housing.room.type_' + rt.lower()) for rt in room_types],
        )
        if index is None:
            print(housing_text("housing.common.operation_cancelled", default="Operation cancelled."))
            conn.close()
            return
        preferred_room_type = room_types[index]

        move_in_date = prompt_required(
            get_text("housing.application.move_in_date_prompt"), _validate_date)
        if move_in_date is None:
            print(housing_text("housing.common.operation_cancelled", default="Operation cancelled."))
            conn.close()
            return

        duration = prompt_required(
            get_text("housing.application.duration_prompt"), _validate_positive_int)
        if duration is None:
            print(housing_text("housing.common.operation_cancelled", default="Operation cancelled."))
            conn.close()
            return

        # The only genuinely optional field, so blank is a real answer here
        # rather than an error.
        special_requirements = input(
            get_text("housing.application.special_requirements_prompt")
            + " (" + get_text("housing.common.optional", default="optional") + "): "
        ).strip() or None

        # Create application
        application_id = generate_id('APP')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        actor = auth.current_user.get('username') if auth.current_user else 'housing'

        # Withdraw the old application(s) in the same transaction as the new
        # one, so the student is never left with none at all.
        if overriding:
            supersede_applications(cursor, existing_applications, actor, timestamp)

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

        student_name, student_email = _student_contact(cursor, student_id)

        conn.commit()

        if overriding:
            print("\n" + housing_text(
                "housing.application.override_success",
                default="Application {id} submitted, replacing {count} previous application(s).",
                id=application_id, count=len(existing_applications),
            ))
        else:
            print("\n" + get_text("housing.application.create_success", id=application_id))

        # Email the student through the university email system, after the
        # commit so we never promise something that was rolled back.
        email_payload = {
            'application_id': application_id,
            'student_id': student_id,
            'student_name': student_name,
            'email_address': student_email,
            'submission_date': timestamp,
            'submitted_by': actor,
            'preferred_building': preferred_building_name,
            'room_type': preferred_room_type,
            'move_in_date': move_in_date,
            'duration_months': duration,
            'special_requirements': special_requirements,
            'status': 'Pending',
        }
        if overriding:
            emailed = _common.send_application_overwritten_email(
                email_payload, existing_applications)
        else:
            emailed = _common.send_application_submitted_email(email_payload)

        if emailed:
            print(housing_text("housing.application.email_sent",
                           default="A confirmation email has been sent to {email}.",
                           email=student_email))
        else:
            print(get_text("housing.application.email_failed",
                           default="Note: the confirmation email could not be sent."))

        # If staff/admin is creating, ask if they want to approve immediately
        if auth.check_permission('approve_accommodations'):
            approve_now = input("\n" + get_text("housing.application.approve_now_prompt") + " (y/n): ").lower() == 'y'

            if approve_now:
                conn.close()
                process_application(application_id)
                return

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
        print(f"{get_text('housing.application.requirements_label')}: {application[10] or get_text('housing.common.none', default='None')}")

        # Ask for decision
        print("\n" + get_text("housing.application.process_title") + ":")
        print("1. " + get_text("housing.application.approve_action"))
        print("2. " + get_text("housing.application.reject_action"))
        print("3. " + get_text("housing.application.waitlist_action"))
        print("4. " + get_text("housing.application.request_info_action"))
        print("5. " + get_text("housing.common.cancel", default="Cancel"))

        decision = input("\n" + get_text("housing.application.enter_decision") + ": ")

        if decision == '5':
            print(housing_text("housing.common.operation_cancelled", default="Operation cancelled."))
            conn.close()
            return

        notes = input(get_text("housing.application.notes_prompt") + ": ").strip() or None
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pending_rent_charge = None

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
                        send_outcome_notification(application_id)
                        return

                    print("\n" + get_text("housing.application.available_room_types") + ":")
                    for i, room_type in enumerate(available_types, 1):
                        print(f"{i}. {room_type[0]}")

                    while True:
                        try:
                            type_choice = int(input("\n" + get_text("housing.common.select_prompt", default="Select: ") + " "))
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
                        send_outcome_notification(application_id)
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
                    send_outcome_notification(application_id)
                    return

                else:
                    print(housing_text("housing.common.operation_cancelled", default="Operation cancelled."))
                    conn.close()
                    return

            # Display available rooms
            print("\n" + get_text("housing.room.available_rooms") + ":")
            print("=" * 15)

            for i, room in enumerate(available_rooms, 1):
                building_id = room[1]
                cursor.execute('SELECT building_name FROM housing_buildings WHERE building_id = ?', (building_id,))
                building_name = cursor.fetchone()[0]

                print(f"{i}. {get_text('housing.building.name_label')}: {building_name}, {get_text('housing.room.number_label')}: {room[2]}, {get_text('housing.room.floor_label')}: {room[3]}, {get_text('housing.room.type_label')}: {room[4]}, {get_text('housing.room.rent_label')}: £{room[5]}/{get_text('housing.common.month', default='Month')}")

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
                from education_system.systems.university.services.bus import (
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
                logger.debug("Suppressed exception", exc_info=True)

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

            # Cross-domain: post the first month's rent through finance_bus so
            # the Finance GUI's account view, holds and bus events all reflect
            # the new tenancy.
            #
            # This is deliberately *deferred* until after this connection has
            # committed and closed. finance_bus opens its own connection to the
            # same SQLite file; called from here it would try to write while
            # the housing INSERT/UPDATEs above still hold a RESERVED lock, and
            # the second writer would sit out its busy-timeout and fail with
            # "database is locked" — which is exactly what
            #   raise_charge(S12345, 770.0) failed: database is locked
            # was. One writer at a time, so it goes after the commit.
            pending_rent_charge = {
                'student_id': application[1],
                'assignment_id': assignment_id,
                'amount': monthly_rent,
                'period_start': move_in_date,
                'period_end': (datetime.datetime.strptime(move_in_date, '%Y-%m-%d')
                               + datetime.timedelta(days=30)).strftime('%Y-%m-%d'),
                'processed_by': (auth.current_user.get('username')
                                 if auth and auth.current_user else None),
            }

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
            print(f"{get_text('housing.room.number_label')}: {assignment[2]} {get_text('housing.common.in', default='In')} {assignment[3]}")
            print(f"{get_text('housing.assignment.move_in_label')}: {assignment[4]}")
            print(f"{get_text('housing.assignment.move_out_label')}: {assignment[5]}")
            print(f"{get_text('housing.assignment.rent_label')}: £{assignment[6]}")

        conn.close()

        # Everything below runs with no housing connection open, so the
        # second writer (finance_bus) and the email system each get the
        # database to themselves.
        if pending_rent_charge:
            try:
                from education_system.systems.university.services.bus import (
                    housing_finance,
                )
                housing_finance.post_rent_charge(
                    pending_rent_charge['student_id'],
                    pending_rent_charge['assignment_id'],
                    pending_rent_charge['amount'],
                    period_start=pending_rent_charge['period_start'],
                    period_end=pending_rent_charge['period_end'],
                    processed_by=pending_rent_charge['processed_by'],
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        # Tell the student the outcome, whatever it was.
        if send_outcome_notification(application_id):
            print(get_text("housing.application.outcome_email_sent",
                           default="An email about this decision has been sent to the student."))

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
                    print(get_text("housing.common.invalid_choice", default="Invalid Choice."))
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
                print(get_text("housing.common.invalid_choice", default="Invalid Choice."))
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
        print(f"{get_text('housing.application.requirements_label')}: {application[11] or get_text('housing.common.none', default='None')}")
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
            print(f"{get_text('housing.room.number_label')}: {assignment[2]} {get_text('housing.common.in', default='In')} {assignment[3]}")
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


# Room types a student can ask for (the housing GUI's list).
ROOM_TYPES = ("Single", "Double", "Triple", "Suite", "Studio", "Apartment")


def list_halls():
    """``[(building_id, building_name), ...]`` — the halls a student can ask
    for, by name."""
    conn = get_connection()
    try:
        return [(r[0], r[1]) for r in conn.execute(
            "SELECT building_id, building_name FROM housing_buildings ORDER BY building_name")]
    finally:
        conn.close()


def submit_new_application(student_id, *, room_type, move_in_date, duration_months,
                           preferred_building_id=None, special_requirements=None,
                           actor="housing"):
    """File a Pending housing application without prompting — for screens
    other than Housing's own (Create Student). It joins the Housing GUI's
    Applications list for staff to process (approve, reject, waiting list),
    and the student gets the same confirmation e-mail as from Housing.

    Refuses (ValueError) a bad room type, date or duration, an unknown hall,
    or a student who already has an open application. Returns
    ``{'application_id', 'emailed'}``.
    """
    if room_type not in ROOM_TYPES:
        raise ValueError(f"Choose a room type ({', '.join(ROOM_TYPES)}).")
    try:
        datetime.datetime.strptime(str(move_in_date), '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"'{move_in_date}' is not a valid move-in date. Use YYYY-MM-DD.") from None
    try:
        duration_months = int(duration_months)
    except (TypeError, ValueError):
        duration_months = 0
    if not 1 <= duration_months <= 60:
        raise ValueError("The stay is between 1 and 60 months.")
    building_name = "No Preference"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if preferred_building_id:
            row = cursor.execute("SELECT building_name FROM housing_buildings WHERE building_id = ?",
                                 (preferred_building_id,)).fetchone()
            if not row:
                raise ValueError("That hall no longer exists.")
            building_name = row[0]
        if find_open_applications(cursor, student_id):
            raise ValueError(f"{student_id} already has an open housing application.")
        application_id = generate_id('APP')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO housing_applications (
            application_id, student_id, application_date, preferred_building_id, preferred_room_type,
            requested_move_in_date, requested_duration_months, special_requirements, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (application_id, student_id, timestamp, preferred_building_id or None, room_type,
              move_in_date, duration_months, (special_requirements or "").strip() or None,
              'Pending', timestamp, timestamp))
        student_name, student_email = _student_contact(cursor, student_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # E-mail after the commit, as Housing's own screens do.
    emailed = _common.send_application_submitted_email({
        'application_id': application_id, 'student_id': student_id,
        'student_name': student_name, 'email_address': student_email,
        'submission_date': timestamp, 'submitted_by': actor,
        'preferred_building': building_name, 'room_type': room_type,
        'move_in_date': move_in_date, 'duration_months': duration_months,
        'special_requirements': special_requirements, 'status': 'Pending',
    })
    log_create('housing_application', application_id,
               f"Housing application for {student_id} filed by {actor}")
    return {'application_id': application_id, 'emailed': bool(emailed)}
