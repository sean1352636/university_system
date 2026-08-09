"""Extracted ChurchManagementSystem behaviour."""
from . import *

from .persistence.schema import init_church_database

class ChurchStateMixin:
    def save_data(self):
        """Save data is handled immediately on each operation."""
        pass

    def load_data(self):
        """Load data from database."""
        init_church_database()
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                # Load members
                cursor = conn.execute("SELECT * FROM church_members ORDER BY name")
                self.members = [dict(row) for row in cursor.fetchall()]

                # Load donations
                cursor = conn.execute("SELECT * FROM church_donations ORDER BY date DESC")
                self.donations = [dict(row) for row in cursor.fetchall()]

                # Load events from unified_events (primary key column is event_id)
                cursor = conn.execute("""
                    SELECT event_id AS id, title, description,
                           DATE(start_datetime) as date,
                           TIME(start_datetime) as time,
                           location, event_type, max_capacity as capacity,
                           created_at
                    FROM unified_events
                    WHERE source_type = 'church'
                    ORDER BY start_datetime DESC
                """)
                self.events = [dict(row) for row in cursor.fetchall()]

                # Load prayer requests
                cursor = conn.execute("SELECT * FROM church_prayer_requests ORDER BY date DESC")
                self.prayer_requests = [dict(row) for row in cursor.fetchall()]

                # Load sermons
                cursor = conn.execute("SELECT * FROM church_sermons ORDER BY date DESC")
                self.sermons = [dict(row) for row in cursor.fetchall()]

                # Load announcements
                cursor = conn.execute("SELECT * FROM church_announcements ORDER BY date DESC")
                self.announcements = [dict(row) for row in cursor.fetchall()]

                # Load volunteers
                cursor = conn.execute("SELECT * FROM church_volunteers ORDER BY name")
                self.volunteers = [dict(row) for row in cursor.fetchall()]

                # Load attendance records
                cursor = conn.execute("SELECT * FROM church_attendance ORDER BY service_date DESC")
                self.attendance_records = [dict(row) for row in cursor.fetchall()]

                # Load small groups
                cursor = conn.execute("SELECT * FROM church_small_groups ORDER BY name")
                rows = cursor.fetchall()
                self.small_groups = []
                for row in rows:
                    group = dict(row)
                    # Parse members JSON if stored as string
                    if group.get('members') and isinstance(group['members'], str):
                        try:
                            group['members'] = json.loads(group['members'])
                        except (ValueError, json.JSONDecodeError):
                            group['members'] = []
                    self.small_groups.append(group)

                # Load expenses
                cursor = conn.execute("SELECT * FROM church_expenses ORDER BY date DESC")
                self.expenses = [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error loading church data: {e}")
            # Initialize empty lists if database load fails
            self.members = []
            self.donations = []
            self.events = []
            self.prayer_requests = []
            self.sermons = []
            self.announcements = []
            self.volunteers = []
            self.attendance_records = []
            self.small_groups = []
            self.expenses = []
