from __future__ import annotations

from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager
from university_system.modules.core.services.student_union_misc import context as ctx
from university_system.modules.core.services.student_union_misc.union_context import (
    display_club_menu, display_event_menu, display_facility_menu, display_election_menu,
    manage_engagement_rewards, manage_interclub_competitions, manage_peer_support_system,
    manage_academic_support, manage_mentorship_system, manage_equipment_system,
    manage_green_initiatives, manage_community_engagement, manage_virtual_events,
    manage_learning_integration, generate_advanced_analytics, manage_enhanced_voting,
    display_admin_menu
)

def display_student_union_menu():
    """Enhanced Student Union Portal with academic calendar sync"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to access the Student Union Portal.")
        return

    while True:
        print("\n🏛️ Enhanced Student Union Portal")
        print("=" * 45)

        # Core features
        print("📋 CORE FEATURES")
        print("1. Club Management")
        print("2. Events & Activities")
        print("3. Facilities & Bookings")
        print("4. Elections & Democracy")

        # Enhanced features
        print("\n🌟 ENHANCED FEATURES")
        print("5. Engagement Rewards System")
        print("6. Inter-club Competitions")
        print("7. Peer Support & Wellness")
        print("8. Academic Support")
        print("9. Mentorship Program")

        # Specialized systems
        print("\n🎯 SPECIALIZED SYSTEMS")
        print("10. Equipment Management")
        print("11. Green Initiatives")
        print("12. Community Engagement")
        print("13. Virtual Events")
        print("14. Learning Integration")

        # Analytics and admin
        print("\n📊 ANALYTICS & ADMIN")
        if ctx.auth.check_permission('manage_all_clubs') or ctx.auth.check_permission('view_election_results'):
            print("15. Advanced Analytics")
            print("16. Enhanced Voting System")
            print("17. Admin Dashboard")

        # Navigation options
        print("\n18. Return to Main Menu")
        print("19. Sync Academic Calendar")

        choice = input("\nChoose an option (1-19): ").strip()

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
            ical_url = input("Academic calendar iCal URL: ").strip()
            manager.calendar_sync(ical_url)
            print("Done syncing. Check your calendar for any conflicts or upcoming deadlines.")
        else:
            print("Invalid choice. Please try again.")
