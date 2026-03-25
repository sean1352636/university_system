"""Ofsted Self-Evaluation Form builder with evidence linking to system data."""

from education_system.college_system.core.exceptions import SEFBuilderError
from education_system.college_system.infrastructure.database.db import connect
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SEFBuilderService:
    """Service for building and managing Ofsted SEF documents."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _ensure_tables(self, conn):
        """Create tables if they don't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sef_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                academic_year TEXT,
                title TEXT NOT NULL,
                version TEXT DEFAULT '1.0',
                overall_effectiveness TEXT,
                status TEXT DEFAULT 'draft',
                created_by INTEGER,
                approved_by INTEGER,
                approved_date TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sef_judgement_areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sef_id INTEGER REFERENCES sef_documents(id),
                area_name TEXT NOT NULL,
                area_number TEXT,
                self_grade TEXT,
                narrative TEXT,
                strengths TEXT,
                areas_for_improvement TEXT,
                key_actions TEXT,
                display_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sef_evidence_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                judgement_area_id INTEGER REFERENCES sef_judgement_areas(id),
                evidence_type TEXT,
                evidence_description TEXT NOT NULL,
                data_source TEXT,
                data_query TEXT,
                data_value TEXT,
                document_path TEXT,
                linked_at TEXT DEFAULT (datetime('now')),
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    _VALID_GRADES = ("outstanding", "good", "requires_improvement", "inadequate")

    def create_sef(self, academic_year, title, created_by):
        """Create a new SEF document."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                """INSERT INTO sef_documents (academic_year, title, created_by)
                   VALUES (?, ?, ?)""",
                (academic_year, title, created_by),
            )
            conn.commit()
            logger.info("Created SEF id=%d: %s", cur.lastrowid, title)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create SEF: %s", exc)
            raise SEFBuilderError(f"Failed to create SEF: {exc}") from exc
        finally:
            conn.close()

    def list_sefs(self, academic_year=None):
        """List SEF documents with optional year filter."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            sql = "SELECT * FROM sef_documents WHERE 1=1"
            params = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY created_at DESC"
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list SEFs: %s", exc)
            raise SEFBuilderError(f"Failed to list SEFs: {exc}") from exc
        finally:
            conn.close()

    def get_sef(self, sef_id):
        """Get a single SEF by ID."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute("SELECT * FROM sef_documents WHERE id = ?", (sef_id,))
            row = cur.fetchone()
            if not row:
                raise SEFBuilderError(f"SEF {sef_id} not found")
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        except SEFBuilderError:
            raise
        except Exception as exc:
            logger.error("Failed to get SEF: %s", exc)
            raise SEFBuilderError(f"Failed to get SEF: {exc}") from exc
        finally:
            conn.close()

    def update_sef(self, sef_id, **updates):
        """Update a SEF document."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if "overall_effectiveness" in updates and updates["overall_effectiveness"] not in self._VALID_GRADES:
                raise SEFBuilderError(f"Invalid grade: {updates['overall_effectiveness']}")
            allowed = {"title", "version", "overall_effectiveness", "status", "academic_year"}
            filtered = {k: v for k, v in updates.items() if k in allowed}
            if not filtered:
                return
            sets = ", ".join(f"{k} = ?" for k in filtered)
            vals = list(filtered.values()) + [sef_id]
            conn.execute(
                f"UPDATE sef_documents SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("Updated SEF %d", sef_id)
        except SEFBuilderError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update SEF: %s", exc)
            raise SEFBuilderError(f"Failed to update SEF: {exc}") from exc
        finally:
            conn.close()

    def add_judgement_area(self, sef_id, area_name, area_number, self_grade=None):
        """Add a judgement area to a SEF."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if self_grade and self_grade not in self._VALID_GRADES:
                raise SEFBuilderError(f"Invalid grade: {self_grade}")
            # Get next display order
            cur = conn.execute(
                "SELECT COALESCE(MAX(display_order), 0) + 1 FROM sef_judgement_areas WHERE sef_id = ?",
                (sef_id,),
            )
            order = cur.fetchone()[0]
            cur = conn.execute(
                """INSERT INTO sef_judgement_areas
                   (sef_id, area_name, area_number, self_grade, display_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (sef_id, area_name, area_number, self_grade, order),
            )
            conn.commit()
            logger.info("Added judgement area id=%d to SEF %d", cur.lastrowid, sef_id)
            return cur.lastrowid
        except SEFBuilderError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to add judgement area: %s", exc)
            raise SEFBuilderError(f"Failed to add judgement area: {exc}") from exc
        finally:
            conn.close()

    def update_judgement_area(self, area_id, **updates):
        """Update a judgement area."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if "self_grade" in updates and updates["self_grade"] and updates["self_grade"] not in self._VALID_GRADES:
                raise SEFBuilderError(f"Invalid grade: {updates['self_grade']}")
            allowed = {
                "area_name", "area_number", "self_grade", "narrative",
                "strengths", "areas_for_improvement", "key_actions", "display_order",
            }
            filtered = {k: v for k, v in updates.items() if k in allowed}
            if not filtered:
                return
            sets = ", ".join(f"{k} = ?" for k in filtered)
            vals = list(filtered.values()) + [area_id]
            conn.execute(
                f"UPDATE sef_judgement_areas SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("Updated judgement area %d", area_id)
        except SEFBuilderError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update judgement area: %s", exc)
            raise SEFBuilderError(f"Failed to update judgement area: {exc}") from exc
        finally:
            conn.close()

    def list_judgement_areas(self, sef_id):
        """List judgement areas for a SEF."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                "SELECT * FROM sef_judgement_areas WHERE sef_id = ? ORDER BY display_order",
                (sef_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list judgement areas: %s", exc)
            raise SEFBuilderError(f"Failed to list judgement areas: {exc}") from exc
        finally:
            conn.close()

    def add_evidence_link(self, judgement_area_id, evidence_type, evidence_description,
                          data_source=None, data_value=None):
        """Add an evidence link to a judgement area."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            valid_types = ("data", "document", "observation", "survey", "outcome", "external")
            if evidence_type not in valid_types:
                raise SEFBuilderError(f"Invalid evidence type: {evidence_type}")
            cur = conn.execute(
                """INSERT INTO sef_evidence_links
                   (judgement_area_id, evidence_type, evidence_description, data_source, data_value)
                   VALUES (?, ?, ?, ?, ?)""",
                (judgement_area_id, evidence_type, evidence_description, data_source, data_value),
            )
            conn.commit()
            logger.info("Added evidence link id=%d to area %d", cur.lastrowid, judgement_area_id)
            return cur.lastrowid
        except SEFBuilderError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to add evidence link: %s", exc)
            raise SEFBuilderError(f"Failed to add evidence link: {exc}") from exc
        finally:
            conn.close()

    def list_evidence(self, judgement_area_id):
        """List evidence links for a judgement area."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                "SELECT * FROM sef_evidence_links WHERE judgement_area_id = ? ORDER BY linked_at",
                (judgement_area_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list evidence: %s", exc)
            raise SEFBuilderError(f"Failed to list evidence: {exc}") from exc
        finally:
            conn.close()

    def remove_evidence(self, evidence_id):
        """Remove an evidence link."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            conn.execute("DELETE FROM sef_evidence_links WHERE id = ?", (evidence_id,))
            conn.commit()
            logger.info("Removed evidence link %d", evidence_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to remove evidence: %s", exc)
            raise SEFBuilderError(f"Failed to remove evidence: {exc}") from exc
        finally:
            conn.close()

    def pull_system_data(self, sef_id):
        """Auto-populate evidence from attendance rates, achievement data, destination data."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            areas = self._list_areas_conn(conn, sef_id)
            evidence_added = 0
            for area in areas:
                area_name_lower = (area.get("area_name") or "").lower()
                # Try to pull attendance data
                if "attendance" in area_name_lower or "behaviour" in area_name_lower:
                    try:
                        cur = conn.execute(
                            """SELECT COUNT(*) as total,
                                      SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) as present
                               FROM attendance"""
                        )
                        row = cur.fetchone()
                        if row and row[0] > 0:
                            rate = round(row[1] / row[0] * 100, 2) if row[0] else 0
                            conn.execute(
                                """INSERT INTO sef_evidence_links
                                   (judgement_area_id, evidence_type, evidence_description,
                                    data_source, data_value)
                                   VALUES (?, 'data', ?, 'attendance', ?)""",
                                (area["id"], f"Overall attendance rate: {rate}%", str(rate)),
                            )
                            evidence_added += 1
                    except Exception:
                        pass
                # Try to pull achievement data
                if "outcomes" in area_name_lower or "achievement" in area_name_lower or "quality" in area_name_lower:
                    try:
                        cur = conn.execute("SELECT COUNT(*) FROM grades")
                        row = cur.fetchone()
                        if row and row[0] > 0:
                            conn.execute(
                                """INSERT INTO sef_evidence_links
                                   (judgement_area_id, evidence_type, evidence_description,
                                    data_source, data_value)
                                   VALUES (?, 'data', ?, 'grades', ?)""",
                                (area["id"], f"Total grade records: {row[0]}", str(row[0])),
                            )
                            evidence_added += 1
                    except Exception:
                        pass
                # Try to pull destination data
                if "destination" in area_name_lower or "progression" in area_name_lower:
                    try:
                        cur = conn.execute(
                            """SELECT outcome_type, COUNT(*) FROM destination_outcomes
                               GROUP BY outcome_type"""
                        )
                        rows = cur.fetchall()
                        if rows:
                            summary = ", ".join(f"{r[0]}: {r[1]}" for r in rows)
                            conn.execute(
                                """INSERT INTO sef_evidence_links
                                   (judgement_area_id, evidence_type, evidence_description,
                                    data_source, data_value)
                                   VALUES (?, 'data', ?, 'destination_outcomes', ?)""",
                                (area["id"], f"Destination outcomes: {summary}", summary),
                            )
                            evidence_added += 1
                    except Exception:
                        pass
            conn.commit()
            logger.info("Pulled %d evidence items for SEF %d", evidence_added, sef_id)
            return evidence_added
        except SEFBuilderError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to pull system data: %s", exc)
            raise SEFBuilderError(f"Failed to pull system data: {exc}") from exc
        finally:
            conn.close()

    def approve_sef(self, sef_id, approved_by):
        """Approve a SEF document."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            now = datetime.now().isoformat()
            conn.execute(
                """UPDATE sef_documents
                   SET status = 'approved', approved_by = ?, approved_date = ?,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (approved_by, now, sef_id),
            )
            conn.commit()
            logger.info("Approved SEF %d by user %d", sef_id, approved_by)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to approve SEF: %s", exc)
            raise SEFBuilderError(f"Failed to approve SEF: {exc}") from exc
        finally:
            conn.close()

    def export_sef(self, sef_id):
        """Export a SEF document as a formatted dict."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute("SELECT * FROM sef_documents WHERE id = ?", (sef_id,))
            row = cur.fetchone()
            if not row:
                raise SEFBuilderError(f"SEF {sef_id} not found")
            cols = [d[0] for d in cur.description]
            sef = dict(zip(cols, row))

            areas = self._list_areas_conn(conn, sef_id)
            for area in areas:
                cur = conn.execute(
                    "SELECT * FROM sef_evidence_links WHERE judgement_area_id = ?",
                    (area["id"],),
                )
                ev_cols = [d[0] for d in cur.description]
                area["evidence"] = [dict(zip(ev_cols, r)) for r in cur.fetchall()]

            sef["judgement_areas"] = areas
            logger.info("Exported SEF %d", sef_id)
            return sef
        except SEFBuilderError:
            raise
        except Exception as exc:
            logger.error("Failed to export SEF: %s", exc)
            raise SEFBuilderError(f"Failed to export SEF: {exc}") from exc
        finally:
            conn.close()

    def get_sef_summary(self, sef_id):
        """Get a summary of the SEF document."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute("SELECT * FROM sef_documents WHERE id = ?", (sef_id,))
            row = cur.fetchone()
            if not row:
                raise SEFBuilderError(f"SEF {sef_id} not found")
            cols = [d[0] for d in cur.description]
            sef = dict(zip(cols, row))

            areas = self._list_areas_conn(conn, sef_id)
            grade_counts = {}
            total_evidence = 0
            for area in areas:
                grade = area.get("self_grade") or "ungraded"
                grade_counts[grade] = grade_counts.get(grade, 0) + 1
                cur = conn.execute(
                    "SELECT COUNT(*) FROM sef_evidence_links WHERE judgement_area_id = ?",
                    (area["id"],),
                )
                total_evidence += cur.fetchone()[0]

            return {
                "sef_id": sef_id,
                "title": sef["title"],
                "status": sef["status"],
                "version": sef.get("version", "1.0"),
                "overall_effectiveness": sef.get("overall_effectiveness"),
                "total_areas": len(areas),
                "grade_distribution": grade_counts,
                "total_evidence_links": total_evidence,
            }
        except SEFBuilderError:
            raise
        except Exception as exc:
            logger.error("Failed to get SEF summary: %s", exc)
            raise SEFBuilderError(f"Failed to get SEF summary: {exc}") from exc
        finally:
            conn.close()

    # ── helpers ──

    def _list_areas_conn(self, conn, sef_id):
        """List judgement areas using an existing connection."""
        cur = conn.execute(
            "SELECT * FROM sef_judgement_areas WHERE sef_id = ? ORDER BY display_order",
            (sef_id,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
