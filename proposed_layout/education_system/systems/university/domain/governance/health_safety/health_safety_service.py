"""
Tkinter-free data layer for the Health & Safety portal.

Holds ``HSDatabase``, factored out of ``health_safety_portal.py`` so that
non-GUI callers (e.g. the text CLI) can reach the same
``student_records.db`` tables — ``hs_incidents``, ``hs_hazards`` and
``hs_training`` — without importing Tkinter. The GUI portal imports
``HSDatabase`` from here, so both front-ends share one source of truth.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class HSDatabase:
    """Wraps the central `student_records.db` for incidents, hazards,
    and training records. Tables are created on demand."""

    def __init__(self):
        from education_system.systems.university.infrastructure.database.db import get_connection
        self._connect = get_connection
        self._ensure_schema()

    def _connection(self):
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        conn = self._connection()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS hs_incidents (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ref             TEXT,
                    incident_type   TEXT,
                    location        TEXT,
                    incident_date   TEXT,
                    severity        TEXT,
                    people_involved TEXT,
                    description     TEXT,
                    actions_taken   TEXT,
                    reported_by     TEXT,
                    department      TEXT,
                    status          TEXT DEFAULT 'Open',
                    reported_at     TEXT NOT NULL,
                    updated_at      TEXT
                );
                CREATE TABLE IF NOT EXISTS hs_hazards (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ref             TEXT,
                    category        TEXT,
                    location        TEXT,
                    risk_level      TEXT,
                    description     TEXT,
                    mitigation      TEXT,
                    reported_by     TEXT,
                    department      TEXT,
                    status          TEXT DEFAULT 'Active',
                    reported_at     TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hs_training (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user            TEXT NOT NULL,
                    module          TEXT NOT NULL,
                    department      TEXT,
                    completed_at    TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    # --- incidents ------------------------------------------------------
    def list_incidents(self) -> list:
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM hs_incidents ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def add_incident(self, data: dict) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO hs_incidents
                   (ref, incident_type, location, incident_date, severity,
                    people_involved, description, actions_taken,
                    reported_by, department, status, reported_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data.get('ref'), data.get('incident_type'), data.get('location'),
                 data.get('incident_date'), data.get('severity'),
                 data.get('people_involved'), data.get('description'),
                 data.get('actions_taken'), data.get('reported_by'),
                 data.get('department'), data.get('status', 'Open'), now),
            )
            conn.commit()
            new_id = cur.lastrowid
        finally:
            conn.close()

        # Bus broadcast (#2): subscribers (First Aid, Finance, DM,
        # chatbot) link, charge, attach evidence, and notify managers.
        try:
            from education_system.systems.university.interfaces.gui.academics._event_bus import (
                publish, EVENT_INCIDENT_LOGGED,
            )
            publish(
                EVENT_INCIDENT_LOGGED,
                incident_id=new_id, domain="hs",
                ref=data.get('ref'),
                incident_type=data.get('incident_type'),
                severity=data.get('severity'),
                location=data.get('location'),
                department=data.get('department'),
                reported_by=data.get('reported_by'),
                description=data.get('description'),
            )
        except Exception:
            pass

        # Finance link (#7) — if the incident carries an estimated cost,
        # post it as a charge against the responsible department.
        cost = data.get('estimated_cost') or data.get('cost')
        if cost:
            try:
                amount = float(cost)
                if amount > 0:
                    from education_system.systems.university.services.bus.finance_bus import (
                        raise_charge,
                    )
                    raise_charge(
                        data.get('reported_by') or 'department',
                        amount,
                        source="hs_incident",
                        description=(
                            f"H&S incident #{new_id} ("
                            f"{data.get('incident_type') or 'incident'})"
                        ),
                        reference_id=f"incident:{new_id}",
                        processed_by="health_safety_portal",
                    )
            except Exception:
                pass

        return new_id

    def schedule_evacuation_drill(self, *, drill_date: str,
                                  location: str | None = None,
                                  description: str | None = None,
                                  scheduled_by: str | None = None) -> str | None:
        """Persist an evacuation drill as a Calendar event (#8).

        Single source for "what's happening on what day" — the drill
        shows up automatically in the Academic Calendar GUI; H&S
        doesn't run its own drill scheduler.
        """
        try:
            from education_system.systems.university.infrastructure.database.db import (
                get_connection,
            )
            import uuid
            event_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO academic_calendar_events "
                    "(id, name, date, description, event_type, "
                    " date_added, last_modified, created_by) "
                    "VALUES (?, ?, ?, ?, 'evacuation_drill', ?, ?, ?)",
                    (event_id,
                     f"Evacuation drill — {location or 'campus'}",
                     drill_date,
                     description or "Scheduled evacuation drill",
                     now, now, scheduled_by),
                )
                conn.commit()
            try:
                from education_system.systems.university.interfaces.gui.academics._event_bus import (
                    publish, EVENT_CALENDAR_CHANGED,
                )
                publish(EVENT_CALENDAR_CHANGED, event_id=event_id,
                        event_type="evacuation_drill", action="created",
                        date=drill_date)
            except Exception:
                pass
            return event_id
        except Exception as exc:
            logger.warning("schedule_evacuation_drill failed: %s", exc)
            return None

    def update_incident_status(self, incident_id: int, status: str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            conn.execute(
                "UPDATE hs_incidents SET status=?, updated_at=? WHERE id=?",
                (status, now, incident_id))
            conn.commit()
        finally:
            conn.close()

    # --- hazards --------------------------------------------------------
    def list_hazards(self) -> list:
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM hs_hazards ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def add_hazard(self, data: dict) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO hs_hazards
                   (ref, category, location, risk_level, description,
                    mitigation, reported_by, department, status, reported_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (data.get('ref'), data.get('category'), data.get('location'),
                 data.get('risk_level'), data.get('description'),
                 data.get('mitigation'), data.get('reported_by'),
                 data.get('department'), data.get('status', 'Active'), now),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update_hazard_status(self, hazard_id: int, status: str) -> bool:
        """Set the workflow status of a hazard (e.g. Active/Completed).

        Persists to the existing ``hs_hazards.status`` column; used by the
        CLI to mark a reported hazard as resolved/completed.
        """
        conn = self._connection()
        try:
            cur = conn.execute(
                "UPDATE hs_hazards SET status=? WHERE id=?",
                (status, hazard_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # --- training -------------------------------------------------------
    def list_training(self) -> list:
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM hs_training ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def add_training(self, data: dict) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            cur = conn.execute(
                "INSERT INTO hs_training (user, module, department, completed_at) "
                "VALUES (?,?,?,?)",
                (data['user'], data['module'], data.get('department', ''), now))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
