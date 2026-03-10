#!/usr/bin/env python3
"""
Tests for custom exception hierarchy

Tests:
- Base exception functionality
- Exception inheritance
- Error codes and messages
- Exception details
- to_dict() serialization
- All exception types
"""

import pytest

from education_system.university_system.infrastructure.exceptions import (
    # Base
    UniversitySystemError,
    # Database
    DatabaseError, DatabaseConnectionError, QueryError, TransactionError, IntegrityError,
    # Authentication
    AuthenticationError, InvalidCredentialsError, SessionExpiredError,
    PermissionDeniedError, MFARequiredError,
    # Validation
    ValidationError, InvalidInputError, MissingFieldError, FormatError,
    # Student
    StudentError, StudentNotFoundError, DuplicateStudentError, StudentEnrollmentError,
    # Course
    CourseError, CourseNotFoundError, CourseFullError, PrerequisiteError,
    # Enrollment
    EnrollmentError, AlreadyEnrolledError, EnrollmentClosedError, CapacityExceededError,
    # Grade
    GradeError, InvalidGradeError, GradeNotFoundError,
    # Finance
    FinanceError, PaymentError, InsufficientFundsError, TransactionFailedError,
    # Email
    EmailError, EmailDeliveryError, TemplateError, AttachmentError,
    # File
    FileError, UniversityFileNotFoundError, FileUploadError, FileValidationError,
    # Configuration
    ConfigurationError, MissingConfigError, InvalidConfigError,
)


# ============================================================================
# Base Exception Tests
# ============================================================================

class TestUniversitySystemError:
    """Test base exception class"""

    def test_create_basic_exception(self):
        """Test creating exception with just message"""
        exc = UniversitySystemError("Test error")

        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.code is None
        assert exc.details == {}

    def test_create_exception_with_code(self):
        """Test creating exception with error code"""
        exc = UniversitySystemError("Test error", code="TEST_001")

        assert exc.code == "TEST_001"
        assert str(exc) == "[TEST_001] Test error"

    def test_create_exception_with_details(self):
        """Test creating exception with details"""
        exc = UniversitySystemError(
            "Test error",
            details={'field': 'username', 'value': 'test'}
        )

        assert exc.details == {'field': 'username', 'value': 'test'}

    def test_to_dict(self):
        """Test serializing exception to dictionary"""
        exc = UniversitySystemError(
            "Test error",
            code="TEST_001",
            details={'key': 'value'}
        )

        result = exc.to_dict()

        assert result['error_type'] == 'UniversitySystemError'
        assert result['message'] == "Test error"
        assert result['code'] == "TEST_001"
        assert result['details'] == {'key': 'value'}


# ============================================================================
# Database Exceptions Tests
# ============================================================================

class TestDatabaseExceptions:
    """Test database exception classes"""

    def test_database_connection_error(self):
        """Test DatabaseConnectionError"""
        exc = DatabaseConnectionError()

        assert isinstance(exc, DatabaseError)
        assert isinstance(exc, UniversitySystemError)
        assert exc.code == "DB_CONNECTION_ERROR"
        assert "connection failed" in exc.message.lower()

    def test_query_error(self):
        """Test QueryError with query details"""
        exc = QueryError("Invalid SQL", query="SELECT * FROM invalid")

        assert exc.code == "DB_QUERY_ERROR"
        assert exc.details['query'] == "SELECT * FROM invalid"

    def test_transaction_error(self):
        """Test TransactionError"""
        exc = TransactionError()

        assert exc.code == "DB_TRANSACTION_ERROR"
        assert "transaction" in exc.message.lower()

    def test_integrity_error(self):
        """Test IntegrityError"""
        exc = IntegrityError("Unique constraint violated")

        assert exc.code == "DB_INTEGRITY_ERROR"


# ============================================================================
# Authentication Exceptions Tests
# ============================================================================

class TestAuthenticationExceptions:
    """Test authentication exception classes"""

    def test_invalid_credentials_error(self):
        """Test InvalidCredentialsError"""
        exc = InvalidCredentialsError()

        assert isinstance(exc, AuthenticationError)
        assert exc.code == "AUTH_INVALID_CREDENTIALS"

    def test_session_expired_error(self):
        """Test SessionExpiredError"""
        exc = SessionExpiredError()

        assert exc.code == "AUTH_SESSION_EXPIRED"
        assert "expired" in exc.message.lower()

    def test_permission_denied_error(self):
        """Test PermissionDeniedError"""
        exc = PermissionDeniedError(resource="grades")

        assert exc.code == "AUTH_PERMISSION_DENIED"
        assert exc.details['resource'] == "grades"

    def test_mfa_required_error(self):
        """Test MFARequiredError"""
        exc = MFARequiredError()

        assert exc.code == "AUTH_MFA_REQUIRED"


