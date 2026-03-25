"""API error handlers for the College system."""

import logging

from education_system.shared.api.errors import register_common_error_handlers, domain_error_handler
from education_system.college_system.core.exceptions import (
    CollegeSystemError, AuthError, ValidationError, DatabaseError,
    StudentError, CourseError, EnrollmentError, GradeError, AttendanceError,
    TimetableError, AssignmentError, NotificationError, MFAError,
)

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register error handlers on the Flask app."""
    register_common_error_handlers(app)

    app.register_error_handler(ValidationError, domain_error_handler(ValidationError, "Validation Error"))
    app.register_error_handler(AuthError, domain_error_handler(AuthError, "Authentication Error", 401))
    app.register_error_handler(StudentError, domain_error_handler(StudentError, "Student Error"))
    app.register_error_handler(CourseError, domain_error_handler(CourseError, "Course Error"))
    app.register_error_handler(EnrollmentError, domain_error_handler(EnrollmentError, "Enrollment Error"))
    app.register_error_handler(GradeError, domain_error_handler(GradeError, "Grade Error"))
    app.register_error_handler(AttendanceError, domain_error_handler(AttendanceError, "Attendance Error"))
    app.register_error_handler(TimetableError, domain_error_handler(TimetableError, "Timetable Error"))
    app.register_error_handler(AssignmentError, domain_error_handler(AssignmentError, "Assignment Error"))
    app.register_error_handler(NotificationError, domain_error_handler(NotificationError, "Notification Error"))
    app.register_error_handler(MFAError, domain_error_handler(MFAError, "MFA Error"))
    app.register_error_handler(DatabaseError, domain_error_handler(DatabaseError, "Database Error", 500))
    app.register_error_handler(CollegeSystemError, domain_error_handler(CollegeSystemError, "System Error", 500))
