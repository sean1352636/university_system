from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
    display_language_menu_option,
)
from datetime import datetime


def display_helpdesk_menu(auth):
    """Main menu for enhanced helpdesk system"""
    # Initialize enhanced helpdesk database
    from education_system.systems.university.domains.student_support.domain.helpdesk.database import init_helpdesk_db
    init_helpdesk_db()

    # Setup permissions
    from education_system.systems.university.domains.student_support.domain.helpdesk.permissions import setup_enhanced_helpdesk_permissions
    setup_enhanced_helpdesk_permissions()

    while True:
        print("\n" + "="*50)
        print(f"🎫 {get_text('helpdesk.title', default='ENHANCED HELPDESK SYSTEM')}")
        print("="*50)

        # Check for overdue tickets (admin only)
        if auth.check_permission('view_all_tickets'):
            check_overdue_tickets(auth)

        options = []
        option_num = 1

        # User options
        if auth.check_permission('create_ticket'):
            print(f"{option_num}. 🆕 {get_text('helpdesk.menu.create_ticket', default='Create New Support Ticket')}")
            options.append('create_ticket')
            option_num += 1

        if auth.check_permission('view_own_tickets'):
            print(f"{option_num}. 📋 {get_text('helpdesk.menu.my_tickets', default='View My Support Tickets')}")
            options.append('view_own_tickets')
            option_num += 1

        # Search functionality
        print(f"{option_num}. 🔍 {get_text('helpdesk.menu.search', default='Advanced Search')}")
        options.append('advanced_search')
        option_num += 1

        if auth.current_user:
            print(f"{option_num}. 💾 {get_text('helpdesk.menu.saved_searches', default='Saved Searches')}")
            options.append('saved_searches')
            option_num += 1

        if auth.current_user:
            print(f"{option_num}. 📢 Known Issues")
            options.append('known_issues')
            option_num += 1

        # Knowledge base
        print(f"{option_num}. 📚 {get_text('helpdesk.menu.knowledge_base', default='Knowledge Base')}")
        options.append('knowledge_base')
        option_num += 1

        # Admin options
        if auth.check_permission('view_all_tickets'):
            print(f"{option_num}. 👥 {get_text('helpdesk.menu.all_tickets', default='View All Support Tickets')}")
            options.append('view_all_tickets')
            option_num += 1

            print(f"{option_num}. 👁️ Tickets I Follow")
            options.append('followed')
            option_num += 1

            print(f"{option_num}. 🚨 Major Incidents")
            options.append('incidents')
            option_num += 1

            print(f"{option_num}. 📊 {get_text('helpdesk.menu.analytics', default='Analytics Dashboard')}")
            options.append('analytics')
            option_num += 1

            print(f"{option_num}. 📈 {get_text('helpdesk.menu.reports', default='Generate Reports')}")
            options.append('generate_report')
            option_num += 1

            print(f"{option_num}. ⚙️ {get_text('helpdesk.menu.system', default='System Management')}")
            options.append('system_management')
            option_num += 1

        print(f"{option_num}. 🌐 {get_text('helpdesk.menu.language', default='Language')}")
        options.append('language')
        option_num += 1

        print(f"{option_num}. 🚪 {get_text('helpdesk.menu.return_main', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('helpdesk.prompt.choice', default='Enter your choice')}: ").strip()

        try:
            choice_idx = int(choice) - 1

            if choice_idx == len(options):  # Return option
                print(get_text('helpdesk.returning', default='Returning to main menu...'))
                return
            elif 0 <= choice_idx < len(options):
                action = options[choice_idx]

                if action == 'create_ticket':
                    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.creation import create_ticket_enhanced
                    create_ticket_enhanced(auth)
                elif action == 'view_own_tickets':
                    view_user_tickets_enhanced(auth)
                elif action == 'advanced_search':
                    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.search import advanced_search_tickets
                    advanced_search_tickets(auth)
                elif action == 'saved_searches':
                    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.search import load_saved_searches
                    load_saved_searches(auth)
                elif action == 'knowledge_base':
                    from education_system.systems.university.domains.student_support.domain.helpdesk.knowledge_base import manage_knowledge_base
                    manage_knowledge_base(auth)
                elif action == 'view_all_tickets':
                    from education_system.systems.university.domains.student_support.domain.helpdesk.bulk import view_all_tickets_enhanced
                    view_all_tickets_enhanced(auth)
                elif action == 'analytics':
                    from education_system.systems.university.domains.student_support.domain.helpdesk.analytics.dashboard import generate_analytics_dashboard
                    generate_analytics_dashboard(auth)
                elif action == 'generate_report':
                    from education_system.systems.university.domains.student_support.domain.helpdesk.analytics.reports import generate_enhanced_ticket_report
                    generate_enhanced_ticket_report(auth)
                elif action in ('known_issues', 'followed', 'incidents'):
                    from education_system.systems.university.domains.student_support.domain.helpdesk import (
                        collab_menus,
                    )
                    {'known_issues': collab_menus.known_issues_menu,
                     'followed': collab_menus.followed_menu,
                     'incidents': collab_menus.incidents_menu}[action](auth)
                elif action == 'system_management':
                    system_management_menu(auth)
                elif action == 'language':
                    display_language_menu_option()
            else:
                print(get_text('helpdesk.invalid_choice', default='Invalid choice. Please try again.'))
        except ValueError:
            print(get_text('helpdesk.invalid_choice', default='Invalid choice. Please try again.'))


