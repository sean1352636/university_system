"""
Validation Rules

Provides a declarative validation system using rule objects.
Allows defining validation schemas for forms and data objects.
"""

import re
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Any, Callable, Dict, List, Optional, Union, Type
from dataclasses import dataclass


@dataclass
class RuleResult:
    """Result from a single rule check."""
    is_valid: bool
    error: Optional[str] = None


class ValidationRule(ABC):
    """
    Base class for validation rules.

    Subclass this to create custom validation rules.
    """

    def __init__(self, message: Optional[str] = None):
        self.custom_message = message

    @abstractmethod
    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        """
        Validate a value.

        Args:
            value: Value to validate
            field_name: Name of the field (for error messages)

        Returns:
            RuleResult
        """
        pass

    def get_message(self, field_name: str, default: str) -> str:
        """Get error message, using custom if provided."""
        if self.custom_message:
            return self.custom_message.format(field=field_name)
        return default.format(field=field_name)


class Required(ValidationRule):
    """Ensure a value is present and not empty."""

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "" or (isinstance(value, (list, dict)) and len(value) == 0):
            return RuleResult(
                False,
                self.get_message(field_name, "{field} is required")
            )
        return RuleResult(True)


class MinLength(ValidationRule):
    """Ensure string has minimum length."""

    def __init__(self, min_length: int, message: Optional[str] = None):
        super().__init__(message)
        self.min_length = min_length

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None:
            return RuleResult(True)  # Use Required for checking presence

        if len(str(value)) < self.min_length:
            return RuleResult(
                False,
                self.get_message(field_name, f"{{field}} must be at least {self.min_length} characters")
            )
        return RuleResult(True)


class MaxLength(ValidationRule):
    """Ensure string doesn't exceed maximum length."""

    def __init__(self, max_length: int, message: Optional[str] = None):
        super().__init__(message)
        self.max_length = max_length

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None:
            return RuleResult(True)

        if len(str(value)) > self.max_length:
            return RuleResult(
                False,
                self.get_message(field_name, f"{{field}} cannot exceed {self.max_length} characters")
            )
        return RuleResult(True)


class Pattern(ValidationRule):
    """Validate against a regex pattern."""

    def __init__(self, pattern: str, message: Optional[str] = None, flags: int = 0):
        super().__init__(message)
        self.pattern = re.compile(pattern, flags)

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None:
            return RuleResult(True)

        if not self.pattern.match(str(value)):
            return RuleResult(
                False,
                self.get_message(field_name, "{field} has an invalid format")
            )
        return RuleResult(True)


class Email(ValidationRule):
    """Validate email format."""

    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        if not self.EMAIL_PATTERN.match(str(value)):
            return RuleResult(
                False,
                self.get_message(field_name, "{field} must be a valid email address")
            )
        return RuleResult(True)


class Phone(ValidationRule):
    """Validate phone number format."""

    PHONE_PATTERN = re.compile(r'^\+?[\d\s\-\(\)]{10,}$')

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        # Remove formatting for validation
        cleaned = re.sub(r'[\s\-\(\)]', '', str(value))

        if not cleaned.replace('+', '').isdigit() or len(cleaned) < 10:
            return RuleResult(
                False,
                self.get_message(field_name, "{field} must be a valid phone number")
            )
        return RuleResult(True)


class DateFormat(ValidationRule):
    """Validate date format and optionally range."""

    def __init__(
        self,
        formats: List[str] = None,
        min_date: date = None,
        max_date: date = None,
        message: Optional[str] = None
    ):
        super().__init__(message)
        self.formats = formats or ['%Y-%m-%d']
        self.min_date = min_date
        self.max_date = max_date

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        # If already a date/datetime
        if isinstance(value, (date, datetime)):
            parsed_date = value if isinstance(value, date) else value.date()
        else:
            parsed_date = None
            for fmt in self.formats:
                try:
                    parsed_date = datetime.strptime(str(value), fmt).date()
                    break
                except ValueError:
                    continue

        if parsed_date is None:
            return RuleResult(
                False,
                self.get_message(field_name, "{field} must be a valid date")
            )

        if self.min_date and parsed_date < self.min_date:
            return RuleResult(
                False,
                f"{field_name} must be on or after {self.min_date}"
            )

        if self.max_date and parsed_date > self.max_date:
            return RuleResult(
                False,
                f"{field_name} must be on or before {self.max_date}"
            )

        return RuleResult(True)


