"""API route blueprints."""

from education_system.college_system.api.routes.auth_routes import auth_bp, init_auth_routes
from education_system.college_system.api.routes.student_routes import student_bp, init_student_routes
from education_system.college_system.api.routes.course_routes import course_bp, init_course_routes
from education_system.college_system.api.routes.enrollment_routes import enrollment_bp, init_enrollment_routes
from education_system.college_system.api.routes.grade_routes import grade_bp, init_grade_routes
from education_system.college_system.api.routes.attendance_routes import attendance_bp, init_attendance_routes
from education_system.college_system.api.routes.system_routes import system_bp, init_system_routes
from education_system.college_system.api.routes.timetable_routes import timetable_bp, init_timetable_routes
from education_system.college_system.api.routes.assignment_routes import assignment_bp, init_assignment_routes
from education_system.college_system.api.routes.notification_routes import notification_bp, init_notification_routes
from education_system.college_system.api.routes.mfa_routes import mfa_bp, init_mfa_routes
from education_system.college_system.api.routes.funding_routes import funding_bp, init_funding_routes
from education_system.college_system.api.routes.destination_routes import destination_bp, init_destination_routes
from education_system.college_system.api.routes.student_support_routes import student_support_bp, init_student_support_routes
from education_system.college_system.api.routes.finance_routes import finance_bp, init_finance_routes
from education_system.college_system.api.routes.department_routes import department_bp, init_department_routes
from education_system.college_system.api.routes.group_routes import group_bp, init_group_routes
from education_system.college_system.api.routes.room_routes import room_bp, init_room_routes
# New feature modules
from education_system.college_system.api.routes.cpd_routes import cpd_bp, init_cpd_routes
from education_system.college_system.api.routes.observations_routes import observations_bp, init_observations_routes
from education_system.college_system.api.routes.appraisals_routes import appraisals_bp, init_appraisals_routes
from education_system.college_system.api.routes.resource_booking_routes import resource_booking_bp, init_resource_booking_routes
from education_system.college_system.api.routes.markbook_routes import markbook_bp, init_markbook_routes
from education_system.college_system.api.routes.staff_wellbeing_routes import staff_wellbeing_bp, init_staff_wellbeing_routes
from education_system.college_system.api.routes.lesson_plans_routes import lesson_plan_bp, init_lesson_plan_routes
from education_system.college_system.api.routes.data_dashboard_routes import data_dashboard_bp, init_data_dashboard_routes
from education_system.college_system.api.routes.absence_requests_routes import absence_request_bp, init_absence_request_routes
from education_system.college_system.api.routes.intervention_tracking_routes import intervention_bp, init_intervention_routes
from education_system.college_system.api.routes.visitors_routes import visitor_bp, init_visitor_routes
from education_system.college_system.api.routes.policies_routes import policy_bp, init_policy_routes
from education_system.college_system.api.routes.gdpr_routes import gdpr_bp, init_gdpr_routes
from education_system.college_system.api.routes.quality_assurance_routes import quality_assurance_bp, init_quality_assurance_routes
from education_system.college_system.api.routes.bulk_operations_routes import bulk_operation_bp, init_bulk_operation_routes
from education_system.college_system.api.routes.emergency_routes import emergency_bp, init_emergency_routes
from education_system.college_system.api.routes.academic_year_routes import academic_year_bp, init_academic_year_routes
from education_system.college_system.api.routes.kpi_dashboard_routes import kpi_bp, init_kpi_routes
from education_system.college_system.api.routes.audit_reports_routes import audit_report_bp, init_audit_report_routes
from education_system.college_system.api.routes.user_management_routes import user_management_bp, init_user_management_routes
from education_system.college_system.api.routes.portfolio_routes import portfolio_bp, init_portfolio_routes
from education_system.college_system.api.routes.study_planner_routes import study_planner_bp, init_study_planner_routes
from education_system.college_system.api.routes.enrichment_routes import enrichment_bp, init_enrichment_routes
from education_system.college_system.api.routes.peer_mentoring_routes import peer_mentoring_bp, init_peer_mentoring_routes
from education_system.college_system.api.routes.surveys_routes import survey_bp, init_survey_routes
from education_system.college_system.api.routes.skills_passport_routes import skills_passport_bp, init_skills_passport_routes
from education_system.college_system.api.routes.progress_dashboard_routes import progress_dashboard_bp, init_progress_dashboard_routes
from education_system.college_system.api.routes.meal_ordering_routes import meal_ordering_bp, init_meal_ordering_routes
from education_system.college_system.api.routes.print_credits_routes import print_credit_bp, init_print_credit_routes
from education_system.college_system.api.routes.work_journal_routes import work_journal_bp, init_work_journal_routes
from education_system.college_system.api.routes.announcements_routes import announcement_bp, init_announcement_routes
from education_system.college_system.api.routes.document_hub_routes import document_hub_bp, init_document_hub_routes
from education_system.college_system.api.routes.advanced_search_routes import advanced_search_bp, init_advanced_search_routes
from education_system.college_system.api.routes.feedback_routes import feedback_bp, init_feedback_routes
from education_system.college_system.api.routes.accessibility_routes import accessibility_bp, init_accessibility_routes
from education_system.college_system.api.routes.mobile_dashboard_routes import mobile_dashboard_bp, init_mobile_dashboard_routes
from education_system.college_system.api.routes.attachments_routes import attachment_bp, init_attachment_routes
from education_system.college_system.api.routes.activity_feed_routes import activity_feed_bp, init_activity_feed_routes
from education_system.college_system.api.routes.sms_email_routes import sms_email_bp, init_sms_email_routes
from education_system.college_system.api.routes.multi_language_routes import multi_language_bp, init_multi_language_routes

