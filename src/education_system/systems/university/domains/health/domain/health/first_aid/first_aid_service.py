"""
Tkinter-free data layer for the First Aid portal.

Holds the persistence class (``IncidentDB``) and the static emergency
contact directory, factored out of ``first_aid_portal.py`` so that
non-GUI callers (e.g. the text CLI) can reach the same
``student_records.db`` tables without importing Tkinter. The GUI portal
imports ``IncidentDB`` and ``EMERGENCY_CONTACTS`` from here, so both
front-ends share one source of truth.
"""

from __future__ import annotations

import logging
import sqlite3
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608 - identifier validation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Emergency contact directory (UK). National numbers are fixed; the campus
# numbers are the university's own, kept in ``system_settings`` (keys in
# CAMPUS_NUMBER_KEYS, edited in the portal's Registers & RIDDOR → Campus
# numbers tab) and shown as "not set" until someone enters them — the old
# directory listed invented (555) numbers.
# ---------------------------------------------------------------------------
NOT_SET = "Not set — see the campus directory"
CAMPUS_NUMBER_KEYS = {
    "campus_security": "first_aid.campus_security_phone",
    "health_centre": "first_aid.health_centre_phone",
    "wellbeing": "first_aid.wellbeing_phone",
    "first_aid_officer": "first_aid.first_aid_officer_phone",
}

EMERGENCY_CONTACTS = [
    {
        "name": "Emergency Services",
        "number": "999",
        "description": "Police, fire, ambulance and coastguard — call for any life-threatening "
                       "emergency (112 also works).",
        "location": "24/7 nationwide",
        "icon": "🚨",
        "color": "#c0392b",
    },
    {
        "key": "campus_security",
        "name": "Campus Security",
        "number": NOT_SET,
        "description": "24-hour campus security and first response team. Call them as well "
                       "as 999 so they can meet the ambulance.",
        "location": "Security Office, Main Gate",
        "icon": "🛡",
        "color": "#2c3e50",
    },
    {
        "key": "health_centre",
        "name": "University Health Centre",
        "number": NOT_SET,
        "description": "Medical care for students and staff. Walk-in and appointments available.",
        "location": "Building H, Ground Floor",
        "icon": "🏥",
        "color": "#27ae60",
    },
    {
        "name": "NHS 111",
        "number": "111",
        "description": "Urgent medical advice when it is not a 999 emergency, including "
                       "poisoning and overdose advice (also online at 111.nhs.uk).",
        "location": "National 24/7 line",
        "icon": "☎",
        "color": "#8e44ad",
    },
    {
        "name": "Samaritans",
        "number": "116 123",
        "description": "Free, confidential emotional support, any time. Text SHOUT to 85258 "
                       "for the Shout text service.",
        "location": "National 24/7 line",
        "icon": "💙",
        "color": "#2980b9",
    },
    {
        "key": "wellbeing",
        "name": "Student Wellbeing Service",
        "number": NOT_SET,
        "description": "Confidential counselling and mental health support for students.",
        "location": "Student Services, Building C",
        "icon": "💬",
        "color": "#16a085",
    },
    {
        "key": "first_aid_officer",
        "name": "Campus First Aid Officer",
        "number": NOT_SET,
        "description": "On-duty first aider for minor incidents. See Registers & RIDDOR for "
                       "first aiders by location.",
        "location": "Rotating locations",
        "icon": "⚕",
        "color": "#e67e22",
    },
]


def campus_numbers(conn=None) -> dict:
    """``key -> number`` for the campus lines that have been set."""
    own = conn is None
    if own:
        try:
            from education_system.systems.university.domains.health.infrastructure.health.storage import (
                get_connection,
            )
            conn = get_connection()
        except Exception:
            return {}
    try:
        keys = list(CAMPUS_NUMBER_KEYS.values())
        rows = conn.execute(
            f"SELECT key, COALESCE(value, setting_value) FROM system_settings "  # nosec B608
            f"WHERE key IN ({','.join('?' * len(keys))})", keys).fetchall()
        by_setting = {r[0]: r[1] for r in rows if r[1]}
        return {k: by_setting[v] for k, v in CAMPUS_NUMBER_KEYS.items() if v in by_setting}
    except sqlite3.Error:
        return {}
    finally:
        if own:
            conn.close()


