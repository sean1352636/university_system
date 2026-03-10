"""Parents evening service for managing evenings and booking slots."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import ParentsEveningError


class ParentsEveningService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Evenings ---

    def create_evening(self, title: str, event_date: str,
                        start_time: str = "16:00", end_time: str = "20:00",
                        slot_duration_mins: int = 5, created_by: int = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO parents_evenings
                   (title, event_date, start_time, end_time, slot_duration_mins, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, event_date, start_time, end_time, slot_duration_mins, created_by),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM parents_evenings WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ParentsEveningError(f"Failed to create evening: {e}")
        finally:
            conn.close()

    def list_evenings(self, status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM parents_evenings WHERE status = ? ORDER BY event_date DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM parents_evenings ORDER BY event_date DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_evening(self, evening_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM parents_evenings WHERE id = ?", (evening_id,)
            ).fetchone()
            if not row:
                raise ParentsEveningError(f"Evening {evening_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_evening(self, evening_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"title", "event_date", "start_time", "end_time",
                        "slot_duration_mins", "status"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise ParentsEveningError("No valid fields to update")
            params.append(evening_id)
            conn.execute(
                f"UPDATE parents_evenings SET {', '.join(parts)} WHERE id = ?", params
            )
            conn.commit()
            return self.get_evening(evening_id)
        except ParentsEveningError:
            raise
        except Exception as e:
            raise ParentsEveningError(f"Failed to update evening: {e}")
        finally:
            conn.close()

    # --- Slots ---

    def create_slot(self, evening_id: int, teacher_id: int, slot_time: str,
                     parent_user_id: int = None, student_id: int = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO parents_evening_slots
                   (evening_id, teacher_id, slot_time, parent_user_id, student_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (evening_id, teacher_id, slot_time, parent_user_id, student_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM parents_evening_slots WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ParentsEveningError(f"Failed to create slot: {e}")
        finally:
            conn.close()

    def list_slots(self, evening_id: int, teacher_id: int = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT ps.*, u.username as teacher_name
                       FROM parents_evening_slots ps
                       LEFT JOIN users u ON ps.teacher_id = u.id
                       WHERE ps.evening_id = ?"""
            params = [evening_id]
            if teacher_id:
                query += " AND ps.teacher_id = ?"
                params.append(teacher_id)
            query += " ORDER BY ps.slot_time"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def book_slot(self, slot_id: int, parent_user_id: int, student_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM parents_evening_slots WHERE id = ?", (slot_id,)
            ).fetchone()
            if not row:
                raise ParentsEveningError(f"Slot {slot_id} not found")
            if row["status"] == "booked":
                raise ParentsEveningError("Slot is already booked")
            conn.execute(
                """UPDATE parents_evening_slots
                   SET parent_user_id = ?, student_id = ?, status = 'booked'
                   WHERE id = ?""",
                (parent_user_id, student_id, slot_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM parents_evening_slots WHERE id = ?", (slot_id,)
            ).fetchone()
            return dict(row)
        except ParentsEveningError:
            raise
        except Exception as e:
            raise ParentsEveningError(f"Failed to book slot: {e}")
        finally:
            conn.close()

    def cancel_slot(self, slot_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE parents_evening_slots
                   SET parent_user_id = NULL, student_id = NULL, status = 'available'
                   WHERE id = ?""",
                (slot_id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM parents_evening_slots WHERE id = ?", (slot_id,)
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def get_parent_bookings(self, parent_user_id: int, evening_id: int = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT ps.*, pe.title as evening_title, pe.event_date, u.username as teacher_name
                       FROM parents_evening_slots ps
                       LEFT JOIN parents_evenings pe ON ps.evening_id = pe.id
                       LEFT JOIN users u ON ps.teacher_id = u.id
                       WHERE ps.parent_user_id = ?"""
            params = [parent_user_id]
            if evening_id:
                query += " AND ps.evening_id = ?"
                params.append(evening_id)
            query += " ORDER BY pe.event_date, ps.slot_time"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
