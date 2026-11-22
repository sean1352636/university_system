from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.application.ports import get_connection

class EventTicketRepository:
    def list_for_event(self, event_id: int):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM event_tickets WHERE event_id = ? ORDER BY ticket_id", (event_id,)).fetchall()
