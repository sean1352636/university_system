"""CLI menu router for the enhanced search & analytics system."""
from education_system.systems.university.services.analytics.advanced_search.analytics import (
    search_analytics_dashboard,
    student_demographics_reports,
    academic_performance_analysis,
)
from education_system.systems.university.services.analytics.advanced_search.search import (
    multi_criteria_search,
    fuzzy_name_search,
    module_enrollment_search,
    date_range_search,
    combined_filters_search,
)
from education_system.systems.university.services.analytics.advanced_search.text_search import advanced_text_search
from education_system.systems.university.services.analytics.advanced_search.conditional import conditional_logic_search
from education_system.systems.university.services.analytics.advanced_search.saved_searches import (
    manage_saved_searches,
    view_search_history,
    load_saved_search,
)
from education_system.systems.university.services.analytics.advanced_search.bulk_ops import (
    bulk_operations_menu,
    mass_email_students,
    batch_data_updates,
    bulk_export,
)
from education_system.systems.university.services.analytics.advanced_search.duplicates import duplicate_detection, data_quality_reports
from education_system.systems.university.services.analytics.advanced_search.charts import interactive_charts
from education_system.systems.university.services.analytics.advanced_search.reports import generate_custom_reports, manage_scheduled_reports
from education_system.systems.university.services.analytics.advanced_search.admin import view_search_audit_trail, manage_user_permissions
from education_system.systems.university.services.analytics.advanced_search.smart import auto_complete_search, smart_suggestions, predictive_analytics
from education_system.systems.university.services.analytics.advanced_search.system import performance_optimization, export_system_statistics
from education_system.systems.university.services.analytics.advanced_search.db import init_enhanced_database


def display_enhanced_menu():
    """Display the enhanced search menu with all new features"""
    while True:
        print("\n" + "="*80)
        print("🔍 ENHANCED STUDENT SEARCH & ANALYTICS SYSTEM")
        print("="*80)

        print("\n📊 ANALYTICS & REPORTING:")
        print("1.  Search Analytics Dashboard")
        print("2.  Student Demographics Reports")
        print("3.  Academic Performance Analysis")

        print("\n🔍 ADVANCED SEARCH:")
        print("4.  Multi-Criteria Student Search")
        print("5.  Fuzzy Name Search")
        print("6.  Module Enrollment Search")
        print("7.  Date Range Search")
        print("8.  Combined Filters Search")
        print("9.  Advanced Text Search (Regex/Wildcard)")
        print("10. Conditional Logic Search")

        print("\n💾 SEARCH MANAGEMENT:")
        print("11. Saved Search Profiles")
        print("12. Search History & Favorites")
        print("13. Load Saved Search")

        print("\n🔧 BULK OPERATIONS:")
        print("14. Bulk Operations on Results")
        print("15. Mass Email to Students")
        print("16. Batch Data Updates")

        print("\n📋 DATA MANAGEMENT:")
        print("17. Duplicate Detection")
        print("18. Data Quality Reports")
        print("19. Enhanced Import/Export")

        print("\n📈 VISUALIZATION:")
        print("20. Interactive Charts & Graphs")
        print("21. Generate Custom Reports")

        print("\n🔐 ADMIN FEATURES:")
        print("22. Search Audit Trail")
        print("23. User Permissions Management")
        print("24. Scheduled Reports")

        print("\n⚡ SMART FEATURES:")
        print("25. Auto-Complete Search")
        print("26. Smart Suggestions")
        print("27. Predictive Analytics")

        print("\n🛠️ SYSTEM:")
        print("28. Initialize Enhanced Database")
        print("29. Performance Optimization")
        print("30. Export System Statistics")
        print("31. Return to Main Menu")

        choice = input("\nEnter your choice (1-31): ").strip()

        # Route to appropriate functions
        if choice == '1':
            search_analytics_dashboard()
        elif choice == '2':
            student_demographics_reports()
        elif choice == '3':
            academic_performance_analysis()
        elif choice == '4':
            multi_criteria_search()
        elif choice == '5':
            fuzzy_name_search()
        elif choice == '6':
            module_enrollment_search()
        elif choice == '7':
            date_range_search()
        elif choice == '8':
            combined_filters_search()
        elif choice == '9':
            advanced_text_search()
        elif choice == '10':
            conditional_logic_search()
        elif choice == '11':
            manage_saved_searches()
        elif choice == '12':
            view_search_history()
        elif choice == '13':
            load_saved_search()
        elif choice == '14':
            bulk_operations_menu()
        elif choice == '15':
            mass_email_students()
        elif choice == '16':
            batch_data_updates()
        elif choice == '17':
            duplicate_detection()
        elif choice == '18':
            data_quality_reports()
        elif choice == '19':
            bulk_export()
        elif choice == '20':
            interactive_charts()
        elif choice == '21':
            generate_custom_reports()
        elif choice == '22':
            view_search_audit_trail()
        elif choice == '23':
            manage_user_permissions()
        elif choice == '24':
            manage_scheduled_reports()
        elif choice == '25':
            auto_complete_search()
        elif choice == '26':
            smart_suggestions()
        elif choice == '27':
            predictive_analytics()
        elif choice == '28':
            init_enhanced_database()
        elif choice == '29':
            performance_optimization()
        elif choice == '30':
            export_system_statistics()
        elif choice == '31':
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")
