"""Telling trip participants things: messages, reminders, the itinerary
pack, change and cancellation notices.

Every e-mail goes to the university outbox (``email_service.send_email``)
after the write it follows has committed. Messages that must go once — the
T-7 / T-1 reminders, a cancellation notice, an evaluation request — carry a
reference (``to_ref``, e.g. ``trip:12:reminder:7:345``) and are recorded in
``trip_history`` (action ``'email'``) when sent; a reference already in the
history or in the outbox is not sent again, so the scheduled job and a
repeated click are both safe.
"""

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import (
    get_text, logging, datetime, timedelta,
)

logger = logging.getLogger(__name__)

SYSTEM_ACTOR = 'system:trips'
REMINDER_DAYS = (7, 1)
# Trips that are going ahead (reminders are only sent for these).
_GOING_AHEAD = ('open', 'full', 'closed')
# Places that get trip mail: people holding a place.
_HOLDING = ('registered', 'offered', 'confirmed')


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _date(value):
    return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def participant_contacts(conn, trip_id, statuses=_HOLDING):
    """``[{id, student_id, user_id, status, name, email}]`` for a trip's participants."""
    statuses = tuple(statuses)
    cur = conn.execute(
        "SELECT tp.id, tp.student_id, tp.user_id, tp.status, "
        "COALESCE(NULLIF(TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')), ''), "
        "NULLIF(TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, '')), ''), "
        "u.username, tp.student_id) AS name, "
        "COALESCE(NULLIF(s.email_address, ''), u.email) AS email "
        "FROM trip_participants tp LEFT JOIN students s ON s.student_id = tp.student_id "
        "LEFT JOIN users u ON u.id = tp.user_id "
        f"WHERE tp.trip_id = ? AND tp.status IN ({', '.join('?' * len(statuses))}) "
        "ORDER BY tp.id", (trip_id, *statuses))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def already_sent(conn, ref):
    """True when a message with reference ``ref`` was sent before."""
    if conn.execute("SELECT 1 FROM trip_history WHERE action = 'email' AND field = ? LIMIT 1",
                    (ref,)).fetchone():
        return True
    try:
        return conn.execute("SELECT 1 FROM email_outbox WHERE to_ref = ? LIMIT 1",
                            (ref,)).fetchone() is not None
    except Exception:   # no outbox table yet
        return False


def send(address, subject, body, *, trip_id=None, ref=None, category='trips'):
    """Send one e-mail now (call after commit). With ``ref`` it is sent at
    most once and recorded in ``trip_history``. Returns True when sent."""
    if not address or '@' not in str(address):
        return False
    db = _db()
    if ref:
        with db.read_connection() as c:
            if already_sent(c, ref):
                return False
    try:
        from education_system.systems.university.infrastructure.email.email_service import send_email
        sent = send_email(address, subject, body, kind="transactional", category=category,
                          to_ref=ref)
    except Exception as exc:
        logger.warning("trip e-mail %r to %s failed: %s", subject, address, exc)
        return False
    if sent and ref and trip_id is not None:
        try:
            with db.write_transaction() as c:
                row = c.execute("SELECT version FROM trips WHERE id = ?", (trip_id,)).fetchone()
                _trips().record_history(c, trip_id, version=row[0] if row else None,
                                        changed_by=SYSTEM_ACTOR, action='email', field=ref,
                                        new_value=address)
        except Exception:
            logger.warning("trip e-mail %s sent but not recorded", ref, exc_info=True)
    return bool(sent)


def _load(trip_id, conn=None):
    trip = _trips().get_trip(trip_id, conn=conn)
    if not trip:
        raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
    return trip


def _require_manager(auth, trip, conn, who):
    if not _trips().can_manage_trip(auth, trip, conn=conn, who=who):
        raise PermissionError(get_text("mobility.trip_management.comms.not_manager",
                                       "Only the trip's organisers can message its participants."))


def _dates(trip):
    start, end = trip.get('start_date'), trip.get('end_date')
    if not end or start == end:
        return str(start)
    return f"{start} to {end}"


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def notify_participants(auth, trip_id, subject, body):
    """E-mail everyone holding a place on the trip. Trip managers only.
    Returns the number of e-mails sent."""
    subject = str(subject or '').strip()
    body = str(body or '').strip()
    if not subject or not body:
        raise ValueError("a subject and a message are required")
    trips = _trips()
    who = trips.actor(auth)
    with _db().read_connection() as c:
        trip = _load(trip_id, c)
        _require_manager(auth, trip, c, who)
        people = participant_contacts(c, trip_id)
    with _db().write_transaction() as c:
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='message', field='participants', new_value=subject)
    full_subject = f"{trip['trip_name']}: {subject}"
    return sum(send(p['email'], full_subject, body, trip_id=trip_id) for p in people)


