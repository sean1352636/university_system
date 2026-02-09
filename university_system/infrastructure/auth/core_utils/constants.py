"""
Authentication Constants Module

This module centralizes all authentication-related constants including:
- Role definitions and descriptions
- Permission sets for each role
- Session and security configuration constants
- Authentication timeouts and limits

Part of the authentication module refactoring to improve maintainability
and clarity by separating constants from business logic.
"""

from typing import Dict, List

__all__ = [
    'ROLES',
    'PERMISSIONS',
    'DEFAULT_SESSION_TIMEOUT',
    'DEFAULT_MAX_LOGIN_ATTEMPTS',
    'DEFAULT_LOCKOUT_TIME',
    'PBKDF2_ITERATIONS',
    'PASSWORD_MIN_LENGTH',
]

# Role Definitions
ROLES: Dict[str, str] = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records'
}

# Updated Permission sets for different roles with AI detector permissions
PERMISSIONS: Dict[str, List[str]] = {
    'admin': [
        'create_student', 'view_any_student', 'update_any_student', 'delete_any_student',
        'view_own_record', 'update_own_profile',
        'manage_modules', 'view_assigned_modules',
        'manage_users', 'manage_roles',
        'manage_schedules', 'view_own_timetable', 'export_data',
        'manage_academic_calendar', 'view_academic_calendar',
        'view_reports', 'generate_reports', 'view_analytics',
        'backup_restore', 'system_config', 'view_logs',
        'export_data', 'import_data', 'export_module_data',
        'manage_grades', 'view_own_grades', 'manage_module_grades',
        'manage_attendance', 'view_own_attendance', 'manage_module_attendance',
        'manage_schedules', 'view_own_timetable', 'send_emails', 'batch_operations',
        'delete_any_permit', 'delete_own_permit', 'view_own_permit', 'update_own_permit',
        'update_violation', 'delete_violation', 'view_parking_lots', 'manage_parking_lots',
        'generate_reports', 'manage_books', 'manage_loans', 'view_books', 'checkout_books', 'view_loans',
        'manage_reservations', 'manage_reading_lists', 'manage_reviews',
        'manage_parking', 'create_permit', 'view_any_permit', 'update_any_permit',
        'delete_any_permit', 'register_vehicle', 'view_any_vehicle', 'update_any_vehicle',
        'delete_any_vehicle', 'record_violation', 'view_any_violation', 'update_violation',
        'delete_violation', 'manage_parking_lots', 'view_parking_lots',
        'view_own_permit', 'update_own_permit', 'register_own_vehicle', 'view_own_vehicle',
        'update_own_vehicle', 'view_own_violation',
        'manage_finances', 'view_financial_reports', 'export_financial_data', 'record_payments',
        'view_own_finances',
        'manage_alumni', 'view_alumni', 'view_own_alumni_profile', 'manage_events',
        'view_events', 'make_donation', 'view_own_donations', 'manage_mentorships',
        'view_menu', 'place_own_order', 'manage_menu', 'create_order',
        'view_internships', 'manage_internships', 'apply_for_internship', 'view_own_applications',
        'view_own_health_record', 'view_any_health_record', 'manage_health_records',
        'schedule_health_appointment', 'view_own_appointments', 'manage_health_appointments',
        'view_own_vaccinations', 'manage_vaccinations', 'view_health_advisories',
        'issue_health_advisories', 'view_health_resources', 'manage_courses', 'view_courses',
        'manage_accommodations', 'view_accommodations', 'approve_accommodations',
        # AI Detector permissions for admin (full access)
        'access_ai_detector', 'analyze_submissions', 'view_own_ai_results',
        'view_any_ai_results', 'manage_ai_whitelist', 'configure_ai_detector',
        'view_ai_statistics',
        # Plagiarism permissions for admin
        'check_plagiarism', 'manage_plagiarism_system', 'submit_document',
        'check_plagiarism_any_course', 'access_plagiarism_menu',
        'manage_trips', 'create_trips', 'view_trips', 'register_for_trips',
        'view_own_trip_registrations', 'cancel_trip_registration',
        'manage_trip_participants', 'view_trip_reports', 'manage_trip_expenses',
        'approve_trip_registrations',
        # Course Management permissions (admin - full access)
        'create_course', 'edit_course', 'delete_course', 'view_courses', 'search_courses',
        'manage_prerequisites', 'manage_course_status', 'manage_instructors',
        'assign_instructors', 'import_export_courses', 'database_backup',
        'bulk_course_update', 'system_maintenance', 'data_validation',
        'course_analytics', 'enrollment_reports', 'department_statistics',
        'view_course_schedules', 'manage_course_schedules', 'manage_waitlists',
        # Assignment System permissions (admin - full access)
        'view_assignments', 'create_assignment', 'manage_assignments', 'delete_assignment',
        'grade_submissions', 'view_all_submissions', 'manage_rubrics', 'create_rubric',
        'manage_templates', 'review_extensions', 'manage_peer_reviews',
        'assignment_analytics', 'advanced_analytics', 'custom_reports',
        'system_backup', 'data_cleanup', 'file_preview',
        # Grade Tracking permissions (admin - full access)
        'manage_students', 'add_student', 'edit_student', 'delete_student',
        'manage_modules', 'add_module', 'edit_module',
        'manage_assessments', 'create_assessment', 'edit_assessment', 'delete_assessment',
        'enter_grades', 'edit_grades', 'view_all_grades',
        'generate_transcripts', 'grade_curve_analysis', 'learning_outcomes',
        'competency_assessment', 'predictive_analytics', 'performance_analysis',
        'grade_statistics', 'grade_reports',
        # Finance GUI permissions (admin - full access to all 14 tabs)
        'manage_finances', 'view_core_finance', 'manage_payments', 'manage_fees',
        'manage_students_finance', 'view_financial_reports', 'manage_revenue_sources',
        'manage_collections', 'manage_financial_aid', 'manage_budget', 'financial_forecasting',
        'manage_research_grants', 'finance_admin_panel', 'finance_settings',
        # Health Portal permissions (admin - full system access)
        'view_any_health_record', 'manage_health_records', 'manage_health_appointments',
        'manage_vaccinations', 'view_health_reports', 'health_email_manager',
        'health_security_audit', 'health_data_management',
        # Shop Management permissions (admin - full management)
        'manage_shop_products', 'manage_shop_inventory', 'view_all_transactions',
        'manage_shop_discounts', 'view_shop_reports', 'shop_analytics', 'print_product_labels',
        # Student Support permissions (admin - full support system)
        'export_support_data', 'view_all_support_tickets', 'manage_support_system',
        # Helpdesk permissions (admin - full system management)
        'export_helpdesk_data', 'import_helpdesk_data', 'view_all_tickets',
        'create_knowledge_articles', 'helpdesk_analytics', 'generate_helpdesk_reports',
        'helpdesk_system_management', 'helpdesk_user_management', 'helpdesk_settings',
        # Internship Portal permissions (admin - full management)
        'view_all_applications', 'create_internship', 'edit_internship',
        'manage_placements', 'view_internship_reports',
        # Career Services permissions (admin - full career services)
        'manage_job_postings', 'manage_career_events', 'career_analytics',
        # Parent Portal permissions (admin - system management)
        'parent_admin_panel', 'manage_parent_accounts', 'link_students_to_parents',
        'view_any_parent_dashboard', 'parent_account_reports'
    ],
    'staff': [
        'create_student', 'view_any_student', 'update_any_student',
        'manage_modules', 'view_assigned_modules',
        'view_reports', 'generate_reports', 'view_analytics',
        'export_data', 'export_module_data', 'view_assignments',
        'manage_assignments', 'grade_assignments',
        'view_all_submissions', 'export_submission_data',
        'manage_grades', 'manage_attendance', 'manage_schedules',
        'send_emails', 'manage_courses', 'view_courses',
        'view_books', 'checkout_books', 'view_loans',
        'manage_reservations', 'manage_reading_lists', 'manage_reviews',
        'manage_schedules', 'view_own_timetable', 'export_data',
        'manage_academic_calendar', 'view_academic_calendar',
        'create_permit', 'view_any_permit', 'update_any_permit',
        'register_vehicle', 'view_any_vehicle', 'record_violation',
        'view_any_violation', 'view_parking_lots',
        'record_payments', 'view_financial_reports',
        'view_alumni', 'manage_events', 'view_events',
        'view_menu', 'place_own_order',
        'view_internships', 'manage_internships',
        'view_health_resources', 'view_health_advisories',
        'view_accommodations',
        'access_ai_detector', 'analyze_submissions',
        'view_any_ai_results', 'view_ai_statistics',
        'check_plagiarism', 'submit_document', 'access_plagiarism_menu',
        'create_trips', 'view_trips', 'manage_trip_participants',
        'view_trip_reports', 'manage_trip_expenses', 'approve_trip_registrations',
        # Course Management permissions (staff - teaching/administrative access)
        'create_course', 'edit_course', 'view_courses', 'search_courses',
        'manage_prerequisites', 'manage_course_status', 'import_export_courses',
        'course_analytics', 'enrollment_reports', 'department_statistics',
        'view_course_schedules', 'manage_course_schedules',
        # Assignment System permissions (staff - teaching and grading)
        'view_assignments', 'create_assignment', 'manage_assignments',
        'grade_submissions', 'view_all_submissions', 'grade_with_rubrics',
        'manage_groups', 'manage_peer_reviews', 'send_messages_to_students',
        'assignment_analytics', 'advanced_analytics', 'custom_reports', 'file_preview',
        # Grade Tracking permissions (staff - teaching and grading)
        'manage_students', 'manage_modules', 'manage_assessments',
        'create_assessment', 'edit_assessment',
        'enter_grades', 'edit_grades', 'view_all_grades',
        'generate_transcripts', 'grade_statistics', 'grade_reports',
        # Finance GUI permissions (staff - core operations, 11 tabs)
        'view_core_finance', 'manage_payments', 'manage_fees', 'manage_students_finance',
        'view_financial_reports', 'manage_revenue_sources', 'manage_collections',
        'manage_research_grants', 'finance_settings',
        # Health Portal permissions (staff - patient care operations)
        'view_any_health_record', 'manage_health_appointments', 'manage_vaccinations',
        'view_health_reports', 'health_email_manager',
        # Shop Management permissions (staff - full management)
        'manage_shop_products', 'manage_shop_inventory', 'view_all_transactions',
        'manage_shop_discounts', 'view_shop_reports', 'shop_analytics', 'print_product_labels',
        # Student Support permissions (staff - support operations)
        'export_support_data', 'view_all_support_tickets',
        # Helpdesk permissions (staff - support operations)
        'export_helpdesk_data', 'import_helpdesk_data', 'view_all_tickets',
        'create_knowledge_articles', 'helpdesk_analytics', 'generate_helpdesk_reports',
        # Internship Portal permissions (staff - create and manage)
        'view_all_applications', 'create_internship', 'edit_internship',
        'manage_placements', 'view_internship_reports',
        # Career Services permissions (staff - career management)
        'manage_job_postings', 'manage_career_events', 'career_analytics'
    ],
    'student': [
        'view_own_record', 'update_own_profile',
        'view_own_grades', 'view_own_attendance', 'view_own_timetable', 'view_assigned_modules',
        'view_books', 'checkout_books', 'view_loans', 'view_courses',
        'manage_reading_lists', 'manage_reviews',
        'view_own_permit', 'update_own_permit', 'register_own_vehicle', 'view_own_vehicle',
        'update_own_vehicle', 'view_own_violation',
        'view_own_finances', 'view_assignments', 'submit_assignment', 'view_own_submissions',
        'view_own_alumni_profile', 'view_events', 'make_donation', 'view_own_donations',
        'view_menu', 'place_own_order', 'view_own_timetable', 'view_academic_calendar',
        'view_internships', 'apply_for_internship', 'view_own_applications',
        'view_own_health_record', 'schedule_health_appointment', 'view_own_appointments',
        'view_own_vaccinations', 'view_health_advisories', 'view_health_resources',
        'send_emails', 'view_messages', 'send_messages', 'view_announcements',
        'access_communication_dashboard', 'use_chat_rooms', 'manage_notification_preferences',
        'access_ai_detector', 'analyze_submissions', 'view_own_ai_results',
        'submit_document', 'access_plagiarism_menu',
        'view_trips', 'register_for_trips', 'view_own_trip_registrations',
        'cancel_trip_registration',
        # Course Management permissions (student - read-only)
        'view_courses', 'search_courses', 'find_alternative_courses',
        'view_course_schedules', 'view_waitlists',
        # Assignment System permissions (student - submit and view own work)
        'view_assignments', 'submit_assignment', 'view_own_submissions',
        'request_extension', 'peer_review_dashboard', 'complete_peer_reviews',
        'view_messages', 'manage_notifications',
        # Grade Tracking permissions (student - view own data only)
        'view_own_grades', 'view_own_transcript',
        # Finance GUI permissions (student - self-service, 4 tabs)
        'view_own_finances', 'make_payments', 'view_fees', 'view_financial_aid',
        # Health Portal permissions (student - personal health access)
        'view_own_health_record', 'schedule_health_appointment', 'view_own_appointments',
        'view_own_vaccinations', 'manage_emergency_contacts', 'view_accessibility_tools',
        # Shop Management permissions (student - shopping only)
        'browse_shop_products', 'view_shopping_cart', 'place_shop_order', 'view_order_history',
        # Student Support permissions (student - self-service support)
        'create_support_ticket', 'view_own_support_tickets', 'search_support_tickets',
        # Helpdesk permissions (student - ticket management)
        'create_ticket', 'view_own_tickets', 'search_tickets', 'browse_knowledge_base',
        # Internship Portal permissions (student - application features)
        'view_internships', 'apply_for_internship', 'view_own_applications',
        # Career Services permissions (student - career development)
        'view_job_postings', 'apply_for_jobs', 'manage_resume', 'schedule_career_interviews',
        'attend_career_events', 'access_mentorship', 'develop_skills'
    ],
    'instructor': [
        'view_assigned_modules', 'manage_module_grades', 'view_module_students',
        'manage_module_attendance', 'export_module_data',
        'send_emails', 'view_assignments', 'manage_assignments',
        'grade_assignments', 'view_all_submissions', 'export_submission_data',
        'view_own_timetable', 'manage_schedules',
        'view_own_timetable', 'manage_schedules', 'view_academic_calendar',
        'view_books', 'view_health_resources', 'view_menu',
        'manage_reading_lists', 'manage_reviews',
        'access_ai_detector', 'analyze_submissions',
        'view_any_ai_results', 'view_ai_statistics',
        'check_plagiarism', 'submit_document', 'access_plagiarism_menu',
        'view_trips', 'register_for_trips', 'view_own_trip_registrations',
        'cancel_trip_registration',
        # Course Management permissions (instructor - same as staff)
        'create_course', 'edit_course', 'view_courses', 'search_courses',
        'manage_prerequisites', 'manage_course_status', 'import_export_courses',
        'course_analytics', 'enrollment_reports', 'department_statistics',
        'view_course_schedules', 'manage_course_schedules',
        # Assignment System permissions (instructor - same as staff)
        'view_assignments', 'create_assignment', 'manage_assignments',
        'grade_submissions', 'view_all_submissions', 'grade_with_rubrics',
        'manage_groups', 'manage_peer_reviews', 'send_messages_to_students',
        'assignment_analytics', 'advanced_analytics', 'custom_reports', 'file_preview',
        # Grade Tracking permissions (instructor - same as staff)
        'manage_students', 'manage_modules', 'manage_assessments',
        'create_assessment', 'edit_assessment',
        'enter_grades', 'edit_grades', 'view_all_grades',
        'generate_transcripts', 'grade_statistics', 'grade_reports',
        # Finance GUI permissions (instructor - similar to staff, limited access)
        'view_core_finance', 'manage_payments', 'view_financial_reports',
        # Health Portal permissions (instructor - basic access)
        'view_health_resources',
        # Internship Portal permissions (instructor - create opportunities)
        'view_all_applications', 'create_internship', 'edit_internship',
        'view_internship_reports',
        # Career Services permissions (instructor - career guidance)
        'manage_job_postings', 'manage_career_events'
    ],
    'parent': [
        'view_child_records', 'view_academic_calendar', 'view_child_grades',
        'view_child_attendance', 'view_teacher_reports', 'message_teachers',
        'view_child_timetable', 'view_child_assignments', 'set_notification_preferences',
        'update_contact_info', 'view_school_calendar', 'report_absence', 'access_parent_dashboard',
        # Parent Portal permissions (parent - full parent features)
        'view_children', 'view_academic_records', 'view_attendance_behavior',
        'view_health_safety', 'parent_communication', 'view_financial_info',
        'access_academic_support', 'manage_parent_settings', 'view_notifications',
        'update_emergency_contacts', 'manage_transportation', 'set_pickup_permissions',
        'manage_medical_info', 'report_student_absence', 'request_parent_teacher_meeting',
        'view_documents', 'upload_documents', 'manage_meal_plans'
    ]
}

# Session and Security Constants
DEFAULT_SESSION_TIMEOUT: int = 30  # minutes
DEFAULT_MAX_LOGIN_ATTEMPTS: int = 5
DEFAULT_LOCKOUT_TIME: int = 15  # minutes

# Password Security Constants
PBKDF2_ITERATIONS: int = 1_000_000  # OWASP recommended iterations for PBKDF2-SHA256
PASSWORD_MIN_LENGTH: int = 8
PASSWORD_SALT_LENGTH: int = 16  # hex characters (32 bytes)
PASSWORD_HASH_LENGTH: int = 64  # key length in bytes
