"""API route blueprints."""

# --- Original routes ---
from education_system.shared.api.college.routes.auth_routes import auth_bp, init_auth_routes
from education_system.shared.api.college.routes.student_routes import student_bp, init_student_routes
from education_system.shared.api.college.routes.course_routes import course_bp, init_course_routes
from education_system.shared.api.college.routes.enrollment_routes import enrollment_bp, init_enrollment_routes
from education_system.shared.api.college.routes.grade_routes import grade_bp, init_grade_routes
from education_system.shared.api.college.routes.attendance_routes import attendance_bp, init_attendance_routes
from education_system.shared.api.college.routes.system_routes import system_bp, init_system_routes
from education_system.shared.api.college.routes.timetable_routes import timetable_bp, init_timetable_routes
from education_system.shared.api.college.routes.assignment_routes import assignment_bp, init_assignment_routes
from education_system.shared.api.college.routes.notification_routes import notification_bp, init_notification_routes
from education_system.shared.api.college.routes.mfa_routes import mfa_bp, init_mfa_routes
from education_system.shared.api.college.routes.funding_routes import funding_bp, init_funding_routes
from education_system.shared.api.college.routes.destination_routes import destination_bp, init_destination_routes
from education_system.shared.api.college.routes.student_support_routes import student_support_bp, init_student_support_routes
from education_system.shared.api.college.routes.finance_routes import finance_bp, init_finance_routes
from education_system.shared.api.college.routes.department_routes import department_bp, init_department_routes
from education_system.shared.api.college.routes.group_routes import group_bp, init_group_routes
from education_system.shared.api.college.routes.room_routes import room_bp, init_room_routes
from education_system.shared.api.college.routes.cpd_routes import cpd_bp, init_cpd_routes
from education_system.shared.api.college.routes.observations_routes import observations_bp, init_observations_routes
from education_system.shared.api.college.routes.appraisals_routes import appraisals_bp, init_appraisals_routes
from education_system.shared.api.college.routes.resource_booking_routes import resource_booking_bp, init_resource_booking_routes
from education_system.shared.api.college.routes.markbook_routes import markbook_bp, init_markbook_routes
from education_system.shared.api.college.routes.staff_wellbeing_routes import staff_wellbeing_bp, init_staff_wellbeing_routes
from education_system.shared.api.college.routes.lesson_plans_routes import lesson_plan_bp, init_lesson_plan_routes
from education_system.shared.api.college.routes.data_dashboard_routes import data_dashboard_bp, init_data_dashboard_routes
from education_system.shared.api.college.routes.absence_requests_routes import absence_request_bp, init_absence_request_routes
from education_system.shared.api.college.routes.intervention_tracking_routes import intervention_bp, init_intervention_routes
from education_system.shared.api.college.routes.visitors_routes import visitor_bp, init_visitor_routes
from education_system.shared.api.college.routes.policies_routes import policy_bp, init_policy_routes
from education_system.shared.api.college.routes.gdpr_routes import gdpr_bp, init_gdpr_routes
from education_system.shared.api.college.routes.quality_assurance_routes import quality_assurance_bp, init_quality_assurance_routes
from education_system.shared.api.college.routes.bulk_operations_routes import bulk_operation_bp, init_bulk_operation_routes
from education_system.shared.api.college.routes.emergency_routes import emergency_bp, init_emergency_routes
from education_system.shared.api.college.routes.academic_year_routes import academic_year_bp, init_academic_year_routes
from education_system.shared.api.college.routes.kpi_dashboard_routes import kpi_bp, init_kpi_routes
from education_system.shared.api.college.routes.audit_reports_routes import audit_report_bp, init_audit_report_routes
from education_system.shared.api.college.routes.user_management_routes import user_management_bp, init_user_management_routes
from education_system.shared.api.college.routes.portfolio_routes import portfolio_bp, init_portfolio_routes
from education_system.shared.api.college.routes.study_planner_routes import study_planner_bp, init_study_planner_routes
from education_system.shared.api.college.routes.enrichment_routes import enrichment_bp, init_enrichment_routes
from education_system.shared.api.college.routes.peer_mentoring_routes import peer_mentoring_bp, init_peer_mentoring_routes
from education_system.shared.api.college.routes.surveys_routes import survey_bp, init_survey_routes
from education_system.shared.api.college.routes.skills_passport_routes import skills_passport_bp, init_skills_passport_routes
from education_system.shared.api.college.routes.progress_dashboard_routes import progress_dashboard_bp, init_progress_dashboard_routes
from education_system.shared.api.college.routes.meal_ordering_routes import meal_ordering_bp, init_meal_ordering_routes
from education_system.shared.api.college.routes.print_credits_routes import print_credit_bp, init_print_credit_routes
from education_system.shared.api.college.routes.work_journal_routes import work_journal_bp, init_work_journal_routes
from education_system.shared.api.college.routes.announcements_routes import announcement_bp, init_announcement_routes
from education_system.shared.api.college.routes.document_hub_routes import document_hub_bp, init_document_hub_routes
from education_system.shared.api.college.routes.advanced_search_routes import advanced_search_bp, init_advanced_search_routes
from education_system.shared.api.college.routes.feedback_routes import feedback_bp, init_feedback_routes
from education_system.shared.api.college.routes.accessibility_routes import accessibility_bp, init_accessibility_routes
from education_system.shared.api.college.routes.mobile_dashboard_routes import mobile_dashboard_bp, init_mobile_dashboard_routes
from education_system.shared.api.college.routes.attachments_routes import attachment_bp, init_attachment_routes
from education_system.shared.api.college.routes.activity_feed_routes import activity_feed_bp, init_activity_feed_routes
from education_system.shared.api.college.routes.sms_email_routes import sms_email_bp, init_sms_email_routes
from education_system.shared.api.college.routes.multi_language_routes import multi_language_bp, init_multi_language_routes

