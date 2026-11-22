"""Retention of trip participants' personal details.

Medical information, dietary requirements, accessibility needs, emergency
contacts, passport expiry and visa status are needed for the trip and a
short while after (follow-up, claims). :func:`purge_due` clears them for
trips that ended more than ``months`` ago (default six), and the name of
whoever gave parental consent (the consent timestamps are kept as the
record that consent was given). ``trips.data_purged_at`` records when.
Incidents are not touched — they are kept for three years under the
incident rules. Run daily by the scheduled trip jobs.
"""

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import (
    logging, datetime,
)

logger = logging.getLogger(__name__)

RETENTION_MONTHS = 6
PURGED_COLUMNS = ('medical_info', 'dietary_requirements', 'accessibility_needs',
                  'emergency_contact', 'emergency_contact_name', 'emergency_contact_phone',
                  'emergency_contact_relationship', 'passport_expiry', 'visa_status',
                  'parental_consent_by')
ACTOR = 'system:trip-retention'


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def cutoff(now=None, months=RETENTION_MONTHS):
    """The date (YYYY-MM-DD) before which a trip's end means its data is due."""
    now = now or datetime.now()
    month = now.month - int(months)
    year = now.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(now.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
                        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return f"{year:04d}-{month:02d}-{day:02d}"


def due_trips(now=None, months=RETENTION_MONTHS, conn=None):
    """Trips that ended before the cutoff and have not been purged."""
    with _db().read_connection(conn) as c:
        return [dict(zip(('id', 'trip_name', 'end_date'), tuple(r))) for r in c.execute(
            "SELECT id, trip_name, COALESCE(end_date, start_date) FROM trips "
            "WHERE data_purged_at IS NULL AND substr(COALESCE(end_date, start_date), 1, 10) < ? "
            "AND status NOT IN ('open', 'full', 'in_progress') ORDER BY id",
            (cutoff(now, months),)).fetchall()]


def purge_due(now=None, months=RETENTION_MONTHS):
    """Clear the personal details on every trip due (see the module
    docstring). Returns ``{'trips': [ids], 'participants': n}``."""
    now = now or datetime.now()
    stamp = now.strftime('%Y-%m-%d %H:%M:%S')
    purged, cleared = [], 0
    for trip in due_trips(now, months):
        with _db().write_transaction() as c:
            row = c.execute("SELECT version, data_purged_at FROM trips WHERE id = ?",
                            (trip['id'],)).fetchone()
            if not row or row[1]:
                continue
            n = c.execute(
                f"UPDATE trip_participants SET {', '.join(col + ' = NULL' for col in PURGED_COLUMNS)} "
                "WHERE trip_id = ?", (trip['id'],)).rowcount
            c.execute("UPDATE trips SET data_purged_at = ? WHERE id = ?", (stamp, trip['id']))
            _trips().record_history(c, trip['id'], version=row[0], changed_by=ACTOR,
                                    action='data_purged', field='participants',
                                    new_value=f"{n} participant record(s); kept {months} months")
        purged.append(trip['id'])
        cleared += n
        _audit(trip['id'], n, months)
    if purged:
        logger.info("Trip retention: cleared personal details on trips %s", purged)
    return {'trips': purged, 'participants': cleared}


def _audit(trip_id, count, months):
    try:
        from education_system.systems.university.infrastructure.security.immutable_audit_log import (
            log_security_event,
        )
        log_security_event(user_id=ACTOR, action='DATA_PURGE',
                           resource_type='trip_participant_health', resource_id=str(trip_id),
                           details={'participants': count, 'retention_months': months,
                                    'columns': list(PURGED_COLUMNS)})
    except Exception:
        # The purge itself is recorded in trip_history; the audit entry is extra.
        logger.warning("Trip %s purge not written to the audit log", trip_id, exc_info=True)
