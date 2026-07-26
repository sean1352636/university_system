"""
CLI Input Validators - Common validation functions for Staff HR CLI menus.

Provides consistent input validation and error messages across all CLI menus.
"""

import re
from datetime import datetime
from typing import Any, List, Optional, Tuple, Callable


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_date(value: str, field_name: str = "Date",
                  allow_empty: bool = False) -> Optional[str]:
    """
    Validate date format (YYYY-MM-DD).

    Args:
        value: The input value
        field_name: Name of the field for error messages
        allow_empty: Whether to allow empty/None values

    Returns:
        The validated date string or None if empty and allowed

    Raises:
        ValidationError: If date format is invalid
    """
    value = value.strip() if value else ""

    if not value:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} is required.")

    # Check format
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        raise ValidationError(f"{field_name} must be in YYYY-MM-DD format.")

    # Check if valid date
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise ValidationError(f"{field_name} is not a valid date.")

    return value


def validate_date_range(start_date: str, end_date: str,
                        start_field: str = "Start date",
                        end_field: str = "End date") -> Tuple[str, str]:
    """
    Validate that end date is after start date.

    Args:
        start_date: Start date string
        end_date: End date string
        start_field: Name of start date field
        end_field: Name of end date field

    Returns:
        Tuple of validated (start_date, end_date)

    Raises:
        ValidationError: If dates are invalid or end is before start
    """
    start = validate_date(start_date, start_field)
    end = validate_date(end_date, end_field)

    start_dt = datetime.strptime(start, '%Y-%m-%d')
    end_dt = datetime.strptime(end, '%Y-%m-%d')

    if end_dt < start_dt:
        raise ValidationError(f"{end_field} cannot be before {start_field}.")

    return start, end


def validate_number(value: str, field_name: str = "Value",
                   allow_empty: bool = False,
                   min_value: float = None,
                   max_value: float = None,
                   allow_decimal: bool = True) -> Optional[float]:
    """
    Validate numeric input.

    Args:
        value: The input value
        field_name: Name of the field for error messages
        allow_empty: Whether to allow empty/None values
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_decimal: Whether to allow decimal values

    Returns:
        The validated number or None if empty and allowed

    Raises:
        ValidationError: If number format is invalid
    """
    value = value.strip() if value else ""

    if not value:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} is required.")

    try:
        if allow_decimal:
            num = float(value)
        else:
            num = int(value)
    except ValueError:
        type_name = "number" if allow_decimal else "integer"
        raise ValidationError(f"{field_name} must be a valid {type_name}.")

    if min_value is not None and num < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value}.")

    if max_value is not None and num > max_value:
        raise ValidationError(f"{field_name} cannot exceed {max_value}.")

    return num


def validate_integer(value: str, field_name: str = "Value",
                    allow_empty: bool = False,
                    min_value: int = None,
                    max_value: int = None) -> Optional[int]:
    """
    Validate integer input.

    Args:
        value: The input value
        field_name: Name of the field for error messages
        allow_empty: Whether to allow empty/None values
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        The validated integer or None if empty and allowed

    Raises:
        ValidationError: If integer format is invalid
    """
    result = validate_number(value, field_name, allow_empty,
                            min_value, max_value, allow_decimal=False)
    return int(result) if result is not None else None


def validate_required(value: str, field_name: str = "Field") -> str:
    """
    Validate that a field is not empty.

    Args:
        value: The input value
        field_name: Name of the field for error messages

    Returns:
        The validated non-empty string

    Raises:
        ValidationError: If value is empty
    """
    value = value.strip() if value else ""

    if not value:
        raise ValidationError(f"{field_name} is required.")

    return value


def validate_choice(value: str, choices: List[str],
                   field_name: str = "Selection",
                   case_sensitive: bool = False,
                   allow_empty: bool = False) -> Optional[str]:
    """
    Validate that value is one of the allowed choices.

    Args:
        value: The input value
        choices: List of valid choices
        field_name: Name of the field for error messages
        case_sensitive: Whether comparison is case-sensitive
        allow_empty: Whether to allow empty/None values

    Returns:
        The validated choice (matching case of choices list)

    Raises:
        ValidationError: If value is not in choices
    """
    value = value.strip() if value else ""

    if not value:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} is required.")

    if case_sensitive:
        if value in choices:
            return value
    else:
        value_lower = value.lower()
        for choice in choices:
            if choice.lower() == value_lower:
                return choice

    choices_str = ", ".join(choices)
    raise ValidationError(f"{field_name} must be one of: {choices_str}")


def validate_email(value: str, field_name: str = "Email",
                  allow_empty: bool = False) -> Optional[str]:
    """
    Validate email format.

    Args:
        value: The input value
        field_name: Name of the field for error messages
        allow_empty: Whether to allow empty/None values

    Returns:
        The validated email string

    Raises:
        ValidationError: If email format is invalid
    """
    value = value.strip() if value else ""

    if not value:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} is required.")

    # Basic email pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, value):
        raise ValidationError(f"{field_name} is not a valid email address.")

    return value


def validate_currency(value: str, field_name: str = "Amount",
                     allow_empty: bool = False,
                     min_value: float = 0) -> Optional[float]:
    """
    Validate currency/money input.

    Args:
        value: The input value (may include currency symbols)
        field_name: Name of the field for error messages
        allow_empty: Whether to allow empty/None values
        min_value: Minimum allowed value

    Returns:
        The validated amount as float

    Raises:
        ValidationError: If currency format is invalid
    """
    value = value.strip() if value else ""

    if not value:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} is required.")

    # Remove common currency symbols and commas
    cleaned = re.sub(r'[$,]', '', value)

    try:
        amount = float(cleaned)
    except ValueError:
        raise ValidationError(f"{field_name} must be a valid amount.")

    if amount < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value}.")

    return round(amount, 2)


