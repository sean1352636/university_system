"""The Helpdesk analytics dashboard (CLI) — figures only.

Every figure is a count or an average over the tickets the signed-in
support staff member may see (``student_support.auth.ticket_scope_sql``:
their teams and confidentiality tiers); no ticket text is read.
"""

from education_system.systems.university.infrastructure.database.db import get_connection
from datetime import datetime
import json


def collect_analytics(auth) -> dict:
    """The dashboard's figures for ``auth`` (support staff; PermissionError
    otherwise)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, schema, store,
    )
    if not support_auth.is_case_worker(auth):
        raise PermissionError("You don't have permission to view analytics.")
    status = schema.status_case_sql('t.status')
    with store.reading() as conn:
        scope, sp = support_auth.ticket_scope_sql(auth, alias='t', conn=conn)

        def rows(sql, params=()):
            # Every query is limited to the viewer's tickets by ``scope``.
            return conn.execute(sql.replace('{scope}', scope), list(sp) + list(params)).fetchall()

        data = {'generated_at': datetime.now().isoformat(),
                'generated_by': (support_auth.user_of(auth) or {}).get('username')}
        data['total_tickets'] = rows("SELECT COUNT(*) FROM support_tickets t WHERE {scope}")[0][0]
        data['by_status'] = {schema.status_label(r[0]): r[1] for r in rows(
            f"SELECT {status} AS s, COUNT(*) AS n FROM support_tickets t WHERE {{scope}} "  # nosec B608 - fixed CASE
            "GROUP BY s ORDER BY n DESC")}
        r = rows('''
            SELECT AVG(CASE WHEN first_response_at IS NOT NULL
                       THEN (julianday(first_response_at) - julianday(created_at)) * 24 END),
                   AVG(CASE WHEN resolved_at IS NOT NULL
                       THEN (julianday(resolved_at) - julianday(created_at)) * 24 END)
            FROM support_tickets t WHERE {scope} AND created_at >= date('now', '-30 days')''')[0]
        data['avg_first_response_hours'], data['avg_resolution_hours'] = r[0], r[1]
        due = "COALESCE(t.sla_due_at, t.due_date)"
        r = rows(f'''
            SELECT COUNT(CASE WHEN resolved_at IS NULL OR resolved_at <= {due} THEN 1 END),
                   COUNT(CASE WHEN resolved_at IS NOT NULL AND resolved_at > {due} THEN 1 END),
                   COUNT(*)
            FROM support_tickets t WHERE {{scope}} AND {due} IS NOT NULL
              AND created_at >= date('now', '-30 days')''')[0]  # nosec B608 - fixed fragments
        data['sla'] = {'met': r[0], 'missed': r[1], 'total': r[2]}
        data['by_category'] = {str(c or ''): n for c, n in rows('''
            SELECT category, COUNT(*) AS n FROM support_tickets t
            WHERE {scope} AND created_at >= date('now', '-30 days')
            GROUP BY category ORDER BY n DESC''')}
        # assigned_to holds a username (older Helpdesk rows: a users.id).
        data['staff'] = [dict(zip(('username', 'assigned', 'resolved', 'avg_resolution_hours',
                                   'hours_logged'), r)) for r in rows(f'''
            SELECT u.username, COUNT(t.ticket_id),
                   COUNT(CASE WHEN {status} IN ('resolved', 'closed') THEN 1 END),
                   AVG(CASE WHEN t.resolved_at IS NOT NULL
                       THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24 END),
                   COALESCE((SELECT SUM(tt.duration_minutes) FROM ticket_time_tracking tt
                             WHERE tt.user_id = u.id
                               AND tt.created_at >= date('now', '-30 days')), 0) / 60.0
            FROM support_tickets t
            JOIN users u ON u.username = t.assigned_to OR CAST(u.id AS TEXT) = CAST(t.assigned_to AS TEXT)
            WHERE {{scope}} AND t.created_at >= date('now', '-30 days')
            GROUP BY u.id, u.username
            ORDER BY 3 DESC''')]  # nosec B608 - fixed fragments
        r = rows('''
            SELECT AVG(satisfaction_rating), COUNT(satisfaction_rating)
            FROM support_tickets t WHERE {scope} AND satisfaction_rating IS NOT NULL
              AND created_at >= date('now', '-30 days')''')[0]
        data['satisfaction'] = {'average': r[0], 'responses': r[1], 'distribution': {
            str(k): n for k, n in rows('''
            SELECT satisfaction_rating, COUNT(*) FROM support_tickets t
            WHERE {scope} AND satisfaction_rating IS NOT NULL
              AND created_at >= date('now', '-30 days')
            GROUP BY satisfaction_rating ORDER BY satisfaction_rating DESC''')}}
        r = rows('''
            SELECT COUNT(CASE WHEN created_at >= date('now', '-7 days') THEN 1 END),
                   COUNT(CASE WHEN created_at >= date('now', '-14 days')
                              AND created_at < date('now', '-7 days') THEN 1 END)
            FROM support_tickets t WHERE {scope}''')[0]
        data['trend'] = {'last_7_days': r[0], 'previous_7_days': r[1]}
    return data


def generate_analytics_dashboard(auth):
    """Generate comprehensive analytics dashboard"""
    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return

    try:
        data = collect_analytics(auth)
    except PermissionError as e:
        print(e)
        return

    print("\nHelpdesk Analytics Dashboard")
    print("=" * 50)

    print("\n📊 OVERALL STATISTICS")
    print("-" * 30)
    total_tickets = data['total_tickets']
    print(f"Total Tickets: {total_tickets}")
    for status, count in data['by_status'].items():
        percentage = (count / total_tickets * 100) if total_tickets > 0 else 0
        print(f"  {status}: {count} ({percentage:.1f}%)")

    print("\n⏱️ RESPONSE TIME ANALYSIS")
    print("-" * 30)
    if data['avg_first_response_hours']:
        print(f"Average First Response Time: {data['avg_first_response_hours']:.1f} hours")
    if data['avg_resolution_hours']:
        print(f"Average Resolution Time: {data['avg_resolution_hours']:.1f} hours")

    print("\n🎯 SLA COMPLIANCE")
    print("-" * 30)
    sla = data['sla']
    if sla['total'] > 0:
        print(f"SLA Compliance Rate: {sla['met'] / sla['total'] * 100:.1f}%")
        print(f"  Met SLA: {sla['met']}")
        print(f"  Missed SLA: {sla['missed']}")

    print("\n📋 TICKET CATEGORIES")
    print("-" * 30)
    for category, count in data['by_category'].items():
        print(f"  {category}: {count}")

    print("\n👥 STAFF PERFORMANCE (Last 30 Days)")
    print("-" * 30)
    for staff in data['staff']:
        assigned, resolved = staff['assigned'], staff['resolved']
        resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
        print(f"  {staff['username']}:")
        print(f"    Assigned: {assigned}, Resolved: {resolved} ({resolution_rate:.1f}%)")
        if staff['avg_resolution_hours']:
            print(f"    Avg Resolution Time: {staff['avg_resolution_hours']:.1f} hours")
        print(f"    Total Time Logged: {staff['hours_logged']:.1f} hours")

    print("\n⭐ CUSTOMER SATISFACTION")
    print("-" * 30)
    sat = data['satisfaction']
    if sat['responses'] > 0:
        print(f"Average Rating: {sat['average']:.1f}/5.0")
        print(f"Total Responses: {sat['responses']}")
        for rating, count in sat['distribution'].items():
            print(f"  {rating} stars: {count} ({count / sat['responses'] * 100:.1f}%)")

    print("\n📈 TRENDS (Last 7 Days vs Previous 7 Days)")
    print("-" * 30)
    recent, previous = data['trend']['last_7_days'], data['trend']['previous_7_days']
    if previous > 0:
        trend_percentage = ((recent - previous) / previous * 100)
        trend_direction = "📈" if trend_percentage > 0 else "📉" if trend_percentage < 0 else "➡️"
        print(f"Ticket Volume: {recent} vs {previous} {trend_direction} {abs(trend_percentage):.1f}%")

    export_choice = input("\nExport analytics to file? (y/n): ").strip().lower()
    if export_choice == 'y':
        export_analytics_report(auth)


def export_analytics_report(auth):
    """Export the dashboard's figures to a JSON file in the reports folder."""
    try:
        from education_system import paths
        data = collect_analytics(auth)
        paths.UNIVERSITY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = str(paths.UNIVERSITY_REPORTS_DIR / f"analytics_report_{timestamp}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Analytics report exported to {filename}")
        return filename
    except (PermissionError, OSError) as e:
        print(f"Error exporting analytics: {e}")
        return None