def change_notice(auth, trip_id, what_changed):
    """Tell everyone holding a place that the trip has changed (dates,
    itinerary, meeting point...). Trip managers only. Returns e-mails sent."""
    what_changed = str(what_changed or '').strip()
    if not what_changed:
        raise ValueError("say what has changed")
    trips = _trips()
    who = trips.actor(auth)
    with _db().read_connection() as c:
        trip = _load(trip_id, c)
        _require_manager(auth, trip, c, who)
        people = participant_contacts(c, trip_id)
    with _db().write_transaction() as c:
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='change_notice', new_value=what_changed)
    subject = get_text("mobility.trip_management.comms.change_subject",
                       "Change to your trip: {trip_name}").format(trip_name=trip['trip_name'])
    body = get_text(
        "mobility.trip_management.comms.change_body",
        "Dear {name},\n\nThere has been a change to {trip_name} ({dates}, {destination}):\n\n"
        "{what_changed}\n\nIf this means you can no longer go, you can cancel your place in "
        "Trip Management.",
    )
    sent = 0
    for p in people:
        sent += send(p['email'], subject, body.format(
            name=p['name'] or '', trip_name=trip['trip_name'], dates=_dates(trip),
            destination=trip.get('destination') or '', what_changed=what_changed),
            trip_id=trip_id)
    return sent


def archive_notice(trip, people, reason=""):
    """E-mail each person who held a place on a trip that has just been
    archived (call after the commit; ``people`` from
    :func:`participant_contacts`, read before the places were released).
    Each person is e-mailed at most once. Returns how many were sent."""
    subject = get_text("mobility.trip_management.comms.archive_subject",
                       "Trip cancelled: {trip_name}").format(trip_name=trip['trip_name'])
    body = get_text(
        "mobility.trip_management.comms.archive_body",
        "Dear {name},\n\n{trip_name} ({dates}, {destination}) will not go ahead and your place "
        "has been released.{reason_line}\n\nIf you paid for the trip, the finance office will "
        "confirm your refund separately.",
    )
    reason_line = f"\n\nReason: {reason}" if reason else ""
    sent = 0
    for person in people:
        sent += send(person.get('email'), subject, body.format(
            name=person.get('name') or '', trip_name=trip['trip_name'], dates=_dates(trip),
            destination=trip.get('destination') or '', reason_line=reason_line),
            trip_id=trip['id'], ref=f"trip:{trip['id']}:archived:{person['id']}")
    return sent


def cancellation_notice(auth, trip_id, reason=""):
    """The university has cancelled the trip: release every place still
    held, refund what each participant paid in full (the university cancelled,
    so the deposit is returned too — ``money.refund_due``), and e-mail each
    of them once. Safe to call after ``trips.set_trip_status(...,
    'cancelled')`` has already released the places: refunds already made are
    not repeated and nobody is e-mailed twice. Trip managers only.
    Returns ``{'cancelled', 'refunds', 'emailed'}``.
    """
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import money, registrations
    trips = _trips()
    db = _db()
    who = trips.actor(auth)
    trip_reason = get_text("mobility.trip_management.cancel.trip_cancelled_reason", "Trip cancelled")
    label = f"{trip_reason}: {reason}" if reason else trip_reason
    statuses = db.CURRENT_PARTICIPANT_STATUSES
    with db.write_transaction() as c:
        trip = _load(trip_id, c)
        _require_manager(auth, trip, c, who)
        released = c.execute(
            f"UPDATE trip_participants SET status = 'cancelled', cancellation_date = ?, "
            f"cancellation_reason = ?, offer_expires_at = NULL, waitlist_position = NULL "
            f"WHERE trip_id = ? AND status IN ({', '.join('?' * len(statuses))})",
            (_now(), label, trip_id, *statuses)).rowcount
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='cancellation_notice', new_value=reason or None)
        cur = c.execute(
            "SELECT * FROM trip_participants WHERE trip_id = ? AND status = 'cancelled' "
            "AND (cancellation_reason = ? OR cancellation_reason LIKE ?)",
            (trip_id, trip_reason, trip_reason + '%'))
        names = [d[0] for d in cur.description]
        affected = [dict(zip(names, r)) for r in cur.fetchall()]
        people = {p['id']: p for p in participant_contacts(c, trip_id, ('cancelled',))}

    refunds = []
    for place in affected:
        if place.get('payment_status') not in ('paid', 'partial'):
            continue
        due = money.refund_due_for(place, trip, university_cancelled=True)
        if due['amount'] > 0:
            refunds.append(registrations.refund_participant(
                place, trip, processed_by=who['username'], amount=due['amount']))

    subject = get_text("mobility.trip_management.comms.cancel_subject",
                       "Trip cancelled: {trip_name}").format(trip_name=trip['trip_name'])
    body = get_text(
        "mobility.trip_management.comms.cancel_body",
        "Dear {name},\n\nWe are sorry to tell you that {trip_name} ({dates}, {destination}) "
        "has been cancelled by the university.{reason_line}\n\nAnything you paid for the trip "
        "is refunded in full; the finance office will confirm the refund separately.",
    )
    reason_line = f"\n\nReason: {reason}" if reason else ""
    emailed = 0
    for place in affected:
        person = people.get(place['id']) or {}
        emailed += send(person.get('email'), subject, body.format(
            name=person.get('name') or '', trip_name=trip['trip_name'], dates=_dates(trip),
            destination=trip.get('destination') or '', reason_line=reason_line),
            trip_id=trip_id, ref=f"trip:{trip_id}:cancelled:{place['id']}")
    return {'cancelled': released, 'refunds': refunds, 'emailed': emailed}