def system_management_menu(auth):
    """System management menu for admins"""
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to access system management.")
        return

    while True:
        print("\nSystem Management")
        print("================")
        print("1. Manage SLA Policies")
        print("2. Manage Ticket Templates")
        print("3. Manage Workflows")
        print("4. Manage Departments")
        print("5. Manage Organizations")
        print("6. System Maintenance")
        print("7. Data Import/Export")
        print("8. Support E-mail (review quarantine)")
        print("9. Automation Settings")
        print("10. Return to main menu")

        choice = input("\nEnter your choice: ").strip()

        if choice == '1':
            from education_system.systems.university.domains.student_support.domain.helpdesk.admin.sla import manage_sla_policies
            manage_sla_policies(auth)
        elif choice == '2':
            from education_system.systems.university.domains.student_support.domain.helpdesk.admin.templates import manage_ticket_templates
            manage_ticket_templates(auth)
        elif choice == '3':
            from education_system.systems.university.domains.student_support.domain.helpdesk.admin.admin_workflows import manage_workflows
            manage_workflows(auth)
        elif choice == '4':
            from education_system.systems.university.domains.student_support.domain.helpdesk.admin.departments import manage_departments
            manage_departments(auth)
        elif choice == '5':
            from education_system.systems.university.domains.student_support.domain.helpdesk.admin.organizations import manage_organizations
            manage_organizations(auth)
        elif choice == '6':
            from education_system.systems.university.domains.student_support.domain.helpdesk.maintenance import system_maintenance
            system_maintenance(auth)
        elif choice == '7':
            from education_system.systems.university.domains.student_support.domain.helpdesk.data_io import data_import_export
            data_import_export(auth)
        elif choice in ('8', '9'):
            from education_system.systems.university.domains.student_support.domain.helpdesk import (
                collab_menus,
            )
            (collab_menus.mail_menu if choice == '8' else collab_menus.automation_menu)(auth)
        elif choice == '10':
            return
        else:
            print("Invalid choice. Please try again.")


def check_overdue_tickets(auth):
    """Alert support staff to the overdue tickets they may see (past their
    SLA due time and still active) — a count only."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, schema, store,
    )
    if not support_auth.is_case_worker(auth):
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    active = list(schema.ACTIVE_STATUSES)
    with store.reading() as conn:
        scope, params = support_auth.ticket_scope_sql(auth, conn=conn)
        overdue_count = conn.execute(
            f"SELECT COUNT(*) FROM support_tickets WHERE {scope} "  # nosec B608 - scope is built from fixed fragments
            "AND COALESCE(sla_due_at, due_date) IS NOT NULL AND COALESCE(sla_due_at, due_date) < ? "
            f"AND status IN ({', '.join('?' * len(active))})",
            params + [now] + active).fetchone()[0]

    if overdue_count > 0:
        print(f"\n⚠️  ALERT: {overdue_count} tickets are overdue!")


_STATUS_ORDER = {s: i for i, s in enumerate(
    ('open', 'in_progress', 'waiting_on_student', 'escalated', 'resolved', 'closed'))}
_PRIORITY_ORDER = {'critical': 0, 'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}


def view_user_tickets_enhanced(auth):
    """The signed-in person's own tickets (raised from either front-end),
    through the ticket service — with their tier, status and SLA standing."""
    if not auth or not auth.current_user:
        print("You must be logged in to view your support tickets.")
        return

    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.service import (
        iter_tickets,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        sla_label, status_label, tier_badge,
    )
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )

    print("\nFilter Options:")
    print("1. All my tickets")
    print("2. Open tickets only")
    print("3. In progress tickets only")
    print("4. Resolved/Closed tickets")

    filter_choice = input("Select filter (1-4): ").strip()
    filters = {}
    if filter_choice == '2':
        filters['status'] = 'open'
    elif filter_choice == '3':
        filters['status'] = 'in_progress'
    elif filter_choice == '4':
        filters['status'] = list(schema.DONE_STATUSES)

    try:
        tickets = list(iter_tickets(auth, filters, mine=True))
    except (PermissionError, ValueError) as e:
        print(e)
        return
    tickets.sort(key=lambda t: str(t.get('updated_at') or ''), reverse=True)
    tickets.sort(key=lambda t: (
        _STATUS_ORDER.get(schema.normalize_status(t.get('status'), default='open'), 9),
        _PRIORITY_ORDER.get(str(t.get('priority') or '').lower(), 9)))

    if not tickets:
        print("\nYou have no support tickets matching the selected filter.")
        return

    print(f"\nYour Support Tickets ({len(tickets)} found):")
    print("=" * 100)
    print(f"{'ID':<5} {'Subject':<25} {'Category':<15} {'Status':<20} {'Priority':<8} {'Updated':<20}")
    print("=" * 100)

    for ticket in tickets:
        status = schema.normalize_status(ticket.get('status'), default='open')
        status_icon = {
            'open': '🆕',
            'in_progress': '🔄',
            'waiting_on_student': '⏳',
            'escalated': '🔺',
            'resolved': '✅',
            'closed': '🔒'
        }.get(status, '📋')
        badge = tier_badge(ticket)
        subject = (badge + ' ' if badge else '') + str(ticket.get('subject') or '')
        print(f"{ticket['ticket_id']:<5} {subject[:23]:<25} {str(ticket.get('category') or '')[:13]:<15} "
              f"{status_icon} {status_label(ticket)[:17]:<18} {str(ticket.get('priority') or '').upper()[:8]:<8} "
              f"{str(ticket.get('updated_at') or ''):<20}")
        if status not in schema.DONE_STATUSES:
            label = sla_label(ticket)
            if label.startswith('Overdue') or label == 'Breached':
                print(f"      ⚠️  {label}")

    print("=" * 100)
