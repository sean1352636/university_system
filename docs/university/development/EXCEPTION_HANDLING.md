# Exception Handling Guidelines

## Overview

The University Management System uses a structured exception hierarchy to handle errors consistently and securely throughout the application. This document provides guidelines for proper exception handling.

## Table of Contents

- [Exception Hierarchy](#exception-hierarchy)
- [Core Principles](#core-principles)
- [Exception Types](#exception-types)
- [Usage Guidelines](#usage-guidelines)
- [Error Messages](#error-messages)
- [Logging](#logging)
- [API Error Responses](#api-error-responses)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Exception Hierarchy

```
Exception (Python built-in)
│
└── UniversitySystemError (base)
    ├── DatabaseError
    │   ├── DatabaseConnectionError
    │   ├── QueryError
    │   ├── TransactionError
    │   └── IntegrityError
    ├── AuthenticationError
    │   ├── InvalidCredentialsError
    │   ├── SessionExpiredError
    │   ├── PermissionDeniedError
    │   └── MFARequiredError
    ├── ValidationError
    │   ├── InvalidInputError
    │   ├── MissingFieldError
    │   └── FormatError
    ├── StudentError
    │   ├── StudentNotFoundError
    │   ├── DuplicateStudentError
    │   └── StudentEnrollmentError
    ├── CourseError
    │   ├── CourseNotFoundError
    │   ├── CourseFullError
    │   └── PrerequisiteError
    ├── EnrollmentError
    │   ├── AlreadyEnrolledError
    │   ├── EnrollmentClosedError
    │   └── CapacityExceededError
    ├── GradeError
    │   ├── InvalidGradeError
    │   └── GradeNotFoundError
    ├── FinanceError
    │   ├── PaymentError
    │   ├── InsufficientFundsError
    │   └── TransactionFailedError
    ├── EmailError
    │   ├── EmailDeliveryError
    │   ├── TemplateError
    │   └── AttachmentError
    ├── FileError
    │   ├── UniversityFileNotFoundError
    │   ├── FileUploadError
    │   └── FileValidationError
    └── ConfigurationError
        ├── MissingConfigError
        └── InvalidConfigError
```

## Core Principles

### 1. Use Specific Exceptions

**DO:**
```python
raise CourseNotFoundError(course_id)
```

**DON'T:**
```python
raise Exception("Course not found")  # Too generic
```

### 2. Never Expose Sensitive Information

**DO:**
```python
try:
    authenticate(username, password)
except Exception as e:
    logger.error(f"Authentication failed for {username}: {e}")
    raise AuthenticationError("Invalid credentials")
```

**DON'T:**
```python
raise AuthenticationError(f"Password hash mismatch: {hash_details}")  # Exposes internals
```

### 3. Log Before Raising

Always log detailed error information before raising to user-facing code:

```python
try:
    result = database_operation()
except sqlite3.IntegrityError as e:
    logger.error(f"Database integrity error: {e}", exc_info=True)
    raise IntegrityError("Data constraint violation")
```

### 4. Catch Specific Exceptions

**DO:**
```python
try:
    process_payment()
except PaymentError as e:
    handle_payment_error(e)
except DatabaseError as e:
    handle_database_error(e)
```

**DON'T:**
```python
try:
    process_payment()
except Exception as e:  # Too broad
    handle_error(e)
```

## Exception Types

The classes are defined in `src/education_system/platform/kernel/exceptions.py` and re-exported by `education_system.systems.university.infrastructure.exceptions`.

### Base Exception

```python
class UniversitySystemError(Exception):
    """
    Base exception for all university system errors.

    All custom exceptions in the system should inherit from this class.
    This allows for catching all system-specific errors with a single
    except clause if needed.

    Attributes:
        message: Human-readable error message
        code: Optional error code for programmatic handling
        details: Optional dict with additional error context
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dict for logging/API responses."""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'code': self.code,
            'details': self.details
        }
```

### Database Exceptions

```python
class DatabaseError(UniversitySystemError):
    """Base exception for database-related errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Database connection failed or was lost."""
    def __init__(self, message: str = "Database connection failed", **kwargs: Any) -> None:
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="DB_CONNECTION_ERROR", **kwargs)


class QueryError(DatabaseError):
    """Database query execution failed."""
    def __init__(self, message: str, query: Optional[str] = None, **kwargs: Any) -> None:
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        details = kwargs.get('details', {})
        if query:
            details['query'] = query
        kwargs['details'] = details
        super().__init__(message, code="DB_QUERY_ERROR", **kwargs)


class TransactionError(DatabaseError):
    """Database transaction failed."""
    def __init__(self, message: str = "Transaction failed", **kwargs: Any) -> None:
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="DB_TRANSACTION_ERROR", **kwargs)


class IntegrityError(DatabaseError):
    """Database integrity constraint violated."""
    def __init__(self, message: str = "Integrity constraint violated", **kwargs: Any) -> None:
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="DB_INTEGRITY_ERROR", **kwargs)
```

### Authentication Exceptions

```python
class AuthenticationError(UniversitySystemError):
    """Base exception for authentication-related errors."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""
    def __init__(self, message: str = "Invalid credentials", **kwargs: Any) -> None:
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="AUTH_INVALID_CREDENTIALS", **kwargs)


class SessionExpiredError(AuthenticationError):
    """User session has expired."""
    def __init__(self, message: str = "Session expired", **kwargs: Any) -> None:
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="AUTH_SESSION_EXPIRED", **kwargs)


class PermissionDeniedError(AuthenticationError):
    """User lacks permission for the requested operation."""
    def __init__(self, message: str = "Permission denied", resource: Optional[str] = None, **kwargs: Any) -> None:
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        details = kwargs.get('details', {})
        if resource:
            details['resource'] = resource
        kwargs['details'] = details
        super().__init__(message, code="AUTH_PERMISSION_DENIED", **kwargs)


class MFARequiredError(AuthenticationError):
    """Multi-factor authentication required."""
    def __init__(self, message: str = "MFA required", **kwargs: Any) -> None:
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="AUTH_MFA_REQUIRED", **kwargs)
```

### Validation Exceptions

```python
class ValidationError(UniversitySystemError):
    """Base exception for validation errors."""
    pass


class InvalidInputError(ValidationError):
    """Input data is invalid."""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs: Any) -> None:
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="VALIDATION_INVALID_INPUT", **kwargs)


class MissingFieldError(ValidationError):
    """Required field is missing."""
    def __init__(self, field: str, **kwargs: Any) -> None:
        message = f"Required field missing: {field}"
        kwargs['details'] = kwargs.get('details', {})
        kwargs['details']['field'] = field
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="VALIDATION_MISSING_FIELD", **kwargs)


class FormatError(ValidationError):
    """Data format is incorrect."""
    def __init__(self, message: str, expected_format: Optional[str] = None, **kwargs: Any) -> None:
        details = kwargs.get('details', {})
        if expected_format:
            details['expected_format'] = expected_format
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="VALIDATION_FORMAT_ERROR", **kwargs)
```

### Student and Course Exceptions

```python
class StudentNotFoundError(StudentError):
    """Student not found in system."""
    def __init__(self, student_id: Optional[str] = None, **kwargs: Any) -> None:
        message = f"Student not found: {student_id}" if student_id else "Student not found"
        if student_id:
            kwargs['details'] = kwargs.get('details', {})
            kwargs['details']['student_id'] = student_id
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="STUDENT_NOT_FOUND", **kwargs)


class DuplicateStudentError(StudentError):
    """Student already exists in system."""
    def __init__(self, identifier: str, **kwargs: Any) -> None:
        message = f"Student already exists: {identifier}"
        kwargs['details'] = kwargs.get('details', {})
        kwargs['details']['identifier'] = identifier
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="STUDENT_DUPLICATE", **kwargs)


class CourseNotFoundError(CourseError):
    """Course not found in system."""
    def __init__(self, course_id: Optional[str] = None, **kwargs: Any) -> None:
        message = f"Course not found: {course_id}" if course_id else "Course not found"
        if course_id:
            kwargs['details'] = kwargs.get('details', {})
            kwargs['details']['course_id'] = course_id
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="COURSE_NOT_FOUND", **kwargs)


class CourseFullError(CourseError):
    """Course has reached maximum capacity."""
    def __init__(self, course_id: Optional[str] = None, **kwargs: Any) -> None:
        message = f"Course is full: {course_id}" if course_id else "Course is full"
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="COURSE_FULL", **kwargs)


class PrerequisiteError(CourseError):
    """Course prerequisites not met."""
    def __init__(self, course_id: str, missing_prereqs: Optional[list[str]] = None, **kwargs: Any) -> None:
        message = f"Prerequisites not met for course: {course_id}"
        details = kwargs.get('details', {})
        details['course_id'] = course_id
        if missing_prereqs:
            details['missing_prerequisites'] = missing_prereqs
        kwargs['details'] = details
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="COURSE_PREREQUISITE_ERROR", **kwargs)
```

### Enrollment, Grade and Finance Exceptions

```python
class EnrollmentError(UniversitySystemError):
    """Base exception for enrollment-related errors."""
    pass


class AlreadyEnrolledError(EnrollmentError):
    """Student is already enrolled in the course."""
    def __init__(self, student_id: str, course_id: str, **kwargs: Any) -> None:
        message = f"Student {student_id} already enrolled in course {course_id}"
        kwargs.pop('code', None)  # Avoid conflict with explicit code parameter
        super().__init__(message, code="ENROLLMENT_ALREADY_ENROLLED", **kwargs)


class CapacityExceededError(EnrollmentError):
    """Maximum enrollment capacity exceeded."""
    pass


class GradeError(UniversitySystemError):
    """Base exception for grade-related errors."""
    pass


class PaymentError(FinanceError):
    """Payment processing failed."""
    pass
```


## Usage Guidelines

### 1. Raising Exceptions

#### In Service Layer

```python
from education_system.systems.university.infrastructure.exceptions import CourseError, CourseNotFoundError, MissingFieldError

class CourseService:
    def get_course(self, course_id: int) -> dict:
        """
        Get course by ID.

        Args:
            course_id: Course ID

        Returns:
            Course information

        Raises:
            CourseNotFoundError: If course not found
        """
        course = self.repository.find_by_id(course_id)

        if not course:
            raise CourseNotFoundError(course_id)

        return course

    def create_course(self, course_data: dict) -> dict:
        """
        Create a new course.

        Args:
            course_data: Course information

        Returns:
            Created course

        Raises:
            MissingFieldError: If required fields missing
            CourseError: If course code exists
        """
        # Validate required fields
        required = ['code', 'name', 'credits']
        for field in required:
            if field not in course_data:
                raise MissingFieldError(field)

        # Check if course exists
        if self.repository.exists_by_code(course_data['code']):
            raise CourseError(f"Course already exists: {course_data['code']}")

        return self.repository.create(course_data)
```

#### In Database Layer

```python
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.exceptions import QueryError

class CourseRepository:
    def find_by_id(self, course_id: int) -> Optional[dict]:
        """
        Find course by ID.

        Args:
            course_id: Course ID

        Returns:
            Course dict if found, None otherwise

        Raises:
            QueryError: If database query fails
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
            result = cursor.fetchone()

            conn.close()
            return result

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving course {course_id}: {e}", exc_info=True)
            raise QueryError(f"Failed to retrieve course: {e}")
```

### 2. Catching Exceptions

#### In Controllers

```python
from education_system.systems.university.infrastructure.exceptions import (
    CourseNotFoundError,
    PermissionDeniedError,
)

class CourseController:
    def handle_get_course(self, course_id: int, user_id: int) -> dict:
        """
        Handle get course request.

        Returns:
            Response dict with status and data/error
        """
        try:
            # Check permission
            if not self.auth.has_permission('courses.view'):
                raise PermissionDeniedError(resource='courses.view')

            # Get course
            course = self.service.get_course(course_id)

            return {
                'success': True,
                'data': course
            }

        except CourseNotFoundError as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 404
            }

        except PermissionDeniedError as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 403
            }

        except Exception as e:
            logger.error(f"Unexpected error in get_course: {e}", exc_info=True)
            return {
                'success': False,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'An unexpected error occurred'
                },
                'status_code': 500
            }
```

#### In CLI

```python
def enroll_student_cli():
    """CLI handler for student enrollment."""
    try:
        student_id = int(input("Student ID: "))
        course_id = int(input("Course ID: "))

        enrollment_service.enroll(student_id, course_id)
        print("Enrollment successful!")

    except (StudentNotFoundError, CourseNotFoundError) as e:
        print(f"Error: {e.message}")

    except EnrollmentError as e:
        print(f"Enrollment error: {e.message}")
        if e.details:
            print(f"Details: {e.details}")

    except ValueError:
        print("Error: Please enter valid numeric IDs")

    except Exception as e:
        logger.error(f"Unexpected error in enrollment: {e}", exc_info=True)
        print("An unexpected error occurred. Please contact support.")
```

#### In GUI

```python
import tkinter.messagebox as messagebox

def handle_create_course(self):
    """GUI handler for course creation."""
    try:
        course_data = {
            'code': self.code_entry.get(),
            'name': self.name_entry.get(),
            'credits': int(self.credits_entry.get())
        }

        course = self.service.create_course(course_data)
        messagebox.showinfo("Success", f"Course {course['code']} created successfully!")

    except MissingFieldError as e:
        messagebox.showerror("Missing Field", e.message)
        # Highlight the missing field
        self.highlight_field(e.details['field'])

    except CourseError as e:
        messagebox.showerror("Duplicate Course", e.message)

    except ValueError as e:
        messagebox.showerror("Invalid Input", "Credits must be a number")

    except Exception as e:
        logger.error(f"Error creating course: {e}", exc_info=True)
        messagebox.showerror("Error", "Failed to create course. Please try again.")
```

## Error Messages

### User-Facing Messages

**DO:**
- Be clear and specific
- Suggest remediation when possible
- Use friendly language
- Avoid technical jargon

```python
"The course CS101 is full. Please contact the registrar for waitlist options."
```

**DON'T:**
- Expose system internals
- Include stack traces
- Reveal database structure
- Show technical error codes

```python
"Foreign key constraint failed: FOREIGN KEY constraint failed on courses.instructor_id"
```

### Example Messages

```python
# Good error messages
MESSAGES = {
    'resource_not_found': "The {resource_type} you're looking for doesn't exist.",
    'permission_denied': "You don't have permission to perform this action.",
    'validation_failed': "Please check your input and try again.",
    'enrollment_full': "This course is currently full. Contact the registrar for waitlist options.",
    'payment_failed': "Payment processing failed. Please verify your payment details.",
    'session_expired': "Your session has expired. Please log in again.",
}
```

## Logging

### Logging Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages (potential issues)
- **ERROR**: Error messages (operation failed)
- **CRITICAL**: Critical errors (system failure)

### Exception Logging

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = perform_operation()
except SpecificException as e:
    # Log with context
    logger.error(
        f"Operation failed for user {user_id}",
        exc_info=True,  # Include stack trace
        extra={
            'user_id': user_id,
            'operation': 'operation_name',
            'error_code': e.code
        }
    )
    raise

except Exception as e:
    # Log unexpected errors as critical
    logger.critical(
        f"Unexpected error in operation",
        exc_info=True,
        extra={'user_id': user_id}
    )
    raise UniversitySystemError("Internal system error")
```

### What to Log

**DO Log:**
- Exception type and message
- User context (user ID, role)
- Operation context (what was being attempted)
- Timestamp (automatic with logger)
- Stack trace (`exc_info=True`)

**DON'T Log:**
- Passwords or password hashes
- Session tokens
- Credit card numbers
- Social security numbers
- Any PII (Personally Identifiable Information) unless necessary

## API Error Responses

### Standard Error Response Format

```python
{
    "success": false,
    "error": {
        "error_type": "CourseNotFoundError",
        "message": "Course not found: 12345",
        "code": "COURSE_NOT_FOUND",
        "details": {
            "course_id": "12345"
        }
    },
    "timestamp": "2025-01-19T10:30:45.123Z",
    "request_id": "abc123..."
}
```

### HTTP Status Codes

Map exceptions to appropriate HTTP status codes:

```python
EXCEPTION_STATUS_CODES = {
    StudentNotFoundError: 404,
    CourseNotFoundError: 404,
    DuplicateStudentError: 409,
    AlreadyEnrolledError: 409,
    ValidationError: 400,
    AuthenticationError: 401,
    PermissionDeniedError: 403,
    EnrollmentError: 422,
    DatabaseError: 500,
    UniversitySystemError: 500,
}
```

### Flask Error Handler

```python
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.errorhandler(UniversitySystemError)
def handle_university_exception(error):
    """Handle university system exceptions."""
    response = {
        'success': False,
        'error': error.to_dict(),
        'timestamp': datetime.now().isoformat(),
        'request_id': request.request_id if hasattr(request, 'request_id') else None
    }

    status_code = EXCEPTION_STATUS_CODES.get(
        type(error),
        500  # Default to internal server error
    )

    return jsonify(response), status_code

@app.errorhandler(Exception)
def handle_generic_exception(error):
    """Handle unexpected exceptions."""
    # Log the error
    logger.error(f"Unexpected error: {error}", exc_info=True)

    # Return generic error to user
    response = {
        'success': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'An unexpected error occurred'
        },
        'timestamp': datetime.now().isoformat()
    }

    return jsonify(response), 500
```

## Best Practices

### 1. Exception Chaining

Preserve exception context with chaining:

```python
try:
    result = database_operation()
except sqlite3.Error as e:
    raise QueryError("Database query failed") from e
```

### 2. Context Managers

Use context managers for resource cleanup:

```python
from contextlib import contextmanager

@contextmanager
def transaction():
    """Database transaction context manager."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise TransactionError("Transaction failed") from e
    finally:
        conn.close()
```

### 3. Custom Exception Context

Add context to exceptions:

```python
try:
    process_enrollment(student_id, course_id)
except EnrollmentError as e:
    e.details['student_id'] = student_id
    e.details['course_id'] = course_id
    raise
```

### 4. Graceful Degradation

Handle non-critical errors gracefully:

```python
try:
    send_notification_email(user_email, message)
except EmailError as e:
    # Log but don't fail the operation
    logger.warning(f"Failed to send notification: {e}")
    # Continue with operation
```

### 5. Testing Exceptions

Write tests for exception paths:

```python
import pytest

def test_course_not_found():
    """Test CourseNotFoundError is raised for missing course."""
    service = CourseService()

    with pytest.raises(CourseNotFoundError) as exc_info:
        service.get_course(99999)

    assert exc_info.value.code == 'COURSE_NOT_FOUND'
    assert exc_info.value.details['course_id'] == 99999
```

## Examples

### Complete Example: Enrollment Flow

```python
# Service layer
class EnrollmentService:
    def enroll_student(self, student_id: int, course_id: int, enrolled_by: int):
        """
        Enroll a student in a course.

        Args:
            student_id: Student to enroll
            course_id: Course to enroll in
            enrolled_by: User performing enrollment

        Raises:
            StudentNotFoundError, CourseNotFoundError: If student or course not found
            PermissionDeniedError: If insufficient permissions
            EnrollmentError: If enrollment rules violated
            DatabaseError: If database operation fails
        """
        try:
            # Check permissions
            if not self.auth.has_permission('enrollments.create'):
                raise PermissionDeniedError(resource='enrollments.create')

            # Validate student exists
            student = self.student_repo.find_by_id(student_id)
            if not student:
                raise StudentNotFoundError(student_id)

            # Validate course exists
            course = self.course_repo.find_by_id(course_id)
            if not course:
                raise CourseNotFoundError(course_id)

            # Check if already enrolled
            if self.enrollment_repo.exists(student_id, course_id):
                raise AlreadyEnrolledError(str(student_id), str(course_id))

            # Check course capacity
            current_enrollment = self.enrollment_repo.count_by_course(course_id)
            if current_enrollment >= course['capacity']:
                raise CapacityExceededError(
                    "Course is full",
                    details={'capacity': course['capacity'], 'enrolled': current_enrollment}
                )

            # Check prerequisites
            if not self.check_prerequisites(student_id, course['prerequisites']):
                raise EnrollmentError(
                    "Prerequisites not met",
                    details={'prerequisites': course['prerequisites']}
                )

            # Create enrollment
            enrollment = self.enrollment_repo.create({
                'student_id': student_id,
                'course_id': course_id,
                'enrolled_by': enrolled_by
            })

            logger.info(f"Student {student_id} enrolled in course {course_id}")

            return enrollment

        except (StudentNotFoundError, CourseNotFoundError, PermissionDeniedError, EnrollmentError):
            # Re-raise known exceptions
            raise

        except Exception as e:
            # Log and wrap unexpected exceptions
            logger.error(
                f"Unexpected error enrolling student {student_id} in course {course_id}: {e}",
                exc_info=True
            )
            raise UniversitySystemError("Enrollment system error")


# Controller layer
class EnrollmentController:
    def handle_enroll(self, request_data: dict, user_id: int) -> dict:
        """Handle enrollment request."""
        try:
            student_id = request_data.get('student_id')
            course_id = request_data.get('course_id')

            if not student_id or not course_id:
                raise MissingFieldError('student_id or course_id')

            enrollment = self.service.enroll_student(student_id, course_id, user_id)

            return {
                'success': True,
                'data': enrollment,
                'message': 'Enrollment successful'
            }

        except MissingFieldError as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 400
            }

        except (StudentNotFoundError, CourseNotFoundError) as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 404
            }

        except PermissionDeniedError as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 403
            }

        except EnrollmentError as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 422
            }

        except Exception as e:
            logger.error(f"Unexpected error in enrollment: {e}", exc_info=True)
            return {
                'success': False,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'An unexpected error occurred'
                },
                'status_code': 500
            }
```

## Summary

1. **Use the exception hierarchy**: Choose the most specific exception type
2. **Log before raising**: Always log detailed errors
3. **Protect sensitive data**: Never expose passwords, tokens, or internal details
4. **Provide context**: Include relevant details in exceptions
5. **Handle gracefully**: Catch specific exceptions and respond appropriately
6. **Test exception paths**: Write tests for error scenarios
7. **Document exceptions**: List exceptions in function docstrings

---

For questions or issues, contact the development team.
