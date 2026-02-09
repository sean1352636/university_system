"""
GUI Input Validators - Common validation functions for Staff HR GUI modules.

Provides consistent input validation and error display for Tkinter-based GUIs.
"""

import re
from datetime import datetime
from typing import Optional, List, Tuple, Any
from tkinter import messagebox


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_entry(widget, field_name: str, required: bool = True,
                   min_length: int = None, max_length: int = None) -> Optional[str]:
    """
    Validate text entry widget.

    Args:
        widget: Tkinter Entry or Text widget
        field_name: Name of the field for error messages
        required: Whether the field is required
        min_length: Minimum text length
        max_length: Maximum text length

    Returns:
        The validated text value or None if empty and not required

    Raises:
        ValidationError: If validation fails
    """
    value = widget.get().strip() if hasattr(widget, 'get') else widget.get("1.0", "end-1c").strip()

    if not value:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None

    if min_length and len(value) < min_length:
        raise ValidationError(f"{field_name} must be at least {min_length} characters.")

    if max_length and len(value) > max_length:
        raise ValidationError(f"{field_name} cannot exceed {max_length} characters.")

    return value


def validate_date_entry(widget, field_name: str = "Date",
                       required: bool = True) -> Optional[str]:
    """
    Validate date entry widget (expects YYYY-MM-DD format).

    Args:
        widget: Tkinter Entry widget
        field_name: Name of the field for error messages
        required: Whether the field is required

    Returns:
        The validated date string or None if empty and not required

    Raises:
        ValidationError: If date format is invalid
    """
    value = widget.get().strip()

    if not value:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None

    # Check format
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        raise ValidationError(f"{field_name} must be in YYYY-MM-DD format.")

    # Check if valid date
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise ValidationError(f"{field_name} is not a valid date.")

    return value


def validate_number_entry(widget, field_name: str = "Value",
                         required: bool = True,
                         min_value: float = None,
                         max_value: float = None,
                         allow_decimal: bool = True) -> Optional[float]:
    """
    Validate numeric entry widget.

    Args:
        widget: Tkinter Entry widget
        field_name: Name of the field for error messages
        required: Whether the field is required
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_decimal: Whether to allow decimal values

    Returns:
        The validated number or None if empty and not required

    Raises:
        ValidationError: If number format is invalid
    """
    value = widget.get().strip()

    if not value:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None

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


def validate_integer_entry(widget, field_name: str = "Value",
                          required: bool = True,
                          min_value: int = None,
                          max_value: int = None) -> Optional[int]:
    """
    Validate integer entry widget.

    Args:
        widget: Tkinter Entry widget
        field_name: Name of the field for error messages
        required: Whether the field is required
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        The validated integer or None if empty and not required

    Raises:
        ValidationError: If integer format is invalid
    """
    result = validate_number_entry(widget, field_name, required,
                                   min_value, max_value, allow_decimal=False)
    return int(result) if result is not None else None


def validate_currency_entry(widget, field_name: str = "Amount",
                           required: bool = True,
                           min_value: float = 0) -> Optional[float]:
    """
    Validate currency entry widget.

    Args:
        widget: Tkinter Entry widget
        field_name: Name of the field for error messages
        required: Whether the field is required
        min_value: Minimum allowed value

    Returns:
        The validated amount as float or None if empty and not required

    Raises:
        ValidationError: If currency format is invalid
    """
    value = widget.get().strip()

    if not value:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None

    # Remove common currency symbols and commas
    cleaned = re.sub(r'[$,]', '', value)

    try:
        amount = float(cleaned)
    except ValueError:
        raise ValidationError(f"{field_name} must be a valid amount.")

    if amount < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value}.")

    return round(amount, 2)


def validate_combobox(widget, field_name: str = "Selection",
                     required: bool = True) -> Optional[str]:
    """
    Validate Combobox selection.

    Args:
        widget: ttk.Combobox widget
        field_name: Name of the field for error messages
        required: Whether the field is required

    Returns:
        The selected value or None if not selected and not required

    Raises:
        ValidationError: If selection is required but not made
    """
    value = widget.get().strip()

    if not value:
        if required:
            raise ValidationError(f"Please select a {field_name.lower()}.")
        return None

    return value


def validate_rating_entry(widget, field_name: str = "Rating",
                         required: bool = True,
                         min_rating: int = 1,
                         max_rating: int = 5) -> Optional[int]:
    """
    Validate a rating entry.

    Args:
        widget: Tkinter Entry widget
        field_name: Name of the field for error messages
        required: Whether the field is required
        min_rating: Minimum rating value
        max_rating: Maximum rating value

    Returns:
        The validated rating as integer or None

    Raises:
        ValidationError: If rating is invalid
    """
    return validate_integer_entry(widget, field_name, required, min_rating, max_rating)


def validate_email_entry(widget, field_name: str = "Email",
                        required: bool = True) -> Optional[str]:
    """
    Validate email entry widget.

    Args:
        widget: Tkinter Entry widget
        field_name: Name of the field for error messages
        required: Whether the field is required

    Returns:
        The validated email or None if empty and not required

    Raises:
        ValidationError: If email format is invalid
    """
    value = widget.get().strip()

    if not value:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, value):
        raise ValidationError(f"{field_name} is not a valid email address.")

    return value


