from education_system.systems.university.domain.pastoral.student_life.student_union.events.application.ports import get_connection

class SQLiteEventRepository:
    def get(self, event_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM union_events WHERE event_id = ?", (event_id,)
            ).fetchone()
