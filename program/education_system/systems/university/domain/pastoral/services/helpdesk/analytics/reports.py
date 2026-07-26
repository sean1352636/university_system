from education_system.systems.university.infrastructure.database.db import get_connection
from datetime import datetime, timedelta


def generate_enhanced_ticket_report(auth):
    """Generate comprehensive ticket reports"""
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not auth.check_permission('view_all_tickets'):
        print("You don't have permission to generate reports.")
        return

    print("\nEnhanced Ticket Report Generator")
    print("================================")
    print("1. Executive Summary Report")
    print("2. Staff Performance Report")
    print("3. SLA Compliance Report")
    print("4. Customer Satisfaction Report")
    print("5. Trend Analysis Report")
    print("6. Department Performance Report")
    print("7. Custom Date Range Report")

    report_choice = input("Select report type (1-7): ").strip()

    if report_choice == '1':
        generate_executive_summary(auth)
    elif report_choice == '2':
        generate_staff_performance_report(auth)
    elif report_choice == '3':
        generate_sla_compliance_report(auth)
    elif report_choice == '4':
        generate_satisfaction_report(auth)
    elif report_choice == '5':
        generate_trend_analysis_report(auth)
    elif report_choice == '6':
        generate_department_report(auth)
    elif report_choice == '7':
        generate_custom_date_report(auth)
    else:
        print("Invalid report selection.")


