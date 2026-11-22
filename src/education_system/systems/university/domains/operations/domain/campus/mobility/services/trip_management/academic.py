"""Trips and teaching: the linked module, timetable clashes, attendance credit.

A trip may belong to a module (fieldwork, a study visit). Linking checks the
module exists. :func:`timetable_clashes` lists participants who have
timetabled sessions while the trip runs, using the university's one
dated-session rule (``application.timetable_occurrences`` — terms,
holidays, teaching weeks and one-off changes), so a cancelled session or a
reading week is not reported. ``counts_as_attendance`` lets roll calls on
the trip count as attendance for the linked module (rollcall writes it).
"""
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import logging

logger = logging.getLogger(__name__)


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def module_exists(conn, module_code):
    """The module's ``(module_code, module_name)``, or ``None``."""
    row = conn.execute("SELECT module_code, module_name FROM modules WHERE module_code = ? "
                       "COLLATE NOCASE LIMIT 1", (str(module_code).strip(),)).fetchone()
    return tuple(row) if row else None


def link_module(auth, trip_id, module_code, *, conn=None, pending=None):
    """Link the trip to a module (``None`` / '' unlinks, and turns attendance credit off).

    Goes through ``trips.update_trip_record``, so it is recorded in the
    trip's history. Returns the trip dict.
    """
    trips = _trips()
    code = (module_code or '').strip() or None
    if code:
        with _db().read_connection(conn) as c:
            found = module_exists(c, code)
        if not found:
            raise ValueError(f"no module {code}")
        code = found[0]
        return trips.update_trip_record(auth, trip_id, conn=conn, pending=pending, module_code=code)
    return trips.update_trip_record(auth, trip_id, conn=conn, pending=pending, module_code=None,
                                    counts_as_attendance=0)


def set_counts_as_attendance(auth, trip_id, counts, *, conn=None, pending=None):
    """Turn attendance credit for the linked module on or off. Needs a linked module."""
    trips = _trips()
    if counts:
        trip = trips.get_trip(trip_id, conn=conn)
        if not trip:
            raise ValueError("Trip not found.")
        if not trip.get('module_code'):
            raise ValueError("link the trip to a module first")
    return trips.update_trip_record(auth, trip_id, conn=conn, pending=pending,
                                    counts_as_attendance=1 if counts else 0)


def timetable_clashes(trip_id, conn=None):
    """Participants with timetabled sessions during the trip.

    Returns ``[{participant_id, student_id, name, sessions: [{date,
    start_time, end_time, module_code, room, status, linked_module}]}]`` —
    only students with at least one scheduled (not cancelled) session
    between the trip's start and end dates. ``linked_module`` marks a
    session of the module the trip belongs to.
    """
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )

    statuses = _db().ACTIVE_PARTICIPANT_STATUSES + ('waitlisted',)
    out = []
    with _db().read_connection(conn) as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError("Trip not found.")
        start, end = trip['start_date'], trip.get('end_date') or trip['start_date']
        linked = (trip.get('module_code') or '').upper()
        cur = c.execute(
            "SELECT tp.id, tp.student_id, COALESCE(s.first_name || ' ' || s.last_name, "
            "u.first_name || ' ' || u.last_name) FROM trip_participants tp "
            "LEFT JOIN students s ON s.student_id = tp.student_id "
            "LEFT JOIN users u ON u.id = tp.user_id "
            f"WHERE tp.trip_id = ? AND tp.status IN ({', '.join('?' * len(statuses))}) "
            "AND COALESCE(tp.student_id, '') <> '' ORDER BY tp.id", (trip_id, *statuses))
        for pid, sid, name in cur.fetchall():
            try:
                sessions = timetable_occurrences.for_student(c, sid, start, end)
            except Exception:
                logger.warning("timetable lookup for %s failed", sid, exc_info=True)
                continue
            booked = [{
                'date': s.get('date'), 'start_time': s.get('start_time'),
                'end_time': s.get('end_time'), 'module_code': s.get('module_code'),
                'room': s.get('room_name') or s.get('room_id'), 'status': s.get('status'),
                'linked_module': bool(linked) and str(s.get('module_code') or '').upper() == linked,
            } for s in sessions if s.get('status') != 'cancelled']
            if booked:
                out.append({'participant_id': pid, 'student_id': sid, 'name': name,
                            'sessions': booked})
    return out
