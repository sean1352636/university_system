"""
Custom exception hierarchy for the university system.

This module defines a comprehensive exception hierarchy that provides
specific exception types for different error scenarios across the system.

Exception Hierarchy:
    UniversitySystemError (base)
    ├── DatabaseError
    │   ├── ConnectionError
    │   ├── QueryError
    │   ├── TransactionError
    │   └── IntegrityError
    ├── AuthenticationError
    │   ├── InvalidCredentialsError
    │   ├── SessionExpiredError
    │   ├── PermissionDeniedError
    │   └── MFARequiredError
    ├── ValidationError
    │   ├── InvalidInputError
    │   ├── MissingFieldError
    │   └── FormatError
    ├── StudentError
    │   ├── StudentNotFoundError
    │   ├── DuplicateStudentError
    │   └── StudentEnrollmentError
    ├── CourseError
    │   ├── CourseNotFoundError
    │   ├── CourseFullError
    │   └── PrerequisiteError
    ├── EnrollmentError
    │   ├── AlreadyEnrolledError
    │   ├── EnrollmentClosedError
    │   └── CapacityExceededError
    ├── GradeError
    │   ├── InvalidGradeError
    │   └── GradeNotFoundError
    ├── FinanceError
    │   ├── PaymentError
    │   ├── InsufficientFundsError
    │   └── TransactionFailedError
    ├── EmailError
    │   ├── EmailDeliveryError
    │   ├── TemplateError
    │   └── AttachmentError
    ├── FileError
    │   ├── FileNotFoundError (custom)
    │   ├── FileUploadError
    │   └── FileValidationError
    └── ConfigurationError
        ├── MissingConfigError
        └── InvalidConfigError
"""

from __future__ import annotations
from typing import Optional, Any

# Lazy i18n import to prevent circular imports during package initialization
# i18n will be imported on first use, not at module import time
_i18n_loaded = False
_get_text_func = None
_translate_func = None

def _load_i18n():
    """Lazy load i18n module to prevent circular imports."""
    global _i18n_loaded, _get_text_func, _translate_func
    if not _i18n_loaded:
        try:
            from education_system.systems.university.infrastructure.i18n import get_text as gt, _ as t
            _get_text_func = gt
            _translate_func = t
        except ImportError:
            # Fallback if i18n not available
            _get_text_func = lambda key, **kwargs: kwargs.get('default', key)
            _translate_func = _get_text_func
        _i18n_loaded = True

def get_text(key: str, **kwargs) -> str:
    """Get translated text with lazy i18n loading."""
    _load_i18n()
    return _get_text_func(key, **kwargs)

def _(key: str, **kwargs) -> str:
    """Translation shorthand with lazy i18n loading."""
    _load_i18n()
    return _translate_func(key, **kwargs)


# ============================================================================
# Base Exception
# ============================================================================

class UniversitySystemError(Exception):
    """
    Base exception for all university system errors.

    All custom exceptions in the system should inherit from this class.
    This allows for catching all system-specific errors with a single
    except clause if needed.

    Attributes:
        message: Human-readable error message
        code: Optional error code for programmatic handling
        details: Optional dict with additional error context
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dict for logging/API responses."""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'code': self.code,
            'details': self.details
        }


# ============================================================================
# Database Exceptions
# ============================================================================

class DatabaseError(UniversitySystemError):
    """Base exception for database-related errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Database connection failed or was lost."""
    def __init__(self, message: str = "Database connection failed", **kwargs):
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="DB_CONNECTION_ERROR", **kwargs)


class QueryError(DatabaseError):
    """Database query execution failed."""
    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        details = kwargs.get('details', {})
        if query:
            details['query'] = query
        kwargs['details'] = details
        super().__init__(message, code="DB_QUERY_ERROR", **kwargs)


class TransactionError(DatabaseError):
    """Database transaction failed."""
    def __init__(self, message: str = "Transaction failed", **kwargs):
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="DB_TRANSACTION_ERROR", **kwargs)


class IntegrityError(DatabaseError):
    """Database integrity constraint violated."""
    def __init__(self, message: str = "Integrity constraint violated", **kwargs):
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="DB_INTEGRITY_ERROR", **kwargs)


# ============================================================================
# Authentication/Authorization Exceptions
# ============================================================================

