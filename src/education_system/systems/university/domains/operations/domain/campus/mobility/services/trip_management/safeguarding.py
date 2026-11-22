"""Trip safeguarding: staffing ratios, first aid, DBS, ages and consents.

:func:`staffing_check` is one of the gates on opening a trip
(``approvals.gate_problems``). Its sources:

* staff on the trip — ``trip_staff``;
* first aid — ``trip_staff.first_aider``, or a current certificate in the
  First Aid register (``first_aiders``, by username) or the staff
  certification register (``staff_certifications``, the register
  ``trip_bus`` checks through ``cert_bus``);
* DBS — Staff HR keeps DBS certificates as staff documents
  (``documents`` rows with ``document_type = 'dbs_check'``,
  ``source_type = owner_type = 'staff'``); a 'dbs' kind in
  ``staff_certifications`` counts too. A certificate is valid for the trip
  when it is active and either its expiry date is on or after the trip's
  end, or — DBS certificates carry no expiry — it was issued within
  :data:`DBS_RENEWAL_YEARS` years of the trip's start.

Ages come from ``students.dob``: anyone under 18 on the trip's start date
needs parental consent, and registering one marks the trip
``involves_minors``.
"""
import math

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import logging, datetime

logger = logging.getLogger(__name__)

# University policy: a DBS certificate older than this needs renewing.
DBS_RENEWAL_YEARS = 3
ADULT_AGE = 18
# Trips with an overnight stay or abroad need at least this many staff.
MIN_STAFF_RESIDENTIAL = 2


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _date(value):
    """A ``date`` from 'YYYY-MM-DD…' or 'DD/MM/YYYY', else ``None``."""
    if not value:
        return None
    text = str(value).strip()
    for fmt, size in (('%Y-%m-%d', 10), ('%d/%m/%Y', 10), ('%d-%m-%Y', 10)):
        try:
            return datetime.strptime(text[:size], fmt).date()
        except ValueError:
            continue
    return None


