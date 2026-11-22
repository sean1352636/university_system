from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.application.ports import get_connection

class EventAttendanceRepository:
    def list_for_event(self, event_id: int):
        with get_connection() as conn:
            # Attendance is recorded on the registration row (same rule as finance_ledger).
            return conn.execute(
                "SELECT * FROM unified_event_registrations WHERE event_id = ? "
                "AND (LOWER(COALESCE(attendance_status, '')) IN ('attended', 'checked_in', 'present') "
                "OR checked_in_at IS NOT NULL) ORDER BY registration_id",
                (event_id,)).fetchall()
