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
└── UniversitySystemException (Base exception)
    │
    ├── DatabaseException
    │   ├── ConnectionException
    │   ├── QueryException
    │   ├── TransactionException
    │   └── IntegrityException
    │
    ├── AuthenticationException
    │   ├── InvalidCredentialsException
    │   ├── AccountLockedException
    │   ├── SessionExpiredException
    │   └── PasswordExpiredException
    │
    ├── AuthorizationException
    │   ├── InsufficientPermissionsException
    │   └── ResourceAccessDeniedException
    │
    ├── ValidationException
    │   ├── InvalidInputException
    │   ├── MissingRequiredFieldException
    │   ├── InvalidFormatException
    │   └── DataConstraintException
    │
    ├── ResourceException
    │   ├── ResourceNotFoundException
    │   ├── ResourceAlreadyExistsException
    │   └── ResourceUnavailableException
    │
    ├── BusinessLogicException
    │   ├── EnrollmentException
    │   ├── GradingException
    │   ├── PaymentException
    │   └── SchedulingException
    │
    └── SystemException
        ├── ConfigurationException
        ├── ServiceUnavailableException
        └── InternalErrorException
```

## Core Principles

### 1. Use Specific Exceptions

**DO:**
```python
raise ResourceNotFoundException(f"Course {course_id} not found")
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
    raise AuthenticationException("Invalid credentials")
```

**DON'T:**
```python
raise AuthenticationException(f"Password hash mismatch: {hash_details}")  # Exposes internals
```

### 3. Log Before Raising

Always log detailed error information before raising to user-facing code:

```python
try:
    result = database_operation()
except sqlite3.IntegrityError as e:
    logger.error(f"Database integrity error: {e}", exc_info=True)
    raise IntegrityException("Data constraint violation")
```

### 4. Catch Specific Exceptions

**DO:**
```python
try:
    process_payment()
except PaymentException as e:
    handle_payment_error(e)
except DatabaseException as e:
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

### Base Exception

```python
# infrastructure/exceptions.py

class UniversitySystemException(Exception):
    """
    Base exception for all university system errors.

    All custom exceptions should inherit from this class.

    Attributes:
        message: Error message
        code: Error code for API responses
        details: Additional error details
    """

    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            'error': self.code,
            'message': self.message,
            'details': self.details
        }
```

### Database Exceptions

```python
class DatabaseException(UniversitySystemException):
    """Base exception for database errors."""
    pass


class ConnectionException(DatabaseException):
    """Database connection errors."""
    pass


class QueryException(DatabaseException):
    """Database query errors."""
    pass


class TransactionException(DatabaseException):
    """Transaction-related errors."""
    pass


class IntegrityException(DatabaseException):
    """Data integrity constraint violations."""
    pass
```

### Authentication Exceptions

```python
class AuthenticationException(UniversitySystemException):
    """Base exception for authentication errors."""
    pass


class InvalidCredentialsException(AuthenticationException):
    """Invalid username or password."""
    pass


class AccountLockedException(AuthenticationException):
    """Account is locked due to failed login attempts."""

    def __init__(self, locked_until: datetime):
        self.locked_until = locked_until
        message = f"Account is locked until {locked_until.strftime('%Y-%m-%d %H:%M:%S')}"
        super().__init__(message, details={'locked_until': locked_until.isoformat()})


class SessionExpiredException(AuthenticationException):
    """Session has expired."""
    pass
```

### Authorization Exceptions

```python
class AuthorizationException(UniversitySystemException):
    """Base exception for authorization errors."""
    pass


class InsufficientPermissionsException(AuthorizationException):
    """User lacks required permissions."""

    def __init__(self, permission: str):
        self.permission = permission
        message = f"Insufficient permissions: {permission} required"
        super().__init__(message, details={'required_permission': permission})


class ResourceAccessDeniedException(AuthorizationException):
    """Access to specific resource denied."""
    pass
```

### Validation Exceptions

