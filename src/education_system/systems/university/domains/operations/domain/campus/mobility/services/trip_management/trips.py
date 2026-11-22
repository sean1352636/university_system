from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import _common
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import sqlite3, get_text, logging, datetime, log_create, log_read, log_update, log_delete
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.calendar_integration import (
    sync_trip_calendar_event,
    remove_trip_calendar_event,
)
logger = logging.getLogger(__name__)


def _run_db_operation(operation):
    from education_system.systems.university.domains.operations.domain.campus.mobility.services import trip_management as _tm
    return _tm.safe_db_operation(operation)


# ---------------------------------------------------------------------------
# Domain API
#
# Every function below takes ``auth`` (an object with ``current_user`` and
# ``check_permission``) first, checks permission itself, raises
# PermissionError / ValueError (never prints, never prompts), opens its own
# short write transaction unless ``conn=`` is given, and publishes events
# only after the commit. With ``conn=`` the caller owns the commit and passes
# ``pending=`` (a list) to receive the post-commit actions; it runs them with
# ``database.run_after_commit(pending)`` once committed.
# ---------------------------------------------------------------------------

DATE_FORMAT = '%Y-%m-%d'

# Fields a create / update may set. Status, source, version and the
# approval / overseas / archive / retention columns have their own writers.
EDITABLE_FIELDS = (
    'trip_name', 'description', 'destination', 'start_date', 'end_date',
    'max_participants', 'cost', 'trip_type', 'organising_club', 'module_code',
    'country', 'is_overseas', 'high_risk', 'involves_minors',
    'involves_vulnerable_adults', 'min_staff_ratio', 'requires_first_aider',
    'emergency_contact_24h', 'budget', 'deposit_amount', 'deposit_due',
    'balance_due', 'refund_policy', 'hardship_eligible', 'counts_as_attendance',
)
_FLAG_FIELDS = ('is_overseas', 'high_risk', 'involves_minors', 'involves_vulnerable_adults',
                'requires_first_aider', 'hardship_eligible', 'counts_as_attendance')
_MONEY_FIELDS = ('cost', 'budget', 'deposit_amount')
_DATE_FIELDS = ('start_date', 'end_date', 'deposit_due', 'balance_due')

# Allowed status moves — the shape of the life cycle: proposed -> approved
# -> open. set_trip_status adds the gates on top (see approvals.gate_problems:
# 'approved' needs every approval stage, 'open' also needs a signed-off risk
# assessment, the staffing checks and, overseas, the overseas checks).
# approvals.decide moves a trip to 'approved' itself once the last stage is
# approved. 'archived' is reached through archive_trip.
TRIP_STATUS_TRANSITIONS = {
    'proposed': ('planning', 'approved', 'cancelled', 'archived'),
    'planning': ('proposed', 'approved', 'cancelled', 'archived'),
    'approved': ('proposed', 'open', 'cancelled', 'archived'),
    'open': ('full', 'closed', 'in_progress', 'cancelled'),
    'full': ('open', 'closed', 'in_progress', 'cancelled'),
    'closed': ('open', 'in_progress', 'cancelled'),
    'in_progress': ('completed', 'cancelled'),
    'completed': ('archived',),
    'cancelled': ('archived',),
    'archived': (),
}
# Statuses that keep the trip on the academic calendar.
_OFF_CALENDAR = ('cancelled', 'archived')
# Trips that can still change (archived / completed ones are history).
_LOCKED_STATUSES = ('completed', 'archived')


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def leader_emails(conn, trip):
    """E-mail addresses of the trip's creator and its leaders (coordinator / supervisor)."""
    rows = conn.execute(
        "SELECT u.email FROM users u WHERE u.id = ? OR u.id IN ("
        "  SELECT staff_user_id FROM trip_staff WHERE trip_id = ? "
        "  AND role IN ('coordinator', 'supervisor'))",
        (trip.get('created_by'), trip['id'])).fetchall()
    return sorted({r[0] for r in rows if r[0]})


def user_email(conn, username):
    """``users.email`` for a username, or ``None``."""
    if not username:
        return None
    row = conn.execute("SELECT email FROM users WHERE username = ? COLLATE NOCASE",
                       (str(username),)).fetchone()
    return row[0] if row and row[0] else None


def queue_email(pending, recipients, subject, body, *, category='trips'):
    """Queue one outbox e-mail per recipient, sent once the write commits."""
    recipients = sorted({r for r in (recipients or ()) if r and '@' in str(r)})
    if not recipients:
        return

    def _send():
        from education_system.systems.university.infrastructure.email.email_service import send_email
        for address in recipients:
            try:
                send_email(address, subject, body, kind="transactional", category=category)
            except Exception:
                logger.warning("trip e-mail %r to %s failed", subject, address, exc_info=True)
    pending.append(_send)


def _publish_after(pending, event, **payload):
    """Queue a trip-bus event to go out once the write commits."""
    def _send():
        from education_system.systems.university.services.bus import trip_bus
        trip_bus.publish_trip_event(event, **payload)
    pending.append(_send)


def actor(auth):
    """Who is acting: ``{'username', 'role', 'user_id', 'student_id'}``.

    ``user_id`` / ``student_id`` are the university database's ids, resolved
    by username — the auth.db id in ``current_user['id']`` is a different id
    space and is never written to a trips table.
    """
    user = getattr(auth, 'current_user', None) if auth else None
    if not user:
        raise PermissionError(get_text("mobility.trip_management.auth.must_login_access",
                                       "You must be logged in to access trip management."))
    username = user.get('username')
    user_id = student_id = None
    if username:
        from education_system.systems.university.infrastructure.auth.session_user import resolve_local_identity
        user_id, student_id = resolve_local_identity(username)
    return {
        'username': username or str(user.get('id') or ''),
        'role': str(user.get('role') or '').lower(),
        'user_id': user_id,
        'student_id': student_id or user.get('student_id'),
    }


def _require(auth, *permissions):
    """Raise PermissionError unless ``auth`` holds one of ``permissions``."""
    who = actor(auth)
    if not any(auth.check_permission(p) for p in permissions):
        raise PermissionError(get_text(
            "mobility.trip_management.auth.no_permission",
            "You don't have permission to do that ({permission}).",
        ).format(permission=" / ".join(permissions)))
    return who


def _as_dict(row):
    if row is None:
        return None
    try:
        return dict(row)
    except (TypeError, ValueError):
        return row


def get_trip(trip_id, conn=None):
    """The trip as a dict (every column), or ``None``."""
    with _db().read_connection(conn) as c:
        c_row = c.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
        row = c_row.fetchone()
        if row is None:
            return None
        names = [d[0] for d in c_row.description]
        return dict(zip(names, row))


def active_participant_count(conn, trip_id):
    """Places taken on the trip (statuses that hold a place)."""
    statuses = _db().ACTIVE_PARTICIPANT_STATUSES
    row = conn.execute(
        f"SELECT COUNT(*) FROM trip_participants WHERE trip_id = ? "
        f"AND status IN ({', '.join('?' * len(statuses))})",
        (trip_id, *statuses)).fetchone()
    return row[0] if row else 0


