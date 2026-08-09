"""
Student Form Business Logic - Testable without GUI dependencies.

This module contains all validation and business logic for student forms,
separated from the Tkinter GUI layer. This allows for comprehensive unit
testing without needing to instantiate any UI components.

Design Pattern: Model-View-Controller (MVC) / Humble Object Pattern
- This class represents the Model/Controller logic
- GUI classes act as thin "Humble Object" wrappers
- All complex logic lives here and is fully testable
"""

import re
from datetime import datetime, date
from typing import Tuple, List, Dict, Any, Optional


class StudentFormLogic:
    """
    Business logic for student form validation and processing.

    This class is intentionally GUI-agnostic and can be tested
    without any Tkinter dependencies.

    Example:
        logic = StudentFormLogic()

        # Validate student data
        valid, errors = logic.validate_student_data({
            'name': 'John Doe',
            'email': 'john.doe@university.edu',
            'student_id': 'STU001',
            'date_of_birth': '2000-01-15'
        })

        if valid:
            # Proceed with saving
            pass
        else:
            # Show errors to user
            print(errors)
    """

    # Configurable validation rules
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 100
    STUDENT_ID_PATTERN = r'^[A-Z]{2,4}\d{3,8}$'
    VALID_EMAIL_DOMAINS = None  # Set to list to restrict domains, e.g., ['university.edu']
    MIN_AGE = 16
    MAX_AGE = 100

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize with optional configuration overrides.

        Args:
            config: Optional dict to override default validation rules.
                   Keys: min_name_length, max_name_length, student_id_pattern,
                         valid_email_domains, min_age, max_age
        """
        if config:
            self.MIN_NAME_LENGTH = config.get('min_name_length', self.MIN_NAME_LENGTH)
            self.MAX_NAME_LENGTH = config.get('max_name_length', self.MAX_NAME_LENGTH)
            self.STUDENT_ID_PATTERN = config.get('student_id_pattern', self.STUDENT_ID_PATTERN)
            self.VALID_EMAIL_DOMAINS = config.get('valid_email_domains', self.VALID_EMAIL_DOMAINS)
            self.MIN_AGE = config.get('min_age', self.MIN_AGE)
            self.MAX_AGE = config.get('max_age', self.MAX_AGE)

    def validate_student_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate all student form data.

        Args:
            data: Dictionary containing student form fields:
                - name (str): Student's full name (required)
                - email (str): Email address (required)
                - student_id (str): Student ID (optional but validated if present)
                - date_of_birth (str): DOB in YYYY-MM-DD format (optional)
                - phone (str): Phone number (optional)
                - address (str): Address (optional)
                - program (str): Academic program (optional)
                - enrollment_date (str): Enrollment date YYYY-MM-DD (optional)

        Returns:
            Tuple of (is_valid: bool, errors: List[str])
        """
        errors = []

        # Required field validations
        name_valid, name_errors = self.validate_name(data.get('name', ''))
        if not name_valid:
            errors.extend(name_errors)

        email_valid, email_errors = self.validate_email(data.get('email', ''))
        if not email_valid:
            errors.extend(email_errors)

        # Optional field validations (only if provided)
        if data.get('student_id'):
            id_valid, id_errors = self.validate_student_id(data['student_id'])
            if not id_valid:
                errors.extend(id_errors)

        if data.get('date_of_birth'):
            dob_valid, dob_errors = self.validate_date_of_birth(data['date_of_birth'])
            if not dob_valid:
                errors.extend(dob_errors)

        if data.get('phone'):
            phone_valid, phone_errors = self.validate_phone(data['phone'])
            if not phone_valid:
                errors.extend(phone_errors)

        if data.get('enrollment_date'):
            enroll_valid, enroll_errors = self.validate_enrollment_date(data['enrollment_date'])
            if not enroll_valid:
                errors.extend(enroll_errors)

        return len(errors) == 0, errors

    def validate_name(self, name: str) -> Tuple[bool, List[str]]:
        """
        Validate student name.

        Args:
            name: The name to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if not name:
            errors.append("Name is required")
            return False, errors

        name = name.strip()

        if len(name) < self.MIN_NAME_LENGTH:
            errors.append(f"Name must be at least {self.MIN_NAME_LENGTH} characters")

        if len(name) > self.MAX_NAME_LENGTH:
            errors.append(f"Name must not exceed {self.MAX_NAME_LENGTH} characters")

        # Check for invalid characters (allow letters, spaces, hyphens, apostrophes)
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", name):
            errors.append("Name contains invalid characters")

        # Check for at least one letter
        if not re.search(r'[a-zA-Z]', name):
            errors.append("Name must contain at least one letter")

        return len(errors) == 0, errors

    def validate_email(self, email: str) -> Tuple[bool, List[str]]:
        """
        Validate email address format and optionally domain.

        Args:
            email: The email address to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if not email:
            errors.append("Email is required")
            return False, errors

        email = email.strip().lower()

        # Basic email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            errors.append("Invalid email format")
            return False, errors

        # Domain validation if configured
        if self.VALID_EMAIL_DOMAINS:
            domain = email.split('@')[1]
            if domain not in self.VALID_EMAIL_DOMAINS:
                errors.append(f"Email must be from: {', '.join(self.VALID_EMAIL_DOMAINS)}")

        return len(errors) == 0, errors

    def validate_student_id(self, student_id: str) -> Tuple[bool, List[str]]:
        """
        Validate student ID format.

        Args:
            student_id: The student ID to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if not student_id:
            return True, errors  # Optional field

        student_id = student_id.strip().upper()

        if not re.match(self.STUDENT_ID_PATTERN, student_id):
            errors.append(
                "Student ID must be 2-4 uppercase letters followed by 3-8 digits "
                "(e.g., STU001, CS12345)"
            )

        return len(errors) == 0, errors

    def validate_date_of_birth(self, dob: str) -> Tuple[bool, List[str]]:
        """
        Validate date of birth and age requirements.

        Args:
            dob: Date of birth in YYYY-MM-DD format

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if not dob:
            return True, errors  # Optional field

        try:
            birth_date = datetime.strptime(dob.strip(), '%Y-%m-%d').date()
        except ValueError:
            errors.append("Date of birth must be in YYYY-MM-DD format")
            return False, errors

        # Check if date is not in the future
        today = date.today()
        if birth_date > today:
            errors.append("Date of birth cannot be in the future")
            return False, errors

        # Calculate age
        age = today.year - birth_date.year
        if today.month < birth_date.month or (
            today.month == birth_date.month and today.day < birth_date.day
        ):
            age -= 1

        if age < self.MIN_AGE:
            errors.append(f"Student must be at least {self.MIN_AGE} years old")

        if age > self.MAX_AGE:
            errors.append(f"Please verify date of birth (age: {age})")

        return len(errors) == 0, errors

    def validate_phone(self, phone: str) -> Tuple[bool, List[str]]:
        """
        Validate phone number format.

        Args:
            phone: Phone number to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if not phone:
            return True, errors  # Optional field

        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\.]', '', phone.strip())

        # Check if it's a valid phone number (10-15 digits, optional + prefix)
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            errors.append("Phone number must be 10-15 digits")

        return len(errors) == 0, errors

    def validate_enrollment_date(self, enrollment_date: str) -> Tuple[bool, List[str]]:
        """
        Validate enrollment date.

        Args:
            enrollment_date: Enrollment date in YYYY-MM-DD format

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if not enrollment_date:
            return True, errors  # Optional field

        try:
            enroll_date = datetime.strptime(enrollment_date.strip(), '%Y-%m-%d').date()
        except ValueError:
            errors.append("Enrollment date must be in YYYY-MM-DD format")
            return False, errors

        # Enrollment date shouldn't be more than 1 year in the future
        today = date.today()
        max_future = date(today.year + 1, today.month, today.day)
        if enroll_date > max_future:
            errors.append("Enrollment date cannot be more than 1 year in the future")

        # Enrollment date shouldn't be more than 10 years in the past
        min_past = date(today.year - 10, today.month, today.day)
        if enroll_date < min_past:
            errors.append("Enrollment date seems too far in the past")

        return len(errors) == 0, errors

    def normalize_student_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and clean student data before saving.

        Args:
            data: Raw student form data

        Returns:
            Normalized data dictionary
        """
        normalized = {}

        if data.get('name'):
            # Normalize name: strip, title case
            normalized['name'] = ' '.join(data['name'].strip().split()).title()

        if data.get('email'):
            # Normalize email: strip, lowercase
            normalized['email'] = data['email'].strip().lower()

        if data.get('student_id'):
            # Normalize student ID: strip, uppercase
            normalized['student_id'] = data['student_id'].strip().upper()

        if data.get('date_of_birth'):
            normalized['date_of_birth'] = data['date_of_birth'].strip()

        if data.get('phone'):
            # Normalize phone: remove formatting
            normalized['phone'] = re.sub(r'[\s\-\(\)\.]', '', data['phone'].strip())

        if data.get('address'):
            normalized['address'] = ' '.join(data['address'].strip().split())

        if data.get('program'):
            normalized['program'] = data['program'].strip()

        if data.get('enrollment_date'):
            normalized['enrollment_date'] = data['enrollment_date'].strip()

        return normalized

    def calculate_age(self, date_of_birth: str) -> Optional[int]:
        """
        Calculate age from date of birth.

        Args:
            date_of_birth: DOB in YYYY-MM-DD format

        Returns:
            Age in years, or None if invalid date
        """
        try:
            birth_date = datetime.strptime(date_of_birth.strip(), '%Y-%m-%d').date()
            today = date.today()
            age = today.year - birth_date.year
            if today.month < birth_date.month or (
                today.month == birth_date.month and today.day < birth_date.day
            ):
                age -= 1
            return age
        except (ValueError, AttributeError):
            return None
