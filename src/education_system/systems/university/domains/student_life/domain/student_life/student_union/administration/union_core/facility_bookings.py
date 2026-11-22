"""Student Union facility bookings: request, view, approve.

Split out of ``student_union_core.py``, which re-exports every name here;
callers keep importing from ``student_union_core``.
"""

from datetime import datetime

from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import mirror as _mirror_to_calendar
from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.common import (
    _club_current_student,
    get_current_user,
    _send_club_email,
)


FACILITY_DECISION_TEMPLATE = "student_life/student_union/facility_booking_decision"

def _current_user_row_id(conn):
    """The numeric users.id for the signed-in user, or None.

    facility_bookings.user_id is an INTEGER with a foreign key onto users(id),
    so writing a student_id string there fails the constraint. The student's
    own reference lives in the TEXT booker_id column instead.
    """
    try:
        user = get_current_user()
    except Exception:
        user = None
    if not user:
        return None
    row = conn.execute(
        "SELECT id FROM users WHERE id = ? OR username = ? LIMIT 1",
        (user.get('id'), user.get('username'))).fetchone()
    return row[0] if row else None


def request_facility_booking():
    """Request a facility booking as the signed-in student.

    The queries here targeted columns that do not exist: the real
    facility_bookings table uses booking_id / user_id / start_time / end_time,
    not id / student_id / time_slot. The CREATE TABLE IF NOT EXISTS above them
    declared the wrong shape but was a no-op against the existing table, so
    every booking failed with "no column named student_id".
    """
    print("\n=== Request Facility Booking ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, student_email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to request a booking.")
            return
        print(f"Booking as: {student_name} ({student_id})")

        cursor.execute(
            "SELECT facility_id, facility_name, location, capacity, booking_fee"
            " FROM union_facilities WHERE COALESCE(status,'available') = 'available'"
            " ORDER BY facility_name")
        facilities = cursor.fetchall()
        if not facilities:
            print("There are no facilities available to book.")
            return

        print("\nAvailable facilities:")
        for index, (_fid, name, location, capacity, fee) in enumerate(facilities, 1):
            bits = [location or 'location TBC']
            if capacity:
                bits.append(f"capacity {capacity}")
            if fee:
                bits.append(f"£{float(fee):.2f}")
            print(f"{index}. {name}  ({' · '.join(bits)})")

        facility_name = None
        while facility_name is None:
            raw = input(f"\nSelect a facility (1-{len(facilities)}, blank to cancel): ").strip()
            if not raw:
                print("Booking cancelled.")
                return
            if raw.isdigit() and 1 <= int(raw) <= len(facilities):
                facility_name = facilities[int(raw) - 1][1]
            else:
                print(f"Please enter a number between 1 and {len(facilities)}.")

        booking_date = None
        while booking_date is None:
            raw = input("Date (YYYY-MM-DD, blank to cancel): ").strip()
            if not raw:
                print("Booking cancelled.")
                return
            try:
                datetime.strptime(raw, '%Y-%m-%d')
                booking_date = raw
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        start_time = None
        while start_time is None:
            raw = input("Start time (HH:MM, blank to cancel): ").strip()
            if not raw:
                print("Booking cancelled.")
                return
            try:
                datetime.strptime(raw, '%H:%M')
                start_time = raw
            except ValueError:
                print("Invalid time format. Please use HH:MM.")

        end_time = None
        while end_time is None:
            raw = input("End time (HH:MM, blank to cancel): ").strip()
            if not raw:
                print("Booking cancelled.")
                return
            try:
                if datetime.strptime(raw, '%H:%M') <= datetime.strptime(start_time, '%H:%M'):
                    print("The end time must be after the start time.")
                    continue
                end_time = raw
            except ValueError:
                print("Invalid time format. Please use HH:MM.")

        purpose = input("Purpose of booking: ").strip()

        # Refuse an overlapping booking rather than double-booking the room.
        cursor.execute('''
            SELECT start_time, end_time FROM facility_bookings
            WHERE facility_name = ? AND booking_date = ?
              AND COALESCE(status, 'pending') IN ('pending', 'approved')
        ''', (facility_name, booking_date))
        for existing_start, existing_end in cursor.fetchall():
            if existing_start and existing_end and start_time < existing_end and end_time > existing_start:
                print(f"{facility_name} is already booked on {booking_date} "
                      f"from {existing_start} to {existing_end}.")
                return

        cursor.execute('''
            INSERT INTO facility_bookings
            (facility_name, user_id, booker_id, booking_date, start_time, end_time,
             purpose, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        ''', (facility_name, _current_user_row_id(conn), student_id, booking_date,
              start_time, end_time, purpose or None,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        booking_id = cursor.lastrowid
        print(f"\n✓ Booking request submitted for {facility_name} on "
              f"{booking_date}, {start_time}-{end_time} (ID {booking_id}).")
        print("It is pending approval — you will be told once it is reviewed.")

        if _mirror_to_calendar(
            name=f"SU Booking: {facility_name}", kind="facility_booking",
            date=booking_date, start_time=start_time, end_time=end_time,
            location=facility_name,
            description=(purpose or "Student Union facility booking")
                        + " (pending approval)",
            created_by=student_id, organizer=student_name,
            source_table="facility_bookings", source_id=booking_id,
            conn=conn,
        ):
            print("It is on the university academic calendar.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def view_my_bookings():
    """View the signed-in student's facility bookings."""
    print("\n=== My Bookings ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to view your bookings.")
            return
        print(f"Bookings for {student_name} ({student_id}):")

        cursor.execute('''
            SELECT facility_name, booking_date, start_time, end_time,
                   COALESCE(status, 'pending'), purpose
            FROM facility_bookings
            WHERE booker_id = ? OR user_id = ?
            ORDER BY booking_date DESC, start_time
        ''', (student_id, _current_user_row_id(cursor.connection)))

        bookings = cursor.fetchall()
        if not bookings:
            print("No bookings found.")
            return

        for facility, date, start, end, status, purpose in bookings:
            when = f"{start or '?'}-{end or '?'}"
            print(f"\n• {facility}")
            print(f"  Date: {date} | Time: {when}")
            print(f"  Status: {status}")
            if purpose:
                print(f"  Purpose: {purpose}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def approve_facility_bookings():
    """Approve or reject pending facility bookings."""
    print("\n=== Approve Bookings ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT b.booking_id, b.facility_name,
                   COALESCE(b.booker_id, u.student_id) AS student_ref, b.booking_date,
                   b.start_time, b.end_time, b.purpose,
                   s.first_name, s.last_name, s.email_address
            FROM facility_bookings b
            LEFT JOIN users u ON b.user_id = u.id
            LEFT JOIN students s ON s.student_id = COALESCE(b.booker_id, u.student_id)
            WHERE COALESCE(b.status, 'pending') = 'pending'
            ORDER BY b.booking_date, b.start_time
        ''')

        bookings = cursor.fetchall()
        if not bookings:
            print("No pending bookings.")
            return

        for index, row in enumerate(bookings, 1):
            (_bid, facility, uid, date, start, end, purpose,
             first, last, _email) = row
            who = f"{first or ''} {last or ''}".strip() or uid
            print(f"\n{index}. {facility} — {who} ({uid})")
            print(f"   {date} {start or '?'}-{end or '?'}")
            if purpose:
                print(f"   Purpose: {purpose}")

        raw = input(f"\nSelect a booking to review (1-{len(bookings)}, blank to quit): ").strip()
        if not raw:
            return
        if not (raw.isdigit() and 1 <= int(raw) <= len(bookings)):
            print("Invalid choice.")
            return

        (booking_id, facility, uid, date, start, end, _purpose,
         first, last, email) = bookings[int(raw) - 1]
        who = f"{first or ''} {last or ''}".strip() or uid

        decision = input("Approve or reject? (a/r, blank to cancel): ").strip().lower()
        if decision not in ('a', 'r'):
            print("No decision recorded.")
            return
        new_status = 'approved' if decision == 'a' else 'rejected'

        cursor.execute('UPDATE facility_bookings SET status = ? WHERE booking_id = ?',
                       (new_status, booking_id))
        conn.commit()
        print(f"✓ Booking {booking_id} {new_status}.")

        # Tell the student either way — an approval nobody hears about is the
        # same as no booking, and a silent rejection means they turn up.
        if _send_club_email(FACILITY_DECISION_TEMPLATE, email, {
                'student_name': who,
                'facility_name': facility,
                'booking_date': date,
                'start_time': start or 'Not specified',
                'end_time': end or 'Not specified',
                'status': new_status,
                'decision_headline': ('APPROVED' if new_status == 'approved'
                                      else 'NOT APPROVED'),
                'decision_emoji': '✅' if new_status == 'approved' else '❌',
                'decision_message': (
                    'Your booking is confirmed. The space is yours for the time below.'
                    if new_status == 'approved' else
                    'Unfortunately this booking could not be approved.'),
                'next_steps': (
                    'Arrive a few minutes early. If you no longer need the space, '
                    'cancel it so someone else can use it.'
                    if new_status == 'approved' else
                    'Contact the Students\' Union to discuss alternative times or '
                    'facilities.'),
                'decided_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):
            print(f"📧 Decision emailed to {email}.")
        elif email:
            print("Note: the decision email could not be sent.")
        else:
            print("No email address on file, so no decision email was sent.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()
