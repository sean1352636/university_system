"""The trip waiting list.

When every place is taken, :func:`join_or_waitlist` puts the person on the
waiting list (status 'waitlisted', ``waitlist_position``) instead of turning
them away. When a place is given up (:func:`on_place_freed`, called after a
cancellation or removal commits), the first person waiting is offered it:
status 'offered' — which holds the place — with ``offer_expires_at`` 48
hours on, and an e-mail. They :func:`accept_offer` (status 'registered') or
:func:`decline_offer`; an offer not taken up in time lapses
(:func:`expire_offers`, run by the scheduled trip jobs) and the next person
is offered the place.
"""

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import (
    get_text, logging, datetime, timedelta,
)

logger = logging.getLogger(__name__)

OFFER_HOURS = 48
# Trips still taking people (an offer is only made on these).
_TAKING = ('open', 'full')


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _registrations():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import registrations
    return registrations


def _stamp(when):
    return when.strftime('%Y-%m-%d %H:%M:%S')


SYSTEM = {'username': 'system:trips', 'role': 'system', 'user_id': None, 'student_id': None}


def join_or_waitlist(auth, trip_id, **kwargs):
    """Register for the trip, or join its waiting list when it is full.

    Same arguments as ``registrations.register``. Returns the booking; a
    waiting-list booking has ``status`` 'waitlisted' and ``position``.
    """
    return _registrations().register(auth, trip_id, waitlist=True, **kwargs)


def next_position(conn, trip_id):
    row = conn.execute("SELECT COALESCE(MAX(waitlist_position), 0) + 1 FROM trip_participants "
                       "WHERE trip_id = ? AND status = 'waitlisted'", (trip_id,)).fetchone()
    return row[0]


def positions(trip_id, conn=None):
    """The waiting list in order: ``[{participant_id, position, place, name,
    waitlisted_at}]`` (``place`` is 1 for the next person to be offered)."""
    with _db().read_connection(conn) as c:
        rows = c.execute(
            "SELECT tp.id, tp.waitlist_position, COALESCE(NULLIF(TRIM(COALESCE(s.first_name, '') "
            "|| ' ' || COALESCE(s.last_name, '')), ''), u.username, tp.student_id), tp.waitlisted_at "
            "FROM trip_participants tp LEFT JOIN students s ON s.student_id = tp.student_id "
            "LEFT JOIN users u ON u.id = tp.user_id "
            "WHERE tp.trip_id = ? AND tp.status = 'waitlisted' "
            "ORDER BY COALESCE(tp.waitlist_position, 999999), tp.waitlisted_at, tp.id",
            (trip_id,)).fetchall()
    return [{'participant_id': r[0], 'position': r[1], 'place': i, 'name': r[2],
             'waitlisted_at': r[3]} for i, r in enumerate(rows, 1)]


def _offer_next(c, trip, now):
    """Offer free places to the people waiting, in order. Returns offered ids."""
    trips = _trips()
    offered = []
    if trip['status'] not in _TAKING:
        return offered
    capacity = trip['max_participants'] or 0
    expires = _stamp(now + timedelta(hours=OFFER_HOURS))
    while trips.active_participant_count(c, trip['id']) < capacity:
        row = c.execute(
            "SELECT id FROM trip_participants WHERE trip_id = ? AND status = 'waitlisted' "
            "ORDER BY COALESCE(waitlist_position, 999999), waitlisted_at, id LIMIT 1",
            (trip['id'],)).fetchone()
        if not row:
            break
        c.execute("UPDATE trip_participants SET status = 'offered', offer_expires_at = ? "
                  "WHERE id = ?", (expires, row[0]))
        offered.append(row[0])
    # Keep 'open' / 'full' right even when nobody was waiting (a lapsed offer).
    trips.refresh_capacity_status(c, trips.get_trip(trip['id'], conn=c), SYSTEM)
    return offered


def _email_offers(trip, participant_ids):
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import comms
    if not participant_ids:
        return
    with _db().read_connection() as c:
        people = {p['id']: p for p in comms.participant_contacts(c, trip['id'], ('offered',))}
        expiry = {r[0]: r[1] for r in c.execute(
            f"SELECT id, offer_expires_at FROM trip_participants WHERE id IN "
            f"({', '.join('?' * len(participant_ids))})", participant_ids).fetchall()}
    subject = get_text("mobility.trip_management.waitlist.offer_subject",
                       "A place is free on {trip_name}").format(trip_name=trip['trip_name'])
    body = get_text(
        "mobility.trip_management.waitlist.offer_body",
        "Dear {name},\n\nA place has come up on {trip_name} ({start_date}, {destination}) and it "
        "is yours if you want it. Accept it in Trip Management (My Registrations) by "
        "{expires}; after that it goes to the next person waiting.",
    )
    for pid in participant_ids:
        person = people.get(pid) or {}
        comms.send(person.get('email'), subject, body.format(
            name=person.get('name') or '', trip_name=trip['trip_name'],
            start_date=trip['start_date'], destination=trip.get('destination') or '',
            expires=expiry.get(pid) or ''),
            trip_id=trip['id'], ref=f"trip:{trip['id']}:offer:{pid}:{expiry.get(pid)}")


