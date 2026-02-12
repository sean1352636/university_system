"""Dashboard routes: aggregate statistics."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify

from university_system.api.auth import token_required
from university_system.core.sql_safety import validate_table_name
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("/stats", methods=["GET"])
@token_required
def stats():
    with get_connection() as conn:
        counts = {}
        tables = {
            "students": "students",
            "modules": "modules",
            "enrollments": "student_modules",
            "courses": "courses",
            "users": "users",
            "payments": "payments",
            "assignments": "assignments",
            "attendance_sessions": "attendance_sessions",
            "housing_applications": "housing_applications",
            "housing_rooms": "housing_rooms",
            "books": "books",
            "book_loans": "book_loans",
            "health_appointments": "health_appointments",
            "facility_bookings": "facility_bookings",
            "maintenance_requests": "maintenance_requests",
            "job_postings": "job_postings",
            "research_projects": "research_projects",
            "admission_applications": "admission_applications",
            "alumni": "alumni",
            "events": "events",
            "meal_accounts": "meal_accounts",
            "notifications": "notifications",
            "mentorship_relationships": "mentorship_relationships",
            "parking_permits": "parking_permits",
            "student_clubs": "student_clubs",
            "security_tickets": "security_desk_tickets",
            "lost_found_items": "lost_found",
            "scholarships": "scholarships",
            "scholarship_applications": "scholarship_applications",
            "study_groups": "study_groups",
            "exams": "exams",
            "calendar_events": "academic_calendar_events",
            "assessments": "assessments",
            "financial_aid_applications": "financial_aid_applications",
            "aid_packages": "aid_packages",
            "degree_programs": "degree_programs",
            "announcements": "announcements",
            "advising_appointments": "advising_appointments",
            "accommodations": "accommodations",
            "accommodation_requests": "accommodation_requests",
            "tutoring_offers": "tutoring_offers",
            "early_warning_profiles": "early_warning_profiles",
            "chat_rooms": "chat_rooms",
            "staff": "staff",
            "departments": "departments",
            "instructors": "instructors",
            "leave_requests": "leave_requests",
            "shifts": "shifts",
            "timesheets": "timesheets",
            "support_tickets": "support_tickets",
            "kb_articles": "kb_articles",
            "faqs": "faqs",
            "parent_accounts": "parent_accounts",
            "parent_conferences": "parent_conferences",
            "lms_courses": "lms_courses",
            "lms_quizzes": "lms_quizzes",
            "misconduct_cases": "academic_misconduct_cases",
            "buildings": "buildings",
            "room_bookings": "room_bookings",
            "campus_tours": "campus_tours",
            "feedback_submissions": "feedback_submissions",
            "course_evaluations": "course_evaluations",
            "messages": "messages",
            "newsletters": "newsletters",
            "mental_health_appointments": "mental_health_appointments",
            "counseling_appointments": "counseling_appointments",
            "emergency_alerts": "emergency_alerts",
            "incidents": "incidents",
            "virtual_classrooms": "virtual_classrooms",
            "virtual_sessions": "virtual_sessions",
            "equipment": "equipment",
            "equipment_checkouts": "equipment_checkouts",
            "facility_assets": "facility_assets",
            "polls": "polls",
            "election_candidates": "election_candidates",
            "union_representatives": "union_representatives",
            "document_repository": "document_repository",
            "student_documents": "student_documents",
            "blockchain_credentials": "blockchain_credentials",
            "digital_badges": "digital_badges",
            "certifications": "certifications",
        }
        for key, table in tables.items():
            try:
                safe_tbl = validate_table_name(table, conn=conn)
                row = conn.execute("SELECT COUNT(*) FROM [" + safe_tbl + "]").fetchone()
                counts[key] = row[0] if row else 0
            except Exception:
                counts[key] = 0

    log_activity("view", "dashboard_stats", user=g.current_user.get("sub"))
    return jsonify({"stats": counts})
