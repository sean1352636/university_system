from education_system.systems.university.infrastructure.database.db import get_connection


class HolidaysMixin:
    def add_holiday(self, name, start_date, end_date=None, description="", recurring=False):
        """Add a holiday or special event"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        if end_date is None:
            end_date = start_date

        cursor.execute('''
        INSERT INTO holidays (holiday_name, start_date, end_date, description, recurring)
        VALUES (?, ?, ?, ?, ?)
        ''', (name, start_date, end_date, description, recurring))

        conn.commit()
        conn.close()

        # Mirror it onto the academic calendar. A holiday that only exists in
        # the scheduler's own table is invisible to everyone reading the
        # calendar, which is where people actually look for term dates and
        # closures.
        self._add_holiday_to_calendar(name, start_date, end_date, description)

        print(f"Holiday '{name}' added for {start_date}" + (f" to {end_date}" if end_date != start_date else ""))

    def _add_holiday_to_calendar(self, name, start_date, end_date, description=""):
        """Create the matching ``academic_calendar_events`` row.

        Best-effort: a holiday is still a holiday if the calendar write fails,
        so this reports and returns rather than undoing the holiday.
        """
        import logging
        logger = logging.getLogger(__name__)
        try:
            conn = get_connection(self.db_path, row_factory=False)
            try:
                cursor = conn.cursor()
                # Don't duplicate on a repeat add of the same holiday.
                existing = cursor.execute(
                    "SELECT 1 FROM academic_calendar_events "
                    " WHERE name = ? AND COALESCE(date_start, date) = ? "
                    "   AND event_type = 'holiday' LIMIT 1",
                    (name, start_date)).fetchone()
                if existing:
                    return
                # date_added is NOT NULL on this table, so it is supplied
                # rather than left to a default that does not exist.
                from datetime import datetime as _dt
                now = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    """INSERT INTO academic_calendar_events
                           (name, date, date_start, date_end, description,
                            event_type, audience, date_added, last_modified)
                       VALUES (?, ?, ?, ?, ?, 'holiday', 'All', ?, ?)""",
                    (name, start_date, start_date, end_date,
                     description or f"{name} (from Module Scheduling)",
                     now, now))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.warning("could not add holiday %r to the academic calendar",
                           name, exc_info=True)

    def list_holidays(self):
        """List all holidays"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT holiday_name, start_date, end_date, description, recurring
        FROM holidays
        ORDER BY start_date
        ''')

        holidays = cursor.fetchall()
        conn.close()

        if not holidays:
            print("No holidays found.")
            return

        print("\nHolidays and Special Events:")
        print("=" * 80)
        print(f"{'Name':<20} {'Start Date':<12} {'End Date':<12} {'Recurring':<10} {'Description':<20}")
        print("-" * 80)

        for holiday in holidays:
            name, start, end, desc, recurring = holiday
            recurring_str = "Yes" if recurring else "No"
            print(f"{name:<20} {start:<12} {end:<12} {recurring_str:<10} {desc:<20}")

        print("=" * 80)

    def check_holiday_conflicts(self, date):
        """Check if a date conflicts with holidays"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT holiday_name, description
        FROM holidays
        WHERE ? BETWEEN start_date AND end_date
        ''', (date,))

        conflicts = cursor.fetchall()
        conn.close()

        return conflicts
