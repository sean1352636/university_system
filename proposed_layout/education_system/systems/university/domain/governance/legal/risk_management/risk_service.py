"""
University Risk Management — data / persistence layer (GUI-free).

The risk-register domain model (:class:`Risk`), the persistence wrapper
(:class:`RiskDB`) and the shared constants used to live inside
``university_risk_management.py`` alongside the Tkinter GUI. They are
factored out here so non-GUI callers (the interactive CLI, the REST API,
tests) can reuse the *exact same* SQL without importing Tkinter.

Rows live in the central ``student_records.db`` ``risks`` table, reached
via ``infrastructure.database.db.get_connection`` — the same database and
table the Risk Management GUI reads and writes, so anything created here
is visible in the GUI and vice-versa.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Academic",
    "Financial",
    "IT / Cybersecurity",
    "Health & Safety",
    "Compliance / Legal",
    "Reputational",
    "Operational",
    "Research",
    "Student Affairs",
    "Facilities",
]

DEPARTMENTS = [
    "Administration",
    "Registrar",
    "Finance",
    "IT Services",
    "Human Resources",
    "Facilities Management",
    "Library",
    "Research Office",
    "Student Services",
    "Faculty of Arts",
    "Faculty of Science",
    "Faculty of Engineering",
    "Faculty of Medicine",
    "Faculty of Business",
]

STATUSES = ["Open", "In Progress", "Mitigated", "Accepted", "Closed"]

LIKELIHOOD_LEVELS = {
    1: "Rare",
    2: "Unlikely",
    3: "Possible",
    4: "Likely",
    5: "Almost Certain",
}

IMPACT_LEVELS = {
    1: "Insignificant",
    2: "Minor",
    3: "Moderate",
    4: "Major",
    5: "Catastrophic",
}


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


@dataclass
class Risk:
    id: Optional[int]
    title: str
    category: str
    department: str
    description: str
    likelihood: int
    impact: int
    status: str
    owner: str
    mitigation: str
    created: str
    updated: str

    @property
    def score(self) -> int:
        return self.likelihood * self.impact

    @property
    def rating(self) -> str:
        s = self.score
        if s >= 20:
            return "Critical"
        if s >= 12:
            return "High"
        if s >= 6:
            return "Medium"
        return "Low"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class RiskDB:
    """Thin wrapper around the central ``student_records.db``.

    The ``risks`` table is part of the canonical schema; this class assumes
    it exists and only ever inserts/reads from it. A short-lived
    connection is opened per call to play nicely with the shared WAL
    pool used elsewhere in the app.
    """

    def __init__(self):
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
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
        # `risks` is in the canonical schema; CREATE IF NOT EXISTS is a
        # belt-and-braces guard for fresh dev DBs that haven't run the
        # full migration set.
        conn = self._connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL,
                    category    TEXT NOT NULL,
                    department  TEXT NOT NULL,
                    description TEXT,
                    likelihood  INTEGER NOT NULL CHECK(likelihood BETWEEN 1 AND 5),
                    impact      INTEGER NOT NULL CHECK(impact BETWEEN 1 AND 5),
                    status      TEXT NOT NULL,
                    owner       TEXT,
                    mitigation  TEXT,
                    created     TEXT NOT NULL,
                    updated     TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    # -- CRUD ---------------------------------------------------------------

    def add(self, r: Risk) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            cur = conn.execute(
                """INSERT INTO risks
                   (title, category, department, description, likelihood, impact,
                    status, owner, mitigation, created, updated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (r.title, r.category, r.department, r.description, r.likelihood,
                 r.impact, r.status, r.owner, r.mitigation, now, now),
            )
            conn.commit()
            new_id = cur.lastrowid
            logger.info("Risk added id=%s title=%r owner=%r score=%s",
                        new_id, r.title, r.owner, r.likelihood * r.impact)
        finally:
            conn.close()

        # Cross-domain: publish a 'risk.raised' bus event so other
        # subscribers (calendar, dashboards) see the new entry. If
        # the Risk model has a next_review_date attribute set, also
        # publish a calendar row for that review.
        try:
            from education_system.systems.university.services.bus import (
                risk_bus,
            )
            from education_system.systems.university.interfaces.gui.academics._event_bus import publish
            publish("risk.raised",
                    risk_id=new_id, category=r.category,
                    likelihood=r.likelihood, impact=r.impact)
            review_date = getattr(r, 'next_review_date', None)
            if review_date:
                risk_bus.set_review_date(new_id, review_date)
        except Exception:
            pass

        return new_id

    def update(self, r: Risk):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection()
        try:
            conn.execute(
                """UPDATE risks SET
                     title=?, category=?, department=?, description=?,
                     likelihood=?, impact=?, status=?, owner=?, mitigation=?,
                     updated=?
                   WHERE id=?""",
                (r.title, r.category, r.department, r.description, r.likelihood,
                 r.impact, r.status, r.owner, r.mitigation, now, r.id),
            )
            conn.commit()
            logger.info("Risk updated id=%s title=%r status=%s", r.id, r.title, r.status)
        finally:
            conn.close()

    def delete(self, risk_id: int):
        conn = self._connection()
        try:
            conn.execute("DELETE FROM risks WHERE id=?", (risk_id,))
            conn.commit()
            logger.info("Risk deleted id=%s", risk_id)
        finally:
            conn.close()

    def fetch_all(self, search: str = "", category: str = "All",
                  status: str = "All") -> list[Risk]:
        query = "SELECT * FROM risks WHERE 1=1"
        params: list = []
        if search:
            query += " AND (title LIKE ? OR description LIKE ? OR owner LIKE ?)"
            like = f"%{search}%"
            params += [like, like, like]
        if category != "All":
            query += " AND category=?"
            params.append(category)
        if status != "All":
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY (likelihood*impact) DESC, id DESC"
        conn = self._connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_risk(row) for row in rows]

    def fetch(self, risk_id: int) -> Optional[Risk]:
        conn = self._connection()
        try:
            row = conn.execute(
                "SELECT * FROM risks WHERE id=?", (risk_id,)
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_risk(row) if row else None

    def stats(self) -> dict:
        by_rating = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        by_status = {s: 0 for s in STATUSES}
        by_category = {cat: 0 for cat in CATEGORIES}
        conn = self._connection()
        try:
            c = conn.cursor()
            total = c.execute("SELECT COUNT(*) FROM risks").fetchone()[0]
            rows = c.execute("SELECT likelihood, impact, status, category FROM risks").fetchall()
        finally:
            conn.close()
        for row in rows:
            score = row[0] * row[1]
            if score >= 20:
                by_rating["Critical"] += 1
            elif score >= 12:
                by_rating["High"] += 1
            elif score >= 6:
                by_rating["Medium"] += 1
            else:
                by_rating["Low"] += 1
            by_status[row[2]] = by_status.get(row[2], 0) + 1
            by_category[row[3]] = by_category.get(row[3], 0) + 1
        return {
            "total": total,
            "by_rating": by_rating,
            "by_status": by_status,
            "by_category": by_category,
        }

    @staticmethod
    def _row_to_risk(row: sqlite3.Row) -> Risk:
        return Risk(
            id=row["id"],
            title=row["title"],
            category=row["category"],
            department=row["department"],
            description=row["description"] or "",
            likelihood=row["likelihood"],
            impact=row["impact"],
            status=row["status"],
            owner=row["owner"] or "",
            mitigation=row["mitigation"] or "",
            created=row["created"],
            updated=row["updated"],
        )
