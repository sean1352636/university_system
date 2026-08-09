"""Extracted ChurchManagementSystem behaviour."""
from .. import *

class ChurchPersistenceMembersMixin:
    def _db_save_member(self, member):
        """Save a member to the database."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                if member.get('id'):
                    conn.execute("""
                        UPDATE church_members SET name=?, email=?, phone=?, address=?,
                        join_date=?, membership_type=?, status=?, notes=? WHERE id=?
                    """, (member.get('name'), member.get('email'), member.get('phone'),
                          member.get('address'), member.get('join_date'), member.get('membership_type'),
                          member.get('status'), member.get('notes'), member['id']))
                else:
                    cursor = conn.execute("""
                        INSERT INTO church_members (name, email, phone, address, join_date,
                        membership_type, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (member.get('name'), member.get('email'), member.get('phone'),
                          member.get('address'), member.get('join_date'), member.get('membership_type'),
                          member.get('status', 'Active'), member.get('notes')))
                    member['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save member: {e}")
            return False