ALL_BLUEPRINTS = [
    auth_bp, student_bp, course_bp, enrollment_bp, grade_bp, attendance_bp, system_bp,
    timetable_bp, assignment_bp, notification_bp, mfa_bp,
    funding_bp, destination_bp, student_support_bp, finance_bp,
    department_bp, group_bp, room_bp,
    # New feature modules
    cpd_bp, observations_bp, appraisals_bp, resource_booking_bp, markbook_bp,
    staff_wellbeing_bp, lesson_plan_bp, data_dashboard_bp, absence_request_bp,
    intervention_bp, visitor_bp, policy_bp, gdpr_bp, quality_assurance_bp,
    bulk_operation_bp, emergency_bp, academic_year_bp, kpi_bp, audit_report_bp,
    user_management_bp, portfolio_bp, study_planner_bp, enrichment_bp,
    peer_mentoring_bp, survey_bp, skills_passport_bp, progress_dashboard_bp,
    meal_ordering_bp, print_credit_bp, work_journal_bp, announcement_bp,
    document_hub_bp, advanced_search_bp, feedback_bp, accessibility_bp,
    mobile_dashboard_bp, attachment_bp, activity_feed_bp, sms_email_bp,
    multi_language_bp,
]

ALL_INIT_FUNCS = [
    init_auth_routes, init_student_routes, init_course_routes,
    init_enrollment_routes, init_grade_routes, init_attendance_routes,
    init_system_routes, init_timetable_routes, init_assignment_routes,
    init_notification_routes, init_mfa_routes,
    init_funding_routes, init_destination_routes, init_student_support_routes,
    init_finance_routes, init_department_routes, init_group_routes,
    init_room_routes,
    # New feature modules
    init_cpd_routes, init_observations_routes, init_appraisals_routes,
    init_resource_booking_routes, init_markbook_routes, init_staff_wellbeing_routes,
    init_lesson_plan_routes, init_data_dashboard_routes, init_absence_request_routes,
    init_intervention_routes, init_visitor_routes, init_policy_routes,
    init_gdpr_routes, init_quality_assurance_routes, init_bulk_operation_routes,
    init_emergency_routes, init_academic_year_routes, init_kpi_routes,
    init_audit_report_routes, init_user_management_routes, init_portfolio_routes,
    init_study_planner_routes, init_enrichment_routes, init_peer_mentoring_routes,
    init_survey_routes, init_skills_passport_routes, init_progress_dashboard_routes,
    init_meal_ordering_routes, init_print_credit_routes, init_work_journal_routes,
    init_announcement_routes, init_document_hub_routes, init_advanced_search_routes,
    init_feedback_routes, init_accessibility_routes, init_mobile_dashboard_routes,
    init_attachment_routes, init_activity_feed_routes, init_sms_email_routes,
    init_multi_language_routes,
]
