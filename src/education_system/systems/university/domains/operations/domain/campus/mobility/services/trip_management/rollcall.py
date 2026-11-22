"""Roll calls on a trip, the emergency card, and trip attendance.

A roll call lists everyone holding a place when it is started (all marked
absent until ticked off); :func:`missing` is who has not been ticked. The
emergency card is what a leader carries: the 24/7 contact, the leaders and
their phones, how many are on the trip, the local emergency number and the
insurance reference.

When a trip counts as attendance (``counts_as_attendance`` with a
``module_code``), :func:`record_attendance` marks each participant who was
there present on the module for every day of the trip — through the
attendance service's writer (``services/bus/trip_care_bus``), once.
"""

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import (
    get_text, logging, datetime, timedelta,
)

logger = logging.getLogger(__name__)

# Places that are on a roll call.
ON_ROLL = ('registered', 'confirmed', 'attended')


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _manager_trip(auth, c, trip_id, who):
    trip = _trips().get_trip(trip_id, conn=c)
    if not trip:
        raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
    if not _trips().can_manage_trip(auth, trip, conn=c, who=who):
        raise PermissionError(get_text("mobility.trip_management.rollcall.not_leader",
                                       "Only the trip's leaders can take a roll call."))
    return trip


def start_rollcall(auth, trip_id, label=""):
    """Start a roll call of everyone on the trip. Returns its id."""
    who = _trips().actor(auth)
    with _db().write_transaction() as c:
        trip = _manager_trip(auth, c, trip_id, who)
        if trip['status'] in ('cancelled', 'archived', 'proposed', 'planning'):
            raise ValueError(f"no roll call on a {trip['status']} trip")
        label = str(label or '').strip() or f"Roll call {_now()[:16]}"
        rollcall_id = c.execute(
            "INSERT INTO trip_rollcalls (trip_id, label, taken_at, taken_by) VALUES (?, ?, ?, ?)",
            (trip_id, label, _now(), who['username'])).lastrowid
        c.execute(
            "INSERT INTO trip_rollcall_entries (rollcall_id, participant_id, present) "
            f"SELECT ?, id, 0 FROM trip_participants WHERE trip_id = ? "
            f"AND status IN ({', '.join('?' * len(ON_ROLL))})", (rollcall_id, trip_id, *ON_ROLL))
        return rollcall_id


def _rollcall_trip(c, rollcall_id):
    row = c.execute("SELECT trip_id FROM trip_rollcalls WHERE id = ?", (rollcall_id,)).fetchone()
    if not row:
        raise ValueError("no such roll call")
    return row[0]


def mark(auth, rollcall_id, participant_id, present, note=""):
    """Tick a participant present (or not) on a roll call."""
    who = _trips().actor(auth)
    with _db().write_transaction() as c:
        trip_id = _rollcall_trip(c, rollcall_id)
        _manager_trip(auth, c, trip_id, who)
        if not c.execute("SELECT 1 FROM trip_participants WHERE id = ? AND trip_id = ?",
                         (participant_id, trip_id)).fetchone():
            raise ValueError("that person is not on this trip")
        c.execute(
            "INSERT INTO trip_rollcall_entries (rollcall_id, participant_id, present, note) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (rollcall_id, participant_id) DO UPDATE SET "
            "present = excluded.present, note = excluded.note",
            (rollcall_id, participant_id, 1 if present else 0, str(note or '').strip() or None))
    return True