def refresh_capacity_status(conn, trip, who):
    """Move an 'open' trip to 'full' when every place is taken, and back.

    Runs on the caller's transaction after a place is taken or freed, or the
    capacity changes. Returns the new status, or ``None`` when unchanged.
    """
    taken = active_participant_count(conn, trip['id'])
    capacity = trip['max_participants'] or 0
    new = None
    if trip['status'] == 'open' and taken >= capacity:
        new = 'full'
    elif trip['status'] == 'full' and taken < capacity:
        new = 'open'
    if new:
        version = int(trip.get('version') or 1) + 1
        conn.execute("UPDATE trips SET status = ?, version = ?, updated_by = ?, updated_at = ? "
                     "WHERE id = ?", (new, version, who['username'], _now(), trip['id']))
        record_history(conn, trip['id'], version=version, changed_by=who['username'],
                       action='status', field='status', old_value=trip['status'], new_value=new)
    return new


def list_trips(source=None, club=None, open_only=False, include_archived=False, conn=None):
    """Trips with their place count, soonest first.

    ``source`` is 'operations' or 'su'; ``club`` matches ``organising_club``;
    ``open_only`` keeps trips taking registrations ('open'). Archived trips
    are left out unless ``include_archived``.
    """
    statuses = _db().ACTIVE_PARTICIPANT_STATUSES
    sql = ("SELECT t.*, (SELECT COUNT(*) FROM trip_participants p WHERE p.trip_id = t.id "
           f"AND p.status IN ({', '.join('?' * len(statuses))})) AS current_participants "
           "FROM trips t WHERE 1 = 1")
    params = list(statuses)
    if source:
        sql += " AND COALESCE(t.source, 'operations') = ?"
        params.append(source)
    if club:
        sql += " AND t.organising_club = ?"
        params.append(club)
    if open_only:
        sql += " AND t.status = 'open'"
    if not include_archived:
        sql += " AND t.status <> 'archived'"
    sql += " ORDER BY t.start_date ASC, t.id ASC"
    with _db().read_connection(conn) as c:
        cur = c.execute(sql, params)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def can_manage_trip(auth, trip, conn=None, who=None):
    """True for ``manage_trips`` holders, the trip's creator and its leaders.

    ``trip`` is a trip id or a trip dict. Leaders are ``trip_staff`` rows
    with role coordinator or supervisor. Pass ``who`` (from :func:`actor`)
    when calling inside a write transaction, so no second connection opens.
    """
    if not auth or not getattr(auth, 'current_user', None):
        return False
    if auth.check_permission('manage_trips'):
        return True
    who = who or actor(auth)
    if who['user_id'] is None:
        return False
    if not isinstance(trip, dict):
        trip = get_trip(trip, conn=conn)
    if not trip:
        return False
    if trip.get('created_by') == who['user_id']:
        return True
    with _db().read_connection(conn) as c:
        row = c.execute(
            "SELECT 1 FROM trip_staff WHERE trip_id = ? AND staff_user_id = ? "
            "AND role IN ('coordinator', 'supervisor')",
            (trip['id'], who['user_id'])).fetchone()
    return row is not None


def _parse_date(name, value):
    try:
        return datetime.strptime(str(value).strip()[:10], DATE_FORMAT).strftime(DATE_FORMAT)
    except (TypeError, ValueError):
        raise ValueError(get_text("mobility.trip_management.validation.invalid_date_field",
                                  "{field}: use YYYY-MM-DD.").format(field=name)) from None


def clean_trip_fields(fields, current=None):
    """Validate and normalise trip fields. Raises ValueError.

    ``current`` is the stored trip for an update, so cross-field rules
    (end date after start date) see the merged result.
    """
    import json

    unknown = set(fields) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"unknown trip field(s): {', '.join(sorted(unknown))}")
    out = {}
    for name, value in fields.items():
        if isinstance(value, str):
            value = value.strip()
        if name in _DATE_FIELDS:
            out[name] = _parse_date(name, value) if value not in (None, '') else None
        elif name in _FLAG_FIELDS:
            out[name] = 1 if value in (True, 1, '1', 'true', 'yes', 'y') else 0
        elif name in _MONEY_FIELDS:
            if value in (None, ''):
                out[name] = None if name == 'budget' else 0.0
                continue
            try:
                out[name] = round(float(value), 2)
            except (TypeError, ValueError):
                raise ValueError(f"{name}: enter an amount") from None
            if out[name] < 0:
                raise ValueError(get_text("mobility.trip_management.validation.cost_non_negative",
                                          "Cost cannot be negative."))
        elif name in ('max_participants', 'min_staff_ratio'):
            try:
                out[name] = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"{name}: enter a whole number") from None
            if out[name] <= 0:
                raise ValueError(get_text("mobility.trip_management.validation.max_participants_positive",
                                          "Maximum participants must be greater than 0."))
        elif name == 'trip_type':
            value = value or 'day'
            if value not in _db().TRIP_TYPES:
                raise ValueError(f"trip_type must be one of {', '.join(_db().TRIP_TYPES)}")
            out[name] = value
        elif name == 'refund_policy':
            if value in (None, '', []):
                out[name] = None
                continue
            tiers = json.loads(value) if isinstance(value, str) else value
            if not isinstance(tiers, list) or not all(
                    isinstance(t, dict) and {'days_before', 'percent'} <= set(t) for t in tiers):
                raise ValueError("refund_policy must be a list of {days_before, percent}")
            for t in tiers:
                if not 0 <= float(t['percent']) <= 100 or int(t['days_before']) < 0:
                    raise ValueError("refund_policy: percent 0-100, days_before 0 or more")
            out[name] = json.dumps([{'days_before': int(t['days_before']),
                                     'percent': float(t['percent'])} for t in tiers])
        else:
            out[name] = value if value != '' else None

    merged = dict(current or {})
    merged.update(out)
    if 'trip_name' in out or current is None:
        if len(merged.get('trip_name') or '') < 3:
            raise ValueError(get_text("mobility.trip_management.validation.trip_name_min_length",
                                      "Trip name must be at least 3 characters long."))
    if 'destination' in out or current is None:
        if len(merged.get('destination') or '') < 3:
            raise ValueError(get_text("mobility.trip_management.validation.destination_min_length",
                                      "Destination must be at least 3 characters long."))
    if current is None and not merged.get('start_date'):
        raise ValueError(get_text("mobility.trip_management.validation.invalid_date_format",
                                  "Invalid date format. Please use YYYY-MM-DD."))
    if 'end_date' in out and not out['end_date']:
        out['end_date'] = merged['end_date'] = merged.get('start_date')
    if current is None and not merged.get('end_date'):
        out['end_date'] = merged['end_date'] = merged['start_date']
    if merged.get('start_date') and merged.get('end_date') and merged['end_date'] < merged['start_date']:
        raise ValueError(get_text("mobility.trip_management.validation.end_date_after_start",
                                  "End date must be after start date."))
    if out.get('trip_type') == 'overseas':
        out['is_overseas'] = 1
    return out


def record_history(conn, trip_id, *, version, changed_by, action, field=None,
                   old_value=None, new_value=None):
    """Append one row to ``trip_history`` on the caller's transaction."""
    conn.execute(
        "INSERT INTO trip_history (trip_id, version, changed_by, changed_at, action, field, "
        "old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (trip_id, version, changed_by, _now(), action, field,
         None if old_value is None else str(old_value),
         None if new_value is None else str(new_value)))


