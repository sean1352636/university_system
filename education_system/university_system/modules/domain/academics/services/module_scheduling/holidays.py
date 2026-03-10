from education_system.university_system.infrastructure.database.db import get_connection


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

        print(f"Holiday '{name}' added for {start_date}" + (f" to {end_date}" if end_date != start_date else ""))

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
