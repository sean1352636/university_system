"""Centralised error handling for the Flask API.

Maps domain exceptions to HTTP status codes and registers global
error handlers that return consistent JSON responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import jsonify

if TYPE_CHECKING:
    from flask import Flask

from education_system.systems.university.infrastructure.exceptions import (
    AlreadyEnrolledError,
    AuthenticationError,
    CourseFullError,
    CourseNotFoundError,
    DatabaseError,
    DuplicateStudentError,
    EnrollmentError,
    FinanceError,
    GradeNotFoundError,
    InsufficientFundsError,
    InvalidCredentialsError,
    PaymentError,
    PermissionDeniedError,
    StudentNotFoundError,
    TransactionFailedError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Domain-exception → HTTP status code mapping
_EXCEPTION_STATUS_MAP: list[tuple[type, int]] = [
    (ValidationError, 400),
    (InvalidCredentialsError, 401),
    (AuthenticationError, 401),
    (PermissionDeniedError, 403),
    (StudentNotFoundError, 404),
    (CourseNotFoundError, 404),
    (GradeNotFoundError, 404),
    (DuplicateStudentError, 409),
    (AlreadyEnrolledError, 409),
    (CourseFullError, 409),
    (EnrollmentError, 400),
    (InsufficientFundsError, 402),
    (PaymentError, 400),
    (TransactionFailedError, 500),
    (FinanceError, 400),
    (DatabaseError, 503),
]


def _error_response(message: str, status: int):
    """Build a standard JSON error response."""
    return jsonify({"error": message, "status": status}), status


def register_error_handlers(app: "Flask") -> None:
    """Register global error handlers on the Flask application."""

    for exc_class, status_code in _EXCEPTION_STATUS_MAP:

        def _make_handler(status: int):
            def handler(exc):
                msg = str(exc) if str(exc) else exc.__class__.__name__
                logger.warning("API error [%d]: %s", status, msg)
                return _error_response(msg, status)

            return handler

        app.register_error_handler(exc_class, _make_handler(status_code))

    @app.errorhandler(404)
    def not_found(exc):
        return _error_response("Resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return _error_response("Method not allowed", 405)

    @app.errorhandler(500)
    def internal_error(exc):
        logger.exception("Internal server error")
        return _error_response("Internal server error", 500)
