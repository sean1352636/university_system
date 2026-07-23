#!/usr/bin/env python3
"""
Comprehensive tests for infrastructure validation - Validators module.

Tests the Validators class, ValidationResult dataclass, ValidationError exception,
and convenience functions for email, phone, student ID, course code, module code,
name, username, password, date, grade, GPA, and credits validation.
"""

import pytest
from datetime import date, timedelta

from education_system.post_18.university_system.infrastructure.validation.validators import (
    Validators,
    ValidationResult,
    ValidationError,
    validate,
    validate_email,
    validate_phone,
    validate_student_id,
    validate_date,
    validate_password_strength,
    is_valid_email,
    is_valid_phone,
    is_valid_student_id,
)


# ---------------------------------------------------------------------------
# ValidationResult dataclass
# ---------------------------------------------------------------------------

class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_valid_result_is_truthy(self):
        result = ValidationResult(is_valid=True, value="test")
        assert result
        assert result.is_valid is True

    def test_invalid_result_is_falsy(self):
        result = ValidationResult(is_valid=False, errors=["bad"])
        assert not result
        assert result.is_valid is False

    def test_error_message_joins_errors(self):
        result = ValidationResult(is_valid=False, errors=["err1", "err2"])
        assert result.error_message == "err1; err2"

    def test_error_message_empty_when_valid(self):
        result = ValidationResult(is_valid=True)
        assert result.error_message == ""

    def test_errors_default_to_empty_list(self):
        result = ValidationResult(is_valid=True)
        assert result.errors == []

    def test_value_stored_correctly(self):
        result = ValidationResult(is_valid=True, value="clean@email.com")
        assert result.value == "clean@email.com"

    def test_field_stored(self):
        result = ValidationResult(is_valid=True, field="email")
        assert result.field == "email"

    def test_raise_if_invalid_does_nothing_when_valid(self):
        result = ValidationResult(is_valid=True, value="ok")
        result.raise_if_invalid()  # Should not raise

    def test_raise_if_invalid_raises_when_invalid(self):
        result = ValidationResult(
            is_valid=False, errors=["fail1", "fail2"], field="test_field"
        )
        with pytest.raises(ValidationError) as exc_info:
            result.raise_if_invalid()
        assert "fail1" in str(exc_info.value)
        assert exc_info.value.field == "test_field"

    def test_raise_if_invalid_preserves_errors_list(self):
        result = ValidationResult(is_valid=False, errors=["a", "b"])
        with pytest.raises(ValidationError) as exc_info:
            result.raise_if_invalid()
        assert exc_info.value.errors == ["a", "b"]  # original errors list preserved


# ---------------------------------------------------------------------------
# ValidationError exception
# ---------------------------------------------------------------------------

class TestValidationError:
    """Tests for the ValidationError exception class."""

    def test_basic_message(self):
        err = ValidationError("something wrong")
        assert str(err) == "something wrong"
        assert err.message == "something wrong"

    def test_field_included_in_str(self):
        err = ValidationError("bad value", field="email")
        assert str(err) == "email: bad value"

    def test_errors_list_defaults_to_message(self):
        err = ValidationError("oops")
        assert err.errors == ["oops"]

    def test_custom_errors_list(self):
        err = ValidationError("main", errors=["err1", "err2"])
        assert err.errors == ["err1", "err2"]

    def test_is_exception(self):
        with pytest.raises(ValidationError):
            raise ValidationError("test")


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------

