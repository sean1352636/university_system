"""
Validation Infrastructure Package

Provides centralized input validation and sanitization for the University Management System:
- Email, phone, and ID format validation
- Date and time validation
- Text sanitization and XSS prevention
- SQL injection prevention
- Custom validation rules
"""

from university_system.infrastructure.validation.validators import (
    Validators,
    ValidationError,
    ValidationResult,
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

from university_system.infrastructure.validation.sanitizers import (
    Sanitizers,
    sanitize_input,
    sanitize_html,
    sanitize_sql_value,
    sanitize_filename,
    escape_html,
    strip_tags,
)

from university_system.infrastructure.validation.rules import (
    ValidationRule,
    Required,
    MinLength,
    MaxLength,
    Pattern,
    Email,
    Phone,
    DateFormat,
    InRange,
    OneOf,
    Custom,
    validate_fields,
)

__all__ = [
    # Core Validators
    'Validators',
    'ValidationError',
    'ValidationResult',
    'validate',
    'validate_email',
    'validate_phone',
    'validate_student_id',
    'validate_date',
    'validate_password_strength',
    'is_valid_email',
    'is_valid_phone',
    'is_valid_student_id',
    # Sanitizers
    'Sanitizers',
    'sanitize_input',
    'sanitize_html',
    'sanitize_sql_value',
    'sanitize_filename',
    'escape_html',
    'strip_tags',
    # Validation Rules
    'ValidationRule',
    'Required',
    'MinLength',
    'MaxLength',
    'Pattern',
    'Email',
    'Phone',
    'DateFormat',
    'InRange',
    'OneOf',
    'Custom',
    'validate_fields',
]