class InRange(ValidationRule):
    """Validate numeric value is within range."""

    def __init__(
        self,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        message: Optional[str] = None
    ):
        super().__init__(message)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        try:
            num_value = float(value)
        except (ValueError, TypeError):
            return RuleResult(
                False,
                self.get_message(field_name, "{field} must be a number")
            )

        if self.min_value is not None and num_value < self.min_value:
            return RuleResult(
                False,
                f"{field_name} must be at least {self.min_value}"
            )

        if self.max_value is not None and num_value > self.max_value:
            return RuleResult(
                False,
                f"{field_name} cannot exceed {self.max_value}"
            )

        return RuleResult(True)


class OneOf(ValidationRule):
    """Validate value is one of allowed choices."""

    def __init__(self, choices: List[Any], message: Optional[str] = None):
        super().__init__(message)
        self.choices = choices

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        if value not in self.choices:
            choices_str = ", ".join(str(c) for c in self.choices[:5])
            if len(self.choices) > 5:
                choices_str += "..."
            return RuleResult(
                False,
                self.get_message(field_name, f"{{field}} must be one of: {choices_str}")
            )
        return RuleResult(True)


class Custom(ValidationRule):
    """Custom validation using a function."""

    def __init__(
        self,
        validator: Callable[[Any], bool],
        message: str = "{field} is invalid"
    ):
        super().__init__(message)
        self.validator = validator

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        try:
            if self.validator(value):
                return RuleResult(True)
            return RuleResult(
                False,
                self.get_message(field_name, self.custom_message or "{field} is invalid")
            )
        except Exception:
            return RuleResult(
                False,
                self.get_message(field_name, "{field} validation failed")
            )


class Integer(ValidationRule):
    """Validate value is an integer."""

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        try:
            int(value)
            return RuleResult(True)
        except (ValueError, TypeError):
            return RuleResult(
                False,
                self.get_message(field_name, "{field} must be a whole number")
            )


class Decimal(ValidationRule):
    """Validate value is a decimal number."""

    def __init__(self, decimal_places: Optional[int] = None, message: Optional[str] = None):
        super().__init__(message)
        self.decimal_places = decimal_places

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        try:
            float_val = float(value)

            if self.decimal_places is not None:
                str_val = str(value)
                if '.' in str_val:
                    actual_places = len(str_val.split('.')[-1])
                    if actual_places > self.decimal_places:
                        return RuleResult(
                            False,
                            f"{field_name} cannot have more than {self.decimal_places} decimal places"
                        )

            return RuleResult(True)
        except (ValueError, TypeError):
            return RuleResult(
                False,
                self.get_message(field_name, "{field} must be a number")
            )


class Alphanumeric(ValidationRule):
    """Validate value contains only letters and numbers."""

    def __init__(self, allow_underscore: bool = False, allow_hyphen: bool = False, message: Optional[str] = None):
        super().__init__(message)
        pattern = r'^[a-zA-Z0-9'
        if allow_underscore:
            pattern += '_'
        if allow_hyphen:
            pattern += '-'
        pattern += ']+$'
        self.pattern = re.compile(pattern)

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        if not self.pattern.match(str(value)):
            return RuleResult(
                False,
                self.get_message(field_name, "{field} must contain only letters and numbers")
            )
        return RuleResult(True)


class URL(ValidationRule):
    """Validate URL format."""

    URL_PATTERN = re.compile(
        r'^https?://'
        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}'
        r'(?:/[^\s]*)?$'
    )

    def validate(self, value: Any, field_name: str = "") -> RuleResult:
        if value is None or value == "":
            return RuleResult(True)

        if not self.URL_PATTERN.match(str(value)):
            return RuleResult(
                False,
                self.get_message(field_name, "{field} must be a valid URL")
            )
        return RuleResult(True)


@dataclass
class FieldValidation:
    """Configuration for validating a single field."""
    field_name: str
    rules: List[ValidationRule]
    display_name: Optional[str] = None

    def validate(self, value: Any) -> List[str]:
        """
        Validate a value against all rules.

        Returns:
            List of error messages
        """
        errors = []
        display = self.display_name or self.field_name.replace('_', ' ').title()

        for rule in self.rules:
            result = rule.validate(value, display)
            if not result.is_valid:
                errors.append(result.error)

        return errors


