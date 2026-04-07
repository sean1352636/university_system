"""API route blueprints for the Secondary School system."""

# ── Original routes ──────────────────────────────────────────────────────────
from education_system.shared.api.secondary.routes.auth_routes import auth_bp, init_auth_routes
from education_system.shared.api.secondary.routes.student_routes import student_bp, init_student_routes
from education_system.shared.api.secondary.routes.subject_routes import subject_bp, init_subject_routes
from education_system.shared.api.secondary.routes.enrollment_routes import enrollment_bp, init_enrollment_routes
from education_system.shared.api.secondary.routes.grade_routes import grade_bp, init_grade_routes
from education_system.shared.api.secondary.routes.attendance_routes import attendance_bp, init_attendance_routes
from education_system.shared.api.secondary.routes.behaviour_routes import behaviour_bp, init_behaviour_routes
from education_system.shared.api.secondary.routes.system_routes import system_bp, init_system_routes

# ── Academics ────────────────────────────────────────────────────────────────
from education_system.shared.api.secondary.routes.exams_routes import exams_bp, init_exams_routes
from education_system.shared.api.secondary.routes.homework_routes import homework_bp, init_homework_routes
from education_system.shared.api.secondary.routes.interventions_routes import interventions_bp, init_interventions_routes
from education_system.shared.api.secondary.routes.progress_routes import progress_bp, init_progress_routes
from education_system.shared.api.secondary.routes.reports_routes import reports_bp, init_reports_routes
from education_system.shared.api.secondary.routes.timetable_routes import timetable_bp, init_timetable_routes

# ── Admin ────────────────────────────────────────────────────────────────────
from education_system.shared.api.secondary.routes.admissions_routes import admissions_bp, init_admissions_routes
from education_system.shared.api.secondary.routes.audit_log_routes import audit_log_bp, init_audit_log_routes
from education_system.shared.api.secondary.routes.data_export_routes import data_export_bp, init_data_export_routes
from education_system.shared.api.secondary.routes.documents_routes import documents_bp, init_documents_routes
from education_system.shared.api.secondary.routes.finance_routes import finance_bp, init_finance_routes
from education_system.shared.api.secondary.routes.policies_routes import policies_bp, init_policies_routes
from education_system.shared.api.secondary.routes.settings_routes import settings_bp, init_settings_routes
from education_system.shared.api.secondary.routes.users_routes import users_bp, init_users_routes

# ── Communication ────────────────────────────────────────────────────────────
from education_system.shared.api.secondary.routes.announcements_routes import announcements_bp, init_announcements_routes
from education_system.shared.api.secondary.routes.calendar_routes import calendar_bp, init_calendar_routes
from education_system.shared.api.secondary.routes.communication_log_routes import comms_bp, init_communication_log_routes
from education_system.shared.api.secondary.routes.email_routes import email_bp, init_email_routes
from education_system.shared.api.secondary.routes.notifications_routes import notifications_bp, init_notifications_routes
from education_system.shared.api.secondary.routes.parents_evening_routes import parents_evening_bp, init_parents_evening_routes

# ── Facilities ───────────────────────────────────────────────────────────────
from education_system.shared.api.secondary.routes.assets_routes import assets_bp, init_assets_routes
from education_system.shared.api.secondary.routes.incidents_routes import incidents_bp, init_incidents_routes
from education_system.shared.api.secondary.routes.room_booking_routes import room_booking_bp, init_room_booking_routes
from education_system.shared.api.secondary.routes.seating_plans_routes import seating_plans_bp, init_seating_plans_routes
from education_system.shared.api.secondary.routes.visitors_routes import visitors_bp, init_visitors_routes

# ── Pastoral Care ────────────────────────────────────────────────────────────
from education_system.shared.api.secondary.routes.detentions_routes import detentions_bp, init_detentions_routes
from education_system.shared.api.secondary.routes.exclusions_routes import exclusions_bp, init_exclusions_routes
from education_system.shared.api.secondary.routes.pastoral_routes import pastoral_bp, init_pastoral_routes
from education_system.shared.api.secondary.routes.rewards_routes import rewards_bp, init_rewards_routes
from education_system.shared.api.secondary.routes.safeguarding_routes import safeguarding_bp, init_safeguarding_routes
from education_system.shared.api.secondary.routes.send_routes import send_bp, init_send_routes