def validate_date_range(start_widget, end_widget,
                       start_name: str = "Start Date",
                       end_name: str = "End Date",
                       end_required: bool = False) -> Tuple[str, Optional[str]]:
    """
    Validate that end date is after start date.

    Args:
        start_widget: Entry widget for start date
        end_widget: Entry widget for end date
        start_name: Name of start date field
        end_name: Name of end date field
        end_required: Whether end date is required

    Returns:
        Tuple of (start_date, end_date)

    Raises:
        ValidationError: If dates are invalid or end is before start
    """
    start_date = validate_date_entry(start_widget, start_name)
    end_date = validate_date_entry(end_widget, end_name, required=end_required)

    if start_date and end_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        if end_dt < start_dt:
            raise ValidationError(f"{end_name} cannot be before {start_name}.")

    return start_date, end_date


def show_validation_error(error: ValidationError, parent=None) -> None:
    """
    Show validation error in a messagebox.

    Args:
        error: The ValidationError to display
        parent: Parent window for the messagebox
    """
    messagebox.showerror("Validation Error", str(error), parent=parent)


def validate_form(validations: List[tuple], parent=None) -> bool:
    """
    Validate multiple form fields and show first error.

    Args:
        validations: List of (validation_func, args, kwargs) tuples
        parent: Parent window for error messagebox

    Returns:
        True if all validations pass, False otherwise

    Example:
        if not validate_form([
            (validate_entry, (name_entry, "Name"), {}),
            (validate_date_entry, (date_entry, "Start Date"), {}),
            (validate_currency_entry, (amount_entry, "Amount"), {'required': False})
        ]):
            return
    """
    for validation_func, args, kwargs in validations:
        try:
            validation_func(*args, **kwargs)
        except ValidationError as e:
            show_validation_error(e, parent)
            return False
    return True


def clear_entry(widget) -> None:
    """Clear an entry widget."""
    if hasattr(widget, 'delete'):
        widget.delete(0, 'end')


def clear_text(widget) -> None:
    """Clear a text widget."""
    widget.delete("1.0", "end")


def set_entry_value(widget, value: str) -> None:
    """Set value in an entry widget, clearing it first."""
    clear_entry(widget)
    if value:
        widget.insert(0, str(value))


def highlight_error(widget, is_error: bool = True) -> None:
    """
    Highlight widget with error styling.

    Args:
        widget: The widget to highlight
        is_error: True to show error style, False to remove it
    """
    if is_error:
        widget.configure(background='#ffcccc')
    else:
        widget.configure(background='white')


class FormValidator:
    """
    Helper class for validating forms with multiple fields.

    Example:
        validator = FormValidator()
        validator.add_required(name_entry, "Name")
        validator.add_date(start_date_entry, "Start Date")
        validator.add_currency(amount_entry, "Amount", required=False)

        if validator.validate():
            # All validations passed
            data = validator.get_values()
    """

    def __init__(self, parent=None):
        self.parent = parent
        self.validations = []
        self.values = {}

    def add_required(self, widget, field_name: str, key: str = None,
                    min_length: int = None, max_length: int = None):
        """Add required text field validation."""
        self.validations.append({
            'func': validate_entry,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': True, 'min_length': min_length, 'max_length': max_length}
        })

    def add_optional(self, widget, field_name: str, key: str = None):
        """Add optional text field validation."""
        self.validations.append({
            'func': validate_entry,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': False}
        })

    def add_date(self, widget, field_name: str, key: str = None, required: bool = True):
        """Add date field validation."""
        self.validations.append({
            'func': validate_date_entry,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': required}
        })

    def add_currency(self, widget, field_name: str, key: str = None,
                    required: bool = True, min_value: float = 0):
        """Add currency field validation."""
        self.validations.append({
            'func': validate_currency_entry,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': required, 'min_value': min_value}
        })

    def add_integer(self, widget, field_name: str, key: str = None,
                   required: bool = True, min_value: int = None, max_value: int = None):
        """Add integer field validation."""
        self.validations.append({
            'func': validate_integer_entry,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': required, 'min_value': min_value, 'max_value': max_value}
        })

    def add_number(self, widget, field_name: str, key: str = None,
                  required: bool = True, min_value: float = None, max_value: float = None):
        """Add number field validation."""
        self.validations.append({
            'func': validate_number_entry,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': required, 'min_value': min_value, 'max_value': max_value}
        })

    def add_combobox(self, widget, field_name: str, key: str = None, required: bool = True):
        """Add combobox selection validation."""
        self.validations.append({
            'func': validate_combobox,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': required}
        })

    def add_rating(self, widget, field_name: str, key: str = None,
                  required: bool = True, min_rating: int = 1, max_rating: int = 5):
        """Add rating field validation."""
        self.validations.append({
            'func': validate_rating_entry,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': required, 'min_rating': min_rating, 'max_rating': max_rating}
        })

    def add_email(self, widget, field_name: str, key: str = None, required: bool = True):
        """Add email field validation."""
        self.validations.append({
            'func': validate_email_entry,
            'widget': widget,
            'field_name': field_name,
            'key': key or field_name.lower().replace(' ', '_'),
            'kwargs': {'required': required}
        })

    def validate(self) -> bool:
        """
        Run all validations.

        Returns:
            True if all validations pass, False otherwise
        """
        self.values = {}

        for v in self.validations:
            try:
                value = v['func'](v['widget'], v['field_name'], **v['kwargs'])
                self.values[v['key']] = value
            except ValidationError as e:
                show_validation_error(e, self.parent)
                # Highlight the error field
                if hasattr(v['widget'], 'focus_set'):
                    v['widget'].focus_set()
                return False

        return True

    def get_values(self) -> dict:
        """
        Get validated values.

        Returns:
            Dictionary of validated field values
        """
        return self.values

    def clear(self):
        """Clear all validations."""
        self.validations = []
        self.values = {}
