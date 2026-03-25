"""Enhanced destination tracking - NEET rates, employment stats, university progression."""

from education_system.college_system.core.exceptions import DestinationOutcomeError
from education_system.college_system.infrastructure.database.db import connect
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DestinationOutcomeService:
    """Service for tracking student destination outcomes."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _ensure_tables(self, conn):
        """Create tables if they don't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS destination_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                academic_year TEXT,
                leaving_date TEXT,
                outcome_type TEXT,
                institution_name TEXT,
                course_title TEXT,
                employer_name TEXT,
                job_title TEXT,
                sustained_at_3m INTEGER DEFAULT 0,
                sustained_at_6m INTEGER DEFAULT 0,
                contact_date TEXT,
                contact_method TEXT,
                verified INTEGER DEFAULT 0,
                verified_by INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS outcome_surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                academic_year TEXT,
                survey_type TEXT,
                sent_date TEXT,
                response_date TEXT,
                current_status TEXT,
                satisfaction_rating INTEGER,
                would_recommend INTEGER DEFAULT 1,
                comments TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    _VALID_OUTCOMES = (
        "university", "apprenticeship", "employment", "further_education",
        "gap_year", "neet", "unknown", "volunteering",
    )

    def record_outcome(self, student_id, academic_year, outcome_type, leaving_date=None,
                       institution_name=None, course_title=None, employer_name=None,
                       job_title=None, contact_date=None, contact_method=None, notes=None):
        """Record a destination outcome for a student."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if outcome_type not in self._VALID_OUTCOMES:
                raise DestinationOutcomeError(f"Invalid outcome type: {outcome_type}")
            cur = conn.execute(
                """INSERT INTO destination_outcomes
                   (student_id, academic_year, outcome_type, leaving_date,
                    institution_name, course_title, employer_name, job_title,
                    contact_date, contact_method, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, academic_year, outcome_type, leaving_date,
                 institution_name, course_title, employer_name, job_title,
                 contact_date, contact_method, notes),
            )
            conn.commit()
            logger.info("Recorded outcome id=%d for student %d", cur.lastrowid, student_id)
            return cur.lastrowid
        except DestinationOutcomeError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to record outcome: %s", exc)
            raise DestinationOutcomeError(f"Failed to record outcome: {exc}") from exc
        finally:
            conn.close()

    def list_outcomes(self, academic_year=None, outcome_type=None):
        """List outcomes with optional filters."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            sql = "SELECT * FROM destination_outcomes WHERE 1=1"
            params = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            if outcome_type:
                sql += " AND outcome_type = ?"
                params.append(outcome_type)
            sql += " ORDER BY created_at DESC"
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list outcomes: %s", exc)
            raise DestinationOutcomeError(f"Failed to list outcomes: {exc}") from exc
        finally:
            conn.close()

    def update_outcome(self, outcome_id, **updates):
        """Update an existing outcome."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if "outcome_type" in updates and updates["outcome_type"] not in self._VALID_OUTCOMES:
                raise DestinationOutcomeError(f"Invalid outcome type: {updates['outcome_type']}")
            allowed = {
                "outcome_type", "leaving_date", "institution_name", "course_title",
                "employer_name", "job_title", "contact_date", "contact_method", "notes",
            }
            filtered = {k: v for k, v in updates.items() if k in allowed}
            if not filtered:
                return
            sets = ", ".join(f"{k} = ?" for k in filtered)
            vals = list(filtered.values()) + [outcome_id]
            conn.execute(
                f"UPDATE destination_outcomes SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("Updated outcome %d", outcome_id)
        except DestinationOutcomeError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update outcome: %s", exc)
            raise DestinationOutcomeError(f"Failed to update outcome: {exc}") from exc
        finally:
            conn.close()

    def verify_outcome(self, outcome_id, verified_by):
        """Mark an outcome as verified."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            conn.execute(
                "UPDATE destination_outcomes SET verified = 1, verified_by = ?, updated_at = datetime('now') WHERE id = ?",
                (verified_by, outcome_id),
            )
            conn.commit()
            logger.info("Verified outcome %d by user %d", outcome_id, verified_by)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to verify outcome: %s", exc)
            raise DestinationOutcomeError(f"Failed to verify outcome: {exc}") from exc
        finally:
            conn.close()

    def get_neet_rate(self, academic_year):
        """Calculate NEET rate for an academic year."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                "SELECT COUNT(*) FROM destination_outcomes WHERE academic_year = ?",
                (academic_year,),
            )
            total = cur.fetchone()[0]
            if total == 0:
                return {"total": 0, "neet_count": 0, "rate": 0.0}
            cur = conn.execute(
                "SELECT COUNT(*) FROM destination_outcomes WHERE academic_year = ? AND outcome_type = 'neet'",
                (academic_year,),
            )
            neet = cur.fetchone()[0]
            return {"total": total, "neet_count": neet, "rate": round(neet / total * 100, 2)}
        except Exception as exc:
            logger.error("Failed to get NEET rate: %s", exc)
            raise DestinationOutcomeError(f"Failed to get NEET rate: {exc}") from exc
        finally:
            conn.close()

    def get_employment_stats(self, academic_year):
        """Get employment statistics for an academic year."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                "SELECT COUNT(*) FROM destination_outcomes WHERE academic_year = ?",
                (academic_year,),
            )
            total = cur.fetchone()[0]
            cur = conn.execute(
                "SELECT COUNT(*) FROM destination_outcomes WHERE academic_year = ? AND outcome_type = 'employment'",
                (academic_year,),
            )
            employed = cur.fetchone()[0]
            cur = conn.execute(
                "SELECT COUNT(*) FROM destination_outcomes WHERE academic_year = ? AND outcome_type = 'apprenticeship'",
                (academic_year,),
            )
            apprenticeships = cur.fetchone()[0]
            cur = conn.execute(
                """SELECT COUNT(*) FROM destination_outcomes
                   WHERE academic_year = ? AND outcome_type = 'employment' AND sustained_at_6m = 1""",
                (academic_year,),
            )
            sustained = cur.fetchone()[0]
            return {
                "total": total,
                "employed": employed,
                "apprenticeships": apprenticeships,
                "employment_rate": round(employed / total * 100, 2) if total else 0.0,
                "sustained_6m": sustained,
            }
        except Exception as exc:
            logger.error("Failed to get employment stats: %s", exc)
            raise DestinationOutcomeError(f"Failed to get employment stats: {exc}") from exc
        finally:
            conn.close()

    def get_university_progression(self, academic_year):
        """Get university progression statistics."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                "SELECT COUNT(*) FROM destination_outcomes WHERE academic_year = ?",
                (academic_year,),
            )
            total = cur.fetchone()[0]
            cur = conn.execute(
                "SELECT COUNT(*) FROM destination_outcomes WHERE academic_year = ? AND outcome_type = 'university'",
                (academic_year,),
            )
            uni = cur.fetchone()[0]
            cur = conn.execute(
                """SELECT institution_name, COUNT(*) as cnt
                   FROM destination_outcomes
                   WHERE academic_year = ? AND outcome_type = 'university' AND institution_name IS NOT NULL
                   GROUP BY institution_name ORDER BY cnt DESC LIMIT 10""",
                (academic_year,),
            )
            top_institutions = [{"institution": row[0], "count": row[1]} for row in cur.fetchall()]
            return {
                "total": total,
                "university_count": uni,
                "progression_rate": round(uni / total * 100, 2) if total else 0.0,
                "top_institutions": top_institutions,
            }
        except Exception as exc:
            logger.error("Failed to get university progression: %s", exc)
            raise DestinationOutcomeError(f"Failed to get university progression: {exc}") from exc
        finally:
            conn.close()

    def get_outcome_summary(self, academic_year):
        """Get full breakdown of outcomes by type."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                """SELECT outcome_type, COUNT(*) as cnt
                   FROM destination_outcomes
                   WHERE academic_year = ?
                   GROUP BY outcome_type ORDER BY cnt DESC""",
                (academic_year,),
            )
            breakdown = {row[0]: row[1] for row in cur.fetchall()}
            total = sum(breakdown.values())
            return {
                "academic_year": academic_year,
                "total": total,
                "breakdown": breakdown,
                "percentages": {k: round(v / total * 100, 2) for k, v in breakdown.items()} if total else {},
            }
        except Exception as exc:
            logger.error("Failed to get outcome summary: %s", exc)
            raise DestinationOutcomeError(f"Failed to get outcome summary: {exc}") from exc
        finally:
            conn.close()

    def mark_sustained(self, outcome_id, months):
        """Mark an outcome as sustained at 3 or 6 months."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if months == 3:
                conn.execute(
                    "UPDATE destination_outcomes SET sustained_at_3m = 1, updated_at = datetime('now') WHERE id = ?",
                    (outcome_id,),
                )
            elif months == 6:
                conn.execute(
                    "UPDATE destination_outcomes SET sustained_at_6m = 1, updated_at = datetime('now') WHERE id = ?",
                    (outcome_id,),
                )
            else:
                raise DestinationOutcomeError(f"Invalid months value: {months}. Must be 3 or 6.")
            conn.commit()
            logger.info("Marked outcome %d sustained at %d months", outcome_id, months)
        except DestinationOutcomeError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to mark sustained: %s", exc)
            raise DestinationOutcomeError(f"Failed to mark sustained: {exc}") from exc
        finally:
            conn.close()

    def create_survey(self, student_id, academic_year, survey_type):
        """Create a destination outcome survey."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if survey_type not in ("3_month", "6_month", "12_month"):
                raise DestinationOutcomeError(f"Invalid survey type: {survey_type}")
            now = datetime.now().strftime("%Y-%m-%d")
            cur = conn.execute(
                """INSERT INTO outcome_surveys
                   (student_id, academic_year, survey_type, sent_date)
                   VALUES (?, ?, ?, ?)""",
                (student_id, academic_year, survey_type, now),
            )
            conn.commit()
            logger.info("Created survey id=%d for student %d", cur.lastrowid, student_id)
            return cur.lastrowid
        except DestinationOutcomeError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create survey: %s", exc)
            raise DestinationOutcomeError(f"Failed to create survey: {exc}") from exc
        finally:
            conn.close()

    def list_surveys(self, academic_year=None, survey_type=None):
        """List surveys with optional filters."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            sql = "SELECT * FROM outcome_surveys WHERE 1=1"
            params = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            if survey_type:
                sql += " AND survey_type = ?"
                params.append(survey_type)
            sql += " ORDER BY created_at DESC"
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list surveys: %s", exc)
            raise DestinationOutcomeError(f"Failed to list surveys: {exc}") from exc
        finally:
            conn.close()

    def record_survey_response(self, survey_id, current_status, satisfaction, would_recommend, comments):
        """Record a response to a destination survey."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            now = datetime.now().strftime("%Y-%m-%d")
            conn.execute(
                """UPDATE outcome_surveys
                   SET response_date = ?, current_status = ?, satisfaction_rating = ?,
                       would_recommend = ?, comments = ?
                   WHERE id = ?""",
                (now, current_status, satisfaction, 1 if would_recommend else 0, comments, survey_id),
            )
            conn.commit()
            logger.info("Recorded survey response for survey %d", survey_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to record survey response: %s", exc)
            raise DestinationOutcomeError(f"Failed to record survey response: {exc}") from exc
        finally:
            conn.close()