_HISTORY_VIEW_PERMISSIONS = ('approve_trips_department', 'approve_trips_hs',
                             'approve_trips_finance', 'approve_trips_international')


def list_history(auth, trip_id, *, limit=None, conn=None):
    """A trip's change history, newest first: ``[{id, version, changed_by,
    changed_at, action, field, old_value, new_value}]``.

    For the people who run or sign off the trip: ``manage_trips`` holders,
    its creator and leaders (:func:`can_manage_trip`) and the approvers.
    """
    actor(auth)
    trip = get_trip(trip_id, conn=conn)
    if not trip:
        raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
    if not (can_manage_trip(auth, trip, conn=conn)
            or any(auth.check_permission(p) for p in _HISTORY_VIEW_PERMISSIONS)):
        raise PermissionError(get_text(
            "mobility.trip_management.history.no_permission",
            "Only the trip's organisers and approvers can see its history."))
    sql = ("SELECT id, version, changed_by, changed_at, action, field, old_value, new_value "
           "FROM trip_history WHERE trip_id = ? ORDER BY changed_at DESC, id DESC")
    params = [trip_id]
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    with _db().read_connection(conn) as c:
        cur = c.execute(sql, params)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def _sync_calendar(conn, trip, pending, changed_by=None):
    if trip['status'] in _OFF_CALENDAR:
        remove_trip_calendar_event(conn, trip['id'], pending=pending)
        return None
    return sync_trip_calendar_event(
        conn, trip['id'], trip_name=trip['trip_name'], destination=trip['destination'],
        start_date=trip['start_date'], end_date=trip['end_date'], cost=trip.get('cost'),
        created_by=changed_by, pending=pending)


def insert_trip(conn, fields, *, created_by=None, changed_by=None, status='proposed',
                source='operations', pending=None, event_payload=None, link_event_id=None):
    """Write a trip, its first history row and its calendar event on ``conn``.

    The low-level writer shared by :func:`create_trip_record` and system
    callers (``trip_bus``, the calendar's create-trip-from-event); it does no
    permission check. ``fields`` must already be cleaned. ``trip.created``
    is queued on ``pending`` (``event_payload`` adds to it). With
    ``link_event_id`` an existing calendar event (one the trip was created
    from) becomes the trip's event instead of a new one being written.
    Returns the trip dict (with ``calendar_event_id``).
    """
    if status not in _db().TRIP_STATUSES:
        raise ValueError(f"unknown trip status {status!r}")
    if source not in _db().TRIP_SOURCES:
        raise ValueError(f"unknown trip source {source!r}")
    now = _now()
    row = dict(fields)
    row.setdefault('max_participants', 50)
    row.setdefault('cost', 0.0)
    row.setdefault('trip_type', 'su_social' if source == 'su' else 'day')
    row.update(status=status, source=source, created_by=created_by, created_at=now,
               updated_at=now, version=1, updated_by=changed_by)
    names = list(row)
    cur = conn.execute(
        f"INSERT INTO trips ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
        [row[n] for n in names])
    trip_id = cur.lastrowid
    record_history(conn, trip_id, version=1, changed_by=changed_by, action='created',
                   new_value=status)
    if link_event_id:
        conn.execute("UPDATE unified_events SET trip_id = ? "
                     "WHERE source_type = 'academic_calendar' AND source_event_id = ?",
                     (trip_id, link_event_id))
    trip = get_trip(trip_id, conn=conn)
    trip['calendar_event_id'] = _sync_calendar(conn, trip, pending, changed_by)
    if pending is not None:
        _publish_after(pending, "trip.created", trip_id=trip_id, trip_name=trip['trip_name'],
                       destination=trip['destination'], start_date=trip['start_date'],
                       end_date=trip['end_date'], cost=trip['cost'],
                       max_participants=trip['max_participants'], source=source,
                       organising_club=trip.get('organising_club'),
                       **({'kind': "university"} | dict(event_payload or {})))
    return trip


def _in_transaction(conn, pending, work):
    """Run ``work(conn, pending)`` in the caller's or a fresh write transaction."""
    db = _db()
    if conn is not None:
        if pending is None:
            # Caller owns the commit but gave nowhere to queue events: they
            # go out now rather than being lost.
            local = []
            result = work(conn, local)
            db.run_after_commit(local)
            return result
        return work(conn, pending)
    local = []
    with db.write_transaction() as own:
        result = work(own, local)
    db.run_after_commit(local)
    return result


def create_trip_record(auth, *, conn=None, pending=None, **fields):
    """Create a trip (status 'proposed') and put it on the calendar.

    Needs ``create_trips`` or ``manage_trips``. Returns the trip dict.
    """
    who = _require(auth, 'create_trips', 'manage_trips')
    source = fields.pop('source', 'operations') or 'operations'
    cleaned = clean_trip_fields(fields)

    def work(c, p):
        return insert_trip(c, cleaned, created_by=who['user_id'], changed_by=who['username'],
                           source=source, pending=p)
    return _in_transaction(conn, pending, work)


def create_su_trip(auth, club, **fields):
    """Create a Students' Union trip for ``club`` (source 'su').

    Goes through :func:`create_trip_record`, so it starts 'proposed' and
    follows the same approval path. ``club`` is the club name (``None`` or
    '' for an individual organiser).
    """
    fields['organising_club'] = club or None
    fields.setdefault('trip_type', 'su_social')
    return create_trip_record(auth, source='su', **fields)


def _load_for_change(c, auth, trip_id, who):
    trip = get_trip(trip_id, conn=c)
    if not trip:
        raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
    if not can_manage_trip(auth, trip, conn=c, who=who):
        raise PermissionError(get_text("mobility.trip_management.update.not_found_or_no_permission",
                                       "Trip not found or you don't have permission to update it."))
    return trip


def update_trip_record(auth, trip_id, *, conn=None, pending=None, **fields):
    """Change trip fields; records history, bumps ``version``, re-syncs the calendar.

    Needs ``manage_trips``, or ``create_trips`` on a trip the user created or
    leads. Returns the updated trip dict (unchanged when nothing differs).
    """
    who = _require(auth, 'manage_trips', 'create_trips')

    def work(c, p):
        trip = _load_for_change(c, auth, trip_id, who)
        if trip['status'] in _LOCKED_STATUSES:
            raise ValueError(f"a {trip['status']} trip cannot be changed")
        cleaned = clean_trip_fields(fields, current=trip)
        changes = {k: v for k, v in cleaned.items() if trip.get(k) != v}
        if not changes:
            return trip
        if 'max_participants' in changes and changes['max_participants'] < active_participant_count(c, trip_id):
            raise ValueError("max_participants is below the number of places already taken")
        version = int(trip.get('version') or 1) + 1
        sets = ", ".join(f"{k} = ?" for k in changes)
        c.execute(f"UPDATE trips SET {sets}, version = ?, updated_by = ?, updated_at = ? WHERE id = ?",
                  [*changes.values(), version, who['username'], _now(), trip_id])
        for k, v in changes.items():
            record_history(c, trip_id, version=version, changed_by=who['username'],
                           action='updated', field=k, old_value=trip.get(k), new_value=v)
        updated = get_trip(trip_id, conn=c)
        if 'max_participants' in changes and refresh_capacity_status(c, updated, who):
            updated = get_trip(trip_id, conn=c)
        # Dates, destination, cost or overseas details changed: the approvals
        # given no longer cover this trip, so they start again.
        from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import approvals
        if set(changes) & set(approvals.MATERIAL_FIELDS):
            if approvals.reset_for_material_change(c, updated, who, sorted(changes), pending=p):
                updated = get_trip(trip_id, conn=c)
        _sync_calendar(c, updated, p, who['username'])
        _publish_after(p, "trip.updated", trip_id=trip_id, fields=sorted(changes), version=version)
        return updated
    return _in_transaction(conn, pending, work)


