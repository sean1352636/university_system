"""Special-category data on trip participants: medical information, dietary
requirements and accessibility needs.

These three columns are sealed at rest with the health module's sealed-field
helper (registered there as always sealed for ``trip_participants``) and are
never returned by ``registrations.list_participants`` or the trip reports.
They are read only through this module:

* :func:`may_view_medical` — the trip's own leaders (``trip_staff``
  coordinator / supervisor / medical) and its creator, the health team
  (health ``access.CLINICAL_ROLES``) and administrators;
* :func:`participant_health` — every participant's details for one trip,
  for those people; each read is written to the immutable audit log first,
  and if it can't be recorded the read is refused (fail closed);
* :func:`my_health_details` — a participant's own details.

:func:`import_from_health_record` copies a student's health profile and
emergency contacts onto their trip registration — only once they have
consented (:func:`give_health_share_consent`), and only as the student
themselves or the health team (the health portal's own access check and
audit apply).
"""

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import (
    get_text, logging, datetime,
)

logger = logging.getLogger(__name__)

SEALED_FIELDS = ('medical_info', 'dietary_requirements', 'accessibility_needs')
CONTACT_FIELDS = ('emergency_contact', 'emergency_contact_name', 'emergency_contact_phone',
                  'emergency_contact_relationship')
# trip_staff roles that see the trip's medical details.
_MEDICAL_STAFF_ROLES = ('coordinator', 'supervisor', 'medical')


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _bus():
    from education_system.systems.university.services.bus import trip_care_bus
    return trip_care_bus


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ---------------------------------------------------------------------------
# Sealing (registrations and anything else writing these columns use these)
# ---------------------------------------------------------------------------

def seal_details(values):
    """A copy of ``values`` with the special-category fields sealed."""
    present = {k: v for k, v in values.items() if k in SEALED_FIELDS}
    if not present:
        return dict(values)
    sealed = _bus().seal_values(present)
    return {**values, **sealed}


def seal_existing(conn=None):
    """Seal any plain-text values still in the three columns (rows written
    before sealing). Idempotent. Returns the number of values sealed."""
    bus = _bus()
    count = 0
    with _db().write_transaction(conn) as c:
        for column in SEALED_FIELDS:
            rows = c.execute(
                f"SELECT id, {column} FROM trip_participants WHERE {column} IS NOT NULL "  # nosec B608 - constants
                f"AND {column} <> '' AND {column} NOT LIKE 'enc1:%'").fetchall()
            for pid, value in rows:
                c.execute(f"UPDATE trip_participants SET {column} = ? WHERE id = ?",  # nosec B608
                          (bus.seal(column, value), pid))
                count += 1
    return count


def _audit(who, trip_id, details):
    """Write the access to the immutable audit log, or refuse (fail closed)."""
    from education_system.systems.university.infrastructure.security.immutable_audit_log import (
        AuditAction, log_security_event,
    )
    try:
        log_security_event(user_id=who['username'], action=AuditAction.DATA_VIEW,
                           resource_type="trip_participant_health",
                           resource_id=None if trip_id is None else str(trip_id),
                           details={**details, 'role': who['role']})
    except Exception as exc:
        raise PermissionError(get_text(
            "mobility.trip_management.medical.audit_failed",
            "The access could not be recorded, so it was refused ({error})").format(error=exc)) from None


# ---------------------------------------------------------------------------
# Who may see it
# ---------------------------------------------------------------------------

def may_view_medical(auth, trip_id, conn=None, who=None):
    """True for this trip's leaders and creator, the health team and admins."""
    if not auth or not getattr(auth, 'current_user', None):
        return False
    who = who or _trips().actor(auth)
    bus = _bus()
    if who['role'] in bus.admin_roles() or who['role'] in bus.clinical_roles():
        return True
    if who['user_id'] is None:
        return False
    with _db().read_connection(conn) as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            return False
        if trip.get('created_by') == who['user_id']:
            return True
        return c.execute(
            f"SELECT 1 FROM trip_staff WHERE trip_id = ? AND staff_user_id = ? "
            f"AND role IN ({', '.join('?' * len(_MEDICAL_STAFF_ROLES))})",
            (trip_id, who['user_id'], *_MEDICAL_STAFF_ROLES)).fetchone() is not None


def _reveal_row(row):
    bus = _bus()
    return {k: (bus.reveal(v) if k in SEALED_FIELDS else v) for k, v in row.items()}


