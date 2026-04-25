"""Outcomes layer for early-warning interventions.

The university `early_warning_interventions` table tracks *that* an
intervention exists, who it's assigned to, and when it was completed.
This module adds the *measurement* layer: pre/post assessment scores,
session-by-session attendance logging, value-added calculation, and
roll-up summaries.

Two new tables, both keyed off the existing `intervention_id`:

- `intervention_outcomes`  : 1:1 with intervention — baseline & post scores,
                             session totals, computed value_added.
- `intervention_sessions`  : 1:many session log rows.

The early-warning module is left untouched; this service is additive.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class InterventionOutcomesError(Exception):
    """Raised for any outcomes data or workflow failure."""


_VALID_SESSION_STATUS = {"attended", "missed", "cancelled", "rescheduled"}


class InterventionOutcomesService:
    """Pre/post scoring + session tracking for early-warning interventions."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path
        self.init_schema()

    def _conn(self):
        return get_connection(self._db_path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS intervention_outcomes (
                    intervention_id INTEGER PRIMARY KEY,
                    subject_area TEXT,
                    sessions_total INTEGER DEFAULT 0,
                    sessions_completed INTEGER DEFAULT 0,
                    pre_assessment_score REAL,
                    pre_assessment_date TEXT,
                    post_assessment_score REAL,
                    post_assessment_date TEXT,
                    value_added REAL,
                    impact_notes TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (intervention_id)
                        REFERENCES early_warning_interventions (intervention_id)
                );

                CREATE TABLE IF NOT EXISTS intervention_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intervention_id INTEGER NOT NULL,
                    session_date TEXT NOT NULL,
                    duration_minutes INTEGER,
                    status TEXT DEFAULT 'attended',
                    notes TEXT,
                    recorded_by TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (intervention_id)
                        REFERENCES early_warning_interventions (intervention_id)
                );

                CREATE INDEX IF NOT EXISTS idx_intervention_sessions_iid
                    ON intervention_sessions (intervention_id);
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ymd(value: str, field: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except (TypeError, ValueError) as exc:
            raise InterventionOutcomesError(
                f"{field} must be YYYY-MM-DD",
            ) from exc
        return value

    def _ensure_intervention(self, intervention_id: int) -> None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM early_warning_interventions WHERE intervention_id = ?",
                (intervention_id,),
            ).fetchone()
            if not row:
                raise InterventionOutcomesError(
                    f"intervention {intervention_id} not found",
                )

    def _upsert_outcome(self, intervention_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO intervention_outcomes (intervention_id) VALUES (?)",
                (intervention_id,),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Baseline / outcome
    # ------------------------------------------------------------------

    def set_baseline(
        self,
        intervention_id: int,
        pre_assessment_score: float,
        subject_area: Optional[str] = None,
        sessions_total: Optional[int] = None,
        pre_assessment_date: Optional[str] = None,
    ) -> dict:
        """Record the pre-intervention baseline."""
        self._ensure_intervention(intervention_id)
        if pre_assessment_date:
            pre_assessment_date = self._ymd(pre_assessment_date, "pre_assessment_date")
        else:
            pre_assessment_date = datetime.now().strftime("%Y-%m-%d")
        if sessions_total is not None and sessions_total < 0:
            raise InterventionOutcomesError("sessions_total must be >= 0")
        self._upsert_outcome(intervention_id)
        with self._conn() as conn:
            sets = ["pre_assessment_score = ?", "pre_assessment_date = ?",
                    "updated_at = datetime('now')"]
            params: list = [pre_assessment_score, pre_assessment_date]
            if subject_area is not None:
                sets.append("subject_area = ?")
                params.append(subject_area)
            if sessions_total is not None:
                sets.append("sessions_total = ?")
                params.append(sessions_total)
            params.append(intervention_id)
            conn.execute(
                f"UPDATE intervention_outcomes SET {', '.join(sets)} "
                "WHERE intervention_id = ?",
                params,
            )
            conn.commit()
        return self.get_outcome(intervention_id)

    def set_outcome(
        self,
        intervention_id: int,
        post_assessment_score: float,
        post_assessment_date: Optional[str] = None,
        impact_notes: Optional[str] = None,
    ) -> dict:
        """Record the post-intervention score and compute value_added."""
        self._ensure_intervention(intervention_id)
        if post_assessment_date:
            post_assessment_date = self._ymd(post_assessment_date, "post_assessment_date")
        else:
            post_assessment_date = datetime.now().strftime("%Y-%m-%d")
        self._upsert_outcome(intervention_id)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT pre_assessment_score FROM intervention_outcomes "
                "WHERE intervention_id = ?",
                (intervention_id,),
            ).fetchone()
            pre = row["pre_assessment_score"] if row else None
            value_added = (
                round(post_assessment_score - pre, 2) if pre is not None else None
            )
            conn.execute(
                """UPDATE intervention_outcomes
                   SET post_assessment_score = ?,
                       post_assessment_date = ?,
                       value_added = ?,
                       impact_notes = COALESCE(?, impact_notes),
                       updated_at = datetime('now')
                   WHERE intervention_id = ?""",
                (post_assessment_score, post_assessment_date, value_added,
                 impact_notes, intervention_id),
            )
            conn.commit()
        return self.get_outcome(intervention_id)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def record_session(
        self,
        intervention_id: int,
        session_date: str,
        duration_minutes: Optional[int] = None,
        status: str = "attended",
        notes: Optional[str] = None,
        recorded_by: Optional[str] = None,
    ) -> int:
        self._ensure_intervention(intervention_id)
        if status not in _VALID_SESSION_STATUS:
            raise InterventionOutcomesError(
                f"status must be one of {sorted(_VALID_SESSION_STATUS)}",
            )
        self._ymd(session_date, "session_date")
        if duration_minutes is not None and duration_minutes < 0:
            raise InterventionOutcomesError("duration_minutes must be >= 0")
        self._upsert_outcome(intervention_id)
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO intervention_sessions
                   (intervention_id, session_date, duration_minutes,
                    status, notes, recorded_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (intervention_id, session_date, duration_minutes,
                 status, notes, recorded_by),
            )
            session_id = cur.lastrowid
            if status == "attended":
                conn.execute(
                    """UPDATE intervention_outcomes
                       SET sessions_completed = sessions_completed + 1,
                           updated_at = datetime('now')
                       WHERE intervention_id = ?""",
                    (intervention_id,),
                )
            conn.commit()
        return session_id

    def list_sessions(self, intervention_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM intervention_sessions WHERE intervention_id = ? "
                "ORDER BY session_date DESC, session_id DESC",
                (intervention_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Reads / rollups
    # ------------------------------------------------------------------

    def get_outcome(self, intervention_id: int) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM intervention_outcomes WHERE intervention_id = ?",
                (intervention_id,),
            ).fetchone()
            return dict(row) if row else {}

    def get_full_record(self, intervention_id: int) -> dict:
        """Intervention + outcome + sessions in one payload."""
        self._ensure_intervention(intervention_id)
        with self._conn() as conn:
            iv = conn.execute(
                "SELECT * FROM early_warning_interventions WHERE intervention_id = ?",
                (intervention_id,),
            ).fetchone()
        return {
            "intervention": dict(iv) if iv else {},
            "outcome": self.get_outcome(intervention_id),
            "sessions": self.list_sessions(intervention_id),
        }

    def list_with_outcomes(
        self,
        student_id: Optional[str] = None,
        status: Optional[str] = None,
        only_with_outcome: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        sql = (
            "SELECT i.*, o.subject_area, o.sessions_total, o.sessions_completed, "
            "o.pre_assessment_score, o.post_assessment_score, o.value_added, "
            "o.impact_notes "
            "FROM early_warning_interventions i "
            + ("JOIN" if only_with_outcome else "LEFT JOIN")
            + " intervention_outcomes o ON o.intervention_id = i.intervention_id "
            "WHERE 1=1"
        )
        params: list = []
        if student_id is not None:
            sql += " AND i.student_id = ?"
            params.append(student_id)
        if status is not None:
            sql += " AND i.status = ?"
            params.append(status)
        sql += " ORDER BY i.intervention_id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def summary(self, student_id: Optional[str] = None) -> dict:
        """Aggregate value-added stats across interventions."""
        sql = (
            "SELECT COUNT(*) AS interventions, "
            "SUM(CASE WHEN o.pre_assessment_score IS NOT NULL THEN 1 ELSE 0 END) AS with_baseline, "
            "SUM(CASE WHEN o.post_assessment_score IS NOT NULL THEN 1 ELSE 0 END) AS with_outcome, "
            "AVG(o.value_added) AS avg_value_added, "
            "SUM(CASE WHEN o.value_added > 0 THEN 1 ELSE 0 END) AS positive_value_added, "
            "COALESCE(SUM(o.sessions_completed), 0) AS total_sessions_completed, "
            "COALESCE(SUM(o.sessions_total), 0) AS total_sessions_planned "
            "FROM early_warning_interventions i "
            "LEFT JOIN intervention_outcomes o ON o.intervention_id = i.intervention_id "
            "WHERE 1=1"
        )
        params: list = []
        if student_id is not None:
            sql += " AND i.student_id = ?"
            params.append(student_id)
        with self._conn() as conn:
            row = conn.execute(sql, params).fetchone()
        result = dict(row) if row else {}
        # Normalise None -> 0 / 0.0 for cleaner consumption
        for k in ("with_baseline", "with_outcome", "positive_value_added"):
            result[k] = result.get(k) or 0
        result["avg_value_added"] = (
            round(result["avg_value_added"], 2)
            if result.get("avg_value_added") is not None else None
        )
        return result
