"""
Custom exception hierarchy for the university system.

DEPRECATED: This module has been moved to university_system.core.exceptions
to prevent circular imports. This file now re-exports everything from core
for backward compatibility.

New code should import from:
    from university_system.core.exceptions import DatabaseError, ...

This backward compatibility shim will be removed in a future version.
"""

# Re-export everything from core.exceptions for backward compatibility
from university_system.core.exceptions import (
    AlreadyEnrolledError,
    AttachmentError,
    AuthenticationError,
    CapacityExceededError,
    ConfigurationError,
    CourseError,
    CourseFullError,
    CourseNotFoundError,
    DatabaseConnectionError,
    DatabaseError,
    DuplicateStudentError,
    EmailDeliveryError,
    EmailError,
    EnrollmentClosedError,
    EnrollmentError,
    FileError,
    FileUploadError,
    FileValidationError,
    FinanceError,
    FormatError,
    GradeError,
    GradeNotFoundError,
    InsufficientFundsError,
    IntegrityError,
    InvalidConfigError,
    InvalidCredentialsError,
    InvalidGradeError,
    InvalidInputError,
    MFARequiredError,
    MissingConfigError,
    MissingFieldError,
    PaymentError,
    PermissionDeniedError,
    PrerequisiteError,
    QueryError,
    SessionExpiredError,
    StudentEnrollmentError,
    StudentError,
    StudentNotFoundError,
    TemplateError,
    TransactionError,
    TransactionFailedError,
    UniversityFileNotFoundError,
    UniversitySystemError,
    ValidationError,
)

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
