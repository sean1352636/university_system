from education_system.systems.university.domain.pastoral.student_life.student_union.events.application.ports import get_connection

class EventAttendanceRepository:
    def list_for_event(self, event_id: int):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM event_attendance WHERE event_id = ? ORDER BY attendance_id", (event_id,)).fetchall()
