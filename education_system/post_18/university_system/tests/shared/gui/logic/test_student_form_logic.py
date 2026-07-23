"""
Comprehensive tests for StudentFormLogic.

These tests demonstrate how separating business logic from GUI components
enables thorough unit testing without any Tkinter dependencies.

Test Coverage:
- Name validation (required, format, length)
- Email validation (required, format, domain restrictions)
- Student ID validation (format pattern)
- Date of birth validation (format, age requirements)
- Phone number validation (format)
- Enrollment date validation (format, range)
- Data normalization
- Configuration customization
- Edge cases and boundary conditions
"""

import pytest
from datetime import date, timedelta
from education_system.post_18.university_system.modules.shared.gui.logic.student_form_logic import StudentFormLogic


class TestStudentFormLogicValidation:
    """Test the main validate_student_data method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_validate_complete_valid_data(self):
        """Test validation with all valid fields."""
        data = {
            'name': 'John Doe',
            'email': 'john.doe@university.edu',
            'student_id': 'STU001',
            'date_of_birth': '2000-01-15',
            'phone': '555-123-4567'
        }
        valid, errors = self.logic.validate_student_data(data)
        assert valid is True
        assert errors == []

    def test_validate_minimal_valid_data(self):
        """Test validation with only required fields."""
        data = {
            'name': 'Jane Smith',
            'email': 'jane@example.com'
        }
        valid, errors = self.logic.validate_student_data(data)
        assert valid is True
        assert errors == []

    def test_validate_missing_required_name(self):
        """Test validation fails when name is missing."""
        data = {
            'email': 'test@example.com'
        }
        valid, errors = self.logic.validate_student_data(data)
        assert valid is False
        assert 'Name is required' in errors

    def test_validate_missing_required_email(self):
        """Test validation fails when email is missing."""
        data = {
            'name': 'John Doe'
        }
        valid, errors = self.logic.validate_student_data(data)
        assert valid is False
        assert 'Email is required' in errors

    def test_validate_multiple_errors(self):
        """Test that multiple validation errors are collected."""
        data = {
            'name': '',
            'email': 'invalid-email',
            'student_id': 'invalid',
            'date_of_birth': 'not-a-date'
        }
        valid, errors = self.logic.validate_student_data(data)
        assert valid is False
        assert len(errors) >= 3  # At least name, email, and date errors


class TestNameValidation:
    """Test name field validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_validate_name_missing(self):
        """Test empty name is rejected."""
        valid, errors = self.logic.validate_name('')
        assert valid is False
        assert 'Name is required' in errors

    def test_validate_name_none(self):
        """Test None name is rejected."""
        valid, errors = self.logic.validate_name(None)
        assert valid is False
        assert 'Name is required' in errors

    def test_validate_name_too_short(self):
        """Test name shorter than minimum length."""
        valid, errors = self.logic.validate_name('A')
        assert valid is False
        assert any('at least' in e for e in errors)

    def test_validate_name_valid_minimum(self):
        """Test name at minimum length."""
        valid, errors = self.logic.validate_name('Jo')
        assert valid is True
        assert errors == []

    def test_validate_name_too_long(self):
        """Test name exceeding maximum length."""
        long_name = 'A' * 101
        valid, errors = self.logic.validate_name(long_name)
        assert valid is False
        assert any('exceed' in e for e in errors)

    def test_validate_name_with_hyphen(self):
        """Test hyphenated names are valid."""
        valid, errors = self.logic.validate_name('Mary-Jane Watson')
        assert valid is True

    def test_validate_name_with_apostrophe(self):
        """Test names with apostrophes are valid."""
        valid, errors = self.logic.validate_name("O'Connor")
        assert valid is True

    def test_validate_name_with_period(self):
        """Test names with periods (Jr., Sr., etc.) are valid."""
        valid, errors = self.logic.validate_name("John Smith Jr.")
        assert valid is True

    def test_validate_name_with_numbers(self):
        """Test names with numbers are rejected."""
        valid, errors = self.logic.validate_name('John123')
        assert valid is False
        assert any('invalid characters' in e for e in errors)

    def test_validate_name_with_special_chars(self):
        """Test names with special characters are rejected."""
        valid, errors = self.logic.validate_name('John@Doe')
        assert valid is False

    def test_validate_name_only_spaces(self):
        """Test name with only spaces is rejected."""
        valid, errors = self.logic.validate_name('   ')
        assert valid is False

    def test_validate_name_whitespace_trimmed(self):
        """Test name with extra whitespace is trimmed."""
        valid, errors = self.logic.validate_name('  John Doe  ')
        assert valid is True