```python
class ValidationException(UniversitySystemException):
    """Base exception for validation errors."""
    pass


class InvalidInputException(ValidationException):
    """Invalid input data."""

    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        message = f"Invalid input for {field}: {reason}"
        super().__init__(message, details={'field': field, 'reason': reason})


class MissingRequiredFieldException(ValidationException):
    """Required field is missing."""

    def __init__(self, field: str):
        self.field = field
        message = f"Required field missing: {field}"
        super().__init__(message, details={'field': field})
```

### Resource Exceptions

```python
class ResourceException(UniversitySystemException):
    """Base exception for resource-related errors."""
    pass


class ResourceNotFoundException(ResourceException):
    """Requested resource not found."""

    def __init__(self, resource_type: str, resource_id: Any):
        self.resource_type = resource_type
        self.resource_id = resource_id
        message = f"{resource_type} not found: {resource_id}"
        super().__init__(
            message,
            details={'resource_type': resource_type, 'resource_id': str(resource_id)}
        )


class ResourceAlreadyExistsException(ResourceException):
    """Resource already exists."""

    def __init__(self, resource_type: str, identifier: str):
        message = f"{resource_type} already exists: {identifier}"
        super().__init__(message, details={'resource_type': resource_type, 'identifier': identifier})
```

### Business Logic Exceptions

```python
class BusinessLogicException(UniversitySystemException):
    """Base exception for business logic errors."""
    pass


class EnrollmentException(BusinessLogicException):
    """Enrollment-related errors."""
    pass


class GradingException(BusinessLogicException):
    """Grading-related errors."""
    pass


class PaymentException(BusinessLogicException):
    """Payment processing errors."""

    def __init__(self, message: str, transaction_id: str = None):
        super().__init__(
            message,
            details={'transaction_id': transaction_id} if transaction_id else {}
        )
```

## Usage Guidelines

### 1. Raising Exceptions

#### In Service Layer

```python
from infrastructure.exceptions import ResourceNotFoundException, ValidationException

class CourseService:
    def get_course(self, course_id: int) -> dict:
        """
        Get course by ID.

        Args:
            course_id: Course ID

        Returns:
            Course information

        Raises:
            ResourceNotFoundException: If course not found
        """
        course = self.repository.find_by_id(course_id)

        if not course:
            raise ResourceNotFoundException('Course', course_id)

        return course

    def create_course(self, course_data: dict) -> dict:
        """
        Create a new course.

        Args:
            course_data: Course information

        Returns:
            Created course

        Raises:
            MissingRequiredFieldException: If required fields missing
            ResourceAlreadyExistsException: If course code exists
        """
        # Validate required fields
        required = ['code', 'name', 'credits']
        for field in required:
            if field not in course_data:
                raise MissingRequiredFieldException(field)

        # Check if course exists
        if self.repository.exists_by_code(course_data['code']):
            raise ResourceAlreadyExistsException('Course', course_data['code'])

        return self.repository.create(course_data)
```

#### In Database Layer

```python
from infrastructure.exceptions import DatabaseException, QueryException, TransactionException

class CourseRepository:
    def find_by_id(self, course_id: int) -> Optional[dict]:
        """
        Find course by ID.

        Args:
            course_id: Course ID

        Returns:
            Course dict if found, None otherwise

        Raises:
            QueryException: If database query fails
        """
        try:
            db = DatabaseManager()
            conn = db.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
            result = cursor.fetchone()

            db.close()
            return result

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving course {course_id}: {e}", exc_info=True)
            raise QueryException(f"Failed to retrieve course: {e}")
```

### 2. Catching Exceptions

#### In Controllers

```python
from infrastructure.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    AuthorizationException
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
            if not has_permission(user_id, 'courses.view'):
                raise InsufficientPermissionsException('courses.view')

            # Get course
            course = self.service.get_course(course_id)

            return {
                'success': True,
                'data': course
            }

        except ResourceNotFoundException as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 404
            }

        except AuthorizationException as e:
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

    except ResourceNotFoundException as e:
        print(f"Error: {e.message}")

    except EnrollmentException as e:
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

    except MissingRequiredFieldException as e:
        messagebox.showerror("Missing Field", e.message)
        # Highlight the missing field
        self.highlight_field(e.field)

    except ResourceAlreadyExistsException as e:
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
    raise SystemException("Internal system error")
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
        "code": "RESOURCE_NOT_FOUND",
        "message": "Course not found",
        "details": {
            "resource_type": "Course",
            "resource_id": "12345"
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
    ResourceNotFoundException: 404,
    ResourceAlreadyExistsException: 409,
    ValidationException: 400,
    AuthenticationException: 401,
    AuthorizationException: 403,
    BusinessLogicException: 422,
    DatabaseException: 500,
    SystemException: 500,
}
```