def validate_rating(value: str, field_name: str = "Rating",
                   allow_empty: bool = False,
                   min_rating: int = 1,
                   max_rating: int = 5) -> Optional[int]:
    """
    Validate a rating value.

    Args:
        value: The input value
        field_name: Name of the field for error messages
        allow_empty: Whether to allow empty/None values
        min_rating: Minimum rating value
        max_rating: Maximum rating value

    Returns:
        The validated rating as integer

    Raises:
        ValidationError: If rating is invalid
    """
    return validate_integer(value, field_name, allow_empty, min_rating, max_rating)


def validate_confirmation(value: str,
                         affirmative: List[str] = None) -> bool:
    """
    Validate a yes/no confirmation.

    Args:
        value: The input value
        affirmative: List of values that mean "yes" (default: ['yes', 'y'])

    Returns:
        True if affirmative, False otherwise
    """
    if affirmative is None:
        affirmative = ['yes', 'y']

    value = value.strip().lower() if value else ""
    return value in [a.lower() for a in affirmative]


def validate_user_id(value: str, field_name: str = "User ID",
                    allow_empty: bool = False) -> Optional[str]:
    """
    Validate a user ID format.

    Args:
        value: The input value
        field_name: Name of the field for error messages
        allow_empty: Whether to allow empty/None values

    Returns:
        The validated user ID

    Raises:
        ValidationError: If user ID format is invalid
    """
    value = value.strip() if value else ""

    if not value:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} is required.")

    # Basic alphanumeric with underscores/dashes
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        raise ValidationError(
            f"{field_name} can only contain letters, numbers, underscores, and dashes."
        )

    if len(value) < 2:
        raise ValidationError(f"{field_name} must be at least 2 characters.")

    return value


def validate_text_length(value: str, field_name: str = "Text",
                        allow_empty: bool = False,
                        min_length: int = None,
                        max_length: int = None) -> Optional[str]:
    """
    Validate text length.

    Args:
        value: The input value
        field_name: Name of the field for error messages
        allow_empty: Whether to allow empty/None values
        min_length: Minimum length
        max_length: Maximum length

    Returns:
        The validated text

    Raises:
        ValidationError: If length constraints are violated
    """
    value = value.strip() if value else ""

    if not value:
        if allow_empty:
            return None
        raise ValidationError(f"{field_name} is required.")

    if min_length and len(value) < min_length:
        raise ValidationError(f"{field_name} must be at least {min_length} characters.")

    if max_length and len(value) > max_length:
        raise ValidationError(f"{field_name} cannot exceed {max_length} characters.")

    return value


# Input helpers with validation

def get_validated_input(prompt: str, validator: Callable,
                       **validator_kwargs) -> Any:
    """
    Get validated input from user, re-prompting on error.

    Args:
        prompt: The input prompt
        validator: Validation function to call
        **validator_kwargs: Arguments to pass to validator

    Returns:
        The validated value
    """
    while True:
        value = input(prompt).strip()
        try:
            return validator(value, **validator_kwargs)
        except ValidationError as e:
            print(f"Error: {e}")


def get_date_input(prompt: str, field_name: str = "Date",
                  allow_empty: bool = False) -> Optional[str]:
    """Get validated date input."""
    return get_validated_input(prompt, validate_date,
                               field_name=field_name, allow_empty=allow_empty)


def get_number_input(prompt: str, field_name: str = "Value",
                    allow_empty: bool = False,
                    min_value: float = None,
                    max_value: float = None) -> Optional[float]:
    """Get validated number input."""
    return get_validated_input(prompt, validate_number,
                               field_name=field_name, allow_empty=allow_empty,
                               min_value=min_value, max_value=max_value)


def get_integer_input(prompt: str, field_name: str = "Value",
                     allow_empty: bool = False,
                     min_value: int = None,
                     max_value: int = None) -> Optional[int]:
    """Get validated integer input."""
    return get_validated_input(prompt, validate_integer,
                               field_name=field_name, allow_empty=allow_empty,
                               min_value=min_value, max_value=max_value)


def get_choice_input(prompt: str, choices: List[str],
                    field_name: str = "Selection",
                    allow_empty: bool = False) -> Optional[str]:
    """Get validated choice input."""
    return get_validated_input(prompt, validate_choice,
                               choices=choices, field_name=field_name,
                               allow_empty=allow_empty)


def get_required_input(prompt: str, field_name: str = "Field") -> str:
    """Get validated required input."""
    return get_validated_input(prompt, validate_required, field_name=field_name)


def get_currency_input(prompt: str, field_name: str = "Amount",
                      allow_empty: bool = False) -> Optional[float]:
    """Get validated currency input."""
    return get_validated_input(prompt, validate_currency,
                               field_name=field_name, allow_empty=allow_empty)


def get_rating_input(prompt: str, field_name: str = "Rating",
                    allow_empty: bool = False,
                    min_rating: int = 1,
                    max_rating: int = 5) -> Optional[int]:
    """Get validated rating input."""
    return get_validated_input(prompt, validate_rating,
                               field_name=field_name, allow_empty=allow_empty,
                               min_rating=min_rating, max_rating=max_rating)


def get_confirmation(prompt: str, default: bool = False) -> bool:
    """
    Get yes/no confirmation from user.

    Args:
        prompt: The confirmation prompt
        default: Default value if user just presses Enter

    Returns:
        True for yes, False for no
    """
    default_str = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({default_str}): ").strip()

    if not value:
        return default

    return validate_confirmation(value)
