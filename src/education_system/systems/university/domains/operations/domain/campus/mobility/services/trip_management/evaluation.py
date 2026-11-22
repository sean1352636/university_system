"""Trip evaluations: participants who went and the trip's leaders rate it
(1-5) and say what went well and what to improve, once each.

:func:`results` is for the trip's organisers; participants' comments are
shown without their names. :func:`request_evaluations` e-mails everyone who
can give one (sent when the trip is completed; each person once).
"""

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import (
    get_text, logging, datetime,
)

logger = logging.getLogger(__name__)

# Trips that can be evaluated.
_EVALUABLE = ('in_progress', 'completed', 'archived')


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _is_leader(c, trip, who):
    if who['user_id'] is None:
        return False
    if trip.get('created_by') == who['user_id']:
        return True
    return c.execute("SELECT 1 FROM trip_staff WHERE trip_id = ? AND staff_user_id = ?",
                     (trip['id'], who['user_id'])).fetchone() is not None


def _attended(c, trip_id, who):
    """True when the signed-in user was on the trip (attended, or ticked
    present on a roll call)."""
    row = c.execute(
        "SELECT id, status FROM trip_participants WHERE trip_id = ? AND "
        "((user_id IS NOT NULL AND user_id = ?) OR (student_id IS NOT NULL AND student_id = ?)) "
        "ORDER BY id DESC LIMIT 1", (trip_id, who['user_id'], who['student_id'])).fetchone()
    if not row:
        return False
    if row[1] == 'attended':
        return True
    if row[1] not in ('registered', 'confirmed'):
        return False
    return c.execute(
        "SELECT 1 FROM trip_rollcall_entries e JOIN trip_rollcalls r ON r.id = e.rollcall_id "
        "WHERE r.trip_id = ? AND e.participant_id = ? AND e.present = 1 LIMIT 1",
        (trip_id, row[0])).fetchone() is not None


def submit_evaluation(auth, trip_id, rating, went_well="", improve=""):
    """Record the signed-in user's evaluation of a trip they went on (or
    led). Once per person. Returns the evaluation id."""
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise ValueError("rating must be a whole number from 1 to 5") from None
    if not 1 <= rating <= 5:
        raise ValueError("rating must be from 1 to 5")
    who = _trips().actor(auth)
    with _db().write_transaction() as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        if trip['status'] not in _EVALUABLE:
            raise ValueError(get_text("mobility.trip_management.evaluation.not_yet",
                                      "A trip can be evaluated once it has run."))
        if _is_leader(c, trip, who):
            role = 'leader'
        elif _attended(c, trip_id, who):
            role = 'participant'
        else:
            raise PermissionError(get_text("mobility.trip_management.evaluation.not_on_trip",
                                           "Only people who went on the trip can evaluate it."))
        if c.execute("SELECT 1 FROM trip_evaluations WHERE trip_id = ? AND respondent = ?",
                     (trip_id, who['username'])).fetchone():
            raise ValueError(get_text("mobility.trip_management.evaluation.already",
                                      "You have already evaluated this trip."))
        return c.execute(
            "INSERT INTO trip_evaluations (trip_id, respondent, role, rating, went_well, improve, "
            "submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trip_id, who['username'], role, rating, str(went_well or '').strip() or None,
             str(improve or '').strip() or None, _now())).lastrowid


def results(auth, trip_id):
    """``{'responses', 'average', 'by_role': {role: {count, average}},
    'distribution': {1..5: n}, 'comments': [...]}`` for the trip's organisers
    (or ``view_trip_reports``). Participants' comments carry no name."""
    who = _trips().actor(auth)
    with _db().read_connection() as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        if not (_trips().can_manage_trip(auth, trip, conn=c, who=who)
                or auth.check_permission('view_trip_reports')):
            raise PermissionError(get_text("mobility.trip_management.evaluation.results_not_allowed",
                                           "Evaluation results are for the trip's organisers."))
        rows = [dict(zip(('respondent', 'role', 'rating', 'went_well', 'improve', 'submitted_at'),
                         tuple(r))) for r in c.execute(
            "SELECT respondent, role, rating, went_well, improve, submitted_at FROM trip_evaluations "
            "WHERE trip_id = ? ORDER BY submitted_at, id", (trip_id,)).fetchall()]
    by_role = {}
    for row in rows:
        entry = by_role.setdefault(row['role'] or 'participant', {'count': 0, 'total': 0})
        entry['count'] += 1
        entry['total'] += row['rating'] or 0
    comments = [{'role': r['role'], 'rating': r['rating'], 'went_well': r['went_well'],
                 'improve': r['improve'],
                 'respondent': r['respondent'] if r['role'] == 'leader' else None}
                for r in rows if r['went_well'] or r['improve']]
    return {
        'trip_id': trip_id, 'responses': len(rows),
        'average': round(sum(r['rating'] for r in rows) / len(rows), 2) if rows else None,
        'by_role': {k: {'count': v['count'], 'average': round(v['total'] / v['count'], 2)}
                    for k, v in by_role.items()},
        'distribution': {n: sum(1 for r in rows if r['rating'] == n) for n in range(1, 6)},
        'comments': comments,
    }


def request_evaluations(trip_id):
    """E-mail the trip's participants (those who went, or everyone still
    holding a place when nobody was marked) and its leaders, asking for an
    evaluation. Each person is asked once. Returns the number e-mailed."""
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import comms
    with _db().read_connection() as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        people = comms.participant_contacts(c, trip_id, ('attended',))
        if not people:
            people = comms.participant_contacts(c, trip_id, ('registered', 'confirmed'))
        recipients = [(f"participant:{p['id']}", p['email'], p['name']) for p in people]
        for r in c.execute(
                "SELECT u.id, u.email, COALESCE(NULLIF(TRIM(COALESCE(u.first_name, '') || ' ' || "
                "COALESCE(u.last_name, '')), ''), u.username) FROM users u WHERE u.id = ? "
                "OR u.id IN (SELECT staff_user_id FROM trip_staff WHERE trip_id = ?)",
                (trip.get('created_by'), trip_id)).fetchall():
            recipients.append((f"leader:{r[0]}", r[1], r[2]))
    subject = get_text("mobility.trip_management.evaluation.request_subject",
                       "How was {trip_name}?").format(trip_name=trip['trip_name'])
    body = get_text(
        "mobility.trip_management.evaluation.request_body",
        "Dear {name},\n\nThank you for taking part in {trip_name} ({start_date}). Please tell us "
        "how it went: sign in, open Trip Management, choose the trip (trip {trip_id}) and select "
        "'Evaluate trip'. Rate it from 1 to 5 and say what went well and what we could improve. "
        "Participants' comments are shared with the organisers without your name.",
    )
    sent = 0
    for key, email, name in recipients:
        sent += comms.send(email, subject, body.format(
            name=name or '', trip_name=trip['trip_name'], start_date=trip['start_date'],
            trip_id=trip_id), trip_id=trip_id, ref=f"trip:{trip_id}:evaluation:{key}")
    return sent
