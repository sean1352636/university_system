"""Tests for university_system.core.exceptions."""
import pytest

from education_system.systems.university.infrastructure import exceptions as exc


class TestBaseException:
    def test_message_only(self):
        e = exc.UniversitySystemError("oops")
        assert str(e) == "oops"
        assert e.code is None
        assert e.details == {}

    def test_with_code(self):
        e = exc.UniversitySystemError("oops", code="ERR1")
        assert str(e) == "[ERR1] oops"
        assert e.code == "ERR1"

    def test_with_details(self):
        e = exc.UniversitySystemError("oops", details={"field": "x"})
        assert e.details == {"field": "x"}

    def test_to_dict(self):
        e = exc.UniversitySystemError("oops", code="C", details={"k": "v"})
        d = e.to_dict()
        assert d == {
            "error_type": "UniversitySystemError",
            "message": "oops",
            "code": "C",
            "details": {"k": "v"},
        }


class TestHierarchy:
    @pytest.mark.parametrize("cls,parent", [
        (exc.DatabaseConnectionError, exc.DatabaseError),
        (exc.QueryError, exc.DatabaseError),
        (exc.TransactionError, exc.DatabaseError),
        (exc.IntegrityError, exc.DatabaseError),
        (exc.DatabaseError, exc.UniversitySystemError),
        (exc.InvalidCredentialsError, exc.AuthenticationError),
        (exc.SessionExpiredError, exc.AuthenticationError),
        (exc.PermissionDeniedError, exc.AuthenticationError),
        (exc.MFARequiredError, exc.AuthenticationError),
        (exc.InvalidInputError, exc.ValidationError),
        (exc.MissingFieldError, exc.ValidationError),
        (exc.FormatError, exc.ValidationError),
        (exc.StudentNotFoundError, exc.StudentError),
        (exc.DuplicateStudentError, exc.StudentError),
        (exc.CourseNotFoundError, exc.CourseError),
        (exc.CourseFullError, exc.CourseError),
        (exc.PrerequisiteError, exc.CourseError),
        (exc.AlreadyEnrolledError, exc.EnrollmentError),
        (exc.EnrollmentClosedError, exc.EnrollmentError),
        (exc.CapacityExceededError, exc.EnrollmentError),
        (exc.InvalidGradeError, exc.GradeError),
        (exc.InsufficientFundsError, exc.FinanceError),
        (exc.PaymentError, exc.FinanceError),
        (exc.EmailDeliveryError, exc.EmailError),
        (exc.UniversityFileNotFoundError, exc.FileError),
        (exc.FileValidationError, exc.FileError),
        (exc.MissingConfigError, exc.ConfigurationError),
        (exc.InvalidConfigError, exc.ConfigurationError),
    ])
    def test_subclass_relationship(self, cls, parent):
        assert issubclass(cls, parent)
        assert issubclass(cls, exc.UniversitySystemError)


class TestDatabaseErrors:
    def test_connection_default_message(self):
        e = exc.DatabaseConnectionError()
        assert e.code == "DB_CONNECTION_ERROR"
        assert "Database connection failed" in e.message

    def test_query_error_captures_query(self):
        e = exc.QueryError("syntax", query="SELECT *")
        assert e.details["query"] == "SELECT *"
        assert e.code == "DB_QUERY_ERROR"


class TestAuthErrors:
    def test_invalid_credentials_default(self):
        e = exc.InvalidCredentialsError()
        assert e.code == "AUTH_INVALID_CREDENTIALS"

    def test_permission_denied_captures_resource(self):
        e = exc.PermissionDeniedError(resource="finance")
        assert e.details["resource"] == "finance"


class TestValidationErrors:
    def test_invalid_input_captures_field(self):
        e = exc.InvalidInputError("bad", field="email")
        assert e.details["field"] == "email"
        assert e.code == "VALIDATION_INVALID_INPUT"

    def test_missing_field_message(self):
        e = exc.MissingFieldError("name")
        assert "name" in e.message
        assert e.details["field"] == "name"

    def test_format_error_captures_expected(self):
        e = exc.FormatError("bad date", expected_format="YYYY-MM-DD")
        assert e.details["expected_format"] == "YYYY-MM-DD"


class TestStudentErrors:
    def test_not_found_with_id(self):
        e = exc.StudentNotFoundError(student_id="S1")
        assert "S1" in e.message
        assert e.details["student_id"] == "S1"

    def test_not_found_without_id(self):
        e = exc.StudentNotFoundError()
        assert e.message == "Student not found"
        assert "student_id" not in e.details

    def test_duplicate(self):
        e = exc.DuplicateStudentError("S1")
        assert "S1" in e.message


class TestCourseErrors:
    def test_course_not_found(self):
        e = exc.CourseNotFoundError("CS101")
        assert "CS101" in e.message
        assert e.details["course_id"] == "CS101"

    def test_prerequisite_error(self):
        e = exc.PrerequisiteError("CS201", missing_prereqs=["CS101"])
        assert e.details["missing_prerequisites"] == ["CS101"]


class TestEnrollmentErrors:
    def test_already_enrolled_message(self):
        e = exc.AlreadyEnrolledError("S1", "CS101")
        assert "S1" in e.message and "CS101" in e.message


class TestGradeErrors:
    def test_invalid_grade_captures_value(self):
        e = exc.InvalidGradeError("XYZ")
        assert e.details["grade"] == "XYZ"


class TestFinanceErrors:
    def test_insufficient_funds_captures_amounts(self):
        e = exc.InsufficientFundsError(required=100.0, available=10.0)
        assert e.details["required_amount"] == 100.0
        assert e.details["available_amount"] == 10.0


class TestEmailErrors:
    def test_delivery_error_with_reason(self):
        e = exc.EmailDeliveryError("a@x", reason="timeout")
        assert e.details["recipient"] == "a@x"
        assert e.details["reason"] == "timeout"
        assert "timeout" in e.message


class TestFileErrors:
    def test_not_found_captures_path(self):
        e = exc.UniversityFileNotFoundError("/tmp/x")
        assert e.details["file_path"] == "/tmp/x"

    def test_validation_with_filename(self):
        e = exc.FileValidationError("too big", file_name="x.pdf")
        assert e.details["file_name"] == "x.pdf"


class TestConfigErrors:
    def test_missing_config(self):
        e = exc.MissingConfigError("DB_URL")
        assert e.details["config_key"] == "DB_URL"

    def test_invalid_config_with_reason(self):
        e = exc.InvalidConfigError("DB_URL", reason="not a url")
        assert "not a url" in e.message
        assert e.details["reason"] == "not a url"


class TestI18nHelpers:
    def test_get_text_returns_string(self):
        # Either real translation or fallback returns the key
        assert isinstance(exc.get_text("some.key"), str)

    def test_underscore_alias(self):
        assert isinstance(exc._("some.key"), str)
