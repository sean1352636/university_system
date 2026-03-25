"""System routes: health check, version info, and root redirect."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, redirect

system_bp = Blueprint("system", __name__)


@system_bp.route("/", methods=["GET"])
def root():
    """Redirect the root URL to the web frontend."""
    return redirect("/web/login")


@system_bp.route("/api", methods=["GET"])
@system_bp.route("/api/", methods=["GET"])
def index():
    return jsonify({
        "name": "University Management System API",
        "version": "5.46.3",
        "web_portal": "/web/login",
        "endpoints": {
            "portal": "/portal",
            "docs": "/api/docs",
            "openapi_spec": "/api/openapi.json",
            "health": "/api/health",
            "version": "/api/version",
            "auth": "/api/auth/login",
            "students": "/api/students",
            "modules": "/api/modules",
            "enrollments": "/api/enrollments",
            "grades": "/api/grades",
            "finance": "/api/finance",
            "attendance": "/api/attendance",
            "assignments": "/api/assignments",
            "timetable": "/api/timetable",
            "courses": "/api/courses",
            "users": "/api/users",
            "dashboard": "/api/dashboard/stats",
            "housing": "/api/housing",
            "library": "/api/library",
            "health_services": "/api/health-services",
            "facilities": "/api/facilities",
            "career": "/api/career",
            "research": "/api/research",
            "admissions": "/api/admissions",
            "alumni": "/api/alumni",
            "events": "/api/events",
            "dining": "/api/dining",
            "notifications": "/api/notifications",
            "mentorship": "/api/mentorship",
            "parking": "/api/parking",
            "clubs": "/api/clubs",
            "security": "/api/security",
            "lost_found": "/api/lost-found",
            "scholarships": "/api/scholarships",
            "study_groups": "/api/study-groups",
            "exams": "/api/exams",
            "calendar": "/api/calendar",
            "assessments": "/api/assessments",
            "financial_aid": "/api/financial-aid",
            "degrees": "/api/degrees",
            "announcements": "/api/announcements",
            "advising": "/api/advising",
            "accommodations": "/api/accommodations",
            "tutoring": "/api/tutoring",
            "early_warning": "/api/early-warning",
            "chat": "/api/chat",
            "hr": "/api/hr",
            "helpdesk": "/api/helpdesk",
            "parents": "/api/parents",
            "lms": "/api/lms",
            "integrity": "/api/integrity",
            "campus": "/api/campus",
            "evaluations": "/api/evaluations",
            "communication": "/api/communication",
            "counseling": "/api/counseling",
            "emergency": "/api/emergency",
            "virtual_classrooms": "/api/virtual-classrooms",
            "equipment": "/api/equipment",
            "elections": "/api/elections",
            "documents": "/api/documents",
            "credentials": "/api/credentials",
            "mfa": "/api/mfa",
            "account": "/api/account",
        },
    })


@system_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@system_bp.route("/api/version", methods=["GET"])
def version():
    return jsonify({
        "version": "5.46.3",
        "api_version": "1.0",
        "python_framework": "Flask",
    })
