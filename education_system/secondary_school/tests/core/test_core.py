"""Tests for core modules: defaults, exceptions, logs, paths, sql_safety."""

import logging
import os

import pytest


class TestDefaults:
    """Tests for core.defaults configuration values."""

    def test_api_host_default(self):
        from education_system.secondary_school.core.defaults import API_HOST
        assert API_HOST == os.getenv("SCHOOL_API_HOST", "127.0.0.1")

    def test_api_port_default(self):
        from education_system.secondary_school.core.defaults import API_PORT
        assert isinstance(API_PORT, int)
        assert API_PORT > 0

    def test_student_id_prefix(self):
        from education_system.secondary_school.core.defaults import STUDENT_ID_PREFIX
        assert STUDENT_ID_PREFIX == "SEC"

    def test_student_id_length(self):
        from education_system.secondary_school.core.defaults import STUDENT_ID_LENGTH
        assert STUDENT_ID_LENGTH == 7

    def test_default_admin_username(self):
        from education_system.secondary_school.core.defaults import DEFAULT_ADMIN_USERNAME
        assert DEFAULT_ADMIN_USERNAME == "admin2"

    def test_default_teacher_username(self):
        from education_system.secondary_school.core.defaults import DEFAULT_TEACHER_USERNAME
        assert DEFAULT_TEACHER_USERNAME == "staff2"

    def test_default_student_username(self):
        from education_system.secondary_school.core.defaults import DEFAULT_STUDENT_USERNAME
        assert DEFAULT_STUDENT_USERNAME == "student2"

    def test_shared_reexports(self):
        from education_system.secondary_school.core.defaults import (
            LOCKOUT_DURATION_MINUTES,
            MAX_LOGIN_ATTEMPTS,
            MIN_PASSWORD_LENGTH,
            SESSION_TIMEOUT_MINUTES,
            STAFF_ID_PREFIX,
            generate_secure_password,
        )
        assert isinstance(LOCKOUT_DURATION_MINUTES, int)
        assert isinstance(MAX_LOGIN_ATTEMPTS, int)
        assert isinstance(MIN_PASSWORD_LENGTH, int)
        assert isinstance(SESSION_TIMEOUT_MINUTES, int)
        assert isinstance(STAFF_ID_PREFIX, str)
        pw = generate_secure_password(16)
        assert len(pw) >= 16


class TestExceptions:
    """Tests for exception hierarchy."""

    def test_base_exception(self):
        from education_system.secondary_school.core.exceptions import SchoolSystemError
        assert issubclass(SchoolSystemError, Exception)

    def test_database_error_inherits_base(self):
        from education_system.secondary_school.core.exceptions import DatabaseError, SchoolSystemError
        assert issubclass(DatabaseError, SchoolSystemError)

    def test_auth_error_inherits_shared(self):
        from education_system.secondary_school.core.exceptions import AuthError, SchoolSystemError
        from education_system.shared.auth.exceptions import AuthError as SharedAuthError
        assert issubclass(AuthError, SharedAuthError)
        assert issubclass(AuthError, SchoolSystemError)

    def test_validation_error_inherits_shared(self):
        from education_system.secondary_school.core.exceptions import ValidationError, SchoolSystemError
        from education_system.shared.auth.exceptions import ValidationError as SharedValidationError
        assert issubclass(ValidationError, SharedValidationError)
        assert issubclass(ValidationError, SchoolSystemError)

    def test_all_domain_errors_inherit_base(self):
        from education_system.secondary_school.core import exceptions as exc
        domain_errors = [
            exc.StudentError, exc.SubjectError, exc.EnrollmentError,
            exc.GradeError, exc.AttendanceError, exc.TimetableError,
            exc.BehaviourError, exc.StaffError, exc.EmailError,
            exc.ExamError, exc.HRError, exc.FinanceError,
            exc.ReportError, exc.SENDError, exc.SafeguardingError,
            exc.ParentsEveningError, exc.CoverError, exc.HomeworkError,
            exc.CalendarError, exc.AnnouncementError, exc.UserManagementError,
            exc.PastoralError, exc.LibraryError, exc.MedicalError,
            exc.MealsError, exc.TripsError, exc.ClubsError,
            exc.DetentionError, exc.DocumentError, exc.VisitorError,
            exc.RoomBookingError, exc.AssetError, exc.SettingsError,
            exc.AdmissionsError, exc.InterventionError, exc.CPDError,
            exc.TransportError, exc.RewardsError, exc.CareersError,
            exc.FormGroupError, exc.AuditError, exc.PolicyError,
            exc.CommunicationLogError, exc.ExclusionError, exc.ProgressError,
            exc.SeatingPlanError, exc.ConsentError, exc.IncidentError,
            exc.PayrollError,
        ]
        for err_cls in domain_errors:
            assert issubclass(err_cls, exc.SchoolSystemError), (
                f"{err_cls.__name__} does not inherit from SchoolSystemError"
            )

    def test_exception_can_be_raised_and_caught(self):
        from education_system.secondary_school.core.exceptions import StudentError, SchoolSystemError
        with pytest.raises(SchoolSystemError):
            raise StudentError("test error")

    def test_exception_message(self):
        from education_system.secondary_school.core.exceptions import GradeError
        err = GradeError("invalid grade")
        assert str(err) == "invalid grade"