def on_place_freed(trip_id, now=None):
    """A place may have come free: offer it to the next person waiting.
    Call after the cancellation / removal has committed. Returns the ids
    offered a place."""
    now = now or datetime.now()
    with _db().write_transaction() as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            return []
        offered = _offer_next(c, trip, now)
    _email_offers(trip, offered)
    return offered


def _own_offer(auth, c, participant_id, who):
    place = _registrations().get_participant(participant_id, conn=c)
    if not place:
        raise ValueError(get_text("mobility.trip_management.participants.not_found",
                                  "Participant not found."))
    trip = _trips().get_trip(place['trip_id'], conn=c)
    own = ((who['user_id'] is not None and place.get('user_id') == who['user_id'])
           or (who['student_id'] and place.get('student_id') == who['student_id']))
    if not own and not (auth.check_permission('manage_trip_participants')
                        or _trips().can_manage_trip(auth, trip, conn=c, who=who)):
        raise PermissionError(get_text("mobility.trip_management.waitlist.not_yours",
                                       "That offer is not yours."))
    if place['status'] != 'offered':
        raise ValueError(get_text("mobility.trip_management.waitlist.no_offer",
                                  "There is no open offer on this registration ({status}).")
                         .format(status=place['status']))
    return place, trip


def accept_offer(auth, participant_id, now=None):
    """Take up an offered place (status 'registered'; payment then as for
    any registration). Refuses an offer that has expired. Returns the place."""
    now = now or datetime.now()
    trips = _trips()
    who = trips.actor(auth)
    with _db().write_transaction() as c:
        place, trip = _own_offer(auth, c, participant_id, who)
        if place.get('offer_expires_at') and place['offer_expires_at'] < _stamp(now):
            raise ValueError(get_text("mobility.trip_management.waitlist.offer_expired",
                                      "This offer has expired."))
        if trip['status'] not in _TAKING:
            raise ValueError(f"the trip is {trip['status']}")
        # The offered place is already counted; re-check nobody overfilled it.
        if trips.active_participant_count(c, trip['id']) > (trip['max_participants'] or 0):
            raise _registrations().TripFullError(get_text(
                "mobility.trip_management.registration.full", "Trip is full."))
        c.execute("UPDATE trip_participants SET status = 'registered', offer_expires_at = NULL, "
                  "waitlist_position = NULL, registration_date = ? WHERE id = ?",
                  (_stamp(now), participant_id))
        trips.refresh_capacity_status(c, trip, who)
        pending = []
        trips._publish_after(pending, "trip.registration.changed", registration_id=participant_id,
                             trip_id=trip['id'], student_id=place.get('student_id'),
                             user_id=place.get('user_id'), action="offer_accepted",
                             fee=float(trip.get('cost') or 0))
        result = _registrations().get_participant(participant_id, conn=c)
    _db().run_after_commit(pending)
    return result


def decline_offer(auth, participant_id, reason=""):
    """Turn down an offered place; it goes to the next person waiting."""
    who = _trips().actor(auth)
    with _db().write_transaction() as c:
        place, trip = _own_offer(auth, c, participant_id, who)
        c.execute("UPDATE trip_participants SET status = 'cancelled', cancellation_date = ?, "
                  "cancellation_reason = ?, offer_expires_at = NULL WHERE id = ?",
                  (_stamp(datetime.now()), reason or "Offer declined", participant_id))
    on_place_freed(trip['id'])
    return True


def expire_offers(now=None):
    """Lapse offers past ``offer_expires_at`` and offer those places on.
    Returns ``{'expired': n, 'offered': n}``."""
    now = now or datetime.now()
    with _db().write_transaction() as c:
        rows = c.execute("SELECT id, trip_id FROM trip_participants WHERE status = 'offered' "
                         "AND offer_expires_at IS NOT NULL AND offer_expires_at < ?",
                         (_stamp(now),)).fetchall()
        for pid, _trip in rows:
            c.execute("UPDATE trip_participants SET status = 'cancelled', cancellation_date = ?, "
                      "cancellation_reason = 'Offer expired', offer_expires_at = NULL WHERE id = ?",
                      (_stamp(now), pid))
    offered = 0
    for trip_id in sorted({r[1] for r in rows}):
        offered += len(on_place_freed(trip_id, now=now))
    return {'expired': len(rows), 'offered': offered}