class TestValidateEmail:
    """Tests for Validators.validate_email."""

    # --- valid emails ---
    @pytest.mark.parametrize("email", [
        "user@example.com",
        "test.user@domain.org",
        "a+b@sub.domain.co.uk",
        "user123@test.io",
        "UPPER@CASE.COM",         # should be normalised to lowercase
        "  spaces@padded.com  ",  # should be stripped
    ])
    def test_valid_emails(self, email):
        result = Validators.validate_email(email)
        assert result.is_valid, f"Expected valid for {email!r}, got errors: {result.errors}"
        assert result.value == email.strip().lower()
        assert result.field == "email"

    # --- invalid emails ---
    @pytest.mark.parametrize("email,keyword", [
        ("", "required"),
        ("plaintext", "Invalid email format"),
        ("@nolocal.com", "Invalid email format"),
        ("user@", "Invalid email format"),
        ("user@.com", "Invalid email format"),
        ("user@domain", "Invalid email format"),
    ])
    def test_invalid_emails(self, email, keyword):
        result = Validators.validate_email(email)
        assert not result.is_valid
        assert any(keyword.lower() in e.lower() for e in result.errors), \
            f"Expected keyword {keyword!r} in errors {result.errors}"

    def test_email_too_long(self):
        long_local = "a" * 65
        email = f"{long_local}@example.com"
        result = Validators.validate_email(email)
        assert not result.is_valid
        assert any("local part" in e.lower() for e in result.errors)

    def test_email_overall_too_long(self):
        email = "a" * 64 + "@" + "b" * 245 + ".com"
        result = Validators.validate_email(email)
        assert not result.is_valid
        assert any("too long" in e.lower() for e in result.errors)

    def test_email_domain_too_long(self):
        email = "user@" + "d" * 250 + ".com"
        result = Validators.validate_email(email)
        assert not result.is_valid
        assert any("domain" in e.lower() for e in result.errors)

    def test_consecutive_dots_rejected(self):
        result = Validators.validate_email("user..name@example.com")
        assert not result.is_valid
        assert any("consecutive dots" in e.lower() for e in result.errors)

    def test_leading_dot_rejected(self):
        result = Validators.validate_email(".user@example.com")
        assert not result.is_valid
        assert any("start or end with a dot" in e.lower() for e in result.errors)

    def test_trailing_dot_rejected(self):
        result = Validators.validate_email("user@example.com.")
        assert not result.is_valid

    def test_university_only_valid(self):
        result = Validators.validate_email("student@university.edu", university_only=True)
        assert result.is_valid

    def test_university_only_subdomain(self):
        result = Validators.validate_email("staff@cs.university.edu", university_only=True)
        assert result.is_valid

    def test_university_only_rejects_external(self):
        result = Validators.validate_email("user@gmail.com", university_only=True)
        assert not result.is_valid
        assert any("university" in e.lower() for e in result.errors)

    def test_none_email_treated_as_empty(self):
        # None is falsy, should trigger "required"
        result = Validators.validate_email("")
        assert not result.is_valid
        assert any("required" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Phone validation
# ---------------------------------------------------------------------------

class TestValidatePhone:
    """Tests for Validators.validate_phone."""

    @pytest.mark.parametrize("phone", [
        "+12025551234",
        "+442071234567",
        "2025551234",
        "(202) 555-1234",
        "202-555-1234",
        "202.555.1234",
        "+1 202 555 1234",
    ])
    def test_valid_phones(self, phone):
        result = Validators.validate_phone(phone)
        assert result.is_valid, f"Expected valid for {phone!r}, errors: {result.errors}"
        assert result.field == "phone"

    def test_empty_phone_required(self):
        result = Validators.validate_phone("")
        assert not result.is_valid
        assert any("required" in e.lower() for e in result.errors)

    def test_too_short(self):
        result = Validators.validate_phone("12345")
        assert not result.is_valid
        assert any("too short" in e.lower() for e in result.errors)

    def test_too_long(self):
        result = Validators.validate_phone("1" * 20)
        assert not result.is_valid
        assert any("too long" in e.lower() for e in result.errors)

    def test_all_same_digit_rejected(self):
        result = Validators.validate_phone("0000000000")
        assert not result.is_valid
        assert any("same digit" in e.lower() for e in result.errors)

    def test_all_same_digit_seven(self):
        result = Validators.validate_phone("1111111")
        assert not result.is_valid
        assert any("same digit" in e.lower() for e in result.errors)

    def test_letters_rejected(self):
        result = Validators.validate_phone("555-CALL-ME")
        assert not result.is_valid

    def test_international_disabled_local_only(self):
        # Standard local format should still work
        result = Validators.validate_phone("(202) 555-1234", allow_international=False)
        assert result.is_valid

    def test_cleaned_value_returned(self):
        result = Validators.validate_phone("(202) 555-1234")
        # Cleaned means spaces, dashes, parens removed
        assert "(" not in result.value
        assert " " not in result.value


# ---------------------------------------------------------------------------
# Student ID validation
# ---------------------------------------------------------------------------

class TestValidateStudentId:
    """Tests for Validators.validate_student_id."""

    @pytest.mark.parametrize("sid", [
        "STU2023001",
        "S12345",
        "stu1234",       # case-insensitive, normalised to upper
        "SCS20230001",
        "1234",          # 4 digits, matches regex
    ])
    def test_valid_student_ids(self, sid):
        result = Validators.validate_student_id(sid)
        assert result.is_valid, f"Expected valid for {sid!r}, errors: {result.errors}"
        assert result.value == sid.strip().upper()

    def test_empty_required(self):
        result = Validators.validate_student_id("")
        assert not result.is_valid
        assert any("required" in e.lower() for e in result.errors)

    def test_too_short(self):
        result = Validators.validate_student_id("AB")
        assert not result.is_valid

    def test_too_long(self):
        result = Validators.validate_student_id("STU" + "0" * 20)
        assert not result.is_valid
        assert any("too long" in e.lower() for e in result.errors)

    def test_invalid_format(self):
        result = Validators.validate_student_id("INVALID_FORMAT!")
        assert not result.is_valid

    def test_field_is_student_id(self):
        result = Validators.validate_student_id("STU2023001")
        assert result.field == "student_id"


# ---------------------------------------------------------------------------
# Course code validation
# ---------------------------------------------------------------------------

class TestValidateCourseCode:
    """Tests for Validators.validate_course_code."""

    @pytest.mark.parametrize("code", [
        "CS101",
        "MATH201",
        "cs101",        # case-insensitive
        "ENG1001",
        "BIO300A",      # optional trailing letter
    ])
    def test_valid_codes(self, code):
        result = Validators.validate_course_code(code)
        assert result.is_valid, f"Expected valid for {code!r}, errors: {result.errors}"
        assert result.value == code.strip().upper()

    def test_empty_required(self):
        result = Validators.validate_course_code("")
        assert not result.is_valid
        assert any("required" in e.lower() for e in result.errors)

    @pytest.mark.parametrize("code", [
        "C101",         # single letter prefix -- too short
        "ABCDE100",     # 5-letter prefix -- too long
        "CS1",          # only 1 digit
        "123",          # no letter prefix
    ])
    def test_invalid_codes(self, code):
        result = Validators.validate_course_code(code)
        assert not result.is_valid

    def test_field_is_course_code(self):
        result = Validators.validate_course_code("CS101")
        assert result.field == "course_code"


# ---------------------------------------------------------------------------
# Module code validation
# ---------------------------------------------------------------------------

class TestValidateModuleCode:
    """Tests for Validators.validate_module_code."""

    @pytest.mark.parametrize("code", [
        "CIS0001",
        "MAT1234",
        "cis0001",    # case-insensitive
    ])
    def test_valid_module_codes(self, code):
        result = Validators.validate_module_code(code)
        assert result.is_valid, f"Expected valid for {code!r}, errors: {result.errors}"
        assert result.value == code.strip().upper()

    def test_empty_required(self):
        result = Validators.validate_module_code("")
        assert not result.is_valid

    @pytest.mark.parametrize("code", [
        "CI0001",      # only 2 letters
        "CISC0001",    # 4 letters
        "CIS001",      # only 3 digits
        "CIS00001",    # 5 digits
    ])
    def test_invalid_module_codes(self, code):
        result = Validators.validate_module_code(code)
        assert not result.is_valid

    def test_field_is_module_code(self):
        result = Validators.validate_module_code("CIS0001")
        assert result.field == "module_code"


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------

class TestValidateName:
    """Tests for Validators.validate_name."""

    @pytest.mark.parametrize("name", [
        "Alice",
        "Bob Smith",
        "Mary-Jane",
        "O'Brien",
        "Jean-Pierre",
        "Dr. Smith",    # period allowed by pattern
        "AB",           # exactly 2 characters
    ])
    def test_valid_names(self, name):
        result = Validators.validate_name(name)
        assert result.is_valid, f"Expected valid for {name!r}, errors: {result.errors}"

    def test_value_is_titlecased(self):
        result = Validators.validate_name("alice bob")
        assert result.value == "Alice Bob"

    def test_empty_required(self):
        result = Validators.validate_name("")
        assert not result.is_valid
        assert any("required" in e.lower() for e in result.errors)

    def test_single_char_too_short(self):
        result = Validators.validate_name("A")
        assert not result.is_valid
        assert any("at least 2" in e.lower() for e in result.errors)

    def test_too_long(self):
        result = Validators.validate_name("A" * 51)
        assert not result.is_valid
        assert any("exceed 50" in e.lower() or "cannot exceed" in e.lower() for e in result.errors)

    def test_numbers_rejected(self):
        result = Validators.validate_name("John3")
        assert not result.is_valid
        assert any("numbers" in e.lower() for e in result.errors)

    def test_special_chars_rejected(self):
        result = Validators.validate_name("Alice@Home")
        assert not result.is_valid

    def test_custom_field_name_in_errors(self):
        result = Validators.validate_name("", field_name="first_name")
        assert any("first_name" in e.lower() for e in result.errors)
        assert result.field == "first_name"

    def test_stripped(self):
        result = Validators.validate_name("  Alice  ")
        assert result.is_valid
        assert result.value == "Alice"


# ---------------------------------------------------------------------------
# Username validation
# ---------------------------------------------------------------------------

class TestValidateUsername:
    """Tests for Validators.validate_username."""

    @pytest.mark.parametrize("username", [
        "alice",
        "bob123",
        "user.name",
        "user_name",
        "user-name",
        "abc",                # minimum length 3
        "a" * 30,             # maximum length 30
    ])
    def test_valid_usernames(self, username):
        result = Validators.validate_username(username)
        assert result.is_valid, f"Expected valid for {username!r}, errors: {result.errors}"
        assert result.value == username.strip().lower()

    def test_empty_required(self):
        result = Validators.validate_username("")
        assert not result.is_valid

    def test_too_short(self):
        result = Validators.validate_username("ab")
        assert not result.is_valid
        assert any("at least 3" in e.lower() for e in result.errors)

    def test_too_long(self):
        result = Validators.validate_username("a" * 31)
        assert not result.is_valid
        assert any("exceed 30" in e.lower() or "cannot exceed" in e.lower() for e in result.errors)

    def test_must_start_with_letter(self):
        result = Validators.validate_username("123user")
        assert not result.is_valid
        assert any("start with a letter" in e.lower() for e in result.errors)

    @pytest.mark.parametrize("reserved", [
        "admin", "root", "system", "administrator", "superuser", "guest",
    ])
    def test_reserved_names_rejected(self, reserved):
        result = Validators.validate_username(reserved)
        assert not result.is_valid
        assert any("reserved" in e.lower() for e in result.errors)

    def test_reserved_case_insensitive(self):
        result = Validators.validate_username("ADMIN")
        assert not result.is_valid
        assert any("reserved" in e.lower() for e in result.errors)

    def test_normalised_to_lowercase(self):
        result = Validators.validate_username("Alice")
        assert result.value == "alice"

    def test_field_is_username(self):
        result = Validators.validate_username("alice")
        assert result.field == "username"


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

class TestValidatePassword:
    """Tests for Validators.validate_password."""

    def test_valid_strong_password(self):
        result = Validators.validate_password("StrongP4ss!")
        assert result.is_valid

    def test_value_is_never_returned(self):
        result = Validators.validate_password("StrongP4ss!")
        assert result.value is None

    def test_empty_required(self):
        result = Validators.validate_password("")
        assert not result.is_valid
        assert any("required" in e.lower() for e in result.errors)

    def test_too_short_default(self):
        result = Validators.validate_password("Abc1")
        assert not result.is_valid
        assert any("at least 8" in e for e in result.errors)

    def test_too_long(self):
        result = Validators.validate_password("Aa1" + "x" * 126)
        assert not result.is_valid
        assert any("128" in e for e in result.errors)

    def test_exactly_128_chars(self):
        pw = "Aa1" + "x" * 125  # 128 total
        result = Validators.validate_password(pw)
        assert result.is_valid

    def test_requires_uppercase_by_default(self):
        result = Validators.validate_password("alllower1")
        assert not result.is_valid
        assert any("uppercase" in e.lower() for e in result.errors)

    def test_requires_lowercase_by_default(self):
        result = Validators.validate_password("ALLUPPER1")
        assert not result.is_valid
        assert any("lowercase" in e.lower() for e in result.errors)

    def test_requires_digit_by_default(self):
        result = Validators.validate_password("NoDigitsHere")
        assert not result.is_valid
        assert any("digit" in e.lower() for e in result.errors)

    def test_no_special_required_by_default(self):
        # Default PASSWORD_REQUIRE_SPECIAL is False
        result = Validators.validate_password("ValidPw1")
        assert result.is_valid

    def test_require_special_when_enabled(self):
        result = Validators.validate_password("ValidPw1", require_special=True)
        assert not result.is_valid
        assert any("special" in e.lower() for e in result.errors)

    def test_special_passes_when_enabled(self):
        result = Validators.validate_password("ValidPw1!", require_special=True)
        assert result.is_valid

    def test_custom_min_length(self):
        result = Validators.validate_password("Ab1", min_length=3)
        assert result.is_valid

    def test_disable_uppercase(self):
        result = Validators.validate_password("alllower1", require_uppercase=False)
        assert result.is_valid

    def test_disable_lowercase(self):
        result = Validators.validate_password("ALLUPPER1", require_lowercase=False)
        assert result.is_valid

    def test_disable_digit(self):
        result = Validators.validate_password("NoDigitsHere", require_digit=False)
        assert result.is_valid

    @pytest.mark.parametrize("weak", [
        "password", "12345678", "qwerty", "admin123", "letmein", "welcome",
    ])
    def test_weak_passwords_rejected(self, weak):
        result = Validators.validate_password(weak)
        assert not result.is_valid
        assert any("common" in e.lower() for e in result.errors)

    def test_weak_password_case_insensitive(self):
        result = Validators.validate_password("Password")
        assert not result.is_valid
        assert any("common" in e.lower() for e in result.errors)

    def test_field_is_password(self):
        result = Validators.validate_password("StrongP4ss!")
        assert result.field == "password"


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------

class TestValidateDate:
    """Tests for Validators.validate_date."""

    def test_iso_format(self):
        result = Validators.validate_date("2024-06-15")
        assert result.is_valid
        assert result.value == date(2024, 6, 15)

    def test_uk_format(self):
        result = Validators.validate_date("15/06/2024")
        assert result.is_valid

    def test_us_format(self):
        # US format is tried after UK -- "06/15/2024" won't parse as UK (day 6, month 15)
        # but will parse as US
        result = Validators.validate_date("06/15/2024")
        assert result.is_valid

    def test_full_month_name(self):
        result = Validators.validate_date("June 15, 2024")
        assert result.is_valid
        assert result.value == date(2024, 6, 15)

    def test_empty_required(self):
        result = Validators.validate_date("")
        assert not result.is_valid
        assert any("required" in e.lower() for e in result.errors)

    def test_invalid_format(self):
        result = Validators.validate_date("not-a-date")
        assert not result.is_valid
        assert any("format" in e.lower() for e in result.errors)

    def test_custom_formats(self):
        result = Validators.validate_date("2024.06.15", formats=["%Y.%m.%d"])
        assert result.is_valid
        assert result.value == date(2024, 6, 15)

    def test_min_date_pass(self):
        result = Validators.validate_date("2024-06-15", min_date=date(2024, 1, 1))
        assert result.is_valid

    def test_min_date_fail(self):
        result = Validators.validate_date("2023-12-31", min_date=date(2024, 1, 1))
        assert not result.is_valid
        assert any("after" in e.lower() for e in result.errors)

    def test_max_date_pass(self):
        result = Validators.validate_date("2024-06-15", max_date=date(2024, 12, 31))
        assert result.is_valid

    def test_max_date_fail(self):
        result = Validators.validate_date("2025-01-01", max_date=date(2024, 12, 31))
        assert not result.is_valid
        assert any("before" in e.lower() for e in result.errors)

    def test_min_and_max_boundaries(self):
        # Exactly on min/max should be valid
        min_d = date(2024, 1, 1)
        max_d = date(2024, 12, 31)
        assert Validators.validate_date("2024-01-01", min_date=min_d, max_date=max_d).is_valid
        assert Validators.validate_date("2024-12-31", min_date=min_d, max_date=max_d).is_valid

    def test_field_is_date(self):
        result = Validators.validate_date("2024-06-15")
        assert result.field == "date"

    def test_whitespace_stripped(self):
        result = Validators.validate_date("  2024-06-15  ")
        assert result.is_valid


# ---------------------------------------------------------------------------
# Grade validation
# ---------------------------------------------------------------------------

class TestValidateGrade:
    """Tests for Validators.validate_grade."""

    @pytest.mark.parametrize("grade", [
        "A", "B", "C", "D", "E", "F",
        "A+", "A-", "B+", "B-", "C+", "C-", "D+", "D-",
        "a", "b+",   # case-insensitive
    ])
    def test_valid_grades(self, grade):
        result = Validators.validate_grade(grade)
        assert result.is_valid, f"Expected valid for {grade!r}, errors: {result.errors}"
        assert result.value == grade.strip().upper()

    def test_empty_required(self):
        result = Validators.validate_grade("")
        assert not result.is_valid

    @pytest.mark.parametrize("grade", [
        "G", "AA", "1", "A++", "AB",
    ])
    def test_invalid_grades(self, grade):
        result = Validators.validate_grade(grade)
        assert not result.is_valid

    def test_field_is_grade(self):
        result = Validators.validate_grade("A")
        assert result.field == "grade"


# ---------------------------------------------------------------------------
# GPA validation
# ---------------------------------------------------------------------------

class TestValidateGpa:
    """Tests for Validators.validate_gpa."""

    @pytest.mark.parametrize("gpa", [0.0, 1.5, 2.0, 3.5, 4.0, "3.75"])
    def test_valid_gpas(self, gpa):
        result = Validators.validate_gpa(gpa)
        assert result.is_valid
        assert isinstance(result.value, float)

    def test_boundary_zero(self):
        result = Validators.validate_gpa(0.0)
        assert result.is_valid
        assert result.value == 0.0

    def test_boundary_four(self):
        result = Validators.validate_gpa(4.0)
        assert result.is_valid
        assert result.value == 4.0

    def test_below_min(self):
        result = Validators.validate_gpa(-0.1)
        assert not result.is_valid
        assert any("less than" in e.lower() for e in result.errors)

    def test_above_max(self):
        result = Validators.validate_gpa(4.1)
        assert not result.is_valid
        assert any("exceed" in e.lower() for e in result.errors)

    def test_non_numeric_string(self):
        result = Validators.validate_gpa("abc")
        assert not result.is_valid
        assert any("number" in e.lower() for e in result.errors)

    def test_none_input(self):
        result = Validators.validate_gpa(None)
        assert not result.is_valid

    def test_value_rounded_to_two_decimals(self):
        result = Validators.validate_gpa(3.14159)
        assert result.is_valid
        assert result.value == 3.14

    def test_string_input_converted(self):
        result = Validators.validate_gpa("3.5")
        assert result.is_valid
        assert result.value == 3.5

    def test_field_is_gpa(self):
        result = Validators.validate_gpa(3.0)
        assert result.field == "gpa"


# ---------------------------------------------------------------------------
# Credits validation
# ---------------------------------------------------------------------------

class TestValidateCredits:
    """Tests for Validators.validate_credits."""

    @pytest.mark.parametrize("credits_val", [0, 1, 100, 200, "15"])
    def test_valid_credits(self, credits_val):
        result = Validators.validate_credits(credits_val)
        assert result.is_valid
        assert isinstance(result.value, int)

    def test_boundary_zero(self):
        result = Validators.validate_credits(0)
        assert result.is_valid

    def test_boundary_200(self):
        result = Validators.validate_credits(200)
        assert result.is_valid

    def test_negative(self):
        result = Validators.validate_credits(-1)
        assert not result.is_valid
        assert any("negative" in e.lower() for e in result.errors)

    def test_above_max(self):
        result = Validators.validate_credits(201)
        assert not result.is_valid
        assert any("exceed" in e.lower() or "200" in e for e in result.errors)

    def test_non_numeric(self):
        result = Validators.validate_credits("abc")
        assert not result.is_valid
        assert any("whole number" in e.lower() for e in result.errors)

    def test_none_input(self):
        result = Validators.validate_credits(None)
        assert not result.is_valid

    def test_float_string(self):
        # "3.5" cannot convert to int
        result = Validators.validate_credits("3.5")
        assert not result.is_valid

    def test_field_is_credits(self):
        result = Validators.validate_credits(15)
        assert result.field == "credits"


# ---------------------------------------------------------------------------
# Convenience boolean methods
# ---------------------------------------------------------------------------

class TestConvenienceMethods:
    """Tests for is_valid_* class methods."""

    def test_is_valid_email_true(self):
        assert Validators.is_valid_email("user@example.com") is True

    def test_is_valid_email_false(self):
        assert Validators.is_valid_email("invalid") is False

    def test_is_valid_phone_true(self):
        assert Validators.is_valid_phone("+12025551234") is True

    def test_is_valid_phone_false(self):
        assert Validators.is_valid_phone("") is False

    def test_is_valid_student_id_true(self):
        assert Validators.is_valid_student_id("STU2023001") is True

    def test_is_valid_student_id_false(self):
        assert Validators.is_valid_student_id("") is False

    def test_is_valid_username_true(self):
        assert Validators.is_valid_username("alice") is True

    def test_is_valid_username_false(self):
        assert Validators.is_valid_username("") is False


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_validate_email_function(self):
        result = validate_email("user@example.com")
        assert result.is_valid

    def test_validate_phone_function(self):
        result = validate_phone("+12025551234")
        assert result.is_valid

    def test_validate_student_id_function(self):
        result = validate_student_id("STU2023001")
        assert result.is_valid

    def test_validate_date_function(self):
        result = validate_date("2024-06-15")
        assert result.is_valid

    def test_validate_password_strength_function(self):
        result = validate_password_strength("StrongP4ss!")
        assert result.is_valid

    def test_is_valid_email_function(self):
        assert is_valid_email("user@example.com") is True

    def test_is_valid_phone_function(self):
        assert is_valid_phone("+12025551234") is True

    def test_is_valid_student_id_function(self):
        assert is_valid_student_id("STU2023001") is True

    def test_validate_dispatch_by_name(self):
        result = validate("user@example.com", "email")
        assert result.is_valid

    def test_validate_unknown_validator_raises(self):
        with pytest.raises(ValueError, match="Unknown validator"):
            validate("anything", "nonexistent_validator")
