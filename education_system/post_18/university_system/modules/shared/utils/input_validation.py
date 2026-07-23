"""
Input Validation Utilities - Centralized validation for user input.

This module provides validation functions for common input types used
throughout the university system, including email addresses, phone numbers,
dates, numeric values, and identifiers.

Usage:
    from education_system.post_18.university_system.modules.shared.utils.input_validation import (
        validate_email,
        validate_phone,
        validate_date,
        validate_numeric,
        validate_student_id,
        validate_required,
        ValidationError,
    )

    # Validate email
    try:
        email = validate_email(user_input)
    except ValidationError as e:
        print(f"Invalid email: {e}")

    # Validate with custom error message
    phone = validate_phone(user_input, error_msg="Please enter a valid phone number")
"""

import re
import logging
from datetime import datetime, date
from typing import Optional, Union, Any, List, Callable, TypeVar, Tuple
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ValidationError(ValueError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field_name: Optional[str] = None):
        self.field_name = field_name
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        if self.field_name:
            return f"{self.field_name}: {self.message}"
        return self.message


# Common regex patterns
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Flexible phone pattern - allows various formats
PHONE_PATTERN = re.compile(
    r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{7,}$'
)

# Student ID pattern (alphanumeric, typically starts with letter)
STUDENT_ID_PATTERN = re.compile(
    r'^[A-Za-z][A-Za-z0-9]{4,19}$'
)

# Username pattern (alphanumeric, underscores, periods)
USERNAME_PATTERN = re.compile(
    r'^[a-zA-Z][a-zA-Z0-9._]{2,29}$'
)

# Date formats to try when parsing
DATE_FORMATS = [
    '%Y-%m-%d',      # ISO format: 2024-01-15
    '%d/%m/%Y',      # UK format: 15/01/2024
    '%m/%d/%Y',      # US format: 01/15/2024
]


def validate_required(
    value: Any,
    field_name: str = "Field",
    strip: bool = True
) -> str:
    """
    Validate that a value is not empty.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        strip: Whether to strip whitespace from strings

    Returns:
        The validated string value

    Raises:
        ValidationError: If value is empty or None
    """
    if value is None:
        raise ValidationError(f"{field_name} is required", field_name)

    if isinstance(value, str):
        result = value.strip() if strip else value
        if not result:
            raise ValidationError(f"{field_name} is required", field_name)
        return result

    return str(value)


def validate_email(
    email: str,
    field_name: str = "Email",
    error_msg: Optional[str] = None
) -> str:
    """
    Validate an email address.

    Args:
        email: The email address to validate
        field_name: Name of the field for error messages
        error_msg: Custom error message

    Returns:
        The validated email address (lowercase)

    Raises:
        ValidationError: If email format is invalid
    """
    if not email or not isinstance(email, str):
        raise ValidationError(
            error_msg or f"{field_name} is required",
            field_name
        )

    email = email.strip().lower()

    if not EMAIL_PATTERN.match(email):
        raise ValidationError(
            error_msg or f"Invalid email format: {email}",
            field_name
        )

    # Additional validation
    if len(email) > 254:
        raise ValidationError(
            error_msg or "Email address is too long (max 254 characters)",
            field_name
        )

    local_part, domain = email.rsplit('@', 1)
    if len(local_part) > 64:
        raise ValidationError(
            error_msg or "Email local part is too long (max 64 characters)",
            field_name
        )

    return email


def validate_phone(
    phone: str,
    field_name: str = "Phone",
    error_msg: Optional[str] = None,
    min_digits: int = 7,
    max_digits: int = 15
) -> str:
    """
    Validate a phone number.

    Args:
        phone: The phone number to validate
        field_name: Name of the field for error messages
        error_msg: Custom error message
        min_digits: Minimum number of digits required
        max_digits: Maximum number of digits allowed

    Returns:
        The cleaned phone number (digits only with optional leading +)

    Raises:
        ValidationError: If phone format is invalid
    """
    if not phone or not isinstance(phone, str):
        raise ValidationError(
            error_msg or f"{field_name} is required",
            field_name
        )

    phone = phone.strip()

    if not PHONE_PATTERN.match(phone):
        raise ValidationError(
            error_msg or f"Invalid phone number format: {phone}",
            field_name
        )

    # Count actual digits
    digits = re.sub(r'[^0-9]', '', phone)
    if len(digits) < min_digits:
        raise ValidationError(
            error_msg or f"Phone number must have at least {min_digits} digits",
            field_name
        )
    if len(digits) > max_digits:
        raise ValidationError(
            error_msg or f"Phone number must have at most {max_digits} digits",
            field_name
        )

    # Return normalized format
    if phone.startswith('+'):
        return '+' + digits
    return digits


