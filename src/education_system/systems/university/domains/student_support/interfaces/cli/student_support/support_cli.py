"""The Student Support portal menu (command line).

The numbered options are the ones the portal has always had, in the same
order and with the same numbers for students and staff; the newer areas are
lettered groups below them, each shown only to the people who can use it
(the domain still checks every action). Ticket screens call the support
service, never the ticket tables.
"""

from __future__ import annotations

import logging

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
)
from education_system.systems.university.domains.student_support.interfaces.cli.student_support.common import (
    Leave,
    _t,
    ask,
    call,
    is_admin,
    is_staff,
    pause,
)

logger = logging.getLogger(__name__)


def _ensure_auth(auth) -> bool:
    if auth is not None:
        _auth.set_auth(auth)
    if _auth.get_auth_instance() is None:
        try:
            from education_system.systems.university.infrastructure.auth import UserAuth
            from education_system.systems.university.infrastructure.shared_context import get_auth
            _auth.set_auth(get_auth() or UserAuth())
        except Exception as exc:
            print(_t('auth_error', "Error initializing authentication system: {error}", error=exc))
            return False
    return True


def _support():
    """The legacy facade the older screens take as their argument."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        EnhancedStudentSupport,
    )
    from education_system.systems.university.domains.student_support.domain.student_support.config import (
        SupportConfig,
    )
    return EnhancedStudentSupport(SupportConfig())


def _numbered(staff: bool) -> list:
    """``[(action, label)]`` in the portal's long-standing order."""
    items = [
        ('dashboard', _t('o_dashboard', "📊 View Dashboard")),
        ('advanced_search', _t('o_search', "🔍 Advanced Search")),
        ('view_faqs', _t('o_faqs', "❓ Browse FAQs")),
        ('knowledge_base', _t('o_kb', "📚 Knowledge Base")),
        ('view_resources', _t('o_resources', "📋 Support Resources")),
    ]
    if not staff:
        items += [
            ('create_ticket', _t('o_create', "🎫 Create Support Ticket")),
            ('my_tickets', _t('o_my', "📋 My Support Tickets")),
            ('use_template', _t('o_template', "📋 Use Ticket Template")),
        ]
    else:
        items += [
            ('all_tickets', _t('o_all', "🎫 All Support Tickets")),
            ('reports', _t('o_reports', "📊 Generate Reports")),
            ('manage_templates', _t('o_templates', "🔧 Manage Templates")),
            ('manage_kb', _t('o_manage_kb', "📝 Manage Knowledge Base")),
            ('bulk_operations', _t('o_bulk', "🔄 Bulk Operations")),
            ('export_data', _t('o_export', "📤 Export Data")),
        ]
    items += [
        ('preferences', _t('o_prefs', "⚙️ Preferences")),
        ('notifications', _t('o_notifications', "🔔 Notifications")),
    ]
    return items


def _lettered(staff: bool, admin: bool) -> list:
    """``[(letter, action, label)]`` — the newer areas, grouped."""
    items = [('T', 'tickets', _t('l_tickets', "Tickets: view, reply, sharing consent"))]
    if staff:
        items += [
            ('N', 'new_for', _t('l_new_for', "Raise a ticket (for yourself or a student)")),
            ('C', 'caseload', _t('l_caseload', "Caseload & team queue")),
            ('W', 'work', _t('l_work', "Work a ticket: status, assign, escalate, merge, tier, "
                             "refer…")),
            ('S', 'student_360', _t('l_360', "Student 360 (support history)")),
            ('P', 'service_report', _t('l_report', "Service report")),
            ('M', 'teams', _t('l_teams', "Teams & duty rota")),
            ('I', 'incidents', _t('l_incidents', "Major incidents")),
            ('F', 'followed', _t('l_followed', "Tickets I follow")),
        ]
    else:
        items.append(('K', 'known_issues', _t('l_known', "Known issues (report that one "
                                               "affects you)")))
    if admin:
        items.append(('D', 'data_protection', _t('l_dp', "Data protection (retention, SAR, "
                                                  "erasure)")))
        items.append(('E', 'support_mail', _t('l_mail', "Support e-mail waiting for review")))
        items.append(('A', 'automation', _t('l_automation', "Automation settings (auto-close, "
                                             "SLA pause, e-mail in)")))
    items.append(('H', 'helpdesk', _t('l_helpdesk', "IT Helpdesk")))
    return items


