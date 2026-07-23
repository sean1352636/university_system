from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.core import get_db_connection, auth


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
        cursor.execute("SELECT COUNT(*) FROM unified_event_registrations uer JOIN unified_events ue ON uer.event_id = ue.event_id WHERE ue.source_type = 'alumni'")
        total_registrations = cursor.fetchone()[0]
        print(f"Total Event Registrations: {total_registrations}")

        # Donations
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM alumni_donations')
        donation_stats = cursor.fetchone()
        print(f"Total Donations: {donation_stats[0]}")
        print(f"Total Amount Donated: £{donation_stats[1] or 0:.2f}")

        # Mentorships
        cursor.execute('SELECT COUNT(*) FROM alumni_mentorships WHERE status = "active"')
        active_mentors = cursor.fetchone()[0]
        print(f"Active Mentors: {active_mentors}")

        # Gift Aid summary
        try:
            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM donations WHERE is_gift_aided = 1')
            gift_aid_total = cursor.fetchone()[0]
            print(f"Gift Aid Eligible: £{gift_aid_total:,.2f}")
        except Exception:
            pass

        conn.close()
        print("\nReport generated successfully!")
    except Exception as e:
        print(f"Error generating alumni report: {e}")


def get_engagement_dashboard():
    """Get aggregated engagement dashboard data."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        total_alumni = cursor.execute('SELECT COUNT(*) FROM alumni').fetchone()[0]
        active_mentors = 0
        try:
            active_mentors = cursor.execute('SELECT COUNT(*) FROM alumni_mentorships WHERE status = "active"').fetchone()[0]
        except Exception:
            try:
                active_mentors = cursor.execute('SELECT COUNT(*) FROM mentorships WHERE status = "active"').fetchone()[0]
            except Exception:
                pass
        total_donated = cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM donations').fetchone()[0]
        upcoming_events = 0
        try:
            upcoming_events = cursor.execute("SELECT COUNT(*) FROM unified_events WHERE source_type = 'alumni' AND start_datetime >= date('now')").fetchone()[0]
        except Exception:
            pass
        gift_aid_total = 0
        try:
            gift_aid_total = cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM donations WHERE is_gift_aided = 1').fetchone()[0]
        except Exception:
            pass
        conn.close()
        return {
            "total_alumni": total_alumni,
            "active_mentors": active_mentors,
            "total_donated": round(total_donated, 2),
            "upcoming_events": upcoming_events,
            "gift_aid_total": round(gift_aid_total, 2),
        }
    except Exception as e:
        print(f"Error getting engagement dashboard: {e}")
        return {"total_alumni": 0, "active_mentors": 0, "total_donated": 0, "upcoming_events": 0, "gift_aid_total": 0}