def validate_fields(data: Dict[str, Any], schema: Dict[str, List[ValidationRule]]) -> Dict[str, List[str]]:
    """
    Validate a dictionary of data against a schema.

    Args:
        data: Dictionary of field values
        schema: Dictionary mapping field names to list of rules

    Returns:
        Dictionary of field names to error messages

    Example:
        schema = {
            'email': [Required(), Email()],
            'age': [Required(), Integer(), InRange(18, 100)],
            'name': [Required(), MinLength(2), MaxLength(50)],
        }

        data = {
            'email': 'invalid',
            'age': 15,
            'name': ''
        }

        errors = validate_fields(data, schema)
        # {
        #     'email': ['email must be a valid email address'],
        #     'age': ['age must be at least 18'],
        #     'name': ['name is required']
        # }
    """
    errors = {}

    for field_name, rules in schema.items():
        value = data.get(field_name)
        display_name = field_name.replace('_', ' ').title()

        field_errors = []
        for rule in rules:
            result = rule.validate(value, display_name)
            if not result.is_valid:
                field_errors.append(result.error)

        if field_errors:
            errors[field_name] = field_errors

    return errors


class ValidationSchema:
    """
    Reusable validation schema for forms and data objects.

    Example:
        class StudentSchema(ValidationSchema):
            def __init__(self):
                super().__init__()
                self.add_field('student_id', [Required(), Pattern(r'^STU\d+$')])
                self.add_field('email', [Required(), Email()])
                self.add_field('gpa', [InRange(0, 4.0)])

        schema = StudentSchema()
        errors = schema.validate({
            'student_id': 'STU123',
            'email': 'student@example.com',
            'gpa': 3.5
        })
    """

    def __init__(self):
        self._fields: Dict[str, FieldValidation] = {}

    def add_field(
        self,
        field_name: str,
        rules: List[ValidationRule],
        display_name: Optional[str] = None
    ):
        """Add a field to the schema."""
        self._fields[field_name] = FieldValidation(
            field_name=field_name,
            rules=rules,
            display_name=display_name
        )

    def validate(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Validate data against the schema.

        Returns:
            Dictionary of field names to error messages
        """
        errors = {}

        for field_name, field_validation in self._fields.items():
            value = data.get(field_name)
            field_errors = field_validation.validate(value)

            if field_errors:
                errors[field_name] = field_errors

        return errors

    def is_valid(self, data: Dict[str, Any]) -> bool:
        """Check if data is valid."""
        return len(self.validate(data)) == 0


# Pre-built schemas for common entities
class StudentValidationSchema(ValidationSchema):
    """Validation schema for student data."""

    def __init__(self):
        super().__init__()
        self.add_field('first_name', [Required(), MinLength(2), MaxLength(50)], "First Name")
        self.add_field('last_name', [Required(), MinLength(2), MaxLength(50)], "Last Name")
        self.add_field('email', [Required(), Email()])
        self.add_field('phone', [Phone()])
        self.add_field('student_id', [Pattern(r'^(STU|S)?[A-Z]{0,2}\d{4,10}$', flags=re.IGNORECASE)], "Student ID")
        self.add_field('gpa', [InRange(0.0, 4.0)], "GPA")


class CourseValidationSchema(ValidationSchema):
    """Validation schema for course data."""

    def __init__(self):
        super().__init__()
        self.add_field('course_code', [Required(), Pattern(r'^[A-Z]{2,4}\d{3,4}[A-Z]?$', flags=re.IGNORECASE)], "Course Code")
        self.add_field('name', [Required(), MinLength(3), MaxLength(100)], "Course Name")
        self.add_field('credits', [Required(), Integer(), InRange(1, 12)])
        self.add_field('max_enrollment', [Integer(), InRange(1, 500)], "Max Enrollment")


class UserValidationSchema(ValidationSchema):
    """Validation schema for user accounts."""

    def __init__(self):
        super().__init__()
        self.add_field('username', [Required(), MinLength(3), MaxLength(30), Alphanumeric(allow_underscore=True)])
        self.add_field('email', [Required(), Email()])
        self.add_field('first_name', [Required(), MinLength(2), MaxLength(50)], "First Name")
        self.add_field('last_name', [Required(), MinLength(2), MaxLength(50)], "Last Name")
        self.add_field('role', [Required(), OneOf(['admin', 'staff', 'instructor', 'student', 'parent'])])
