"""
Core Validators

Provides validation functions for common data formats used throughout
the University Management System.
"""

import re
from datetime import datetime, date
from typing import Optional, List, Any, Union, Tuple
from dataclasses import dataclass, field


class ValidationError(Exception):
    """Exception raised when validation fails."""

    def __init__(self, message: str, field: str = "", errors: List[str] = None):
        self.message = message
        self.field = field
        self.errors = errors or [message]
        super().__init__(message)

    def __str__(self):
        if self.field:
            return f"{self.field}: {self.message}"
        return self.message


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    value: Any = None
    errors: List[str] = field(default_factory=list)
    field: str = ""

    def __bool__(self):
        return self.is_valid

    @property
    def error_message(self) -> str:
        """Get combined error message."""
        return "; ".join(self.errors)

    def raise_if_invalid(self):
        """Raise ValidationError if validation failed."""
        if not self.is_valid:
            raise ValidationError(self.error_message, self.field, self.errors)


class Validators:
    """
    Centralized validators for common data formats.

    Usage:
        from education_system.systems.university.infrastructure.validation import Validators

        # Direct validation
        if Validators.is_valid_email("user@example.com"):
            print("Valid email")

        # Validation with result
        result = Validators.validate_email("user@example.com")
        if result.is_valid:
            print(f"Email: {result.value}")
        else:
            print(f"Errors: {result.errors}")

        # Raise on invalid
        Validators.validate_email("invalid").raise_if_invalid()
    """

    # Email pattern (RFC 5322 simplified)
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    # University email pattern
    UNIVERSITY_EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@(.*\.)?university\.edu$'
    )

    # Phone patterns (international and local)
    PHONE_PATTERN = re.compile(
        r'^(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$'
    )
    PHONE_INTERNATIONAL_PATTERN = re.compile(
        r'^\+?[1-9]\d{6,14}$'
    )

    # Student ID pattern (configurable format)
    STUDENT_ID_PATTERN = re.compile(
        r'^(STU|S)?[A-Z]{0,2}\d{4,10}$',
        re.IGNORECASE
    )

    # Course code pattern
    COURSE_CODE_PATTERN = re.compile(
        r'^[A-Z]{2,4}\d{3,4}[A-Z]?$',
        re.IGNORECASE
    )

    # Module code pattern
    MODULE_CODE_PATTERN = re.compile(
        r'^[A-Z]{3}\d{4}$',
        re.IGNORECASE
    )

    # Name pattern (allows letters, spaces, hyphens, apostrophes)
    NAME_PATTERN = re.compile(
        r"^[a-zA-Z][a-zA-Z\s\-'\.]{0,49}$"
    )

    # Username pattern
    USERNAME_PATTERN = re.compile(
        r'^[a-zA-Z][a-zA-Z0-9._-]{2,29}$'
    )

    # Password requirements
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SPECIAL = False

    # Date formats
    DATE_FORMATS = [
        '%Y-%m-%d',           # ISO format
        '%d/%m/%Y',           # UK format
        '%m/%d/%Y',           # US format
        '%Y/%m/%d',           # Alternative ISO
        '%d-%m-%Y',           # UK with dashes
        '%B %d, %Y',          # Full month name
        '%d %B %Y',           # Day month year
    ]

    # Time formats
    TIME_FORMATS = [
        '%H:%M',              # 24-hour
        '%H:%M:%S',           # 24-hour with seconds
        '%I:%M %p',           # 12-hour with AM/PM
        '%I:%M:%S %p',        # 12-hour with seconds
    ]

    # Grade patterns
    LETTER_GRADE_PATTERN = re.compile(
        r'^[A-F][+-]?$',
        re.IGNORECASE
    )

    # GPA range
    GPA_MIN = 0.0
    GPA_MAX = 4.0

    # Credit range
    CREDITS_MIN = 0
    CREDITS_MAX = 200

    @classmethod
    def validate_email(cls, email: str, university_only: bool = False) -> ValidationResult:
        """
        Validate email address format.

        Args:
            email: Email address to validate
            university_only: If True, only accept university domain emails

        Returns:
            ValidationResult with normalized email
        """
        if not email:
            return ValidationResult(False, email, ["Email is required"])

        email = email.strip().lower()
        errors = []

        if len(email) > 254:
            errors.append("Email address is too long (max 254 characters)")

        # RFC 5321 local-part and domain-part length checks
        if '@' in email:
            local_part, domain_part = email.rsplit('@', 1)
            if len(local_part) > 64:
                errors.append("Email local part is too long (max 64 characters)")
            if len(domain_part) > 253:
                errors.append("Email domain is too long (max 253 characters)")

        if university_only:
            if not cls.UNIVERSITY_EMAIL_PATTERN.match(email):
                errors.append("Must be a valid university email address")
        else:
            if not cls.EMAIL_PATTERN.match(email):
                errors.append("Invalid email format")

        # Check for common issues
        if '..' in email:
            errors.append("Email cannot contain consecutive dots")

        if email.startswith('.') or email.endswith('.'):
            errors.append("Email cannot start or end with a dot")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=email,
            errors=errors,
            field="email"
        )

    @classmethod
    def validate_phone(cls, phone: str, allow_international: bool = True) -> ValidationResult:
        """
        Validate phone number format.

        Args:
            phone: Phone number to validate
            allow_international: If True, accept international formats

        Returns:
            ValidationResult with normalized phone number
        """
        if not phone:
            return ValidationResult(False, phone, ["Phone number is required"], "phone")

        # Remove common formatting characters for validation
        cleaned = re.sub(r'[\s\-\.\(\)]', '', phone)
        errors = []

        # Count only digits for E.164 length validation
        digits_only = re.sub(r'[^\d]', '', cleaned)

        if len(digits_only) < 7:
            errors.append("Phone number is too short (minimum 7 digits)")
        elif len(digits_only) > 15:
            errors.append("Phone number is too long (maximum 15 digits)")

        # Reject numbers that are all the same digit (e.g., 0000000000)
        if len(digits_only) >= 7 and len(set(digits_only)) == 1:
            errors.append("Phone number cannot be all the same digit")

        # Check for valid characters
        if not re.match(r'^\+?\d+$', cleaned):
            errors.append("Phone number contains invalid characters")

        # Pattern matching
        if allow_international:
            if not cls.PHONE_INTERNATIONAL_PATTERN.match(cleaned):
                if not cls.PHONE_PATTERN.match(phone):
                    errors.append("Invalid phone number format")
        else:
            if not cls.PHONE_PATTERN.match(phone):
                errors.append("Invalid phone number format")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=cleaned,
            errors=errors,
            field="phone"
        )

    @classmethod
    def validate_student_id(cls, student_id: str) -> ValidationResult:
        """
        Validate student ID format.

        Args:
            student_id: Student ID to validate

        Returns:
            ValidationResult with normalized ID
        """
        if not student_id:
            return ValidationResult(False, student_id, ["Student ID is required"], "student_id")

        student_id = student_id.strip().upper()
        errors = []

        if not cls.STUDENT_ID_PATTERN.match(student_id):
            errors.append("Invalid student ID format (expected format: STU2023001 or similar)")

        if len(student_id) < 4:
            errors.append("Student ID is too short")

        if len(student_id) > 15:
            errors.append("Student ID is too long")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=student_id,
            errors=errors,
            field="student_id"
        )

    @classmethod
    def validate_course_code(cls, code: str) -> ValidationResult:
        """Validate course code format (e.g., CS101, MATH201)."""
        if not code:
            return ValidationResult(False, code, ["Course code is required"], "course_code")

        code = code.strip().upper()
        errors = []

        if not cls.COURSE_CODE_PATTERN.match(code):
            errors.append("Invalid course code format (expected: CS101, MATH201, etc.)")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=code,
            errors=errors,
            field="course_code"
        )

    @classmethod
    def validate_module_code(cls, code: str) -> ValidationResult:
        """Validate module code format (e.g., CIS0001)."""
        if not code:
            return ValidationResult(False, code, ["Module code is required"], "module_code")

        code = code.strip().upper()
        errors = []

        if not cls.MODULE_CODE_PATTERN.match(code):
            errors.append("Invalid module code format (expected: CIS0001, etc.)")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=code,
            errors=errors,
            field="module_code"
        )

    @classmethod
    def validate_name(cls, name: str, field_name: str = "name") -> ValidationResult:
        """
        Validate a person's name.

        Args:
            name: Name to validate
            field_name: Field name for error messages

        Returns:
            ValidationResult
        """
        if not name:
            return ValidationResult(False, name, [f"{field_name.capitalize()} is required"], field_name)

        name = name.strip()
        errors = []

        if len(name) < 2:
            errors.append(f"{field_name.capitalize()} must be at least 2 characters")

        if len(name) > 50:
            errors.append(f"{field_name.capitalize()} cannot exceed 50 characters")

        if not cls.NAME_PATTERN.match(name):
            errors.append(f"{field_name.capitalize()} contains invalid characters")

        # Check for suspicious patterns
        if re.search(r'\d', name):
            errors.append(f"{field_name.capitalize()} should not contain numbers")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=name.title(),  # Normalize capitalization
            errors=errors,
            field=field_name
        )

    @classmethod
    def validate_username(cls, username: str) -> ValidationResult:
        """Validate username format."""
        if not username:
            return ValidationResult(False, username, ["Username is required"], "username")

        username = username.strip().lower()
        errors = []

        if len(username) < 3:
            errors.append("Username must be at least 3 characters")

        if len(username) > 30:
            errors.append("Username cannot exceed 30 characters")

        if not cls.USERNAME_PATTERN.match(username):
            errors.append("Username must start with a letter and contain only letters, numbers, dots, underscores, and hyphens")

        # Check for reserved usernames
        reserved = ['admin', 'root', 'system', 'administrator', 'superuser', 'guest']
        if username in reserved:
            errors.append("This username is reserved")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=username,
            errors=errors,
            field="username"
        )

    @classmethod
    def validate_password(
        cls,
        password: str,
        min_length: int = None,
        require_uppercase: bool = None,
        require_lowercase: bool = None,
        require_digit: bool = None,
        require_special: bool = None
    ) -> ValidationResult:
        """
        Validate password strength.

        Args:
            password: Password to validate
            min_length: Minimum length (default: 8)
            require_uppercase: Require uppercase letters
            require_lowercase: Require lowercase letters
            require_digit: Require digits
            require_special: Require special characters

        Returns:
            ValidationResult
        """
        if not password:
            return ValidationResult(False, None, ["Password is required"], "password")

        # Use defaults if not specified
        min_length = min_length or cls.PASSWORD_MIN_LENGTH
        require_uppercase = require_uppercase if require_uppercase is not None else cls.PASSWORD_REQUIRE_UPPERCASE
        require_lowercase = require_lowercase if require_lowercase is not None else cls.PASSWORD_REQUIRE_LOWERCASE
        require_digit = require_digit if require_digit is not None else cls.PASSWORD_REQUIRE_DIGIT
        require_special = require_special if require_special is not None else cls.PASSWORD_REQUIRE_SPECIAL

        errors = []

        if len(password) < min_length:
            errors.append(f"Password must be at least {min_length} characters")

        if len(password) > 128:
            errors.append("Password cannot exceed 128 characters")

        if require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")

        if require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")

        if require_digit and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")

        if require_special and not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            errors.append("Password must contain at least one special character")

        # Check for common weak passwords
        weak_passwords = ['password', '12345678', 'qwerty', 'admin123', 'letmein', 'welcome']
        if password.lower() in weak_passwords:
            errors.append("Password is too common")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=None,  # Never return password in result
            errors=errors,
            field="password"
        )

    @classmethod
    def validate_date(
        cls,
        date_str: str,
        formats: List[str] = None,
        min_date: date = None,
        max_date: date = None
    ) -> ValidationResult:
        """
        Validate and parse date string.

        Args:
            date_str: Date string to validate
            formats: List of accepted formats (default: common formats)
            min_date: Minimum allowed date
            max_date: Maximum allowed date

        Returns:
            ValidationResult with parsed date
        """
        if not date_str:
            return ValidationResult(False, None, ["Date is required"], "date")

        date_str = date_str.strip()
        formats = formats or cls.DATE_FORMATS
        errors = []
        parsed_date = None

        # Try each format
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue

        if parsed_date is None:
            errors.append(f"Invalid date format. Expected formats: {', '.join(formats[:3])}")
            return ValidationResult(False, None, errors, "date")

        # Range validation
        if min_date and parsed_date < min_date:
            errors.append(f"Date must be on or after {min_date}")

        if max_date and parsed_date > max_date:
            errors.append(f"Date must be on or before {max_date}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=parsed_date,
            errors=errors,
            field="date"
        )

    @classmethod
    def validate_grade(cls, grade: str) -> ValidationResult:
        """Validate letter grade format."""
        if not grade:
            return ValidationResult(False, grade, ["Grade is required"], "grade")

        grade = grade.strip().upper()
        errors = []

        if not cls.LETTER_GRADE_PATTERN.match(grade):
            errors.append("Invalid grade format (expected: A, B+, C-, etc.)")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=grade,
            errors=errors,
            field="grade"
        )

    @classmethod
    def validate_gpa(cls, gpa: Union[str, float]) -> ValidationResult:
        """Validate GPA value."""
        errors = []

        try:
            gpa_value = float(gpa)
        except (ValueError, TypeError):
            return ValidationResult(False, None, ["GPA must be a number"], "gpa")

        if gpa_value < cls.GPA_MIN:
            errors.append(f"GPA cannot be less than {cls.GPA_MIN}")

        if gpa_value > cls.GPA_MAX:
            errors.append(f"GPA cannot exceed {cls.GPA_MAX}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=round(gpa_value, 2),
            errors=errors,
            field="gpa"
        )

    @classmethod
    def validate_credits(cls, credits: Union[str, int]) -> ValidationResult:
        """Validate credit hours."""
        errors = []

        try:
            credits_value = int(credits)
        except (ValueError, TypeError):
            return ValidationResult(False, None, ["Credits must be a whole number"], "credits")

        if credits_value < cls.CREDITS_MIN:
            errors.append("Credits cannot be negative")

        if credits_value > cls.CREDITS_MAX:
            errors.append(f"Credits cannot exceed {cls.CREDITS_MAX}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            value=credits_value,
            errors=errors,
            field="credits"
        )

    # Convenience methods (return bool)
    @classmethod
    def is_valid_email(cls, email: str) -> bool:
        """Quick check if email is valid."""
        return cls.validate_email(email).is_valid

    @classmethod
    def is_valid_phone(cls, phone: str) -> bool:
        """Quick check if phone number is valid."""
        return cls.validate_phone(phone).is_valid

    @classmethod
    def is_valid_student_id(cls, student_id: str) -> bool:
        """Quick check if student ID is valid."""
        return cls.validate_student_id(student_id).is_valid

    @classmethod
    def is_valid_username(cls, username: str) -> bool:
        """Quick check if username is valid."""
        return cls.validate_username(username).is_valid