def validate_date(
    date_str: str,
    field_name: str = "Date",
    error_msg: Optional[str] = None,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    formats: Optional[List[str]] = None
) -> date:
    """
    Validate and parse a date string.

    Args:
        date_str: The date string to validate
        field_name: Name of the field for error messages
        error_msg: Custom error message
        min_date: Minimum allowed date
        max_date: Maximum allowed date
        formats: List of date formats to try (defaults to DATE_FORMATS)

    Returns:
        Parsed date object

    Raises:
        ValidationError: If date format is invalid or out of range
    """
    if not date_str or not isinstance(date_str, str):
        raise ValidationError(
            error_msg or f"{field_name} is required",
            field_name
        )

    date_str = date_str.strip()
    parsed_date = None

    # Try each format
    for fmt in (formats or DATE_FORMATS):
        try:
            parsed_date = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue

    if parsed_date is None:
        raise ValidationError(
            error_msg or f"Invalid date format: {date_str}. Try YYYY-MM-DD format.",
            field_name
        )

    # Range validation
    if min_date and parsed_date < min_date:
        raise ValidationError(
            error_msg or f"{field_name} must be on or after {min_date}",
            field_name
        )

    if max_date and parsed_date > max_date:
        raise ValidationError(
            error_msg or f"{field_name} must be on or before {max_date}",
            field_name
        )

    return parsed_date


