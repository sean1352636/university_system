"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import (
    display_admin_tools_menu,
    display_analytics_menu,
    display_batch_menu,
    display_business_intelligence_menu,
    display_enhanced_menu,
    display_predictive_analytics_menu,
    display_user_management_menu,
)

def display_administrative_tools_menu(auth):
    """Consolidated administrative tools and analytics menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access administrative tools.")
        return

    while True:
        print("\n" + "="*60)
        print("            ADMINISTRATIVE TOOLS & ANALYTICS")
        print("="*60)
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")

        print("\n👥 User & Access Management:")
        print("1. User Management")

        print("\n📊 Reporting & Analytics:")
        print("2. Enhanced Reporting")
        print("3. Student Analytics Dashboard")
        print("4. Predictive Analytics Dashboard")
        print("5. Business Intelligence Reports")

        print("\n🔧 System Operations:")
        print("6. Batch Operations")
        print("7. Advanced Search and Filtering")

        if auth.current_user['role'] == 'admin':
            print("\n🛠️ Database Administration:")
            print("8. Admin Database Tools")

        print("\n↩️ Navigation:")
        if auth.current_user['role'] == 'admin':
            print("9. Return to Main Menu")
            max_choice = 9
        else:
            print("8. Return to Main Menu")
            max_choice = 8
        print("="*60)

        choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()

        if choice == '1':
            # User Management
            display_user_management_menu(auth)
        elif choice == '2':
            # Enhanced Reporting
            from education_system.systems.university.services.analytics.enhanced_reporting import display_enhanced_reporting_menu
            display_enhanced_reporting_menu()
        elif choice == '3':
            # Student Analytics Dashboard
            display_analytics_menu()
        elif choice == '4':
            # Predictive Analytics Dashboard
            display_predictive_analytics_menu(auth)
        elif choice == '5':
            # Business Intelligence Reports
            display_business_intelligence_menu(auth)
        elif choice == '6':
            # Batch Operations
            display_batch_menu()
        elif choice == '7':
            # Advanced Search
            display_enhanced_menu()
        elif choice == '8':
            if auth.current_user['role'] == 'admin':
                # Admin Database Tools
                display_admin_tools_menu()
            else:
                # Return to main menu (non-admin)
                break
        elif choice == '9' and auth.current_user['role'] == 'admin':
            # Return to main menu (admin)
            break
        else:
            print("Invalid choice. Please try again.")
