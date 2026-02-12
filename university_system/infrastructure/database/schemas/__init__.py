from __future__ import annotations
from university_system.core.i18n import init_i18n
init_i18n()

from .core_schemas import init_grade_system_db, init_academics_tables, init_courses_tables
from .finance_schemas import init_finance_system_db, init_finance_tables
from .student_union_schemas import init_student_union_db, init_student_affairs_tables, init_social_tables
from .communication_schemas import init_email_system_db, init_communication_tables
from .health_wellness_schemas import init_health_system_db, init_mental_health_system_db, init_health_tables, init_wellness_tables
from .lms_schemas import init_lms_system_db
from .attendance_warning_schemas import init_attendance_system_db, init_early_warning_system_db, init_peer_support_tables
from .degree_audit_schemas import init_degree_audit_system_db
from .career_alumni_schemas import init_career_services_system_db, init_alumni_relations_system_db, init_career_tables, init_alumni_tables
from .admissions_schemas import init_admissions_crm_system_db
from .analytics_bi_schemas import init_analytics_dashboard_system_db, init_business_intelligence_system_db, init_analytics_tables
from .campus_events_schemas import init_campus_events_system_db, init_smart_timetable_system_db
from .facilities_housing_schemas import init_facilities_management_system_db, init_housing_tables, init_parking_tables, init_travel_tables
from .research_integration_schemas import init_research_grants_system_db, init_integration_marketplace_system_db, init_integration_tables
from .ai_features_schemas import init_ai_features_system_db, init_ai_tables
from .admin_support_schemas import init_course_evaluation_system_db, init_auth_tables, init_audit_tables, init_documents_tables, init_support_tables, init_parent_tables, init_library_tables, init_commerce_tables, init_other_tables
from .aggregators import init_additional_missing_tables, init_all_missing_tables
from .misc_schemas import create_performance_indexes, initialize_all_schemas

__all__ = [
    'init_grade_system_db',
    'init_academics_tables',
    'init_courses_tables',
    'init_finance_system_db',
    'init_finance_tables',
    'init_student_union_db',
    'init_student_affairs_tables',
    'init_social_tables',
    'init_email_system_db',
    'init_communication_tables',
    'init_health_system_db',
    'init_mental_health_system_db',
    'init_health_tables',
    'init_wellness_tables',
    'init_lms_system_db',
    'init_attendance_system_db',
    'init_early_warning_system_db',
    'init_peer_support_tables',
    'init_degree_audit_system_db',
    'init_career_services_system_db',
    'init_alumni_relations_system_db',
    'init_career_tables',
    'init_alumni_tables',
    'init_admissions_crm_system_db',
    'init_analytics_dashboard_system_db',
    'init_business_intelligence_system_db',
    'init_analytics_tables',
    'init_campus_events_system_db',
    'init_smart_timetable_system_db',
    'init_facilities_management_system_db',
    'init_housing_tables',
    'init_parking_tables',
    'init_travel_tables',
    'init_research_grants_system_db',
    'init_integration_marketplace_system_db',
    'init_integration_tables',
    'init_ai_features_system_db',
    'init_ai_tables',
    'init_course_evaluation_system_db',
    'init_auth_tables',
    'init_audit_tables',
    'init_documents_tables',
    'init_support_tables',
    'init_parent_tables',
    'init_library_tables',
    'init_commerce_tables',
    'init_other_tables',
    'init_additional_missing_tables',
    'init_all_missing_tables',
    'create_performance_indexes',
    'initialize_all_schemas',
    'init_all_schemas',
]

def init_all_schemas():
    """Initialize all system database schemas."""
    # Phase 0: Re-initialize i18n
    init_i18n()
    init_grade_system_db()
    init_finance_system_db()
    init_student_union_db()
    init_email_system_db()
    init_health_system_db()
    init_lms_system_db()
    init_attendance_system_db()
    init_mental_health_system_db()
    init_early_warning_system_db()
    init_degree_audit_system_db()
    init_career_services_system_db()
    init_admissions_crm_system_db()
    init_analytics_dashboard_system_db()
    init_smart_timetable_system_db()
    init_campus_events_system_db()
    init_alumni_relations_system_db()
    init_research_grants_system_db()
    init_facilities_management_system_db()
    init_course_evaluation_system_db()
    init_business_intelligence_system_db()
    init_ai_features_system_db()
    init_integration_marketplace_system_db()
    init_academics_tables()
    init_ai_tables()
    init_alumni_tables()
    init_analytics_tables()
    init_audit_tables()
    init_auth_tables()
    init_career_tables()
    init_commerce_tables()
    init_communication_tables()
    init_courses_tables()
    init_documents_tables()
    init_finance_tables()
    init_health_tables()
    init_housing_tables()
    init_integration_tables()
    init_library_tables()
    init_other_tables()
    init_parent_tables()
    init_parking_tables()
    init_peer_support_tables()
    init_social_tables()
    init_student_affairs_tables()
    init_support_tables()
    init_travel_tables()
    init_wellness_tables()
    init_additional_missing_tables()
    create_performance_indexes()
    return
