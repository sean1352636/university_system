"""Dashboard routes: role-aware aggregate statistics."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify

from education_system.shared.api.university.auth import token_required
from education_system.university_system.core.sql_safety import validate_table_name
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _safe_count(conn, table: str) -> int:
    try:
        safe_tbl = validate_table_name(table, conn=conn)
        row = conn.execute("SELECT COUNT(*) FROM [" + safe_tbl + "]").fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def _safe_count_where(conn, table: str, where: str, params: tuple = ()) -> int:
    try:
        safe_tbl = validate_table_name(table, conn=conn)
        row = conn.execute(
            "SELECT COUNT(*) FROM [" + safe_tbl + "] WHERE " + where, params
        ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def _safe_query_val(conn, sql: str, params: tuple = (), default=0):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else default
    except Exception:
        return default


def _system_wide_counts(conn) -> dict:
    """Full table counts used by admin dashboard (original behavior)."""
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
    counts = {}
    for key, table in tables.items():
        counts[key] = _safe_count(conn, table)
    return counts


def _admin_dashboard(conn) -> dict:
    """Admin: system-wide counts plus user/activity stats."""
    stats = _system_wide_counts(conn)

    stats["active_users"] = _safe_count_where(conn, "users", "is_active = 1")
    stats["admin_users"] = _safe_count_where(conn, "users", "role = ?", ("admin",))
    stats["staff_users"] = _safe_count_where(conn, "users", "role = ?", ("staff",))
    stats["instructor_users"] = _safe_count_where(conn, "users", "role = ?", ("instructor",))
    stats["student_users"] = _safe_count_where(conn, "users", "role = ?", ("student",))
    stats["pending_leave_requests"] = _safe_count_where(
        conn, "leave_requests", "status = ?", ("pending",)
    )
    stats["open_support_tickets"] = _safe_count_where(
        conn, "support_tickets", "status IN ('open', 'in_progress')"
    )

    return stats


def _staff_dashboard(conn, user_id: int) -> dict:
    """Staff: department-level stats, HR metrics."""
    stats = {}

    stats["staff"] = _safe_count(conn, "staff")
    stats["departments"] = _safe_count(conn, "departments")
    stats["leave_requests"] = _safe_count(conn, "leave_requests")
    stats["pending_leave_requests"] = _safe_count_where(
        conn, "leave_requests", "status = ?", ("pending",)
    )
    stats["approved_leave_requests"] = _safe_count_where(
        conn, "leave_requests", "status = ?", ("approved",)
    )
    stats["shifts"] = _safe_count(conn, "shifts")
    stats["timesheets"] = _safe_count(conn, "timesheets")
    stats["support_tickets"] = _safe_count(conn, "support_tickets")
    stats["open_support_tickets"] = _safe_count_where(
        conn, "support_tickets", "status IN ('open', 'in_progress')"
    )
    stats["maintenance_requests"] = _safe_count(conn, "maintenance_requests")
    stats["announcements"] = _safe_count(conn, "announcements")
    stats["events"] = _safe_count(conn, "events")

    return stats


def _student_dashboard(conn, user_id: int, username: str) -> dict:
    """Student: personal academic data."""
    stats = {}

    # Try to find the student record linked to this user
    student_id = _safe_query_val(
        conn,
        "SELECT student_id FROM students WHERE user_id = ? OR student_id = ?",
        (user_id, username),
        default=None,
    )

    if student_id:
        stats["enrolled_modules"] = _safe_count_where(
            conn, "student_modules", "student_id = ? AND status = 'active'",
            (student_id,),
        )
        stats["total_assignments"] = _safe_count_where(
            conn, "assignments",
            "module_code IN (SELECT module_code FROM student_modules WHERE student_id = ?)",
            (student_id,),
        )
        stats["grades_recorded"] = _safe_count_where(
            conn, "grades", "student_id = ?", (student_id,),
        )

        # Attendance percentage
        total_sessions = _safe_query_val(
            conn,
            "SELECT COUNT(*) FROM attendance_records WHERE student_id = ?",
            (student_id,),
        )
        present_sessions = _safe_query_val(
            conn,
            "SELECT COUNT(*) FROM attendance_records WHERE student_id = ? AND status = 'present'",
            (student_id,),
        )
        if total_sessions and total_sessions > 0:
            stats["attendance_percentage"] = round(present_sessions / total_sessions * 100, 1)
        else:
            stats["attendance_percentage"] = 0

        # Financial balance
        total_fees = _safe_query_val(
            conn, "SELECT COALESCE(SUM(amount), 0) FROM fees WHERE student_id = ?",
            (student_id,),
        )
        total_paid = _safe_query_val(
            conn, "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE student_id = ?",
            (student_id,),
        )
        stats["financial_balance"] = round(float(total_fees) - float(total_paid), 2)
    else:
        stats["enrolled_modules"] = 0
        stats["total_assignments"] = 0
        stats["grades_recorded"] = 0
        stats["attendance_percentage"] = 0
        stats["financial_balance"] = 0

    stats["upcoming_exams"] = _safe_count(conn, "exams")
    stats["announcements"] = _safe_count(conn, "announcements")

    return stats


def _instructor_dashboard(conn, user_id: int, username: str) -> dict:
    """Instructor: teaching overview."""
    stats = {}

    # Count modules assigned to this instructor
    stats["assigned_modules"] = _safe_count_where(
        conn, "modules", "instructor_id = ? OR instructor = ?",
        (user_id, username),
    )

    # Student count across instructor's modules
    stats["total_students"] = _safe_query_val(
        conn,
        "SELECT COUNT(DISTINCT student_id) FROM student_modules "
        "WHERE module_code IN (SELECT module_code FROM modules WHERE instructor_id = ? OR instructor = ?)",
        (user_id, username),
    )

    stats["assignments"] = _safe_count(conn, "assignments")
    stats["exams"] = _safe_count(conn, "exams")
    stats["assessments"] = _safe_count(conn, "assessments")
    stats["attendance_sessions"] = _safe_count(conn, "attendance_sessions")
    stats["misconduct_cases"] = _safe_count(conn, "academic_misconduct_cases")
    stats["course_evaluations"] = _safe_count(conn, "course_evaluations")

    return stats


@dashboard_bp.route("/stats", methods=["GET"])
@token_required
def stats():
    role = g.current_user.get("role", "student")
    user_id = g.current_user.get("user_id")
    username = g.current_user.get("sub", "")

    with get_connection() as conn:
        if role == "admin":
            data = _admin_dashboard(conn)
        elif role == "staff":
            data = _staff_dashboard(conn, user_id)
        elif role == "instructor":
            data = _instructor_dashboard(conn, user_id, username)
        elif role == "student":
            data = _student_dashboard(conn, user_id, username)
        else:
            data = _system_wide_counts(conn)

    log_activity("view", "dashboard_stats", user=username)
    return jsonify({"stats": data, "role": role})
