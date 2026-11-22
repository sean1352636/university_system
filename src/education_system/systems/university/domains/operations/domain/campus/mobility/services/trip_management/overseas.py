"""Overseas trips: FCDO advice, insurance and participants' travel documents.

There is no FCDO feed to call: staff read the advice on GOV.UK
(:func:`advice_url`) and record what it said, when, and who checked.
:func:`overseas_problems` is one of the gates on opening an overseas trip
(``approvals.gate_problems``):

* FCDO advice against all travel blocks the trip outright; advice against
  all but essential travel marks it ``high_risk`` and makes the
  International approval stage required (a change resets approvals);
* the FCDO check must be no more than :data:`FCDO_MAX_AGE_DAYS` days old,
  measured at today or the departure date, whichever is earlier;
* insurance must be registered;
* every participant needs a passport valid until at least six months after
  the trip ends, and a visa that is not required or has been granted.
"""
import re
from datetime import timedelta

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import logging, datetime

logger = logging.getLogger(__name__)

FCDO_LEVELS = ('none', 'some_areas', 'all_but_essential', 'all_travel')
FCDO_LABELS = {
    'none': 'No FCDO advice against travel',
    'some_areas': 'FCDO advises against travel to some areas',
    'all_but_essential': 'FCDO advises against all but essential travel',
    'all_travel': 'FCDO advises against all travel',
}
VISA_STATUSES = ('not_required', 'applied', 'granted', 'refused')
VISA_OK = ('not_required', 'granted')
FCDO_MAX_AGE_DAYS = 14
PASSPORT_MARGIN_MONTHS = 6
ADVICE_BASE_URL = "https://www.gov.uk/foreign-travel-advice/"


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _date(value):
    try:
        return datetime.strptime(str(value).strip()[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _add_months(d, months):
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return d.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    return d


def advice_url(country):
    """GOV.UK foreign travel advice page for ``country`` ('' when none)."""
    if not country:
        return ''
    slug = re.sub(r'[^a-z0-9]+', '-', str(country).lower().replace('&', 'and')).strip('-')
    return ADVICE_BASE_URL + slug if slug else ''


def _may_manage(auth, trip, c, who):
    return (_trips().can_manage_trip(auth, trip, conn=c, who=who)
            or auth.check_permission('approve_trips_international'))


def record_fcdo_check(auth, trip_id, advice_level, checked_at=None, *, conn=None, pending=None):
    """Record the FCDO advice level a member of staff read for the trip's country.

    ``advice_level`` is one of :data:`FCDO_LEVELS`; ``checked_at`` defaults
    to now. 'all_but_essential' sets ``high_risk``. A changed level after
    the trip was submitted resets its approvals (the International stage may
    now be needed). Trip organisers or International approvers. Returns
    ``{'trip', 'advice_url'}``.
    """
    trips = _trips()
    who = trips.actor(auth)
    if advice_level not in FCDO_LEVELS:
        raise ValueError(f"advice level must be one of {', '.join(FCDO_LEVELS)}")
    when = checked_at or trips._now()
    if not _date(when):
        raise ValueError("checked_at: use YYYY-MM-DD")
    if _date(when) > datetime.now().date():
        raise ValueError("the FCDO check cannot be dated in the future")

    def work(c, p):
        from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import approvals
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError("Trip not found.")
        if not _may_manage(auth, trip, c, who):
            raise PermissionError("only the trip's organisers or International approvers can do that")
        if not trip.get('country'):
            raise ValueError("set the trip's country first")
        old = trip.get('fcdo_advice_level')
        high = 1 if advice_level == 'all_but_essential' else int(trip.get('high_risk') or 0)
        c.execute("UPDATE trips SET fcdo_advice_level = ?, fcdo_checked_at = ?, fcdo_checked_by = ?, "
                  "high_risk = ?, updated_by = ?, updated_at = ? WHERE id = ?",
                  (advice_level, str(when)[:19], who['username'], high, who['username'],
                   trips._now(), trip_id))
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='fcdo_check', field='fcdo_advice_level', old_value=old,
                             new_value=f"{advice_level} ({advice_url(trip['country'])})")
        updated = trips.get_trip(trip_id, conn=c)
        if old is not None and old != advice_level:
            approvals.reset_for_material_change(c, updated, who, ['fcdo_advice_level'], pending=p)
            updated = trips.get_trip(trip_id, conn=c)
        if advice_level == 'all_travel' and trip['status'] in ('open', 'full', 'closed', 'in_progress'):
            trips.queue_email(
                p, trips.leader_emails(c, trip),
                f"FCDO now advises against all travel: {trip['trip_name']}",
                f"{who['username']} recorded that the FCDO advises against all travel to "
                f"{trip['country']} ({advice_url(trip['country'])}). The trip "
                f"'{trip['trip_name']}' is {trip['status']}; decide whether to cancel it.")
        trips._publish_after(p, "trip.updated", trip_id=trip_id, fields=['fcdo_advice_level'])
        return {'trip': updated, 'advice_url': advice_url(trip['country'])}
    return trips._in_transaction(conn, pending, work)


def record_insurance(auth, trip_id, reference, *, conn=None, pending=None):
    """Record the university travel insurance registration for the trip."""
    trips = _trips()
    who = trips.actor(auth)
    reference = (reference or '').strip()
    if len(reference) < 3:
        raise ValueError("enter the insurance registration reference")

    def work(c, p):
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError("Trip not found.")
        if not _may_manage(auth, trip, c, who):
            raise PermissionError("only the trip's organisers or International approvers can do that")
        now = trips._now()
        c.execute("UPDATE trips SET insurance_reference = ?, insurance_registered_at = ?, "
                  "updated_by = ?, updated_at = ? WHERE id = ?",
                  (reference, now, who['username'], now, trip_id))
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='insurance', field='insurance_reference',
                             old_value=trip.get('insurance_reference'), new_value=reference)
        return trips.get_trip(trip_id, conn=c)
    return trips._in_transaction(conn, pending, work)


