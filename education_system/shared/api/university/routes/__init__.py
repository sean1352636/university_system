"""Register all API route blueprints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

# --- Existing routes ---
from education_system.shared.api.university.routes.absence_routes import absence_bp
from education_system.shared.api.university.routes.accommodation_routes import accommodation_bp
from education_system.shared.api.university.routes.account_routes import account_bp
from education_system.shared.api.university.routes.admission_routes import admission_bp
from education_system.shared.api.university.routes.advising_routes import advising_bp
from education_system.shared.api.university.routes.alumni_routes import alumni_bp
from education_system.shared.api.university.routes.announcement_routes import announcement_bp
from education_system.shared.api.university.routes.assessment_routes import assessment_bp
from education_system.shared.api.university.routes.assignment_routes import assignment_bp
from education_system.shared.api.university.routes.attendance_routes import attendance_bp
from education_system.shared.api.university.routes.auth_routes import auth_bp
from education_system.shared.api.university.routes.calendar_routes import calendar_bp
from education_system.shared.api.university.routes.campus_routes import campus_bp
from education_system.shared.api.university.routes.career_routes import career_bp
from education_system.shared.api.university.routes.chat_routes import chat_bp
from education_system.shared.api.university.routes.club_routes import club_bp
from education_system.shared.api.university.routes.communication_routes import communication_bp
from education_system.shared.api.university.routes.counseling_routes import counseling_bp
from education_system.shared.api.university.routes.course_routes import course_bp
from education_system.shared.api.university.routes.credential_routes import credential_bp
from education_system.shared.api.university.routes.dashboard_routes import dashboard_bp
from education_system.shared.api.university.routes.degree_routes import degree_bp
from education_system.shared.api.university.routes.dining_routes import dining_bp
from education_system.shared.api.university.routes.docs_routes import docs_bp
from education_system.shared.api.university.routes.document_routes import document_bp
from education_system.shared.api.university.routes.early_warning_routes import early_warning_bp
from education_system.shared.api.university.routes.election_routes import election_bp
from education_system.shared.api.university.routes.emergency_routes import emergency_bp
from education_system.shared.api.university.routes.enrollment_routes import enrollment_bp
from education_system.shared.api.university.routes.equipment_routes import equipment_bp
from education_system.shared.api.university.routes.evaluation_routes import evaluation_bp
from education_system.shared.api.university.routes.event_routes import event_bp
from education_system.shared.api.university.routes.exam_routes import exam_bp
from education_system.shared.api.university.routes.facility_routes import facility_bp
from education_system.shared.api.university.routes.finance_routes import finance_bp
from education_system.shared.api.university.routes.financial_aid_routes import financial_aid_bp
from education_system.shared.api.university.routes.grade_routes import grade_bp
from education_system.shared.api.university.routes.health_routes import health_bp
from education_system.shared.api.university.routes.helpdesk_routes import helpdesk_bp
from education_system.shared.api.university.routes.housing_routes import housing_bp
from education_system.shared.api.university.routes.hr_routes import hr_bp
from education_system.shared.api.university.routes.integrity_routes import integrity_bp
from education_system.shared.api.university.routes.library_routes import library_bp
from education_system.shared.api.university.routes.lms_routes import lms_bp
from education_system.shared.api.university.routes.lost_found_routes import lost_found_bp
from education_system.shared.api.university.routes.mentorship_routes import mentorship_bp
from education_system.shared.api.university.routes.mfa_routes import mfa_bp
from education_system.shared.api.university.routes.module_routes import module_bp
from education_system.shared.api.university.routes.notification_routes import notification_bp
from education_system.shared.api.university.routes.office_hours_routes import office_hours_bp
from education_system.shared.api.university.routes.parent_routes import parent_bp
from education_system.shared.api.university.routes.parking_routes import parking_bp
from education_system.shared.api.university.routes.research_routes import research_bp
from education_system.shared.api.university.routes.scholarship_routes import scholarship_bp
from education_system.shared.api.university.routes.security_routes import security_bp
from education_system.shared.api.university.routes.student_routes import student_bp
from education_system.shared.api.university.routes.study_group_routes import study_group_bp
from education_system.shared.api.university.routes.system_routes import system_bp
from education_system.shared.api.university.routes.ta_routes import ta_bp
from education_system.shared.api.university.routes.timetable_routes import timetable_bp
from education_system.shared.api.university.routes.tutoring_routes import tutoring_bp
from education_system.shared.api.university.routes.user_routes import user_bp
from education_system.shared.api.university.routes.virtual_classroom_routes import virtual_classroom_bp
from education_system.shared.api.university.routes.web_routes import web_bp

# --- New routes (domain module coverage) ---
from education_system.shared.api.university.routes.academic_progress_routes import academic_progress_bp
from education_system.shared.api.university.routes.academics_domain_routes import academics_domain_bp
from education_system.shared.api.university.routes.accessibility_routes import accessibility_bp
from education_system.shared.api.university.routes.admissions_crm_routes import admissions_crm_bp
from education_system.shared.api.university.routes.ai_study_routes import ai_study_bp
from education_system.shared.api.university.routes.barber_routes import barber_bp
from education_system.shared.api.university.routes.betting_routes import betting_bp
from education_system.shared.api.university.routes.blockchain_routes import blockchain_bp
from education_system.shared.api.university.routes.budget_routes import budget_bp
from education_system.shared.api.university.routes.butcher_routes import butcher_bp
from education_system.shared.api.university.routes.campus_navigation_routes import campus_navigation_bp
from education_system.shared.api.university.routes.carrental_routes import carrental_bp
from education_system.shared.api.university.routes.cinema_routes import cinema_bp
from education_system.shared.api.university.routes.commerce_routes import commerce_bp
from education_system.shared.api.university.routes.course_planning_routes import course_planning_bp
from education_system.shared.api.university.routes.dentist_routes import dentist_bp
from education_system.shared.api.university.routes.events_discovery_routes import events_discovery_bp
from education_system.shared.api.university.routes.facilities_mgmt_routes import facilities_mgmt_bp
from education_system.shared.api.university.routes.feedback_system_routes import feedback_system_bp
from education_system.shared.api.university.routes.gym_routes import gym_bp
from education_system.shared.api.university.routes.legal_routes import legal_bp
from education_system.shared.api.university.routes.mail_routes import mail_bp
from education_system.shared.api.university.routes.marketplace_routes import marketplace_bp
from education_system.shared.api.university.routes.mobility_routes import mobility_bp
from education_system.shared.api.university.routes.musicshop_routes import musicshop_bp
from education_system.shared.api.university.routes.nailbar_routes import nailbar_bp
from education_system.shared.api.university.routes.notification_center_routes import notification_center_bp
from education_system.shared.api.university.routes.phoneshop_routes import phoneshop_bp
from education_system.shared.api.university.routes.portfolio_routes import portfolio_bp
from education_system.shared.api.university.routes.printing_routes import printing_bp
from education_system.shared.api.university.routes.roommate_finder_routes import roommate_finder_bp
from education_system.shared.api.university.routes.scholarship_finder_routes import scholarship_finder_bp
from education_system.shared.api.university.routes.social_matching_routes import social_matching_bp
from education_system.shared.api.university.routes.staff_hr_routes import staff_hr_bp
from education_system.shared.api.university.routes.student_affairs_routes import student_affairs_bp
from education_system.shared.api.university.routes.student_id_routes import student_id_bp
from education_system.shared.api.university.routes.student_jobs_routes import student_jobs_bp
from education_system.shared.api.university.routes.study_matching_routes import study_matching_bp
from education_system.shared.api.university.routes.study_rooms_routes import study_rooms_bp
from education_system.shared.api.university.routes.textbooks_routes import textbooks_bp
from education_system.shared.api.university.routes.wellness_routes import wellness_bp

# --- Missing GUI-to-API coverage ---
from education_system.shared.api.university.routes.achievement_badge_routes import achievement_badge_bp
from education_system.shared.api.university.routes.clearing_adjustment_routes import clearing_adjustment_bp
from education_system.shared.api.university.routes.external_examiner_routes import external_examiner_bp
from education_system.shared.api.university.routes.hesa_export_routes import hesa_export_bp
from education_system.shared.api.university.routes.student_app_routes import student_app_bp
from education_system.shared.api.university.routes.student_finance_routes import student_finance_bp
from education_system.shared.api.university.routes.student_wellbeing_routes import student_wellbeing_bp
from education_system.shared.api.university.routes.study_recommendation_routes import study_recommendation_bp


def register_routes(app: "Flask") -> None:
    """Register all API blueprints on the Flask application."""
    # --- Existing ---
    app.register_blueprint(system_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(module_bp)
    app.register_blueprint(enrollment_bp)
    app.register_blueprint(grade_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(timetable_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(housing_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(facility_bp)
    app.register_blueprint(career_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(admission_bp)
    app.register_blueprint(alumni_bp)
    app.register_blueprint(event_bp)
    app.register_blueprint(dining_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(mentorship_bp)
    app.register_blueprint(parking_bp)
    app.register_blueprint(club_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(lost_found_bp)
    app.register_blueprint(scholarship_bp)
    app.register_blueprint(study_group_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(assessment_bp)
    app.register_blueprint(financial_aid_bp)
    app.register_blueprint(degree_bp)
    app.register_blueprint(announcement_bp)
    app.register_blueprint(advising_bp)
    app.register_blueprint(accommodation_bp)
    app.register_blueprint(tutoring_bp)
    app.register_blueprint(early_warning_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(helpdesk_bp)
    app.register_blueprint(parent_bp)
    app.register_blueprint(lms_bp)
    app.register_blueprint(integrity_bp)
    app.register_blueprint(campus_bp)
    app.register_blueprint(evaluation_bp)
    app.register_blueprint(communication_bp)
    app.register_blueprint(counseling_bp)
    app.register_blueprint(emergency_bp)
    app.register_blueprint(virtual_classroom_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(election_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(credential_bp)
    app.register_blueprint(office_hours_bp)
    app.register_blueprint(ta_bp)
    app.register_blueprint(mfa_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(web_bp)

    # --- New domain module routes ---
    app.register_blueprint(academic_progress_bp)
    app.register_blueprint(academics_domain_bp)
    app.register_blueprint(accessibility_bp)
    app.register_blueprint(admissions_crm_bp)
    app.register_blueprint(ai_study_bp)
    app.register_blueprint(barber_bp)
    app.register_blueprint(betting_bp)
    app.register_blueprint(blockchain_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(butcher_bp)
    app.register_blueprint(campus_navigation_bp)
    app.register_blueprint(carrental_bp)
    app.register_blueprint(cinema_bp)
    app.register_blueprint(commerce_bp)
    app.register_blueprint(course_planning_bp)
    app.register_blueprint(dentist_bp)
    app.register_blueprint(events_discovery_bp)
    app.register_blueprint(facilities_mgmt_bp)
    app.register_blueprint(feedback_system_bp)
    app.register_blueprint(gym_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(mail_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(mobility_bp)
    app.register_blueprint(musicshop_bp)
    app.register_blueprint(nailbar_bp)
    app.register_blueprint(notification_center_bp)
    app.register_blueprint(phoneshop_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(printing_bp)
    app.register_blueprint(roommate_finder_bp)
    app.register_blueprint(scholarship_finder_bp)
    app.register_blueprint(social_matching_bp)
    app.register_blueprint(staff_hr_bp)
    app.register_blueprint(student_affairs_bp)
    app.register_blueprint(student_id_bp)
    app.register_blueprint(student_jobs_bp)
    app.register_blueprint(study_matching_bp)
    app.register_blueprint(study_rooms_bp)
    app.register_blueprint(textbooks_bp)
    app.register_blueprint(wellness_bp)

    # --- Missing GUI-to-API coverage ---
    app.register_blueprint(achievement_badge_bp)
    app.register_blueprint(clearing_adjustment_bp)
    app.register_blueprint(external_examiner_bp)
    app.register_blueprint(hesa_export_bp)
    app.register_blueprint(student_app_bp)
    app.register_blueprint(student_finance_bp)
    app.register_blueprint(student_wellbeing_bp)
    app.register_blueprint(study_recommendation_bp)
