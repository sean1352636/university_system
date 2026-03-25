"""Self-Assessment & Ofsted service — SEF sections, improvement actions, Ofsted prep."""

from education_system.college_system.core.exceptions import SelfAssessmentError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import escape_like
import logging

logger = logging.getLogger(__name__)


class SelfAssessmentService:
    """Service for managing SEF sections, improvement actions, and Ofsted prep checklists."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # -- SEF Sections --

    def create_section(self, section_name: str, section_number: str | None = None,
                       academic_year: str | None = None, self_grade: str | None = None,
                       strengths: str | None = None, areas_for_improvement: str | None = None,
                       evidence: str | None = None, last_updated_by: int | None = None,
                       status: str = "draft") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO sef_sections
                   (section_name, section_number, academic_year, self_grade,
                    strengths, areas_for_improvement, evidence, last_updated_by, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (section_name, section_number, academic_year, self_grade,
                 strengths, areas_for_improvement, evidence, last_updated_by, status),
            )
            conn.commit()
            logger.info("SEF section created: %s", section_name)
            row = conn.execute("SELECT * FROM sef_sections WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to create SEF section: {e}") from e
        finally:
            conn.close()

    def list_sections(self, academic_year: str | None = None,
                      status: str | None = None,
                      search: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM sef_sections WHERE 1=1"
            params: list = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if search:
                sql += " AND (section_name LIKE ? OR strengths LIKE ? OR areas_for_improvement LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term])
            sql += " ORDER BY section_number, created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_section(self, section_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM sef_sections WHERE id = ?", (section_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_section(self, section_id: int, **updates) -> dict:
        allowed = {"section_name", "section_number", "academic_year", "self_grade",
                    "strengths", "areas_for_improvement", "evidence", "last_updated_by", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise SelfAssessmentError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM sef_sections WHERE id = ?", (section_id,)).fetchone()
            if not existing:
                raise SelfAssessmentError("SEF section not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE sef_sections SET {set_parts}, updated_at = datetime('now') WHERE id = ?",
                (*updates.values(), section_id),
            )
            conn.commit()
            logger.info("SEF section updated: id=%d", section_id)
            row = conn.execute("SELECT * FROM sef_sections WHERE id = ?", (section_id,)).fetchone()
            return dict(row)
        except SelfAssessmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to update SEF section: {e}") from e
        finally:
            conn.close()

    def delete_section(self, section_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM sef_sections WHERE id = ?", (section_id,)).fetchone()
            if not existing:
                raise SelfAssessmentError("SEF section not found.")
            conn.execute("DELETE FROM improvement_actions WHERE sef_section_id = ?", (section_id,))
            conn.execute("DELETE FROM sef_sections WHERE id = ?", (section_id,))
            conn.commit()
            logger.info("SEF section deleted (cascade): id=%d", section_id)
            return True
        except SelfAssessmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to delete SEF section: {e}") from e
        finally:
            conn.close()

    # -- Improvement Actions --

    def create_action(self, sef_section_id: int, action_description: str,
                      responsible_person: str | None = None,
                      start_date: str | None = None,
                      target_date: str | None = None,
                      success_criteria: str | None = None,
                      progress: str | None = None,
                      impact: str | None = None,
                      cost: float = 0,
                      status: str = "not_started") -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM sef_sections WHERE id = ?", (sef_section_id,)).fetchone()
            if not existing:
                raise SelfAssessmentError("SEF section not found.")
            conn.execute(
                """INSERT INTO improvement_actions
                   (sef_section_id, action_description, responsible_person, start_date,
                    target_date, success_criteria, progress, impact, cost, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sef_section_id, action_description, responsible_person, start_date,
                 target_date, success_criteria, progress, impact, cost, status),
            )
            conn.commit()
            logger.info("Improvement action created for section %d", sef_section_id)
            row = conn.execute("SELECT * FROM improvement_actions WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except SelfAssessmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to create improvement action: {e}") from e
        finally:
            conn.close()

    def list_actions(self, sef_section_id: int | None = None,
                     status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT ia.*, ss.section_name
                     FROM improvement_actions ia
                     LEFT JOIN sef_sections ss ON ia.sef_section_id = ss.id
                     WHERE 1=1"""
            params: list = []
            if sef_section_id:
                sql += " AND ia.sef_section_id = ?"
                params.append(sef_section_id)
            if status:
                sql += " AND ia.status = ?"
                params.append(status)
            sql += " ORDER BY ia.target_date, ia.created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_action(self, action_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT ia.*, ss.section_name
                   FROM improvement_actions ia
                   LEFT JOIN sef_sections ss ON ia.sef_section_id = ss.id
                   WHERE ia.id = ?""",
                (action_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_action(self, action_id: int, **updates) -> dict:
        allowed = {"action_description", "responsible_person", "start_date", "target_date",
                    "success_criteria", "progress", "impact", "cost", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise SelfAssessmentError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM improvement_actions WHERE id = ?", (action_id,)).fetchone()
            if not existing:
                raise SelfAssessmentError("Improvement action not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE improvement_actions SET {set_parts}, updated_at = datetime('now') WHERE id = ?",
                (*updates.values(), action_id),
            )
            conn.commit()
            logger.info("Improvement action updated: id=%d", action_id)
            row = conn.execute("SELECT * FROM improvement_actions WHERE id = ?", (action_id,)).fetchone()
            return dict(row)
        except SelfAssessmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to update improvement action: {e}") from e
        finally:
            conn.close()

    def delete_action(self, action_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM improvement_actions WHERE id = ?", (action_id,)).fetchone()
            if not existing:
                raise SelfAssessmentError("Improvement action not found.")
            conn.execute("DELETE FROM improvement_actions WHERE id = ?", (action_id,))
            conn.commit()
            logger.info("Improvement action deleted: id=%d", action_id)
            return True
        except SelfAssessmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to delete improvement action: {e}") from e
        finally:
            conn.close()

    # -- Ofsted Prep Checklist --

    def create_checklist_item(self, category: str, item: str,
                              responsible_person: str | None = None,
                              document_location: str | None = None,
                              is_ready: int = 0,
                              notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ofsted_prep_checklist
                   (category, item, responsible_person, document_location, is_ready, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (category, item, responsible_person, document_location, is_ready, notes),
            )
            conn.commit()
            logger.info("Checklist item created: %s - %s", category, item)
            row = conn.execute("SELECT * FROM ofsted_prep_checklist WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to create checklist item: {e}") from e
        finally:
            conn.close()

    def list_checklist(self, category: str | None = None,
                       ready: int | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM ofsted_prep_checklist WHERE 1=1"
            params: list = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if ready is not None:
                sql += " AND is_ready = ?"
                params.append(ready)
            sql += " ORDER BY category, item"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_checklist_item(self, item_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM ofsted_prep_checklist WHERE id = ?", (item_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_checklist_item(self, item_id: int, **updates) -> dict:
        allowed = {"category", "item", "responsible_person", "document_location",
                    "is_ready", "notes", "last_checked"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise SelfAssessmentError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM ofsted_prep_checklist WHERE id = ?", (item_id,)).fetchone()
            if not existing:
                raise SelfAssessmentError("Checklist item not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE ofsted_prep_checklist SET {set_parts} WHERE id = ?",
                (*updates.values(), item_id),
            )
            conn.commit()
            logger.info("Checklist item updated: id=%d", item_id)
            row = conn.execute("SELECT * FROM ofsted_prep_checklist WHERE id = ?", (item_id,)).fetchone()
            return dict(row)
        except SelfAssessmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to update checklist item: {e}") from e
        finally:
            conn.close()

    def delete_checklist_item(self, item_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM ofsted_prep_checklist WHERE id = ?", (item_id,)).fetchone()
            if not existing:
                raise SelfAssessmentError("Checklist item not found.")
            conn.execute("DELETE FROM ofsted_prep_checklist WHERE id = ?", (item_id,))
            conn.commit()
            logger.info("Checklist item deleted: id=%d", item_id)
            return True
        except SelfAssessmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to delete checklist item: {e}") from e
        finally:
            conn.close()

    def toggle_ready(self, item_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id, is_ready FROM ofsted_prep_checklist WHERE id = ?", (item_id,)).fetchone()
            if not existing:
                raise SelfAssessmentError("Checklist item not found.")
            new_ready = 0 if existing["is_ready"] else 1
            conn.execute(
                "UPDATE ofsted_prep_checklist SET is_ready = ?, last_checked = datetime('now') WHERE id = ?",
                (new_ready, item_id),
            )
            conn.commit()
            logger.info("Checklist item toggled: id=%d ready=%d", item_id, new_ready)
            row = conn.execute("SELECT * FROM ofsted_prep_checklist WHERE id = ?", (item_id,)).fetchone()
            return dict(row)
        except SelfAssessmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SelfAssessmentError(f"Failed to toggle checklist item: {e}") from e
        finally:
            conn.close()

    # -- Statistics --

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            # SEF section stats
            sec_row = conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft_count,
                          SUM(CASE WHEN status = 'final' THEN 1 ELSE 0 END) as final_count
                   FROM sef_sections"""
            ).fetchone()

            # Improvement action stats
            act_row = conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN status = 'not_started' THEN 1 ELSE 0 END) as not_started,
                          SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                          SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                   FROM improvement_actions"""
            ).fetchone()

            # Checklist stats
            chk_row = conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN is_ready = 1 THEN 1 ELSE 0 END) as ready_count,
                          SUM(CASE WHEN is_ready = 0 THEN 1 ELSE 0 END) as not_ready_count
                   FROM ofsted_prep_checklist"""
            ).fetchone()

            return {
                "total_sections": sec_row["total"] or 0,
                "draft_count": sec_row["draft_count"] or 0,
                "final_count": sec_row["final_count"] or 0,
                "total_actions": act_row["total"] or 0,
                "not_started": act_row["not_started"] or 0,
                "in_progress": act_row["in_progress"] or 0,
                "completed": act_row["completed"] or 0,
                "total_checklist": chk_row["total"] or 0,
                "ready_count": chk_row["ready_count"] or 0,
                "not_ready_count": chk_row["not_ready_count"] or 0,
            }
        finally:
            conn.close()
