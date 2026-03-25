"""API error handlers for the Secondary School system."""

import logging

from education_system.shared.api.errors import register_common_error_handlers, domain_error_handler
from education_system.secondary_school.core.exceptions import (
    SchoolSystemError, AuthError, ValidationError, DatabaseError,
    StudentError, SubjectError, EnrollmentError, GradeError, AttendanceError,
    BehaviourError, TimetableError,
)
from education_system.shared.auth.exceptions import AuthError as SharedAuthError

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register error handlers on the Flask app."""
    register_common_error_handlers(app)

    app.register_error_handler(ValidationError, domain_error_handler(ValidationError, "Validation Error"))
    app.register_error_handler(AuthError, domain_error_handler(AuthError, "Authentication Error", 401))
    app.register_error_handler(SharedAuthError, domain_error_handler(SharedAuthError, "Authentication Error", 401))
    app.register_error_handler(StudentError, domain_error_handler(StudentError, "Student Error"))
    app.register_error_handler(SubjectError, domain_error_handler(SubjectError, "Subject Error"))
    app.register_error_handler(EnrollmentError, domain_error_handler(EnrollmentError, "Enrollment Error"))
    app.register_error_handler(GradeError, domain_error_handler(GradeError, "Grade Error"))
    app.register_error_handler(AttendanceError, domain_error_handler(AttendanceError, "Attendance Error"))
    app.register_error_handler(BehaviourError, domain_error_handler(BehaviourError, "Behaviour Error"))
    app.register_error_handler(TimetableError, domain_error_handler(TimetableError, "Timetable Error"))
    app.register_error_handler(DatabaseError, domain_error_handler(DatabaseError, "Database Error", 500))
    app.register_error_handler(SchoolSystemError, domain_error_handler(SchoolSystemError, "System Error", 500))
