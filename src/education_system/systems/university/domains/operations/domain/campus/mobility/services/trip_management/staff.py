from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import _common
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import sqlite3, get_text, logging, datetime, log_create
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.database import safe_db_operation


logger = logging.getLogger(__name__)

STAFF_ROLES = ('supervisor', 'coordinator', 'medical', 'transport')


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


# ---------------------------------------------------------------------------
# Domain API (same contract as trips.py). Assigning staff needs
# ``manage_trips`` — it decides who leads, so a leader cannot add leaders.
# ---------------------------------------------------------------------------

def list_trip_staff(trip_id, conn=None):
    """``[{id, staff_user_id, role, assigned_date, first_aider, dbs_status,
    dbs_checked_at, username, name}]`` for a trip, by role then name."""
    with _db().read_connection(conn) as c:
        cur = c.execute(
            "SELECT ts.id, ts.staff_user_id, ts.role, ts.assigned_date, ts.first_aider, "
            "ts.dbs_status, ts.dbs_checked_at, u.username, "
            "COALESCE(NULLIF(TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, '')), ''), "
            "u.username, 'user ' || ts.staff_user_id) AS name "
            "FROM trip_staff ts LEFT JOIN users u ON u.id = ts.staff_user_id "
            "WHERE ts.trip_id = ? ORDER BY ts.role, name", (trip_id,))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def assign_staff_member(auth, trip_id, staff_user_id, role='supervisor', *, first_aider=False,
                        conn=None, pending=None):
    """Put a member of staff (``users.id``) on a trip. Returns the assignment id."""
    trips = _trips()
    who = trips._require(auth, 'manage_trips')
    if role not in STAFF_ROLES:
        raise ValueError(f"role must be one of {', '.join(STAFF_ROLES)}")

    def work(c, p):
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        if trip['status'] in ('completed', 'archived', 'cancelled'):
            raise ValueError(f"the trip is {trip['status']}")
        staff = c.execute(
            "SELECT 1 FROM users WHERE id = ? AND LOWER(role) IN ('admin', 'staff', 'instructor')",
            (staff_user_id,)).fetchone()
        if not staff:
            raise ValueError(get_text("mobility.trip_management.staff.invalid_selection",
                                      "Invalid staff selection."))
        try:
            assignment_id = c.execute(
                "INSERT INTO trip_staff (trip_id, staff_user_id, role, assigned_date, first_aider) "
                "VALUES (?, ?, ?, ?, ?)",
                (trip_id, staff_user_id, role, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                 1 if first_aider else 0)).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(get_text("mobility.trip_management.staff.already_assigned",
                                      "Staff member is already assigned to this trip.")) from None
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='staff_assigned', field='trip_staff',
                             new_value=f"{staff_user_id}:{role}")
        trips._publish_after(p, "trip.updated", trip_id=trip_id, fields=['staff'])
        return assignment_id
    return trips._in_transaction(conn, pending, work)


def unassign_staff_member(auth, trip_id, assignment_id, *, conn=None, pending=None):
    """Take a staff assignment (``trip_staff.id``) off a trip."""
    trips = _trips()
    who = trips._require(auth, 'manage_trips')

    def work(c, p):
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        row = c.execute("SELECT staff_user_id, role FROM trip_staff WHERE id = ? AND trip_id = ?",
                        (assignment_id, trip_id)).fetchone()
        if not row:
            raise ValueError("staff assignment not found")
        c.execute("DELETE FROM trip_staff WHERE id = ? AND trip_id = ?", (assignment_id, trip_id))
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='staff_removed', field='trip_staff',
                             old_value=f"{row[0]}:{row[1]}")
        trips._publish_after(p, "trip.updated", trip_id=trip_id, fields=['staff'])
        return True
    return trips._in_transaction(conn, pending, work)


