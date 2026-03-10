from __future__ import annotations

from education_system.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
from education_system.university_system.modules.domain.student_affairs.student_union.services import context as ctx
from education_system.university_system.modules.domain.student_affairs.student_union.services.union_context import (
    display_club_menu, display_event_menu, display_facility_menu, display_election_menu,
    manage_engagement_rewards, manage_interclub_competitions, manage_peer_support_system,
    manage_academic_support, manage_mentorship_system, manage_equipment_system,
    manage_green_initiatives, manage_community_engagement, manage_virtual_events,
    manage_learning_integration, generate_advanced_analytics, manage_enhanced_voting,
    display_admin_menu
)
from education_system.university_system.modules.shared.utils.i18n import get_text

def display_student_union_menu():
    """Enhanced Student Union Portal with academic calendar sync"""

    if not ctx.auth or not ctx.auth.current_user:
        print(get_text("student_union.menu.login_required"))
        return

    while True:
        print("\n" + get_text("student_union.menu.title"))
        print("=" * 45)

        # Core features
        print(get_text("student_union.menu.core_features_header"))
        print(get_text("student_union.menu.option_1"))
        print(get_text("student_union.menu.option_2"))
        print(get_text("student_union.menu.option_3"))
        print(get_text("student_union.menu.option_4"))

        # Enhanced features
        print("\n" + get_text("student_union.menu.enhanced_features_header"))
        print(get_text("student_union.menu.option_5"))
        print(get_text("student_union.menu.option_6"))
        print(get_text("student_union.menu.option_7"))
        print(get_text("student_union.menu.option_8"))
        print(get_text("student_union.menu.option_9"))

        # Specialized systems
        print("\n" + get_text("student_union.menu.specialized_systems_header"))
        print(get_text("student_union.menu.option_10"))
        print(get_text("student_union.menu.option_11"))
        print(get_text("student_union.menu.option_12"))
        print(get_text("student_union.menu.option_13"))
        print(get_text("student_union.menu.option_14"))

        # Analytics and admin
        print("\n" + get_text("student_union.menu.analytics_admin_header"))
        if ctx.auth.check_permission('manage_all_clubs') or ctx.auth.check_permission('view_election_results'):
            print(get_text("student_union.menu.option_15"))
            print(get_text("student_union.menu.option_16"))
            print(get_text("student_union.menu.option_17"))

        # Navigation options
        print("\n" + get_text("student_union.menu.option_18"))
        print(get_text("student_union.menu.option_19"))

        choice = input("\n" + get_text("student_union.menu.choose_option")).strip()

        # Core features
        if choice == '1':
            display_club_menu()
        elif choice == '2':
            display_event_menu()
        elif choice == '3':
            display_facility_menu()
        elif choice == '4':
            display_election_menu()

        # Enhanced features
        elif choice == '5':
            manage_engagement_rewards()
        elif choice == '6':
            manage_interclub_competitions()
        elif choice == '7':
            manage_peer_support_system()
        elif choice == '8':
            manage_academic_support()
        elif choice == '9':
            manage_mentorship_system()

        # Specialized systems
        elif choice == '10':
            manage_equipment_system()
        elif choice == '11':
            manage_green_initiatives()
        elif choice == '12':
            manage_community_engagement()
        elif choice == '13':
            manage_virtual_events()
        elif choice == '14':
            manage_learning_integration()

        # Analytics and admin
        elif choice == '15' and (ctx.auth.check_permission('manage_all_clubs') or ctx.auth.check_permission('view_election_results')):
            generate_advanced_analytics()
        elif choice == '16' and ctx.auth.check_permission('set_up_elections'):
            manage_enhanced_voting()
        elif choice == '17' and (ctx.auth.check_permission('manage_all_clubs') or ctx.auth.check_permission('view_election_results')):
            display_admin_menu()

        # Navigation and calendar sync
        elif choice == '18':
            return
        elif choice == '19':
            # Sync Academic Calendar
            manager = AcademicCalendarManager()
            ical_url = input(get_text("student_union.menu.calendar_url_prompt")).strip()
            manager.calendar_sync(ical_url)
            print(get_text("student_union.menu.sync_done"))
        else:
            print(get_text("student_union.menu.invalid_choice"))