# ── Staff ────────────────────────────────────────────────────────────────────
from education_system.shared.api.secondary.routes.cover_routes import cover_bp, init_cover_routes
from education_system.shared.api.secondary.routes.cpd_routes import cpd_bp, init_cpd_routes
from education_system.shared.api.secondary.routes.hr_routes import hr_bp, init_hr_routes
from education_system.shared.api.secondary.routes.staff_directory_routes import staff_directory_bp, init_staff_directory_routes

# ── Student Life ─────────────────────────────────────────────────────────────
from education_system.shared.api.secondary.routes.careers_routes import careers_bp, init_careers_routes
from education_system.shared.api.secondary.routes.clubs_routes import clubs_bp, init_clubs_routes
from education_system.shared.api.secondary.routes.consent_routes import consent_bp, init_consent_routes
from education_system.shared.api.secondary.routes.form_groups_routes import form_groups_bp, init_form_groups_routes
from education_system.shared.api.secondary.routes.library_routes import library_bp, init_library_routes
from education_system.shared.api.secondary.routes.meals_routes import meals_bp, init_meals_routes
from education_system.shared.api.secondary.routes.medical_routes import medical_bp, init_medical_routes
from education_system.shared.api.secondary.routes.transport_routes import transport_bp, init_transport_routes
from education_system.shared.api.secondary.routes.trips_routes import trips_bp, init_trips_routes