def set_trip_status(auth, trip_id, new_status, reason="", *, conn=None, pending=None):
    """Move a trip to ``new_status`` along :data:`TRIP_STATUS_TRANSITIONS`.

    'archived' goes through :func:`archive_trip`. Cancelling releases every
    current place and refunds what was paid (after the commit), then sends
    ``comms.cancellation_notice``; completing asks for evaluations
    (``evaluation.request_evaluations``). Moving to 'approved' or 'open' is
    gated by :func:`approvals.gate_problems` — a ValueError lists every
    problem. Needs the same rights as :func:`update_trip_record`. Returns
    ``{'trip', 'refunds'}``.
    """
    db = _db()
    new_status = db.LEGACY_TRIP_STATUSES.get(new_status, new_status)
    if new_status not in db.TRIP_STATUSES:
        raise ValueError(f"unknown trip status {new_status!r}")
    if new_status == 'archived':
        return archive_trip(auth, trip_id, reason=reason, conn=conn, pending=pending)
    who = _require(auth, 'manage_trips', 'create_trips')
    released = []

    def work(c, p):
        trip = _load_for_change(c, auth, trip_id, who)
        old = trip['status']
        if new_status == old:
            return trip
        if new_status not in TRIP_STATUS_TRANSITIONS.get(old, ()):
            raise ValueError(f"a trip cannot go from {old} to {new_status}")
        if new_status in ('approved', 'open'):
            from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import approvals
            problems = approvals.gate_problems(trip_id, new_status, conn=c, record=True)
            if problems:
                raise ValueError(get_text(
                    "mobility.trip_management.status.blocked",
                    "The trip cannot be {status} yet:").format(status=new_status)
                    + "\n- " + "\n- ".join(problems))
        version = int(trip.get('version') or 1) + 1
        c.execute("UPDATE trips SET status = ?, version = ?, updated_by = ?, updated_at = ? WHERE id = ?",
                  (new_status, version, who['username'], _now(), trip_id))
        record_history(c, trip_id, version=version, changed_by=who['username'], action='status',
                       field='status', old_value=old, new_value=new_status)
        if reason:
            record_history(c, trip_id, version=version, changed_by=who['username'],
                           action='status_reason', field='status', new_value=reason)
        if new_status == 'cancelled':
            released.extend(_release_places(c, trip_id, get_text(
                "mobility.trip_management.cancel.trip_cancelled_reason", "Trip cancelled")))
        updated = get_trip(trip_id, conn=c)
        _sync_calendar(c, updated, p, who['username'])
        _publish_after(p, "trip.status.changed", trip_id=trip_id, old_status=old,
                       new_status=new_status, reason=reason, version=version)
        if released:
            p.append(lambda: refunds.extend(_refund_released(released, updated, who['username'])))
        if new_status == 'cancelled':
            p.append(lambda: _after_cancelled(auth, trip_id, reason))
        elif new_status == 'completed':
            p.append(lambda: _after_completed(trip_id))
        return updated

    refunds = []
    trip = _in_transaction(conn, pending, work)
    return {'trip': trip, 'refunds': refunds}


def _after_cancelled(auth, trip_id, reason):
    """After commit: tell the participants (comms owns the notice)."""
    try:
        from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import comms
    except ImportError:
        logger.info("trip %s cancelled: comms is unavailable, no notice sent", trip_id)
        return
    comms.cancellation_notice(auth, trip_id, reason)


def _after_completed(trip_id):
    """After commit: ask participants and leaders to evaluate the trip."""
    try:
        from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import evaluation
    except ImportError:
        logger.info("trip %s completed: evaluation is unavailable, none requested", trip_id)
        return
    evaluation.request_evaluations(trip_id)


def archive_trip(auth, trip_id, reason="", *, conn=None, pending=None):
    """Archive a trip — this replaces deleting one.

    The trip, its participants, payments, expenses and history are kept;
    status becomes 'archived' with ``archived_at`` / ``archived_by``, the
    calendar event is removed, and if the trip had not run, every current
    place is released and paid participants are refunded through
    ``payments.refund_payment`` after the commit. Needs ``manage_trips`` or
    ``create_trips`` on the user's own trip. Everyone whose place was
    released is e-mailed after the commit (``comms.archive_notice``), whichever
    screen archived the trip. Returns ``{'trip', 'refunds', 'emailed'}``.
    """
    who = _require(auth, 'manage_trips', 'create_trips')
    released = []
    refunds = []
    emailed = []

    def work(c, p):
        trip = _load_for_change(c, auth, trip_id, who)
        old = trip['status']
        if old == 'archived':
            return trip
        if old in ('in_progress',):
            raise ValueError("a trip that is under way cannot be archived")
        version = int(trip.get('version') or 1) + 1
        now = _now()
        c.execute("UPDATE trips SET status = 'archived', archived_at = ?, archived_by = ?, "
                  "version = ?, updated_by = ?, updated_at = ? WHERE id = ?",
                  (now, who['username'], version, who['username'], now, trip_id))
        record_history(c, trip_id, version=version, changed_by=who['username'], action='archived',
                       field='status', old_value=old, new_value='archived')
        if reason:
            record_history(c, trip_id, version=version, changed_by=who['username'],
                           action='status_reason', field='status', new_value=reason)
        people = []
        if old != 'completed':
            from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import comms
            people = comms.participant_contacts(c, trip_id)
            released.extend(_release_places(c, trip_id, get_text(
                "mobility.trip_management.cancel.trip_archived_reason", "Trip archived")))
        updated = get_trip(trip_id, conn=c)
        remove_trip_calendar_event(c, trip_id, pending=p)
        _publish_after(p, "trip.status.changed", trip_id=trip_id, old_status=old,
                       new_status='archived', reason=reason, version=version)
        if released:
            p.append(lambda: refunds.extend(_refund_released(released, updated, who['username'])))
        if people:
            p.append(lambda: emailed.append(_archive_notice(updated, people, reason)))
        return updated

    trip = _in_transaction(conn, pending, work)
    return {'trip': trip, 'refunds': refunds, 'emailed': sum(emailed)}


def _archive_notice(trip, people, reason):
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import comms
    try:
        return comms.archive_notice(trip, people, reason)
    except Exception:
        logger.exception("archive notice for trip %s failed", trip.get('id'))
        return 0


def _release_places(conn, trip_id, reason):
    """Cancel every current place on a trip; return the rows that were paid for."""
    db = _db()
    statuses = db.CURRENT_PARTICIPANT_STATUSES
    cur = conn.execute(
        "SELECT * FROM trip_participants WHERE trip_id = ? "
        f"AND status IN ({', '.join('?' * len(statuses))})", (trip_id, *statuses))
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    if rows:
        conn.execute(
            "UPDATE trip_participants SET status = 'cancelled', cancellation_date = ?, "
            "cancellation_reason = ?, offer_expires_at = NULL, waitlist_position = NULL "
            f"WHERE trip_id = ? AND status IN ({', '.join('?' * len(statuses))})",
            (_now(), reason, trip_id, *statuses))
    return [r for r in rows if r.get('payment_status') in ('paid', 'partial')]


