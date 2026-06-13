"""Comprehensive tests for university_system.core.exceptions module.

Tests the full exception hierarchy, lazy i18n loading, base class behavior,
and all 40+ custom exception classes.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Lazy i18n helpers
# ---------------------------------------------------------------------------

class TestLazyI18n:
    """Tests for the lazy i18n loading mechanism in exceptions module."""

    def test_load_i18n_success(self):
        """Test that _load_i18n successfully loads i18n functions."""
        import education_system.university_system.core.exceptions as exc_mod

        # Reset state so we force a re-load
        exc_mod._i18n_loaded = False
        exc_mod._get_text_func = None
        exc_mod._translate_func = None

        exc_mod._load_i18n()

        assert exc_mod._i18n_loaded is True
        assert exc_mod._get_text_func is not None
        assert exc_mod._translate_func is not None

    def test_load_i18n_import_error_uses_fallback(self):
        """Test that _load_i18n falls back gracefully if i18n module is not available."""
        import education_system.university_system.core.exceptions as exc_mod

        # Reset state
        exc_mod._i18n_loaded = False
        exc_mod._get_text_func = None
        exc_mod._translate_func = None

        with patch.dict('sys.modules', {'university_system.core.i18n': None}):
            exc_mod._load_i18n()

        assert exc_mod._i18n_loaded is True
        # Fallback functions should be set
        assert exc_mod._get_text_func is not None
        assert exc_mod._translate_func is not None

        # Fallback returns key when no default
        result = exc_mod._get_text_func("some_key")
        assert result == "some_key"

        # Fallback returns default when provided
        result = exc_mod._get_text_func("some_key", default="fallback_value")
        assert result == "fallback_value"

    def test_load_i18n_only_runs_once(self):
        """Test that _load_i18n is idempotent after first successful load."""
        import education_system.university_system.core.exceptions as exc_mod

        # Force first load
        exc_mod._i18n_loaded = False
        exc_mod._load_i18n()

        func_after_first = exc_mod._get_text_func

        # Call again - should be a no-op
        exc_mod._load_i18n()
        assert exc_mod._get_text_func is func_after_first

    def test_get_text_delegates_to_loaded_func(self):
        """Test that module-level get_text calls _load_i18n and delegates."""
        import education_system.university_system.core.exceptions as exc_mod

        # Reset state
        exc_mod._i18n_loaded = False
        mock_func = MagicMock(return_value="translated")
        exc_mod._get_text_func = None

        with patch.object(exc_mod, '_load_i18n') as mock_load:
            def side_effect():
                exc_mod._i18n_loaded = True
                exc_mod._get_text_func = mock_func
            mock_load.side_effect = side_effect

            result = exc_mod.get_text("key", default="d")
            mock_load.assert_called_once()
            mock_func.assert_called_once_with("key", default="d")
            assert result == "translated"

    def test_underscore_func_delegates_to_translate_func(self):
        """Test that module-level _ calls _load_i18n and delegates."""
        import education_system.university_system.core.exceptions as exc_mod

        exc_mod._i18n_loaded = False
        mock_func = MagicMock(return_value="translated_2")
        exc_mod._translate_func = None

        with patch.object(exc_mod, '_load_i18n') as mock_load:
            def side_effect():
                exc_mod._i18n_loaded = True
                exc_mod._translate_func = mock_func
            mock_load.side_effect = side_effect

            result = exc_mod._("key2", name="test")
            mock_load.assert_called_once()
            mock_func.assert_called_once_with("key2", name="test")
            assert result == "translated_2"


# ---------------------------------------------------------------------------
# Base Exception class
# ---------------------------------------------------------------------------

class TestUniversitySystemError:
    """Tests for the base UniversitySystemError class."""

    def test_basic_construction(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        err = UniversitySystemError("Something went wrong")
        assert err.message == "Something went wrong"
        assert err.code is None
        assert err.details == {}
        assert str(err) == "Something went wrong"

    def test_construction_with_code(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        err = UniversitySystemError("Bad request", code="ERR_400")
        assert err.message == "Bad request"
        assert err.code == "ERR_400"
        assert str(err) == "[ERR_400] Bad request"

    def test_construction_with_details(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        details = {"field": "email", "reason": "invalid"}
        err = UniversitySystemError("Validation failed", details=details)
        assert err.details == details
        assert err.details["field"] == "email"

    def test_details_defaults_to_empty_dict(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        err = UniversitySystemError("msg", details=None)
        assert err.details == {}

    def test_to_dict(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        err = UniversitySystemError("test msg", code="T001", details={"k": "v"})
        d = err.to_dict()
        assert d == {
            'error_type': 'UniversitySystemError',
            'message': 'test msg',
            'code': 'T001',
            'details': {'k': 'v'},
        }

    def test_to_dict_subclass_name(self):
        """to_dict should use the actual subclass name, not the base name."""
        from education_system.university_system.core.exceptions import DatabaseError

        err = DatabaseError("db fail", code="DB")
        d = err.to_dict()
        assert d['error_type'] == 'DatabaseError'

    def test_is_exception(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        err = UniversitySystemError("x")
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        with pytest.raises(UniversitySystemError) as exc_info:
            raise UniversitySystemError("boom", code="X")
        assert "boom" in str(exc_info.value)

    def test_str_without_code(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        err = UniversitySystemError("no code here")
        assert str(err) == "no code here"

    def test_str_with_code(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        err = UniversitySystemError("with code", code="ABC")
        assert str(err) == "[ABC] with code"


# ---------------------------------------------------------------------------
# Database Exceptions
# ---------------------------------------------------------------------------

class TestDatabaseExceptions:
    """Tests for database-related exception classes."""

    def test_database_error_is_university_error(self):
        from education_system.university_system.core.exceptions import DatabaseError, UniversitySystemError

        err = DatabaseError("db fail")
        assert isinstance(err, UniversitySystemError)

    def test_database_connection_error_defaults(self):
        from education_system.university_system.core.exceptions import DatabaseConnectionError

        err = DatabaseConnectionError()
        assert err.message == "Database connection failed"
        assert err.code == "DB_CONNECTION_ERROR"

    def test_database_connection_error_custom_message(self):
        from education_system.university_system.core.exceptions import DatabaseConnectionError

        err = DatabaseConnectionError("Cannot reach MySQL server")
        assert err.message == "Cannot reach MySQL server"
        assert err.code == "DB_CONNECTION_ERROR"

    def test_database_connection_error_code_kwarg_stripped(self):
        """Passing code= in kwargs should be silently ignored (popped)."""
        from education_system.university_system.core.exceptions import DatabaseConnectionError

        err = DatabaseConnectionError("fail", code="CUSTOM")
        assert err.code == "DB_CONNECTION_ERROR"  # always forced

    def test_query_error(self):
        from education_system.university_system.core.exceptions import QueryError

        err = QueryError("Syntax error", query="SELECT * FORM users")
        assert err.message == "Syntax error"
        assert err.code == "DB_QUERY_ERROR"
        assert err.details['query'] == "SELECT * FORM users"

    def test_query_error_without_query(self):
        from education_system.university_system.core.exceptions import QueryError

        err = QueryError("query failed")
        assert err.code == "DB_QUERY_ERROR"
        assert 'query' not in err.details

    def test_transaction_error_defaults(self):
        from education_system.university_system.core.exceptions import TransactionError

        err = TransactionError()
        assert err.message == "Transaction failed"
        assert err.code == "DB_TRANSACTION_ERROR"

    def test_transaction_error_custom(self):
        from education_system.university_system.core.exceptions import TransactionError

        err = TransactionError("Rollback needed")
        assert err.message == "Rollback needed"

    def test_integrity_error_defaults(self):
        from education_system.university_system.core.exceptions import IntegrityError

        err = IntegrityError()
        assert err.message == "Integrity constraint violated"
        assert err.code == "DB_INTEGRITY_ERROR"

    def test_integrity_error_custom(self):
        from education_system.university_system.core.exceptions import IntegrityError

        err = IntegrityError("Unique constraint on email")
        assert err.message == "Unique constraint on email"

    def test_database_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            DatabaseError, DatabaseConnectionError, QueryError,
            TransactionError, IntegrityError
        )

        assert issubclass(DatabaseConnectionError, DatabaseError)
        assert issubclass(QueryError, DatabaseError)
        assert issubclass(TransactionError, DatabaseError)
        assert issubclass(IntegrityError, DatabaseError)


# ---------------------------------------------------------------------------
# Authentication Exceptions
# ---------------------------------------------------------------------------

class TestAuthenticationExceptions:
    """Tests for authentication-related exception classes."""

    def test_authentication_error_base(self):
        from education_system.university_system.core.exceptions import AuthenticationError, UniversitySystemError

        err = AuthenticationError("auth fail")
        assert isinstance(err, UniversitySystemError)

    def test_invalid_credentials_error_defaults(self):
        from education_system.university_system.core.exceptions import InvalidCredentialsError

        err = InvalidCredentialsError()
        assert err.message == "Invalid credentials"
        assert err.code == "AUTH_INVALID_CREDENTIALS"

    def test_invalid_credentials_error_custom(self):
        from education_system.university_system.core.exceptions import InvalidCredentialsError

        err = InvalidCredentialsError("Wrong password")
        assert err.message == "Wrong password"

    def test_session_expired_error_defaults(self):
        from education_system.university_system.core.exceptions import SessionExpiredError

        err = SessionExpiredError()
        assert err.message == "Session expired"
        assert err.code == "AUTH_SESSION_EXPIRED"

    def test_permission_denied_error_without_resource(self):
        from education_system.university_system.core.exceptions import PermissionDeniedError

        err = PermissionDeniedError()
        assert err.message == "Permission denied"
        assert err.code == "AUTH_PERMISSION_DENIED"
        assert 'resource' not in err.details

    def test_permission_denied_error_with_resource(self):
        from education_system.university_system.core.exceptions import PermissionDeniedError

        err = PermissionDeniedError("No access", resource="/admin/panel")
        assert err.details['resource'] == "/admin/panel"
        assert err.message == "No access"

    def test_mfa_required_error_defaults(self):
        from education_system.university_system.core.exceptions import MFARequiredError

        err = MFARequiredError()
        assert err.message == "MFA required"
        assert err.code == "AUTH_MFA_REQUIRED"

    def test_auth_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            AuthenticationError, InvalidCredentialsError,
            SessionExpiredError, PermissionDeniedError, MFARequiredError
        )

        assert issubclass(InvalidCredentialsError, AuthenticationError)
        assert issubclass(SessionExpiredError, AuthenticationError)
        assert issubclass(PermissionDeniedError, AuthenticationError)
        assert issubclass(MFARequiredError, AuthenticationError)


# ---------------------------------------------------------------------------
# Validation Exceptions
# ---------------------------------------------------------------------------

class TestValidationExceptions:
    """Tests for validation-related exception classes."""

    def test_validation_error_base(self):
        from education_system.university_system.core.exceptions import ValidationError, UniversitySystemError

        err = ValidationError("invalid")
        assert isinstance(err, UniversitySystemError)

    def test_invalid_input_error_with_field(self):
        from education_system.university_system.core.exceptions import InvalidInputError

        err = InvalidInputError("Bad email format", field="email")
        assert err.code == "VALIDATION_INVALID_INPUT"
        assert err.details['field'] == "email"

    def test_invalid_input_error_without_field(self):
        from education_system.university_system.core.exceptions import InvalidInputError

        err = InvalidInputError("Bad data")
        assert err.code == "VALIDATION_INVALID_INPUT"
        assert 'field' not in err.details

    def test_missing_field_error(self):
        from education_system.university_system.core.exceptions import MissingFieldError

        err = MissingFieldError("username")
        assert err.message == "Required field missing: username"
        assert err.code == "VALIDATION_MISSING_FIELD"
        assert err.details['field'] == "username"

    def test_format_error_with_expected(self):
        from education_system.university_system.core.exceptions import FormatError

        err = FormatError("Invalid date", expected_format="YYYY-MM-DD")
        assert err.code == "VALIDATION_FORMAT_ERROR"
        assert err.details['expected_format'] == "YYYY-MM-DD"

    def test_format_error_without_expected(self):
        from education_system.university_system.core.exceptions import FormatError

        err = FormatError("Bad format")
        assert err.code == "VALIDATION_FORMAT_ERROR"
        assert 'expected_format' not in err.details

    def test_validation_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            ValidationError, InvalidInputError, MissingFieldError, FormatError
        )

        assert issubclass(InvalidInputError, ValidationError)
        assert issubclass(MissingFieldError, ValidationError)
        assert issubclass(FormatError, ValidationError)


# ---------------------------------------------------------------------------
# Student Exceptions
# ---------------------------------------------------------------------------

class TestStudentExceptions:
    """Tests for student-related exception classes."""

    def test_student_error_base(self):
        from education_system.university_system.core.exceptions import StudentError, UniversitySystemError

        err = StudentError("student err")
        assert isinstance(err, UniversitySystemError)

    def test_student_not_found_with_id(self):
        from education_system.university_system.core.exceptions import StudentNotFoundError

        err = StudentNotFoundError("S12345")
        assert err.message == "Student not found: S12345"
        assert err.code == "STUDENT_NOT_FOUND"
        assert err.details['student_id'] == "S12345"

    def test_student_not_found_without_id(self):
        from education_system.university_system.core.exceptions import StudentNotFoundError

        err = StudentNotFoundError()
        assert err.message == "Student not found"
        assert err.code == "STUDENT_NOT_FOUND"

    def test_duplicate_student_error(self):
        from education_system.university_system.core.exceptions import DuplicateStudentError

        err = DuplicateStudentError("jdoe@uni.edu")
        assert err.message == "Student already exists: jdoe@uni.edu"
        assert err.code == "STUDENT_DUPLICATE"
        assert err.details['identifier'] == "jdoe@uni.edu"

    def test_student_enrollment_error(self):
        from education_system.university_system.core.exceptions import StudentEnrollmentError, StudentError

        err = StudentEnrollmentError("Cannot enroll")
        assert isinstance(err, StudentError)

    def test_student_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            StudentError, StudentNotFoundError, DuplicateStudentError,
            StudentEnrollmentError
        )

        assert issubclass(StudentNotFoundError, StudentError)
        assert issubclass(DuplicateStudentError, StudentError)
        assert issubclass(StudentEnrollmentError, StudentError)


# ---------------------------------------------------------------------------
# Course Exceptions
# ---------------------------------------------------------------------------

class TestCourseExceptions:
    """Tests for course-related exception classes."""

    def test_course_error_base(self):
        from education_system.university_system.core.exceptions import CourseError, UniversitySystemError

        err = CourseError("course err")
        assert isinstance(err, UniversitySystemError)

    def test_course_not_found_with_id(self):
        from education_system.university_system.core.exceptions import CourseNotFoundError

        err = CourseNotFoundError("CS101")
        assert err.message == "Course not found: CS101"
        assert err.code == "COURSE_NOT_FOUND"
        assert err.details['course_id'] == "CS101"

    def test_course_not_found_without_id(self):
        from education_system.university_system.core.exceptions import CourseNotFoundError

        err = CourseNotFoundError()
        assert err.message == "Course not found"
        assert err.code == "COURSE_NOT_FOUND"

    def test_course_full_with_id(self):
        from education_system.university_system.core.exceptions import CourseFullError

        err = CourseFullError("CS102")
        assert err.message == "Course is full: CS102"
        assert err.code == "COURSE_FULL"

    def test_course_full_without_id(self):
        from education_system.university_system.core.exceptions import CourseFullError

        err = CourseFullError()
        assert err.message == "Course is full"
        assert err.code == "COURSE_FULL"

    def test_prerequisite_error_with_missing(self):
        from education_system.university_system.core.exceptions import PrerequisiteError

        err = PrerequisiteError("CS201", missing_prereqs=["CS101", "CS102"])
        assert err.message == "Prerequisites not met for course: CS201"
        assert err.code == "COURSE_PREREQUISITE_ERROR"
        assert err.details['course_id'] == "CS201"
        assert err.details['missing_prerequisites'] == ["CS101", "CS102"]

    def test_prerequisite_error_without_missing(self):
        from education_system.university_system.core.exceptions import PrerequisiteError

        err = PrerequisiteError("CS201")
        assert err.details['course_id'] == "CS201"
        assert 'missing_prerequisites' not in err.details

    def test_course_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            CourseError, CourseNotFoundError, CourseFullError, PrerequisiteError
        )

        assert issubclass(CourseNotFoundError, CourseError)
        assert issubclass(CourseFullError, CourseError)
        assert issubclass(PrerequisiteError, CourseError)


# ---------------------------------------------------------------------------
# Enrollment Exceptions
# ---------------------------------------------------------------------------

class TestEnrollmentExceptions:
    """Tests for enrollment-related exception classes."""

    def test_enrollment_error_base(self):
        from education_system.university_system.core.exceptions import EnrollmentError, UniversitySystemError

        err = EnrollmentError("enroll err")
        assert isinstance(err, UniversitySystemError)

    def test_already_enrolled_error(self):
        from education_system.university_system.core.exceptions import AlreadyEnrolledError

        err = AlreadyEnrolledError("S001", "CS101")
        assert "S001" in err.message
        assert "CS101" in err.message
        assert err.code == "ENROLLMENT_ALREADY_ENROLLED"

    def test_enrollment_closed_with_course(self):
        from education_system.university_system.core.exceptions import EnrollmentClosedError

        err = EnrollmentClosedError("CS101")
        assert err.message == "Enrollment closed for course: CS101"
        assert err.code == "ENROLLMENT_CLOSED"

    def test_enrollment_closed_without_course(self):
        from education_system.university_system.core.exceptions import EnrollmentClosedError

        err = EnrollmentClosedError()
        assert err.message == "Enrollment closed"
        assert err.code == "ENROLLMENT_CLOSED"

    def test_capacity_exceeded_error(self):
        from education_system.university_system.core.exceptions import CapacityExceededError, EnrollmentError

        err = CapacityExceededError("Capacity exceeded")
        assert isinstance(err, EnrollmentError)

    def test_enrollment_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            EnrollmentError, AlreadyEnrolledError, EnrollmentClosedError,
            CapacityExceededError
        )

        assert issubclass(AlreadyEnrolledError, EnrollmentError)
        assert issubclass(EnrollmentClosedError, EnrollmentError)
        assert issubclass(CapacityExceededError, EnrollmentError)


# ---------------------------------------------------------------------------
# Grade Exceptions
# ---------------------------------------------------------------------------

class TestGradeExceptions:
    """Tests for grade-related exception classes."""

    def test_grade_error_base(self):
        from education_system.university_system.core.exceptions import GradeError, UniversitySystemError

        err = GradeError("grade err")
        assert isinstance(err, UniversitySystemError)

    def test_invalid_grade_error(self):
        from education_system.university_system.core.exceptions import InvalidGradeError

        err = InvalidGradeError("Z+")
        assert err.message == "Invalid grade: Z+"
        assert err.code == "GRADE_INVALID"
        assert err.details['grade'] == "Z+"

    def test_invalid_grade_error_numeric(self):
        from education_system.university_system.core.exceptions import InvalidGradeError

        err = InvalidGradeError(150)
        assert err.message == "Invalid grade: 150"
        assert err.details['grade'] == 150

    def test_grade_not_found_error(self):
        from education_system.university_system.core.exceptions import GradeNotFoundError, GradeError

        err = GradeNotFoundError("Grade not found")
        assert isinstance(err, GradeError)

    def test_grade_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            GradeError, InvalidGradeError, GradeNotFoundError
        )

        assert issubclass(InvalidGradeError, GradeError)
        assert issubclass(GradeNotFoundError, GradeError)


# ---------------------------------------------------------------------------
# Finance Exceptions
# ---------------------------------------------------------------------------

class TestFinanceExceptions:
    """Tests for finance-related exception classes."""

    def test_finance_error_base(self):
        from education_system.university_system.core.exceptions import FinanceError, UniversitySystemError

        err = FinanceError("finance err")
        assert isinstance(err, UniversitySystemError)

    def test_payment_error(self):
        from education_system.university_system.core.exceptions import PaymentError, FinanceError

        err = PaymentError("Payment declined")
        assert isinstance(err, FinanceError)

    def test_insufficient_funds_error(self):
        from education_system.university_system.core.exceptions import InsufficientFundsError

        err = InsufficientFundsError(required=500.0, available=100.0)
        assert "500.0" in err.message
        assert "100.0" in err.message
        assert err.code == "FINANCE_INSUFFICIENT_FUNDS"
        assert err.details['required_amount'] == 500.0
        assert err.details['available_amount'] == 100.0

    def test_transaction_failed_error(self):
        from education_system.university_system.core.exceptions import TransactionFailedError, FinanceError

        err = TransactionFailedError("tx fail")
        assert isinstance(err, FinanceError)

    def test_finance_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            FinanceError, PaymentError, InsufficientFundsError,
            TransactionFailedError
        )

        assert issubclass(PaymentError, FinanceError)
        assert issubclass(InsufficientFundsError, FinanceError)
        assert issubclass(TransactionFailedError, FinanceError)


# ---------------------------------------------------------------------------
# Email Exceptions
# ---------------------------------------------------------------------------

class TestEmailExceptions:
    """Tests for email-related exception classes."""

    def test_email_error_base(self):
        from education_system.university_system.core.exceptions import EmailError, UniversitySystemError

        err = EmailError("email err")
        assert isinstance(err, UniversitySystemError)

    def test_email_delivery_error_with_reason(self):
        from education_system.university_system.core.exceptions import EmailDeliveryError

        err = EmailDeliveryError("user@test.com", reason="mailbox full")
        assert "user@test.com" in err.message
        assert "mailbox full" in err.message
        assert err.code == "EMAIL_DELIVERY_ERROR"
        assert err.details['recipient'] == "user@test.com"
        assert err.details['reason'] == "mailbox full"

    def test_email_delivery_error_without_reason(self):
        from education_system.university_system.core.exceptions import EmailDeliveryError

        err = EmailDeliveryError("user@test.com")
        assert "user@test.com" in err.message
        assert err.code == "EMAIL_DELIVERY_ERROR"
        assert err.details['recipient'] == "user@test.com"
        assert 'reason' not in err.details

    def test_template_error(self):
        from education_system.university_system.core.exceptions import TemplateError, EmailError

        err = TemplateError("Bad template")
        assert isinstance(err, EmailError)

    def test_attachment_error(self):
        from education_system.university_system.core.exceptions import AttachmentError, EmailError

        err = AttachmentError("File too large")
        assert isinstance(err, EmailError)

    def test_email_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            EmailError, EmailDeliveryError, TemplateError, AttachmentError
        )

        assert issubclass(EmailDeliveryError, EmailError)
        assert issubclass(TemplateError, EmailError)
        assert issubclass(AttachmentError, EmailError)


# ---------------------------------------------------------------------------
# File Exceptions
# ---------------------------------------------------------------------------

class TestFileExceptions:
    """Tests for file-related exception classes."""

    def test_file_error_base(self):
        from education_system.university_system.core.exceptions import FileError, UniversitySystemError

        err = FileError("file err")
        assert isinstance(err, UniversitySystemError)

    def test_university_file_not_found_error(self):
        from education_system.university_system.core.exceptions import UniversityFileNotFoundError

        err = UniversityFileNotFoundError("/path/to/file.txt")
        assert err.message == "File not found: /path/to/file.txt"
        assert err.code == "FILE_NOT_FOUND"
        assert err.details['file_path'] == "/path/to/file.txt"

    def test_file_upload_error(self):
        from education_system.university_system.core.exceptions import FileUploadError, FileError

        err = FileUploadError("Upload failed")
        assert isinstance(err, FileError)

    def test_file_validation_error_with_filename(self):
        from education_system.university_system.core.exceptions import FileValidationError

        err = FileValidationError("Invalid file type", file_name="malware.exe")
        assert err.code == "FILE_VALIDATION_ERROR"
        assert err.details['file_name'] == "malware.exe"

    def test_file_validation_error_without_filename(self):
        from education_system.university_system.core.exceptions import FileValidationError

        err = FileValidationError("File too large")
        assert err.code == "FILE_VALIDATION_ERROR"
        assert 'file_name' not in err.details

    def test_file_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            FileError, UniversityFileNotFoundError, FileUploadError,
            FileValidationError
        )

        assert issubclass(UniversityFileNotFoundError, FileError)
        assert issubclass(FileUploadError, FileError)
        assert issubclass(FileValidationError, FileError)


# ---------------------------------------------------------------------------
# Configuration Exceptions
# ---------------------------------------------------------------------------

class TestConfigurationExceptions:
    """Tests for configuration-related exception classes."""

    def test_configuration_error_base(self):
        from education_system.university_system.core.exceptions import ConfigurationError, UniversitySystemError

        err = ConfigurationError("config err")
        assert isinstance(err, UniversitySystemError)

    def test_missing_config_error(self):
        from education_system.university_system.core.exceptions import MissingConfigError

        err = MissingConfigError("DATABASE_URL")
        assert err.message == "Missing required configuration: DATABASE_URL"
        assert err.code == "CONFIG_MISSING"
        assert err.details['config_key'] == "DATABASE_URL"

    def test_invalid_config_error_with_reason(self):
        from education_system.university_system.core.exceptions import InvalidConfigError

        err = InvalidConfigError("PORT", reason="must be an integer")
        assert "PORT" in err.message
        assert "must be an integer" in err.message
        assert err.code == "CONFIG_INVALID"
        assert err.details['config_key'] == "PORT"
        assert err.details['reason'] == "must be an integer"

    def test_invalid_config_error_without_reason(self):
        from education_system.university_system.core.exceptions import InvalidConfigError

        err = InvalidConfigError("PORT")
        assert err.message == "Invalid configuration for PORT"
        assert err.code == "CONFIG_INVALID"
        assert err.details['config_key'] == "PORT"
        assert 'reason' not in err.details

    def test_config_hierarchy(self):
        from education_system.university_system.core.exceptions import (
            ConfigurationError, MissingConfigError, InvalidConfigError
        )

        assert issubclass(MissingConfigError, ConfigurationError)
        assert issubclass(InvalidConfigError, ConfigurationError)


# ---------------------------------------------------------------------------
# Cross-cutting / __all__ / catch-all tests
# ---------------------------------------------------------------------------

class TestExceptionsCrossCutting:
    """Cross-cutting tests for the exceptions module."""

    def test_all_exports_are_importable(self):
        """Every name listed in __all__ should be importable."""
        from education_system.university_system.core import exceptions

        for name in exceptions.__all__:
            assert hasattr(exceptions, name), f"{name} listed in __all__ but not found"

    def test_all_exceptions_catchable_as_base(self):
        """All custom exceptions should be catchable as UniversitySystemError."""
        from education_system.university_system.core.exceptions import (
            UniversitySystemError, DatabaseConnectionError,
            InvalidCredentialsError, MissingFieldError,
            StudentNotFoundError, CourseFullError,
            AlreadyEnrolledError, InvalidGradeError,
            PaymentError, EmailDeliveryError,
            UniversityFileNotFoundError, MissingConfigError,
        )

        exceptions_to_test = [
            DatabaseConnectionError(),
            InvalidCredentialsError(),
            MissingFieldError("f"),
            StudentNotFoundError(),
            CourseFullError(),
            AlreadyEnrolledError("s", "c"),
            InvalidGradeError("X"),
            PaymentError("p"),
            EmailDeliveryError("a@b.c"),
            UniversityFileNotFoundError("/p"),
            MissingConfigError("k"),
        ]

        for exc in exceptions_to_test:
            assert isinstance(exc, UniversitySystemError), \
                f"{type(exc).__name__} is not a UniversitySystemError"

    def test_to_dict_includes_correct_types_for_all(self):
        """to_dict should always include the correct error_type for each class."""
        from education_system.university_system.core.exceptions import (
            DatabaseConnectionError, InvalidCredentialsError,
            MissingFieldError, StudentNotFoundError,
            InsufficientFundsError, EmailDeliveryError,
        )

        cases = [
            (DatabaseConnectionError(), "DatabaseConnectionError"),
            (InvalidCredentialsError(), "InvalidCredentialsError"),
            (MissingFieldError("x"), "MissingFieldError"),
            (StudentNotFoundError("S1"), "StudentNotFoundError"),
            (InsufficientFundsError(100, 50), "InsufficientFundsError"),
            (EmailDeliveryError("a@b.c"), "EmailDeliveryError"),
        ]

        for exc, expected_type in cases:
            d = exc.to_dict()
            assert d['error_type'] == expected_type

    def test_exception_with_empty_string_message(self):
        from education_system.university_system.core.exceptions import UniversitySystemError

        err = UniversitySystemError("")
        assert err.message == ""
        assert str(err) == ""

    def test_exception_details_mutability(self):
        """Details dict should be independent per instance."""
        from education_system.university_system.core.exceptions import UniversitySystemError

        err1 = UniversitySystemError("a")
        err2 = UniversitySystemError("b")
        err1.details['key'] = 'val'
        assert 'key' not in err2.details