# ── New domain modules ──────────────────────────────────────────────────────
# Academics
from education_system.shared.api.secondary.routes.academic_year_routes import academic_year_bp, init_academic_year_routes
from education_system.shared.api.secondary.routes.assignments_routes import assignments_bp, init_assignments_routes
from education_system.shared.api.secondary.routes.baseline_assessment_routes import baseline_assessment_bp, init_baseline_assessment_routes
from education_system.shared.api.secondary.routes.markbook_routes import markbook_bp, init_markbook_routes
from education_system.shared.api.secondary.routes.target_setting_routes import target_setting_bp, init_target_setting_routes
from education_system.shared.api.secondary.routes.question_analysis_routes import question_analysis_bp, init_question_analysis_routes
# Admin
from education_system.shared.api.secondary.routes.health_safety_routes import health_safety_bp, init_health_safety_routes
from education_system.shared.api.secondary.routes.risk_management_routes import risk_management_bp, init_risk_management_routes
from education_system.shared.api.secondary.routes.compliance_routes import compliance_bp, init_compliance_routes
from education_system.shared.api.secondary.routes.prevent_duty_routes import prevent_duty_bp, init_prevent_duty_routes
from education_system.shared.api.secondary.routes.audit_reports_routes import audit_reports_bp, init_audit_reports_routes
from education_system.shared.api.secondary.routes.bulk_operations_routes import bulk_operations_bp, init_bulk_operations_routes
from education_system.shared.api.secondary.routes.census_routes import census_bp, init_census_routes
from education_system.shared.api.secondary.routes.quality_assurance_routes import quality_assurance_bp, init_quality_assurance_routes
from education_system.shared.api.secondary.routes.self_assessment_routes import self_assessment_bp, init_self_assessment_routes
from education_system.shared.api.secondary.routes.helpdesk_routes import helpdesk_bp, init_helpdesk_routes
from education_system.shared.api.secondary.routes.letter_templates_routes import letter_templates_bp, init_letter_templates_routes
from education_system.shared.api.secondary.routes.onboarding_routes import onboarding_bp, init_onboarding_routes
from education_system.shared.api.secondary.routes.todo_routes import todo_bp, init_todo_routes
from education_system.shared.api.secondary.routes.multi_language_routes import multi_language_bp, init_multi_language_routes
# Staff
from education_system.shared.api.secondary.routes.dbs_checks_routes import dbs_checks_bp, init_dbs_checks_routes
from education_system.shared.api.secondary.routes.first_aid_routes import first_aid_bp, init_first_aid_routes
from education_system.shared.api.secondary.routes.recruitment_routes import recruitment_bp, init_recruitment_routes
from education_system.shared.api.secondary.routes.staff_absence_routes import staff_absence_bp, init_staff_absence_routes
# Pastoral Care
from education_system.shared.api.secondary.routes.absence_requests_routes import absence_requests_bp, init_absence_requests_routes
from education_system.shared.api.secondary.routes.early_warning_routes import early_warning_bp, init_early_warning_routes
from education_system.shared.api.secondary.routes.accessibility_routes import accessibility_bp, init_accessibility_routes
# Student Life
from education_system.shared.api.secondary.routes.equality_diversity_routes import equality_diversity_bp, init_equality_diversity_routes
from education_system.shared.api.secondary.routes.ilp_routes import ilp_bp, init_ilp_routes
from education_system.shared.api.secondary.routes.peer_mentoring_routes import peer_mentoring_bp, init_peer_mentoring_routes
from education_system.shared.api.secondary.routes.student_support_routes import student_support_bp, init_student_support_routes
# Communication
from education_system.shared.api.secondary.routes.messaging_routes import messaging_bp, init_messaging_routes
from education_system.shared.api.secondary.routes.sms_email_routes import sms_email_bp, init_sms_email_routes
from education_system.shared.api.secondary.routes.surveys_routes import surveys_bp, init_surveys_routes
from education_system.shared.api.secondary.routes.activity_feed_routes import activity_feed_bp, init_activity_feed_routes
# Facilities
from education_system.shared.api.secondary.routes.resource_booking_routes import resource_booking_bp, init_resource_booking_routes
from education_system.shared.api.secondary.routes.departments_routes import departments_bp, init_departments_routes
from education_system.shared.api.secondary.routes.emergency_routes import emergency_bp, init_emergency_routes
from education_system.shared.api.secondary.routes.lettings_routes import lettings_bp, init_lettings_routes
# Portals
from education_system.shared.api.secondary.routes.parent_portal_routes import parent_portal_bp, init_parent_portal_routes
from education_system.shared.api.secondary.routes.student_portal_routes import student_portal_bp, init_student_portal_routes
from education_system.shared.api.secondary.routes.document_hub_routes import document_hub_bp, init_document_hub_routes
from education_system.shared.api.secondary.routes.kpi_dashboard_routes import kpi_dashboard_bp, init_kpi_dashboard_routes
from education_system.shared.api.secondary.routes.mobile_dashboard_routes import mobile_dashboard_bp, init_mobile_dashboard_routes
from education_system.shared.api.secondary.routes.progress_dashboard_routes import progress_dashboard_bp, init_progress_dashboard_routes

