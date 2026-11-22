"""Statutory reporting — #30 HESA export, #31 UKVI engagement."""

from __future__ import annotations

import csv
import sqlite3
from datetime import date
from typing import List, Optional, Tuple

from .log import logger


# ===========================================================================
# ComplianceService — #30 HESA, #31 UKVI
# ===========================================================================

HESA_COLS = [
    "HUSID", "STULOAD", "MODULECODE", "MODULENAME",
    "ENGAGEMENT_DATE", "ENGAGEMENT_TYPE", "ENGAGEMENT_OUTCOME",
    "EXPECTED_SESSIONS", "ATTENDED_SESSIONS", "ATTENDANCE_PCT",
]


class ComplianceService:
    """HESA export + UKVI engagement monitoring."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # --- HESA --------------------------------------------------------
    def hesa_export(self, out_path: str,
                    term_start: Optional[str] = None,
                    term_end: Optional[str] = None) -> int:
        try:
            cur = self.conn.execute("PRAGMA table_info(students)")
            scols = {r[1] for r in cur.fetchall()}
        except sqlite3.Error:
            logger.exception("students PRAGMA failed")
            return 0
        stuload_expr = ("COALESCE(s.study_mode, 'FT')"
                        if "study_mode" in scols else "'FT'")
        sql = f"""
            SELECT s.student_id AS HUSID,
                   {stuload_expr} AS STULOAD,
                   m.module_code AS MODULECODE,
                   m.module_name AS MODULENAME,
                   MAX(a.date)   AS ENGAGEMENT_DATE,
                   'ATTENDANCE' AS ENGAGEMENT_TYPE,
                   CASE WHEN SUM(CASE WHEN a.status='present'
                                       THEN 1 ELSE 0 END)
                              >= 0.75 * COUNT(a.id)
                        THEN 'ENGAGED' ELSE 'AT_RISK'
                   END AS ENGAGEMENT_OUTCOME,
                   COUNT(a.id) AS EXPECTED_SESSIONS,
                   SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                       AS ATTENDED_SESSIONS,
                   ROUND(100.0 * SUM(CASE WHEN a.status='present'
                                          THEN 1 ELSE 0 END)
                           / NULLIF(COUNT(a.id), 0), 2) AS ATTENDANCE_PCT
              FROM attendance a
              JOIN students s ON s.student_id = a.student_id
              JOIN modules  m ON m.module_code = a.module_code
             WHERE (? IS NULL OR a.date >= ?)
               AND (? IS NULL OR a.date <= ?)
             GROUP BY s.student_id, m.module_code, m.module_name
             ORDER BY s.student_id, m.module_code
        """
        try:
            rows = self.conn.execute(
                sql, (term_start, term_start, term_end, term_end)).fetchall()
        except sqlite3.Error:
            logger.exception("HESA query failed")
            return 0
        try:
            with open(out_path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(HESA_COLS)
                w.writerows(rows)
        except OSError:
            logger.exception("HESA write failed path=%s", out_path)
            return 0
        logger.info("HESA export wrote %d rows -> %s", len(rows), out_path)
        return len(rows)

    # --- UKVI --------------------------------------------------------
    def ukvi_log(self, student_id: str, event_type: str,
                 event_date: Optional[str] = None,
                 notes: str = "", recorded_by: str = "") -> None:
        try:
            cur = self.conn.execute(
                """INSERT INTO ukvi_engagement_events
                     (student_id, event_type, event_date, notes, recorded_by)
                   VALUES(?,?,?,?,?)""",
                (student_id, event_type,
                 (event_date or date.today().isoformat()),
                 notes, recorded_by))
            event_id = cur.lastrowid
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("UKVI log failed sid=%s ev=%s",
                             student_id, event_type)
            raise

        # Mirror into the visa-sponsorship dashboard. Best-effort: if the
        # international_compliance module isn't installed (e.g. minimal
        # deployment) or the visa table isn't there yet, swallow the error
        # — the source row is committed and that's what matters.
        try:
            self._mirror_to_visa_engagement(
                event_id, student_id, event_type,
                event_date or date.today().isoformat(),
                notes, recorded_by,
            )
        except Exception:
            logger.debug("visa-mirror skipped sid=%s ev=%s", student_id, event_type, exc_info=True)

    def _mirror_to_visa_engagement(
        self, event_id: int, student_id: str, event_type: str,
        event_date: str, notes: str, recorded_by: str,
    ) -> None:
        """Insert a matching row into ``visa_engagement_checks`` on the
        same DB connection. Idempotent via the unique partial index on
        ``source_event_id``."""
        # Map legacy event_type to the visa module's three-valued outcome.
        et = (event_type or "").strip().lower()
        if et in {"missed", "no_engagement", "absent_critical", "failed"}:
            outcome = "missed"
        elif et in {"at_risk", "low_attendance", "partial", "late"}:
            outcome = "partial"
        else:
            outcome = "engaged"
        try:
            rec_by_int: Optional[int] = int(recorded_by) if recorded_by not in (None, "") else None
        except (TypeError, ValueError):
            rec_by_int = None
        try:
            self.conn.execute(
                """INSERT INTO visa_engagement_checks
                     (student_id, check_date, term, method, evidence,
                      outcome, recorded_by, source_event_id)
                   VALUES (?, ?, NULL, ?, ?, ?, ?, ?)""",
                (
                    student_id, event_date,
                    f"attendance pipeline ({event_type or 'unspecified'})",
                    notes, outcome, rec_by_int, event_id,
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Already mirrored by a parallel run / earlier importer.
            self.conn.rollback()

    def ukvi_at_risk(self, min_pct: float = 80.0) -> List[Tuple]:
        """Student-Route / Tier-4 holders below engagement threshold."""
        try:
            cur = self.conn.execute("PRAGMA table_info(students)")
            cols = {r[1] for r in cur.fetchall()}
        except sqlite3.Error:
            logger.exception("students PRAGMA failed")
            return []
        # visa_filter is built from a closed set of column names — safe to
        # interpolate into the SQL string.
        if "visa_type" in cols:
            visa_filter = ("AND s.visa_type IN ('student_route','tier_4',"
                           "'Tier 4','Student Route')")
        elif "international" in cols:
            visa_filter = "AND s.international = 1"
        else:
            visa_filter = ""
        sql = f"""
            SELECT s.student_id,
                   TRIM(COALESCE(s.first_name,'')||' '
                        ||COALESCE(s.last_name,'')) AS name,
                   ROUND(100.0 * SUM(CASE WHEN a.status='present'
                                          THEN 1 ELSE 0 END)
                         / NULLIF(COUNT(a.id),0), 2) AS pct,
                   SUM(CASE WHEN a.status IN ('absent','late')
                            THEN 1 ELSE 0 END) AS missed
              FROM students s
              JOIN attendance a ON a.student_id = s.student_id
             WHERE 1=1 {visa_filter}
             GROUP BY s.student_id
            HAVING pct IS NOT NULL AND pct < ?
             ORDER BY pct ASC
        """
        try:
            return list(self.conn.execute(sql, (min_pct,)).fetchall())
        except sqlite3.Error:
            logger.exception("UKVI at-risk query failed")
            return []


def hesa_export(conn, out_path: str,
                term_start: Optional[str] = None,
                term_end: Optional[str] = None) -> int:
    return ComplianceService(conn).hesa_export(out_path, term_start, term_end)


def ukvi_log_event(conn, student_id, event_type, event_date=None,
                   notes: str = "", recorded_by: str = "") -> None:
    ComplianceService(conn).ukvi_log(
        student_id, event_type, event_date, notes, recorded_by)


def ukvi_at_risk(conn, min_pct: float = 80.0) -> List[Tuple]:
    return ComplianceService(conn).ukvi_at_risk(min_pct)


__all__ = [
    "HESA_COLS",
    "ComplianceService",
    "hesa_export",
    "ukvi_log_event",
    "ukvi_at_risk",
]