### Flask Error Handler

```python
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.errorhandler(UniversitySystemException)
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
    raise QueryException("Database query failed") from e
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
        raise TransactionException("Transaction failed") from e
    finally:
        conn.close()
```

### 3. Custom Exception Context

Add context to exceptions:

```python
try:
    process_enrollment(student_id, course_id)
except EnrollmentException as e:
    e.details['student_id'] = student_id
    e.details['course_id'] = course_id
    raise
```

### 4. Graceful Degradation

Handle non-critical errors gracefully:

```python
try:
    send_notification_email(user_email, message)
except EmailException as e:
    # Log but don't fail the operation
    logger.warning(f"Failed to send notification: {e}")
    # Continue with operation
```

### 5. Testing Exceptions

Write tests for exception paths:

```python
import pytest

def test_course_not_found():
    """Test ResourceNotFoundException is raised for missing course."""
    service = CourseService()

    with pytest.raises(ResourceNotFoundException) as exc_info:
        service.get_course(99999)

    assert exc_info.value.resource_type == 'Course'
    assert exc_info.value.resource_id == 99999
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
            ResourceNotFoundException: If student or course not found
            AuthorizationException: If insufficient permissions
            EnrollmentException: If enrollment rules violated
            DatabaseException: If database operation fails
        """
        try:
            # Check permissions
            if not has_permission(enrolled_by, 'enrollments.create'):
                raise InsufficientPermissionsException('enrollments.create')

            # Validate student exists
            student = self.student_repo.find_by_id(student_id)
            if not student:
                raise ResourceNotFoundException('Student', student_id)

            # Validate course exists
            course = self.course_repo.find_by_id(course_id)
            if not course:
                raise ResourceNotFoundException('Course', course_id)

            # Check if already enrolled
            if self.enrollment_repo.exists(student_id, course_id):
                raise ResourceAlreadyExistsException(
                    'Enrollment',
                    f"student_{student_id}_course_{course_id}"
                )

            # Check course capacity
            current_enrollment = self.enrollment_repo.count_by_course(course_id)
            if current_enrollment >= course['capacity']:
                raise EnrollmentException(
                    "Course is full",
                    details={'capacity': course['capacity'], 'enrolled': current_enrollment}
                )

            # Check prerequisites
            if not self.check_prerequisites(student_id, course['prerequisites']):
                raise EnrollmentException(
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

        except (ResourceNotFoundException, AuthorizationException, EnrollmentException):
            # Re-raise known exceptions
            raise

        except Exception as e:
            # Log and wrap unexpected exceptions
            logger.error(
                f"Unexpected error enrolling student {student_id} in course {course_id}: {e}",
                exc_info=True
            )
            raise SystemException("Enrollment system error")


# Controller layer
class EnrollmentController:
    def handle_enroll(self, request_data: dict, user_id: int) -> dict:
        """Handle enrollment request."""
        try:
            student_id = request_data.get('student_id')
            course_id = request_data.get('course_id')

            if not student_id or not course_id:
                raise MissingRequiredFieldException('student_id or course_id')

            enrollment = self.service.enroll_student(student_id, course_id, user_id)

            return {
                'success': True,
                'data': enrollment,
                'message': 'Enrollment successful'
            }

        except MissingRequiredFieldException as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 400
            }

        except ResourceNotFoundException as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 404
            }

        except AuthorizationException as e:
            return {
                'success': False,
                'error': e.to_dict(),
                'status_code': 403
            }

        except EnrollmentException as e:
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
