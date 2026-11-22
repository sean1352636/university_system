"""
Dashboard data and display for support system.
"""

import logging


from education_system.systems.university.domains.student_support.domain.student_support.config import (
    SupportConfig
)
from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod
from education_system.systems.university.domains.student_support.domain.student_support.features.notifications import _get_recent_notifications
from education_system.systems.university.domains.student_support.domain.student_support import store
from education_system.systems.university.domains.student_support.domain.student_support.schema import status_label

logger = logging.getLogger(__name__)

def get_dashboard_data(user_role, user_id):
    """Get dashboard data based on user role"""
    # Check if we have user information
    if not user_role or not user_id:
        raise PermissionError("You must be logged in to view dashboard")

    try:
        with store.reading() as conn:
            cursor = conn.cursor()
            dashboard_data = {}
            if _auth_mod.is_support_staff({'username': '-', 'role': user_role}):
                dashboard_data = _get_staff_dashboard(user_id, cursor, user_role)
            else:
                dashboard_data = _get_student_dashboard(user_id, cursor)

        # Add common data
        # 50, not the default 10: the Notifications tab renders this same
        # list in full, and the dashboard widget slices its own top 3.
        dashboard_data['notifications'] = _get_recent_notifications(
            user_id, None, limit=50)
        dashboard_data['system_status'] = _get_system_status()

        logger.info(f"Dashboard data retrieved for {user_role} {user_id}")
        return dashboard_data

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise

def _username_for(user_id):
    """The username behind ``user_id``: the signed-in session's own when it is
    that session's id (which may be an auth.db id), else the local users row."""
    session = _auth_mod.user_of()
    if session and str(session.get('id')) == str(user_id) and session.get('username'):
        return session['username']
    with store.reading() as conn:
        row = conn.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
    return row[0] if row else None


def _labelled(rows):
    """``{status label: count}`` from ``(status, count)`` rows (labels keep the
    keys the dashboards have always used: 'Open', 'In Progress', ...)."""
    out = {}
    for status, count in rows:
        label = status_label(status)
        out[label] = out.get(label, 0) + count
    return out


def _get_student_dashboard(user_id, cursor):
    """Get dashboard data for students"""
    username = _username_for(user_id)
    if not username:
        return {}
    session = {'username': username, 'role': 'student'}
    scope_sql, scope_params = _auth_mod.ticket_scope_sql(session, conn=cursor.connection)

    # Get ticket statistics
    cursor.execute(f'SELECT status, COUNT(*) FROM support_tickets WHERE {scope_sql} GROUP BY status',  # nosec B608
                   scope_params)
    ticket_stats = _labelled(cursor.fetchall())

    # Get recent tickets
    cursor.execute(f'''
    SELECT ticket_id, subject, status, created_at
    FROM support_tickets
    WHERE {scope_sql}
    ORDER BY created_at DESC
    LIMIT 5
    ''', scope_params)  # nosec B608
    recent_tickets = [dict(zip(['ticket_id', 'title', 'status', 'created_datetime'], row)) for row in cursor.fetchall()]

    # Get featured resources
    cursor.execute('SELECT * FROM support_resources WHERE is_featured = 1 LIMIT 5')
    featured_resources = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    return {
        'ticket_stats': ticket_stats,
        'recent_tickets': recent_tickets,
        'featured_resources': featured_resources,
        'quick_actions': [
            {'name': 'Create Ticket', 'action': 'create_ticket'},
            {'name': 'View FAQs', 'action': 'view_faqs'},
            {'name': 'Search Resources', 'action': 'search_resources'}
        ]
    }

