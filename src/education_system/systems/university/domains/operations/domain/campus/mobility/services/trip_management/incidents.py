"""Trip incidents: reporting, routing and review.

Every incident on a trip — minor ones included — is a ``trip_incidents``
row. After the commit it is routed:

* injuries, serious / critical incidents and RIDDOR-reportable ones become a
  Health & Safety incident (``safety_bus.record_trip_incident``); its id is
  stored in ``hs_reference`` as ``hs_incidents:<id>``;
* safeguarding incidents become a safeguarding concern in the safeguarding
  service (``trip_bus.raise_safeguarding_concern``, the same route the chat
  and chatbot reports use); stored in ``conduct_case_ref`` as
  ``safeguarding:<id>``;
* conduct incidents of moderate severity or worse open a disciplinary case
  (``cases_bus.open_case``, as ``trip_bus.record_incident`` always has);
  stored in ``conduct_case_ref`` as ``disciplinary:<id>``.

Serious and critical incidents are e-mailed to the trip's leaders and to the
24-hour emergency contact (when it is an e-mail address).

Who may report: the trip's organisers and staff, ``manage_trips`` holders,
and participants on the trip (a participant's report is 'open' until an
organiser or Health & Safety reviews it; staff reports start
'under_review').
"""
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import logging

logger = logging.getLogger(__name__)

KINDS = ('incident', 'near_miss', 'illness', 'injury', 'safeguarding', 'conduct', 'other')
SEVERITIES = ('minor', 'moderate', 'serious', 'critical')
HS_SEVERITIES = ('serious', 'critical')
ALERT_SEVERITIES = ('serious', 'critical')
# Disciplinary case severities (``disciplinary_records.severity``).
_CASE_SEVERITY = {'minor': 'Minor', 'moderate': 'Moderate', 'serious': 'Major',
                  'critical': 'Critical'}
# Safeguarding service severities.
_CONCERN_SEVERITY = {'minor': 'MEDIUM', 'moderate': 'HIGH', 'serious': 'HIGH',
                     'critical': 'CRITICAL'}
REVIEW_PERMISSION = 'approve_trips_hs'


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _rows(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _is_trip_staff(c, trip_id, user_id):
    return user_id is not None and c.execute(
        "SELECT 1 FROM trip_staff WHERE trip_id = ? AND staff_user_id = ?",
        (trip_id, user_id)).fetchone() is not None


def _participant_on(c, trip_id, who):
    """The user's participant row on the trip (any status but cancelled / removed), or ``None``."""
    cur = c.execute(
        "SELECT * FROM trip_participants WHERE trip_id = ? AND status NOT IN ('cancelled', 'removed') "
        "AND ((? IS NOT NULL AND user_id = ?) OR (? IS NOT NULL AND student_id = ?))",
        (trip_id, who['user_id'], who['user_id'], who['student_id'], who['student_id']))
    rows = _rows(cur)
    return rows[0] if rows else None


def _role_on_trip(auth, c, trip, who):
    """'staff' (organiser, trip staff, manage_trips), 'participant' or ``None``."""
    trips = _trips()
    if trips.can_manage_trip(auth, trip, conn=c, who=who) or _is_trip_staff(c, trip['id'], who['user_id']):
        return 'staff'
    if _participant_on(c, trip['id'], who):
        return 'participant'
    return None


def _clean(kind, severity, description):
    kind = (kind or '').strip().lower()
    severity = (severity or '').strip().lower()
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {', '.join(SEVERITIES)}")
    description = (description or '').strip()
    if len(description) < 5:
        raise ValueError("describe what happened")
    return kind, severity, description


def _insert(c, p, trip, *, kind, severity, description, occurred_at, location, persons_involved,
            actions_taken, riddor_reportable, reported_by, status, subject_id, offense_type=None):
    """Write the incident and queue its routing / alerts. Returns the id."""
    trips = _trips()
    now = trips._now()
    if riddor_reportable is None:
        # Someone hurt badly enough to need hospital treatment is RIDDOR-
        # reportable for a non-worker; H&S confirms on review.
        riddor_reportable = kind == 'injury' and severity in HS_SEVERITIES
    riddor = 1 if riddor_reportable else 0
    incident_id = c.execute(
        "INSERT INTO trip_incidents (trip_id, kind, severity, occurred_at, location, description, "
        "persons_involved, actions_taken, reported_by, reported_at, riddor_reportable, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (trip['id'], kind, severity, (occurred_at or now), location or None, description,
         persons_involved or None, actions_taken or None, reported_by, now, riddor,
         status)).lastrowid
    trips.record_history(c, trip['id'], version=trip.get('version'), changed_by=reported_by,
                         action='incident_reported', field='incident',
                         new_value=f"#{incident_id} {kind}/{severity}")
    incident = {'id': incident_id, 'trip_id': trip['id'], 'trip_name': trip['trip_name'],
                'kind': kind, 'severity': severity, 'occurred_at': occurred_at or now,
                'location': location, 'description': description,
                'persons_involved': persons_involved, 'actions_taken': actions_taken,
                'reported_by': reported_by, 'riddor_reportable': riddor, 'subject_id': subject_id,
                'offense_type': offense_type or f"trip_incident:{kind}"}
    p.append(lambda: route(incident))
    trips._publish_after(p, "trip.incident.reported", trip_id=trip['id'], incident_id=incident_id,
                         kind=kind, severity=severity)
    if severity in ALERT_SEVERITIES:
        recipients = trips.leader_emails(c, trip)
        contact = trip.get('emergency_contact_24h') or ''
        if '@' in contact:
            recipients.append(contact.strip())
        trips.queue_email(
            p, recipients,
            f"{severity.upper()} incident on trip: {trip['trip_name']}",
            f"A {severity} {kind.replace('_', ' ')} was reported on '{trip['trip_name']}' "
            f"({trip['destination']}) by {reported_by}.\n\n"
            f"When: {occurred_at or now}\nWhere: {location or 'not recorded'}\n"
            f"What happened: {description}\nActions taken: {actions_taken or 'none recorded'}\n"
            + ("\nFlagged as RIDDOR-reportable; Health & Safety have been notified.\n" if riddor else "")
            + f"\nIncident #{incident_id} — review it in Trip Management.",
            category='trip_incidents')
    return incident_id


