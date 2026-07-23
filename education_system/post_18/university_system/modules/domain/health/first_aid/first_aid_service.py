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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static emergency contact directory (display-only reference data).
# ---------------------------------------------------------------------------
EMERGENCY_CONTACTS = [
    {
        "name": "Emergency Services",
        "number": "911",
        "description": "Police, fire, and ambulance — call for any life-threatening emergency.",
        "location": "24/7 nationwide",
        "icon": "🚨",
        "color": "#c0392b",
    },
    {
        "name": "Campus Security",
        "number": "(555) 123-9999",
        "description": "24-hour campus security and first response team.",
        "location": "Security Office, Main Gate",
        "icon": "🛡",
        "color": "#2c3e50",
    },
    {
        "name": "University Health Center",
        "number": "(555) 123-4567",
        "description": "Medical care for students and staff. Walk-in and appointments available.",
        "location": "Building H, Ground Floor",
        "icon": "🏥",
        "color": "#27ae60",
    },
    {
        "name": "Mental Health Hotline",
        "number": "(555) 123-7777",
        "description": "24/7 confidential counselling and mental health support for students.",
        "location": "Student Services, Building C",
        "icon": "💙",
        "color": "#2980b9",
    },
    {
        "name": "Poison Control",
        "number": "1-800-222-1222",
        "description": "Immediate advice for poisoning and overdose emergencies.",
        "location": "National 24/7 hotline",
        "icon": "☠",
        "color": "#8e44ad",
    },
    {
        "name": "Campus First Aid Officer",
        "number": "(555) 123-4580",
        "description": "On-duty certified first aid responder for minor incidents.",
        "location": "Rotating locations — see app",
        "icon": "⚕",
        "color": "#e67e22",
    },
]


# ---------------------------------------------------------------------------
# DATA LAYER
# ---------------------------------------------------------------------------
class IncidentDB:
    """Persists first-aid incident reports in the central
    `student_records.db`. Creates the `first_aid_incidents` table on
    demand."""

    def __init__(self):
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
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
        conn = self._connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS first_aid_incidents (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    submitted_at    TEXT NOT NULL,
                    reporter_user   TEXT,
                    reporter_name   TEXT NOT NULL,
                    reporter_id     TEXT,
                    phone           TEXT,
                    email           TEXT,
                    location        TEXT,
                    incident_type   TEXT,
                    severity        TEXT,
                    description     TEXT NOT NULL,
                    status          TEXT DEFAULT 'Open'
                )
                """
            )
            # Migrate older databases that predate the email/status columns.
            for col, ddl in (
                ("email", "ALTER TABLE first_aid_incidents ADD COLUMN email TEXT"),
                ("status", "ALTER TABLE first_aid_incidents "
                           "ADD COLUMN status TEXT DEFAULT 'Open'"),
            ):
                if not self._has_column(conn, "first_aid_incidents", col):
                    try:
                        conn.execute(ddl)
                    except sqlite3.Error:
                        logger.debug("Could not add %s column", col, exc_info=True)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS first_aid_training_registrations (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    submitted_at    TEXT NOT NULL,
                    course          TEXT NOT NULL,
                    user_id         TEXT,
                    name            TEXT NOT NULL,
                    email           TEXT,
                    phone           TEXT,
                    preferred_date  TEXT,
                    notes           TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _has_column(conn, table, column):
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
                    preferred_date, notes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (reg['submitted_at'], reg['course'], reg.get('user_id', ''),
                 reg['name'], reg.get('email', ''), reg.get('phone', ''),
                 reg.get('preferred_date', ''), reg.get('notes', '')),
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
                    description, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (report['submitted_at'], report.get('reporter_user', ''),
                 report['reporter_name'], report.get('reporter_id', ''),
                 report.get('phone', ''), report.get('email', ''),
                 report.get('location', ''),
                 report.get('incident_type', ''), report.get('severity', ''),
                 report['description'], report.get('status', 'Open')),
            )
            conn.commit()
            new_id = cur.lastrowid
        finally:
            conn.close()

        # Bus broadcast (#2). Lets H&S link this treatment to a parent
        # incident, the chatbot proactively notify managers, and DM
        # offer an evidence-pack slot.
        try:
            from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import (
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
            pass

        # Cross-domain: severe incidents open a cases_bus hs_incident
        # case so they inherit hearing scheduling, sanction routing,
        # and the auto-raised risk-register row (8.109.0). Minor
        # treatments stay first-aid-only.
        sev = str(report.get('severity', '')).lower()
        if sev in ('high', 'critical', 'severe'):
            try:
                from education_system.post_18.university_system.modules.services import (
                    cases_bus,
                )
                subject = (str(report.get('reporter_id', ''))
                           or str(report.get('reporter_user', ''))
                           or f"first_aid:{new_id}")
                cases_bus.open_case(
                    kind="hs_incident",
                    subject_id=subject,
                    opened_by=str(report.get('reporter_user', ''))
                              or "first_aid_portal",
                    description=(
                        f"First-aid {report.get('incident_type','incident')} "
                        f"({sev}) at {report.get('location','—')}. "
                        f"{report.get('description','')}"
                    ),
                    severity=str(report.get('severity', '')).title(),
                    offense_type=report.get('incident_type', 'Incident'),
                    incident_date=str(report.get('submitted_at', ''))[:10],
                    location=report.get('location'),
                )
            except Exception as exc:
                logger.debug("hs_incident case open failed: %s", exc)

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
                        "WHERE location = ? "
                        "  AND submitted_at >= date('now', '-90 days')",
                        (loc,),
                    ).fetchone()
                    incident_count = int(row[0] or 0) if row else 0
                finally:
                    conn2.close()
                if incident_count >= 3:
                    from education_system.post_18.university_system.modules.services import (
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
                  status: str | None = None) -> list:
        """Return incident rows, newest first. Optionally filter by
        ``severity`` and/or ``status`` (case-insensitive)."""
        sql = "SELECT * FROM first_aid_incidents"
        clauses, params = [], []
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
