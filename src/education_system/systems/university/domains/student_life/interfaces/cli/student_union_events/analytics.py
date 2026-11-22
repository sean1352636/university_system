"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.student_life.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.student_life.interfaces.cli.student_union_events.context import auth

def event_popularity_predictions(cursor):
    """Predict event popularity based on historical data"""
    try:
        print("\n🔮 Event Popularity Predictions")
        print("=" * 40)

        # Analyze factors that contribute to event success
        cursor.execute('''
        SELECT
            category,
            AVG(current_attendees) as avg_attendance,
            COUNT(*) as event_count,
            AVG(CASE WHEN current_attendees >
                (SELECT AVG(current_attendees) FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union'))
                THEN 1 ELSE 0 END) as success_rate
        FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')
        WHERE event_date >= date('now', '-12 months')
        GROUP BY category
        HAVING COUNT(*) >= 3
        ORDER BY avg_attendance DESC
        ''')

        category_performance = cursor.fetchall()

        if category_performance:
            print("Event Category Performance:")
            print(f"{'Category':<20} {'Avg Attendance':<15} {'Events':<8} {'Success Rate':<12}")
            print("-" * 60)

            for cat in category_performance:
                success_rate = f"{cat[3]*100:.1f}%"
                print(f"{cat[0]:<20} {cat[1]:<15.1f} {cat[2]:<8} {success_rate:<12}")

        # Day of week analysis
        cursor.execute('''
        SELECT
            CASE CAST(strftime('%w', event_date) AS INTEGER)
                WHEN 0 THEN 'Sunday'
                WHEN 1 THEN 'Monday'
                WHEN 2 THEN 'Tuesday'
                WHEN 3 THEN 'Wednesday'
                WHEN 4 THEN 'Thursday'
                WHEN 5 THEN 'Friday'
                WHEN 6 THEN 'Saturday'
            END as day_of_week,
            AVG(current_attendees) as avg_attendance,
            COUNT(*) as event_count
        FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')
        WHERE event_date >= date('now', '-6 months')
        GROUP BY strftime('%w', event_date)
        ORDER BY avg_attendance DESC
        ''')

        day_analysis = cursor.fetchall()

        if day_analysis:
            print("\nBest Days for Events:")
            print(f"{'Day':<12} {'Avg Attendance':<15} {'Events Held':<12}")
            print("-" * 40)

            for day in day_analysis:
                print(f"{day[0]:<12} {day[1]:<15.1f} {day[2]:<12}")

        # Time of day analysis
        cursor.execute('''
        SELECT
            CASE
                WHEN start_time < '12:00' THEN 'Morning'
                WHEN start_time < '17:00' THEN 'Afternoon'
                ELSE 'Evening'
            END as time_period,
            AVG(current_attendees) as avg_attendance,
            COUNT(*) as event_count
        FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')
        WHERE event_date >= date('now', '-6 months')
        GROUP BY
            CASE
                WHEN start_time < '12:00' THEN 'Morning'
                WHEN start_time < '17:00' THEN 'Afternoon'
                ELSE 'Evening'
            END
        ORDER BY avg_attendance DESC
        ''')

        time_analysis = cursor.fetchall()

        if time_analysis:
            print("\nOptimal Event Times:")
            print(f"{'Time Period':<12} {'Avg Attendance':<15} {'Events Held':<12}")
            print("-" * 40)

            for time_period in time_analysis:
                print(f"{time_period[0]:<12} {time_period[1]:<15.1f} {time_period[2]:<12}")

        # Prediction recommendations
        print("\n💡 Recommendations for High Attendance:")
        if category_performance:
            best_category = category_performance[0]
            print(f"- Choose {best_category[0]} category events (avg {best_category[1]:.1f} attendees)")

        if day_analysis:
            best_day = day_analysis[0]
            print(f"- Schedule events on {best_day[0]}s (avg {best_day[1]:.1f} attendees)")

        if time_analysis:
            best_time = time_analysis[0]
            print(f"- Host events in the {best_time[0].lower()} (avg {best_time[1]:.1f} attendees)")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_event_analytics():
    """View analytics and statistics for events."""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view event analytics.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')")
        total_events = cursor.fetchone()[0]

        # Total attendees across all events
        cursor.execute("SELECT COALESCE(SUM(current_attendees), 0) FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')")
        total_attendees = cursor.fetchone()[0]

        # Average attendance rate
        cursor.execute('''
            SELECT COALESCE(
                AVG(CASE WHEN max_attendees > 0
                    THEN (current_attendees * 100.0 / max_attendees)
                    ELSE 0 END), 0)
            FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')
            WHERE max_attendees > 0
        ''')
        avg_attendance_rate = cursor.fetchone()[0]

        # Per-event breakdown
        cursor.execute('''
            SELECT e.event_name, e.max_attendees, e.current_attendees,
                   CASE WHEN e.max_attendees > 0
                        THEN ROUND(e.current_attendees * 100.0 / e.max_attendees, 1)
                        ELSE 0 END AS attendance_rate,
                   COALESCE(SUM(CASE WHEN f.amount > 0 THEN f.amount ELSE 0 END), 0) AS revenue,
                   COALESCE(SUM(CASE WHEN f.amount < 0 THEN ABS(f.amount) ELSE 0 END), 0) AS expenses
            FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e
            LEFT JOIN event_finances f ON e.event_id = f.event_id
            GROUP BY e.event_id
            ORDER BY e.event_date DESC
        ''')
        event_details = cursor.fetchall()

        # Print analytics report
        print("\nEvent Analytics Report")
        print("=" * 60)
        print(f"Total Events: {total_events}")
        print(f"Total Attendees: {total_attendees}")
        print(f"Average Attendance Rate: {avg_attendance_rate:.1f}%")

        if event_details:
            print(f"\n{'Event':<25} {'Capacity':<10} {'Attended':<10} {'Rate':<8} {'Revenue':<12} {'Expenses':<12}")
            print("-" * 77)
            for event in event_details:
                print(f"{str(event[0])[:24]:<25} {event[1]:<10} {event[2]:<10} "
                      f"{event[3]:<8} £{event[4]:<11.2f} £{event[5]:<11.2f}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