# ============================================================================
# Validation Exceptions Tests
# ============================================================================

class TestValidationExceptions:
    """Test validation exception classes"""

    def test_invalid_input_error(self):
        """Test InvalidInputError"""
        exc = InvalidInputError("Invalid email format", field="email")

        assert isinstance(exc, ValidationError)
        assert exc.code == "VALIDATION_INVALID_INPUT"
        assert exc.details['field'] == "email"

    def test_missing_field_error(self):
        """Test MissingFieldError"""
        exc = MissingFieldError("username")

        assert exc.code == "VALIDATION_MISSING_FIELD"
        assert "username" in exc.message
        assert exc.details['field'] == "username"

    def test_format_error(self):
        """Test FormatError"""
        exc = FormatError("Invalid date", expected_format="YYYY-MM-DD")

        assert exc.code == "VALIDATION_FORMAT_ERROR"
        assert exc.details['expected_format'] == "YYYY-MM-DD"


# ============================================================================
# Student Exceptions Tests
# ============================================================================

class TestStudentExceptions:
    """Test student exception classes"""

    def test_student_not_found_error(self):
        """Test StudentNotFoundError"""
        exc = StudentNotFoundError("S12345")

        assert isinstance(exc, StudentError)
        assert exc.code == "STUDENT_NOT_FOUND"
        assert "S12345" in exc.message
        assert exc.details['student_id'] == "S12345"

    def test_student_not_found_error_no_id(self):
        """Test StudentNotFoundError without ID"""
        exc = StudentNotFoundError()

        assert "not found" in exc.message.lower()

    def test_duplicate_student_error(self):
        """Test DuplicateStudentError"""
        exc = DuplicateStudentError("john@example.com")

        assert exc.code == "STUDENT_DUPLICATE"
        assert "john@example.com" in exc.message
        assert exc.details['identifier'] == "john@example.com"

    def test_student_enrollment_error(self):
        """Test StudentEnrollmentError"""
        exc = StudentEnrollmentError("Enrollment failed")

        assert isinstance(exc, StudentError)


# ============================================================================
# Course Exceptions Tests
# ============================================================================

class TestCourseExceptions:
    """Test course exception classes"""

    def test_course_not_found_error(self):
        """Test CourseNotFoundError"""
        exc = CourseNotFoundError("CS101")

        assert isinstance(exc, CourseError)
        assert exc.code == "COURSE_NOT_FOUND"
        assert "CS101" in exc.message

    def test_course_full_error(self):
        """Test CourseFullError"""
        exc = CourseFullError("CS101")

        assert exc.code == "COURSE_FULL"
        assert "full" in exc.message.lower()

    def test_prerequisite_error(self):
        """Test PrerequisiteError"""
        exc = PrerequisiteError("CS201", missing_prereqs=["CS101", "MATH101"])

        assert exc.code == "COURSE_PREREQUISITE_ERROR"
        assert exc.details['course_id'] == "CS201"
        assert exc.details['missing_prerequisites'] == ["CS101", "MATH101"]


# ============================================================================
# Enrollment Exceptions Tests
# ============================================================================

class TestEnrollmentExceptions:
    """Test enrollment exception classes"""

    def test_already_enrolled_error(self):
        """Test AlreadyEnrolledError"""
        exc = AlreadyEnrolledError("S12345", "CS101")

        assert isinstance(exc, EnrollmentError)
        assert exc.code == "ENROLLMENT_ALREADY_ENROLLED"
        assert "S12345" in exc.message
        assert "CS101" in exc.message

    def test_enrollment_closed_error(self):
        """Test EnrollmentClosedError"""
        exc = EnrollmentClosedError("CS101")

        assert exc.code == "ENROLLMENT_CLOSED"
        assert "closed" in exc.message.lower()

    def test_capacity_exceeded_error(self):
        """Test CapacityExceededError"""
        exc = CapacityExceededError("Maximum enrollment reached")

        assert isinstance(exc, EnrollmentError)


