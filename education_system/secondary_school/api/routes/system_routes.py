"""System/health API routes."""

from flask import Blueprint, jsonify

system_bp = Blueprint("system", __name__, url_prefix="/api")

_db_path = None


def init_system_routes(db_path=None):
    global _db_path
    _db_path = db_path


@system_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "system": "Secondary School Management System",
        "version": "1.0.0",
    })


@system_bp.route("/info", methods=["GET"])
def system_info():
    return jsonify({
        "name": "Secondary School Management System",
        "version": "1.0.0",
        "year_groups": ["7", "8", "9", "10", "11"],
        "key_stages": ["KS3", "KS4"],
        "modules": [
            "students", "subjects", "enrollment", "grades", "attendance",
            "timetable", "homework", "exams", "progress", "interventions",
            "reports", "behaviour", "detentions", "exclusions", "rewards",
            "pastoral", "safeguarding", "send", "hr", "cpd", "cover",
            "staff_directory", "users", "settings", "admissions", "finance",
            "data_export", "audit_log", "policies", "documents",
            "clubs", "meals", "transport", "trips", "careers", "library",
            "medical", "form_groups", "consent", "room_booking", "assets",
            "seating_plans", "visitors", "incidents", "email", "notifications",
            "announcements", "calendar", "communication_log", "parents_evening",
        ],
    })
