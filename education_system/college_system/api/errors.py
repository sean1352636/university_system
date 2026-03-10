"""API error handlers."""

from flask import jsonify
import logging

from education_system.college_system.core.exceptions import (
    CollegeSystemError, AuthError, ValidationError, DatabaseError,
    StudentError, CourseError, EnrollmentError, GradeError, AttendanceError,
    TimetableError, AssignmentError, NotificationError, MFAError,
)

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register error handlers on the Flask app."""

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        logger.warning("Validation error: %s", e)
        return jsonify({"error": "Validation Error", "message": str(e)}), 400

    @app.errorhandler(AuthError)
    def handle_auth_error(e):
        logger.warning("Auth error: %s", e)
        return jsonify({"error": "Authentication Error", "message": str(e)}), 401

    @app.errorhandler(StudentError)
    def handle_student_error(e):
        return jsonify({"error": "Student Error", "message": str(e)}), 400

    @app.errorhandler(CourseError)
    def handle_course_error(e):
        return jsonify({"error": "Course Error", "message": str(e)}), 400

    @app.errorhandler(EnrollmentError)
    def handle_enrollment_error(e):
        return jsonify({"error": "Enrollment Error", "message": str(e)}), 400

    @app.errorhandler(GradeError)
    def handle_grade_error(e):
        return jsonify({"error": "Grade Error", "message": str(e)}), 400

    @app.errorhandler(AttendanceError)
    def handle_attendance_error(e):
        return jsonify({"error": "Attendance Error", "message": str(e)}), 400

    @app.errorhandler(TimetableError)
    def handle_timetable_error(e):
        return jsonify({"error": "Timetable Error", "message": str(e)}), 400

    @app.errorhandler(AssignmentError)
    def handle_assignment_error(e):
        return jsonify({"error": "Assignment Error", "message": str(e)}), 400

    @app.errorhandler(NotificationError)
    def handle_notification_error(e):
        return jsonify({"error": "Notification Error", "message": str(e)}), 400

    @app.errorhandler(MFAError)
    def handle_mfa_error(e):
        return jsonify({"error": "MFA Error", "message": str(e)}), 400

    @app.errorhandler(DatabaseError)
    def handle_db_error(e):
        logger.error("Database error: %s", e)
        return jsonify({"error": "Database Error", "message": str(e)}), 500

    @app.errorhandler(CollegeSystemError)
    def handle_system_error(e):
        logger.error("System error: %s", e)
        return jsonify({"error": "System Error", "message": str(e)}), 500

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "Not Found", "message": "Resource not found."}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({"error": "Method Not Allowed", "message": str(e)}), 405

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error("Internal server error: %s", e)
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500