def _has_table(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def _columns(conn, table):
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def is_residential(trip):
    """Overnight or overseas: needs at least two staff."""
    start, end = _date(trip.get('start_date')), _date(trip.get('end_date'))
    return (trip.get('trip_type') in ('residential', 'overseas')
            or int(trip.get('is_overseas') or 0) == 1
            or bool(start and end and end > start))


# ---------------------------------------------------------------------------
# Staff checks
# ---------------------------------------------------------------------------

def _staff_rows(conn, trip_id):
    cur = conn.execute(
        "SELECT ts.id, ts.staff_user_id, ts.role, ts.first_aider, ts.dbs_status, "
        "ts.dbs_checked_at, u.username, u.first_name, u.last_name "
        "FROM trip_staff ts LEFT JOIN users u ON u.id = ts.staff_user_id "
        "WHERE ts.trip_id = ? ORDER BY ts.id", (trip_id,))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _staff_name(row):
    name = " ".join(p for p in (row.get('first_name'), row.get('last_name')) if p).strip()
    return name or row.get('username') or f"user {row.get('staff_user_id')}"


def _staff_keys(row):
    """Ids a staff member may be filed under in HR registers: users.id and username."""
    return [k for k in (str(row.get('staff_user_id') or ''), row.get('username') or '') if k]


def has_first_aid(conn, row, on_date):
    """True when the staff member is flagged a first aider or holds a current certificate."""
    if int(row.get('first_aider') or 0):
        return True
    keys = _staff_keys(row)
    if not keys:
        return False
    marks = ", ".join('?' * len(keys))
    if _has_table(conn, 'first_aiders') and row.get('username'):
        if conn.execute("SELECT 1 FROM first_aiders WHERE LOWER(username) = LOWER(?) "
                        "AND status = 'active' AND expires_on >= ?",
                        (row['username'], on_date)).fetchone():
            return True
    if _has_table(conn, 'staff_certifications'):
        if conn.execute(
                f"SELECT 1 FROM staff_certifications WHERE staff_id IN ({marks}) "
                "AND COALESCE(is_active, 1) = 1 AND LOWER(kind) LIKE '%first%aid%' "
                "AND (expires_on IS NULL OR expires_on = '' OR expires_on >= ?)",
                (*keys, on_date)).fetchone():
            return True
    return False


def dbs_status(conn, row, trip):
    """``('valid' | 'expired' | 'missing', evidence date or None)`` for a staff member.

    See the module docstring for the rule. Fails closed: no register, or no
    certificate on file, is 'missing'.
    """
    start = _date(trip.get('start_date'))
    end = _date(trip.get('end_date')) or start
    keys = _staff_keys(row)
    found = []
    if keys and _has_table(conn, 'documents'):
        marks = ", ".join('?' * len(keys))
        cols = _columns(conn, 'documents')
        current_only = " AND COALESCE(is_current_version, 1) = 1" if 'is_current_version' in cols else ""
        found += conn.execute(
            "SELECT issue_date, expiry_date, upload_date, status, verification_status "
            f"FROM documents WHERE document_type = 'dbs_check' AND source_type = 'staff' "
            f"AND owner_id IN ({marks}){current_only}", keys).fetchall()
    if keys and _has_table(conn, 'staff_certifications'):
        marks = ", ".join('?' * len(keys))
        found += [(r[0], r[1], None, 'active' if r[2] in (None, 1) else 'inactive', None)
                  for r in conn.execute(
                      f"SELECT issued_on, expires_on, is_active FROM staff_certifications "
                      f"WHERE staff_id IN ({marks}) AND LOWER(kind) LIKE '%dbs%'", keys).fetchall()]
    if not found:
        return 'missing', None
    best = None
    for issue, expiry, uploaded, status, verification in found:
        if str(status or 'active').lower() not in ('active', 'valid', 'current'):
            continue
        if str(verification or '').lower() in ('rejected', 'failed', 'invalid'):
            continue
        issued = _date(issue) or _date(uploaded)
        expires = _date(expiry)
        if expires:
            ok = end is not None and expires >= end
        else:
            ok = bool(issued and start and (start - issued).days <= DBS_RENEWAL_YEARS * 365)
        if ok:
            return 'valid', (issued or expires).isoformat()
        best = best or (issued or expires)
    return 'expired', best.isoformat() if best else None


def staffing_check(trip_id, conn=None, record=False):
    """Problems with the trip's staffing (an empty list means it is fine).

    * enough staff for the participants: ``ceil(participants /
      min_staff_ratio)``, at least one, and at least two for residential or
      overseas trips;
    * a first aider when ``requires_first_aider``;
    * a valid DBS for every staff member when the trip involves minors or
      vulnerable adults.

    With ``record`` on a write connection, each staff member's DBS finding
    is mirrored onto ``trip_staff.dbs_status`` / ``dbs_checked_at`` and a
    certificated first aider is flagged ``first_aider``.
    """
    problems = []
    statuses = _db().ACTIVE_PARTICIPANT_STATUSES
    with _db().read_connection(conn) as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            return ["trip not found"]
        participants = c.execute(
            f"SELECT COUNT(*) FROM trip_participants WHERE trip_id = ? "
            f"AND status IN ({', '.join('?' * len(statuses))})", (trip_id, *statuses)).fetchone()[0]
        staff = _staff_rows(c, trip_id)
        ratio = max(int(trip.get('min_staff_ratio') or 10), 1)
        needed = max(math.ceil(participants / ratio), 1)
        if is_residential(trip):
            needed = max(needed, MIN_STAFF_RESIDENTIAL)
        if len(staff) < needed:
            why = (f"{participants} participant(s) at 1 staff per {ratio}"
                   + (", minimum 2 for a residential / overseas trip" if is_residential(trip) else ""))
            problems.append(f"{len(staff)} staff assigned but {needed} needed ({why})")
        on_date = trip.get('end_date') or trip.get('start_date')
        if int(trip.get('requires_first_aider') if trip.get('requires_first_aider') is not None else 1):
            aiders = [s for s in staff if has_first_aid(c, s, on_date)]
            if not aiders:
                problems.append("no qualified first aider among the trip staff")
            if record and conn is not None:
                for s in aiders:
                    if not int(s.get('first_aider') or 0):
                        c.execute("UPDATE trip_staff SET first_aider = 1 WHERE id = ?", (s['id'],))
        needs_dbs = int(trip.get('involves_minors') or 0) or int(trip.get('involves_vulnerable_adults') or 0)
        if needs_dbs or record:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for s in staff:
                status, _evidence = dbs_status(c, s, trip)
                if record and conn is not None:
                    c.execute("UPDATE trip_staff SET dbs_status = ?, dbs_checked_at = ? WHERE id = ?",
                              (status, now, s['id']))
                if needs_dbs and status != 'valid':
                    who = "minors" if int(trip.get('involves_minors') or 0) else "vulnerable adults"
                    problems.append(f"{_staff_name(s)} has no valid DBS check on file ({status}); "
                                    f"required because the trip involves {who}")
    return problems


def refresh_staff_checks(auth, trip_id, *, conn=None, pending=None):
    """Re-check every staff member's DBS / first aid and record it on ``trip_staff``.

    Returns the :func:`staffing_check` problems.
    """
    trips = _trips()
    who = trips._require(auth, 'manage_trips', 'create_trips')

    def work(c, p):
        trips._load_for_change(c, auth, trip_id, who)
        return staffing_check(trip_id, conn=c, record=True)
    return trips._in_transaction(conn, pending, work)


# ---------------------------------------------------------------------------
# Ages and consents
# ---------------------------------------------------------------------------

def _dob(conn, student_id):
    cols = _columns(conn, 'students')
    column = 'dob' if 'dob' in cols else ('date_of_birth' if 'date_of_birth' in cols else None)
    if not column or not student_id:
        return None
    row = conn.execute(f"SELECT {column} FROM students WHERE student_id = ?",
                       (str(student_id),)).fetchone()
    return _date(row[0]) if row else None


def _age_on(dob, on):
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def age_check(student_id, on_date=None, conn=None):
    """``{'student_id', 'dob', 'age', 'minor', 'parental_consent_required'}``.

    ``on_date`` (default today) is usually the trip's start date. With no
    date of birth on record ``minor`` is ``None`` (unknown).
    """
    on = _date(on_date) or datetime.now().date()
    with _db().read_connection(conn) as c:
        dob = _dob(c, student_id)
    if not dob:
        return {'student_id': student_id, 'dob': None, 'age': None, 'minor': None,
                'parental_consent_required': False}
    age = _age_on(dob, on)
    return {'student_id': student_id, 'dob': dob.isoformat(), 'age': age,
            'minor': age < ADULT_AGE, 'parental_consent_required': age < ADULT_AGE}


def note_participant_age(conn, trip_id, student_id):
    """On the caller's transaction: mark the trip ``involves_minors`` for a minor.

    Called by registration. Returns True when the participant is under 18
    on the trip's start date.
    """
    trip = _trips().get_trip(trip_id, conn=conn)
    if not trip or not student_id:
        return False
    result = age_check(student_id, trip.get('start_date'), conn=conn)
    if not result['minor']:
        return False
    if not int(trip.get('involves_minors') or 0):
        conn.execute("UPDATE trips SET involves_minors = 1 WHERE id = ?", (trip_id,))
        _trips().record_history(conn, trip_id, version=trip.get('version'), changed_by='system',
                                action='updated', field='involves_minors', old_value=0, new_value=1)
    return True


def _participant(c, participant_id):
    cur = c.execute("SELECT * FROM trip_participants WHERE id = ?", (participant_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("participant not found")
    return dict(zip([d[0] for d in cur.description], row))


def _is_own(who, place):
    return ((who['user_id'] is not None and place.get('user_id') == who['user_id'])
            or (who['student_id'] and place.get('student_id') == who['student_id']))


def _may_manage_people(auth, trip, c, who):
    return (auth.check_permission('manage_trip_participants')
            or _trips().can_manage_trip(auth, trip, conn=c, who=who))


def record_conduct_acceptance(auth, participant_id, *, conn=None, pending=None):
    """Record that the participant accepted the trip code of conduct.

    The participant accepts their own; an organiser may record a signed
    paper copy for them. Returns the timestamp.
    """
    trips = _trips()
    who = trips.actor(auth)

    def work(c, p):
        place = _participant(c, participant_id)
        trip = trips.get_trip(place['trip_id'], conn=c)
        if not (_is_own(who, place) or _may_manage_people(auth, trip, c, who)):
            raise PermissionError("only the participant or the trip's organisers can do that")
        now = trips._now()
        c.execute("UPDATE trip_participants SET conduct_accepted_at = ? WHERE id = ?",
                  (now, participant_id))
        trips.record_history(c, trip['id'], version=trip.get('version'), changed_by=who['username'],
                             action='conduct_accepted', field='participant',
                             new_value=str(participant_id))
        return now
    return trips._in_transaction(conn, pending, work)


def record_parental_consent(auth, participant_id, consenting_adult_name, *, conn=None, pending=None):
    """Record the parent / guardian consent received for a participant under 18.

    Organisers only (a minor cannot consent for themselves). Refused for a
    participant known to be an adult on the trip's start date. Returns the
    timestamp.
    """
    trips = _trips()
    who = trips.actor(auth)
    name = (consenting_adult_name or '').strip()
    if len(name) < 2:
        raise ValueError("enter the name of the parent or guardian who consented")

    def work(c, p):
        place = _participant(c, participant_id)
        trip = trips.get_trip(place['trip_id'], conn=c)
        if not _may_manage_people(auth, trip, c, who):
            raise PermissionError("only the trip's organisers can record parental consent")
        if place.get('student_id'):
            age = age_check(place['student_id'], trip.get('start_date'), conn=c)
            if age['minor'] is False:
                raise ValueError("this participant is 18 or over on the trip date; "
                                 "parental consent does not apply")
        now = trips._now()
        c.execute("UPDATE trip_participants SET parental_consent_by = ?, parental_consent_at = ? "
                  "WHERE id = ?", (name, now, participant_id))
        trips.record_history(c, trip['id'], version=trip.get('version'), changed_by=who['username'],
                             action='parental_consent', field='participant',
                             new_value=f"{participant_id}: {name}")
        return now
    return trips._in_transaction(conn, pending, work)


def participant_checks(trip_id, conn=None):
    """Per-participant safeguarding gaps: ``[{participant_id, student_id, problems}]``.

    Minors without parental consent and anyone yet to accept the code of
    conduct. For organisers' lists; not a gate on opening (people register
    after a trip opens).
    """
    statuses = _db().ACTIVE_PARTICIPANT_STATUSES
    out = []
    with _db().read_connection(conn) as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            return out
        cur = c.execute(
            "SELECT id, student_id, conduct_accepted_at, parental_consent_at FROM trip_participants "
            f"WHERE trip_id = ? AND status IN ({', '.join('?' * len(statuses))}) ORDER BY id",
            (trip_id, *statuses))
        for pid, sid, conduct, consent in cur.fetchall():
            problems = []
            if not conduct:
                problems.append("code of conduct not accepted")
            if sid:
                age = age_check(sid, trip.get('start_date'), conn=c)
                if age['minor'] and not consent:
                    problems.append(f"under 18 ({age['age']}) with no parental consent")
                elif age['minor'] is None:
                    problems.append("no date of birth on record")
            if problems:
                out.append({'participant_id': pid, 'student_id': sid, 'problems': problems})
    return out