def report_incident(auth, trip_id, kind, severity, description, occurred_at=None, location="",
                    persons_involved="", actions_taken="", riddor_reportable=None, *,
                    subject_id=None, conn=None, pending=None):
    """Report an incident on a trip. Returns the incident id.

    ``kind`` is one of :data:`KINDS`, ``severity`` one of
    :data:`SEVERITIES`. ``riddor_reportable`` ``None`` means "work it out"
    (a serious / critical injury). ``subject_id`` is the student a conduct
    incident is about (needed to open a disciplinary case). Routing and
    e-mails happen after the commit (see the module docstring).
    """
    trips = _trips()
    who = trips.actor(auth)
    kind, severity, description = _clean(kind, severity, description)

    def work(c, p):
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError("Trip not found.")
        role = _role_on_trip(auth, c, trip, who)
        if role is None:
            raise PermissionError("only the trip's staff, organisers and participants can report "
                                  "an incident on it")
        return _insert(c, p, trip, kind=kind, severity=severity, description=description,
                       occurred_at=occurred_at, location=location,
                       persons_involved=persons_involved, actions_taken=actions_taken,
                       riddor_reportable=riddor_reportable, reported_by=who['username'],
                       status='under_review' if role == 'staff' else 'open',
                       subject_id=subject_id if role == 'staff' else None)
    return trips._in_transaction(conn, pending, work)


def record_system_incident(trip_id, kind, severity, description, *, reported_by='trip_management',
                           subject_id=None, location="", persons_involved="", offense_type=None):
    """Store and route an incident reported by another system (``trip_bus.record_incident``).

    No signed-in user: the caller has already decided it may report. Returns
    ``{'incident_id', 'case_id', 'hs_id', 'concern_id'}`` once routed.
    """
    trips = _trips()
    kind, severity, description = _clean(kind, severity, description)
    routed = {}
    pending = []
    with _db().write_transaction() as c:
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError("Trip not found.")
        incident_id = _insert(c, pending, trip, kind=kind, severity=severity,
                              description=description, occurred_at=None, location=location,
                              persons_involved=persons_involved, actions_taken=None,
                              riddor_reportable=None, reported_by=str(reported_by or 'system'),
                              status='open', subject_id=subject_id, offense_type=offense_type)
    # route() is the first action queued; capture what it returns.
    first, rest = pending[0], pending[1:]
    try:
        routed = first() or {}
    except Exception:
        logger.warning("routing incident %s failed", incident_id, exc_info=True)
    _db().run_after_commit(rest)
    return {'incident_id': incident_id, 'case_id': routed.get('case_id'),
            'hs_id': routed.get('hs_id'), 'concern_id': routed.get('concern_id')}