def _get_staff_dashboard(user_id, cursor, role='staff'):
    """Get dashboard data for staff (only tickets the person may see)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        caseload,
    )
    username = _username_for(user_id)
    if not username:
        return {}
    session = {'username': username, 'role': role}
    conn = cursor.connection
    scope_sql, scope_params = _auth_mod.ticket_scope_sql(session, alias='st', conn=conn)

    # Get assigned tickets
    cursor.execute('''
    SELECT status, COUNT(*)
    FROM support_tickets
    WHERE assigned_to = ?
    GROUP BY status
    ''', (username,))
    assigned_stats = _labelled(cursor.fetchall())

    # High priority tickets the person may see
    rows = conn.execute(f'''
    SELECT st.* FROM support_tickets st
    WHERE lower(st.priority) IN ('high', 'critical', 'urgent')
    AND st.status NOT IN ('resolved', 'closed') AND {scope_sql}
    ORDER BY
        CASE lower(st.priority)
            WHEN 'critical' THEN 1
            WHEN 'urgent' THEN 2
            WHEN 'high' THEN 3
        END,
        st.created_at ASC
    LIMIT 50
    ''', scope_params).fetchall()  # nosec B608 - scope from auth.ticket_scope_sql
    priority_tickets = [{'ticket_id': r['ticket_id'], 'title': r['subject'], 'priority': r['priority'],
                         'created_datetime': r['created_at'], 'student_id': r['user_id']}
                        for r in rows if _auth_mod.can_view_ticket(session, r, conn)][:10]

    # Team performance metrics (counts only)
    cursor.execute('''
    SELECT
        COUNT(*) as total_tickets,
        AVG(CASE WHEN resolved_at IS NOT NULL
            THEN julianday(resolved_at) - julianday(created_at)
            END) as avg_resolution_days,
        COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_count
    FROM support_tickets
    WHERE created_at >= date('now', '-30 days')
    ''')

    performance_data = cursor.fetchone()
    performance_metrics = {
        'total_tickets_month': performance_data[0] or 0,
        'avg_resolution_time': round(performance_data[1] or 0, 2),
        'resolution_rate': round((performance_data[2] or 0) / max(performance_data[0] or 1, 1) * 100, 1)
    }

    # Recent activity on tickets the person may see (no internal notes' text)
    rows = conn.execute(f'''
    SELECT tr.ticket_id, st.subject, tr.response_datetime, tr.responder_role, st.*
    FROM ticket_responses tr
    JOIN support_tickets st ON tr.ticket_id = st.ticket_id
    WHERE tr.response_datetime >= datetime('now', 'localtime', '-24 hours') AND {scope_sql}
    ORDER BY tr.response_datetime DESC
    LIMIT 50
    ''', scope_params).fetchall()  # nosec B608 - scope from auth.ticket_scope_sql
    recent_activity = [{'ticket_id': r[0], 'title': r[1], 'datetime': r[2], 'responder_role': r[3]}
                       for r in rows if _auth_mod.can_view_ticket(session, r, conn)][:10]

    # Caseload by SLA urgency and the team queue
    try:
        mine = caseload.my_caseload(session)
        queue = caseload.team_queue(session)
        sla_summary = {
            'my_open': len(mine),
            'my_breached': sum(1 for t in mine if t['breached']),
            'my_due_4h': sum(1 for t in mine if not t['breached'] and t['hours_left'] is not None
                             and t['hours_left'] <= 4),
            'team_queue': len(queue),
            'next_up': mine[:5],
        }
    except Exception:
        logger.warning("Caseload summary unavailable", exc_info=True)
        sla_summary = {}

    return {
        'assigned_stats': assigned_stats,
        'priority_tickets': priority_tickets,
        'performance_metrics': performance_metrics,
        'recent_activity': recent_activity,
        'sla': sla_summary,
        'quick_actions': [
            {'name': 'View Assigned Tickets', 'action': 'view_assigned'},
            {'name': 'Manage Templates', 'action': 'manage_templates'},
            {'name': 'View Reports', 'action': 'view_reports'}
        ]
    }

def _get_system_status():
    """Current state of the support service, from the tickets themselves:
    escalated tickets, open SLA breaches and whether the background worker
    (escalations, SLA checks) is running in this process."""
    import threading
    status = {'status': 'operational', 'active_incidents': 0, 'sla_breaches_open': 0,
              'background_worker': any(t.name == 'support-jobs' and t.is_alive()
                                       for t in threading.enumerate())}
    try:
        with store.reading() as conn:
            status['active_incidents'] = conn.execute(
                "SELECT COUNT(*) FROM support_tickets WHERE status = 'escalated'").fetchone()[0]
            status['sla_breaches_open'] = conn.execute(
                "SELECT COUNT(DISTINCT f.ticket_id) FROM support_escalation_fires f "
                "JOIN support_tickets t ON t.ticket_id = f.ticket_id WHERE f.rule_id IN (-2, -4) "
                "AND t.status NOT IN ('resolved', 'closed')").fetchone()[0]
    except Exception:
        logger.warning("Support status unreadable", exc_info=True)
        status['status'] = 'unknown'
        return status
    if status['active_incidents'] or status['sla_breaches_open']:
        status['status'] = 'attention needed'
    return status

def display_dashboard(support):
    """Display user dashboard"""
    try:
        dashboard_data = support.get_dashboard_data(_auth_mod.auth.current_user['role'], _auth_mod.auth.current_user['id'])

        print("\n📊 DASHBOARD")
        print("="*50)

        if _auth_mod.auth.current_user['role'] == 'student':
            # Student dashboard
            stats = dashboard_data.get('ticket_stats', {})
            print(f"🎫 Your Tickets: Open: {stats.get('Open', 0)}, In Progress: {stats.get('In Progress', 0)}, Resolved: {stats.get('Resolved', 0)}")

            print("\n📋 Recent Tickets:")
            for ticket in dashboard_data.get('recent_tickets', [])[:5]:
                print(f"  #{ticket['ticket_id']} - {ticket['title']} ({ticket['status']})")

            print("\n⭐ Featured Resources:")
            for resource in dashboard_data.get('featured_resources', [])[:3]:
                print(f"  📄 {resource['title']} - {resource['description'][:50]}...")

        else:
            # Staff dashboard
            stats = dashboard_data.get('assigned_stats', {})
            print(f"🎫 Assigned Tickets: Open: {stats.get('Open', 0)}, In Progress: {stats.get('In Progress', 0)}")

            metrics = dashboard_data.get('performance_metrics', {})
            print(f"📈 Performance (30 days): {metrics.get('total_tickets_month', 0)} tickets, {metrics.get('avg_resolution_time', 0)} days avg resolution")

            print("\n🚨 High Priority Tickets:")
            for ticket in dashboard_data.get('priority_tickets', [])[:5]:
                print(f"  #{ticket['ticket_id']} - {ticket['title']} ({ticket['priority']})")

        # Notifications
        notifications = dashboard_data.get('notifications', [])
        if notifications:
            print(f"\n🔔 Recent Notifications ({len(notifications)}):")
            for notif in notifications[:3]:
                status = "📫" if notif['is_read'] else "📬"
                print(f"  {status} {notif['title']}")

    except Exception as e:
        print(f"Error loading dashboard: {e}")

    input("\nPress Enter to continue...")

def display_support_menu(auth=None):
    """The Student Support portal menu. The screens live with the pastoral
    CLI (``interfaces/cli/student_support``); this name is kept for the
    launchers and integrations that import it from here."""
    from education_system.systems.university.domains.student_support.interfaces.cli.student_support.support_cli import (
        display_support_menu as _menu,
    )
    return _menu(auth)