def validate_numeric(
    value: Union[str, int, float],
    field_name: str = "Value",
    error_msg: Optional[str] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allow_negative: bool = True,
    decimal_places: Optional[int] = None,
    return_type: type = float
) -> Union[int, float, Decimal]:
    """
    Validate a numeric value.

    Args:
        value: The value to validate (string or number)
        field_name: Name of the field for error messages
        error_msg: Custom error message
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_negative: Whether negative values are allowed
        decimal_places: Maximum decimal places (None for unlimited)
        return_type: Type to return (int, float, or Decimal)

    Returns:
        Validated numeric value

    Raises:
        ValidationError: If value is not a valid number or out of range
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(
            error_msg or f"{field_name} is required",
            field_name
        )

    # Convert to string for parsing
    if isinstance(value, str):
        value = value.strip().replace(',', '')  # Remove commas

    try:
        if return_type is int:
            num = int(float(value))
        elif return_type is Decimal:
            num = Decimal(str(value))
        else:
            num = float(value)
    except (ValueError, InvalidOperation):
        raise ValidationError(
            error_msg or f"Invalid numeric value: {value}",
            field_name
        )

    # Validate constraints
    if not allow_negative and num < 0:
        raise ValidationError(
            error_msg or f"{field_name} must be non-negative",
            field_name
        )

    if min_value is not None and num < min_value:
        raise ValidationError(
            error_msg or f"{field_name} must be at least {min_value}",
            field_name
        )

    if max_value is not None and num > max_value:
        raise ValidationError(
            error_msg or f"{field_name} must be at most {max_value}",
            field_name
        )

    # Check decimal places
    if decimal_places is not None:
        str_value = str(value)
        if '.' in str_value:
            actual_decimals = len(str_value.split('.')[1])
            if actual_decimals > decimal_places:
                raise ValidationError(
                    error_msg or f"{field_name} must have at most {decimal_places} decimal places",
                    field_name
                )

    return num


def validate_integer(
    value: Union[str, int],
    field_name: str = "Value",
    error_msg: Optional[str] = None,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    allow_negative: bool = True
) -> int:
    """
    Validate an integer value.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        error_msg: Custom error message
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_negative: Whether negative values are allowed

    Returns:
        Validated integer value

    Raises:
        ValidationError: If value is not a valid integer or out of range
    """
    return int(validate_numeric(
        value,
        field_name=field_name,
        error_msg=error_msg,
        min_value=min_value,
        max_value=max_value,
        allow_negative=allow_negative,
        return_type=int
    ))


def validate_student_id(
    student_id: str,
    field_name: str = "Student ID",
    error_msg: Optional[str] = None
) -> str:
    """
    Validate a student ID.

    Args:
        student_id: The student ID to validate
        field_name: Name of the field for error messages
        error_msg: Custom error message

    Returns:
        The validated student ID (uppercase)

    Raises:
        ValidationError: If student ID format is invalid
    """
    if not student_id or not isinstance(student_id, str):
        raise ValidationError(
            error_msg or f"{field_name} is required",
            field_name
        )

    student_id = student_id.strip().upper()

    if not STUDENT_ID_PATTERN.match(student_id):
        raise ValidationError(
            error_msg or f"Invalid student ID format: {student_id}. "
            "Must start with a letter and be 5-20 alphanumeric characters.",
            field_name
        )

    return student_id


def validate_username(
    username: str,
    field_name: str = "Username",
    error_msg: Optional[str] = None
) -> str:
    """
    Validate a username.

    Args:
        username: The username to validate
        field_name: Name of the field for error messages
        error_msg: Custom error message

    Returns:
        The validated username (lowercase)

    Raises:
        ValidationError: If username format is invalid
    """
    if not username or not isinstance(username, str):
        raise ValidationError(
            error_msg or f"{field_name} is required",
            field_name
        )

    username = username.strip().lower()

    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            error_msg or f"Invalid username format: {username}. "
            "Must start with a letter, be 3-30 characters, and contain only "
            "letters, numbers, underscores, and periods.",
            field_name
        )

    return username


def validate_choice(
    value: str,
    choices: List[str],
    field_name: str = "Selection",
    error_msg: Optional[str] = None,
    case_sensitive: bool = False
) -> str:
    """
    Validate that a value is one of the allowed choices.

    Args:
        value: The value to validate
        choices: List of allowed choices
        field_name: Name of the field for error messages
        error_msg: Custom error message
        case_sensitive: Whether comparison should be case-sensitive

    Returns:
        The validated value (matching the case in choices if not case-sensitive)

    Raises:
        ValidationError: If value is not in choices
    """
    if not value or not isinstance(value, str):
        raise ValidationError(
            error_msg or f"{field_name} is required",
            field_name
        )

    value = value.strip()

    if case_sensitive:
        if value not in choices:
            raise ValidationError(
                error_msg or f"Invalid {field_name.lower()}: {value}. "
                f"Must be one of: {', '.join(choices)}",
                field_name
            )
        return value
    else:
        value_lower = value.lower()
        for choice in choices:
            if choice.lower() == value_lower:
                return choice  # Return the original case from choices
        raise ValidationError(
            error_msg or f"Invalid {field_name.lower()}: {value}. "
            f"Must be one of: {', '.join(choices)}",
            field_name
        )


def validate_length(
    value: str,
    field_name: str = "Value",
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    error_msg: Optional[str] = None
) -> str:
    """
    Validate the length of a string.

    Args:
        value: The string to validate
        field_name: Name of the field for error messages
        min_length: Minimum length
        max_length: Maximum length
        error_msg: Custom error message

    Returns:
        The validated string

    Raises:
        ValidationError: If length is out of range
    """
    if not isinstance(value, str):
        raise ValidationError(
            error_msg or f"{field_name} must be a string",
            field_name
        )

    value = value.strip()

    if min_length is not None and len(value) < min_length:
        raise ValidationError(
            error_msg or f"{field_name} must be at least {min_length} characters",
            field_name
        )

    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            error_msg or f"{field_name} must be at most {max_length} characters",
            field_name
        )

    return value


def validate_pattern(
    value: str,
    pattern: Union[str, re.Pattern],
    field_name: str = "Value",
    error_msg: Optional[str] = None
) -> str:
    """
    Validate a string against a regex pattern.

    Args:
        value: The string to validate
        pattern: Regex pattern (string or compiled pattern)
        field_name: Name of the field for error messages
        error_msg: Custom error message

    Returns:
        The validated string

    Raises:
        ValidationError: If pattern doesn't match
    """
    if not value or not isinstance(value, str):
        raise ValidationError(
            error_msg or f"{field_name} is required",
            field_name
        )

    value = value.strip()

    if isinstance(pattern, str):
        pattern = re.compile(pattern)

    if not pattern.match(value):
        raise ValidationError(
            error_msg or f"Invalid format for {field_name}: {value}",
            field_name
        )

    return value


def validate_money(
    value: Union[str, float, Decimal],
    field_name: str = "Amount",
    error_msg: Optional[str] = None,
    min_value: float = 0.0,
    max_value: Optional[float] = None,
    currency_symbol: Optional[str] = None
) -> Decimal:
    """
    Validate a monetary amount.

    Args:
        value: The amount to validate
        field_name: Name of the field for error messages
        error_msg: Custom error message
        min_value: Minimum allowed amount
        max_value: Maximum allowed amount
        currency_symbol: Currency symbol to strip if present

    Returns:
        Validated amount as Decimal

    Raises:
        ValidationError: If amount is invalid
    """
    if isinstance(value, str):
        value = value.strip()
        # Remove currency symbol if present
        if currency_symbol and value.startswith(currency_symbol):
            value = value[len(currency_symbol):].strip()
        # Remove common currency symbols
        value = value.lstrip('$£€¥₹')

    return validate_numeric(
        value,
        field_name=field_name,
        error_msg=error_msg,
        min_value=min_value,
        max_value=max_value,
        allow_negative=False,
        decimal_places=2,
        return_type=Decimal
    )


def validate_percentage(
    value: Union[str, float],
    field_name: str = "Percentage",
    error_msg: Optional[str] = None,
    min_value: float = 0.0,
    max_value: float = 100.0
) -> float:
    """
    Validate a percentage value.

    Args:
        value: The percentage to validate
        field_name: Name of the field for error messages
        error_msg: Custom error message
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Validated percentage as float

    Raises:
        ValidationError: If percentage is invalid
    """
    if isinstance(value, str):
        value = value.strip().rstrip('%')

    return validate_numeric(
        value,
        field_name=field_name,
        error_msg=error_msg,
        min_value=min_value,
        max_value=max_value,
        allow_negative=False,
        return_type=float
    )


# Convenience function for CLI input validation
def get_validated_input(
    prompt: str,
    validator: Callable[[str], T],
    error_msg: str = "Invalid input. Please try again.",
    max_attempts: int = 3
) -> Optional[T]:
    """
    Get validated input from the user with retry logic.

    Args:
        prompt: The prompt to display
        validator: Validation function to apply
        error_msg: Error message to display on invalid input
        max_attempts: Maximum number of attempts

    Returns:
        Validated input or None if max attempts exceeded
    """
    for attempt in range(max_attempts):
        try:
            value = input(prompt).strip()
            return validator(value)
        except ValidationError as e:
            remaining = max_attempts - attempt - 1
            if remaining > 0:
                print(f"{e}. {remaining} attempt(s) remaining.")
            else:
                print(f"{error_msg}")
    return None


# =============================================================================
# Boolean Helper Functions for GUI Usage
# =============================================================================
# These functions return True/False instead of raising exceptions,
# making them easier to use in GUI code where try/except is cumbersome.

def is_valid_email(email: str) -> bool:
    """
    Check if email format is valid.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    email = email.strip().lower()
    return bool(EMAIL_PATTERN.match(email)) and len(email) <= 254