# Convenience functions
def validate(value: Any, validator_name: str, **kwargs) -> ValidationResult:
    """
    Validate a value using named validator.

    Args:
        value: Value to validate
        validator_name: Name of validator method (e.g., 'email', 'phone')
        **kwargs: Additional arguments for the validator

    Returns:
        ValidationResult
    """
    method_name = f"validate_{validator_name}"
    if hasattr(Validators, method_name):
        return getattr(Validators, method_name)(value, **kwargs)
    raise ValueError(f"Unknown validator: {validator_name}")


def validate_email(email: str, **kwargs) -> ValidationResult:
    """Validate email address."""
    return Validators.validate_email(email, **kwargs)


def validate_phone(phone: str, **kwargs) -> ValidationResult:
    """Validate phone number."""
    return Validators.validate_phone(phone, **kwargs)


def validate_student_id(student_id: str) -> ValidationResult:
    """Validate student ID."""
    return Validators.validate_student_id(student_id)


def validate_date(date_str: str, **kwargs) -> ValidationResult:
    """Validate date string."""
    return Validators.validate_date(date_str, **kwargs)


def validate_password_strength(password: str, **kwargs) -> ValidationResult:
    """Validate password strength."""
    return Validators.validate_password(password, **kwargs)


def is_valid_email(email: str) -> bool:
    """Check if email is valid."""
    return Validators.is_valid_email(email)


def is_valid_phone(phone: str) -> bool:
    """Check if phone is valid."""
    return Validators.is_valid_phone(phone)


def is_valid_student_id(student_id: str) -> bool:
    """Check if student ID is valid."""
    return Validators.is_valid_student_id(student_id)