def _refund_released(rows, trip, processed_by):
    """Refund each released paid place (runs after commit). Returns outcomes."""
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import registrations
    return [registrations.refund_participant(row, trip, processed_by=processed_by) for row in rows]


# ---------------------------------------------------------------------------
# CLI
#
# Each command gathers its input first (reads on a short connection), then
# writes through the domain functions above in one short transaction.
# ---------------------------------------------------------------------------

def _cli_auth(must_login_key, must_login_default):
    auth = _common.get_auth()
    if not auth or not auth.current_user:
        print(get_text(must_login_key, must_login_default))
        return None
    return auth


def _active_status_sql():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.database import ACTIVE_PARTICIPANT_STATUSES
    return ", ".join(f"'{s}'" for s in ACTIVE_PARTICIPANT_STATUSES)


def view_trips_with_calendar():
    """View trips with calendar event information"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_view", "You must be logged in to view trips.")
    if not auth:
        return False

    if not auth.check_permission('view_trips'):
        print(get_text("mobility.trip_management.auth.no_permission_view", "You don't have permission to view trips."))
        return False

    def view_trips_calendar_operation(conn):
        cursor = conn.cursor()

        try:
            # Get trips with calendar event info
            cursor.execute(f'''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(DISTINCT tp.id) as current_participants,
                   e.title as calendar_event_name,
                   e.source_event_id as calendar_event_id
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status IN ({_active_status_sql()})
            LEFT JOIN unified_events e ON e.source_type = 'academic_calendar' AND e.trip_id = t.id
            WHERE t.status <> 'archived'
            GROUP BY t.id
            ORDER BY t.start_date ASC
            ''')

            trips = cursor.fetchall()

            if not trips:
                print(get_text("mobility.trip_management.trips.no_trips_found", "No trips found."))
                return True

            print("\n" + get_text("mobility.trip_management.trips.calendar_integration_title", "Trips with Calendar Integration"))
            print("=" * 130)
            print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<20} {get_text('mobility.trip_management.headers.destination', 'Destination'):<15} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.participants', 'Participants'):<12} {get_text('mobility.trip_management.headers.cost', 'Cost'):<10} {get_text('mobility.trip_management.headers.status', 'Status'):<10} {get_text('mobility.trip_management.headers.calendar_event', 'Calendar Event'):<20}")
            print("-" * 130)

            for trip in trips:
                trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, cal_event_name, cal_event_id = trip
                participants_info = f"{current_parts}/{max_parts}"
                calendar_info = cal_event_name[:19] if cal_event_name else get_text("mobility.trip_management.trips.no_event", "No Event")

                print(f"{trip_id:<5} {name[:19]:<20} {destination[:14]:<15} {start_date:<12} {participants_info:<12} £{cost or 0:<9.2f} {status.title():<10} {calendar_info:<20}")

            print("=" * 130)
            return True

        except sqlite3.Error as e:
            logging.error(get_text("mobility.trip_management.database.error_viewing_calendar", "Database error viewing trips with calendar: {error}").format(error=e))
            print(get_text("mobility.trip_management.errors.retrieving_trips", "Error retrieving trips from database."))
            return False

    return _run_db_operation(view_trips_calendar_operation)


def _prompt_new_trip():
    """Ask for a new trip's details. Returns the fields and the status chosen."""
    print("\n" + get_text("mobility.trip_management.create.title", "Create New Trip"))
    print("=" * 30)

    while True:
        trip_name = input(get_text("mobility.trip_management.create.trip_name_prompt", "Trip Name: ")).strip()
        if len(trip_name) >= 3:
            break
        print(get_text("mobility.trip_management.validation.trip_name_min_length", "Trip name must be at least 3 characters long."))

    description = input(get_text("mobility.trip_management.create.description_prompt", "Description (optional): ")).strip()

    # Single-day trips end on the day they start, so the end date is
    # derived rather than prompted for.
    print("\n" + get_text("mobility.trip_management.create.duration_label", "Trip Duration:"))
    print("1. " + get_text("mobility.trip_management.create.duration_single_day", "Single day trip"))
    print("2. " + get_text("mobility.trip_management.create.duration_multi_day", "Multiple day trip"))

    while True:
        duration_choice = input(get_text("mobility.trip_management.create.select_duration_prompt", "Select duration (1-2): ")).strip()
        if duration_choice in ('1', '2'):
            single_day = duration_choice == '1'
            break
        print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))

    start_prompt = (
        get_text("mobility.trip_management.create.trip_date_prompt", "Trip Date (YYYY-MM-DD): ")
        if single_day else
        get_text("mobility.trip_management.create.start_date_prompt", "Start Date (YYYY-MM-DD): ")
    )
    while True:
        start_date_str = input(start_prompt).strip()
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            break
        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_date_format", "Invalid date format. Please use YYYY-MM-DD."))

    while True:
        destination = input(get_text("mobility.trip_management.create.destination_prompt", "Destination: ")).strip()
        if len(destination) >= 3:
            break
        print(get_text("mobility.trip_management.validation.destination_min_length", "Destination must be at least 3 characters long."))

    end_date_str = start_date_str
    if not single_day:
        while True:
            end_date_str = input(get_text("mobility.trip_management.create.end_date_prompt", "End Date (YYYY-MM-DD): ")).strip()
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                if end_date.date() <= start_date.date():
                    print(get_text("mobility.trip_management.validation.end_date_after_start", "End date must be after start date."))
                    continue
                break
            except ValueError:
                print(get_text("mobility.trip_management.validation.invalid_date_format", "Invalid date format. Please use YYYY-MM-DD."))

    while True:
        try:
            max_participants = int(input(get_text("mobility.trip_management.create.max_participants_prompt", "Maximum Participants (default 50): ")) or "50")
            if max_participants > 0:
                break
            print(get_text("mobility.trip_management.validation.max_participants_positive", "Maximum participants must be greater than 0."))
        except ValueError:
            print(get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))

    while True:
        try:
            cost = float(input(get_text("mobility.trip_management.create.cost_prompt", "Cost per person (default 0.0): ")) or "0.0")
            if cost >= 0:
                break
            print(get_text("mobility.trip_management.validation.cost_non_negative", "Cost cannot be negative."))
        except ValueError:
            print(get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))

    # A new trip is proposed; opening it straight away goes through
    # set_trip_status and its approval gates.
    status_options = ['proposed', 'open']
    status = status_options[0]
    print("\n" + get_text("mobility.trip_management.create.trip_status_label", "Trip Status:"))
    for i, status_opt in enumerate(status_options, 1):
        print(f"{i}. {status_opt.title()}")
    while True:
        try:
            status_choice = int(input(get_text("mobility.trip_management.create.select_status_prompt", "Select status (1-2): "))) - 1
            if 0 <= status_choice < len(status_options):
                status = status_options[status_choice]
                break
            print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
        except ValueError:
            print(get_text("mobility.trip_management.validation.enter_number", "Please enter a number."))

    fields = {
        'trip_name': trip_name, 'description': description, 'destination': destination,
        'start_date': start_date_str, 'end_date': end_date_str,
        'max_participants': max_participants, 'cost': cost,
    }
    return fields, status, single_day


