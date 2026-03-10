"""Cover service for managing substitution/cover arrangements."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import CoverError


class CoverService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_arrangement(self, absent_staff_id: int, cover_staff_id: int = None,
                             timetable_slot_id: int = None,
                             cover_date: str = None,
                             reason: str = None, notes: str = None,
                             arranged_by: int = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO cover_arrangements
                   (absent_staff_id, cover_staff_id, timetable_slot_id,
                    cover_date, reason, notes, arranged_by)
                   VALUES (?, ?, ?, COALESCE(?, date('now')), ?, ?, ?)""",
                (absent_staff_id, cover_staff_id, timetable_slot_id,
                 cover_date, reason, notes, arranged_by),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM cover_arrangements WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise CoverError(f"Failed to create cover arrangement: {e}")
        finally:
            conn.close()

    def list_arrangements(self, cover_date: str = None, status: str = None,
                            absent_staff_id: int = None,
                            cover_staff_id: int = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT ca.*,
                              u1.username as absent_staff_name,
                              u2.username as cover_staff_name
                       FROM cover_arrangements ca
                       LEFT JOIN users u1 ON ca.absent_staff_id = u1.id
                       LEFT JOIN users u2 ON ca.cover_staff_id = u2.id
                       WHERE 1=1"""
            params = []
            if cover_date:
                query += " AND ca.cover_date = ?"
                params.append(cover_date)
            if status:
                query += " AND ca.status = ?"
                params.append(status)
            if absent_staff_id:
                query += " AND ca.absent_staff_id = ?"
                params.append(absent_staff_id)
            if cover_staff_id:
                query += " AND ca.cover_staff_id = ?"
                params.append(cover_staff_id)
            query += " ORDER BY ca.cover_date DESC, ca.id"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_arrangement(self, arrangement_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT ca.*,
                          u1.username as absent_staff_name,
                          u2.username as cover_staff_name
                   FROM cover_arrangements ca
                   LEFT JOIN users u1 ON ca.absent_staff_id = u1.id
                   LEFT JOIN users u2 ON ca.cover_staff_id = u2.id
                   WHERE ca.id = ?""",
                (arrangement_id,),
            ).fetchone()
            if not row:
                raise CoverError(f"Arrangement {arrangement_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_arrangement(self, arrangement_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"cover_staff_id", "timetable_slot_id", "status",
                        "notes", "reason", "arranged_by"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise CoverError("No valid fields to update")
            params.append(arrangement_id)
            conn.execute(
                f"UPDATE cover_arrangements SET {', '.join(parts)} WHERE id = ?", params
            )
            conn.commit()
            return self.get_arrangement(arrangement_id)
        except CoverError:
            raise
        except Exception as e:
            raise CoverError(f"Failed to update arrangement: {e}")
        finally:
            conn.close()

    def get_today_cover(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ca.*,
                          u1.username as absent_staff_name,
                          u2.username as cover_staff_name
                   FROM cover_arrangements ca
                   LEFT JOIN users u1 ON ca.absent_staff_id = u1.id
                   LEFT JOIN users u2 ON ca.cover_staff_id = u2.id
                   WHERE ca.cover_date = date('now')
                   ORDER BY ca.id"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_staff_cover_count(self, staff_id: int, term_start: str = None,
                                term_end: str = None) -> int:
        conn = self._conn()
        try:
            query = "SELECT COUNT(*) as cnt FROM cover_arrangements WHERE cover_staff_id = ?"
            params = [staff_id]
            if term_start:
                query += " AND cover_date >= ?"
                params.append(term_start)
            if term_end:
                query += " AND cover_date <= ?"
                params.append(term_end)
            row = conn.execute(query, params).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def delete_arrangement(self, arrangement_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM cover_arrangements WHERE id = ?", (arrangement_id,))
            conn.commit()
            return True
        finally:
            conn.close()