def is_valid_phone(phone: str, min_digits: int = 7, max_digits: int = 15) -> bool:
    """
    Check if phone number format is valid.

    Args:
        phone: Phone number to validate
        min_digits: Minimum number of digits required
        max_digits: Maximum number of digits allowed

    Returns:
        True if valid phone format, False otherwise
    """
    if not phone or not isinstance(phone, str):
        return False
    phone = phone.strip()
    if not PHONE_PATTERN.match(phone):
        return False
    digits = re.sub(r'[^0-9]', '', phone)
    return min_digits <= len(digits) <= max_digits


def is_valid_date(
    date_str: str,
    formats: Optional[List[str]] = None
) -> bool:
    """
    Check if date string is valid.

    Args:
        date_str: Date string to validate
        formats: List of date formats to try (defaults to DATE_FORMATS)

    Returns:
        True if valid date format, False otherwise
    """
    if not date_str or not isinstance(date_str, str):
        return False
    date_str = date_str.strip()
    formats_to_try = formats or DATE_FORMATS
    for fmt in formats_to_try:
        try:
            datetime.strptime(date_str, fmt)
            return True
        except ValueError:
            continue
    return False


def is_valid_datetime(
    datetime_str: str,
    format: str = "%Y-%m-%d %H:%M:%S"
) -> bool:
    """
    Check if datetime string is valid.

    Args:
        datetime_str: Datetime string to validate
        format: Expected datetime format

    Returns:
        True if valid datetime format, False otherwise
    """
    if not datetime_str or not isinstance(datetime_str, str):
        return False
    try:
        datetime.strptime(datetime_str.strip(), format)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def parse_date_safe(
    date_str: str,
    format: str = "%Y-%m-%d"
) -> Tuple[bool, Optional[datetime]]:
    """
    Parse date string safely, returning tuple with validity and parsed datetime.

    This is useful for GUI code that needs both the validation result
    and the parsed datetime object.

    Args:
        date_str: Date string to parse
        format: Expected date format

    Returns:
        Tuple of (is_valid, datetime_object or None)
    """
    if not date_str or not isinstance(date_str, str):
        return False, None
    try:
        date_obj = datetime.strptime(date_str.strip(), format)
        return True, date_obj
    except (ValueError, AttributeError, TypeError):
        return False, None