class TestEmailValidation:
    """Test email field validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_validate_email_missing(self):
        """Test empty email is rejected."""
        valid, errors = self.logic.validate_email('')
        assert valid is False
        assert 'Email is required' in errors

    def test_validate_email_valid_simple(self):
        """Test simple valid email."""
        valid, errors = self.logic.validate_email('user@example.com')
        assert valid is True

    def test_validate_email_valid_subdomain(self):
        """Test email with subdomain."""
        valid, errors = self.logic.validate_email('user@mail.example.com')
        assert valid is True

    def test_validate_email_valid_plus_addressing(self):
        """Test email with plus addressing."""
        valid, errors = self.logic.validate_email('user+tag@example.com')
        assert valid is True

    def test_validate_email_missing_at(self):
        """Test email without @ symbol."""
        valid, errors = self.logic.validate_email('userexample.com')
        assert valid is False
        assert any('Invalid email format' in e for e in errors)

    def test_validate_email_missing_domain(self):
        """Test email without domain."""
        valid, errors = self.logic.validate_email('user@')
        assert valid is False

    def test_validate_email_missing_tld(self):
        """Test email without TLD."""
        valid, errors = self.logic.validate_email('user@example')
        assert valid is False

    def test_validate_email_short_tld(self):
        """Test email with single character TLD (invalid)."""
        valid, errors = self.logic.validate_email('user@example.c')
        assert valid is False

    def test_validate_email_case_insensitive(self):
        """Test email validation is case-insensitive."""
        valid, errors = self.logic.validate_email('User@EXAMPLE.COM')
        assert valid is True

    def test_validate_email_domain_restriction(self):
        """Test email domain restriction when configured."""
        logic = StudentFormLogic(config={'valid_email_domains': ['university.edu']})
        valid, errors = logic.validate_email('user@gmail.com')
        assert valid is False
        expected_domain = 'university.edu'
        assert any(expected_domain in e for e in errors)

    def test_validate_email_allowed_domain(self):
        """Test email from allowed domain passes."""
        logic = StudentFormLogic(config={'valid_email_domains': ['university.edu']})
        valid, errors = logic.validate_email('user@university.edu')
        assert valid is True


class TestStudentIdValidation:
    """Test student ID field validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_validate_student_id_empty(self):
        """Test empty student ID is allowed (optional field)."""
        valid, errors = self.logic.validate_student_id('')
        assert valid is True

    def test_validate_student_id_none(self):
        """Test None student ID is allowed (optional field)."""
        valid, errors = self.logic.validate_student_id(None)
        assert valid is True

    def test_validate_student_id_valid_short(self):
        """Test valid short student ID."""
        valid, errors = self.logic.validate_student_id('ST001')
        assert valid is True

    def test_validate_student_id_valid_long(self):
        """Test valid long student ID."""
        valid, errors = self.logic.validate_student_id('STUD12345678')
        assert valid is True

    def test_validate_student_id_lowercase(self):
        """Test lowercase student ID is normalized and valid."""
        valid, errors = self.logic.validate_student_id('stu001')
        assert valid is True

    def test_validate_student_id_invalid_no_letters(self):
        """Test student ID without letters is invalid."""
        valid, errors = self.logic.validate_student_id('12345')
        assert valid is False

    def test_validate_student_id_invalid_no_numbers(self):
        """Test student ID without numbers is invalid."""
        valid, errors = self.logic.validate_student_id('STUDENT')
        assert valid is False

    def test_validate_student_id_invalid_format(self):
        """Test student ID with wrong format."""
        valid, errors = self.logic.validate_student_id('123STU')
        assert valid is False

    def test_validate_student_id_too_few_digits(self):
        """Test student ID with too few digits."""
        valid, errors = self.logic.validate_student_id('STU01')
        assert valid is False

    def test_validate_student_id_custom_pattern(self):
        """Test custom student ID pattern."""
        logic = StudentFormLogic(config={'student_id_pattern': r'^ID\d{6}$'})
        valid, errors = logic.validate_student_id('ID123456')
        assert valid is True
        valid2, errors2 = logic.validate_student_id('STU001')
        assert valid2 is False