def participant_health(auth, trip_id, *, include_ended=False):
    """Every participant's medical, dietary and accessibility details, with
    emergency contacts. Leaders, the health team and admins only; audited
    (fail closed). Returns ``[{participant_id, name, student_id, status,
    medical_info, dietary_requirements, accessibility_needs, emergency_*}]``."""
    who = _trips().actor(auth)
    db = _db()
    with db.read_connection() as c:
        if not _trips().get_trip(trip_id, conn=c):
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        if not may_view_medical(auth, trip_id, conn=c, who=who):
            raise PermissionError(get_text(
                "mobility.trip_management.medical.not_allowed",
                "Medical and dietary details are for the trip's leaders and the health team."))
        statuses = db.PARTICIPANT_STATUSES if include_ended else db.CURRENT_PARTICIPANT_STATUSES
        cur = c.execute(
            "SELECT tp.id AS participant_id, COALESCE(NULLIF(TRIM(COALESCE(s.first_name, '') || ' ' || "
            "COALESCE(s.last_name, '')), ''), u.username, tp.student_id) AS name, tp.student_id, "
            "tp.status, tp.medical_info, tp.dietary_requirements, tp.accessibility_needs, "
            "tp.emergency_contact, tp.emergency_contact_name, tp.emergency_contact_phone, "
            "tp.emergency_contact_relationship, tp.health_share_consent_at "
            "FROM trip_participants tp LEFT JOIN students s ON s.student_id = tp.student_id "
            "LEFT JOIN users u ON u.id = tp.user_id "
            f"WHERE tp.trip_id = ? AND tp.status IN ({', '.join('?' * len(statuses))}) "
            "ORDER BY name", (trip_id, *statuses))
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    _audit(who, trip_id, {'participants': [r['participant_id'] for r in rows]})
    return [_reveal_row(r) for r in rows]


def counts(trip_id):
    """How many current participants have each kind of detail recorded —
    no content, so anyone managing the trip may see it."""
    db = _db()
    statuses = db.CURRENT_PARTICIPANT_STATUSES
    with db.read_connection() as c:
        row = c.execute(
            "SELECT SUM(COALESCE(medical_info, '') <> ''), SUM(COALESCE(dietary_requirements, '') <> ''), "
            "SUM(COALESCE(accessibility_needs, '') <> '') FROM trip_participants "
            f"WHERE trip_id = ? AND status IN ({', '.join('?' * len(statuses))})",
            (trip_id, *statuses)).fetchone()
    return {'medical_info': int(row[0] or 0), 'dietary_requirements': int(row[1] or 0),
            'accessibility_needs': int(row[2] or 0)}


def _place_for(auth, c, participant_id, who):
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import registrations
    place = registrations.get_participant(participant_id, conn=c)
    if not place:
        raise ValueError(get_text("mobility.trip_management.participants.not_found",
                                  "Participant not found."))
    own = ((who['user_id'] is not None and place.get('user_id') == who['user_id'])
           or (who['student_id'] and place.get('student_id') == who['student_id']))
    return place, own


def my_health_details(auth, participant_id):
    """A participant's own details (or, for those who may view the trip's
    medical details, anyone's). Audited, fail closed."""
    who = _trips().actor(auth)
    with _db().read_connection() as c:
        place, own = _place_for(auth, c, participant_id, who)
        if not own and not may_view_medical(auth, place['trip_id'], conn=c, who=who):
            raise PermissionError(get_text(
                "mobility.trip_management.medical.not_allowed",
                "Medical and dietary details are for the trip's leaders and the health team."))
    _audit(who, place['trip_id'], {'participants': [participant_id], 'own': own})
    keep = SEALED_FIELDS + CONTACT_FIELDS + ('health_share_consent_at',)
    return _reveal_row({'participant_id': participant_id, **{k: place.get(k) for k in keep}})


def update_health_details(auth, participant_id, **fields):
    """Change a participant's medical / dietary / accessibility details or
    emergency contact — the participant themselves, or the trip's leaders /
    health team. Sealed on write. Returns True."""
    allowed = SEALED_FIELDS + CONTACT_FIELDS
    unknown = set(fields) - set(allowed)
    if unknown:
        raise ValueError(f"unknown field(s): {', '.join(sorted(unknown))}")
    if not fields:
        return True
    values = {k: (str(v).strip() or None) if v is not None else None for k, v in fields.items()}
    values = fill_contact_text(values)
    who = _trips().actor(auth)
    with _db().write_transaction() as c:
        place, own = _place_for(auth, c, participant_id, who)
        if not own and not may_view_medical(auth, place['trip_id'], conn=c, who=who):
            raise PermissionError(get_text(
                "mobility.trip_management.medical.not_allowed",
                "Medical and dietary details are for the trip's leaders and the health team."))
        sealed = seal_details(values)
        c.execute(f"UPDATE trip_participants SET {', '.join(k + ' = ?' for k in sealed)} WHERE id = ?",
                  [*sealed.values(), participant_id])
        _trips().record_history(c, place['trip_id'], version=None, changed_by=who['username'],
                                action='participant_details', field=f"participant:{participant_id}",
                                new_value=", ".join(sorted(sealed)))
    return True


