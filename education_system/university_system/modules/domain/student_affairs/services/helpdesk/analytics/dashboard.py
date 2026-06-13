from education_system.university_system.infrastructure.database.db import get_connection
from datetime import datetime
import json


def generate_analytics_dashboard(auth):
    """Generate comprehensive analytics dashboard"""
    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return

    if not auth.check_permission('view_all_tickets'):
        print("You don't have permission to view analytics.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nHelpdesk Analytics Dashboard")
    print("=" * 50)

    # Overall statistics
    print("\n📊 OVERALL STATISTICS")
    print("-" * 30)

    # Total tickets
    cursor.execute("SELECT COUNT(*) FROM support_tickets")
    total_tickets = cursor.fetchone()[0]
    print(f"Total Tickets: {total_tickets}")

    # Tickets by status
    cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM support_tickets
    GROUP BY status
    ORDER BY count DESC
    ''')

    status_stats = cursor.fetchall()
    for status, count in status_stats:
        percentage = (count / total_tickets * 100) if total_tickets > 0 else 0
        print(f"  {status.title()}: {count} ({percentage:.1f}%)")

    # Response time statistics
    print("\n⏱️ RESPONSE TIME ANALYSIS")
    print("-" * 30)

    cursor.execute('''
    SELECT
        AVG(CASE WHEN first_response_at IS NOT NULL
            THEN (julianday(first_response_at) - julianday(created_at)) * 24
            ELSE NULL END) as avg_first_response_hours,
        AVG(CASE WHEN resolved_at IS NOT NULL
            THEN (julianday(resolved_at) - julianday(created_at)) * 24
            ELSE NULL END) as avg_resolution_hours
    FROM support_tickets
    WHERE created_at >= date('now', '-30 days')
    ''')

    response_stats = cursor.fetchone()
    if response_stats[0]:
        print(f"Average First Response Time: {response_stats[0]:.1f} hours")
    if response_stats[1]:
        print(f"Average Resolution Time: {response_stats[1]:.1f} hours")

    # SLA compliance
    print("\n🎯 SLA COMPLIANCE")
    print("-" * 30)

    cursor.execute('''
    SELECT
        COUNT(CASE WHEN due_date IS NULL OR resolved_at IS NULL OR resolved_at <= due_date THEN 1 END) as met_sla,
        COUNT(CASE WHEN due_date IS NOT NULL AND resolved_at IS NOT NULL AND resolved_at > due_date THEN 1 END) as missed_sla,
        COUNT(*) as total_with_sla
    FROM support_tickets
    WHERE due_date IS NOT NULL AND created_at >= date('now', '-30 days')
    ''')

    sla_stats = cursor.fetchone()
    if sla_stats[2] > 0:
        sla_compliance = (sla_stats[0] / sla_stats[2] * 100)
        print(f"SLA Compliance Rate: {sla_compliance:.1f}%")
        print(f"  Met SLA: {sla_stats[0]}")
        print(f"  Missed SLA: {sla_stats[1]}")

    # Category analysis
    print("\n📋 TICKET CATEGORIES")
    print("-" * 30)

    cursor.execute('''
    SELECT category, COUNT(*) as count
    FROM support_tickets
    WHERE created_at >= date('now', '-30 days')
    GROUP BY category
    ORDER BY count DESC
    ''')

    category_stats = cursor.fetchall()
    for category, count in category_stats:
        print(f"  {category}: {count}")

    # Staff performance
    print("\n👥 STAFF PERFORMANCE (Last 30 Days)")
    print("-" * 30)

    cursor.execute('''
    SELECT
        u.username,
        COUNT(t.ticket_id) as assigned_tickets,
        COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        AVG(CASE WHEN t.resolved_at IS NOT NULL
            THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24
            ELSE NULL END) as avg_resolution_hours,
        COALESCE(SUM(tt.duration_minutes), 0) / 60.0 as total_hours
    FROM users u
    LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= date('now', '-30 days')
    LEFT JOIN ticket_time_tracking tt ON t.ticket_id = tt.ticket_id AND tt.user_id = u.id
    WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
    GROUP BY u.id, u.username
    HAVING assigned_tickets > 0
    ORDER BY resolved_tickets DESC
    ''')

    staff_stats = cursor.fetchall()
    for staff in staff_stats:
        username, assigned, resolved, avg_resolution, total_hours = staff
        resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
        print(f"  {username}:")
        print(f"    Assigned: {assigned}, Resolved: {resolved} ({resolution_rate:.1f}%)")
        if avg_resolution:
            print(f"    Avg Resolution Time: {avg_resolution:.1f} hours")
        print(f"    Total Time Logged: {total_hours:.1f} hours")

    # Customer satisfaction
    print("\n⭐ CUSTOMER SATISFACTION")
    print("-" * 30)

    cursor.execute('''
    SELECT
        AVG(satisfaction_rating) as avg_rating,
        COUNT(satisfaction_rating) as total_ratings
    FROM support_tickets
    WHERE satisfaction_rating IS NOT NULL
    AND created_at >= date('now', '-30 days')
    ''')

    satisfaction_stats = cursor.fetchone()
    if satisfaction_stats[1] > 0:
        print(f"Average Rating: {satisfaction_stats[0]:.1f}/5.0")
        print(f"Total Responses: {satisfaction_stats[1]}")

        # Rating distribution
        cursor.execute('''
        SELECT satisfaction_rating, COUNT(*) as count
        FROM support_tickets
        WHERE satisfaction_rating IS NOT NULL
        AND created_at >= date('now', '-30 days')
        GROUP BY satisfaction_rating
        ORDER BY satisfaction_rating DESC
        ''')

        rating_dist = cursor.fetchall()
        for rating, count in rating_dist:
            percentage = (count / satisfaction_stats[1] * 100)
            print(f"  {rating} stars: {count} ({percentage:.1f}%)")

    # Trend analysis
    print("\n📈 TRENDS (Last 7 Days vs Previous 7 Days)")
    print("-" * 30)

    cursor.execute('''
    SELECT
        COUNT(CASE WHEN created_at >= date('now', '-7 days') THEN 1 END) as recent_tickets,
        COUNT(CASE WHEN created_at >= date('now', '-14 days') AND created_at < date('now', '-7 days') THEN 1 END) as previous_tickets
    FROM support_tickets
    ''')

    trend_stats = cursor.fetchone()
    recent, previous = trend_stats

    if previous > 0:
        trend_percentage = ((recent - previous) / previous * 100)
        trend_direction = "📈" if trend_percentage > 0 else "📉" if trend_percentage < 0 else "➡️"
        print(f"Ticket Volume: {recent} vs {previous} {trend_direction} {abs(trend_percentage):.1f}%")

    conn.close()

    # Export option
    export_choice = input("\nExport analytics to file? (y/n): ").strip().lower()
    if export_choice == 'y':
        export_analytics_report(auth)


def export_analytics_report(auth):
    """Export analytics to a file"""
    try:
        from education_system.university_system.core import paths
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = str(paths.REPORTS_DIR / f"analytics_report_{timestamp}.json")

        # Generate detailed analytics data
        conn = get_connection()
        cursor = conn.cursor()

        analytics_data = {
            'generated_at': datetime.now().isoformat(),
            'generated_by': auth.current_user['username'],
            'summary': {},
            'detailed_stats': {}
        }

        # Add comprehensive data collection here
        # This would include all the analytics from the dashboard function

        with open(filename, 'w') as f:
            json.dump(analytics_data, f, indent=2)

        print(f"Analytics report exported to {filename}")

        conn.close()

    except Exception as e:
        print(f"Error exporting analytics: {e}")