class TestDateOfBirthValidation:
    """Test date of birth field validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_validate_dob_empty(self):
        """Test empty DOB is allowed (optional field)."""
        valid, errors = self.logic.validate_date_of_birth('')
        assert valid is True

    def test_validate_dob_valid(self):
        """Test valid date of birth."""
        valid, errors = self.logic.validate_date_of_birth('2000-01-15')
        assert valid is True

    def test_validate_dob_invalid_format(self):
        """Test invalid date format."""
        valid, errors = self.logic.validate_date_of_birth('01/15/2000')
        assert valid is False
        assert any('YYYY-MM-DD' in e for e in errors)

    def test_validate_dob_invalid_date(self):
        """Test invalid date (Feb 30)."""
        valid, errors = self.logic.validate_date_of_birth('2000-02-30')
        assert valid is False

    def test_validate_dob_future_date(self):
        """Test future date is rejected."""
        future_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        valid, errors = self.logic.validate_date_of_birth(future_date)
        assert valid is False
        assert any('future' in e for e in errors)

    def test_validate_dob_too_young(self):
        """Test student too young (under 16)."""
        young_date = (date.today() - timedelta(days=365 * 10)).strftime('%Y-%m-%d')
        valid, errors = self.logic.validate_date_of_birth(young_date)
        assert valid is False
        assert any('16 years' in e for e in errors)

    def test_validate_dob_minimum_age(self):
        """Test student at minimum age."""
        min_age_date = date.today().replace(year=date.today().year - 16)
        valid, errors = self.logic.validate_date_of_birth(min_age_date.strftime('%Y-%m-%d'))
        assert valid is True

    def test_validate_dob_very_old(self):
        """Test very old date triggers verification warning."""
        old_date = '1900-01-01'
        valid, errors = self.logic.validate_date_of_birth(old_date)
        assert valid is False
        assert any('verify' in e.lower() for e in errors)

    def test_validate_dob_custom_min_age(self):
        """Test custom minimum age."""
        logic = StudentFormLogic(config={'min_age': 18})
        age_17_date = date.today().replace(year=date.today().year - 17)
        valid, errors = logic.validate_date_of_birth(age_17_date.strftime('%Y-%m-%d'))
        assert valid is False
        assert any('18 years' in e for e in errors)


class TestPhoneValidation:
    """Test phone number field validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_validate_phone_empty(self):
        """Test empty phone is allowed (optional field)."""
        valid, errors = self.logic.validate_phone('')
        assert valid is True

    def test_validate_phone_valid_10_digits(self):
        """Test valid 10-digit phone number."""
        valid, errors = self.logic.validate_phone('5551234567')
        assert valid is True

    def test_validate_phone_valid_with_formatting(self):
        """Test phone with formatting characters."""
        valid, errors = self.logic.validate_phone('(555) 123-4567')
        assert valid is True

    def test_validate_phone_valid_international(self):
        """Test valid international phone number."""
        valid, errors = self.logic.validate_phone('+1-555-123-4567')
        assert valid is True

    def test_validate_phone_too_short(self):
        """Test phone number too short."""
        valid, errors = self.logic.validate_phone('12345')
        assert valid is False

    def test_validate_phone_too_long(self):
        """Test phone number too long."""
        valid, errors = self.logic.validate_phone('1234567890123456')
        assert valid is False

    def test_validate_phone_with_letters(self):
        """Test phone with letters is invalid."""
        valid, errors = self.logic.validate_phone('555-CALL-ME')
        assert valid is False