# ============================================================================
# Grade Exceptions Tests
# ============================================================================

class TestGradeExceptions:
    """Test grade exception classes"""

    def test_invalid_grade_error(self):
        """Test InvalidGradeError"""
        exc = InvalidGradeError("Z")

        assert isinstance(exc, GradeError)
        assert exc.code == "GRADE_INVALID"
        assert exc.details['grade'] == "Z"

    def test_grade_not_found_error(self):
        """Test GradeNotFoundError"""
        exc = GradeNotFoundError("Grade record not found")

        assert isinstance(exc, GradeError)


# ============================================================================
# Finance Exceptions Tests
# ============================================================================

class TestFinanceExceptions:
    """Test finance exception classes"""

    def test_payment_error(self):
        """Test PaymentError"""
        exc = PaymentError("Payment gateway timeout")

        assert isinstance(exc, FinanceError)

    def test_insufficient_funds_error(self):
        """Test InsufficientFundsError"""
        exc = InsufficientFundsError(required=1000.00, available=500.00)

        assert exc.code == "FINANCE_INSUFFICIENT_FUNDS"
        assert exc.details['required_amount'] == 1000.00
        assert exc.details['available_amount'] == 500.00
        assert "1000" in exc.message

    def test_transaction_failed_error(self):
        """Test TransactionFailedError"""
        exc = TransactionFailedError("Transaction rollback")

        assert isinstance(exc, FinanceError)


# ============================================================================
# Email Exceptions Tests
# ============================================================================

class TestEmailExceptions:
    """Test email exception classes"""

    def test_email_delivery_error(self):
        """Test EmailDeliveryError"""
        exc = EmailDeliveryError("test@example.com", reason="Invalid recipient")

        assert isinstance(exc, EmailError)
        assert exc.code == "EMAIL_DELIVERY_ERROR"
        assert "test@example.com" in exc.message
        assert exc.details['recipient'] == "test@example.com"
        assert exc.details['reason'] == "Invalid recipient"

    def test_template_error(self):
        """Test TemplateError"""
        exc = TemplateError("Template not found")

        assert isinstance(exc, EmailError)

    def test_attachment_error(self):
        """Test AttachmentError"""
        exc = AttachmentError("File too large")

        assert isinstance(exc, EmailError)


# ============================================================================
# File Exceptions Tests
# ============================================================================

class TestFileExceptions:
    """Test file exception classes"""

    def test_university_file_not_found_error(self):
        """Test UniversityFileNotFoundError"""
        exc = UniversityFileNotFoundError("/path/to/file.txt")

        assert isinstance(exc, FileError)
        assert exc.code == "FILE_NOT_FOUND"
        assert "/path/to/file.txt" in exc.message
        assert exc.details['file_path'] == "/path/to/file.txt"

    def test_file_upload_error(self):
        """Test FileUploadError"""
        exc = FileUploadError("Upload failed")

        assert isinstance(exc, FileError)

    def test_file_validation_error(self):
        """Test FileValidationError"""
        exc = FileValidationError("Invalid file type", file_name="document.exe")

        assert exc.code == "FILE_VALIDATION_ERROR"
        assert exc.details['file_name'] == "document.exe"


# ============================================================================
# Configuration Exceptions Tests
# ============================================================================

class TestConfigurationExceptions:
    """Test configuration exception classes"""

    def test_missing_config_error(self):
        """Test MissingConfigError"""
        exc = MissingConfigError("DATABASE_URL")

        assert isinstance(exc, ConfigurationError)
        assert exc.code == "CONFIG_MISSING"
        assert "DATABASE_URL" in exc.message
        assert exc.details['config_key'] == "DATABASE_URL"

    def test_invalid_config_error(self):
        """Test InvalidConfigError"""
        exc = InvalidConfigError("PORT", reason="Must be between 1-65535")

        assert exc.code == "CONFIG_INVALID"
        assert "PORT" in exc.message
        assert exc.details['config_key'] == "PORT"
        assert exc.details['reason'] == "Must be between 1-65535"


# ============================================================================
# Inheritance Tests
# ============================================================================