class AuthenticationError(UniversitySystemError):
    """Base exception for authentication-related errors."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""
    def __init__(self, message: str = "Invalid credentials", **kwargs):
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="AUTH_INVALID_CREDENTIALS", **kwargs)


class SessionExpiredError(AuthenticationError):
    """User session has expired."""
    def __init__(self, message: str = "Session expired", **kwargs):
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="AUTH_SESSION_EXPIRED", **kwargs)


class PermissionDeniedError(AuthenticationError):
    """User lacks permission for the requested operation."""
    def __init__(self, message: str = "Permission denied", resource: Optional[str] = None, **kwargs):
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        details = kwargs.get('details', {})
        if resource:
            details['resource'] = resource
        kwargs['details'] = details
        super().__init__(message, code="AUTH_PERMISSION_DENIED", **kwargs)


class MFARequiredError(AuthenticationError):
    """Multi-factor authentication required."""
    def __init__(self, message: str = "MFA required", **kwargs):
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="AUTH_MFA_REQUIRED", **kwargs)


# ============================================================================
# Validation Exceptions
# ============================================================================

class ValidationError(UniversitySystemError):
    """Base exception for validation errors."""
    pass


class InvalidInputError(ValidationError):
    """Input data is invalid."""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="VALIDATION_INVALID_INPUT", **kwargs)


class MissingFieldError(ValidationError):
    """Required field is missing."""
    def __init__(self, field: str, **kwargs):
        message = f"Required field missing: {field}"
        kwargs['details'] = kwargs.get('details', {})
        kwargs['details']['field'] = field
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="VALIDATION_MISSING_FIELD", **kwargs)


class FormatError(ValidationError):
    """Data format is incorrect."""
    def __init__(self, message: str, expected_format: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if expected_format:
            details['expected_format'] = expected_format
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="VALIDATION_FORMAT_ERROR", **kwargs)


# ============================================================================
# Student-related Exceptions
# ============================================================================

class StudentError(UniversitySystemError):
    """Base exception for student-related errors."""
    pass


class StudentNotFoundError(StudentError):
    """Student not found in system."""
    def __init__(self, student_id: Optional[str] = None, **kwargs):
        message = f"Student not found: {student_id}" if student_id else "Student not found"
        if student_id:
            kwargs['details'] = kwargs.get('details', {})
            kwargs['details']['student_id'] = student_id
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="STUDENT_NOT_FOUND", **kwargs)


class DuplicateStudentError(StudentError):
    """Student already exists in system."""
    def __init__(self, identifier: str, **kwargs):
        message = f"Student already exists: {identifier}"
        kwargs['details'] = kwargs.get('details', {})
        kwargs['details']['identifier'] = identifier
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="STUDENT_DUPLICATE", **kwargs)


class StudentEnrollmentError(StudentError):
    """Student enrollment operation failed."""
    pass


# ============================================================================
# Course-related Exceptions
# ============================================================================

class CourseError(UniversitySystemError):
    """Base exception for course-related errors."""
    pass


class CourseNotFoundError(CourseError):
    """Course not found in system."""
    def __init__(self, course_id: Optional[str] = None, **kwargs):
        message = f"Course not found: {course_id}" if course_id else "Course not found"
        if course_id:
            kwargs['details'] = kwargs.get('details', {})
            kwargs['details']['course_id'] = course_id
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="COURSE_NOT_FOUND", **kwargs)


class CourseFullError(CourseError):
    """Course has reached maximum capacity."""
    def __init__(self, course_id: Optional[str] = None, **kwargs):
        message = f"Course is full: {course_id}" if course_id else "Course is full"
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="COURSE_FULL", **kwargs)


class PrerequisiteError(CourseError):
    """Course prerequisites not met."""
    def __init__(self, course_id: str, missing_prereqs: Optional[list[str]] = None, **kwargs):
        message = f"Prerequisites not met for course: {course_id}"
        details = kwargs.get('details', {})
        details['course_id'] = course_id
        if missing_prereqs:
            details['missing_prerequisites'] = missing_prereqs
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="COURSE_PREREQUISITE_ERROR", **kwargs)


# ============================================================================
# Enrollment Exceptions
# ============================================================================

class EnrollmentError(UniversitySystemError):
    """Base exception for enrollment-related errors."""
    pass


class AlreadyEnrolledError(EnrollmentError):
    """Student is already enrolled in the course."""
    def __init__(self, student_id: str, course_id: str, **kwargs):
        message = f"Student {student_id} already enrolled in course {course_id}"
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="ENROLLMENT_ALREADY_ENROLLED", **kwargs)


class EnrollmentClosedError(EnrollmentError):
    """Enrollment period has closed."""
    def __init__(self, course_id: Optional[str] = None, **kwargs):
        message = f"Enrollment closed for course: {course_id}" if course_id else "Enrollment closed"
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="ENROLLMENT_CLOSED", **kwargs)


class CapacityExceededError(EnrollmentError):
    """Maximum enrollment capacity exceeded."""
    pass


# ============================================================================
# Grade-related Exceptions
# ============================================================================

class GradeError(UniversitySystemError):
    """Base exception for grade-related errors."""
    pass


class InvalidGradeError(GradeError):
    """Grade value is invalid."""
    def __init__(self, grade: Any, **kwargs):
        message = f"Invalid grade: {grade}"
        kwargs['details'] = kwargs.get('details', {})
        kwargs['details']['grade'] = grade
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="GRADE_INVALID", **kwargs)


class GradeNotFoundError(GradeError):
    """Grade record not found."""
    pass


# ============================================================================
# Finance Exceptions
# ============================================================================

class FinanceError(UniversitySystemError):
    """Base exception for finance-related errors."""
    pass


class PaymentError(FinanceError):
    """Payment processing failed."""
    pass


class InsufficientFundsError(FinanceError):
    """Account has insufficient funds."""
    def __init__(self, required: float, available: float, **kwargs):
        message = f"Insufficient funds: required {required}, available {available}"
        details = kwargs.get('details', {})
        details['required_amount'] = required
        details['available_amount'] = available
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="FINANCE_INSUFFICIENT_FUNDS", **kwargs)


class TransactionFailedError(FinanceError):
    """Financial transaction failed."""
    pass


# ============================================================================
# Email Exceptions
# ============================================================================

class EmailError(UniversitySystemError):
    """Base exception for email-related errors."""
    pass


class EmailDeliveryError(EmailError):
    """Email delivery failed."""
    def __init__(self, recipient: str, reason: Optional[str] = None, **kwargs):
        message = f"Failed to deliver email to {recipient}"
        if reason:
            message += f": {reason}"
        details = kwargs.get('details', {})
        details['recipient'] = recipient
        if reason:
            details['reason'] = reason
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="EMAIL_DELIVERY_ERROR", **kwargs)


class TemplateError(EmailError):
    """Email template error."""
    pass


class AttachmentError(EmailError):
    """Email attachment error."""
    pass


# ============================================================================
# File Exceptions
# ============================================================================

class FileError(UniversitySystemError):
    """Base exception for file-related errors."""
    pass


class UniversityFileNotFoundError(FileError):
    """File not found (custom to avoid conflict with built-in)."""
    def __init__(self, file_path: str, **kwargs):
        message = f"File not found: {file_path}"
        kwargs['details'] = kwargs.get('details', {})
        kwargs['details']['file_path'] = file_path
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="FILE_NOT_FOUND", **kwargs)


class FileUploadError(FileError):
    """File upload failed."""
    pass


class FileValidationError(FileError):
    """File failed validation checks."""
    def __init__(self, message: str, file_name: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if file_name:
            details['file_name'] = file_name
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="FILE_VALIDATION_ERROR", **kwargs)


# ============================================================================
# Configuration Exceptions
# ============================================================================

class ConfigurationError(UniversitySystemError):
    """Base exception for configuration errors."""
    pass


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""
    def __init__(self, config_key: str, **kwargs):
        message = f"Missing required configuration: {config_key}"
        kwargs['details'] = kwargs.get('details', {})
        kwargs['details']['config_key'] = config_key
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="CONFIG_MISSING", **kwargs)


class InvalidConfigError(ConfigurationError):
    """Configuration value is invalid."""
    def __init__(self, config_key: str, reason: Optional[str] = None, **kwargs):
        message = f"Invalid configuration for {config_key}"
        if reason:
            message += f": {reason}"
        details = kwargs.get('details', {})
        details['config_key'] = config_key
        if reason:
            details['reason'] = reason
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="CONFIG_INVALID", **kwargs)


# ============================================================================
# Export all exception classes
# ============================================================================

__all__ = [
    # Base
    'UniversitySystemError',
    # Database
    'DatabaseError',
    'DatabaseConnectionError',
    'QueryError',
    'TransactionError',
    'IntegrityError',
    # Authentication
    'AuthenticationError',
    'InvalidCredentialsError',
    'SessionExpiredError',
    'PermissionDeniedError',
    'MFARequiredError',
    # Validation
    'ValidationError',
    'InvalidInputError',
    'MissingFieldError',
    'FormatError',
    # Student
    'StudentError',
    'StudentNotFoundError',
    'DuplicateStudentError',
    'StudentEnrollmentError',
    # Course
    'CourseError',
    'CourseNotFoundError',
    'CourseFullError',
    'PrerequisiteError',
    # Enrollment
    'EnrollmentError',
    'AlreadyEnrolledError',
    'EnrollmentClosedError',
    'CapacityExceededError',
    # Grade
    'GradeError',
    'InvalidGradeError',
    'GradeNotFoundError',
    # Finance
    'FinanceError',
    'PaymentError',
    'InsufficientFundsError',
    'TransactionFailedError',
    # Email
    'EmailError',
    'EmailDeliveryError',
    'TemplateError',
    'AttachmentError',
    # File
    'FileError',
    'UniversityFileNotFoundError',
    'FileUploadError',
    'FileValidationError',
    # Configuration
    'ConfigurationError',
    'MissingConfigError',
    'InvalidConfigError',
]
