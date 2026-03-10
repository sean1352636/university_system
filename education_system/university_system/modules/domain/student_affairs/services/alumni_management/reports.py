from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from .core import get_db_connection, auth


def generate_alumni_report():
    """Generate alumni reports"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to generate alumni reports.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n--- Alumni Report ---")

        # Total alumni count
        cursor.execute('SELECT COUNT(*) FROM user_accounts WHERE role = "alumni"')
        total_alumni = cursor.fetchone()[0]
        print(f"Total Alumni: {total_alumni}")

        # Event participation
        cursor.execute('SELECT COUNT(*) FROM alumni_event_registrations')
        total_registrations = cursor.fetchone()[0]
        print(f"Total Event Registrations: {total_registrations}")

        # Donations
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM alumni_donations')
        donation_stats = cursor.fetchone()
        print(f"Total Donations: {donation_stats[0]}")
        print(f"Total Amount Donated: ${donation_stats[1] or 0:.2f}")

        # Mentorships
        cursor.execute('SELECT COUNT(*) FROM alumni_mentorships WHERE status = "active"')
        active_mentors = cursor.fetchone()[0]
        print(f"Active Mentors: {active_mentors}")

        conn.close()
        print("\nReport generated successfully!")
    except Exception as e:
        print(f"Error generating alumni report: {e}")