def set_campus_number(key, number, conn=None) -> None:
    if key not in CAMPUS_NUMBER_KEYS:
        raise ValueError(f"Unknown campus line {key!r}")
    own = conn is None
    if own:
        from education_system.systems.university.domains.health.infrastructure.health.storage import (
            get_connection,
        )
        conn = get_connection()
    try:
        conn.execute("INSERT INTO system_settings (key, value, description, last_modified) "
                     "VALUES (?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT (key) DO UPDATE SET "
                     "value = excluded.value, last_modified = CURRENT_TIMESTAMP",
                     (CAMPUS_NUMBER_KEYS[key], str(number or "").strip() or None,
                      "First aid portal: campus phone number"))
        conn.commit()
    finally:
        if own:
            conn.close()


def emergency_contacts(conn=None) -> list[dict]:
    """The directory with the campus numbers that have been set filled in."""
    numbers = campus_numbers(conn)
    out = []
    for contact in EMERGENCY_CONTACTS:
        entry = dict(contact)
        if entry.get("key") in numbers:
            entry["number"] = numbers[entry["key"]]
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
class IncidentDB:
    """Persists first-aid incident reports in the central
    `student_records.db`. Creates the `first_aid_incidents` table on
    demand."""

    def __init__(self):
        try:
            from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection
            self._connect = get_connection
        except Exception:
            logger.exception("Could not import central get_connection")
            raise
        self._ensure_schema()

    def _connection(self):
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        # One schema for first aid (incidents with RIDDOR, first-aider
        # register, kits/AEDs, course sessions): infrastructure/health/
        # first_aid_schema, also applied by migration 9c1e3a5d7f0b.
        from education_system.systems.university.domains.health.infrastructure.health import (
            first_aid_schema,
        )
        conn = self._connection()
        try:
            first_aid_schema.apply_to_connection(conn)
        finally:
            conn.close()

    @staticmethod
    def _has_column(conn, table, column):
        # db-audit: ignore[DBW001] - parameter passed through a validator
        # Identifiers cannot be parameterised, so they are validated instead.
        table = validate_identifier(table)
        column = validate_identifier(column)
        try:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return any((r["name"] if isinstance(r, sqlite3.Row) else r[1]) == column
                       for r in rows)
        except sqlite3.Error:
            return False

    def add_registration(self, reg: dict) -> int:
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO first_aid_training_registrations
                   (submitted_at, course, user_id, name, email, phone,
                    preferred_date, notes, session_id)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (reg['submitted_at'], reg['course'], reg.get('user_id', ''),
                 reg['name'], reg.get('email', ''), reg.get('phone', ''),
                 reg.get('preferred_date', ''), reg.get('notes', ''),
                 reg.get('session_id')),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def add(self, report: dict) -> int:
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO first_aid_incidents
                   (submitted_at, reporter_user, reporter_name, reporter_id,
                    phone, email, location, incident_type, severity,
                    description, status, incident_date, person_type)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (report['submitted_at'], report.get('reporter_user', ''),
                 report['reporter_name'], report.get('reporter_id', ''),
                 report.get('phone', ''), report.get('email', ''),
                 report.get('location', ''),
                 report.get('incident_type', ''), report.get('severity', ''),
                 report['description'], report.get('status', 'Open'),
                 report.get('incident_date') or str(report['submitted_at'])[:10],
                 report.get('person_type') or None),
            )
            conn.commit()
            new_id = cur.lastrowid
        finally:
            conn.close()

        # Bus broadcast (#2). Lets H&S link this treatment to a parent
        # incident, the chatbot proactively notify managers, and DM
        # offer an evidence-pack slot.
        try:
            from education_system.systems.university.infrastructure.event_bus import (
                publish, EVENT_INCIDENT_LOGGED,
            )
            publish(
                EVENT_INCIDENT_LOGGED,
                incident_id=new_id, domain="first_aid",
                incident_type=report.get('incident_type', ''),
                severity=report.get('severity', ''),
                location=report.get('location', ''),
                reporter_id=report.get('reporter_id', ''),
                reporter_name=report.get('reporter_name', ''),
                description=report.get('description', ''),
            )
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        # Cross-domain: a serious incident becomes a Health & Safety
        # incident (hs_incidents) for the H&S team to investigate the event,
        # with the coordinators told and RIDDOR assessment due. (It used to
        # open a cases_bus case against the *reporter*, which landed in
        # disciplinary_records.)
        sev = str(report.get('severity', '')).lower()
        if sev in ('high', 'critical', 'severe'):
            try:
                from education_system.systems.university.services.bus import safety_bus
                safety_bus.record_first_aid_incident(new_id, report)
            except Exception:
                logger.exception("Could not open the H&S incident for first-aid incident %s",
                                 new_id)

        # Cross-domain: location rollup. Three or more incidents at
        # the same location within 90 days indicates a site-level
        # safety risk — raise a risks row tagged by location so the
        # legal/risk GUI surfaces the pattern. Idempotent: only
        # raised once per (location, 90-day window).
        loc = (report.get('location') or '').strip()
        if loc:
            try:
                conn2 = self._connection()
                try:
                    row = conn2.execute(
                        "SELECT COUNT(*) FROM first_aid_incidents "
                        "WHERE location = ? AND COALESCE(archived, 0) = 0 "
                        "  AND submitted_at >= date('now', '-90 days')",
                        (loc,),
                    ).fetchone()
                    incident_count = int(row[0] or 0) if row else 0
                finally:
                    conn2.close()
                if incident_count >= 3:
                    from education_system.systems.university.services.bus import (
                        risk_bus,
                    )
                    ref = f"location:{loc.lower().replace(' ','_')[:60]}"
                    if not risk_bus.list_risks_for(ref):
                        risk_bus.raise_risk(
                            title=f"Repeated first-aid incidents: {loc}",
                            category="Safety",
                            department="Health & Safety",
                            description=(
                                f"{incident_count} first-aid incidents "
                                f"recorded at '{loc}' in the last 90 "
                                f"days. Investigate site hazards, "
                                f"signage, and staffing."
                            ),
                            likelihood=4, impact=3,
                            reference_id=ref,
                        )
            except Exception as exc:
                logger.debug("location rollup risk failed: %s", exc)

        return new_id

    def fetch_all(self, severity: str | None = None,
                  status: str | None = None, include_archived: bool = False) -> list:
        """Return incident rows, newest first. Optionally filter by
        ``severity`` and/or ``status`` (case-insensitive). Archived incidents
        (``application/health/first_aid.archive_incident``) are left out
        unless ``include_archived``."""
        sql = "SELECT * FROM first_aid_incidents"
        clauses, params = [], []
        if not include_archived:
            clauses.append("COALESCE(archived, 0) = 0")
        if severity:
            clauses.append("LOWER(severity) = ?")
            params.append(severity.lower())
        if status:
            clauses.append("LOWER(COALESCE(status, 'Open')) = ?")
            params.append(status.lower())
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC"
        conn = self._connection()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def update_status(self, incident_id: int, status: str) -> bool:
        """Set the workflow status of an incident (e.g. Open/Resolved)."""
        conn = self._connection()
        try:
            cur = conn.execute(
                "UPDATE first_aid_incidents SET status = ? WHERE id = ?",
                (status, incident_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def fetch_registrations(self) -> list:
        """Return all course/training registrations, newest first."""
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM first_aid_training_registrations "
                "ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]