@log_create(module="trips", description="Creating new trip")
def create_trip():
    """Create a new trip with comprehensive validation"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_create", "You must be logged in to create trips.")
    if not auth:
        return False

    if not (auth.check_permission('create_trips') or auth.check_permission('manage_trips')):
        print(get_text("mobility.trip_management.auth.no_permission_create", "You don't have permission to create trips."))
        return False

    fields, status, single_day = _prompt_new_trip()

    try:
        trip = create_trip_record(auth, **fields)
        if status != trip['status']:
            try:
                trip = set_trip_status(auth, trip['id'], status)['trip']
            except ValueError as e:
                # The trip exists; it stays 'proposed' until it is approved.
                print(get_text("mobility.trip_management.create.kept_proposed",
                               "The trip was created as Proposed: {error}").format(error=e))
    except (ValueError, PermissionError) as e:
        print(get_text("mobility.trip_management.errors.creating_trip", "Could not create the trip: {error}").format(error=e))
        return False
    except sqlite3.Error as e:
        logger.error("create_trip failed: %s", e)
        print(get_text("mobility.trip_management.errors.creating_trip", "Could not create the trip: {error}").format(error=e))
        return False

    result = {
        'trip_id': trip['id'],
        'trip_name': trip['trip_name'],
        'destination': trip['destination'],
        'start_date': trip['start_date'],
        'end_date': trip['end_date'],
        'max_participants': trip['max_participants'],
        'cost': trip['cost'],
        'status': trip['status'],
        'single_day': single_day,
        'calendar_event_id': trip.get('calendar_event_id'),
    }
    _print_created_trip(result)
    try:
        from education_system.systems.university.domains.operations.domain.campus.mobility.services import trip_management as _tm
        _tm.log_activity('create', 'trip')
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return result


def _print_created_trip(trip):
    """Print the confirmation summary for a freshly created trip."""
    print(get_text("mobility.trip_management.create.success", "\nTrip '{trip_name}' created successfully!").format(trip_name=trip['trip_name']))
    print(get_text("mobility.trip_management.create.trip_id_label", "Trip ID: {trip_id}").format(trip_id=trip['trip_id']))
    print(get_text("mobility.trip_management.create.destination_label", "Destination: {destination}").format(destination=trip['destination']))
    if trip['single_day']:
        print(get_text("mobility.trip_management.create.date_label", "Date: {start_date} (single day)").format(start_date=trip['start_date']))
    else:
        print(get_text("mobility.trip_management.create.dates_label", "Dates: {start_date} to {end_date}").format(start_date=trip['start_date'], end_date=trip['end_date']))
    print(get_text("mobility.trip_management.create.max_participants_label", "Max Participants: {max_participants}").format(max_participants=trip['max_participants']))
    print(get_text("mobility.trip_management.create.cost_label", "Cost: £{cost:.2f}").format(cost=trip['cost'] or 0))
    print(get_text("mobility.trip_management.create.status_label", "Status: {status}").format(status=trip['status'].title()))
    if trip.get('calendar_event_id'):
        print(get_text("mobility.trip_management.create.calendar_added", "Added to the academic calendar."))


@log_read(module="trips", description="Viewing trips")
def view_trips():
    """View trips based on user permissions"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_view", "You must be logged in to view trips.")
    if not auth:
        return False

    if not auth.check_permission('view_trips'):
        print(get_text("mobility.trip_management.auth.no_permission_view", "You don't have permission to view trips."))
        return False

    def view_trips_operation(conn):
        cursor = conn.cursor()
        try:
            # Get all trips with participant count
            cursor.execute(f'''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
                   t.max_participants, t.cost, t.status,
                   COUNT(tp.id) as current_participants,
                   u.first_name || ' ' || u.last_name as created_by_name
            FROM trips t
            LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status IN ({_active_status_sql()})
            LEFT JOIN users u ON t.created_by = u.id
            WHERE t.status <> 'archived'
            GROUP BY t.id
            ORDER BY t.start_date ASC
            ''')
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(get_text("mobility.trip_management.database.error_viewing_trips", "Database error viewing trips: {error}").format(error=e))
            print(get_text("mobility.trip_management.errors.retrieving_trips", "Error retrieving trips from database."))
            return None

    trips = _run_db_operation(view_trips_operation)
    if trips is None or trips is False:
        return False

    if not trips:
        print(get_text("mobility.trip_management.trips.no_trips_found", "No trips found."))
        return True

    print("\n" + get_text("mobility.trip_management.trips.all_trips_title", "All Trips"))
    print("=" * 120)
    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.end_date', 'End Date'):<12} {get_text('mobility.trip_management.headers.participants', 'Participants'):<12} {get_text('mobility.trip_management.headers.cost', 'Cost'):<10} {get_text('mobility.trip_management.headers.status', 'Status'):<12} {get_text('mobility.trip_management.headers.created_by', 'Created By'):<15}")
    print("-" * 120)

    for trip in trips:
        trip_id, name, destination, start_date, end_date, max_parts, cost, status, current_parts, created_by = trip
        participants_info = f"{current_parts}/{max_parts}"
        print(f"{trip_id:<5} {name[:24]:<25} {destination[:19]:<20} {start_date:<12} {end_date:<12} {participants_info:<12} £{cost or 0:<9.2f} {status.title():<12} {created_by[:14] if created_by else get_text('mobility.trip_management.common.na', 'N/A'):<15}")

    print("=" * 120)

    # Option to view detailed trip information (no connection held open here)
    while True:
        choice = input(get_text("mobility.trip_management.trips.enter_id_or_back", "\nEnter trip ID to view details (or 'back' to return): ")).strip()
        if choice.lower() == 'back' or not choice:
            break
        try:
            view_trip_details(int(choice))
        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID. Please enter a number."))
        except Exception as e:
            print(get_text("mobility.trip_management.errors.viewing_details", "Error viewing trip details: {error}").format(error=e))

    return True