# ---------------------------------------------------------------------------
# Itinerary pack and reminders
# ---------------------------------------------------------------------------

def itinerary_pack(trip_id):
    """The trip pack as text: dates, meeting point, the day-by-day
    itinerary, the emergency card and the 24/7 contact."""
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import rollcall
    with _db().read_connection() as c:
        trip = _load(trip_id, c)
        items = [tuple(r) for r in c.execute(
            "SELECT day_number, start_time, end_time, activity, location, notes "
            "FROM trip_itinerary WHERE trip_id = ? "
            "ORDER BY day_number, COALESCE(start_time, ''), id", (trip_id,)).fetchall()]
    lines = [
        trip['trip_name'],
        "=" * len(trip['trip_name']),
        f"{get_text('mobility.trip_management.pack.dates', 'Dates')}: {_dates(trip)}",
        f"{get_text('mobility.trip_management.pack.destination', 'Destination')}: "
        f"{trip.get('destination') or ''}",
    ]
    meeting = next((i for i in items if i[4]), None)
    if meeting:
        when = f"day {meeting[0]}" + (f", {meeting[1]}" if meeting[1] else "")
        lines.append(f"{get_text('mobility.trip_management.pack.meeting_point', 'Meeting point')}: "
                     f"{meeting[4]} ({when})")
    lines += ["", get_text('mobility.trip_management.pack.itinerary', 'Itinerary')]
    if not items:
        lines.append("  " + get_text('mobility.trip_management.pack.no_itinerary',
                                     'The itinerary has not been published yet.'))
    day = None
    for day_number, start, end, activity, location, notes in items:
        if day_number != day:
            day = day_number
            lines.append(f"  Day {day_number}")
        times = f"{start or ''}{'-' + end if end else ''}".strip()
        lines.append(f"    {times + '  ' if times else ''}{activity}"
                     f"{' @ ' + location if location else ''}{' (' + notes + ')' if notes else ''}")
    lines += ["", rollcall.emergency_card(trip_id)['text']]
    return "\n".join(lines)


def _reminder_tier(days_until):
    """Which reminder is due ``days_until`` days before the trip, or None."""
    if 0 <= days_until <= 1:
        return 1
    if 1 < days_until <= 7:
        return 7
    return None


def send_reminders(now=None):
    """Send the T-7 and T-1 reminders (each with the itinerary pack) for
    trips going ahead. Each participant gets each reminder once, however
    often this runs. Returns ``{'sent', 'trips'}``."""
    today = (now or datetime.now()).date()
    horizon = (today + timedelta(days=7)).isoformat()
    with _db().read_connection() as c:
        due = [dict(zip(('id', 'start_date'), tuple(r))) for r in c.execute(
            f"SELECT id, start_date FROM trips WHERE status IN ({', '.join('?' * len(_GOING_AHEAD))}) "
            "AND substr(start_date, 1, 10) BETWEEN ? AND ?",
            (*_GOING_AHEAD, today.isoformat(), horizon)).fetchall()]
    sent = 0
    for row in due:
        tier = _reminder_tier((_date(row['start_date']) - today).days)
        if tier is None:
            continue
        with _db().read_connection() as c:
            trip = _load(row['id'], c)
            people = [p for p in participant_contacts(c, row['id'], ('registered', 'confirmed'))
                      if not already_sent(c, f"trip:{row['id']}:reminder:{tier}:{p['id']}")]
        if not people:
            continue
        pack = itinerary_pack(row['id'])
        subject = get_text("mobility.trip_management.comms.reminder_subject",
                           "Reminder: {trip_name} starts {when}").format(
            trip_name=trip['trip_name'],
            when=get_text("mobility.trip_management.comms.tomorrow", "tomorrow") if tier == 1
            else get_text("mobility.trip_management.comms.next_week", "in a week"))
        for p in people:
            body = get_text("mobility.trip_management.comms.reminder_body",
                            "Dear {name},\n\nYour trip is coming up. Here is everything you "
                            "need:\n\n{pack}").format(name=p['name'] or '', pack=pack)
            sent += send(p['email'], subject, body, trip_id=row['id'],
                         ref=f"trip:{row['id']}:reminder:{tier}:{p['id']}")
    return {'sent': sent, 'trips': len(due)}
