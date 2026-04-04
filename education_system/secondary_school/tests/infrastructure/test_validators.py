"""Tests for infrastructure validation modules."""

import pytest

from education_system.secondary_school.core.exceptions import ValidationError


class TestValidateStudentId:
    """Tests for validate_student_id."""

    def test_valid_id(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_student_id
        assert validate_student_id("SEC0001") == "SEC0001"

    def test_lowercase_normalised(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_student_id
        assert validate_student_id("sec0001") == "SEC0001"

    def test_whitespace_stripped(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_student_id
        assert validate_student_id("  SEC0001  ") == "SEC0001"

    def test_invalid_prefix(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_student_id
        with pytest.raises(ValidationError):
            validate_student_id("PRI0001")

    def test_too_few_digits(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_student_id
        with pytest.raises(ValidationError):
            validate_student_id("SEC01")

    def test_too_many_digits(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_student_id
        with pytest.raises(ValidationError):
            validate_student_id("SEC00001")

    def test_empty_string(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_student_id
        with pytest.raises(ValidationError):
            validate_student_id("")


class TestValidateYearGroup:
    """Tests for validate_year_group."""

    def test_valid_year_7(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_year_group
        assert validate_year_group("7") == "7"

    def test_valid_year_11(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_year_group
        assert validate_year_group("11") == "11"

    def test_invalid_year_6(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_year_group
        with pytest.raises(ValidationError):
            validate_year_group("6")

    def test_invalid_year_12(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_year_group
        with pytest.raises(ValidationError):
            validate_year_group("12")

    def test_non_numeric(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_year_group
        with pytest.raises(ValidationError):
            validate_year_group("Reception")


class TestValidateGCSEGrade:
    """Tests for validate_gcse_grade."""

    def test_valid_grade_9(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_gcse_grade
        assert validate_gcse_grade("9") == "9"

    def test_valid_grade_1(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_gcse_grade
        assert validate_gcse_grade("1") == "1"

    def test_valid_grade_u(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_gcse_grade
        assert validate_gcse_grade("U") == "U"

    def test_invalid_grade_0(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_gcse_grade
        with pytest.raises(ValidationError):
            validate_gcse_grade("0")

    def test_invalid_grade_10(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_gcse_grade
        with pytest.raises(ValidationError):
            validate_gcse_grade("10")

    def test_invalid_grade_a(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_gcse_grade
        with pytest.raises(ValidationError):
            validate_gcse_grade("A")


class TestSharedValidatorWrappers:
    """Tests for wrapped shared validators raising secondary-specific ValidationError."""

    def test_validate_email_valid(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_email
        result = validate_email("test@school.local")
        assert "test@school.local" in result

    def test_validate_email_invalid(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_email
        with pytest.raises(ValidationError):
            validate_email("not-an-email")

    def test_validate_non_empty_valid(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_non_empty
        assert validate_non_empty("hello", "field") == "hello"

    def test_validate_non_empty_blank(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_non_empty
        with pytest.raises(ValidationError):
            validate_non_empty("", "field")

    def test_validate_date_valid(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_date
        assert validate_date("2025-09-01") == "2025-09-01"

    def test_validate_date_invalid(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_date
        with pytest.raises(ValidationError):
            validate_date("not-a-date")

    def test_validate_positive_int_valid(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_positive_int
        assert validate_positive_int(5, "count") == 5

    def test_validate_positive_int_zero(self):
        from education_system.secondary_school.infrastructure.validation.validators import validate_positive_int
        with pytest.raises(ValidationError):
            validate_positive_int(0, "count")

    def test_wrapped_error_is_secondary_specific(self):
        """Confirm wrapped validators raise the secondary-school ValidationError, not the shared one."""
        from education_system.secondary_school.infrastructure.validation.validators import validate_email
        from education_system.secondary_school.core.exceptions import ValidationError as SecondaryValidationError
        with pytest.raises(SecondaryValidationError):
            validate_email("invalid")