@log_create(module="trips", description="Assigning staff to trip")
def assign_trip_staff():
    """Assign staff members to trips"""
    auth = _common.get_auth()

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_assign_staff", "You must be logged in to assign trip staff."))
        return False

    if not auth.check_permission('manage_trips'):
        print(get_text("mobility.trip_management.auth.no_permission_assign_staff", "You don't have permission to assign trip staff."))
        return False

    with _db().read_connection() as conn:
        trips = [tuple(r) for r in conn.execute('''
        SELECT id, trip_name, destination, start_date, status
        FROM trips
        WHERE status NOT IN ('completed', 'archived', 'cancelled')
        ORDER BY start_date ASC
        ''').fetchall()]

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
    except ValueError:
        print(get_text("mobility.trip_management.validation.invalid_input", "Invalid input."))
        return False

    trip_name = next((t[1] for t in trips if t[0] == trip_id), None)
    if trip_name is None:
        print(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        return False

    with _db().read_connection() as conn:
        available_staff = [tuple(r) for r in conn.execute('''
        SELECT u.id, u.first_name, u.last_name, u.username, LOWER(u.role)
        FROM users u
        WHERE LOWER(u.role) IN ('admin', 'staff', 'instructor')
        AND u.id NOT IN (
            SELECT staff_user_id FROM trip_staff WHERE trip_id = ?
        )
        ORDER BY LOWER(u.role), u.last_name
        ''', (trip_id,)).fetchall()]
        current_staff = [tuple(r) for r in conn.execute('''
        SELECT ts.role, u.first_name || ' ' || u.last_name as staff_name
        FROM trip_staff ts
        JOIN users u ON ts.staff_user_id = u.id
        WHERE ts.trip_id = ?
        ORDER BY ts.role
        ''', (trip_id,)).fetchall()]

    if not available_staff:
        print(get_text("mobility.trip_management.staff.no_available_staff", "No available staff members to assign."))
        return False

    print(get_text("mobility.trip_management.staff.assigning_to", "\nAssigning staff to: {trip_name}").format(trip_name=trip_name))
    if current_staff:
        print("\n" + get_text("mobility.trip_management.staff.currently_assigned", "Currently Assigned Staff:"))
        for role, name in current_staff:
            print(get_text("mobility.trip_management.staff.staff_line", "- {name} - {role}").format(name=name, role=role.title()))

    print("\n" + get_text("mobility.trip_management.staff.available_members", "Available Staff Members:"))
    print("-" * 70)
    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.username', 'Username'):<20} {get_text('mobility.trip_management.headers.role', 'Role'):<15}")
    print("-" * 70)
    for user_id, first_name, last_name, username, role in available_staff:
        full_name = f"{first_name or ''} {last_name or ''}".strip() or username
        print(f"{user_id:<5} {full_name[:24]:<25} {username[:19]:<20} {role.title():<15}")
    print("-" * 70)

    try:
        staff_id = int(input(get_text("mobility.trip_management.staff.enter_staff_id", "\nEnter Staff User ID to assign: ")))
    except ValueError:
        print(get_text("mobility.trip_management.validation.invalid_input", "Invalid input."))
        return False

    selected_staff = next((s for s in available_staff if s[0] == staff_id), None)
    if not selected_staff:
        print(get_text("mobility.trip_management.staff.invalid_selection", "Invalid staff selection."))
        return False
    staff_name = f"{selected_staff[1]} {selected_staff[2]}"

    print(get_text("mobility.trip_management.staff.select_role", "\nAssigning {staff_name} to trip. Select role:").format(staff_name=staff_name))
    for i, role_option in enumerate(STAFF_ROLES, 1):
        print(f"{i}. {role_option.title()}")
    while True:
        try:
            role_choice = int(input(get_text("mobility.trip_management.staff.select_role_prompt", "Select role (1-4): "))) - 1
            if 0 <= role_choice < len(STAFF_ROLES):
                selected_role = STAFF_ROLES[role_choice]
                break
            print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
        except ValueError:
            print(get_text("mobility.trip_management.validation.enter_number", "Please enter a number."))
    first_aider = input(get_text("mobility.trip_management.staff.first_aider_prompt",
                                 "Qualified first aider on this trip? (y/n): ")).strip().lower() in ('y', 'yes')

    try:
        assign_staff_member(auth, trip_id, staff_id, selected_role, first_aider=first_aider)
    except (ValueError, PermissionError) as e:
        print(str(e))
        return False
    except sqlite3.Error as e:
        print(get_text("mobility.trip_management.errors.assigning_staff", "Error assigning staff: {error}").format(error=e))
        logging.error(get_text("mobility.trip_management.errors.in_assign_staff", "Error in assign_trip_staff: {error}").format(error=e))
        return False

    print(get_text("mobility.trip_management.staff.assigned", "{staff_name} assigned to '{trip_name}' as {role}").format(staff_name=staff_name, trip_name=trip_name, role=selected_role.title()))
    return True