def route(incident):
    """After commit: send the incident where it must go and store the references.

    Returns ``{'hs_id', 'concern_id', 'case_id'}`` (``None`` where not routed
    or the route failed — a failure is logged and the incident stays on
    record for review).
    """
    out = {'hs_id': None, 'concern_id': None, 'case_id': None}
    kind, severity = incident['kind'], incident['severity']
    if kind == 'injury' or severity in HS_SEVERITIES or incident['riddor_reportable']:
        try:
            from education_system.systems.university.services.bus import safety_bus
            out['hs_id'] = safety_bus.record_trip_incident(incident['id'], {
                'incident_type': f"Trip {kind.replace('_', ' ')}",
                'location': incident.get('location') or incident['trip_name'],
                'incident_date': incident.get('occurred_at'),
                'severity': severity,
                'people_involved': incident.get('persons_involved'),
                'description': f"{incident['trip_name']}: {incident['description']}",
                'actions_taken': incident.get('actions_taken'),
                'reported_by': incident.get('reported_by'),
                'riddor_reportable': incident['riddor_reportable'],
            })
        except Exception:
            logger.warning("H&S routing of trip incident %s failed", incident['id'], exc_info=True)
    if kind == 'safeguarding':
        try:
            from education_system.systems.university.services.bus import trip_bus
            out['concern_id'] = trip_bus.raise_safeguarding_concern(
                reporter=incident.get('reported_by'),
                text=(f"Safeguarding concern reported on trip '{incident['trip_name']}' "
                      f"(trip:{incident['trip_id']}, incident #{incident['id']}).\n\n"
                      f"{incident['description']}\n\nPeople involved: "
                      f"{incident.get('persons_involved') or 'not recorded'}\n"
                      f"Actions taken: {incident.get('actions_taken') or 'none recorded'}"),
                severity=_CONCERN_SEVERITY[severity],
                location=incident.get('location') or f"trip:{incident['trip_id']}")
        except Exception:
            logger.warning("safeguarding routing of trip incident %s failed", incident['id'],
                           exc_info=True)
    if kind == 'conduct' and severity != 'minor' and incident.get('subject_id'):
        try:
            from education_system.systems.university.services.bus.cases_bus import open_case
            out['case_id'] = open_case(
                kind="disciplinary", subject_id=str(incident['subject_id']),
                offense_type=incident.get('offense_type') or "trip_incident:conduct", severity=_CASE_SEVERITY[severity],
                description=f"Incident on trip:{incident['trip_id']} — {incident['description']}",
                opened_by=incident.get('reported_by') or "trip_management",
                incident_date=str(incident.get('occurred_at') or '')[:10] or None,
                location=f"trip:{incident['trip_id']}")
        except Exception:
            logger.warning("disciplinary routing of trip incident %s failed", incident['id'],
                           exc_info=True)
    refs = {}
    if out['hs_id']:
        refs['hs_reference'] = f"hs_incidents:{out['hs_id']}"
    if out['concern_id']:
        refs['conduct_case_ref'] = f"safeguarding:{out['concern_id']}"
    elif out['case_id']:
        refs['conduct_case_ref'] = f"disciplinary:{out['case_id']}"
    if refs:
        try:
            with _db().write_transaction() as c:
                c.execute(f"UPDATE trip_incidents SET {', '.join(k + ' = ?' for k in refs)} WHERE id = ?",
                          (*refs.values(), incident['id']))
        except Exception:
            logger.warning("could not store routing refs on trip incident %s", incident['id'],
                           exc_info=True)
    return out


def list_incidents(auth, trip_id, conn=None):
    """The trip's incidents, newest first.

    Organisers, trip staff, ``manage_trips`` and Health & Safety
    (``approve_trips_hs``) see all; a participant sees the ones they reported.
    """
    trips = _trips()
    who = trips.actor(auth)
    with _db().read_connection(conn) as c:
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError("Trip not found.")
        role = 'staff' if auth.check_permission(REVIEW_PERMISSION) else _role_on_trip(auth, c, trip, who)
        if role is None:
            raise PermissionError("you cannot see this trip's incidents")
        if role == 'staff':
            cur = c.execute("SELECT * FROM trip_incidents WHERE trip_id = ? ORDER BY id DESC", (trip_id,))
        else:
            cur = c.execute("SELECT * FROM trip_incidents WHERE trip_id = ? AND reported_by = ? "
                            "ORDER BY id DESC", (trip_id, who['username']))
        return _rows(cur)


def review_incident(auth, incident_id, notes, close=True, *, conn=None, pending=None):
    """Review an incident: record notes and close it (or keep it under review).

    The trip's organisers, ``manage_trips`` or Health & Safety. Returns the
    incident dict.
    """
    trips = _trips()
    who = trips.actor(auth)
    notes = (notes or '').strip()
    if not notes:
        raise ValueError("record what was reviewed or done (notes)")

    def work(c, p):
        rows = _rows(c.execute("SELECT * FROM trip_incidents WHERE id = ?", (incident_id,)))
        if not rows:
            raise ValueError("incident not found")
        incident = rows[0]
        trip = trips.get_trip(incident['trip_id'], conn=c)
        if not (auth.check_permission(REVIEW_PERMISSION)
                or trips.can_manage_trip(auth, trip, conn=c, who=who)):
            raise PermissionError("only the trip's organisers or Health & Safety can review incidents")
        if incident['status'] == 'closed':
            raise ValueError("the incident is already closed")
        now = trips._now()
        status = 'closed' if close else 'under_review'
        review = "\n".join(x for x in (incident.get('review_notes'),
                                      f"[{now[:16]} {who['username']}] {notes}") if x)
        c.execute("UPDATE trip_incidents SET status = ?, reviewed_by = ?, reviewed_at = ?, "
                  "review_notes = ? WHERE id = ?", (status, who['username'], now, review, incident_id))
        trips.record_history(c, trip['id'], version=trip.get('version'), changed_by=who['username'],
                             action='incident_reviewed', field='incident',
                             new_value=f"#{incident_id} {status}")
        incident.update(status=status, reviewed_by=who['username'], reviewed_at=now,
                        review_notes=review)
        return incident
    return trips._in_transaction(conn, pending, work)
