from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import get_connection

class EventFinanceRepository:
    def list_for_event(self, event_id: int):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM event_finances WHERE event_id = ? ORDER BY finance_id", (event_id,)).fetchall()