def missing(rollcall_id):
    """Who has not been ticked present: ``[{participant_id, name,
    emergency_contact_name, emergency_contact_phone, note}]``."""
    with _db().read_connection() as c:
        _rollcall_trip(c, rollcall_id)
        cur = c.execute(
            "SELECT e.participant_id, COALESCE(NULLIF(TRIM(COALESCE(s.first_name, '') || ' ' || "
            "COALESCE(s.last_name, '')), ''), u.username, tp.student_id) AS name, "
            "tp.emergency_contact_name, COALESCE(tp.emergency_contact_phone, tp.emergency_contact) "
            "AS emergency_contact_phone, e.note "
            "FROM trip_rollcall_entries e JOIN trip_participants tp ON tp.id = e.participant_id "
            "LEFT JOIN students s ON s.student_id = tp.student_id "
            "LEFT JOIN users u ON u.id = tp.user_id "
            "WHERE e.rollcall_id = ? AND COALESCE(e.present, 0) = 0 ORDER BY name",
            (rollcall_id,))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def list_rollcalls(trip_id):
    """A trip's roll calls, newest first, with present / total counts."""
    with _db().read_connection() as c:
        cur = c.execute(
            "SELECT r.id, r.label, r.taken_at, r.taken_by, "
            "COALESCE(SUM(e.present), 0) AS present, COUNT(e.id) AS total "
            "FROM trip_rollcalls r LEFT JOIN trip_rollcall_entries e ON e.rollcall_id = r.id "
            "WHERE r.trip_id = ? GROUP BY r.id ORDER BY r.taken_at DESC, r.id DESC", (trip_id,))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def emergency_card(trip_id):
    """The emergency card: a dict, with the printable version under ``'text'``."""
    db = _db()
    with db.read_connection() as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        leaders = [dict(zip(('name', 'role', 'phone', 'email', 'first_aider'), tuple(r))) for r in c.execute(
            "SELECT COALESCE(NULLIF(TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, '')), ''), "
            "u.username), ts.role, sp.phone_extension, u.email, COALESCE(ts.first_aider, 0) "
            "FROM trip_staff ts JOIN users u ON u.id = ts.staff_user_id "
            "LEFT JOIN staff_profiles sp ON sp.user_id = u.id "
            "WHERE ts.trip_id = ? ORDER BY CASE ts.role WHEN 'coordinator' THEN 0 ELSE 1 END, u.id",
            (trip_id,)).fetchall()]
        count = _trips().active_participant_count(c, trip_id)
    if trip.get('is_overseas'):
        local = get_text(
            "mobility.trip_management.card.local_overseas",
            "Local emergency number: check it for {country} before you travel "
            "(112 works across the EU and from most mobiles).",
        ).format(country=trip.get('country') or trip.get('destination') or '')
    else:
        local = get_text("mobility.trip_management.card.local_uk",
                         "Emergency services: 999 (or 112).")
    contact = trip.get('emergency_contact_24h') or get_text(
        "mobility.trip_management.card.no_24h", "NOT SET — add a 24/7 contact before the trip")
    card = {
        'trip_id': trip_id, 'trip_name': trip['trip_name'],
        'dates': (trip['start_date'], trip.get('end_date')),
        'destination': trip.get('destination'), 'emergency_contact_24h': trip.get('emergency_contact_24h'),
        'leaders': leaders, 'participant_count': count, 'local_emergency': local,
        'insurance_reference': trip.get('insurance_reference'),
    }
    lines = [get_text("mobility.trip_management.card.title", "EMERGENCY CARD"),
             f"{trip['trip_name']} — {trip.get('destination') or ''} "
             f"({trip['start_date']}{' to ' + trip['end_date'] if trip.get('end_date') and trip['end_date'] != trip['start_date'] else ''})",
             f"{get_text('mobility.trip_management.card.contact_24h', '24/7 university contact')}: {contact}",
             local,
             f"{get_text('mobility.trip_management.card.participants', 'Participants')}: {count}",
             f"{get_text('mobility.trip_management.card.insurance', 'Insurance reference')}: "
             f"{trip.get('insurance_reference') or get_text('mobility.trip_management.common.na', 'N/A')}",
             get_text('mobility.trip_management.card.leaders', 'Leaders') + ":"]
    if not leaders:
        lines.append("  " + get_text("mobility.trip_management.card.no_leaders", "none assigned"))
    for leader in leaders:
        extras = [x for x in (leader['phone'], leader['email']) if x]
        aid = " [first aider]" if leader['first_aider'] else ""
        lines.append(f"  {leader['name']} ({leader['role']}){aid}"
                     f"{': ' + ', '.join(extras) if extras else ''}")
    card['text'] = "\n".join(lines)
    return card


def _trip_days(trip):
    start = datetime.strptime(str(trip['start_date'])[:10], '%Y-%m-%d').date()
    end = datetime.strptime(str(trip.get('end_date') or trip['start_date'])[:10], '%Y-%m-%d').date()
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def present_students(trip_id, conn=None):
    """Student numbers of the participants who were on the trip: marked
    'attended', or ticked present on a roll call (and not marked no-show)."""
    with _db().read_connection(conn) as c:
        return [r[0] for r in c.execute(
            "SELECT DISTINCT tp.student_id FROM trip_participants tp "
            "WHERE tp.trip_id = ? AND tp.student_id IS NOT NULL AND ("
            "  tp.status = 'attended' OR (tp.status IN ('registered', 'confirmed') AND EXISTS ("
            "    SELECT 1 FROM trip_rollcall_entries e JOIN trip_rollcalls r ON r.id = e.rollcall_id "
            "    WHERE e.participant_id = tp.id AND r.trip_id = tp.trip_id AND e.present = 1)))",
            (trip_id,)).fetchall()]


def record_attendance(trip_id, *, recorded_by=None):
    """Mark each participant who was there present on the trip's module for
    every trip day (one ``attendance_records`` row per student per day).
    Only for trips with ``counts_as_attendance`` and a ``module_code``, once
    the trip is under way or done. Idempotent. Returns rows written."""
    trip = _trips().get_trip(trip_id)
    if not trip:
        raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
    if not trip.get('counts_as_attendance') or not trip.get('module_code'):
        return 0
    if trip['status'] not in ('in_progress', 'completed', 'archived'):
        return 0
    students = present_students(trip_id)
    if not students:
        return 0
    from education_system.systems.university.services.bus import trip_care_bus
    return trip_care_bus.record_trip_attendance(
        trip['module_code'], _trip_days(trip), students,
        recorded_by=recorded_by or 'system:trips',
        note=f"Trip {trip_id}: {trip['trip_name']}")
