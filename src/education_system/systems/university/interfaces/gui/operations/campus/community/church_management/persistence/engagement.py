"""Extracted ChurchManagementSystem behaviour."""
from .. import *

class ChurchPersistenceEngagementMixin:
    def _db_save_volunteer(self, volunteer):
        """Save a volunteer to the database."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                if volunteer.get('id'):
                    conn.execute("""
                        UPDATE church_volunteers SET name=?, email=?, phone=?, ministry=?,
                        availability=?, skills=?, status=? WHERE id=?
                    """, (volunteer.get('name'), volunteer.get('email'), volunteer.get('phone'),
                          volunteer.get('ministry'), volunteer.get('availability'),
                          volunteer.get('skills'), volunteer.get('status'), volunteer['id']))
                else:
                    cursor = conn.execute("""
                        INSERT INTO church_volunteers (name, email, phone, ministry, availability,
                        skills, status) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (volunteer.get('name'), volunteer.get('email'), volunteer.get('phone'),
                          volunteer.get('ministry'), volunteer.get('availability'),
                          volunteer.get('skills'), volunteer.get('status', 'Active')))
                    volunteer['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save volunteer: {e}")
            return False
