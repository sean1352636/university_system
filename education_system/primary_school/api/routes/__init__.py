"""API route blueprints for the Primary School system."""

from education_system.primary_school.api.routes.auth_routes import auth_bp, init_auth_routes
from education_system.primary_school.api.routes.system_routes import system_bp, init_system_routes
from education_system.primary_school.api.routes.pupil_routes import pupils_bp, init_pupils_routes
from education_system.primary_school.api.routes.subject_routes import subjects_bp, init_subjects_routes
from education_system.primary_school.api.routes.class_routes import classes_bp, init_classes_routes
from education_system.primary_school.api.routes.assessment_routes import assessments_bp, init_assessments_routes
from education_system.primary_school.api.routes.attendance_routes import attendance_bp, init_attendance_routes
from education_system.primary_school.api.routes.timetable_routes import timetable_bp, init_timetable_routes
from education_system.primary_school.api.routes.homework_routes import homework_bp, init_homework_routes
from education_system.primary_school.api.routes.sats_routes import sats_bp, init_sats_routes
from education_system.primary_school.api.routes.phonics_routes import phonics_bp, init_phonics_routes
from education_system.primary_school.api.routes.reading_record_routes import reading_records_bp, init_reading_records_routes
from education_system.primary_school.api.routes.progress_routes import progress_bp, init_progress_routes
from education_system.primary_school.api.routes.behaviour_routes import behaviour_bp, init_behaviour_routes
from education_system.primary_school.api.routes.rewards_routes import rewards_bp, init_rewards_routes
from education_system.primary_school.api.routes.safeguarding_routes import safeguarding_bp, init_safeguarding_routes
from education_system.primary_school.api.routes.send_routes import send_bp, init_send_routes
from education_system.primary_school.api.routes.pastoral_routes import pastoral_bp, init_pastoral_routes
from education_system.primary_school.api.routes.hr_routes import hr_bp, init_hr_routes
from education_system.primary_school.api.routes.cpd_routes import cpd_bp, init_cpd_routes
from education_system.primary_school.api.routes.cover_routes import cover_bp, init_cover_routes
from education_system.primary_school.api.routes.staff_directory_routes import staff_directory_bp, init_staff_directory_routes
from education_system.primary_school.api.routes.user_routes import users_bp, init_users_routes
from education_system.primary_school.api.routes.settings_routes import settings_bp, init_settings_routes
from education_system.primary_school.api.routes.admissions_routes import admissions_bp, init_admissions_routes
from education_system.primary_school.api.routes.finance_routes import finance_bp, init_finance_routes
from education_system.primary_school.api.routes.data_export_routes import data_export_bp, init_data_export_routes
from education_system.primary_school.api.routes.audit_log_routes import audit_log_bp, init_audit_log_routes
from education_system.primary_school.api.routes.policy_routes import policies_bp, init_policies_routes
from education_system.primary_school.api.routes.document_routes import documents_bp, init_documents_routes
from education_system.primary_school.api.routes.club_routes import clubs_bp, init_clubs_routes
from education_system.primary_school.api.routes.meal_routes import meals_bp, init_meals_routes
from education_system.primary_school.api.routes.transport_routes import transport_bp, init_transport_routes
from education_system.primary_school.api.routes.trip_routes import trips_bp, init_trips_routes
from education_system.primary_school.api.routes.library_routes import library_bp, init_library_routes
from education_system.primary_school.api.routes.medical_routes import medical_bp, init_medical_routes
from education_system.primary_school.api.routes.class_group_routes import class_groups_bp, init_class_groups_routes
from education_system.primary_school.api.routes.consent_routes import consent_bp, init_consent_routes
from education_system.primary_school.api.routes.email_routes import emails_bp, init_emails_routes
from education_system.primary_school.api.routes.notification_routes import notifications_bp, init_notifications_routes
from education_system.primary_school.api.routes.announcement_routes import announcements_bp, init_announcements_routes
from education_system.primary_school.api.routes.calendar_routes import calendar_bp, init_calendar_routes
from education_system.primary_school.api.routes.parents_evening_routes import parents_evening_bp, init_parents_evening_routes
from education_system.primary_school.api.routes.communication_log_routes import communication_log_bp, init_communication_log_routes
from education_system.primary_school.api.routes.room_booking_routes import room_bookings_bp, init_room_bookings_routes
from education_system.primary_school.api.routes.asset_routes import assets_bp, init_assets_routes
from education_system.primary_school.api.routes.visitor_routes import visitors_bp, init_visitors_routes
from education_system.primary_school.api.routes.incident_routes import incidents_bp, init_incidents_routes

ALL_BLUEPRINTS = [
    auth_bp, system_bp,
    pupils_bp, subjects_bp, classes_bp, assessments_bp, attendance_bp,
    timetable_bp, homework_bp, sats_bp, phonics_bp, reading_records_bp, progress_bp,
    behaviour_bp, rewards_bp, safeguarding_bp, send_bp, pastoral_bp,
    hr_bp, cpd_bp, cover_bp, staff_directory_bp,
    users_bp, settings_bp, admissions_bp, finance_bp, data_export_bp,
    audit_log_bp, policies_bp, documents_bp,
    clubs_bp, meals_bp, transport_bp, trips_bp, library_bp,
    medical_bp, class_groups_bp, consent_bp,
    emails_bp, notifications_bp, announcements_bp, calendar_bp,
    parents_evening_bp, communication_log_bp,
    room_bookings_bp, assets_bp, visitors_bp, incidents_bp,
]

ALL_INIT_FUNCS = [
    init_auth_routes, init_system_routes,
    init_pupils_routes, init_subjects_routes, init_classes_routes,
    init_assessments_routes, init_attendance_routes, init_timetable_routes,
    init_homework_routes, init_sats_routes, init_phonics_routes,
    init_reading_records_routes, init_progress_routes,
    init_behaviour_routes, init_rewards_routes, init_safeguarding_routes,
    init_send_routes, init_pastoral_routes,
    init_hr_routes, init_cpd_routes, init_cover_routes, init_staff_directory_routes,
    init_users_routes, init_settings_routes, init_admissions_routes,
    init_finance_routes, init_data_export_routes, init_audit_log_routes,
    init_policies_routes, init_documents_routes,
    init_clubs_routes, init_meals_routes, init_transport_routes,
    init_trips_routes, init_library_routes, init_medical_routes,
    init_class_groups_routes, init_consent_routes,
    init_emails_routes, init_notifications_routes, init_announcements_routes,
    init_calendar_routes, init_parents_evening_routes, init_communication_log_routes,
    init_room_bookings_routes, init_assets_routes, init_visitors_routes,
    init_incidents_routes,
]