class TestExceptionInheritance:
    """Test exception inheritance hierarchy"""

    def test_database_error_inherits_from_base(self):
        """Test DatabaseError inherits from UniversitySystemError"""
        exc = DatabaseError("Test")

        assert isinstance(exc, UniversitySystemError)

    def test_authentication_error_inherits_from_base(self):
        """Test AuthenticationError inherits from UniversitySystemError"""
        exc = AuthenticationError("Test")

        assert isinstance(exc, UniversitySystemError)

    def test_validation_error_inherits_from_base(self):
        """Test ValidationError inherits from UniversitySystemError"""
        exc = ValidationError("Test")

        assert isinstance(exc, UniversitySystemError)

    def test_specific_exceptions_inherit_from_category(self):
        """Test specific exceptions inherit from their category"""
        assert isinstance(InvalidCredentialsError(), AuthenticationError)
        assert isinstance(InvalidInputError("test"), ValidationError)
        assert isinstance(StudentNotFoundError(), StudentError)
        assert isinstance(CourseFullError(), CourseError)


# ============================================================================
# Exception Catching Tests
# ============================================================================

class TestExceptionCatching:
    """Test catching exceptions at different levels"""

    def test_catch_base_exception(self):
        """Test catching any university system exception"""
        try:
            raise StudentNotFoundError("S123")
        except UniversitySystemError as e:
            assert e.code == "STUDENT_NOT_FOUND"

    def test_catch_category_exception(self):
        """Test catching by category"""
        try:
            raise InvalidCredentialsError()
        except AuthenticationError as e:
            assert e.code == "AUTH_INVALID_CREDENTIALS"

    def test_catch_specific_exception(self):
        """Test catching specific exception"""
        try:
            raise CourseFullError("CS101")
        except CourseFullError as e:
            assert "full" in str(e).lower()

    def test_multiple_exception_types(self):
        """Test catching multiple exception types"""
        def raise_various_exceptions(error_type):
            if error_type == "auth":
                raise InvalidCredentialsError()
            elif error_type == "validation":
                raise MissingFieldError("email")
            elif error_type == "database":
                raise QueryError("Bad query")

        # Catch all with base exception
        for error_type in ["auth", "validation", "database"]:
            try:
                raise_various_exceptions(error_type)
            except UniversitySystemError as e:
                assert e.code is not None


# ============================================================================
# Exception Raising Tests
# ============================================================================

class TestExceptionRaising:
    """Test raising and handling exceptions"""

    def test_raise_and_catch(self):
        """Test raising and catching exception"""
        with pytest.raises(StudentNotFoundError) as exc_info:
            raise StudentNotFoundError("S12345")

        assert "S12345" in str(exc_info.value)

    def test_reraise_exception(self):
        """Test re-raising exception"""
        with pytest.raises(DatabaseConnectionError):
            try:
                raise DatabaseConnectionError()
            except DatabaseError:
                # Do something
                raise  # Re-raise

    def test_exception_context(self):
        """Test exception with context"""
        try:
            try:
                raise ValueError("Original error")
            except ValueError:
                raise DatabaseError("Database failed") from None
        except DatabaseError as e:
            assert "Database failed" in str(e)


# ============================================================================
# Serialization Tests
# ============================================================================

class TestExceptionSerialization:
    """Test exception serialization"""

    def test_to_dict_complete(self):
        """Test complete to_dict serialization"""
        exc = InvalidGradeError("F+", details={'student_id': 'S123'})

        result = exc.to_dict()

        assert result['error_type'] == 'InvalidGradeError'
        assert result['message'] is not None
        assert result['code'] == 'GRADE_INVALID'
        assert 'grade' in result['details']

    def test_to_dict_minimal(self):
        """Test to_dict with minimal information"""
        exc = UniversitySystemError("Simple error")

        result = exc.to_dict()

        assert result['error_type'] == 'UniversitySystemError'
        assert result['message'] == "Simple error"
        assert result['code'] is None
        assert result['details'] == {}


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestExceptionEdgeCases:
    """Test exception edge cases"""

    def test_empty_message(self):
        """Test exception with empty message"""
        exc = UniversitySystemError("")

        assert str(exc) == ""

    def test_none_details(self):
        """Test exception with None details"""
        exc = UniversitySystemError("Test", details=None)

        assert exc.details == {}

    def test_complex_details(self):
        """Test exception with complex details"""
        exc = UniversitySystemError(
            "Test",
            details={
                'nested': {
                    'key': 'value'
                },
                'list': [1, 2, 3],
                'number': 42
            }
        )

        assert exc.details['nested']['key'] == 'value'
        assert exc.details['list'] == [1, 2, 3]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