def _dispatch(action: str, support) -> None:
    from education_system.systems.university.domains.student_support.interfaces.cli.student_support import (
        admin_cli,
        staff_cli,
        tickets_cli,
    )
    if action == 'dashboard':
        from education_system.systems.university.domains.student_support.domain.student_support.features.dashboard import (
            display_dashboard,
        )
        display_dashboard(support)
    elif action == 'advanced_search':
        from education_system.systems.university.domains.student_support.domain.student_support.features.search import (
            perform_advanced_search,
        )
        perform_advanced_search(support)
    elif action in ('view_faqs', 'view_resources', 'preferences'):
        from education_system.systems.university.domains.student_support.domain.student_support.utils import (
            helpers,
        )
        {'view_faqs': helpers.display_enhanced_faqs,
         'view_resources': helpers.display_enhanced_resources,
         'preferences': helpers.manage_preferences}[action](support)
    elif action in ('knowledge_base', 'manage_kb'):
        from education_system.systems.university.domains.student_support.domain.student_support.features import (
            knowledge_base,
        )
        (knowledge_base.browse_knowledge_base if action == 'knowledge_base'
         else knowledge_base.manage_knowledge_base_menu)(support)
    elif action == 'manage_templates':
        from education_system.systems.university.domains.student_support.domain.student_support.features.templates import (
            manage_templates_menu,
        )
        manage_templates_menu(support)
    elif action == 'notifications':
        from education_system.systems.university.domains.student_support.domain.student_support.features.notifications import (
            view_notifications,
        )
        view_notifications(support)
    elif action in ('incidents', 'followed', 'known_issues', 'support_mail', 'automation'):
        from education_system.systems.university.domains.student_support.domain.helpdesk import (
            collab_menus,
        )
        {'incidents': collab_menus.incidents_menu, 'followed': collab_menus.followed_menu,
         'known_issues': collab_menus.known_issues_menu, 'support_mail': collab_menus.mail_menu,
         'automation': collab_menus.automation_menu}[action](_auth.get_auth_instance())
    elif action == 'helpdesk':
        from education_system.systems.university.domains.student_support.domain.helpdesk import (
            display_helpdesk_menu,
        )
        display_helpdesk_menu(_auth.get_auth_instance())
    else:
        screens = {
            'create_ticket': tickets_cli.new_ticket,
            'new_for': tickets_cli.new_ticket,
            'my_tickets': tickets_cli.my_tickets,
            'use_template': lambda s: tickets_cli.new_ticket(s, use_template=True),
            'tickets': lambda s: tickets_cli.tickets_menu(),
            'all_tickets': lambda s: tickets_cli.all_tickets(s, open_ticket=staff_cli.work_ticket),
            'reports': staff_cli.reports_menu,
            'bulk_operations': staff_cli.bulk_menu,
            'export_data': staff_cli.export_menu,
            'caseload': lambda s: staff_cli.caseload_menu(),
            'work': lambda s: staff_cli.work_menu(),
            'student_360': lambda s: staff_cli.student_360(),
            'service_report': lambda s: staff_cli.service_report_screen(),
            'teams': lambda s: admin_cli.teams_menu(),
            'data_protection': lambda s: admin_cli.data_protection_menu(),
        }
        screens[action](support)


def display_support_menu(auth=None) -> None:
    """The Student Support portal. ``auth``: the signed-in session (else the
    one already given to the support module)."""
    if not _ensure_auth(auth):
        return
    try:
        support = _support()
    except Exception as exc:
        print(_t('init_error', "Error initializing enhanced student support system: {error}",
                 error=exc))
        return
    try:
        _loop(support)
    except Leave:
        print()


def _loop(support) -> None:
    while True:
        session = _auth.get_auth_instance()
        print("\n" + "=" * 60)
        print(_t('title', "🎓 ENHANCED STUDENT SUPPORT PORTAL"))
        print("=" * 60)
        current = getattr(session, 'current_user', None) if session else None
        if not current:
            print(_t('login_needed', "❌ You must be logged in to access the support portal."))
            return
        print(_t('logged_in', "👤 Logged in as: {user} ({role})", user=current.get('username'),
                 role=current.get('role')))
        staff, admin = is_staff(), is_admin()
        numbered = _numbered(staff)
        for i, (_action, label) in enumerate(numbered, 1):
            print(f"{i}. {label}")
        back = len(numbered) + 1
        print(f"{back}. " + _t('o_back', "↩️ Return to Main Menu"))
        print("-" * 60)
        lettered = _lettered(staff, admin)
        for letter, _action, label in lettered:
            print(f"{letter}. {label}")
        print("-" * 60)
        choice = ask(_t('choice_main', "Enter your choice: ")).upper()
        if choice in (str(back), '0', 'Q'):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(numbered):
            action = numbered[int(choice) - 1][0]
        else:
            action = next((a for letter, a, _l in lettered if letter == choice), None)
        if action is None:
            print(_t('invalid', "❌ Invalid choice. Please try again."))
            continue
        call(_dispatch, action, support)


__all__ = ['display_support_menu']
