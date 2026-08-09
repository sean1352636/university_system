"""Extracted ChurchManagementSystem behaviour."""
from .. import *

class ChurchPersistenceMinistryMixin:
    def _db_save_prayer_request(self, request):
        """Save a prayer request to the database."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO church_prayer_requests (requester_name, request, category,
                    status, date, is_anonymous) VALUES (?, ?, ?, ?, ?, ?)
                """, (request.get('requester_name'), request.get('request'), request.get('category'),
                      request.get('status', 'Pending'), request.get('date'),
                      1 if request.get('is_anonymous') else 0))
                request['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save prayer request: {e}")
            return False

    def _db_save_sermon(self, sermon):
        """Save a sermon to the database."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO church_sermons (title, speaker, date, scripture, summary, video_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sermon.get('title'), sermon.get('speaker'), sermon.get('date'),
                      sermon.get('scripture'), sermon.get('summary'), sermon.get('video_url')))
                sermon['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save sermon: {e}")
            return False
