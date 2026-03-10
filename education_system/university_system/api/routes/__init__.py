"""Register all API route blueprints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

from education_system.university_system.api.routes.accommodation_routes import accommodation_bp
from education_system.university_system.api.routes.admission_routes import admission_bp
from education_system.university_system.api.routes.campus_routes import campus_bp
from education_system.university_system.api.routes.communication_routes import communication_bp
from education_system.university_system.api.routes.counseling_routes import counseling_bp
from education_system.university_system.api.routes.credential_routes import credential_bp
from education_system.university_system.api.routes.office_hours_routes import office_hours_bp
from education_system.university_system.api.routes.ta_routes import ta_bp
from education_system.university_system.api.routes.document_routes import document_bp
from education_system.university_system.api.routes.election_routes import election_bp
from education_system.university_system.api.routes.emergency_routes import emergency_bp
from education_system.university_system.api.routes.equipment_routes import equipment_bp
from education_system.university_system.api.routes.evaluation_routes import evaluation_bp
from education_system.university_system.api.routes.helpdesk_routes import helpdesk_bp
from education_system.university_system.api.routes.hr_routes import hr_bp
from education_system.university_system.api.routes.integrity_routes import integrity_bp
from education_system.university_system.api.routes.lms_routes import lms_bp
from education_system.university_system.api.routes.parent_routes import parent_bp
from education_system.university_system.api.routes.virtual_classroom_routes import virtual_classroom_bp
from education_system.university_system.api.routes.advising_routes import advising_bp
from education_system.university_system.api.routes.alumni_routes import alumni_bp
from education_system.university_system.api.routes.announcement_routes import announcement_bp
from education_system.university_system.api.routes.assessment_routes import assessment_bp
from education_system.university_system.api.routes.assignment_routes import assignment_bp
from education_system.university_system.api.routes.attendance_routes import attendance_bp
from education_system.university_system.api.routes.auth_routes import auth_bp
from education_system.university_system.api.routes.calendar_routes import calendar_bp
from education_system.university_system.api.routes.career_routes import career_bp
from education_system.university_system.api.routes.chat_routes import chat_bp
from education_system.university_system.api.routes.club_routes import club_bp
from education_system.university_system.api.routes.course_routes import course_bp
from education_system.university_system.api.routes.dashboard_routes import dashboard_bp
from education_system.university_system.api.routes.degree_routes import degree_bp
from education_system.university_system.api.routes.dining_routes import dining_bp
from education_system.university_system.api.routes.early_warning_routes import early_warning_bp
from education_system.university_system.api.routes.enrollment_routes import enrollment_bp
from education_system.university_system.api.routes.event_routes import event_bp
from education_system.university_system.api.routes.exam_routes import exam_bp
from education_system.university_system.api.routes.facility_routes import facility_bp
from education_system.university_system.api.routes.finance_routes import finance_bp
from education_system.university_system.api.routes.financial_aid_routes import financial_aid_bp
from education_system.university_system.api.routes.grade_routes import grade_bp
from education_system.university_system.api.routes.health_routes import health_bp
from education_system.university_system.api.routes.housing_routes import housing_bp
from education_system.university_system.api.routes.library_routes import library_bp
from education_system.university_system.api.routes.lost_found_routes import lost_found_bp
from education_system.university_system.api.routes.mentorship_routes import mentorship_bp
from education_system.university_system.api.routes.module_routes import module_bp
from education_system.university_system.api.routes.notification_routes import notification_bp
from education_system.university_system.api.routes.parking_routes import parking_bp
from education_system.university_system.api.routes.research_routes import research_bp
from education_system.university_system.api.routes.scholarship_routes import scholarship_bp
from education_system.university_system.api.routes.security_routes import security_bp
from education_system.university_system.api.routes.student_routes import student_bp
from education_system.university_system.api.routes.study_group_routes import study_group_bp
from education_system.university_system.api.routes.system_routes import system_bp
from education_system.university_system.api.routes.timetable_routes import timetable_bp
from education_system.university_system.api.routes.docs_routes import docs_bp
from education_system.university_system.api.routes.tutoring_routes import tutoring_bp
from education_system.university_system.api.routes.user_routes import user_bp
from education_system.university_system.api.routes.web_routes import web_bp
from education_system.university_system.api.routes.mfa_routes import mfa_bp
from education_system.university_system.api.routes.account_routes import account_bp


def register_routes(app: "Flask") -> None:
    """Register all API blueprints on the Flask application."""
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
