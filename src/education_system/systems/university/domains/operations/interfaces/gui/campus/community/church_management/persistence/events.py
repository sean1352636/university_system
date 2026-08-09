"""Extracted ChurchManagementSystem behaviour."""
from .. import *

class ChurchPersistenceEventsMixin:
    def _db_save_event(self, event):
        """Save an event to the unified_events table with source_type='church'."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            # Combine date + time into start_datetime
            date_part = event.get('date', '')
            time_part = event.get('time', '')
            if date_part and time_part:
                start_datetime = f"{date_part} {time_part}"
            elif date_part:
                start_datetime = f"{date_part} 00:00"
            else:
                start_datetime = ''

            with get_connection() as conn:
                if event.get('id'):
                    conn.execute("""
                        UPDATE unified_events SET title=?, description=?, start_datetime=?,
                        location=?, event_type=?, max_capacity=? WHERE event_id=? AND source_type='church'
                    """, (event.get('title'), event.get('description'), start_datetime,
                          event.get('location'), event.get('event_type'),
                          event.get('capacity'), event['id']))
                else:
                    cursor = conn.execute("""
                        INSERT INTO unified_events (title, description, start_datetime, location,
                        event_type, max_capacity, source_type) VALUES (?, ?, ?, ?, ?, ?, 'church')
                    """, (event.get('title'), event.get('description'), start_datetime,
                          event.get('location'), event.get('event_type'),
                          event.get('capacity')))
                    event['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save event: {e}")
            return False