def generate_executive_summary(auth):
    """Generate executive summary report"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\nExecutive Summary Report")
    print("=" * 50)

    # Time period selection
    period = input("Select period (7d/30d/90d/1y): ").strip().lower()

    days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
    days = days_map.get(period, 30)

    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Key metrics
    cursor.execute('''
    SELECT
        COUNT(*) as total_tickets,
        COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
        COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority,
        AVG(CASE WHEN resolved_at IS NOT NULL
            THEN (julianday(resolved_at) - julianday(created_at)) * 24
            ELSE NULL END) as avg_resolution_hours,
        AVG(satisfaction_rating) as avg_satisfaction
    FROM support_tickets
    WHERE created_at >= ?
    ''', (start_date,))

    metrics = cursor.fetchone()

    if metrics[0] > 0:  # total_tickets
        resolution_rate = (metrics[1] / metrics[0] * 100)  # resolved/total

        print(f"\n📊 KEY METRICS ({period.upper()})")
        print("-" * 30)
        print(f"Total Tickets: {metrics[0]}")
        print(f"Resolution Rate: {resolution_rate:.1f}%")
        print(f"Open Tickets: {metrics[2]}")
        print(f"High Priority: {metrics[3]}")

        if metrics[4]:
            print(f"Avg Resolution Time: {metrics[4]:.1f} hours")

        if metrics[5]:
            print(f"Customer Satisfaction: {metrics[5]:.1f}/5.0")

        # Top categories
        print("\n📋 TOP CATEGORIES")
        print("-" * 30)

        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= ?
        GROUP BY category
        ORDER BY count DESC
        LIMIT 5
        ''', (start_date,))

        categories = cursor.fetchall()
        for cat, count in categories:
            percentage = (count / metrics[0] * 100)
            print(f"{cat}: {count} ({percentage:.1f}%)")

        # Staff workload
        print("\n👥 STAFF WORKLOAD")
        print("-" * 30)

        cursor.execute('''
        SELECT u.username,
               COUNT(t.ticket_id) as assigned,
               COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved
        FROM users u
        LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
        WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
        GROUP BY u.id, u.username
        HAVING assigned > 0
        ORDER BY assigned DESC
        LIMIT 5
        ''', (start_date,))

        staff_stats = cursor.fetchall()
        for username, assigned, resolved in staff_stats:
            resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
            print(f"{username}: {assigned} assigned, {resolved} resolved ({resolution_rate:.1f}%)")

    # Save report option
    save_choice = input("\nSave report to file? (y/n): ").strip().lower()
    if save_choice == 'y':
        from education_system.systems.university.domain.pastoral.services.helpdesk.notifications import save_report_to_file
        save_report_to_file("executive_summary", period, auth)

    conn.close()


def generate_staff_performance_report(auth):
    """Generate staff performance report"""
    print("\nStaff Performance Report")
    print("=" * 50)

    # Time period selection
    period = input("Select period (7d/30d/90d): ").strip().lower()
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 30)

    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT
        u.username,
        u.department,
        COUNT(t.ticket_id) as assigned_tickets,
        COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        AVG(CASE WHEN t.resolved_at IS NOT NULL
            THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24
            ELSE NULL END) as avg_resolution_hours,
        COALESCE(SUM(tt.duration_minutes), 0) / 60.0 as total_hours,
        AVG(t.satisfaction_rating) as avg_satisfaction
    FROM users u
    LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
    LEFT JOIN ticket_time_tracking tt ON t.ticket_id = tt.ticket_id AND tt.user_id = u.id
    WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
    GROUP BY u.id, u.username, u.department
    HAVING assigned_tickets > 0
    ORDER BY resolved_tickets DESC
    ''', (start_date,))

    staff_stats = cursor.fetchall()

    if staff_stats:
        print(f"\nStaff Performance ({period.upper()}):")
        print("=" * 100)
        print(f"{'Staff':<15} {'Dept':<12} {'Assigned':<8} {'Resolved':<8} {'Rate%':<6} {'Avg Hours':<10} {'Total Hrs':<10} {'Satisfaction':<12}")
        print("=" * 100)

        for staff in staff_stats:
            username, dept, assigned, resolved, avg_resolution, total_hours, avg_satisfaction = staff
            resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
            dept_display = (dept or 'None')[:10]

            print(f"{username[:13]:<15} {dept_display:<12} {assigned:<8} {resolved:<8} "
                  f"{resolution_rate:.1f}%{'':<2} {avg_resolution or 0:.1f}h{'':<5} "
                  f"{total_hours:.1f}h{'':<5} {avg_satisfaction or 0:.1f}/5.0{'':<7}")

        print("=" * 100)
    else:
        print("No staff performance data found.")

    conn.close()


def generate_sla_compliance_report(auth):
    """Generate SLA compliance report"""
    print("\nSLA Compliance Report")
    print("=" * 50)

    period = input("Select period (7d/30d/90d): ").strip().lower()
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 30)

    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    conn = get_connection()
    cursor = conn.cursor()

    # Overall SLA compliance
    cursor.execute('''
    SELECT
        COUNT(*) as total_tickets,
        COUNT(CASE WHEN due_date IS NOT NULL AND resolved_at IS NOT NULL
                   AND resolved_at <= due_date THEN 1 END) as met_sla,
        COUNT(CASE WHEN due_date IS NOT NULL AND resolved_at IS NOT NULL
                   AND resolved_at > due_date THEN 1 END) as missed_sla,
        COUNT(CASE WHEN due_date IS NOT NULL AND resolved_at IS NULL
                   AND due_date < datetime('now') THEN 1 END) as overdue
    FROM support_tickets
    WHERE created_at >= ? AND due_date IS NOT NULL
    ''', (start_date,))

    sla_stats = cursor.fetchone()

    if sla_stats[0] > 0:
        total, met, missed, overdue = sla_stats
        compliance_rate = (met / total * 100) if total > 0 else 0

        print(f"\nOverall SLA Compliance ({period.upper()}):")
        print("-" * 40)
        print(f"Total tickets with SLA: {total}")
        print(f"Met SLA: {met} ({compliance_rate:.1f}%)")
        print(f"Missed SLA: {missed}")
        print(f"Currently overdue: {overdue}")

        # SLA compliance by priority
        print("\nSLA Compliance by Priority:")
        print("-" * 40)

        cursor.execute('''
        SELECT
            priority,
            COUNT(*) as total,
            COUNT(CASE WHEN resolved_at <= due_date THEN 1 END) as met
        FROM support_tickets
        WHERE created_at >= ? AND due_date IS NOT NULL AND resolved_at IS NOT NULL
        GROUP BY priority
        ORDER BY priority
        ''', (start_date,))

        priority_stats = cursor.fetchall()

        for priority, total, met in priority_stats:
            rate = (met / total * 100) if total > 0 else 0
            print(f"{priority.capitalize()}: {met}/{total} ({rate:.1f}%)")
    else:
        print("No SLA data found for the selected period.")

    conn.close()


def generate_satisfaction_report(auth):
    """Generate customer satisfaction report"""
    print("\nCustomer Satisfaction Report")
    print("=" * 50)

    period = input("Select period (7d/30d/90d): ").strip().lower()
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 30)

    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    conn = get_connection()
    cursor = conn.cursor()

    # Overall satisfaction
    cursor.execute('''
    SELECT
        AVG(satisfaction_rating) as avg_rating,
        COUNT(satisfaction_rating) as total_responses,
        COUNT(CASE WHEN satisfaction_rating >= 4 THEN 1 END) as positive_responses
    FROM support_tickets
    WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
    ''', (start_date,))

    satisfaction_stats = cursor.fetchone()

    if satisfaction_stats[1] > 0:  # total_responses
        avg_rating, total_responses, positive_responses = satisfaction_stats
        satisfaction_rate = (positive_responses / total_responses * 100)

        print(f"\nOverall Satisfaction ({period.upper()}):")
        print("-" * 40)
        print(f"Average Rating: {avg_rating:.1f}/5.0")
        print(f"Total Responses: {total_responses}")
        print(f"Positive Ratings (4-5 stars): {positive_responses} ({satisfaction_rate:.1f}%)")

        # Rating distribution
        cursor.execute('''
        SELECT satisfaction_rating, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
        GROUP BY satisfaction_rating
        ORDER BY satisfaction_rating DESC
        ''', (start_date,))

        rating_dist = cursor.fetchall()

        print("\nRating Distribution:")
        print("-" * 40)
        for rating, count in rating_dist:
            percentage = (count / total_responses * 100)
            stars = "⭐" * int(rating)
            print(f"{stars} ({rating}): {count} ({percentage:.1f}%)")

        # Satisfaction by category
        print("\nSatisfaction by Category:")
        print("-" * 40)

        cursor.execute('''
        SELECT category, AVG(satisfaction_rating) as avg_rating, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
        GROUP BY category
        ORDER BY avg_rating DESC
        ''', (start_date,))

        category_stats = cursor.fetchall()

        for category, avg_rating, count in category_stats:
            print(f"{category}: {avg_rating:.1f}/5.0 ({count} responses)")
    else:
        print("No satisfaction data found for the selected period.")

    conn.close()


def generate_trend_analysis_report(auth):
    """Generate trend analysis report"""
    print("\nTrend Analysis Report")
    print("=" * 50)

    conn = get_connection()
    cursor = conn.cursor()

    # Monthly ticket trends (last 12 months)
    print("\nMonthly Ticket Trends (Last 12 Months):")
    print("-" * 50)

    cursor.execute('''
    SELECT
        strftime('%Y-%m', created_at) as month,
        COUNT(*) as total_tickets,
        COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets
    FROM support_tickets
    WHERE created_at >= date('now', '-12 months')
    GROUP BY month
    ORDER BY month
    ''')

    monthly_trends = cursor.fetchall()

    if monthly_trends:
        print(f"{'Month':<10} {'Total':<8} {'Resolved':<10} {'Resolution %':<12}")
        print("-" * 50)

        for month, total, resolved in monthly_trends:
            resolution_rate = (resolved / total * 100) if total > 0 else 0
            print(f"{month:<10} {total:<8} {resolved:<10} {resolution_rate:.1f}%")

    # Weekly trends (last 8 weeks)
    print("\nWeekly Ticket Trends (Last 8 Weeks):")
    print("-" * 50)

    cursor.execute('''
    SELECT
        strftime('%Y-W%W', created_at) as week,
        COUNT(*) as total_tickets
    FROM support_tickets
    WHERE created_at >= date('now', '-8 weeks')
    GROUP BY week
    ORDER BY week
    ''')

    weekly_trends = cursor.fetchall()

    if weekly_trends:
        print(f"{'Week':<10} {'Tickets':<8}")
        print("-" * 20)

        for week, total in weekly_trends:
            print(f"{week:<10} {total:<8}")

    conn.close()


def generate_department_report(auth):
    """Generate department performance report"""
    print("\nDepartment Performance Report")
    print("=" * 50)

    period = input("Select period (7d/30d/90d): ").strip().lower()
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 30)

    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT
        COALESCE(t.department, 'Unassigned') as department,
        COUNT(t.ticket_id) as total_tickets,
        COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        AVG(CASE WHEN t.resolved_at IS NOT NULL
            THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24
            ELSE NULL END) as avg_resolution_hours,
        AVG(t.satisfaction_rating) as avg_satisfaction
    FROM support_tickets t
    WHERE t.created_at >= ?
    GROUP BY t.department
    HAVING total_tickets > 0
    ORDER BY total_tickets DESC
    ''', (start_date,))

    dept_stats = cursor.fetchall()

    if dept_stats:
        print(f"\nDepartment Performance ({period.upper()}):")
        print("=" * 80)
        print(f"{'Department':<15} {'Total':<8} {'Resolved':<10} {'Rate%':<8} {'Avg Hours':<12} {'Satisfaction':<12}")
        print("=" * 80)

        for dept, total, resolved, avg_hours, avg_satisfaction in dept_stats:
            resolution_rate = (resolved / total * 100) if total > 0 else 0
            dept_display = dept[:13]

            print(f"{dept_display:<15} {total:<8} {resolved:<10} {resolution_rate:.1f}%{'':<4} "
                  f"{avg_hours or 0:.1f}h{'':<7} {avg_satisfaction or 0:.1f}/5.0{'':<7}")

        print("=" * 80)
    else:
        print("No department data found.")

    conn.close()


def generate_custom_date_report(auth):
    """Generate custom date range report"""
    print("\nCustom Date Range Report")
    print("=" * 50)

    start_date = input("Start date (YYYY-MM-DD): ").strip()
    end_date = input("End date (YYYY-MM-DD): ").strip()

    try:
        # Validate dates
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Basic statistics for the date range
    cursor.execute('''
    SELECT
        COUNT(*) as total_tickets,
        COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        AVG(CASE WHEN resolved_at IS NOT NULL
            THEN (julianday(resolved_at) - julianday(created_at)) * 24
            ELSE NULL END) as avg_resolution_hours,
        AVG(satisfaction_rating) as avg_satisfaction
    FROM support_tickets
    WHERE DATE(created_at) BETWEEN ? AND ?
    ''', (start_date, end_date))

    stats = cursor.fetchone()

    if stats[0] > 0:  # total_tickets
        total, resolved, avg_hours, avg_satisfaction = stats
        resolution_rate = (resolved / total * 100) if total > 0 else 0

        print(f"\nCustom Report ({start_date} to {end_date}):")
        print("-" * 50)
        print(f"Total Tickets: {total}")
        print(f"Resolved Tickets: {resolved} ({resolution_rate:.1f}%)")

        if avg_hours:
            print(f"Average Resolution Time: {avg_hours:.1f} hours")

        if avg_satisfaction:
            print(f"Average Satisfaction: {avg_satisfaction:.1f}/5.0")

        # Category breakdown
        print("\nTickets by Category:")
        print("-" * 30)

        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM support_tickets
        WHERE DATE(created_at) BETWEEN ? AND ?
        GROUP BY category
        ORDER BY count DESC
        ''', (start_date, end_date))

        categories = cursor.fetchall()

        for category, count in categories:
            percentage = (count / total * 100)
            print(f"{category}: {count} ({percentage:.1f}%)")
    else:
        print(f"No tickets found for the date range {start_date} to {end_date}.")

    conn.close()
