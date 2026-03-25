"""Schedule, assign, track IQR visits and action plans."""

from education_system.college_system.core.exceptions import IQRManagerError
from education_system.college_system.infrastructure.database.db import connect
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class IQRManagerService:
    """Service for managing Internal Quality Reviews."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _ensure_tables(self, conn):
        """Create tables if they don't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS iqr_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                academic_year TEXT,
                cycle_name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                focus_areas TEXT,
                status TEXT DEFAULT 'planned',
                created_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS iqr_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER REFERENCES iqr_cycles(id),
                department TEXT,
                course_id INTEGER,
                visit_date TEXT,
                reviewer_id INTEGER,
                visit_type TEXT,
                duration_minutes INTEGER DEFAULT 60,
                findings TEXT,
                strengths TEXT,
                areas_for_improvement TEXT,
                overall_judgement TEXT,
                status TEXT DEFAULT 'scheduled',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS iqr_action_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visit_id INTEGER REFERENCES iqr_visits(id),
                action_description TEXT NOT NULL,
                responsible_person TEXT,
                target_date TEXT,
                success_criteria TEXT,
                progress TEXT,
                evidence TEXT,
                status TEXT DEFAULT 'not_started',
                reviewed_date TEXT,
                reviewed_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    _VALID_VISIT_TYPES = (
        "learning_walk", "deep_dive", "work_scrutiny", "student_voice", "staff_interview",
    )
    _VALID_JUDGEMENTS = ("outstanding", "good", "requires_improvement", "inadequate")
    _VALID_ACTION_STATUSES = ("not_started", "in_progress", "completed", "overdue")

    def create_cycle(self, academic_year, cycle_name, start_date, end_date, focus_areas, created_by):
        """Create a new IQR cycle."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                """INSERT INTO iqr_cycles
                   (academic_year, cycle_name, start_date, end_date, focus_areas, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (academic_year, cycle_name, start_date, end_date, focus_areas, created_by),
            )
            conn.commit()
            logger.info("Created IQR cycle id=%d: %s", cur.lastrowid, cycle_name)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create cycle: %s", exc)
            raise IQRManagerError(f"Failed to create cycle: {exc}") from exc
        finally:
            conn.close()

    def list_cycles(self, academic_year=None):
        """List IQR cycles with optional year filter."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            sql = "SELECT * FROM iqr_cycles WHERE 1=1"
            params = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY created_at DESC"
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list cycles: %s", exc)
            raise IQRManagerError(f"Failed to list cycles: {exc}") from exc
        finally:
            conn.close()

    def get_cycle(self, cycle_id):
        """Get a single cycle by ID."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute("SELECT * FROM iqr_cycles WHERE id = ?", (cycle_id,))
            row = cur.fetchone()
            if not row:
                raise IQRManagerError(f"Cycle {cycle_id} not found")
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        except IQRManagerError:
            raise
        except Exception as exc:
            logger.error("Failed to get cycle: %s", exc)
            raise IQRManagerError(f"Failed to get cycle: {exc}") from exc
        finally:
            conn.close()

    def schedule_visit(self, cycle_id, department, visit_date, reviewer_id, visit_type, course_id=None):
        """Schedule a new IQR visit."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if visit_type not in self._VALID_VISIT_TYPES:
                raise IQRManagerError(f"Invalid visit type: {visit_type}")
            # Verify cycle exists
            cur = conn.execute("SELECT id FROM iqr_cycles WHERE id = ?", (cycle_id,))
            if not cur.fetchone():
                raise IQRManagerError(f"Cycle {cycle_id} not found")
            cur = conn.execute(
                """INSERT INTO iqr_visits
                   (cycle_id, department, course_id, visit_date, reviewer_id, visit_type)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cycle_id, department, course_id, visit_date, reviewer_id, visit_type),
            )
            conn.commit()
            logger.info("Scheduled visit id=%d for cycle %d", cur.lastrowid, cycle_id)
            return cur.lastrowid
        except IQRManagerError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to schedule visit: %s", exc)
            raise IQRManagerError(f"Failed to schedule visit: {exc}") from exc
        finally:
            conn.close()

    def list_visits(self, cycle_id=None, department=None, status=None):
        """List visits with optional filters."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            sql = "SELECT * FROM iqr_visits WHERE 1=1"
            params = []
            if cycle_id:
                sql += " AND cycle_id = ?"
                params.append(cycle_id)
            if department:
                sql += " AND department = ?"
                params.append(department)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY visit_date ASC"
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list visits: %s", exc)
            raise IQRManagerError(f"Failed to list visits: {exc}") from exc
        finally:
            conn.close()

    def complete_visit(self, visit_id, findings, strengths, areas_for_improvement, overall_judgement):
        """Complete a visit with findings and judgement."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if overall_judgement not in self._VALID_JUDGEMENTS:
                raise IQRManagerError(f"Invalid judgement: {overall_judgement}")
            conn.execute(
                """UPDATE iqr_visits
                   SET findings = ?, strengths = ?, areas_for_improvement = ?,
                       overall_judgement = ?, status = 'completed',
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (findings, strengths, areas_for_improvement, overall_judgement, visit_id),
            )
            conn.commit()
            logger.info("Completed visit %d with judgement: %s", visit_id, overall_judgement)
        except IQRManagerError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to complete visit: %s", exc)
            raise IQRManagerError(f"Failed to complete visit: {exc}") from exc
        finally:
            conn.close()

    def create_action_plan(self, visit_id, action_description, responsible_person, target_date, success_criteria):
        """Create an action plan for a visit."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute("SELECT id FROM iqr_visits WHERE id = ?", (visit_id,))
            if not cur.fetchone():
                raise IQRManagerError(f"Visit {visit_id} not found")
            cur = conn.execute(
                """INSERT INTO iqr_action_plans
                   (visit_id, action_description, responsible_person, target_date, success_criteria)
                   VALUES (?, ?, ?, ?, ?)""",
                (visit_id, action_description, responsible_person, target_date, success_criteria),
            )
            conn.commit()
            logger.info("Created action plan id=%d for visit %d", cur.lastrowid, visit_id)
            return cur.lastrowid
        except IQRManagerError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create action plan: %s", exc)
            raise IQRManagerError(f"Failed to create action plan: {exc}") from exc
        finally:
            conn.close()

    def list_action_plans(self, visit_id=None, status=None):
        """List action plans with optional filters."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            sql = "SELECT * FROM iqr_action_plans WHERE 1=1"
            params = []
            if visit_id:
                sql += " AND visit_id = ?"
                params.append(visit_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY target_date ASC"
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list action plans: %s", exc)
            raise IQRManagerError(f"Failed to list action plans: {exc}") from exc
        finally:
            conn.close()

    def update_action_progress(self, action_id, progress, evidence=None, status=None):
        """Update progress on an action plan."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if status and status not in self._VALID_ACTION_STATUSES:
                raise IQRManagerError(f"Invalid action status: {status}")
            sql = "UPDATE iqr_action_plans SET progress = ?, updated_at = datetime('now')"
            params = [progress]
            if evidence is not None:
                sql += ", evidence = ?"
                params.append(evidence)
            if status is not None:
                sql += ", status = ?"
                params.append(status)
            sql += " WHERE id = ?"
            params.append(action_id)
            conn.execute(sql, params)
            conn.commit()
            logger.info("Updated action %d progress", action_id)
        except IQRManagerError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update action progress: %s", exc)
            raise IQRManagerError(f"Failed to update action progress: {exc}") from exc
        finally:
            conn.close()

    def review_action(self, action_id, reviewed_by):
        """Mark an action as reviewed."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            now = datetime.now().isoformat()
            conn.execute(
                """UPDATE iqr_action_plans
                   SET reviewed_date = ?, reviewed_by = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (now, reviewed_by, action_id),
            )
            conn.commit()
            logger.info("Reviewed action %d by user %d", action_id, reviewed_by)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to review action: %s", exc)
            raise IQRManagerError(f"Failed to review action: {exc}") from exc
        finally:
            conn.close()

    def get_cycle_stats(self, cycle_id):
        """Get statistics for a cycle - visits completed, judgement distribution, action status."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute("SELECT * FROM iqr_cycles WHERE id = ?", (cycle_id,))
            row = cur.fetchone()
            if not row:
                raise IQRManagerError(f"Cycle {cycle_id} not found")

            # Visit counts
            cur = conn.execute(
                "SELECT status, COUNT(*) FROM iqr_visits WHERE cycle_id = ? GROUP BY status",
                (cycle_id,),
            )
            visit_status = {r[0]: r[1] for r in cur.fetchall()}

            # Judgement distribution
            cur = conn.execute(
                """SELECT overall_judgement, COUNT(*)
                   FROM iqr_visits WHERE cycle_id = ? AND status = 'completed'
                   GROUP BY overall_judgement""",
                (cycle_id,),
            )
            judgement_dist = {r[0]: r[1] for r in cur.fetchall()}

            # Action plan status
            cur = conn.execute(
                """SELECT ap.status, COUNT(*)
                   FROM iqr_action_plans ap
                   JOIN iqr_visits v ON ap.visit_id = v.id
                   WHERE v.cycle_id = ?
                   GROUP BY ap.status""",
                (cycle_id,),
            )
            action_status = {r[0]: r[1] for r in cur.fetchall()}

            return {
                "cycle_id": cycle_id,
                "visit_status": visit_status,
                "total_visits": sum(visit_status.values()),
                "judgement_distribution": judgement_dist,
                "action_status": action_status,
                "total_actions": sum(action_status.values()),
            }
        except IQRManagerError:
            raise
        except Exception as exc:
            logger.error("Failed to get cycle stats: %s", exc)
            raise IQRManagerError(f"Failed to get cycle stats: {exc}") from exc
        finally:
            conn.close()
