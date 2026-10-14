from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import get_connection

class SQLiteEventRepository:
    def get(self, event_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') WHERE event_id = ?", (event_id,)
            ).fetchone()