def participant_documents(auth, participant_id, passport_expiry, visa_status, *, conn=None,
                          pending=None):
    """Record a participant's passport expiry and visa status.

    The participant themselves, or the trip's organisers. Returns the
    problems still outstanding for this participant (empty when fine).
    """
    trips = _trips()
    who = trips.actor(auth)
    expiry = _date(passport_expiry) if passport_expiry not in (None, '') else None
    if passport_expiry not in (None, '') and not expiry:
        raise ValueError("passport expiry: use YYYY-MM-DD")
    if visa_status not in (None, '') and visa_status not in VISA_STATUSES:
        raise ValueError(f"visa status must be one of {', '.join(VISA_STATUSES)}")

    def work(c, p):
        cur = c.execute("SELECT * FROM trip_participants WHERE id = ?", (participant_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("participant not found")
        place = dict(zip([d[0] for d in cur.description], row))
        trip = trips.get_trip(place['trip_id'], conn=c)
        own = ((who['user_id'] is not None and place.get('user_id') == who['user_id'])
               or (who['student_id'] and place.get('student_id') == who['student_id']))
        if not (own or auth.check_permission('manage_trip_participants')
                or trips.can_manage_trip(auth, trip, conn=c, who=who)):
            raise PermissionError("only the participant or the trip's organisers can do that")
        c.execute("UPDATE trip_participants SET passport_expiry = ?, visa_status = ? WHERE id = ?",
                  (expiry.isoformat() if expiry else None, visa_status or None, participant_id))
        place.update(passport_expiry=expiry.isoformat() if expiry else None,
                     visa_status=visa_status or None)
        return _document_problems(place, trip)
    return trips._in_transaction(conn, pending, work)


def _document_problems(place, trip):
    problems = []
    end = _date(trip.get('end_date')) or _date(trip.get('start_date'))
    expiry = _date(place.get('passport_expiry'))
    if not expiry:
        problems.append("passport expiry not recorded")
    elif end and expiry < _add_months(end, PASSPORT_MARGIN_MONTHS):
        problems.append(f"passport expires {expiry.isoformat()}, less than "
                        f"{PASSPORT_MARGIN_MONTHS} months after the trip ends")
    if (place.get('visa_status') or '') not in VISA_OK:
        problems.append(f"visa {place.get('visa_status') or 'status not recorded'}")
    return problems


def overseas_problems(trip_id, conn=None, today=None):
    """Everything stopping an overseas trip opening (empty when fine or not overseas)."""
    statuses = _db().ACTIVE_PARTICIPANT_STATUSES
    problems = []
    with _db().read_connection(conn) as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip or not int(trip.get('is_overseas') or 0):
            return problems
        url = advice_url(trip.get('country'))
        if not trip.get('country'):
            problems.append("the destination country is not recorded")
        level = trip.get('fcdo_advice_level')
        checked = _date(trip.get('fcdo_checked_at'))
        if not level or not checked:
            problems.append("FCDO travel advice has not been checked" + (f" ({url})" if url else ""))
        else:
            if level == 'all_travel':
                problems.append(f"the FCDO advises against all travel to {trip['country']} ({url})")
            start = _date(trip.get('start_date'))
            today = _date(today) or datetime.now().date()
            as_at = min(today, start) if start else today
            if (as_at - checked) > timedelta(days=FCDO_MAX_AGE_DAYS):
                problems.append(f"the FCDO check of {checked.isoformat()} is more than "
                                f"{FCDO_MAX_AGE_DAYS} days old; check {url} again")
        if not trip.get('insurance_reference'):
            problems.append("travel insurance is not registered")
        cur = c.execute(
            "SELECT tp.id, tp.student_id, tp.passport_expiry, tp.visa_status, u.username "
            "FROM trip_participants tp LEFT JOIN users u ON u.id = tp.user_id "
            f"WHERE tp.trip_id = ? AND tp.status IN ({', '.join('?' * len(statuses))}) ORDER BY tp.id",
            (trip_id, *statuses))
        names = [d[0] for d in cur.description]
        for row in cur.fetchall():
            place = dict(zip(names, row))
            for problem in _document_problems(place, trip):
                who = place.get('student_id') or place.get('username') or f"participant {place['id']}"
                problems.append(f"{who}: {problem}")
    return problems
