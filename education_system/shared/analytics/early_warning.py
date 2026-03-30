"""Early warning system for student risk prediction.

Uses statistical analysis of attendance, grades, and engagement data
to identify students at risk of falling behind or dropping out.
Designed to work across all education levels.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from education_system.shared.database.paths import SYSTEM_DB_PATHS, SYSTEM_LABELS

logger = logging.getLogger(__name__)


def _connect(path):
    if not path or not Path(path).exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


class EarlyWarningService:
    """Identifies at-risk students using statistical indicators.

    Risk factors:
    - Attendance below threshold (default 90%)
    - Declining grades (downward trend)
    - Low engagement (missing assignments)
    - Behavioural flags

    Each factor contributes a weighted score. Students with scores
    above the threshold are flagged for intervention.
    """

    # Risk weights (sum to ~1.0)
    WEIGHTS = {
        "attendance": 0.35,
        "grades": 0.30,
        "assignments": 0.20,
        "behaviour": 0.15,
    }

    RISK_THRESHOLDS = {
        "low": 0.3,
        "medium": 0.5,
        "high": 0.7,
        "critical": 0.85,
    }

    def __init__(self, db_paths=None):
        self._db_paths = db_paths or dict(SYSTEM_DB_PATHS)

    def assess_student_risk(self, student_id: str, system: str) -> dict:
        """Assess risk for a single student.

        Returns a dict with overall risk_score, risk_level,
        and per-factor breakdown.
        """
        db_path = self._db_paths.get(system)
        if not db_path:
            return {"error": f"Unknown system: {system}"}

        conn = _connect(db_path)
        if not conn:
            return {"error": f"Database not found for {system}"}

        try:
            factors = {}

            # Attendance risk
            attendance_score = self._calc_attendance_risk(conn, student_id, system)
            factors["attendance"] = {"score": attendance_score, "weight": self.WEIGHTS["attendance"]}

            # Grade trend risk
            grade_score = self._calc_grade_risk(conn, student_id, system)
            factors["grades"] = {"score": grade_score, "weight": self.WEIGHTS["grades"]}

            # Assignment completion risk
            assignment_score = self._calc_assignment_risk(conn, student_id, system)
            factors["assignments"] = {"score": assignment_score, "weight": self.WEIGHTS["assignments"]}

            # Behaviour risk
            behaviour_score = self._calc_behaviour_risk(conn, student_id, system)
            factors["behaviour"] = {"score": behaviour_score, "weight": self.WEIGHTS["behaviour"]}

            # Weighted overall score
            overall = sum(f["score"] * f["weight"] for f in factors.values())

            # Determine risk level
            risk_level = "low"
            for level, threshold in sorted(self.RISK_THRESHOLDS.items(),
                                           key=lambda x: x[1], reverse=True):
                if overall >= threshold:
                    risk_level = level
                    break

            return {
                "student_id": student_id,
                "system": system,
                "risk_score": round(overall, 3),
                "risk_level": risk_level,
                "factors": factors,
                "assessed_at": datetime.utcnow().isoformat(),
                "recommendations": self._generate_recommendations(factors, risk_level),
            }
        finally:
            conn.close()

    def _calc_attendance_risk(self, conn, student_id, system) -> float:
        """Calculate attendance-based risk (0=no risk, 1=highest risk)."""
        if not _table_exists(conn, "attendance"):
            return 0.0
        try:
            id_col = "pupil_id" if system == "primary" else "student_id"
            cols = {r[1] for r in conn.execute("PRAGMA table_info(attendance)").fetchall()}
            if id_col not in cols:
                return 0.0

            cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            total = conn.execute(
                f"SELECT COUNT(*) FROM attendance WHERE {id_col} = ? AND date >= ?",
                (student_id, cutoff),
            ).fetchone()[0]

            if total == 0:
                return 0.5  # No data = moderate concern

            present_statuses = ("present", "Present", "P", "L")  # L = Late but present
            present = conn.execute(
                f"SELECT COUNT(*) FROM attendance WHERE {id_col} = ? AND date >= ? AND status IN ({','.join('?' * len(present_statuses))})",
                (student_id, cutoff, *present_statuses),
            ).fetchone()[0]

            rate = present / total if total > 0 else 1.0
            # 100% attendance = 0 risk, 80% = ~0.67 risk, 60% = 1.0 risk
            return max(0.0, min(1.0, (0.95 - rate) / 0.35))
        except Exception:
            return 0.0

    def _calc_grade_risk(self, conn, student_id, system) -> float:
        """Calculate grade-based risk from declining trend."""
        for table in ("grades", "assessment", "assessments", "results"):
            if not _table_exists(conn, table):
                continue
            try:
                cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                id_col = "pupil_id" if system == "primary" and "pupil_id" in cols else (
                    "student_id" if "student_id" in cols else None
                )
                score_col = None
                for c in ("score", "mark", "grade_value", "percentage"):
                    if c in cols:
                        score_col = c
                        break
                if not id_col or not score_col:
                    continue

                rows = conn.execute(
                    f"SELECT {score_col} FROM {table} WHERE {id_col} = ? ORDER BY rowid DESC LIMIT 10",
                    (student_id,),
                ).fetchall()

                if len(rows) < 3:
                    return 0.0

                scores = [float(r[0]) for r in rows if r[0] is not None]
                if not scores:
                    return 0.0

                # Check for declining trend
                recent = scores[:len(scores) // 2]
                older = scores[len(scores) // 2:]
                recent_avg = sum(recent) / len(recent) if recent else 0
                older_avg = sum(older) / len(older) if older else 0

                if older_avg == 0:
                    return 0.0

                decline = (older_avg - recent_avg) / older_avg
                # Absolute level check too
                level_risk = max(0, (50 - recent_avg) / 50) if recent_avg < 50 else 0

                return max(0.0, min(1.0, max(decline, level_risk)))
            except Exception:
                continue
        return 0.0

    def _calc_assignment_risk(self, conn, student_id, system) -> float:
        """Calculate risk from incomplete assignments."""
        for table in ("assignments", "homework"):
            if not _table_exists(conn, table):
                continue
            try:
                cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                id_col = "pupil_id" if system == "primary" and "pupil_id" in cols else (
                    "student_id" if "student_id" in cols else None
                )
                if not id_col or "status" not in cols:
                    continue

                total = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {id_col} = ?",
                    (student_id,),
                ).fetchone()[0]
                if total == 0:
                    return 0.0

                incomplete_statuses = ("missing", "Missing", "overdue", "Overdue", "not_submitted", "incomplete")
                incomplete = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {id_col} = ? AND status IN ({','.join('?' * len(incomplete_statuses))})",
                    (student_id, *incomplete_statuses),
                ).fetchone()[0]

                rate = incomplete / total
                return min(1.0, rate * 1.5)  # 67% missing = max risk
            except Exception:
                continue
        return 0.0

    def _calc_behaviour_risk(self, conn, student_id, system) -> float:
        """Calculate risk from behavioural incidents."""
        for table in ("behaviour", "incidents", "behaviour_records"):
            if not _table_exists(conn, table):
                continue
            try:
                cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                id_col = "pupil_id" if system == "primary" and "pupil_id" in cols else (
                    "student_id" if "student_id" in cols else None
                )
                if not id_col:
                    continue

                cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                date_col = "date" if "date" in cols else ("incident_date" if "incident_date" in cols else "created_at" if "created_at" in cols else None)
                if not date_col:
                    continue

                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {id_col} = ? AND {date_col} >= ?",
                    (student_id, cutoff),
                ).fetchone()[0]

                # 0 incidents = 0 risk, 5+ = high risk
                return min(1.0, count / 5.0)
            except Exception:
                continue
        return 0.0

    def _generate_recommendations(self, factors: dict, risk_level: str) -> list[str]:
        """Generate intervention recommendations based on risk factors."""
        recs = []
        if factors["attendance"]["score"] > 0.5:
            recs.append("Schedule attendance meeting with student/parents")
        if factors["attendance"]["score"] > 0.7:
            recs.append("Refer to attendance officer for formal monitoring")
        if factors["grades"]["score"] > 0.5:
            recs.append("Arrange additional academic support or tutoring")
        if factors["grades"]["score"] > 0.7:
            recs.append("Consider subject-level intervention plan")
        if factors["assignments"]["score"] > 0.5:
            recs.append("Check-in with student about workload management")
        if factors["behaviour"]["score"] > 0.5:
            recs.append("Pastoral care referral for behavioural support")
        if risk_level == "critical":
            recs.append("URGENT: Immediate multi-agency intervention required")
        if risk_level == "high":
            recs.append("Schedule case conference within 1 week")
        return recs

    def scan_all_students(self, system: str, min_risk: str = "medium") -> list[dict]:
        """Scan all students in a system and return those at or above the given risk level.

        Returns a list of risk assessments sorted by risk_score descending.
        """
        threshold = self.RISK_THRESHOLDS.get(min_risk, 0.5)
        db_path = self._db_paths.get(system)
        if not db_path:
            return []

        conn = _connect(db_path)
        if not conn:
            return []

        try:
            table = "pupils" if system == "primary" else "students"
            if not _table_exists(conn, table):
                return []

            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            id_col = "pupil_id" if system == "primary" and "pupil_id" in cols else (
                "student_id" if "student_id" in cols else "id"
            )

            rows = conn.execute(f"SELECT {id_col} FROM {table} LIMIT 500").fetchall()
            student_ids = [str(r[0]) for r in rows]
        finally:
            conn.close()

        results = []
        for sid in student_ids:
            assessment = self.assess_student_risk(sid, system)
            if assessment.get("risk_score", 0) >= threshold:
                results.append(assessment)

        results.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
        return results