# --- New domain module routes ---
from education_system.shared.api.college.routes.admissions_routes import admissions_bp, init_admissions_routes
from education_system.shared.api.college.routes.alumni_routes import alumni_bp, init_alumni_routes
from education_system.shared.api.college.routes.apprenticeships_routes import apprenticeships_bp, init_apprenticeships_routes
from education_system.shared.api.college.routes.assets_routes import assets_bp, init_assets_routes
from education_system.shared.api.college.routes.baseline_assessment_routes import baseline_assessment_bp, init_baseline_assessment_routes
from education_system.shared.api.college.routes.behaviour_routes import behaviour_bp, init_behaviour_routes
from education_system.shared.api.college.routes.bursary_routes import bursary_bp, init_bursary_routes
from education_system.shared.api.college.routes.calendar_routes import calendar_bp, init_calendar_routes
from education_system.shared.api.college.routes.careers_routes import careers_bp, init_careers_routes
from education_system.shared.api.college.routes.complaints_routes import complaints_bp, init_complaints_routes
from education_system.shared.api.college.routes.compliance_routes import compliance_bp, init_compliance_routes
from education_system.shared.api.college.routes.cover_routes import cover_bp, init_cover_routes
from education_system.shared.api.college.routes.data_export_routes import data_export_bp, init_data_export_routes
from education_system.shared.api.college.routes.dbs_checks_routes import dbs_checks_bp, init_dbs_checks_routes
from education_system.shared.api.college.routes.disciplinary_routes import disciplinary_bp, init_disciplinary_routes
from education_system.shared.api.college.routes.early_warning_routes import early_warning_bp, init_early_warning_routes
from education_system.shared.api.college.routes.equality_diversity_routes import equality_diversity_bp, init_equality_diversity_routes
from education_system.shared.api.college.routes.exams_routes import exams_bp, init_exams_routes
from education_system.shared.api.college.routes.expense_claims_routes import expense_claims_bp, init_expense_claims_routes
from education_system.shared.api.college.routes.first_aid_routes import first_aid_bp, init_first_aid_routes
from education_system.shared.api.college.routes.forums_routes import forums_bp, init_forums_routes
from education_system.shared.api.college.routes.functional_skills_routes import functional_skills_bp, init_functional_skills_routes
from education_system.shared.api.college.routes.governance_routes import governance_bp, init_governance_routes
from education_system.shared.api.college.routes.health_safety_routes import health_safety_bp, init_health_safety_routes
from education_system.shared.api.college.routes.helpdesk_routes import helpdesk_bp, init_helpdesk_routes
from education_system.shared.api.college.routes.ilp_routes import ilp_bp, init_ilp_routes
from education_system.shared.api.college.routes.internal_verification_routes import internal_verification_bp, init_internal_verification_routes
from education_system.shared.api.college.routes.letter_templates_routes import letter_templates_bp, init_letter_templates_routes
from education_system.shared.api.college.routes.lettings_routes import lettings_bp, init_lettings_routes
from education_system.shared.api.college.routes.library_routes import library_bp, init_library_routes
from education_system.shared.api.college.routes.marketing_routes import marketing_bp, init_marketing_routes
from education_system.shared.api.college.routes.messaging_routes import messaging_bp, init_messaging_routes
from education_system.shared.api.college.routes.onboarding_routes import onboarding_bp, init_onboarding_routes
from education_system.shared.api.college.routes.parent_portal_routes import parent_portal_bp, init_parent_portal_routes
from education_system.shared.api.college.routes.parents_evening_routes import parents_evening_bp, init_parents_evening_routes
from education_system.shared.api.college.routes.pastoral_routes import pastoral_bp, init_pastoral_routes
from education_system.shared.api.college.routes.prevent_duty_routes import prevent_duty_bp, init_prevent_duty_routes
from education_system.shared.api.college.routes.recruitment_routes import recruitment_bp, init_recruitment_routes
from education_system.shared.api.college.routes.reports_routes import reports_bp, init_reports_routes
from education_system.shared.api.college.routes.risk_management_routes import risk_management_bp, init_risk_management_routes
from education_system.shared.api.college.routes.safeguarding_routes import safeguarding_bp, init_safeguarding_routes
from education_system.shared.api.college.routes.self_assessment_routes import self_assessment_bp, init_self_assessment_routes
from education_system.shared.api.college.routes.send_routes import send_bp, init_send_routes
from education_system.shared.api.college.routes.settings_routes import settings_bp, init_settings_routes
from education_system.shared.api.college.routes.staff_routes import staff_bp, init_staff_routes
from education_system.shared.api.college.routes.staff_absence_routes import staff_absence_bp, init_staff_absence_routes
from education_system.shared.api.college.routes.staff_hr_routes import staff_hr_bp, init_staff_hr_routes
from education_system.shared.api.college.routes.student_council_routes import student_council_bp, init_student_council_routes
from education_system.shared.api.college.routes.student_portal_routes import student_portal_bp, init_student_portal_routes
from education_system.shared.api.college.routes.student_wellbeing_routes import student_wellbeing_bp, init_student_wellbeing_routes
from education_system.shared.api.college.routes.study_programmes_routes import study_programmes_bp, init_study_programmes_routes
from education_system.shared.api.college.routes.tlevel_routes import tlevel_bp, init_tlevel_routes
from education_system.shared.api.college.routes.todo_routes import todo_bp, init_todo_routes
from education_system.shared.api.college.routes.transport_routes import transport_bp, init_transport_routes
from education_system.shared.api.college.routes.tutorial_routes import tutorial_bp, init_tutorial_routes
from education_system.shared.api.college.routes.ucas_routes import ucas_bp, init_ucas_routes
from education_system.shared.api.college.routes.value_added_routes import value_added_bp, init_value_added_routes

