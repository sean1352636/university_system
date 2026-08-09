"""
Advanced Search & Analytics package.

Split from the original monolithic advanced_search.py into logical sub-modules.
All public names are re-exported here for backwards compatibility so that
``from education_system.systems.university.services.analytics.advanced_search import X``
continues to work unchanged.
"""

# ---------------------------------------------------------------------------
# Shared global state  (importers reference these directly)
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search._globals import (
    last_search_results,
    search_cache,
    search_history,
    saved_searches,
    current_user,
    SEARCH_ANALYTICS_COLUMNS_CACHE,
)

# ---------------------------------------------------------------------------
# Admin / audit
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.admin import (
    audit_log,
    view_search_audit_trail,
    manage_user_permissions,
    view_user_permissions,
    add_user_permissions,
    modify_user_permissions,
    remove_user_permissions,
)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.db import (
    refresh_search_analytics_columns,
    get_search_analytics_columns,
    ensure_search_analytics_schema,
    build_search_analytics_record,
    insert_search_analytics_record,
    init_enhanced_database,
    ensure_tables_exist,
    check_database_status,
)

# ---------------------------------------------------------------------------
# System utilities
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.system import (
    log_search,
    performance_optimization,
    export_system_statistics,
)

# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.export import (
    export_to_json,
    export_to_excel,
    export_to_csv,
    custom_format_export,
    export_single_student,
)

# ---------------------------------------------------------------------------
# Display / student detail
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.display import (
    display_search_results,
    display_student_detail,
    simulate_send_email,
    view_academic_history,
)

# ---------------------------------------------------------------------------
# Analytics & reporting
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.analytics import (
    search_analytics_dashboard,
    student_demographics_reports,
    academic_performance_analysis,
)

# ---------------------------------------------------------------------------
# Core searches
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.search import (
    multi_criteria_search,
    fuzzy_name_search,
    module_enrollment_search,
    date_range_search,
    combined_filters_search,
)

# ---------------------------------------------------------------------------
# Text search
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.text_search import (
    advanced_text_search,
    regex_search,
    wildcard_search,
    search_all_fields,
    phonetic_search,
)

# ---------------------------------------------------------------------------
# Conditional logic search
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.conditional import (
    conditional_logic_search,
    add_condition,
    remove_condition,
    execute_conditional_search,
)

# ---------------------------------------------------------------------------
# Saved searches / history
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.saved_searches import (
    manage_saved_searches,
    save_search_profile,
    view_saved_searches,
    load_saved_search,
    execute_loaded_search,
    view_search_history,
    repeat_search,
    delete_saved_search,
    share_search_profile,
)

# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.bulk_ops import (
    bulk_operations_menu,
    bulk_export,
    save_last_search_results,
    mass_email_students,
    batch_data_updates,
    generate_email_list,
    create_student_groups,
    mark_for_followup,
    bulk_enrollment_management,
)

# ---------------------------------------------------------------------------
# Duplicate detection & data quality
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.duplicates import (
    duplicate_detection,
    detect_exact_name_duplicates,
    detect_fuzzy_name_duplicates,
    comprehensive_duplicate_analysis,
    detect_email_pattern_duplicates,
    data_quality_reports,
)

# ---------------------------------------------------------------------------
# Charts / visualisation
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.charts import (
    interactive_charts,
    generate_age_histogram,
    generate_course_pie_chart,
    generate_registration_timeline,
    generate_gender_course_chart,
    generate_module_popularity_chart,
)

# ---------------------------------------------------------------------------
# Reports (custom & scheduled)
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.reports import (
    generate_custom_reports,
    generate_student_summary_report,
    generate_module_enrollment_report,
    generate_demographics_analysis,
    generate_performance_report,
    generate_custom_sql_report,
    manage_scheduled_reports,
    view_scheduled_reports,
    create_scheduled_report,
    modify_scheduled_report,
    delete_scheduled_report,
    run_scheduled_report,
)

# ---------------------------------------------------------------------------
# Smart / predictive features
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.smart import (
    auto_complete_search,
    smart_suggestions,
    predictive_analytics,
    identify_at_risk_students,
    enrollment_prediction,
    module_success_probability,
    graduation_timeline_forecast,
)

# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
from education_system.systems.university.services.analytics.advanced_search.menu import display_enhanced_menu