def parse_datetime_safe(
    datetime_str: str,
    format: str = "%Y-%m-%d %H:%M:%S"
) -> Tuple[bool, Optional[datetime]]:
    """
    Parse datetime string safely, returning tuple with validity and parsed datetime.

    This is useful for GUI code that needs both the validation result
    and the parsed datetime object.

    Args:
        datetime_str: Datetime string to parse
        format: Expected datetime format

    Returns:
        Tuple of (is_valid, datetime_object or None)
    """
    if not datetime_str or not isinstance(datetime_str, str):
        return False, None
    try:
        dt_obj = datetime.strptime(datetime_str.strip(), format)
        return True, dt_obj
    except (ValueError, AttributeError, TypeError):
        return False, None


# =============================================================================
# Enhanced Input Validator with Length Limits and XSS Protection
# =============================================================================

class InputValidator:
    """
    Enhanced input validator with comprehensive length limits and security checks.

    This class provides centralized validation with:
    - Configurable maximum lengths for common field types
    - XSS pattern detection
    - SQL injection pattern detection
    - Null byte removal
    - Whitespace normalization

    Usage:
        from education_system.post_18.university_system.modules.shared.utils.input_validation import InputValidator

        # Validate with field type
        result = InputValidator.validate_with_length(user_input, 'email')
        if result['valid']:
            safe_email = result['sanitized']
        else:
            print(result['error'])

        # Validate with custom max length
        result = InputValidator.validate_with_length(bio, 'description', custom_max=1000)
    """

    # Maximum lengths for common fields (based on RFC standards and practical limits)
    MAX_LENGTHS = {
        'username': 30,
        'email': 254,           # RFC 5321
        'password': 128,
        'name': 100,
        'first_name': 50,
        'last_name': 50,
        'full_name': 100,
        'address': 500,
        'address_line': 200,
        'city': 100,
        'state': 100,
        'country': 100,
        'postal_code': 20,
        'zip_code': 20,
        'description': 2000,
        'short_description': 500,
        'notes': 5000,
        'comment': 2000,
        'message': 5000,
        'phone': 20,
        'student_id': 20,
        'employee_id': 20,
        'course_code': 20,
        'course_name': 200,
        'department': 100,
        'title': 200,
        'subject': 200,
        'url': 2048,            # Practical browser limit
        'filename': 255,        # Common filesystem limit
        'search_query': 200,
        'tag': 50,
        'category': 100,
        'ssn': 11,              # US Social Security Number with dashes
        'passport': 20,
        'license_number': 30,
        'credit_card': 19,      # With spaces
        'cvv': 4,
        'bank_account': 34,     # IBAN max length
        'routing_number': 9,
    }

    # XSS attack patterns to detect
    XSS_PATTERNS = [
        '<script',
        '</script>',
        'javascript:',
        'vbscript:',
        'onload=',
        'onerror=',
        'onclick=',
        'onmouseover=',
        'onfocus=',
        'onblur=',
        'onchange=',
        'onsubmit=',
        'onkeydown=',
        'onkeyup=',
        'onkeypress=',
        '<iframe',
        '</iframe>',
        '<object',
        '</object>',
        '<embed',
        '</embed>',
        '<svg',
        '<img src=',
        '<body',
        '<meta',
        '<link',
        '<style',
        'expression(',
        'url(',
        'data:text/html',
        'data:application',
    ]

    # SQL injection patterns to detect
    SQL_INJECTION_PATTERNS = [
        "'; --",
        "' OR '",
        "' OR 1=1",
        "'; DROP",
        "'; DELETE",
        "'; UPDATE",
        "'; INSERT",
        "UNION SELECT",
        "UNION ALL SELECT",
        "/*",
        "*/",
        "@@",
        "CHAR(",
        "NCHAR(",
        "VARCHAR(",
        "EXEC(",
        "EXECUTE(",
        "xp_",
        "sp_",
    ]

    @classmethod
    def get_max_length(cls, field_type: str) -> int:
        """
        Get the maximum length for a field type.

        Args:
            field_type: The type of field

        Returns:
            Maximum allowed length (defaults to 255 if not specified)
        """
        return cls.MAX_LENGTHS.get(field_type.lower(), 255)

    @classmethod
    def sanitize(cls, value: str) -> str:
        """
        Sanitize a string value.

        Removes:
        - Leading/trailing whitespace
        - Null bytes
        - Control characters (except newlines and tabs)

        Args:
            value: The string to sanitize

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value) if value is not None else ''

        # Remove null bytes
        sanitized = value.replace('\x00', '')

        # Remove other control characters except newlines and tabs
        sanitized = ''.join(
            char for char in sanitized
            if char in '\n\r\t' or (ord(char) >= 32 and ord(char) != 127)
        )

        # Strip leading/trailing whitespace
        sanitized = sanitized.strip()

        return sanitized

    @classmethod
    def contains_xss_patterns(cls, value: str) -> bool:
        """
        Check for common XSS attack patterns.

        Args:
            value: The string to check

        Returns:
            True if XSS patterns detected, False otherwise
        """
        if not value:
            return False

        value_lower = value.lower()
        return any(pattern.lower() in value_lower for pattern in cls.XSS_PATTERNS)

    @classmethod
    def contains_sql_injection_patterns(cls, value: str) -> bool:
        """
        Check for common SQL injection patterns.

        Note: This is a defense-in-depth measure. Always use parameterized
        queries as the primary defense against SQL injection.

        Args:
            value: The string to check

        Returns:
            True if SQL injection patterns detected, False otherwise
        """
        if not value:
            return False

        value_upper = value.upper()
        return any(pattern.upper() in value_upper for pattern in cls.SQL_INJECTION_PATTERNS)

    @classmethod
    def validate_with_length(
        cls,
        value: str,
        field_type: str,
        custom_max: int = None,
        allow_empty: bool = False,
        check_xss: bool = True,
        check_sql_injection: bool = True,
        field_name: str = None,
    ) -> dict:
        """
        Validate input with length checking and security validation.

        Performs:
        1. Null/empty check
        2. Sanitization (strip, remove null bytes)
        3. Length validation
        4. XSS pattern detection
        5. SQL injection pattern detection
        6. Type-specific validation (email, username, etc.)

        Args:
            value: The input value to validate
            field_type: Type of field (email, username, password, etc.)
            custom_max: Custom maximum length (overrides MAX_LENGTHS)
            allow_empty: Whether empty values are allowed
            check_xss: Whether to check for XSS patterns
            check_sql_injection: Whether to check for SQL injection patterns
            field_name: Display name for error messages (defaults to field_type)

        Returns:
            Dictionary with keys:
            - 'valid': bool - Whether validation passed
            - 'error': str - Error message if invalid (only if valid=False)
            - 'sanitized': str - Sanitized value (only if valid=True)
            - 'warnings': list - Non-fatal warnings (optional)
        """
        display_name = field_name or field_type.replace('_', ' ').title()

        # Check for None
        if value is None:
            if allow_empty:
                return {'valid': True, 'sanitized': '', 'warnings': []}
            return {'valid': False, 'error': f'{display_name} is required'}

        # Ensure string type
        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception:
                return {'valid': False, 'error': f'{display_name} must be a string'}

        # Sanitize
        sanitized = cls.sanitize(value)

        # Check for empty after sanitization
        if not sanitized:
            if allow_empty:
                return {'valid': True, 'sanitized': '', 'warnings': []}
            return {'valid': False, 'error': f'{display_name} is required'}

        # Check length
        max_length = custom_max or cls.get_max_length(field_type)
        if len(sanitized) > max_length:
            return {
                'valid': False,
                'error': f'{display_name} exceeds maximum length of {max_length} characters'
            }

        warnings = []

        # Check for XSS patterns
        if check_xss and cls.contains_xss_patterns(sanitized):
            return {
                'valid': False,
                'error': f'{display_name} contains potentially unsafe content'
            }

        # Check for SQL injection patterns
        if check_sql_injection and cls.contains_sql_injection_patterns(sanitized):
            return {
                'valid': False,
                'error': f'{display_name} contains potentially unsafe content'
            }

        # Type-specific validation
        field_type_lower = field_type.lower()

        if field_type_lower == 'email':
            if not is_valid_email(sanitized):
                return {'valid': False, 'error': 'Invalid email format'}
            sanitized = sanitized.lower()

        elif field_type_lower == 'username':
            if not USERNAME_PATTERN.match(sanitized):
                return {
                    'valid': False,
                    'error': 'Username must start with a letter and contain only '
                             'letters, numbers, underscores, and periods (3-30 chars)'
                }
            sanitized = sanitized.lower()

        elif field_type_lower == 'phone':
            if not is_valid_phone(sanitized):
                return {'valid': False, 'error': 'Invalid phone number format'}

        elif field_type_lower == 'student_id':
            if not STUDENT_ID_PATTERN.match(sanitized.upper()):
                return {
                    'valid': False,
                    'error': 'Student ID must start with a letter and be 5-20 '
                             'alphanumeric characters'
                }
            sanitized = sanitized.upper()

        elif field_type_lower == 'url':
            # Basic URL validation
            if not (sanitized.startswith('http://') or sanitized.startswith('https://')):
                return {'valid': False, 'error': 'URL must start with http:// or https://'}

        elif field_type_lower == 'postal_code' or field_type_lower == 'zip_code':
            # Allow alphanumeric and spaces/hyphens for international postal codes
            if not re.match(r'^[A-Za-z0-9\s\-]{2,20}$', sanitized):
                return {'valid': False, 'error': 'Invalid postal/zip code format'}

        return {
            'valid': True,
            'sanitized': sanitized,
            'warnings': warnings if warnings else []
        }

    @classmethod
    def validate_multiple(
        cls,
        fields: dict,
        field_types: dict = None,
        allow_empty_fields: set = None,
    ) -> dict:
        """
        Validate multiple fields at once.

        Args:
            fields: Dictionary of field_name: value pairs
            field_types: Dictionary of field_name: field_type mappings
                        (defaults to field_name as field_type)
            allow_empty_fields: Set of field names that can be empty

        Returns:
            Dictionary with keys:
            - 'valid': bool - Whether all validations passed
            - 'errors': dict - Field-specific error messages
            - 'sanitized': dict - Sanitized values for valid fields
        """
        field_types = field_types or {}
        allow_empty_fields = allow_empty_fields or set()

        errors = {}
        sanitized = {}

        for field_name, value in fields.items():
            field_type = field_types.get(field_name, field_name)
            allow_empty = field_name in allow_empty_fields

            result = cls.validate_with_length(
                value,
                field_type,
                allow_empty=allow_empty,
                field_name=field_name
            )

            if result['valid']:
                sanitized[field_name] = result['sanitized']
            else:
                errors[field_name] = result['error']

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'sanitized': sanitized
        }

    @classmethod
    def escape_html(cls, value: str) -> str:
        """
        Escape HTML special characters for safe display.

        Args:
            value: String to escape

        Returns:
            HTML-escaped string
        """
        if not value:
            return ''

        html_escape_table = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;',
        }

        return ''.join(html_escape_table.get(c, c) for c in str(value))

    @classmethod
    def truncate(cls, value: str, max_length: int, suffix: str = '...') -> str:
        """
        Truncate a string to a maximum length.

        Args:
            value: String to truncate
            max_length: Maximum length (including suffix)
            suffix: Suffix to add if truncated

        Returns:
            Truncated string
        """
        if not value or len(value) <= max_length:
            return value or ''

        return value[:max_length - len(suffix)] + suffix


# Convenience instance for simpler usage
input_validator = InputValidator()