def view_trip_details(trip_id):
    """View detailed information about a specific trip"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_view", "You must be logged in to view trips.")
    if not auth:
        return False
    if not auth.check_permission('view_trips'):
        print(get_text("mobility.trip_management.auth.no_permission_view", "You don't have permission to view trips."))
        return False
    # Participant names and e-mails are for the trip's organisers only.
    show_people = (auth.check_permission('manage_trip_participants')
                   or can_manage_trip(auth, trip_id))
    statuses = _active_status_sql()

    def view_details_operation(conn):
        cursor = conn.cursor()

        cursor.execute('''
        SELECT t.id, t.trip_name, t.description, t.destination, t.start_date, t.end_date,
               t.max_participants, t.cost, t.status, t.created_at, t.updated_at,
               u.first_name || ' ' || u.last_name AS created_by_name
        FROM trips t
        LEFT JOIN users u ON t.created_by = u.id
        WHERE t.id = ?
        ''', (trip_id,))
        trip = cursor.fetchone()
        if not trip:
            return None
        trip = dict(zip([d[0] for d in cursor.description], trip))

        cursor.execute(f'''
        SELECT tp.registration_date, tp.payment_status, tp.status,
               COALESCE(s.first_name || ' ' || s.last_name,
                        u.first_name || ' ' || u.last_name) AS student_name,
               COALESCE(s.email_address, u.email) AS email
        FROM trip_participants tp
        LEFT JOIN students s ON tp.student_id = s.student_id
        LEFT JOIN users u ON tp.user_id = u.id
        WHERE tp.trip_id = ? AND tp.status IN ({statuses})
        ORDER BY tp.registration_date
        ''', (trip_id,))
        names = [d[0] for d in cursor.description]
        participants = [dict(zip(names, row)) for row in cursor.fetchall()]

        cursor.execute('''
        SELECT ts.role, u.first_name || ' ' || u.last_name as staff_name
        FROM trip_staff ts
        JOIN users u ON ts.staff_user_id = u.id
        WHERE ts.trip_id = ?
        ORDER BY ts.role
        ''', (trip_id,))
        staff = cursor.fetchall()
        return trip, participants, staff

    loaded = _run_db_operation(view_details_operation)
    if not loaded:
        print(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        return False
    trip, participants, staff = loaded

    na = get_text("mobility.trip_management.common.na", "N/A")
    unknown = get_text("mobility.trip_management.common.unknown", "Unknown")
    print(get_text("mobility.trip_management.details.title", "\nTrip Details - ID: {trip_id}").format(trip_id=trip['id']))
    print("=" * 60)
    print(get_text("mobility.trip_management.details.name", "Name: {name}").format(name=trip['trip_name']))
    print(get_text("mobility.trip_management.details.description", "Description: {description}").format(description=trip['description'] or get_text("mobility.trip_management.common.none", "None")))
    print(get_text("mobility.trip_management.details.destination", "Destination: {destination}").format(destination=trip['destination']))
    print(get_text("mobility.trip_management.details.start_date", "Start Date: {start_date}").format(start_date=trip['start_date']))
    print(get_text("mobility.trip_management.details.end_date", "End Date: {end_date}").format(end_date=trip['end_date']))
    print(get_text("mobility.trip_management.details.max_participants", "Max Participants: {max_participants}").format(max_participants=trip['max_participants']))
    print(get_text("mobility.trip_management.details.cost", "Cost: £{cost:.2f}").format(cost=trip['cost'] or 0))
    print(get_text("mobility.trip_management.details.status", "Status: {status}").format(status=(trip['status'] or '').title()))
    print(get_text("mobility.trip_management.details.created_by", "Created By: {created_by}").format(created_by=trip['created_by_name'] or unknown))
    print(get_text("mobility.trip_management.details.created", "Created: {created}").format(created=trip['created_at']))
    print(get_text("mobility.trip_management.details.updated", "Updated: {updated}").format(updated=trip['updated_at']))

    print(get_text("mobility.trip_management.details.participants_count", "\nParticipants ({current}/{max}):").format(current=len(participants), max=trip['max_participants']))
    print("-" * 60)
    if participants and show_people:
        for p in participants:
            print(get_text("mobility.trip_management.details.participant_line", "- {name} ({email}) - Registered: {reg_date} - Payment: {payment}").format(
                name=p['student_name'] or unknown, email=p['email'] or na,
                reg_date=p['registration_date'], payment=(p['payment_status'] or '').title()))
    elif not participants:
        print(get_text("mobility.trip_management.details.no_participants", "No participants registered yet."))

    if staff:
        print(get_text("mobility.trip_management.details.assigned_staff", "\nAssigned Staff:"))
        print("-" * 30)
        for role, name in staff:
            print(get_text("mobility.trip_management.details.staff_line", "- {name} - {role}").format(name=name, role=role.title()))

    print("=" * 60)
    return True


def _editable_trips(auth):
    """Trips the user may change: all for manage_trips, else their own / led."""
    who = actor(auth)
    with _db().read_connection() as conn:
        if auth.check_permission('manage_trips'):
            rows = conn.execute(
                "SELECT id, trip_name, destination, start_date, end_date, status FROM trips "
                "WHERE status NOT IN ('archived') ORDER BY start_date DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT id, trip_name, destination, start_date, end_date, status FROM trips "
                "WHERE status NOT IN ('archived') AND (created_by = ? OR id IN ("
                "  SELECT trip_id FROM trip_staff WHERE staff_user_id = ? "
                "  AND role IN ('coordinator', 'supervisor'))) ORDER BY start_date DESC",
                (who['user_id'], who['user_id'])).fetchall()
    return [tuple(r) for r in rows]


@log_update(module="trips", description="Updating trip information")
def update_trip():
    """Update trip information"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_update", "You must be logged in to update trips.")
    if not auth:
        return False

    if not (auth.check_permission('manage_trips') or auth.check_permission('create_trips')):
        print(get_text("mobility.trip_management.auth.no_permission_update", "You don't have permission to update trips."))
        return False

    trips = _editable_trips(auth)
    if not trips:
        print(get_text("mobility.trip_management.update.no_trips_available", "No trips found that you can update."))
        return False

    print("\n" + get_text("mobility.trip_management.update.trips_available", "Trips Available for Update:"))
    print("=" * 80)
    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.status', 'Status'):<10}")
    print("-" * 80)
    for trip in trips:
        print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[5].title():<10}")
    print("=" * 80)

    try:
        trip_id = int(input(get_text("mobility.trip_management.update.enter_trip_id", "\nEnter Trip ID to update: ")))
    except ValueError:
        print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
        return False

    trip = get_trip(trip_id)
    if not trip or trip_id not in {t[0] for t in trips}:
        print(get_text("mobility.trip_management.update.not_found_or_no_permission", "Trip not found or you don't have permission to update it."))
        return False

    print(get_text("mobility.trip_management.update.updating_trip", "\nUpdating Trip: {trip_name}").format(trip_name=trip['trip_name']))
    print(get_text("mobility.trip_management.update.leave_blank", "Leave fields blank to keep current values."))

    changes = {}
    new_name = input(get_text("mobility.trip_management.update.trip_name_current", "Trip Name (current: {current}): ").format(current=trip['trip_name'])).strip()
    if new_name:
        changes['trip_name'] = new_name
    new_description = input(get_text("mobility.trip_management.update.description_current", "Description (current: {current}): ").format(current=trip['description'] or get_text("mobility.trip_management.common.none", "None"))).strip()
    if new_description:
        changes['description'] = new_description
    new_destination = input(get_text("mobility.trip_management.update.destination_current", "Destination (current: {current}): ").format(current=trip['destination'])).strip()
    if new_destination:
        changes['destination'] = new_destination

    new_start_date = input(get_text("mobility.trip_management.update.start_date_current", "Start Date (current: {current}, format: YYYY-MM-DD): ").format(current=trip['start_date'])).strip()
    if new_start_date:
        try:
            datetime.strptime(new_start_date, '%Y-%m-%d')
            changes['start_date'] = new_start_date
        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_start_date_keeping", "Invalid start date format. Keeping current value."))

    new_end_date = input(get_text("mobility.trip_management.update.end_date_current", "End Date (current: {current}, format: YYYY-MM-DD): ").format(current=trip['end_date'])).strip()
    if new_end_date:
        try:
            datetime.strptime(new_end_date, '%Y-%m-%d')
            changes['end_date'] = new_end_date
        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_end_date_keeping", "Invalid end date format. Keeping current value."))

    new_max_participants = input(get_text("mobility.trip_management.update.max_participants_current", "Max Participants (current: {current}): ").format(current=trip['max_participants'])).strip()
    if new_max_participants:
        try:
            value = int(new_max_participants)
            if value <= 0:
                print(get_text("mobility.trip_management.validation.max_participants_positive_keeping", "Max participants must be positive. Keeping current value."))
            else:
                changes['max_participants'] = value
        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_number_keeping", "Invalid number. Keeping current value."))

    new_cost = input(get_text("mobility.trip_management.update.cost_current", "Cost (current: £{current:.2f}): ").format(current=trip['cost'] or 0)).strip()
    if new_cost:
        try:
            value = float(new_cost)
            if value < 0:
                print(get_text("mobility.trip_management.validation.cost_non_negative_keeping", "Cost cannot be negative. Keeping current value."))
            else:
                changes['cost'] = value
        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_cost_keeping", "Invalid cost. Keeping current value."))

    # Status: only the moves the life cycle allows from here.
    status_options = list(TRIP_STATUS_TRANSITIONS.get(trip['status'], ()))
    new_status = ""
    print(get_text("mobility.trip_management.update.current_status", "\nCurrent Status: {status}").format(status=trip['status'].title()))
    if status_options:
        print(get_text("mobility.trip_management.update.status_options", "Status Options:"))
        for i, status in enumerate(status_options, 1):
            print(f"{i}. {status.replace('_', ' ').title()}")
        choice = input(get_text("mobility.trip_management.update.select_status_n", "Select new status (1-{max}, or blank to keep current): ").format(max=len(status_options))).strip()
        if choice:
            try:
                index = int(choice) - 1
                if 0 <= index < len(status_options):
                    new_status = status_options[index]
                else:
                    print(get_text("mobility.trip_management.validation.invalid_status_keeping", "Invalid status choice. Keeping current value."))
            except ValueError:
                print(get_text("mobility.trip_management.validation.invalid_input_keeping", "Invalid input. Keeping current value."))

    if not changes and not new_status:
        print(get_text("mobility.trip_management.update.no_changes", "No changes to update."))
        return True

    try:
        if changes:
            update_trip_record(auth, trip_id, **changes)
        if new_status:
            outcome = set_trip_status(auth, trip_id, new_status)
            _print_refunds(outcome.get('refunds'))
    except (ValueError, PermissionError) as e:
        print(get_text("mobility.trip_management.errors.updating_trip", "Error updating trip: {error}").format(error=e))
        return False
    except sqlite3.Error as e:
        logging.error(get_text("mobility.trip_management.errors.in_update_trip", "Error in update_trip: {error}").format(error=e))
        print(get_text("mobility.trip_management.errors.updating_trip", "Error updating trip: {error}").format(error=e))
        return False

    print(get_text("mobility.trip_management.update.success", "Trip updated successfully!"))
    return True


