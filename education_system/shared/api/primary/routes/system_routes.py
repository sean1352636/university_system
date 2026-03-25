"""System API routes (health check, info)."""

from flask import Blueprint, jsonify

from education_system.shared.api.primary.auth import token_required

system_bp = Blueprint("system", __name__, url_prefix="/api/system")

_db_path = None
__version__ = "1.0.0"


def init_system_routes(db_path=None):
    global _db_path
    _db_path = db_path


@system_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "version": __version__})


@system_bp.route("/info", methods=["GET"])
@token_required
def system_info():
    return jsonify({
        "name": "Primary School Management System",
        "version": __version__,
        "modules": [
            "pupils", "subjects", "classes", "assessment", "attendance",
            "timetable", "homework", "sats", "phonics", "reading_records", "progress",
            "behaviour", "rewards", "safeguarding", "send", "pastoral",
            "hr", "cpd", "cover", "staff_directory",
            "users", "settings", "admissions", "finance", "data_export", "audit_log", "policies", "documents",
            "clubs", "meals", "transport", "trips", "library", "medical", "class_groups", "consent",
            "email", "notifications", "announcements", "calendar", "parents_evening", "communication_log",
            "room_booking", "assets", "visitors", "incidents",
        ],
    })
