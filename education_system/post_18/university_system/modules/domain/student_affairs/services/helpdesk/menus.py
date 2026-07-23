from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
from datetime import datetime


def display_helpdesk_menu(auth):
    """Main menu for enhanced helpdesk system"""
    # Initialize enhanced helpdesk database
    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.database import init_helpdesk_db
    init_helpdesk_db()

    # Setup permissions
    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.permissions import setup_enhanced_helpdesk_permissions
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

        # Knowledge base
        print(f"{option_num}. 📚 {get_text('helpdesk.menu.knowledge_base', default='Knowledge Base')}")
        options.append('knowledge_base')
        option_num += 1

        # Admin options
        if auth.check_permission('view_all_tickets'):
            print(f"{option_num}. 👥 {get_text('helpdesk.menu.all_tickets', default='View All Support Tickets')}")
            options.append('view_all_tickets')
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
                    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.creation import create_ticket_enhanced
                    create_ticket_enhanced(auth)
                elif action == 'view_own_tickets':
                    view_user_tickets_enhanced(auth)
                elif action == 'advanced_search':
                    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.search import advanced_search_tickets
                    advanced_search_tickets(auth)
                elif action == 'saved_searches':
                    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.search import load_saved_searches
                    load_saved_searches(auth)
                elif action == 'knowledge_base':
                    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.knowledge_base import manage_knowledge_base
                    manage_knowledge_base(auth)
                elif action == 'view_all_tickets':
                    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.bulk import view_all_tickets_enhanced
                    view_all_tickets_enhanced(auth)
                elif action == 'analytics':
                    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.analytics.dashboard import generate_analytics_dashboard
                    generate_analytics_dashboard(auth)
                elif action == 'generate_report':
                    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.analytics.reports import generate_enhanced_ticket_report
                    generate_enhanced_ticket_report(auth)
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
        print("8. Return to main menu")

        choice = input("\nEnter your choice: ").strip()

        if choice == '1':
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.sla import manage_sla_policies
            manage_sla_policies(auth)
        elif choice == '2':
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.templates import manage_ticket_templates
            manage_ticket_templates(auth)
        elif choice == '3':
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.admin_workflows import manage_workflows
            manage_workflows(auth)
        elif choice == '4':
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.departments import manage_departments
            manage_departments(auth)
        elif choice == '5':
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.admin.organizations import manage_organizations
            manage_organizations(auth)
        elif choice == '6':
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.maintenance import system_maintenance
            system_maintenance(auth)
        elif choice == '7':
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.data_io import data_import_export
            data_import_export(auth)
        elif choice == '8':
            return
        else:
            print("Invalid choice. Please try again.")


def check_overdue_tickets(auth):
    """Check for overdue tickets and display alert"""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    SELECT COUNT(*) FROM support_tickets
    WHERE due_date IS NOT NULL
    AND due_date < ?
    AND status NOT IN ('resolved', 'closed')
    ''', (now,))

    overdue_count = cursor.fetchone()[0]

    if overdue_count > 0:
        print(f"\n⚠️  ALERT: {overdue_count} tickets are overdue!")

    conn.close()


def view_user_tickets_enhanced(auth):
    """Enhanced view of user's own tickets"""
    if not auth or not auth.current_user:
        print("You must be logged in to view your support tickets.")
        return

    if not auth.check_permission('view_own_tickets'):
        print("You don't have permission to view support tickets.")
        return

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Filter options
    print("\nFilter Options:")
    print("1. All my tickets")
    print("2. Open tickets only")
    print("3. In progress tickets only")
    print("4. Resolved/Closed tickets")

    filter_choice = input("Select filter (1-4): ").strip()

    where_clause = "WHERE user_id = ?"
    params = [auth.current_user['id']]

    if filter_choice == '2':
        where_clause += " AND status = 'open'"
    elif filter_choice == '3':
        where_clause += " AND status = 'in progress'"
    elif filter_choice == '4':
        where_clause += " AND status IN ('resolved', 'closed')"

    cursor.execute('''
    SELECT ticket_id, subject, category, subcategory, status, priority, impact, urgency,
           created_at, updated_at, due_date, assigned_to
    FROM support_tickets
    ''' + where_clause + '''
    ORDER BY
        CASE
            WHEN status = 'open' THEN 1
            WHEN status = 'in progress' THEN 2
            WHEN status = 'waiting for customer' THEN 3
            WHEN status = 'resolved' THEN 4
            WHEN status = 'closed' THEN 5
        END,
        CASE
            WHEN priority = 'high' THEN 1
            WHEN priority = 'medium' THEN 2
            WHEN priority = 'low' THEN 3
        END,
        updated_at DESC
    ''', params)

    tickets = cursor.fetchall()

    if not tickets:
        print("\nYou have no support tickets matching the selected filter.")
        conn.close()
        return

    print(f"\nYour Support Tickets ({len(tickets)} found):")
    print("=" * 100)
    print(f"{'ID':<5} {'Subject':<25} {'Category':<15} {'Status':<12} {'Priority':<8} {'Updated':<20}")
    print("=" * 100)

    for ticket in tickets:
        status_icon = {
            'open': '🆕',
            'in progress': '🔄',
            'waiting for customer': '⏳',
            'resolved': '✅',
            'closed': '🔒'
        }.get(ticket['status'], '📋')

        print(f"{ticket['ticket_id']:<5} {ticket['subject'][:23]:<25} {ticket['category'][:13]:<15} "
              f"{status_icon} {ticket['status']:<10} {ticket['priority'].upper():<8} {ticket['updated_at']:<20}")

        # Show overdue indicator
        if ticket['due_date']:
            due_dt = datetime.strptime(ticket['due_date'], '%Y-%m-%d %H:%M:%S')
            if due_dt < datetime.now() and ticket['status'] not in ['resolved', 'closed']:
                print(f"      ⚠️  OVERDUE (Due: {ticket['due_date']})")

    print("=" * 100)