def _print_refunds(refunds):
    for outcome in refunds or ():
        if outcome.get('success'):
            print(get_text("mobility.trip_management.archive.refunded",
                           "Refunded £{amount:.2f} to participant {participant_id}.").format(
                amount=outcome.get('amount') or 0, participant_id=outcome.get('participant_id')))
        else:
            print(get_text("mobility.trip_management.archive.refund_failed",
                           "Refund for participant {participant_id} could not be raised: {message}").format(
                participant_id=outcome.get('participant_id'), message=outcome.get('message') or ''))


def _print_emailed(count):
    if count:
        print(get_text("mobility.trip_management.archive.emailed",
                       "{count} participant(s) e-mailed that the trip will not go ahead.").format(count=count))


@log_delete(module="trips", description="Archiving trip")
def delete_trip():
    """Archive a trip (the menu's delete). Nothing is deleted: the trip, its
    participants and payments are kept, places are released and paid
    participants refunded."""
    auth = _cli_auth("mobility.trip_management.auth.must_login_delete", "You must be logged in to delete trips.")
    if not auth:
        return False

    if not auth.check_permission('manage_trips'):
        print(get_text("mobility.trip_management.auth.no_permission_delete", "You don't have permission to delete trips."))
        return False

    with _db().read_connection() as conn:
        trips = conn.execute(f'''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.status,
               (SELECT COUNT(*) FROM trip_participants tp WHERE tp.trip_id = t.id
                AND tp.status IN ({_active_status_sql()}, 'waitlisted')) AS participant_count
        FROM trips t
        WHERE t.status NOT IN ('archived', 'in_progress')
        ORDER BY t.start_date DESC
        ''').fetchall()

    if not trips:
        print(get_text("mobility.trip_management.trips.no_trips_found", "No trips found."))
        return False

    print("\n" + get_text("mobility.trip_management.archive.trips_available", "Trips Available to Archive:"))
    print("=" * 80)
    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.status', 'Status'):<10} {get_text('mobility.trip_management.headers.participants', 'Participants'):<12}")
    print("-" * 80)
    for trip in trips:
        print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[4].title():<10} {trip[5]:<12}")
    print("=" * 80)

    try:
        trip_id = int(input(get_text("mobility.trip_management.archive.enter_trip_id", "\nEnter Trip ID to archive: ")))
    except ValueError:
        print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
        return False

    selected = next((t for t in trips if t[0] == trip_id), None)
    if not selected:
        print(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        return False
    _id, trip_name, destination, start_date, status, participant_count = tuple(selected)

    print(get_text("mobility.trip_management.archive.trip_to_archive", "\nTrip to Archive:"))
    print(get_text("mobility.trip_management.delete.name", "Name: {name}").format(name=trip_name))
    print(get_text("mobility.trip_management.delete.destination", "Destination: {destination}").format(destination=destination))
    print(get_text("mobility.trip_management.delete.start_date", "Start Date: {start_date}").format(start_date=start_date))
    print(get_text("mobility.trip_management.delete.participants", "Participants: {count}").format(count=participant_count))
    if participant_count > 0 and status != 'completed':
        print(get_text("mobility.trip_management.archive.warning_participants",
                       "\nThis trip has {count} current participants. Their places will be released "
                       "and anything they paid will be refunded.").format(count=participant_count))

    confirm = input(get_text("mobility.trip_management.archive.confirm", "\nArchive this trip? (y/n): ")).lower()
    if confirm not in ('y', 'yes'):
        print(get_text("mobility.trip_management.archive.cancelled", "Trip not archived."))
        return True
    reason = input(get_text("mobility.trip_management.archive.reason_prompt", "Reason (optional): ")).strip()

    try:
        outcome = archive_trip(auth, trip_id, reason=reason)
    except (ValueError, PermissionError) as e:
        print(get_text("mobility.trip_management.errors.deleting_trip", "Error deleting trip: {error}").format(error=e))
        return False
    except sqlite3.Error as e:
        logging.error(get_text("mobility.trip_management.errors.in_delete_trip", "Error in delete_trip: {error}").format(error=e))
        print(get_text("mobility.trip_management.errors.deleting_trip", "Error deleting trip: {error}").format(error=e))
        return False

    print(get_text("mobility.trip_management.archive.success", "\nTrip '{trip_name}' has been archived.").format(trip_name=trip_name))
    _print_refunds(outcome.get('refunds'))
    _print_emailed(outcome.get('emailed'))
    return True