ALL_BLUEPRINTS = [
    # Original
    student_bp, course_bp, enrollment_bp, grade_bp, attendance_bp, system_bp,
    timetable_bp, assignment_bp, notification_bp, mfa_bp,
    funding_bp, destination_bp, student_support_bp, finance_bp,
    department_bp, group_bp, room_bp,
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
    # New domain module routes
    admissions_bp, alumni_bp, apprenticeships_bp, assets_bp,
    baseline_assessment_bp, behaviour_bp, bursary_bp, calendar_bp,
    careers_bp, complaints_bp, compliance_bp, cover_bp,
    data_export_bp, dbs_checks_bp, disciplinary_bp, early_warning_bp,
    equality_diversity_bp, exams_bp, expense_claims_bp, first_aid_bp,
    forums_bp, functional_skills_bp, governance_bp, health_safety_bp,
    helpdesk_bp, ilp_bp, internal_verification_bp, letter_templates_bp,
    lettings_bp, library_bp, marketing_bp, messaging_bp,
    onboarding_bp, parent_portal_bp, parents_evening_bp, pastoral_bp,
    prevent_duty_bp, recruitment_bp, reports_bp, risk_management_bp,
    safeguarding_bp, self_assessment_bp, send_bp, settings_bp,
    staff_bp, staff_absence_bp, staff_hr_bp, student_council_bp,
    student_portal_bp, student_wellbeing_bp, study_programmes_bp, tlevel_bp,
    todo_bp, transport_bp, tutorial_bp, ucas_bp, value_added_bp,
]

ALL_INIT_FUNCS = [
    # Original
    init_student_routes, init_course_routes,
    init_enrollment_routes, init_grade_routes, init_attendance_routes,
    init_system_routes, init_timetable_routes, init_assignment_routes,
    init_notification_routes, init_mfa_routes,
    init_funding_routes, init_destination_routes, init_student_support_routes,
    init_finance_routes, init_department_routes, init_group_routes,
    init_room_routes,
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
    # New domain module routes
    init_admissions_routes, init_alumni_routes, init_apprenticeships_routes,
    init_assets_routes, init_baseline_assessment_routes, init_behaviour_routes,
    init_bursary_routes, init_calendar_routes, init_careers_routes,
    init_complaints_routes, init_compliance_routes, init_cover_routes,
    init_data_export_routes, init_dbs_checks_routes, init_disciplinary_routes,
    init_early_warning_routes, init_equality_diversity_routes, init_exams_routes,
    init_expense_claims_routes, init_first_aid_routes, init_forums_routes,
    init_functional_skills_routes, init_governance_routes, init_health_safety_routes,
    init_helpdesk_routes, init_ilp_routes, init_internal_verification_routes,
    init_letter_templates_routes, init_lettings_routes, init_library_routes,
    init_marketing_routes, init_messaging_routes, init_onboarding_routes,
    init_parent_portal_routes, init_parents_evening_routes, init_pastoral_routes,
    init_prevent_duty_routes, init_recruitment_routes, init_reports_routes,
    init_risk_management_routes, init_safeguarding_routes, init_self_assessment_routes,
    init_send_routes, init_settings_routes, init_staff_routes,
    init_staff_absence_routes, init_staff_hr_routes, init_student_council_routes,
    init_student_portal_routes, init_student_wellbeing_routes, init_study_programmes_routes,
    init_tlevel_routes, init_todo_routes, init_transport_routes,
    init_tutorial_routes, init_ucas_routes, init_value_added_routes,
]