class TestEnrollmentDateValidation:
    """Test enrollment date field validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_validate_enrollment_empty(self):
        """Test empty enrollment date is allowed (optional field)."""
        valid, errors = self.logic.validate_enrollment_date('')
        assert valid is True

    def test_validate_enrollment_valid_past(self):
        """Test valid past enrollment date."""
        past_date = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')
        valid, errors = self.logic.validate_enrollment_date(past_date)
        assert valid is True

    def test_validate_enrollment_valid_future(self):
        """Test valid near-future enrollment date."""
        future_date = (date.today() + timedelta(days=180)).strftime('%Y-%m-%d')
        valid, errors = self.logic.validate_enrollment_date(future_date)
        assert valid is True

    def test_validate_enrollment_too_far_future(self):
        """Test enrollment date too far in future."""
        far_future = (date.today() + timedelta(days=400)).strftime('%Y-%m-%d')
        valid, errors = self.logic.validate_enrollment_date(far_future)
        assert valid is False
        assert any('1 year' in e for e in errors)

    def test_validate_enrollment_too_far_past(self):
        """Test enrollment date too far in past."""
        far_past = (date.today() - timedelta(days=365 * 11)).strftime('%Y-%m-%d')
        valid, errors = self.logic.validate_enrollment_date(far_past)
        assert valid is False
        assert any('past' in e.lower() for e in errors)


class TestDataNormalization:
    """Test data normalization functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_normalize_name_title_case(self):
        """Test name is converted to title case."""
        data = {'name': 'john doe'}
        normalized = self.logic.normalize_student_data(data)
        assert normalized['name'] == 'John Doe'

    def test_normalize_name_extra_spaces(self):
        """Test extra spaces in name are removed."""
        data = {'name': '  john   doe  '}
        normalized = self.logic.normalize_student_data(data)
        assert normalized['name'] == 'John Doe'

    def test_normalize_email_lowercase(self):
        """Test email is converted to lowercase."""
        data = {'email': 'John.Doe@EXAMPLE.COM'}
        normalized = self.logic.normalize_student_data(data)
        assert normalized['email'] == 'john.doe@example.com'

    def test_normalize_student_id_uppercase(self):
        """Test student ID is converted to uppercase."""
        data = {'student_id': 'stu001'}
        normalized = self.logic.normalize_student_data(data)
        assert normalized['student_id'] == 'STU001'

    def test_normalize_phone_remove_formatting(self):
        """Test phone formatting is removed."""
        data = {'phone': '(555) 123-4567'}
        normalized = self.logic.normalize_student_data(data)
        assert normalized['phone'] == '5551234567'

    def test_normalize_missing_fields(self):
        """Test normalization handles missing fields gracefully."""
        data = {'name': 'John'}
        normalized = self.logic.normalize_student_data(data)
        assert 'email' not in normalized
        assert 'student_id' not in normalized


class TestCalculateAge:
    """Test age calculation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logic = StudentFormLogic()

    def test_calculate_age_valid(self):
        """Test age calculation with valid date."""
        birth_year = date.today().year - 20
        dob = f'{birth_year}-01-01'
        age = self.logic.calculate_age(dob)
        assert age == 20 or age == 19  # Depends on current date

    def test_calculate_age_invalid_format(self):
        """Test age calculation with invalid date format."""
        age = self.logic.calculate_age('01/01/2000')
        assert age is None

    def test_calculate_age_none(self):
        """Test age calculation with None."""
        age = self.logic.calculate_age(None)
        assert age is None

    def test_calculate_age_empty(self):
        """Test age calculation with empty string."""
        age = self.logic.calculate_age('')
        assert age is None


class TestConfigurationOverrides:
    """Test configuration customization."""

    def test_custom_min_name_length(self):
        """Test custom minimum name length."""
        logic = StudentFormLogic(config={'min_name_length': 3})
        valid, errors = logic.validate_name('Jo')
        assert valid is False
        assert any('3 characters' in e for e in errors)

    def test_custom_max_name_length(self):
        """Test custom maximum name length."""
        logic = StudentFormLogic(config={'max_name_length': 50})
        valid, errors = logic.validate_name('A' * 51)
        assert valid is False
        assert any('50' in e for e in errors)

    def test_custom_student_id_pattern(self):
        """Test custom student ID pattern."""
        logic = StudentFormLogic(config={'student_id_pattern': r'^[A-Z]\d{4}$'})
        valid1, _ = logic.validate_student_id('A1234')
        valid2, _ = logic.validate_student_id('STU001')
        assert valid1 is True
        assert valid2 is False

    def test_custom_email_domains(self):
        """Test custom email domain restriction."""
        logic = StudentFormLogic(config={'valid_email_domains': ['school.edu', 'school.org']})
        valid1, _ = logic.validate_email('user@school.edu')
        valid2, _ = logic.validate_email('user@gmail.com')
        assert valid1 is True
        assert valid2 is False

    def test_custom_age_limits(self):
        """Test custom age limits."""
        logic = StudentFormLogic(config={'min_age': 18, 'max_age': 65})
        assert logic.MIN_AGE == 18
        assert logic.MAX_AGE == 65