class TestLogs:
    """Tests for logging configuration."""

    def test_setup_logging_returns_logger(self):
        from education_system.secondary_school.core.logs import setup_logging
        logger = setup_logging(level=logging.WARNING)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "education_system.secondary_school"

    def test_setup_logging_accepts_level_arg(self):
        from education_system.secondary_school.core.logs import setup_logging
        logger = setup_logging(level=logging.DEBUG)
        # Logger may have handlers that filter, just verify no error
        assert isinstance(logger, logging.Logger)


class TestPaths:
    """Tests for path definitions."""

    def test_paths_are_defined(self):
        from education_system.secondary_school.core.paths import (
            SCHOOL_SYSTEM_ROOT, PROJECT_ROOT, DATA_DIR,
            DB_DIR, DB_FILE, CONFIG_DIR, LOGS_DIR,
        )
        assert SCHOOL_SYSTEM_ROOT is not None
        assert PROJECT_ROOT is not None
        assert DATA_DIR is not None
        assert DB_DIR is not None
        assert DB_FILE is not None
        assert CONFIG_DIR is not None
        assert LOGS_DIR is not None

    def test_db_file_has_correct_name(self):
        from education_system.secondary_school.core.paths import DB_FILE
        assert str(DB_FILE).endswith("secondary_school.db")

    def test_ensure_directories_callable(self):
        from education_system.secondary_school.core.paths import ensure_directories
        ensure_directories()


class TestSqlSafety:
    """Tests for SQL safety utility re-exports."""

    def test_validate_identifier_accepts_valid(self):
        from education_system.secondary_school.core.sql_safety import validate_identifier
        assert validate_identifier("first_name") == "first_name"

    def test_validate_identifier_rejects_invalid(self):
        from education_system.secondary_school.core.sql_safety import validate_identifier
        with pytest.raises(ValueError):
            validate_identifier("Robert'; DROP TABLE students;--")

    def test_escape_like(self):
        from education_system.secondary_school.core.sql_safety import escape_like
        result = escape_like("100%")
        assert "%" not in result or "\\" in result

    def test_build_where_clause_empty(self):
        from education_system.secondary_school.core.sql_safety import build_where_clause
        clause, params = build_where_clause({})
        assert clause == ""
        assert params == []

    def test_build_where_clause_with_filters(self):
        from education_system.secondary_school.core.sql_safety import build_where_clause
        clause, params = build_where_clause({"year_group": "9"})
        assert "year_group" in clause
        assert "9" in params

    def test_allowed_operators_exported(self):
        from education_system.secondary_school.core.sql_safety import ALLOWED_OPERATORS
        assert isinstance(ALLOWED_OPERATORS, (set, frozenset, list, tuple))