def fill_contact_text(values):
    """Keep the old free-text ``emergency_contact`` filled from the
    structured name / relationship / phone when it is not given."""
    if values.get('emergency_contact'):
        return values
    name = values.get('emergency_contact_name')
    phone = values.get('emergency_contact_phone')
    if not (name or phone):
        return values
    relationship = values.get('emergency_contact_relationship')
    text = " ".join(p for p in (name, f"({relationship})" if relationship else None, phone) if p)
    return {**values, 'emergency_contact': text}


# ---------------------------------------------------------------------------
# Consent and import from the health record
# ---------------------------------------------------------------------------

def give_health_share_consent(auth, participant_id, consent=True):
    """The participant agrees (or withdraws agreement) that their health
    profile may be copied to this trip's registration."""
    who = _trips().actor(auth)
    with _db().write_transaction() as c:
        place, own = _place_for(auth, c, participant_id, who)
        if not own:
            raise PermissionError(get_text("mobility.trip_management.medical.consent_own",
                                           "Only the participant can give this consent."))
        c.execute("UPDATE trip_participants SET health_share_consent_at = ? WHERE id = ?",
                  (_now() if consent else None, participant_id))
        _trips().record_history(c, place['trip_id'], version=None, changed_by=who['username'],
                                action='health_share_consent', field=f"participant:{participant_id}",
                                new_value='given' if consent else 'withdrawn')
    return True


def _profile_text(details):
    profile = details.get('profile') or {}
    parts = []
    # The allergy register (one row each, with severity) and the profile's
    # free-text summary can both hold allergies; keep both.
    allergies = [f"{a['allergen']}{' (' + a['severity'] + ')' if a.get('severity') else ''}"
                 f"{' - ' + a['reaction'] if a.get('reaction') else ''}"
                 for a in details.get('allergies') or []]
    if profile.get('allergies') and not any(
            str(profile['allergies']).lower() in a.lower() for a in allergies):
        allergies.append(str(profile['allergies']))
    if allergies:
        parts.append("Allergies: " + "; ".join(allergies))
    for key, label in (('conditions', 'Conditions'), ('medications', 'Medications'),
                       ('blood_type', 'Blood type')):
        if profile.get(key):
            parts.append(f"{label}: {profile[key]}")
    if profile.get('doctor_name') or profile.get('doctor_phone'):
        parts.append("GP: " + " ".join(p for p in (profile.get('doctor_name'),
                                                   profile.get('doctor_phone')) if p))
    return "\n".join(parts) or None


def import_from_health_record(auth, participant_id):
    """Copy the student's health profile (allergies, conditions, medications)
    and primary emergency contact onto their trip registration.

    Only when the participant has consented (``health_share_consent_at``),
    and only as the student themselves or the health team — the health
    portal's access check applies and its audit entry is written (fail
    closed). Returns the names of the fields filled in.
    """
    who = _trips().actor(auth)
    with _db().read_connection() as c:
        place, own = _place_for(auth, c, participant_id, who)
    if not place.get('health_share_consent_at'):
        raise PermissionError(get_text(
            "mobility.trip_management.medical.no_consent",
            "The participant has not agreed to share their health record with this trip."))
    if not place.get('student_id'):
        raise ValueError("only a student's registration can be filled from the health record")
    user = dict(auth.current_user)
    user.setdefault('username', who['username'])
    if own and who['student_id'] and not user.get('student_id'):
        user['student_id'] = who['student_id']
    details = _bus().health_details_for_trip(user, place['student_id'])
    values = {}
    text = _profile_text(details)
    if text:
        values['medical_info'] = text
    contacts = details.get('contacts') or []
    if contacts:
        first = contacts[0]
        values.update(
            emergency_contact_name=first.get('contact_name') or first.get('name'),
            emergency_contact_phone=first.get('phone_primary') or first.get('phone'),
            emergency_contact_relationship=first.get('relationship'))
        values = fill_contact_text({**values, 'emergency_contact': None})
    values = {k: v for k, v in values.items() if v}
    if not values:
        return []
    sealed = seal_details(values)
    with _db().write_transaction() as c:
        c.execute(f"UPDATE trip_participants SET {', '.join(k + ' = ?' for k in sealed)} WHERE id = ?",
                  [*sealed.values(), participant_id])
        _trips().record_history(c, place['trip_id'], version=None, changed_by=who['username'],
                                action='health_import', field=f"participant:{participant_id}",
                                new_value=", ".join(sorted(sealed)))
    return sorted(sealed)
