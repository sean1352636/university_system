"""Differentiated target setting engine service (ALPS-style)."""
from education_system.college_system.core.exceptions import TargetSettingError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)

# Default GCSE grade-to-points mapping
GCSE_POINTS = {
    "9": 9.0, "8": 8.0, "7": 7.0, "6": 6.0, "5": 5.0,
    "4": 4.0, "3": 3.0, "2": 2.0, "1": 1.0, "U": 0.0,
    "A*": 8.5, "A": 7.0, "B": 5.5, "C": 4.0, "D": 3.0,
    "E": 2.0, "F": 1.5, "G": 1.0,
}

# Default A-level target mapping from average GCSE points
DEFAULT_MEG_MAP = {
    (7.5, 9.0): ("A", "A*", "A*"),
    (6.5, 7.49): ("B", "A", "A*"),
    (5.5, 6.49): ("C", "B", "A"),
    (4.5, 5.49): ("D", "C", "B"),
    (3.5, 4.49): ("E", "D", "C"),
    (0.0, 3.49): ("U", "E", "D"),
}


class TargetSettingService:
    """Generate differentiated targets from prior attainment."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ------------------------------------------------------------------
    # Prior Attainment
    # ------------------------------------------------------------------

    def import_prior_attainment(self, student_id, qualification_type, subject,
                                grade, points, academic_year):
        """Import a single prior attainment record."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO prior_attainment
                   (student_id, qualification_type, subject, grade, points,
                    academic_year, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (student_id, qualification_type, subject, grade, points, academic_year),
            )
            conn.commit()
            logger.info("Imported prior attainment for student %s", student_id)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to import prior attainment: %s", exc)
            raise TargetSettingError(f"Failed to import prior attainment: {exc}") from exc
        finally:
            conn.close()

    def bulk_import_prior_attainment(self, records):
        """Bulk import prior attainment records.

        Args:
            records: list of dicts with student_id, qualification_type, subject,
                     grade, points, academic_year.
        """
        conn = self._conn()
        try:
            count = 0
            for rec in records:
                conn.execute(
                    """INSERT INTO prior_attainment
                       (student_id, qualification_type, subject, grade, points,
                        academic_year, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (rec["student_id"], rec["qualification_type"], rec["subject"],
                     rec["grade"], rec.get("points", GCSE_POINTS.get(rec["grade"], 0)),
                     rec["academic_year"]),
                )
                count += 1
            conn.commit()
            logger.info("Bulk imported %d prior attainment records", count)
            return count
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to bulk import prior attainment: %s", exc)
            raise TargetSettingError(f"Failed to bulk import: {exc}") from exc
        finally:
            conn.close()

    def get_student_prior_attainment(self, student_id):
        """Get all prior attainment records for a student."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM prior_attainment WHERE student_id = ? ORDER BY subject",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get prior attainment: %s", exc)
            raise TargetSettingError(f"Failed to get prior attainment: {exc}") from exc
        finally:
            conn.close()

    def calculate_average_points(self, student_id):
        """Calculate average GCSE points for a student."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT AVG(points) AS avg_points
                   FROM prior_attainment WHERE student_id = ?""",
                (student_id,),
            ).fetchone()
            return round(row["avg_points"], 2) if row and row["avg_points"] is not None else 0.0
        except Exception as exc:
            logger.error("Failed to calculate average points: %s", exc)
            raise TargetSettingError(f"Failed to calculate average points: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Target Generation
    # ------------------------------------------------------------------

    def generate_targets(self, student_id, course_id, academic_year, method="alps"):
        """Generate targets for a student on a course."""
        conn = self._conn()
        try:
            avg_pts = self.calculate_average_points(student_id)

            # Try benchmark table first
            meg, target, aspirational = self._lookup_benchmark(conn, avg_pts, method, academic_year)

            if meg is None:
                # Fall back to default mapping
                meg, target, aspirational = self._default_target(avg_pts)

            cur = conn.execute(
                """INSERT INTO target_grades
                   (student_id, course_id, prior_average_points, meg_grade,
                    target_grade, aspirational_grade, setting_method,
                    academic_year, generated_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'),
                           datetime('now'), datetime('now'))""",
                (student_id, course_id, avg_pts, meg, target, aspirational,
                 method, academic_year),
            )
            conn.commit()
            logger.info("Generated targets for student %s course %s", student_id, course_id)
            return cur.lastrowid
        except TargetSettingError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to generate targets: %s", exc)
            raise TargetSettingError(f"Failed to generate targets: {exc}") from exc
        finally:
            conn.close()

    def _lookup_benchmark(self, conn, avg_pts, method, academic_year):
        """Look up benchmark grades from the alps_benchmarks table."""
        row = conn.execute(
            """SELECT meg_grade, target_grade, aspirational_grade
               FROM alps_benchmarks
               WHERE prior_points_min <= ? AND prior_points_max >= ?
               AND (academic_year = ? OR academic_year IS NULL)
               ORDER BY academic_year DESC
               LIMIT 1""",
            (avg_pts, avg_pts, academic_year),
        ).fetchone()
        if row:
            return row["meg_grade"], row["target_grade"], row["aspirational_grade"]
        return None, None, None

    @staticmethod
    def _default_target(avg_pts):
        """Fall back to built-in MEG mapping."""
        for (low, high), grades in DEFAULT_MEG_MAP.items():
            if low <= avg_pts <= high:
                return grades
        return ("E", "D", "C")

    def bulk_generate_targets(self, course_id, academic_year, method="alps"):
        """Generate targets for all enrolled students on a course."""
        conn = self._conn()
        try:
            # Find enrolled students
            rows = conn.execute(
                """SELECT DISTINCT student_id FROM enrollments
                   WHERE course_id = ? AND status = 'active'""",
                (course_id,),
            ).fetchall()
            conn.close()

            generated = 0
            for row in rows:
                try:
                    self.generate_targets(row["student_id"], course_id, academic_year, method)
                    generated += 1
                except TargetSettingError:
                    logger.warning("Skipped target generation for student %s", row["student_id"])
            logger.info("Bulk generated %d targets for course %s", generated, course_id)
            return generated
        except Exception as exc:
            logger.error("Failed to bulk generate targets: %s", exc)
            raise TargetSettingError(f"Failed to bulk generate targets: {exc}") from exc

    def get_targets(self, student_id=None, course_id=None, academic_year=None):
        """Retrieve target grades with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM target_grades WHERE 1=1"
            params = []
            if student_id is not None:
                sql += " AND student_id = ?"
                params.append(student_id)
            if course_id is not None:
                sql += " AND course_id = ?"
                params.append(course_id)
            if academic_year is not None:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY student_id, course_id"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get targets: %s", exc)
            raise TargetSettingError(f"Failed to get targets: {exc}") from exc
        finally:
            conn.close()

    def update_current_grade(self, target_id, current_grade):
        """Update the current working grade for a target."""
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE target_grades SET current_grade = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (current_grade, target_id),
            )
            conn.commit()
            logger.info("Updated current grade for target %s", target_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update current grade: %s", exc)
            raise TargetSettingError(f"Failed to update current grade: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Value Added
    # ------------------------------------------------------------------

    def calculate_value_added(self, target_id):
        """Calculate value-added for a single target."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM target_grades WHERE id = ?", (target_id,),
            ).fetchone()
            if not row:
                raise TargetSettingError(f"Target {target_id} not found")
            row = dict(row)
            current = row.get("current_grade")
            meg = row.get("meg_grade")
            if current and meg:
                current_pts = GCSE_POINTS.get(current, 0)
                meg_pts = GCSE_POINTS.get(meg, 0)
                va = round(current_pts - meg_pts, 2)
                conn.execute(
                    "UPDATE target_grades SET value_added = ?, updated_at = datetime('now') WHERE id = ?",
                    (va, target_id),
                )
                conn.commit()
                row["value_added"] = va
            return row
        except TargetSettingError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to calculate VA: %s", exc)
            raise TargetSettingError(f"Failed to calculate VA: {exc}") from exc
        finally:
            conn.close()

    def get_course_value_added(self, course_id, academic_year):
        """Get value-added data for all students on a course."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM target_grades
                   WHERE course_id = ? AND academic_year = ?
                   ORDER BY student_id""",
                (course_id, academic_year),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get course VA: %s", exc)
            raise TargetSettingError(f"Failed to get course VA: {exc}") from exc
        finally:
            conn.close()

    def get_alps_summary(self, academic_year):
        """Get overall ALPS summary for an academic year."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) AS num_targets,
                          AVG(value_added) AS avg_va,
                          AVG(alps_score) AS avg_alps,
                          COUNT(CASE WHEN value_added > 0 THEN 1 END) AS positive_va,
                          COUNT(CASE WHEN value_added < 0 THEN 1 END) AS negative_va,
                          COUNT(CASE WHEN value_added = 0 THEN 1 END) AS on_target
                   FROM target_grades
                   WHERE academic_year = ? AND value_added IS NOT NULL""",
                (academic_year,),
            ).fetchone()
            return dict(row) if row else {}
        except Exception as exc:
            logger.error("Failed to get ALPS summary: %s", exc)
            raise TargetSettingError(f"Failed to get ALPS summary: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Benchmarks
    # ------------------------------------------------------------------

    def set_benchmark(self, qualification_type, prior_points_min, prior_points_max,
                      subject_group, meg_grade, target_grade, aspirational_grade,
                      academic_year):
        """Set an ALPS benchmark."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO alps_benchmarks
                   (qualification_type, prior_points_min, prior_points_max,
                    subject_group, meg_grade, target_grade, aspirational_grade,
                    academic_year, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (qualification_type, prior_points_min, prior_points_max,
                 subject_group, meg_grade, target_grade, aspirational_grade,
                 academic_year),
            )
            conn.commit()
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to set benchmark: %s", exc)
            raise TargetSettingError(f"Failed to set benchmark: {exc}") from exc
        finally:
            conn.close()

    def list_benchmarks(self, qualification_type=None, academic_year=None):
        """List ALPS benchmarks."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM alps_benchmarks WHERE 1=1"
            params = []
            if qualification_type:
                sql += " AND qualification_type = ?"
                params.append(qualification_type)
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY prior_points_min"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list benchmarks: %s", exc)
            raise TargetSettingError(f"Failed to list benchmarks: {exc}") from exc
        finally:
            conn.close()