ALL_BLUEPRINTS = [
    # Original
    student_bp, subject_bp, enrollment_bp, grade_bp,
    attendance_bp, behaviour_bp, system_bp,
    # Academics
    exams_bp, homework_bp, interventions_bp, progress_bp, reports_bp, timetable_bp,
    # Admin
    admissions_bp, audit_log_bp, data_export_bp, documents_bp, finance_bp,
    policies_bp, settings_bp, users_bp,
    # Communication
    announcements_bp, calendar_bp, comms_bp, email_bp, notifications_bp,
    parents_evening_bp,
    # Facilities
    assets_bp, incidents_bp, room_booking_bp, seating_plans_bp, visitors_bp,
    # Pastoral Care
    detentions_bp, exclusions_bp, pastoral_bp, rewards_bp, safeguarding_bp, send_bp,
    # Staff
    cover_bp, cpd_bp, hr_bp, staff_directory_bp,
    # Student Life
    careers_bp, clubs_bp, consent_bp, form_groups_bp, library_bp, meals_bp,
    medical_bp, transport_bp, trips_bp,
    # ── New domain modules ──────────────────────────────────────────────
    # Academics
    academic_year_bp, assignments_bp, baseline_assessment_bp, markbook_bp,
    target_setting_bp, question_analysis_bp,
    # Admin
    health_safety_bp, risk_management_bp, compliance_bp, prevent_duty_bp,
    audit_reports_bp, bulk_operations_bp, census_bp, quality_assurance_bp,
    self_assessment_bp, helpdesk_bp, letter_templates_bp, onboarding_bp,
    todo_bp, multi_language_bp,
    # Staff
    dbs_checks_bp, first_aid_bp, recruitment_bp, staff_absence_bp,
    # Pastoral Care
    absence_requests_bp, early_warning_bp, accessibility_bp,
    # Student Life
    equality_diversity_bp, ilp_bp, peer_mentoring_bp, student_support_bp,
    # Communication
    messaging_bp, sms_email_bp, surveys_bp, activity_feed_bp,
    # Facilities
    resource_booking_bp, departments_bp, emergency_bp, lettings_bp,
    # Portals
    parent_portal_bp, student_portal_bp, document_hub_bp, kpi_dashboard_bp,
    mobile_dashboard_bp, progress_dashboard_bp,
]

ALL_INIT_FUNCS = [
    # Original
    init_student_routes, init_subject_routes,
    init_enrollment_routes, init_grade_routes, init_attendance_routes,
    init_behaviour_routes, init_system_routes,
    # Academics
    init_exams_routes, init_homework_routes, init_interventions_routes,
    init_progress_routes, init_reports_routes, init_timetable_routes,
    # Admin
    init_admissions_routes, init_audit_log_routes, init_data_export_routes,
    init_documents_routes, init_finance_routes, init_policies_routes,
    init_settings_routes, init_users_routes,
    # Communication
    init_announcements_routes, init_calendar_routes, init_communication_log_routes,
    init_email_routes, init_notifications_routes, init_parents_evening_routes,
    # Facilities
    init_assets_routes, init_incidents_routes, init_room_booking_routes,
    init_seating_plans_routes, init_visitors_routes,
    # Pastoral Care
    init_detentions_routes, init_exclusions_routes, init_pastoral_routes,
    init_rewards_routes, init_safeguarding_routes, init_send_routes,
    # Staff
    init_cover_routes, init_cpd_routes, init_hr_routes, init_staff_directory_routes,
    # Student Life
    init_careers_routes, init_clubs_routes, init_consent_routes,
    init_form_groups_routes, init_library_routes, init_meals_routes,
    init_medical_routes, init_transport_routes, init_trips_routes,
    # ── New domain modules ──────────────────────────────────────────────
    # Academics
    init_academic_year_routes, init_assignments_routes, init_baseline_assessment_routes,
    init_markbook_routes, init_target_setting_routes, init_question_analysis_routes,
    # Admin
    init_health_safety_routes, init_risk_management_routes, init_compliance_routes,
    init_prevent_duty_routes, init_audit_reports_routes, init_bulk_operations_routes,
    init_census_routes, init_quality_assurance_routes, init_self_assessment_routes,
    init_helpdesk_routes, init_letter_templates_routes, init_onboarding_routes,
    init_todo_routes, init_multi_language_routes,
    # Staff
    init_dbs_checks_routes, init_first_aid_routes, init_recruitment_routes,
    init_staff_absence_routes,
    # Pastoral Care
    init_absence_requests_routes, init_early_warning_routes, init_accessibility_routes,
    # Student Life
    init_equality_diversity_routes, init_ilp_routes, init_peer_mentoring_routes,
    init_student_support_routes,
    # Communication
    init_messaging_routes, init_sms_email_routes, init_surveys_routes,
    init_activity_feed_routes,
    # Facilities
    init_resource_booking_routes, init_departments_routes, init_emergency_routes,
    init_lettings_routes,
    # Portals
    init_parent_portal_routes, init_student_portal_routes, init_document_hub_routes,
    init_kpi_dashboard_routes, init_mobile_dashboard_routes, init_progress_dashboard_routes,
]
