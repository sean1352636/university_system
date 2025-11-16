from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from university_system.modules.shared.constants import paths
import os
import requests
import uuid
import json
import csv
import smtplib
import ssl
import platform
import secrets
import subprocess
import shutil
import threading
import time
import re
import hashlib
import calendar as cal
import traceback
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple, Any, Union
from collections import defaultdict, Counter
from dataclasses import dataclass
from functools import wraps
import logging
import numpy as np
import pytz
from university_system.infrastructure.database.db import get_connection
from university_system.utils.logging.log_config import configure_logging

# Additional imports for new features
try:
    import twilio
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logging.warning("Twilio not available for SMS. Install with: pip install twilio")

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    import seaborn as sns
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.warning("matplotlib not available")

# Optional imports with graceful degradation
try:
    from ics import Calendar as ICSCalendar, Event as ICSEvent
    ICS_AVAILABLE = True
except ImportError:
    ICS_AVAILABLE = False
    logging.warning("ICS library not available. Install with: pip install ics")

try:
    import pytz
    TIMEZONE_AVAILABLE = True
except ImportError:
    TIMEZONE_AVAILABLE = False
    logging.warning("pytz not available. Install with: pip install pytz")

try:
    from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
    from dateutil.parser import parse as date_parse
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False
    logging.warning("dateutil not available. Install with: pip install python-dateutil")

try:
    import holidays
    HOLIDAYS_AVAILABLE = True
except ImportError:
    HOLIDAYS_AVAILABLE = False
    logging.warning("holidays library not available. Install with: pip install holidays")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import plotly.graph_objs as go
    import plotly.express as px
    from plotly.offline import plot
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from flask import Flask, jsonify, request, render_template_string, send_file
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

try:
    # Import the trip management module from the mobility services package
    from university_system.modules.domain.mobility.services import trip_management  # type: ignore
    TRIP_MANAGEMENT_AVAILABLE = True
except ImportError:
    TRIP_MANAGEMENT_AVAILABLE = False
    # Use the base logging module here because logger may not yet be configured
    logging.warning("Trip management module not available")

# Configure logging - Fixed the format string and logging configuration
log_path = paths.LOG_DIR / 'calendar.log'

# Ensure the log directory exists
os.makedirs(os.path.dirname(log_path), exist_ok=True)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

# Configure loggers using the custom configure_logging function
logger = configure_logging(name=__name__)
exception_logger = logging.getLogger('calendar.exceptions')

class CalendarError(Exception):
    """Base exception for calendar operations with enhanced functionality"""
    
    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None, 
                 original_exception: Exception = None, user_message: str = None):
        """
        Initialize the calendar error
        
        Args:
            message: Technical error message for developers
            error_code: Unique error code for programmatic handling
            context: Additional context information
            original_exception: The original exception that caused this error
            user_message: User-friendly error message
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self._generate_error_code()
        self.context = context or {}
        self.original_exception = original_exception
        self.user_message = user_message or self._generate_user_message()
        self.timestamp = datetime.now()
        self.stack_trace = traceback.format_exc() if original_exception else None
        
        # Log the error
        self._log_error()
    
    def _generate_error_code(self) -> str:
        """Generate a default error code based on exception type"""
        return f"{self.__class__.__name__.upper()}_001"
    
    def _generate_user_message(self) -> str:
        """Generate a user-friendly error message"""
        return "An error occurred in the calendar system. Please try again or contact support."
    
    def _log_error(self):
        """Log the error with appropriate level"""
        log_data = {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'user_message': self.user_message
        }
        
        if self.original_exception:
            log_data['original_exception'] = str(self.original_exception)
            log_data['stack_trace'] = self.stack_trace
        
        exception_logger.error(f"Calendar Error: {json.dumps(log_data, indent=2)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'user_message': self.user_message,
            'context': self.context,
            'timestamp': self.timestamp.isoformat()
        }
    
    def add_context(self, key: str, value: Any) -> 'CalendarError':
        """Add context information to the error"""
        self.context[key] = value
        return self
    
    def __str__(self) -> str:
        """String representation of the error"""
        return f"{self.__class__.__name__}({self.error_code}): {self.message}"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (f"{self.__class__.__name__}("
                f"message='{self.message}', "
                f"error_code='{self.error_code}', "
                f"context={self.context})")


class ValidationError(CalendarError):
    """Raised when input validation fails"""
    
    def __init__(self, message: str, field_name: str = None, field_value: Any = None, 
                 validation_rules: List[str] = None, **kwargs):
        """
        Initialize validation error
        
        Args:
            message: Error message
            field_name: Name of the field that failed validation
            field_value: Value that failed validation
            validation_rules: List of validation rules that were violated
        """
        self.field_name = field_name
        self.field_value = field_value
        self.validation_rules = validation_rules or []
        
        # Add validation-specific context
        context = kwargs.get('context', {})
        if field_name:
            context['field_name'] = field_name
        if field_value is not None:
            context['field_value'] = str(field_value)
        if validation_rules:
            context['validation_rules'] = validation_rules
        
        kwargs['context'] = context
        super().__init__(message, **kwargs)
    
    def _generate_error_code(self) -> str:
        """Generate validation-specific error code"""
        if self.field_name:
            return f"VALIDATION_ERROR_{self.field_name.upper()}"
        return "VALIDATION_ERROR_GENERAL"
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly validation message"""
        if self.field_name:
            return f"The value provided for '{self.field_name}' is not valid. Please check your input and try again."
        return "The information provided is not valid. Please check your input and try again."
    
    @classmethod
    def required_field(cls, field_name: str) -> 'ValidationError':
        """Create a required field validation error"""
        return cls(
            message=f"Required field '{field_name}' is missing or empty",
            field_name=field_name,
            validation_rules=["required"],
            user_message=f"The field '{field_name}' is required."
        )
    
    @classmethod
    def invalid_format(cls, field_name: str, field_value: Any, expected_format: str) -> 'ValidationError':
        """Create an invalid format validation error"""
        return cls(
            message=f"Field '{field_name}' has invalid format. Expected: {expected_format}",
            field_name=field_name,
            field_value=field_value,
            validation_rules=["format"],
            user_message=f"The format for '{field_name}' is incorrect. Expected format: {expected_format}"
        )
    
    @classmethod
    def out_of_range(cls, field_name: str, field_value: Any, min_val: Any = None, max_val: Any = None) -> 'ValidationError':
        """Create an out of range validation error"""
        range_msg = ""
        if min_val is not None and max_val is not None:
            range_msg = f"between {min_val} and {max_val}"
        elif min_val is not None:
            range_msg = f"at least {min_val}"
        elif max_val is not None:
            range_msg = f"at most {max_val}"
        
        return cls(
            message=f"Field '{field_name}' value {field_value} is out of range. Expected {range_msg}",
            field_name=field_name,
            field_value=field_value,
            validation_rules=["range"],
            user_message=f"The value for '{field_name}' must be {range_msg}."
        )


class DatabaseError(CalendarError):
    """Raised when database operations fail"""
    
    def __init__(self, message: str, operation: str = None, table: str = None, 
                 query: str = None, error_code: str = None, **kwargs):
        """
        Initialize database error
        
        Args:
            message: Error message
            operation: Database operation that failed (SELECT, INSERT, UPDATE, DELETE)
            table: Table name where error occurred
            query: SQL query that failed
            error_code: Database-specific error code
        """
        self.operation = operation
        self.table = table
        self.query = query
        self.db_error_code = error_code
        
        # Add database-specific context
        context = kwargs.get('context', {})
        if operation:
            context['operation'] = operation
        if table:
            context['table'] = table
        if query:
            context['query'] = query[:200] + "..." if len(query) > 200 else query  # Truncate long queries
        if error_code:
            context['db_error_code'] = error_code
        
        kwargs['context'] = context
        super().__init__(message, **kwargs)
    
    def _generate_error_code(self) -> str:
        """Generate database-specific error code"""
        if self.operation and self.table:
            return f"DB_ERROR_{self.operation}_{self.table.upper()}"
        elif self.operation:
            return f"DB_ERROR_{self.operation}"
        return "DB_ERROR_GENERAL"
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly database error message"""
        if self.operation:
            operation_messages = {
                'SELECT': 'retrieve data from',
                'INSERT': 'save data to',
                'UPDATE': 'update data in',
                'DELETE': 'remove data from'
            }
            op_msg = operation_messages.get(self.operation, 'access')
            return f"Unable to {op_msg} the database. Please try again or contact support."
        return "A database error occurred. Please try again or contact support."
    
    @classmethod
    def connection_failed(cls, details: str = None) -> 'DatabaseError':
        """Create a database connection error"""
        return cls(
            message=f"Database connection failed: {details or 'Unknown reason'}",
            operation="CONNECT",
            user_message="Unable to connect to the database. Please try again later."
        )
    
    @classmethod
    def constraint_violation(cls, constraint: str, table: str = None) -> 'DatabaseError':
        """Create a constraint violation error"""
        return cls(
            message=f"Database constraint violation: {constraint}",
            operation="CONSTRAINT",
            table=table,
            user_message="The operation violates database rules. Please check your data and try again."
        )
    
    @classmethod
    def record_not_found(cls, table: str, identifier: str = None) -> 'DatabaseError':
        """Create a record not found error"""
        return cls(
            message=f"Record not found in table {table}" + (f" with identifier {identifier}" if identifier else ""),
            operation="SELECT",
            table=table,
            user_message="The requested record was not found."
        )


class AuthenticationError(CalendarError):
    """Raised when authentication fails"""
    
    def __init__(self, message: str, username: str = None, auth_method: str = None, 
                 reason: str = None, **kwargs):
        """
        Initialize authentication error
        
        Args:
            message: Error message
            username: Username that failed authentication
            auth_method: Authentication method used
            reason: Reason for authentication failure
        """
        self.username = username
        self.auth_method = auth_method
        self.reason = reason
        
        # Add auth-specific context (but don't expose sensitive info)
        context = kwargs.get('context', {})
        if username:
            context['username'] = username
        if auth_method:
            context['auth_method'] = auth_method
        if reason:
            context['reason'] = reason
        
        kwargs['context'] = context
        super().__init__(message, **kwargs)
    
    def _generate_error_code(self) -> str:
        """Generate authentication-specific error code"""
        if self.reason:
            return f"AUTH_ERROR_{self.reason.upper()}"
        return "AUTH_ERROR_GENERAL"
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly authentication error message"""
        reason_messages = {
            'invalid_credentials': 'Invalid username or password.',
            'account_locked': 'Your account has been locked. Please contact support.',
            'account_disabled': 'Your account has been disabled. Please contact support.',
            'session_expired': 'Your session has expired. Please log in again.',
            'insufficient_permissions': 'You do not have permission to perform this action.'
        }
        
        return reason_messages.get(self.reason, 'Authentication failed. Please check your credentials and try again.')
    
    @classmethod
    def invalid_credentials(cls, username: str = None) -> 'AuthenticationError':
        """Create invalid credentials error"""
        return cls(
            message="Invalid username or password provided",
            username=username,
            reason="invalid_credentials"
        )
    
    @classmethod
    def session_expired(cls, username: str = None) -> 'AuthenticationError':
        """Create session expired error"""
        return cls(
            message="User session has expired",
            username=username,
            reason="session_expired"
        )
    
    @classmethod
    def account_locked(cls, username: str) -> 'AuthenticationError':
        """Create account locked error"""
        return cls(
            message=f"Account {username} is locked",
            username=username,
            reason="account_locked"
        )


class PermissionError(CalendarError):
    """Raised when user lacks required permissions"""
    
    def __init__(self, message: str, required_permission: str = None, user_role: str = None, 
                 resource: str = None, action: str = None, **kwargs):
        """
        Initialize permission error
        
        Args:
            message: Error message
            required_permission: Permission that was required
            user_role: Current user's role
            resource: Resource being accessed
            action: Action being attempted
        """
        self.required_permission = required_permission
        self.user_role = user_role
        self.resource = resource
        self.action = action
        
        # Add permission-specific context
        context = kwargs.get('context', {})
        if required_permission:
            context['required_permission'] = required_permission
        if user_role:
            context['user_role'] = user_role
        if resource:
            context['resource'] = resource
        if action:
            context['action'] = action
        
        kwargs['context'] = context
        super().__init__(message, **kwargs)
    
    def _generate_error_code(self) -> str:
        """Generate permission-specific error code"""
        if self.required_permission:
            return f"PERMISSION_ERROR_{self.required_permission.upper()}"
        return "PERMISSION_ERROR_GENERAL"
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly permission error message"""
        if self.action and self.resource:
            return f"You do not have permission to {self.action} {self.resource}."
        elif self.required_permission:
            return f"You need '{self.required_permission}' permission to perform this action."
        return "You do not have sufficient permissions to perform this action."
    
    @classmethod
    def insufficient_role(cls, required_role: str, current_role: str, action: str = None) -> 'PermissionError':
        """Create insufficient role error"""
        return cls(
            message=f"Role '{current_role}' insufficient. Required: '{required_role}'",
            user_role=current_role,
            action=action,
            user_message=f"You need '{required_role}' role to perform this action."
        )
    
    @classmethod
    def resource_access_denied(cls, resource: str, action: str, required_permission: str = None) -> 'PermissionError':
        """Create resource access denied error"""
        return cls(
            message=f"Access denied to {action} {resource}",
            required_permission=required_permission,
            resource=resource,
            action=action
        )


class ExportError(CalendarError):
    """Raised when export operations fail"""
    
    def __init__(self, message: str, export_format: str = None, file_path: str = None, 
                 data_size: int = None, **kwargs):
        """
        Initialize export error
        
        Args:
            message: Error message
            export_format: Format being exported (CSV, PDF, etc.)
            file_path: Path where export was attempted
            data_size: Size of data being exported
        """
        self.export_format = export_format
        self.file_path = file_path
        self.data_size = data_size
        
        # Add export-specific context
        context = kwargs.get('context', {})
        if export_format:
            context['export_format'] = export_format
        if file_path:
            context['file_path'] = file_path
        if data_size:
            context['data_size'] = data_size
        
        kwargs['context'] = context
        super().__init__(message, **kwargs)
    
    def _generate_error_code(self) -> str:
        """Generate export-specific error code"""
        if self.export_format:
            return f"EXPORT_ERROR_{self.export_format.upper()}"
        return "EXPORT_ERROR_GENERAL"
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly export error message"""
        if self.export_format:
            return f"Failed to export data in {self.export_format} format. Please try again or use a different format."
        return "Export operation failed. Please try again or contact support."
    
    @classmethod
    def file_write_failed(cls, file_path: str, export_format: str = None) -> 'ExportError':
        """Create file write failed error"""
        return cls(
            message=f"Failed to write export file: {file_path}",
            export_format=export_format,
            file_path=file_path,
            user_message="Unable to save the export file. Please check file permissions and try again."
        )
    
    @classmethod
    def data_too_large(cls, data_size: int, max_size: int, export_format: str = None) -> 'ExportError':
        """Create data too large error"""
        return cls(
            message=f"Export data size {data_size} exceeds maximum {max_size}",
            export_format=export_format,
            data_size=data_size,
            user_message=f"The data is too large to export. Please filter your data or export in smaller chunks."
        )
    
    @classmethod
    def unsupported_format(cls, export_format: str) -> 'ExportError':
        """Create unsupported format error"""
        return cls(
            message=f"Unsupported export format: {export_format}",
            export_format=export_format,
            user_message=f"The format '{export_format}' is not supported. Please choose a different format."
        )


class SyncError(CalendarError):
    """Raised when calendar sync fails"""
    
    def __init__(self, message: str, sync_source: str = None, sync_destination: str = None, 
                 sync_type: str = None, items_processed: int = None, **kwargs):
        """
        Initialize sync error
        
        Args:
            message: Error message
            sync_source: Source of the sync operation
            sync_destination: Destination of the sync operation
            sync_type: Type of sync (import, export, bidirectional)
            items_processed: Number of items processed before error
        """
        self.sync_source = sync_source
        self.sync_destination = sync_destination
        self.sync_type = sync_type
        self.items_processed = items_processed
        
        # Add sync-specific context
        context = kwargs.get('context', {})
        if sync_source:
            context['sync_source'] = sync_source
        if sync_destination:
            context['sync_destination'] = sync_destination
        if sync_type:
            context['sync_type'] = sync_type
        if items_processed is not None:
            context['items_processed'] = items_processed
        
        kwargs['context'] = context
        super().__init__(message, **kwargs)
    
    def _generate_error_code(self) -> str:
        """Generate sync-specific error code"""
        if self.sync_type:
            return f"SYNC_ERROR_{self.sync_type.upper()}"
        return "SYNC_ERROR_GENERAL"
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly sync error message"""
        if self.sync_source and self.sync_destination:
            return f"Failed to sync calendar data from {self.sync_source} to {self.sync_destination}."
        return "Calendar synchronization failed. Please try again or contact support."
    
    @classmethod
    def connection_failed(cls, sync_source: str) -> 'SyncError':
        """Create sync connection failed error"""
        return cls(
            message=f"Failed to connect to sync source: {sync_source}",
            sync_source=sync_source,
            sync_type="import",
            user_message=f"Unable to connect to {sync_source}. Please check your connection and try again."
        )
    
    @classmethod
    def data_conflict(cls, conflicting_items: List[str], sync_source: str = None) -> 'SyncError':
        """Create data conflict error"""
        return cls(
            message=f"Data conflicts detected during sync: {', '.join(conflicting_items)}",
            sync_source=sync_source,
            sync_type="bidirectional",
            user_message="Conflicting data detected during sync. Please resolve conflicts manually."
        )
    
    @classmethod
    def partial_sync(cls, items_processed: int, total_items: int, sync_source: str = None) -> 'SyncError':
        """Create partial sync error"""
        return cls(
            message=f"Partial sync completed: {items_processed}/{total_items} items processed",
            sync_source=sync_source,
            items_processed=items_processed,
            user_message=f"Sync completed partially. {items_processed} of {total_items} items were processed."
        )


# Exception handler utility functions
class CalendarExceptionHandler:
    """Utility class for handling calendar exceptions"""
    
    @staticmethod
    def handle_exception(func):
        """Decorator to handle exceptions in calendar functions"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CalendarError:
                # Re-raise calendar errors as-is
                raise
            except Exception as e:
                # Wrap other exceptions in CalendarError
                raise CalendarError(
                    message=f"Unexpected error in {func.__name__}: {str(e)}",
                    original_exception=e,
                    context={'function': func.__name__, 'args': str(args)[:100], 'kwargs': str(kwargs)[:100]}
                )
        return wrapper
    
    @staticmethod
    def log_and_suppress(exception: CalendarError, default_return=None):
        """Log an exception and return a default value instead of raising"""
        exception_logger.warning(f"Suppressed exception: {exception}")
        return default_return
    
    @staticmethod
    def convert_to_user_error(exception: CalendarError) -> Dict[str, Any]:
        """Convert exception to user-friendly error response"""
        return {
            'error': True,
            'message': exception.user_message,
            'error_code': exception.error_code,
            'timestamp': exception.timestamp.isoformat()
        }

# Configuration
@dataclass
class CalendarConfig:
    db_file: str = os.fspath(paths.DEFAULT_DB_PATH)
    default_timezone: str = 'UTC'
    max_export_records: int = 10000
    backup_directory: str = 'backups'
    allowed_file_types: frozenset = frozenset(['.pdf', '.txt', '.csv', '.xlsx', '.ics'])
    smtp_timeout: int = 30
    api_rate_limit: int = 100
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    session_timeout: int = 3600  # 1 hour
    max_search_results: int = 1000

# Input validation utilities
class ValidationUtils:
    @staticmethod
    def validate_date(date_string: str) -> bool:
        """Validate date format YYYY-MM-DD"""
        if not isinstance(date_string, str):
            return False
        try:
            datetime.strptime(date_string, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_datetime(datetime_string: str) -> bool:
        """Validate datetime format YYYY-MM-DD HH:MM:SS"""
        if not isinstance(datetime_string, str):
            return False
        try:
            datetime.strptime(datetime_string, "%Y-%m-%d %H:%M:%S")
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        if not isinstance(email, str):
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """Validate UUID format"""
        if not isinstance(uuid_string, str):
            return False
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False

    @staticmethod
    def sanitize_string(input_string: str, max_length: int = 255) -> str:
        """Sanitize string input"""
        if not isinstance(input_string, str):
            return ""
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\';]', '', input_string)
        return sanitized[:max_length].strip()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent directory traversal"""
        if not isinstance(filename, str):
            return "invalid_filename"
        # Remove any path components
        filename = os.path.basename(filename)
        # Remove or replace dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return filename[:255]  # Limit length

    @staticmethod
    def validate_file_path(file_path: str, allowed_directory: str) -> bool:
        """Validate file path to prevent directory traversal"""
        try:
            abs_path = os.path.abspath(file_path)
            abs_allowed = os.path.abspath(allowed_directory)
            return abs_path.startswith(abs_allowed)
        except Exception:
            return False

    @staticmethod
    def validate_url(url: str) -> bool:
        """Basic URL validation"""
        if not isinstance(url, str):
            return False
        return url.startswith(('http://', 'https://')) and len(url) < 2048

# Security utilities
class SecurityUtils:
    @staticmethod
    def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with salt"""
        if salt is None:
            salt = os.urandom(32).hex()
        
        password_hash = hashlib.pbkdf2_hmac('sha256', 
                                          password.encode('utf-8'), 
                                          salt.encode('utf-8'), 
                                          100000)
        return password_hash.hex(), salt

    @staticmethod
    def verify_password(password: str, hash_hex: str, salt: str) -> bool:
        """Verify password against hash"""
        try:
            password_hash = hashlib.pbkdf2_hmac('sha256',
                                              password.encode('utf-8'),
                                              salt.encode('utf-8'),
                                              100000)
            return password_hash.hex() == hash_hex
        except Exception:
            return False

    @staticmethod
    def generate_token() -> str:
        """Generate secure token"""
        return secrets.token_urlsafe(32)

# Database connection manager
class DatabaseManager:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.conn = None
        self.cursor = None
        self._lock = threading.RLock()
        self._connect()

    def _connect(self):
        """Establish database connection with proper configuration"""
        try:
            self.conn = sqlite3.connect(
                self.db_file,
                check_same_thread=False,
                timeout=30.0,
                isolation_level='DEFERRED'  # Use DEFERRED for proper transaction support
            )
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Configure SQLite for better performance and security
            pragma_commands = [
                "PRAGMA foreign_keys = ON",
                "PRAGMA journal_mode = WAL",
                "PRAGMA synchronous = NORMAL",
                "PRAGMA cache_size = 10000",
                "PRAGMA temp_store = MEMORY"
            ]
            
            for pragma in pragma_commands:
                self.cursor.execute(pragma)
                
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseError(f"Failed to connect to database: {e}")

    def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query safely with connection pooling"""
        with self._lock:
            try:
                self.cursor.execute(query, params)
                return self.cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Query execution failed: {e}")
                raise DatabaseError(f"Query failed: {e}")

    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE/DDL query safely"""
        with self._lock:
            try:
                self.cursor.execute(query, params)
                self.conn.commit()
                return self.cursor.rowcount
            except sqlite3.Error as e:
                logger.error(f"Update execution failed: {e}")
                raise DatabaseError(f"Update failed: {e}")

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute many operations efficiently"""
        with self._lock:
            try:
                self.cursor.executemany(query, params_list)
                return self.cursor.rowcount
            except sqlite3.Error as e:
                logger.error(f"Batch execution failed: {e}")
                raise DatabaseError(f"Batch operation failed: {e}")

    def transaction(self):
        """Context manager for database transactions"""
        return DatabaseTransaction(self.conn, self._lock)

    def backup_database(self, backup_path: str):
        """Create database backup"""
        with self._lock:
            try:
                backup = sqlite3.connect(backup_path)
                self.conn.backup(backup)
                backup.close()
                logger.info(f"Database backed up to {backup_path}")
            except sqlite3.Error as e:
                logger.error(f"Backup failed: {e}")
                raise DatabaseError(f"Backup failed: {e}")

    def close(self):
        """Close database connection"""
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None
                self.cursor = None

class DatabaseTransaction:
    def __init__(self, connection, lock):
        self.connection = connection
        self.lock = lock
        self.savepoint = None

    def __enter__(self):
        self.lock.acquire()
        try:
            # Use savepoints for nested transactions
            self.savepoint = f"sp_{uuid.uuid4().hex[:8]}"
            self.connection.execute(f"SAVEPOINT {self.savepoint}")
            return self
        except Exception:
            self.lock.release()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self.connection.execute(f"RELEASE SAVEPOINT {self.savepoint}")
            else:
                self.connection.execute(f"ROLLBACK TO SAVEPOINT {self.savepoint}")
                logger.error(f"Transaction rolled back due to: {exc_val}")
        finally:
            self.lock.release()

# Authentication and Authorization
class AuthenticationManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.current_user = None
        self.permissions_cache = {}
        self.session_token = None
        self.session_expires = None
        # Don't try to create our own user system - use the existing one

    # authenticate_user() removed - use infrastructure.auth.user_authentication.UserAuth instead

    def check_permission(self, permission: str) -> bool:
        """Check if current user has specific permission using main auth system"""
        # Get the global auth instance
        from university_system.infrastructure.auth.user_authentication import _current_auth_instance
        if _current_auth_instance and _current_auth_instance.current_user:
            return _current_auth_instance.check_permission(permission)
        return False

    def _load_permissions(self):
        """Load permissions from main auth system"""
        from university_system.infrastructure.auth.user_authentication import _current_auth_instance
        if _current_auth_instance and _current_auth_instance.current_user:
            self.current_user = _current_auth_instance.current_user
            self.permissions_cache = set(_current_auth_instance.current_user.get('permissions', []))

    def _create_session(self):
        """Create user session"""
        self.session_token = SecurityUtils.generate_token()
        self.session_expires = datetime.now() + timedelta(seconds=3600)  # 1 hour

    def check_permission(self, permission: str) -> bool:
        """Check if current user has specific permission"""
        if not self.current_user or not self._is_session_valid():
            return False
        return permission in self.permissions_cache

    def _is_session_valid(self) -> bool:
        """Check if current session is valid"""
        if not self.session_expires:
            return False
        return datetime.now() < self.session_expires

    def require_permission(self, permission: str):
        """Decorator to require specific permission"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.check_permission(permission):
                    raise PermissionError(f"Required permission: {permission}")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    # logout() removed - use infrastructure.auth.user_authentication.UserAuth.logout() instead

    def create_user(self, username: str, password: str, email: str, role: str = 'student') -> bool:
        """Create new user with secure password hashing"""
        try:
            if not all([username, password, email]):
                raise ValidationError("Username, password, and email are required")

            if not ValidationUtils.validate_email(email):
                raise ValidationError("Invalid email format")

            username = ValidationUtils.sanitize_string(username, 50)
            email = ValidationUtils.sanitize_string(email, 100)
            
            # Check if user already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            )
            if existing:
                raise ValidationError("Username or email already exists")

            # Use centralized authentication system
            from university_system.infrastructure.auth.user_authentication import UserAuthentication

            auth_system = UserAuthentication()
            success = auth_system.register_user(
                username=username,
                password=password,
                email=email,
                role=role
            )

            if success:
                logger.info(f"User {username} created successfully via centralized auth system")
                return True
            else:
                raise ValidationError("User creation failed")

            return True

        except Exception as e:
            logger.error(f"User creation failed: {e}")
            raise

# Enhanced Event Management Classes
class RecurringEventManager:
    """Manages recurring events with complex patterns"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_recurring_event(self, base_event_data: Dict, recurrence_pattern: Dict) -> Tuple[bool, str]:
        """Create a recurring event with specified pattern"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create recurring events")

        if not DATEUTIL_AVAILABLE:
            raise CalendarError("dateutil library required for recurring events")

        try:
            # Validate recurrence pattern
            required_fields = ['frequency', 'interval']
            for field in required_fields:
                if field not in recurrence_pattern:
                    raise ValidationError(f"Missing required field: {field}")

            frequency_map = {
                'daily': DAILY,
                'weekly': WEEKLY,
                'monthly': MONTHLY,
                'yearly': YEARLY
            }

            if recurrence_pattern['frequency'] not in frequency_map:
                raise ValidationError("Invalid frequency. Must be daily, weekly, monthly, or yearly")

            # Validate base event data
            if not base_event_data.get('name'):
                raise ValidationError("Event name is required")

            base_event_id = str(uuid.uuid4())
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                # Create base event
                self.db_manager.execute_update(
                    """INSERT INTO events (id, name, date, date_start, date_end, description, 
                       event_type, date_added, last_modified, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (base_event_id,
                     ValidationUtils.sanitize_string(base_event_data['name']),
                     base_event_data.get('date'),
                     base_event_data.get('date_start'),
                     base_event_data.get('date_end'),
                     ValidationUtils.sanitize_string(base_event_data.get('description', ''), 1000),
                     ValidationUtils.sanitize_string(base_event_data.get('event_type', 'Academic')),
                     current_time, current_time, user_id)
                )

                # Store recurrence pattern
                recurring_id = str(uuid.uuid4())
                self.db_manager.execute_update(
                    """INSERT INTO recurring_events (id, base_event_id, frequency, interval_count, 
                       days_of_week, day_of_month, month_of_year, end_date, occurrence_count, 
                       timezone, exceptions, date_added) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (recurring_id, base_event_id, recurrence_pattern['frequency'],
                     recurrence_pattern.get('interval', 1),
                     json.dumps(recurrence_pattern.get('days_of_week', [])),
                     recurrence_pattern.get('day_of_month'),
                     recurrence_pattern.get('month_of_year'),
                     recurrence_pattern.get('end_date'),
                     recurrence_pattern.get('occurrence_count'),
                     recurrence_pattern.get('timezone', 'UTC'),
                     json.dumps(recurrence_pattern.get('exceptions', [])),
                     current_time)
                )

                # Generate occurrences
                success, message = self._generate_recurring_occurrences(base_event_id, recurrence_pattern, base_event_data)
                if not success:
                    raise CalendarError(f"Failed to generate occurrences: {message}")

            logger.info(f"Recurring event created with base ID: {base_event_id}")
            return True, f"Recurring event created with ID: {base_event_id}"

        except Exception as e:
            logger.error(f"Failed to create recurring event: {e}")
            raise CalendarError(f"Error creating recurring event: {str(e)}")

    def _generate_recurring_occurrences(self, base_event_id: str, pattern: Dict, base_event: Dict) -> Tuple[bool, str]:
        """Generate individual event occurrences from pattern"""
        try:
            # Get base event details
            start_date_str = base_event.get('date') or base_event.get('date_start')
            if not start_date_str:
                return False, "No start date found for base event"

            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

            # Configure dateutil rrule
            frequency_map = {'daily': DAILY, 'weekly': WEEKLY, 'monthly': MONTHLY, 'yearly': YEARLY}
            freq = frequency_map[pattern['frequency']]

            rrule_kwargs = {
                'freq': freq,
                'interval': pattern.get('interval', 1),
                'dtstart': start_date
            }

            if pattern.get('end_date'):
                rrule_kwargs['until'] = datetime.strptime(pattern['end_date'], "%Y-%m-%d")
            elif pattern.get('occurrence_count'):
                rrule_kwargs['count'] = min(pattern['occurrence_count'], 1000)  # Limit occurrences
            else:
                # Default to 1 year if no end specified
                rrule_kwargs['until'] = start_date + timedelta(days=365)

            if pattern.get('days_of_week'):
                rrule_kwargs['byweekday'] = pattern['days_of_week']

            # Generate occurrences
            rule = rrule(**rrule_kwargs)
            exceptions = set(pattern.get('exceptions', []))

            occurrence_count = 0
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            for occurrence_date in rule:
                if occurrence_date.strftime("%Y-%m-%d") in exceptions:
                    continue

                if occurrence_date != start_date:  # Skip the base event
                    occurrence_id = str(uuid.uuid4())

                    # Calculate end date if it's a date range
                    occurrence_end = None
                    if base_event.get('date_end'):
                        duration_days = (datetime.strptime(base_event['date_end'], "%Y-%m-%d") - start_date).days
                        occurrence_end = (occurrence_date + timedelta(days=duration_days)).strftime("%Y-%m-%d")

                    self.db_manager.execute_update(
                        """INSERT INTO events (id, name, date, date_start, date_end, description, 
                           event_type, date_added, last_modified, created_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (occurrence_id,
                         f"{base_event['name']} (Recurring)",
                         occurrence_date.strftime("%Y-%m-%d") if base_event.get('date') else None,
                         occurrence_date.strftime("%Y-%m-%d") if base_event.get('date_start') else None,
                         occurrence_end,
                         base_event.get('description', ''),
                         base_event.get('event_type', 'Academic'),
                         current_time, current_time, user_id)
                    )

                    occurrence_count += 1

            return True, f"Generated {occurrence_count} recurring occurrences"

        except Exception as e:
            logger.error(f"Failed to generate occurrences: {e}")
            return False, f"Error generating occurrences: {str(e)}"

class EventDependencyManager:
    """Manages event dependencies, prerequisites, and workflows"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self._create_dependency_tables()

    def _create_dependency_tables(self):
        """Create tables for event dependencies"""
        try:
            # Event dependencies table
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_dependencies (
                id TEXT PRIMARY KEY,
                prerequisite_event_id TEXT NOT NULL,
                dependent_event_id TEXT NOT NULL,
                dependency_type TEXT NOT NULL,
                delay_days INTEGER DEFAULT 0,
                delay_hours INTEGER DEFAULT 0,
                is_mandatory BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (prerequisite_event_id) REFERENCES events (id) ON DELETE CASCADE,
                FOREIGN KEY (dependent_event_id) REFERENCES events (id) ON DELETE CASCADE,
                UNIQUE(prerequisite_event_id, dependent_event_id)
            )''')

            # Event workflows table
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_workflows (
                id TEXT PRIMARY KEY,
                workflow_name TEXT NOT NULL,
                description TEXT,
                template_data TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_by TEXT,
                created_at TEXT NOT NULL
            )''')

            # Event sequence tracking
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_sequences (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sequence_order INTEGER NOT NULL,
                completion_status TEXT DEFAULT 'pending',
                completion_date TEXT,
                FOREIGN KEY (workflow_id) REFERENCES event_workflows (id) ON DELETE CASCADE,
                FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
            )''')

        except Exception as e:
            logger.error(f"Failed to create dependency tables: {e}")

    def add_event_dependency(self, prerequisite_event_id: str, dependent_event_id: str, 
                            dependency_type: str = 'blocking', delay_days: int = 0, 
                            delay_hours: int = 0, is_mandatory: bool = True) -> Tuple[bool, str]:
        """Add a dependency between two events"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to manage event dependencies")

        try:
            # Validate events exist
            for event_id in [prerequisite_event_id, dependent_event_id]:
                if not ValidationUtils.validate_uuid(event_id):
                    raise ValidationError(f"Invalid event ID: {event_id}")
                
                event_exists = self.db_manager.execute_query(
                    "SELECT id FROM events WHERE id = ?", (event_id,)
                )
                if not event_exists:
                    raise ValidationError(f"Event not found: {event_id}")

            # Check for circular dependencies
            if self._creates_circular_dependency(prerequisite_event_id, dependent_event_id):
                return False, "Cannot create dependency: would create circular dependency"

            dependency_id = str(uuid.uuid4())
            
            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT INTO event_dependencies 
                (id, prerequisite_event_id, dependent_event_id, dependency_type, 
                 delay_days, delay_hours, is_mandatory, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (dependency_id, prerequisite_event_id, dependent_event_id, 
                     dependency_type, delay_days, delay_hours, is_mandatory,
                     datetime.now().isoformat()))

                # Update dependent event dates if necessary
                self._update_dependent_event_dates(dependent_event_id)

            return True, f"Dependency created successfully: {dependency_id}"

        except Exception as e:
            logger.error(f"Failed to create event dependency: {e}")
            return False, f"Error creating dependency: {str(e)}"

    def _creates_circular_dependency(self, prerequisite_id: str, dependent_id: str) -> bool:
        """Check if adding this dependency would create a circular dependency"""
        def has_path(start_id: str, target_id: str, visited: set) -> bool:
            if start_id == target_id:
                return True
            if start_id in visited:
                return False
            
            visited.add(start_id)
            
            # Get all events that depend on start_id
            rows = self.db_manager.execute_query('''
            SELECT dependent_event_id FROM event_dependencies 
            WHERE prerequisite_event_id = ?
            ''', (start_id,))
            
            for row in rows:
                if has_path(row['dependent_event_id'], target_id, visited.copy()):
                    return True
            
            return False

        return has_path(dependent_id, prerequisite_id, set())

    def _update_dependent_event_dates(self, event_id: str):
        """Update event dates based on dependencies"""
        try:
            # Get all prerequisites for this event
            rows = self.db_manager.execute_query('''
            SELECT ed.prerequisite_event_id, ed.delay_days, ed.delay_hours, 
                   e.date, e.date_end
            FROM event_dependencies ed
            JOIN events e ON ed.prerequisite_event_id = e.id
            WHERE ed.dependent_event_id = ? AND ed.is_mandatory = TRUE
            ''', (event_id,))

            if not rows:
                return

            # Find the latest end date among prerequisites
            latest_end_date = None
            max_delay_days = 0
            max_delay_hours = 0

            for row in rows:
                prereq_end = row['date_end'] or row['date']
                if prereq_end:
                    prereq_date = datetime.strptime(prereq_end, "%Y-%m-%d")
                    if latest_end_date is None or prereq_date > latest_end_date:
                        latest_end_date = prereq_date
                        max_delay_days = row['delay_days']
                        max_delay_hours = row['delay_hours']

            if latest_end_date:
                # Calculate new start date
                new_start_date = latest_end_date + timedelta(
                    days=max_delay_days, hours=max_delay_hours
                )

                # Update the dependent event
                self.db_manager.execute_update('''
                UPDATE events SET date_start = ?, last_modified = ?
                WHERE id = ? AND date_start < ?
                ''', (new_start_date.strftime("%Y-%m-%d"),
                     datetime.now().isoformat(), event_id,
                     new_start_date.strftime("%Y-%m-%d")))

        except Exception as e:
            logger.error(f"Failed to update dependent event dates: {e}")

    def create_workflow(self, workflow_name: str, description: str = None, 
                       event_templates: List[Dict] = None) -> Tuple[bool, str]:
        """Create an event workflow template"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create workflows")

        try:
            workflow_id = str(uuid.uuid4())
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT INTO event_workflows (id, workflow_name, description, template_data, 
                                           is_active, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (workflow_id, workflow_name, description,
                     json.dumps(event_templates or []), True, user_id,
                     datetime.now().isoformat()))

            return True, f"Workflow created: {workflow_id}"

        except Exception as e:
            logger.error(f"Failed to create workflow: {e}")
            return False, f"Error creating workflow: {str(e)}"

    def calculate_automatic_deadlines(self, base_event_id: str, 
                                    deadline_rules: List[Dict]) -> List[Dict]:
        """Calculate automatic deadlines based on rules"""
        try:
            # Get base event
            rows = self.db_manager.execute_query(
                "SELECT * FROM events WHERE id = ?", (base_event_id,)
            )
            if not rows:
                return []

            base_event = dict(rows[0])
            base_date_str = base_event['date'] or base_event['date_start']
            if not base_date_str:
                return []

            base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
            calculated_deadlines = []

            for rule in deadline_rules:
                deadline_date = base_date - timedelta(
                    days=rule.get('days_before', 0),
                    hours=rule.get('hours_before', 0)
                )

                calculated_deadlines.append({
                    'name': rule.get('name', 'Deadline'),
                    'date': deadline_date.strftime("%Y-%m-%d"),
                    'description': rule.get('description', ''),
                    'event_type': rule.get('event_type', 'Deadline'),
                    'priority': rule.get('priority', 'medium')
                })

            return calculated_deadlines

        except Exception as e:
            logger.error(f"Failed to calculate deadlines: {e}")
            return []

class AdvancedReportingManager:
    """Comprehensive reporting and analytics system"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def generate_attendance_report(self, course_id: str = None, 
                                 date_range: Tuple[str, str] = None) -> Dict[str, Any]:
        """Generate comprehensive attendance reports"""
        if not self.auth_manager.check_permission('view_reports'):
            raise PermissionError("Insufficient permissions to generate reports")

        try:
            query = '''
            SELECT e.name as event_name, e.date as event_date, e.event_type,
                   COUNT(DISTINCT cea.student_id) as attendees,
                   ce.course_id, c.name as course_name
            FROM events e
            LEFT JOIN course_events ce ON e.id = ce.event_id
            LEFT JOIN courses c ON ce.course_id = c.id
            LEFT JOIN course_event_attendance cea ON e.id = cea.event_id
            WHERE 1=1
            '''
            params = []

            if course_id:
                query += " AND ce.course_id = ?"
                params.append(course_id)

            if date_range:
                query += " AND e.date BETWEEN ? AND ?"
                params.extend(date_range)

            query += " GROUP BY e.id ORDER BY e.date DESC"

            rows = self.db_manager.execute_query(query, tuple(params))
            
            # Calculate statistics
            total_events = len(rows)
            avg_attendance = sum(row['attendees'] for row in rows) / total_events if total_events > 0 else 0
            
            # Group by course
            course_stats = defaultdict(lambda: {'events': 0, 'total_attendance': 0})
            for row in rows:
                course_name = row['course_name'] or 'Unassigned'
                course_stats[course_name]['events'] += 1
                course_stats[course_name]['total_attendance'] += row['attendees']

            return {
                'success': True,
                'total_events': total_events,
                'average_attendance': round(avg_attendance, 2),
                'events': [dict(row) for row in rows],
                'course_statistics': dict(course_stats),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to generate attendance report: {e}")
            return {'success': False, 'error': str(e)}

    def generate_utilization_report(self, resource_type: str = None) -> Dict[str, Any]:
        """Generate resource utilization reports"""
        if not self.auth_manager.check_permission('view_reports'):
            raise PermissionError("Insufficient permissions to generate reports")

        try:
            query = '''
            SELECT r.name as resource_name, r.type as resource_type,
                   COUNT(rb.id) as total_bookings,
                   SUM(julianday(rb.end_time) - julianday(rb.start_time)) as total_hours,
                   AVG(julianday(rb.end_time) - julianday(rb.start_time)) as avg_booking_duration
            FROM resources r
            LEFT JOIN resource_bookings rb ON r.id = rb.resource_id
            WHERE rb.status = 'confirmed'
            '''
            params = []

            if resource_type:
                query += " AND r.type = ?"
                params.append(resource_type)

            query += " GROUP BY r.id ORDER BY total_bookings DESC"

            rows = self.db_manager.execute_query(query, tuple(params))

            # Calculate utilization percentages (assuming 8 hours/day, 5 days/week)
            working_hours_per_week = 40
            weeks_in_period = 52  # Adjust based on actual period

            utilization_data = []
            for row in rows:
                total_available_hours = working_hours_per_week * weeks_in_period
                utilization_percentage = (row['total_hours'] / total_available_hours) * 100 if total_available_hours > 0 else 0
                
                utilization_data.append({
                    'resource_name': row['resource_name'],
                    'resource_type': row['resource_type'],
                    'total_bookings': row['total_bookings'],
                    'total_hours': round(row['total_hours'], 2),
                    'avg_duration': round(row['avg_booking_duration'], 2),
                    'utilization_percentage': round(utilization_percentage, 2)
                })

            return {
                'success': True,
                'resources': utilization_data,
                'total_resources': len(utilization_data),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to generate utilization report: {e}")
            return {'success': False, 'error': str(e)}

    def generate_academic_year_summary(self, academic_year_id: str) -> Dict[str, Any]:
        """Generate comprehensive academic year summary"""
        if not self.auth_manager.check_permission('view_reports'):
            raise PermissionError("Insufficient permissions to generate reports")

        try:
            # Get academic year info
            year_rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE id = ?", (academic_year_id,)
            )
            if not year_rows:
                return {'success': False, 'error': 'Academic year not found'}

            year_info = dict(year_rows[0])

            # Get events for this academic year
            event_query = '''
            SELECT e.*, s.name as semester_name
            FROM events e
            LEFT JOIN semesters s ON (e.date BETWEEN s.start_date AND s.end_date)
            WHERE s.academic_year_id = ?
            ORDER BY e.date
            '''
            event_rows = self.db_manager.execute_query(event_query, (academic_year_id,))

            # Categorize events
            event_stats = defaultdict(int)
            monthly_distribution = defaultdict(int)
            
            for event in event_rows:
                event_stats[event['event_type']] += 1
                if event['date']:
                    month = datetime.strptime(event['date'], "%Y-%m-%d").strftime("%Y-%m")
                    monthly_distribution[month] += 1

            # Get semester info
            semester_rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY start_date",
                (academic_year_id,)
            )

            return {
                'success': True,
                'academic_year': year_info,
                'semesters': [dict(row) for row in semester_rows],
                'total_events': len(event_rows),
                'event_statistics': dict(event_stats),
                'monthly_distribution': dict(monthly_distribution),
                'events': [dict(row) for row in event_rows],
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to generate academic year summary: {e}")
            return {'success': False, 'error': str(e)}

class SMSNotificationManager:
    """SMS notification service using Twilio or similar services"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager, 
                 sms_config: Dict = None):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self.sms_config = sms_config or {}
        self.client = None
        
        if TWILIO_AVAILABLE and self.sms_config:
            try:
                self.client = TwilioClient(
                    self.sms_config.get('account_sid'),
                    self.sms_config.get('auth_token')
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Twilio client: {e}")

    def send_sms_notification(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """Send SMS notification"""
        if not self.client:
            return False, "SMS service not configured"

        try:
            # Validate phone number format
            if not self._validate_phone_number(phone_number):
                return False, "Invalid phone number format"

            message_obj = self.client.messages.create(
                body=message,
                from_=self.sms_config.get('from_number'),
                to=phone_number
            )

            logger.info(f"SMS sent successfully: {message_obj.sid}")
            return True, f"SMS sent successfully: {message_obj.sid}"

        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False, f"Failed to send SMS: {str(e)}"

    def _validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format"""
        import re
        # Basic international phone number validation
        pattern = r'^\+?1?[2-9]\d{2}[2-9]\d{2}\d{4}$'
        return bool(re.match(pattern, phone_number.replace('-', '').replace(' ', '')))

    def send_event_reminder_sms(self, user_id: str, event_id: str) -> Tuple[bool, str]:
        """Send SMS reminder for an event"""
        try:
            # Get user phone number
            user_rows = self.db_manager.execute_query(
                "SELECT phone_number FROM users WHERE id = ?", (user_id,)
            )
            if not user_rows or not user_rows[0]['phone_number']:
                return False, "User phone number not found"

            # Get event details
            event_rows = self.db_manager.execute_query(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            )
            if not event_rows:
                return False, "Event not found"

            event = dict(event_rows[0])
            phone_number = user_rows[0]['phone_number']

            message = f"Reminder: {event['name']} on {event['date'] or event['date_start']}"
            if event['description']:
                message += f" - {event['description'][:100]}"

            return self.send_sms_notification(phone_number, message)

        except Exception as e:
            logger.error(f"Failed to send event reminder SMS: {e}")
            return False, f"Error sending reminder: {str(e)}"

class MobileAPIManager:
    """Enhanced REST API optimized for mobile applications"""
    
    def __init__(self, calendar_manager):
        self.calendar_manager = calendar_manager
        if FLASK_AVAILABLE:
            self.app = Flask(__name__)
            CORS(self.app)
            self._setup_mobile_routes()

    def _setup_mobile_routes(self):
        """Setup mobile-optimized API routes"""
        
        @self.app.route('/api/mobile/events', methods=['GET'])
        def get_mobile_events():
            """Get events optimized for mobile view"""
            try:
                # Get parameters
                date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
                view_type = request.args.get('view', 'day')  # day, week, month
                limit = min(int(request.args.get('limit', 50)), 100)

                # Calculate date range based on view type
                base_date = datetime.strptime(date, "%Y-%m-%d")
                
                if view_type == 'day':
                    start_date = end_date = base_date
                elif view_type == 'week':
                    start_date = base_date - timedelta(days=base_date.weekday())
                    end_date = start_date + timedelta(days=6)
                elif view_type == 'month':
                    start_date = base_date.replace(day=1)
                    next_month = start_date + timedelta(days=32)
                    end_date = next_month.replace(day=1) - timedelta(days=1)

                events = self.calendar_manager.get_events_by_date_range(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )

                # Optimize for mobile
                mobile_events = []
                for event in events[:limit]:
                    mobile_events.append({
                        'id': event['id'],
                        'title': event['name'],
                        'date': event['date'] or event['date_start'],
                        'endDate': event.get('date_end'),
                        'type': event['event_type'],
                        'description': event.get('description', '')[:200],  # Truncate for mobile
                        'isAllDay': bool(event['date']),
                        'color': self._get_event_color(event['event_type'])
                    })

                return jsonify({
                    'success': True,
                    'events': mobile_events,
                    'viewType': view_type,
                    'dateRange': {
                        'start': start_date.strftime("%Y-%m-%d"),
                        'end': end_date.strftime("%Y-%m-%d")
                    },
                    'hasMore': len(events) > limit
                })

            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/mobile/events/<event_id>', methods=['GET'])
        def get_mobile_event_details(event_id):
            """Get detailed event information for mobile"""
            try:
                rows = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM events WHERE id = ?", (event_id,)
                )
                
                if not rows:
                    return jsonify({'success': False, 'error': 'Event not found'}), 404

                event = dict(rows[0])
                
                # Get additional mobile-relevant information
                event_details = {
                    'id': event['id'],
                    'title': event['name'],
                    'description': event.get('description', ''),
                    'date': event['date'] or event['date_start'],
                    'endDate': event.get('date_end'),
                    'type': event['event_type'],
                    'isAllDay': bool(event['date']),
                    'color': self._get_event_color(event['event_type']),
                    'canEdit': self._can_user_edit_event(event_id),
                    'reminders': self._get_event_reminders(event_id),
                    'location': self._get_event_location(event_id),
                    'attachments': self._get_event_attachments(event_id)
                }

                return jsonify({
                    'success': True,
                    'event': event_details
                })

            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/mobile/sync', methods=['POST'])
        def mobile_sync():
            """Sync mobile app data with server"""
            try:
                data = request.json
                last_sync = data.get('lastSync')
                
                # Get events modified since last sync
                if last_sync:
                    query = '''
                    SELECT * FROM events 
                    WHERE last_modified > ? 
                    ORDER BY last_modified DESC
                    '''
                    rows = self.calendar_manager.db_manager.execute_query(
                        query, (last_sync,)
                    )
                else:
                    # First sync - get recent events
                    rows = self.calendar_manager.db_manager.execute_query('''
                    SELECT * FROM events 
                    WHERE date >= date('now', '-30 days')
                    ORDER BY date
                    ''')

                sync_data = {
                    'events': [dict(row) for row in rows],
                    'syncTime': datetime.now().isoformat(),
                    'hasMore': False  # Could implement pagination here
                }

                return jsonify({
                    'success': True,
                    'data': sync_data
                })

            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

    def _get_event_color(self, event_type: str) -> str:
        """Get color for event type"""
        color_map = {
            'Academic': '#1E3A8A',
            'Administrative': '#7C2D12',
            'Social': '#15803D',
            'Sports': '#DC2626',
            'Holiday': '#7C3AED',
            'Deadline': '#EA580C'
        }
        return color_map.get(event_type, '#6B7280')

    def _can_user_edit_event(self, event_id: str) -> bool:
        """Check if current user can edit event"""
        try:
            return self.calendar_manager.auth_manager.check_permission('manage_schedules')
        except:
            return False

    def _get_event_reminders(self, event_id: str) -> List[Dict]:
        """Get reminders for an event"""
        try:
            rows = self.calendar_manager.db_manager.execute_query('''
            SELECT * FROM notification_queue 
            WHERE event_id = ? AND status = 'pending'
            ''', (event_id,))
            return [dict(row) for row in rows]
        except:
            return []

    def _get_event_location(self, event_id: str) -> Optional[str]:
        """Get event location from resource bookings"""
        try:
            rows = self.calendar_manager.db_manager.execute_query('''
            SELECT r.location FROM resource_bookings rb
            JOIN resources r ON rb.resource_id = r.id
            WHERE rb.event_id = ? AND rb.status = 'confirmed'
            LIMIT 1
            ''', (event_id,))
            return rows[0]['location'] if rows else None
        except:
            return None

    def _get_event_attachments(self, event_id: str) -> List[Dict]:
        """Get event attachments (placeholder for future implementation)"""
        return []

class EventCategoryManager:
    """Manages event categories and tagging system"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_category(self, name: str, color_code: str = None, description: str = None) -> Tuple[bool, str]:
        """Create a new event category"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to manage categories")

        try:
            if not name or not name.strip():
                raise ValidationError("Category name is required")

            name = ValidationUtils.sanitize_string(name, 100)
            description = ValidationUtils.sanitize_string(description or "", 500)

            # Check if category already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM event_categories WHERE name = ?", (name,)
            )
            if existing:
                return False, f"Category '{name}' already exists"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO event_categories (name, color_code, description, date_added)
                       VALUES (?, ?, ?, ?)""",
                    (name, color_code, description, datetime.now().isoformat())
                )

            logger.info(f"Category '{name}' created")
            return True, f"Category '{name}' created successfully"

        except Exception as e:
            logger.error(f"Failed to create category: {e}")
            raise CalendarError(f"Failed to create category: {str(e)}")

    def create_tag(self, name: str, color_code: str = None) -> Tuple[bool, str]:
        """Create a new event tag"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to manage tags")

        try:
            if not name or not name.strip():
                raise ValidationError("Tag name is required")

            name = ValidationUtils.sanitize_string(name, 50)

            # Check if tag already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM event_tags WHERE name = ?", (name,)
            )
            if existing:
                return False, f"Tag '{name}' already exists"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO event_tags (name, color_code, date_added)
                       VALUES (?, ?, ?)""",
                    (name, color_code, datetime.now().isoformat())
                )

            logger.info(f"Tag '{name}' created")
            return True, f"Tag '{name}' created successfully"

        except Exception as e:
            logger.error(f"Failed to create tag: {e}")
            raise CalendarError(f"Failed to create tag: {str(e)}")

    def assign_tags_to_event(self, event_id: str, tag_names: List[str]) -> Tuple[bool, str]:
        """Assign multiple tags to an event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to assign tags")

        try:
            if not ValidationUtils.validate_uuid(event_id):
                raise ValidationError("Invalid event ID")

            # Verify event exists
            event_exists = self.db_manager.execute_query(
                "SELECT id FROM events WHERE id = ?", (event_id,)
            )
            if not event_exists:
                raise ValidationError(f"Event with ID '{event_id}' not found")

            successful_assignments = 0
            
            with self.db_manager.transaction():
                for tag_name in tag_names:
                    tag_name = ValidationUtils.sanitize_string(tag_name, 50)
                    
                    # Get or create tag
                    tag_rows = self.db_manager.execute_query(
                        "SELECT id FROM event_tags WHERE name = ?", (tag_name,)
                    )
                    
                    if tag_rows:
                        tag_id = tag_rows[0]['id']
                    else:
                        # Create tag if it doesn't exist
                        success, tag_id = self.create_tag(tag_name)
                        if not success:
                            continue

                    # Check if assignment already exists
                    existing_assignment = self.db_manager.execute_query(
                        "SELECT 1 FROM event_tag_assignments WHERE event_id = ? AND tag_id = ?",
                        (event_id, tag_id)
                    )

                    if not existing_assignment:
                        self.db_manager.execute_update(
                            """INSERT INTO event_tag_assignments (event_id, tag_id, date_added)
                               VALUES (?, ?, ?)""",
                            (event_id, tag_id, datetime.now().isoformat())
                        )
                        successful_assignments += 1

            return True, f"Successfully assigned {successful_assignments} tags to event"

        except Exception as e:
            logger.error(f"Failed to assign tags: {e}")
            raise CalendarError(f"Failed to assign tags: {str(e)}")

class CourseManager:
    """Manages courses and their integration with events"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_course(self, course_data: Dict) -> Tuple[bool, str]:
        """Create a new course"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create courses")

        try:
            required_fields = ['code', 'name']
            for field in required_fields:
                if field not in course_data or not str(course_data[field]).strip():
                    raise ValidationError(f"Required field '{field}' is missing or empty")

            course_code = ValidationUtils.sanitize_string(course_data['code'], 20)
            course_name = ValidationUtils.sanitize_string(course_data['name'], 200)

            # Check if course code already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM courses WHERE code = ?", (course_code,)
            )
            if existing:
                return False, f"Course with code '{course_code}' already exists"

            course_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO courses (id, code, name, credits, department, instructor_id, 
                       academic_year_id, semester_id, status, date_added)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (course_id, course_code, course_name,
                     course_data.get('credits', 3),
                     ValidationUtils.sanitize_string(course_data.get('department', ''), 100),
                     course_data.get('instructor_id'),
                     course_data.get('academic_year_id'),
                     course_data.get('semester_id'),
                     ValidationUtils.sanitize_string(course_data.get('status', 'active'), 20),
                     datetime.now().isoformat())
                )

            logger.info(f"Course '{course_code}' created with ID: {course_id}")
            return True, f"Course created with ID: {course_id}"

        except Exception as e:
            logger.error(f"Failed to create course: {e}")
            raise CalendarError(f"Failed to create course: {str(e)}")

    def link_event_to_course(self, event_id: str, course_id: str, event_sub_type: str = None) -> Tuple[bool, str]:
        """Link an event to a course"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to link events to courses")

        try:
            # Validate event_id as UUID (events use UUID format)
            if not ValidationUtils.validate_uuid(event_id):
                raise ValidationError("Invalid event ID format - must be a valid UUID")

            # Validate course_id is not empty (courses use integer IDs, not UUIDs)
            if not course_id or not str(course_id).strip():
                raise ValidationError("Invalid course ID - cannot be empty")

            # Verify both event and course exist
            event_exists = self.db_manager.execute_query(
                "SELECT id FROM events WHERE id = ?", (event_id,)
            )
            if not event_exists:
                return False, f"Event with ID '{event_id}' not found"

            course_exists = self.db_manager.execute_query(
                "SELECT id FROM courses WHERE id = ?", (course_id,)
            )
            if not course_exists:
                return False, f"Course with ID '{course_id}' not found"

            # Check if link already exists
            existing_link = self.db_manager.execute_query(
                "SELECT 1 FROM course_events WHERE event_id = ? AND course_id = ?",
                (event_id, course_id)
            )

            if existing_link:
                return False, "Event is already linked to this course"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO course_events (event_id, course_id, event_sub_type)
                       VALUES (?, ?, ?)""",
                    (event_id, course_id, ValidationUtils.sanitize_string(event_sub_type or "", 50))
                )

            logger.info(f"Event {event_id} linked to course {course_id}")
            return True, "Event successfully linked to course"

        except Exception as e:
            logger.error(f"Failed to link event to course: {e}")
            raise CalendarError(f"Failed to link event to course: {str(e)}")

class ResourceManager:
    """Manages resources like rooms, equipment, etc."""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_resource(self, resource_data: Dict) -> Tuple[bool, str]:
        """Create a new resource"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create resources")

        try:
            required_fields = ['name', 'type']
            for field in required_fields:
                if field not in resource_data or not str(resource_data[field]).strip():
                    raise ValidationError(f"Required field '{field}' is missing or empty")

            resource_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO resources (id, name, type, capacity, location, equipment, status, date_added)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (resource_id,
                     ValidationUtils.sanitize_string(resource_data['name'], 200),
                     ValidationUtils.sanitize_string(resource_data['type'], 50),
                     resource_data.get('capacity'),
                     ValidationUtils.sanitize_string(resource_data.get('location', ''), 200),
                     ValidationUtils.sanitize_string(resource_data.get('equipment', ''), 500),
                     ValidationUtils.sanitize_string(resource_data.get('status', 'available'), 20),
                     datetime.now().isoformat())
                )

            logger.info(f"Resource created with ID: {resource_id}")
            return True, f"Resource created with ID: {resource_id}"

        except Exception as e:
            logger.error(f"Failed to create resource: {e}")
            raise CalendarError(f"Failed to create resource: {str(e)}")

    def book_resource(self, booking_data: Dict) -> Tuple[bool, str]:
        """Book a resource for an event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to book resources")

        try:
            required_fields = ['resource_id', 'event_id', 'start_time', 'end_time']
            for field in required_fields:
                if field not in booking_data:
                    raise ValidationError(f"Required field '{field}' is missing")

            # Validate time format
            start_time = booking_data['start_time']
            end_time = booking_data['end_time']
            
            if not ValidationUtils.validate_datetime(start_time) or not ValidationUtils.validate_datetime(end_time):
                raise ValidationError("Invalid datetime format. Use YYYY-MM-DD HH:MM:SS")

            # Check for conflicts
            conflicts = self._check_booking_conflicts(
                booking_data['resource_id'],
                start_time,
                end_time,
                booking_data.get('exclude_booking_id')
            )

            if conflicts:
                return False, f"Resource booking conflicts with existing bookings: {', '.join(conflicts)}"

            booking_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO resource_bookings (id, resource_id, event_id, start_time, end_time, 
                       status, notes, date_added) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (booking_id,
                     booking_data['resource_id'],
                     booking_data['event_id'],
                     start_time,
                     end_time,
                     ValidationUtils.sanitize_string(booking_data.get('status', 'confirmed'), 20),
                     ValidationUtils.sanitize_string(booking_data.get('notes', ''), 500),
                     datetime.now().isoformat())
                )

            logger.info(f"Resource booked with ID: {booking_id}")
            return True, f"Resource booked with ID: {booking_id}"

        except Exception as e:
            logger.error(f"Failed to book resource: {e}")
            raise CalendarError(f"Failed to book resource: {str(e)}")

    def _check_booking_conflicts(self, resource_id: str, start_time: str, end_time: str, 
                                exclude_booking_id: str = None) -> List[str]:
        """Check for booking conflicts"""
        try:
            query = """
                SELECT rb.id, e.name 
                FROM resource_bookings rb
                JOIN events e ON rb.event_id = e.id
                WHERE rb.resource_id = ? 
                AND rb.status = 'confirmed'
                AND NOT (rb.end_time <= ? OR rb.start_time >= ?)
            """
            params = [resource_id, start_time, end_time]

            if exclude_booking_id:
                query += " AND rb.id != ?"
                params.append(exclude_booking_id)

            rows = self.db_manager.execute_query(query, tuple(params))
            conflicts = [f"{row['id']} ({row['name']})" for row in rows]

            return conflicts

        except Exception as e:
            logger.error(f"Failed to check booking conflicts: {e}")
            return []

class NotificationManager:
    """Manages notifications and reminders"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager, smtp_config: Dict = None):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self.smtp_config = smtp_config or {}

    def set_notification_preference(self, user_id: str, notification_type: str, 
                                  enabled: bool = True, advance_time: int = 60, 
                                  method: str = 'email') -> Tuple[bool, str]:
        """Set notification preferences for a user"""
        try:
            if not ValidationUtils.validate_uuid(user_id):
                raise ValidationError("Invalid user ID")

            notification_type = ValidationUtils.sanitize_string(notification_type, 50)
            method = ValidationUtils.sanitize_string(method, 20)

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT OR REPLACE INTO notification_preferences 
                       (user_id, notification_type, enabled, advance_time, method, date_added)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, notification_type, enabled, advance_time, method,
                     datetime.now().isoformat())
                )

            return True, "Notification preference updated successfully"

        except Exception as e:
            logger.error(f"Failed to set notification preference: {e}")
            raise CalendarError(f"Failed to set notification preference: {str(e)}")

    def schedule_notification(self, user_id: str, event_id: str, notification_type: str,
                            scheduled_time: str) -> Tuple[bool, str]:
        """Schedule a notification for an event"""
        try:
            if not all([ValidationUtils.validate_uuid(user_id), ValidationUtils.validate_uuid(event_id)]):
                raise ValidationError("Invalid user or event ID")

            if not ValidationUtils.validate_datetime(scheduled_time):
                raise ValidationError("Invalid scheduled time format")

            notification_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO notification_queue (id, user_id, event_id, notification_type, 
                       scheduled_time, status, date_added) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (notification_id, user_id, event_id,
                     ValidationUtils.sanitize_string(notification_type, 50),
                     scheduled_time, 'pending', datetime.now().isoformat())
                )

            return True, f"Notification scheduled with ID: {notification_id}"

        except Exception as e:
            logger.error(f"Failed to schedule notification: {e}")
            raise CalendarError(f"Failed to schedule notification: {str(e)}")

    def send_email_notification(self, recipient_email: str, subject: str, body: str) -> Tuple[bool, str]:
        """Send email notification"""
        if not EMAIL_AVAILABLE:
            return False, "Email functionality not available"

        try:
            from university_system.infrastructure.email.smtp import send_email_via_smtp

            if not ValidationUtils.validate_email(recipient_email):
                raise ValidationError("Invalid recipient email")

            subject = ValidationUtils.sanitize_string(subject, 200)
            body = ValidationUtils.sanitize_string(body, 5000)

            current_time = datetime.now().isoformat()
            success = send_email_via_smtp(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                cc=None,
                bcc=None,
                attachments=None,
                current_time=current_time
            )

            if success:
                logger.info(f"Email sent to {recipient_email}")
                return True, "Email sent successfully"
            else:
                logger.error(f"Failed to send email to {recipient_email}")
                return False, "Failed to send email"

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False, f"Failed to send email: {str(e)}"

class EnhancedCalendarVisualizationManager:
    """Advanced calendar visualization and views"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_timeline_visualization(self, academic_year_id: str, 
                                    output_path: str = None) -> Tuple[bool, str]:
        """Create timeline visualization of academic year"""
        if not MATPLOTLIB_AVAILABLE:
            return False, "Matplotlib not available for visualizations"

        try:
            # Get events for academic year
            query = '''
            SELECT e.*, s.name as semester_name
            FROM events e
            LEFT JOIN semesters s ON (e.date BETWEEN s.start_date AND s.end_date)
            WHERE s.academic_year_id = ?
            ORDER BY COALESCE(e.date, e.date_start)
            '''
            rows = self.db_manager.execute_query(query, (academic_year_id,))
            
            if not rows:
                return False, "No events found for academic year"

            # Create timeline plot
            fig, ax = plt.subplots(figsize=(15, 8))
            
            # Color mapping for event types
            colors = {
                'Academic': '#1E3A8A',
                'Administrative': '#7C2D12', 
                'Social': '#15803D',
                'Sports': '#DC2626',
                'Holiday': '#7C3AED',
                'Deadline': '#EA580C'
            }

            events_by_type = defaultdict(list)
            
            for event in rows:
                event_date = event['date'] or event['date_start']
                if event_date:
                    date_obj = datetime.strptime(event_date, "%Y-%m-%d")
                    events_by_type[event['event_type']].append({
                        'date': date_obj,
                        'name': event['name'],
                        'semester': event['semester_name']
                    })

            # Plot events by type
            y_pos = 0
            type_positions = {}
            
            for event_type, events in events_by_type.items():
                dates = [e['date'] for e in events]
                y_positions = [y_pos] * len(dates)
                
                ax.scatter(dates, y_positions, 
                          c=colors.get(event_type, '#6B7280'),
                          label=event_type, s=100, alpha=0.7)
                
                # Add event names as annotations
                for i, event in enumerate(events):
                    if i % 3 == 0:  # Only show every 3rd label to avoid crowding
                        ax.annotate(event['name'][:20], 
                                  (event['date'], y_pos),
                                  xytext=(5, 5), textcoords='offset points',
                                  fontsize=8, alpha=0.8)
                
                type_positions[event_type] = y_pos
                y_pos += 1

            # Format plot
            ax.set_ylabel('Event Types')
            ax.set_xlabel('Date')
            ax.set_title(f'Academic Calendar Timeline - {academic_year_id}')
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)
            
            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            plt.xticks(rotation=45)
            
            # Set y-axis labels
            ax.set_yticks(list(type_positions.values()))
            ax.set_yticklabels(list(type_positions.keys()))

            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                plt.close()
                return True, f"Timeline saved to {output_path}"
            else:
                plt.show()
                return True, "Timeline displayed"

        except Exception as e:
            logger.error(f"Failed to create timeline visualization: {e}")
            return False, f"Error creating timeline: {str(e)}"

    def create_conflict_visualization(self, date_range: Tuple[str, str], 
                                    output_path: str = None) -> Tuple[bool, str]:
        """Create visualization showing event conflicts"""
        if not MATPLOTLIB_AVAILABLE:
            return False, "Matplotlib not available for visualizations"

        try:
            # Get overlapping events
            query = '''
            SELECT e1.id as event1_id, e1.name as event1_name, 
                   e1.date_start as event1_start, e1.date_end as event1_end,
                   e2.id as event2_id, e2.name as event2_name,
                   e2.date_start as event2_start, e2.date_end as event2_end
            FROM events e1
            JOIN events e2 ON e1.id != e2.id
            WHERE e1.date_start BETWEEN ? AND ?
            AND e2.date_start BETWEEN ? AND ?
            AND e1.date_start < e2.date_end
            AND e2.date_start < e1.date_end
            '''
            
            rows = self.db_manager.execute_query(query, 
                                               date_range + date_range)

            if not rows:
                return True, "No conflicts found in date range"

            # Create conflict visualization
            fig, ax = plt.subplots(figsize=(12, 8))
            
            conflicts = []
            for row in rows:
                conflicts.append({
                    'event1': row['event1_name'],
                    'event2': row['event2_name'],
                    'start1': datetime.strptime(row['event1_start'], "%Y-%m-%d"),
                    'end1': datetime.strptime(row['event1_end'], "%Y-%m-%d"),
                    'start2': datetime.strptime(row['event2_start'], "%Y-%m-%d"),
                    'end2': datetime.strptime(row['event2_end'], "%Y-%m-%d")
                })

            # Plot conflicts
            for i, conflict in enumerate(conflicts):
                y_pos = i
                
                # Event 1
                ax.barh(y_pos - 0.2, (conflict['end1'] - conflict['start1']).days,
                       left=conflict['start1'], height=0.3, 
                       color='red', alpha=0.6, label='Event 1' if i == 0 else "")
                
                # Event 2
                ax.barh(y_pos + 0.2, (conflict['end2'] - conflict['start2']).days,
                       left=conflict['start2'], height=0.3,
                       color='blue', alpha=0.6, label='Event 2' if i == 0 else "")
                
                # Add labels
                ax.text(conflict['start1'], y_pos - 0.2, conflict['event1'][:20],
                       ha='left', va='center', fontsize=8)
                ax.text(conflict['start2'], y_pos + 0.2, conflict['event2'][:20],
                       ha='left', va='center', fontsize=8)

            ax.set_ylabel('Conflicts')
            ax.set_xlabel('Date')
            ax.set_title('Event Conflicts Visualization')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                plt.close()
                return True, f"Conflict visualization saved to {output_path}"
            else:
                plt.show()
                return True, "Conflict visualization displayed"

        except Exception as e:
            logger.error(f"Failed to create conflict visualization: {e}")
            return False, f"Error creating visualization: {str(e)}"

class AcademicDeadlineManager:
    """Enhanced academic deadline and milestone tracking"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self._create_deadline_tables()

    def _create_deadline_tables(self):
        """Create tables for deadline management"""
        try:
            # Project milestones table
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS project_milestones (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                milestone_name TEXT NOT NULL,
                due_date TEXT NOT NULL,
                completion_percentage REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                course_id TEXT,
                student_id TEXT,
                description TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )''')

            # Graduation requirements table
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS graduation_requirements (
                id TEXT PRIMARY KEY,
                requirement_name TEXT NOT NULL,
                requirement_type TEXT NOT NULL,
                credits_required INTEGER,
                course_category TEXT,
                deadline_date TEXT,
                is_mandatory BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL
            )''')

            # Student requirement tracking
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS student_requirement_progress (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                credits_completed REAL DEFAULT 0.0,
                completion_percentage REAL DEFAULT 0.0,
                status TEXT DEFAULT 'in_progress',
                completion_date TEXT,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (requirement_id) REFERENCES graduation_requirements (id),
                UNIQUE(student_id, requirement_id)
            )''')

        except Exception as e:
            logger.error(f"Failed to create deadline tables: {e}")

    def create_project_milestone(self, project_name: str, milestone_name: str,
                                due_date: str, course_id: str = None,
                                student_id: str = None, description: str = None) -> Tuple[bool, str]:
        """Create a project milestone"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create milestones")

        try:
            if not ValidationUtils.validate_date(due_date):
                raise ValidationError("Invalid due date format")

            milestone_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT INTO project_milestones 
                (id, project_name, milestone_name, due_date, course_id, 
                 student_id, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (milestone_id, project_name, milestone_name, due_date,
                     course_id, student_id, description, 
                     datetime.now().isoformat()))

            return True, f"Milestone created: {milestone_id}"

        except Exception as e:
            logger.error(f"Failed to create milestone: {e}")
            return False, f"Error creating milestone: {str(e)}"

    def update_milestone_progress(self, milestone_id: str, 
                                completion_percentage: float,
                                status: str = None) -> Tuple[bool, str]:
        """Update milestone progress"""
        try:
            if not (0 <= completion_percentage <= 100):
                raise ValidationError("Completion percentage must be between 0 and 100")

            update_data = {
                'completion_percentage': completion_percentage,
                'last_updated': datetime.now().isoformat()
            }

            if status:
                update_data['status'] = status

            if completion_percentage >= 100 and not status:
                update_data['status'] = 'completed'

            # Build update query
            set_clauses = []
            params = []
            for field, value in update_data.items():
                set_clauses.append(f"{field} = ?")
                params.append(value)
            
            params.append(milestone_id)
            query = f"UPDATE project_milestones SET {', '.join(set_clauses)} WHERE id = ?"

            rows_affected = self.db_manager.execute_update(query, tuple(params))
            
            if rows_affected > 0:
                return True, "Milestone progress updated"
            else:
                return False, "Milestone not found"

        except Exception as e:
            logger.error(f"Failed to update milestone progress: {e}")
            return False, f"Error updating progress: {str(e)}"

    def track_graduation_requirements(self, student_id: str) -> Dict[str, Any]:
        """Track graduation requirements for a student"""
        try:
            # Get all requirements
            req_rows = self.db_manager.execute_query('''
            SELECT gr.*, srp.credits_completed, srp.completion_percentage, 
                   srp.status, srp.completion_date
            FROM graduation_requirements gr
            LEFT JOIN student_requirement_progress srp ON 
                gr.id = srp.requirement_id AND srp.student_id = ?
            ORDER BY gr.requirement_type, gr.requirement_name
            ''', (student_id,))

            requirements = []
            total_requirements = len(req_rows)
            completed_requirements = 0

            for row in req_rows:
                req_data = dict(row)
                if req_data['status'] == 'completed':
                    completed_requirements += 1
                requirements.append(req_data)

            # Calculate overall completion percentage
            overall_completion = (completed_requirements / total_requirements * 100) if total_requirements > 0 else 0

            return {
                'student_id': student_id,
                'total_requirements': total_requirements,
                'completed_requirements': completed_requirements,
                'overall_completion_percentage': round(overall_completion, 2),
                'requirements': requirements,
                'graduation_eligible': completed_requirements == total_requirements
            }

        except Exception as e:
            logger.error(f"Failed to track graduation requirements: {e}")
            return {'error': str(e)}

class BatchOperationsManager:
    """User-friendly bulk operations interface"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def bulk_create_events(self, events_data: List[Dict], 
                          template_id: str = None) -> Dict[str, Any]:
        """Bulk create events from data or template"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions for bulk operations")

        try:
            created_events = []
            failed_events = []
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                for event_data in events_data:
                    try:
                        # Validate event data
                        if not event_data.get('name'):
                            failed_events.append({
                                'data': event_data,
                                'error': 'Missing event name'
                            })
                            continue

                        event_id = str(uuid.uuid4())
                        
                        self.db_manager.execute_update('''
                        INSERT INTO events (id, name, date, date_start, date_end, 
                                          description, event_type, date_added, 
                                          last_modified, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            event_id,
                            ValidationUtils.sanitize_string(event_data['name'], 255),
                            event_data.get('date'),
                            event_data.get('date_start'),
                            event_data.get('date_end'),
                            ValidationUtils.sanitize_string(event_data.get('description', ''), 1000),
                            ValidationUtils.sanitize_string(event_data.get('event_type', 'Academic'), 50),
                            current_time,
                            current_time,
                            user_id
                        ))

                        created_events.append({
                            'event_id': event_id,
                            'name': event_data['name']
                        })

                    except Exception as e:
                        failed_events.append({
                            'data': event_data,
                            'error': str(e)
                        })

            return {
                'success': True,
                'created_count': len(created_events),
                'failed_count': len(failed_events),
                'created_events': created_events,
                'failed_events': failed_events
            }

        except Exception as e:
            logger.error(f"Bulk create events failed: {e}")
            return {'success': False, 'error': str(e)}

    def bulk_update_events(self, event_ids: List[str], 
                          update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk update multiple events"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions for bulk operations")

        try:
            updated_events = []
            failed_events = []

            # Validate update data
            allowed_fields = {'name', 'description', 'event_type', 'date', 'date_start', 'date_end'}
            invalid_fields = set(update_data.keys()) - allowed_fields
            if invalid_fields:
                return {'success': False, 'error': f'Invalid fields: {invalid_fields}'}

            with self.db_manager.transaction():
                for event_id in event_ids:
                    try:
                        if not ValidationUtils.validate_uuid(event_id):
                            failed_events.append({
                                'event_id': event_id,
                                'error': 'Invalid event ID format'
                            })
                            continue

                        # Build update query
                        set_clauses = []
                        params = []
                        
                        for field, value in update_data.items():
                            if field in allowed_fields and value is not None:
                                set_clauses.append(f"{field} = ?")
                                if field in ['name', 'description', 'event_type']:
                                    params.append(ValidationUtils.sanitize_string(str(value), 255 if field == 'name' else 1000))
                                else:
                                    params.append(str(value))

                        if set_clauses:
                            set_clauses.append("last_modified = ?")
                            params.append(datetime.now().isoformat())
                            params.append(event_id)

                            query = f"UPDATE events SET {', '.join(set_clauses)} WHERE id = ?"
                            rows_affected = self.db_manager.execute_update(query, tuple(params))

                            if rows_affected > 0:
                                updated_events.append(event_id)
                            else:
                                failed_events.append({
                                    'event_id': event_id,
                                    'error': 'Event not found'
                                })

                    except Exception as e:
                        failed_events.append({
                            'event_id': event_id,
                            'error': str(e)
                        })

            return {
                'success': True,
                'updated_count': len(updated_events),
                'failed_count': len(failed_events),
                'updated_events': updated_events,
                'failed_events': failed_events
            }

        except Exception as e:
            logger.error(f"Bulk update events failed: {e}")
            return {'success': False, 'error': str(e)}

    def create_event_template(self, template_name: str, 
                             template_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Create reusable event template"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create templates")

        try:
            template_id = str(uuid.uuid4())
            user_id = self.auth_manager.current_user['id']

            # Ensure templates table exists
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_templates (
                id TEXT PRIMARY KEY,
                template_name TEXT NOT NULL,
                template_data TEXT NOT NULL,
                created_by TEXT,
                created_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            )''')

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT INTO event_templates (id, template_name, template_data, 
                                           created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (template_id, template_name, json.dumps(template_data),
                     user_id, datetime.now().isoformat()))

            return True, f"Template created: {template_id}"

        except Exception as e:
            logger.error(f"Failed to create event template: {e}")
            return False, f"Error creating template: {str(e)}"

class EnhancedTimeZoneManager:
    """Comprehensive timezone and DST handling"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self._create_timezone_tables()

    def _create_timezone_tables(self):
        """Create timezone configuration tables"""
        try:
            # User timezone preferences
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS user_timezone_preferences (
                user_id TEXT PRIMARY KEY,
                timezone_name TEXT NOT NULL,
                auto_dst BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )''')

            # Event timezone data
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_timezones (
                event_id TEXT PRIMARY KEY,
                timezone_name TEXT NOT NULL,
                utc_offset_hours INTEGER NOT NULL,
                is_dst_active BOOLEAN DEFAULT FALSE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
            )''')

        except Exception as e:
            logger.error(f"Failed to create timezone tables: {e}")

    def set_user_timezone(self, user_id: str, timezone_name: str, 
                         auto_dst: bool = True) -> Tuple[bool, str]:
        """Set timezone preference for a user"""
        try:
            # Validate timezone
            if not self._validate_timezone(timezone_name):
                return False, "Invalid timezone name"

            current_time = datetime.now().isoformat()

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT OR REPLACE INTO user_timezone_preferences 
                (user_id, timezone_name, auto_dst, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (user_id, timezone_name, auto_dst, current_time, current_time))

            return True, f"Timezone set to {timezone_name}"

        except Exception as e:
            logger.error(f"Failed to set user timezone: {e}")
            return False, f"Error setting timezone: {str(e)}"

    def _validate_timezone(self, timezone_name: str) -> bool:
        """Validate timezone name"""
        try:
            if not TIMEZONE_AVAILABLE:
                return timezone_name in ['UTC', 'EST', 'PST', 'CST', 'MST']
            
            pytz.timezone(timezone_name)
            return True
        except:
            return False

    def convert_event_time(self, event_id: str, target_timezone: str) -> Dict[str, Any]:
        """Convert event time to different timezone"""
        if not TIMEZONE_AVAILABLE:
            return {'error': 'Timezone conversion not available without pytz'}

        try:
            # Get event details
            event_rows = self.db_manager.execute_query(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            )
            if not event_rows:
                return {'error': 'Event not found'}

            event = dict(event_rows[0])
            
            # Get event timezone
            tz_rows = self.db_manager.execute_query(
                "SELECT timezone_name FROM event_timezones WHERE event_id = ?", 
                (event_id,)
            )
            
            source_tz_name = tz_rows[0]['timezone_name'] if tz_rows else 'UTC'
            
            # Convert times
            source_tz = pytz.timezone(source_tz_name)
            target_tz = pytz.timezone(target_timezone)

            converted_event = event.copy()
            
            for date_field in ['date', 'date_start', 'date_end']:
                if event.get(date_field):
                    # Parse date
                    dt = datetime.strptime(event[date_field], "%Y-%m-%d")
                    
                    # Localize to source timezone
                    dt_localized = source_tz.localize(dt)
                    
                    # Convert to target timezone
                    dt_converted = dt_localized.astimezone(target_tz)
                    
                    converted_event[date_field] = dt_converted.strftime("%Y-%m-%d %H:%M:%S %Z")

            return {
                'success': True,
                'original_timezone': source_tz_name,
                'target_timezone': target_timezone,
                'converted_event': converted_event
            }

        except Exception as e:
            logger.error(f"Failed to convert event time: {e}")
            return {'error': str(e)}

    def get_dst_transitions(self, timezone_name: str, year: int) -> List[Dict]:
        """Get DST transition dates for a timezone and year"""
        if not TIMEZONE_AVAILABLE:
            return []

        try:
            tz = pytz.timezone(timezone_name)
            
            # Get transitions for the year
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            transitions = []
            
            # Sample dates throughout the year to find transitions
            current_date = start_date
            prev_offset = None
            
            while current_date < end_date:
                dt_localized = tz.localize(current_date.replace(hour=12))
                current_offset = dt_localized.utcoffset()
                
                if prev_offset is not None and current_offset != prev_offset:
                    # Found a transition
                    transitions.append({
                        'date': current_date.strftime("%Y-%m-%d"),
                        'from_offset': str(prev_offset),
                        'to_offset': str(current_offset),
                        'type': 'spring_forward' if current_offset > prev_offset else 'fall_back'
                    })
                
                prev_offset = current_offset
                current_date += timedelta(days=1)

            return transitions

        except Exception as e:
            logger.error(f"Failed to get DST transitions: {e}")
            return []

class AdvancedSearchManager:
    """Provides advanced search and filtering capabilities"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def advanced_search(self, search_criteria: Dict) -> Tuple[bool, List[Dict]]:
        """Perform advanced search with multiple criteria"""
        try:
            base_query = """
                SELECT DISTINCT e.*, 
                       GROUP_CONCAT(DISTINCT et.name) as tags,
                       GROUP_CONCAT(DISTINCT c.name) as courses,
                       ec.name as category_name
                FROM events e
                LEFT JOIN event_tag_assignments eta ON e.id = eta.event_id
                LEFT JOIN event_tags et ON eta.tag_id = et.id
                LEFT JOIN course_events ce ON e.id = ce.event_id
                LEFT JOIN courses c ON ce.course_id = c.id
                LEFT JOIN event_categories ec ON e.event_type = ec.name
            """

            conditions = []
            params = []

            # Text search with sanitization
            if search_criteria.get('text'):
                search_text = ValidationUtils.sanitize_string(search_criteria['text'], 200)
                conditions.append("(e.name LIKE ? OR e.description LIKE ?)")
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern, search_pattern])

            # Date range with validation
            if search_criteria.get('start_date'):
                if ValidationUtils.validate_date(search_criteria['start_date']):
                    conditions.append("(e.date >= ? OR e.date_start >= ?)")
                    params.extend([search_criteria['start_date'], search_criteria['start_date']])

            if search_criteria.get('end_date'):
                if ValidationUtils.validate_date(search_criteria['end_date']):
                    conditions.append("(e.date <= ? OR e.date_end <= ?)")
                    params.extend([search_criteria['end_date'], search_criteria['end_date']])

            # Event type with sanitization
            if search_criteria.get('event_type'):
                event_type = ValidationUtils.sanitize_string(search_criteria['event_type'], 50)
                conditions.append("e.event_type = ?")
                params.append(event_type)

            # Tags with proper parameterization
            if search_criteria.get('tags') and isinstance(search_criteria['tags'], list):
                sanitized_tags = [ValidationUtils.sanitize_string(tag, 50) for tag in search_criteria['tags']]
                if sanitized_tags:
                    placeholders = ','.join(['?' for _ in sanitized_tags])
                    conditions.append(f"et.name IN ({placeholders})")
                    params.extend(sanitized_tags)

            # Course (courses use integer IDs, not UUIDs)
            if search_criteria.get('course_id'):
                course_id_value = str(search_criteria['course_id']).strip()
                if course_id_value:
                    conditions.append("c.id = ?")
                    params.append(course_id_value)

            # Build final query
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)

            base_query += " GROUP BY e.id ORDER BY COALESCE(e.date, e.date_start) LIMIT ?"
            params.append(1000)  # Limit results for performance

            rows = self.db_manager.execute_query(base_query, tuple(params))
            results = [dict(row) for row in rows]

            return True, results

        except Exception as e:
            logger.error(f"Advanced search failed: {e}")
            return False, f"Search failed: {str(e)}"

    def save_search_preset(self, user_id: str, name: str, filters: Dict) -> Tuple[bool, str]:
        """Save search criteria as a preset"""
        try:
            if not ValidationUtils.validate_uuid(user_id):
                raise ValidationError("Invalid user ID")

            name = ValidationUtils.sanitize_string(name, 100)
            if not name:
                raise ValidationError("Preset name is required")

            preset_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO search_presets (id, name, user_id, filters, date_added)
                       VALUES (?, ?, ?, ?, ?)""",
                    (preset_id, name, user_id, json.dumps(filters),
                     datetime.now().isoformat())
                )

            return True, f"Search preset '{name}' saved successfully"

        except Exception as e:
            logger.error(f"Failed to save search preset: {e}")
            raise CalendarError(f"Failed to save preset: {str(e)}")

class AuditManager:
    """Manages audit trail and change tracking"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._ensure_audit_table()

    def _ensure_audit_table(self):
        """Ensure audit_log table exists with proper schema"""
        try:
            # Check if audit_log table exists and get its schema
            rows = self.db_manager.execute_query(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='audit_log'"
            )
            
            if not rows:
                # Table doesn't exist, create it
                self._create_audit_table()
            else:
                # Table exists, check if it has id column
                schema = rows[0][0].lower() if rows[0][0] else ""
                if 'id' not in schema or 'primary key' not in schema:
                    # Try to add id column if missing
                    try:
                        self.db_manager.execute_update(
                            "ALTER TABLE audit_log ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT"
                        )
                        logging.info("Added id column to existing audit_log table")
                    except Exception as e:
                        logging.warning(f"Could not add id column to audit_log: {e}")
                        # Continue without id column
                        
        except Exception as e:
            logging.warning(f"Could not ensure audit table: {e}")

    def _create_audit_table(self):
        """Create audit_log table with proper schema"""
        try:
            self.db_manager.execute_update('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    old_values TEXT,
                    new_values TEXT,
                    user_id TEXT,
                    timestamp TEXT NOT NULL,
                    ip_address TEXT
                )
            ''')
            logging.info("Created audit_log table")
        except Exception as e:
            logging.error(f"Failed to create audit_log table: {e}")

    def log_change(self, table_name: str, record_id: str, action: str, 
                  old_values: Dict = None, new_values: Dict = None, 
                  user_id: str = None, ip_address: str = None) -> Tuple[bool, str]:
        """Log a change to the audit trail with fallback for missing id column"""
        try:
            # Check what columns exist in the audit_log table
            rows = self.db_manager.execute_query("PRAGMA table_info(audit_log)")
            columns = [row[1] for row in rows]  # row[1] is column name
            
            # Sanitize inputs
            table_name = ValidationUtils.sanitize_string(table_name, 50)
            record_id = ValidationUtils.sanitize_string(record_id, 100)
            action = ValidationUtils.sanitize_string(action, 20)
            timestamp = datetime.now().isoformat()

            if 'id' in columns:
                # Table has id column, use it
                self.db_manager.execute_update('''
                    INSERT INTO audit_log (table_name, record_id, action, old_values, 
                           new_values, user_id, timestamp, ip_address) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    table_name, record_id, action,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    user_id, timestamp, ip_address
                ))
            else:
                # Table doesn't have id column, insert without it
                available_columns = ['table_name', 'record_id', 'action', 'timestamp']
                values = [table_name, record_id, action, timestamp]
                
                # Add optional columns if they exist
                if 'old_values' in columns and old_values:
                    available_columns.append('old_values')
                    values.append(json.dumps(old_values))
                    
                if 'new_values' in columns and new_values:
                    available_columns.append('new_values')
                    values.append(json.dumps(new_values))
                    
                if 'user_id' in columns and user_id:
                    available_columns.append('user_id')
                    values.append(user_id)
                    
                if 'ip_address' in columns and ip_address:
                    available_columns.append('ip_address')
                    values.append(ip_address)

                # Build and execute query
                placeholders = ', '.join(['?'] * len(values))
                column_names = ', '.join(available_columns)
                
                self.db_manager.execute_update(
                    f"INSERT INTO audit_log ({column_names}) VALUES ({placeholders})",
                    tuple(values)
                )

            return True, "Change logged successfully"

        except Exception as e:
            logging.error(f"Failed to log audit entry: {e}")
            # Don't fail the main operation if audit logging fails
            return False, f"Failed to log change: {str(e)}"

    def get_audit_trail(self, table_name: str = None, record_id: str = None, 
                       user_id: str = None, limit: int = 100) -> Tuple[bool, List[Dict]]:
        """Retrieve audit trail with optional filters"""
        try:
            query = "SELECT * FROM audit_log"
            conditions = []
            params = []

            if table_name:
                conditions.append("table_name = ?")
                params.append(ValidationUtils.sanitize_string(table_name, 50))

            if record_id:
                conditions.append("record_id = ?")
                params.append(ValidationUtils.sanitize_string(record_id, 100))

            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(min(limit, 1000))  # Cap at 1000 records

            rows = self.db_manager.execute_query(query, tuple(params))
            results = [dict(row) for row in rows]

            return True, results

        except Exception as e:
            logging.error(f"Failed to retrieve audit trail: {e}")
            return False, []
        
class HolidayManager:
    """Manages holidays and regional calendar support"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def import_national_holidays(self, country_code: str, year: int, region: str = None) -> Tuple[bool, str]:
        """Import national holidays for a specific country and year"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to import holidays")

        if not HOLIDAYS_AVAILABLE:
            return False, "holidays library not available. Install with: pip install holidays"

        try:
            country_code = ValidationUtils.sanitize_string(country_code, 10).upper()
            region = ValidationUtils.sanitize_string(region or "", 50) if region else None

            # Validate year
            current_year = datetime.now().year
            if not (current_year - 10 <= year <= current_year + 10):
                raise ValidationError("Year must be within 10 years of current year")

            # Get holidays using the holidays library
            try:
                if region:
                    holiday_calendar = holidays.country_holidays(country_code, state=region, years=year)
                else:
                    holiday_calendar = holidays.country_holidays(country_code, years=year)
            except Exception as e:
                return False, f"Invalid country code or region: {country_code}, {region}"

            calendar_id = str(uuid.uuid4())
            imported_count = 0
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                # Create holiday calendar entry
                self.db_manager.execute_update(
                    """INSERT INTO holiday_calendars (id, name, country_code, region, is_active, date_added)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (calendar_id,
                     f"{country_code} {region or 'National'} Holidays {year}",
                     country_code, region, True, current_time)
                )

                # Import holidays as events
                for date, name in holiday_calendar.items():
                    event_id = str(uuid.uuid4())
                    
                    # Check if holiday already exists
                    existing = self.db_manager.execute_query(
                        "SELECT id FROM events WHERE date = ? AND name = ? AND event_type = 'Holiday'",
                        (date.strftime("%Y-%m-%d"), str(name))
                    )
                    
                    if not existing:
                        self.db_manager.execute_update(
                            """INSERT INTO events (id, name, date, description, event_type, 
                               date_added, last_modified, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (event_id, str(name)[:255], date.strftime("%Y-%m-%d"),
                             f"National holiday - {country_code}",
                             'Holiday', current_time, current_time, user_id)
                        )
                        imported_count += 1

            logger.info(f"Imported {imported_count} holidays for {country_code} {year}")
            return True, f"Imported {imported_count} holidays for {country_code} {year}"

        except Exception as e:
            logger.error(f"Failed to import holidays: {e}")
            return False, f"Failed to import holidays: {str(e)}"

class DataVisualizationManager:
    """Creates various data visualizations for calendar analytics"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_calendar_heatmap(self, year: int, output_path: str = None) -> Tuple[bool, str]:
        """Create a calendar heatmap showing event density"""
        if not self.auth_manager.check_permission('export_data'):
            raise PermissionError("Insufficient permissions to create visualizations")

        if not PLOTLY_AVAILABLE:
            return False, "Plotly not available for visualizations"

        try:
            # Validate year
            current_year = datetime.now().year
            if not (current_year - 5 <= year <= current_year + 5):
                raise ValidationError("Year must be within 5 years of current year")

            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"

            query = """
                SELECT DATE(COALESCE(e.date, e.date_start)) as event_date, COUNT(*) as event_count
                FROM events e
                WHERE (e.date BETWEEN ? AND ?) 
                OR (e.date_start BETWEEN ? AND ?)
                GROUP BY DATE(COALESCE(e.date, e.date_start))
                ORDER BY event_date
            """

            rows = self.db_manager.execute_query(query, (start_date, end_date, start_date, end_date))
            data = {row['event_date']: row['event_count'] for row in rows}

            # Create date range for the year
            start = datetime(year, 1, 1)
            dates = []
            event_counts = []

            days_in_year = 366 if cal.isleap(year) else 365
            for i in range(days_in_year):
                current_date = start + timedelta(days=i)
                date_str = current_date.strftime("%Y-%m-%d")
                dates.append(current_date)
                event_counts.append(data.get(date_str, 0))

            # Create heatmap using plotly
            fig = go.Figure(data=go.Heatmap(
                x=[d.strftime("%U") for d in dates],  # Week number
                y=[d.strftime("%A") for d in dates],  # Day of week
                z=event_counts,
                colorscale='Viridis',
                hoverongaps=False,
                hovertemplate='Week %{x}<br>%{y}<br>Events: %{z}<extra></extra>'
            ))

            fig.update_layout(
                title=f'Academic Calendar Activity Heatmap - {year}',
                xaxis_title='Week of Year',
                yaxis_title='Day of Week',
                height=600
            )

            if output_path:
                safe_path = ValidationUtils.sanitize_filename(output_path)
                fig.write_html(safe_path)
                return True, f"Heatmap saved to {safe_path}"
            else:
                html_str = plot(fig, output_type='div', include_plotlyjs=True)
                return True, html_str

        except Exception as e:
            logger.error(f"Failed to create heatmap: {e}")
            return False, f"Error creating heatmap: {str(e)}"

    def create_event_distribution_chart(self, timeframe: str = 'month', output_path: str = None) -> Tuple[bool, str]:
        """Create event distribution charts by type"""
        if not self.auth_manager.check_permission('export_data'):
            raise PermissionError("Insufficient permissions to create visualizations")

        if not PLOTLY_AVAILABLE:
            return False, "Plotly not available for visualizations"

        try:
            timeframe = ValidationUtils.sanitize_string(timeframe, 20).lower()
            
            query = """
                SELECT e.event_type, COUNT(*) as count
                FROM events e
            """

            params = []
            
            # Add time filter
            if timeframe == 'month':
                current_month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
                query += " WHERE COALESCE(e.date, e.date_start) >= ?"
                params.append(current_month_start)
            elif timeframe == 'semester':
                semester_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                query += " WHERE COALESCE(e.date, e.date_start) >= ?"
                params.append(semester_start)
            elif timeframe == 'year':
                year_start = datetime.now().replace(month=1, day=1).strftime("%Y-%m-%d")
                query += " WHERE COALESCE(e.date, e.date_start) >= ?"
                params.append(year_start)

            query += " GROUP BY e.event_type ORDER BY count DESC"

            rows = self.db_manager.execute_query(query, tuple(params))
            data = [dict(row) for row in rows]

            if not data:
                return False, "No data found for the specified timeframe"

            # Create pie chart
            event_types = [row['event_type'] for row in data]
            counts = [row['count'] for row in data]

            fig = px.pie(
                values=counts,
                names=event_types,
                title=f'Event Distribution by Type - {timeframe.title()}'
            )

            fig.update_traces(textposition='inside', textinfo='percent+label')

            if output_path:
                safe_path = ValidationUtils.sanitize_filename(output_path)
                fig.write_html(safe_path)
                return True, f"Distribution chart saved to {safe_path}"
            else:
                html_str = plot(fig, output_type='div', include_plotlyjs=True)
                return True, html_str

        except Exception as e:
            logger.error(f"Failed to create distribution chart: {e}")
            return False, f"Error creating distribution chart: {str(e)}"

# Main Academic Calendar Manager
class AcademicCalendarManager:
    """Enhanced Academic Calendar Manager with all features"""
    
    def __init__(self, config: CalendarConfig = None, auth_manager: AuthenticationManager = None):
        self.config = config or CalendarConfig()
        self.db_manager = DatabaseManager(self.config.db_file)
        
        # Use the provided auth_manager (which should be the main UserAuth system)
        if auth_manager:
            self.auth_manager = auth_manager
        else:
            # Create a wrapper that uses the main auth system
            self.auth_manager = AuthenticationManager(self.db_manager)
            try:
                self.auth_manager._load_permissions()
            except Exception as e:
                logger.warning(f"Failed to load permissions in fallback auth manager: {e}")
                self.auth_manager.current_user = None
                self.auth_manager.permissions_cache = {}
        
        self.audit_manager = AuditManager(self.db_manager)
        
        # Initialize feature managers with error handling
        try:
            self.recurring_events = RecurringEventManager(self.db_manager, self.auth_manager)
            self.categories = EventCategoryManager(self.db_manager, self.auth_manager)
            self.courses = CourseManager(self.db_manager, self.auth_manager)
            self.resources = ResourceManager(self.db_manager, self.auth_manager)
            self.notifications = NotificationManager(self.db_manager, self.auth_manager)
            self.search = AdvancedSearchManager(self.db_manager, self.auth_manager)
            self.holidays = HolidayManager(self.db_manager, self.auth_manager)
            self.visualizations = DataVisualizationManager(self.db_manager, self.auth_manager)
            self.event_dependencies = EventDependencyManager(self.db_manager, self.auth_manager)
            self.advanced_reporting = AdvancedReportingManager(self.db_manager, self.auth_manager)
            self.sms_notifications = SMSNotificationManager(self.db_manager, self.auth_manager)
            self.mobile_api = MobileAPIManager(self) if FLASK_AVAILABLE else None
            self.enhanced_visualizations = EnhancedCalendarVisualizationManager(self.db_manager, self.auth_manager)
            self.academic_deadlines = AcademicDeadlineManager(self.db_manager, self.auth_manager)
            self.batch_operations = BatchOperationsManager(self.db_manager, self.auth_manager)
            self.timezone_manager = EnhancedTimeZoneManager(self.db_manager, self.auth_manager)
        except Exception as e:
            logger.warning(f"Some feature managers failed to initialize: {e}")
        
        # Initialize database with proper error handling
        try:
            self._initialize_database()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            # Try to continue with existing schema by creating minimal required tables
            try:
                self._create_minimal_tables()
                logger.info("Created minimal tables as fallback")
            except Exception as verify_error:
                logger.error(f"Minimal table creation failed: {verify_error}")
                # Don't raise here - allow the system to continue with limited functionality
                logger.warning("Calendar system running with limited functionality")
        
        try:
            self._create_backup_directory()
        except Exception as e:
            logger.warning(f"Could not create backup directory: {e}")

    def _initialize_database(self):
        """Initialize database schema with better error handling"""
        try:
            logger.info("Initializing calendar database...")
            
            # Create core tables first
            self._create_core_tables()
            
            # Create enhanced tables
            self._create_enhanced_tables()
            
            # Create indexes
            self._create_indexes()
            
            # Create default data
            self._create_default_data()
            
            logger.info("Calendar database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}")

    def _create_minimal_tables(self):
        """Create minimal required tables if full initialization fails"""
        try:
            logger.info("Creating minimal calendar tables...")
            
            # Create the most basic tables needed for calendar functionality
            minimal_tables = [
                '''CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    date TEXT,
                    date_start TEXT,
                    date_end TEXT,
                    description TEXT,
                    event_type TEXT DEFAULT 'Academic',
                    date_added TEXT NOT NULL,
                    last_modified TEXT,
                    created_by TEXT
                )''',
                
                '''CREATE TABLE IF NOT EXISTS academic_years (
                    id TEXT PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    date_added TEXT NOT NULL
                )''',
                
                '''CREATE TABLE IF NOT EXISTS semesters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    date_added TEXT NOT NULL
                )''',
                
                '''CREATE TABLE IF NOT EXISTS trip_calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT DEFAULT 'trip_event',
                    created_at TEXT NOT NULL,
                    UNIQUE (trip_id, event_id)
                )'''
            ]
            
            for table_sql in minimal_tables:
                try:
                    self.db_manager.execute_update(table_sql)
                    logger.debug(f"Created table successfully")
                except Exception as e:
                    logger.warning(f"Table creation warning: {e}")
            
            logger.info("Minimal calendar tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create minimal tables: {e}")
            raise

    def _create_backup_directory(self):
        """Create backup directory if it doesn't exist"""
        try:
            import os
            backup_dir = getattr(self.config, 'backup_directory', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            logger.debug(f"Backup directory ensured: {backup_dir}")
        except Exception as e:
            logger.warning(f"Could not create backup directory: {e}")

    def _verify_required_tables(self):
        """Verify that required tables exist, create missing ones"""
        try:
            required_tables = {
                'academic_years': '''
                    CREATE TABLE IF NOT EXISTS academic_years (
                        id TEXT PRIMARY KEY,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        date_added TEXT NOT NULL
                    )
                ''',
                'semesters': '''
                    CREATE TABLE IF NOT EXISTS semesters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        academic_year_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        date_added TEXT NOT NULL
                    )
                ''',
                'events': '''
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        date TEXT,
                        date_start TEXT,
                        date_end TEXT,
                        description TEXT,
                        event_type TEXT DEFAULT 'Academic',
                        date_added TEXT NOT NULL,
                        last_modified TEXT,
                        created_by TEXT
                    )
                ''',
                'event_categories': '''
                    CREATE TABLE IF NOT EXISTS event_categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        color_code TEXT,
                        description TEXT,
                        date_added TEXT NOT NULL
                    )
                '''
            }
            
            for table_name, create_sql in required_tables.items():
                try:
                    # Test if table exists by querying it
                    self.db_manager.execute_query(f"SELECT COUNT(*) FROM {table_name} LIMIT 1")
                    logger.debug(f"Table {table_name} exists")
                except Exception:
                    # Table doesn't exist, create it
                    logger.info(f"Creating missing table: {table_name}")
                    self.db_manager.execute_update(create_sql)
                    logger.info(f"Successfully created table: {table_name}")
            
            logger.info("Required tables verified/created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Table verification failed: {e}")
            return False

    def _create_core_tables(self):
        """Create core database tables"""
        try:
            tables = [
                '''CREATE TABLE IF NOT EXISTS academic_years (
                    id TEXT PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    date_added TEXT NOT NULL,
                    CONSTRAINT valid_dates CHECK (start_date < end_date)
                )''',
                
                '''CREATE TABLE IF NOT EXISTS semesters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    registration_start TEXT,
                    registration_end TEXT,
                    final_exams_start TEXT,
                    final_exams_end TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (academic_year_id) REFERENCES academic_years (id) ON DELETE CASCADE,
                    UNIQUE(academic_year_id, name),
                    CONSTRAINT valid_semester_dates CHECK (start_date < end_date)
                )''',
                
                '''CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    date TEXT,
                    date_start TEXT,
                    date_end TEXT,
                    description TEXT,
                    event_type TEXT DEFAULT 'Academic',
                    date_added TEXT NOT NULL,
                    last_modified TEXT,
                    created_by TEXT,
                    CONSTRAINT valid_event_dates CHECK (
                        (date IS NOT NULL AND date_start IS NULL AND date_end IS NULL) OR
                        (date IS NULL AND date_start IS NOT NULL AND date_end IS NOT NULL AND date_start <= date_end)
                    )
                )'''
            ]

            for table_sql in tables:
                self.db_manager.execute_update(table_sql)
                
        except Exception as e:
            logger.error(f"Failed to create core tables: {e}")
            raise

    def _create_enhanced_tables(self):
        """Create enhanced feature tables with better error handling"""
        try:
            enhanced_tables = [
                '''CREATE TABLE IF NOT EXISTS event_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color_code TEXT,
                    date_added TEXT NOT NULL
                )''',
                
                '''CREATE TABLE IF NOT EXISTS event_tag_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES event_tags (id) ON DELETE CASCADE,
                    UNIQUE(event_id, tag_id)
                )''',
                
                '''CREATE TABLE IF NOT EXISTS courses (
                    id TEXT PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    credits INTEGER DEFAULT 3,
                    department TEXT,
                    instructor_id TEXT,
                    academic_year_id TEXT,
                    semester_id TEXT,
                    status TEXT DEFAULT 'active',
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (academic_year_id) REFERENCES academic_years (id),
                    FOREIGN KEY (semester_id) REFERENCES semesters (id)
                )''',
                
                '''CREATE TABLE IF NOT EXISTS course_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    event_sub_type TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
                    UNIQUE(event_id, course_id)
                )''',
                
                '''CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    capacity INTEGER,
                    location TEXT,
                    equipment TEXT,
                    status TEXT DEFAULT 'available',
                    date_added TEXT NOT NULL
                )''',
                
                '''CREATE TABLE IF NOT EXISTS resource_bookings (
                    id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    event_id TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    status TEXT DEFAULT 'confirmed',
                    notes TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                )''',
                
                '''CREATE TABLE IF NOT EXISTS notification_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT TRUE,
                    advance_time INTEGER DEFAULT 60,
                    method TEXT DEFAULT 'email',
                    date_added TEXT NOT NULL,
                    UNIQUE(user_id, notification_type)
                )''',
                
                '''CREATE TABLE IF NOT EXISTS notification_queue (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_id TEXT,
                    notification_type TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    message TEXT,
                    date_added TEXT NOT NULL,
                    sent_at TEXT,
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                )''',
                
                '''CREATE TABLE IF NOT EXISTS search_presets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    filters TEXT NOT NULL,
                    date_added TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                )''',
                
                '''CREATE TABLE IF NOT EXISTS holiday_calendars (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country_code TEXT NOT NULL,
                    region TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    date_added TEXT NOT NULL
                )''',
                
                '''CREATE TABLE IF NOT EXISTS recurring_events (
                    id TEXT PRIMARY KEY,
                    base_event_id TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    interval_count INTEGER DEFAULT 1,
                    days_of_week TEXT,
                    day_of_month INTEGER,
                    month_of_year INTEGER,
                    end_date TEXT,
                    occurrence_count INTEGER,
                    timezone TEXT DEFAULT 'UTC',
                    exceptions TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (base_event_id) REFERENCES events (id) ON DELETE CASCADE
                )''',
                
                '''CREATE TABLE IF NOT EXISTS backup_history (
                    id TEXT PRIMARY KEY,
                    backup_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    backup_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT
                )''',
                
                '''CREATE TABLE IF NOT EXISTS course_event_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    attendance_status TEXT DEFAULT 'present',
                    notes TEXT,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                    UNIQUE(event_id, student_id)
                )''',
                
                '''CREATE TABLE IF NOT EXISTS trip_calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT DEFAULT 'trip_event',
                    created_at TEXT NOT NULL,
                    UNIQUE (trip_id, event_id)
                )''',

                '''CREATE TABLE IF NOT EXISTS event_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color_code TEXT,
                    description TEXT,
                    date_added TEXT NOT NULL
                )''',

            ]

            for table_sql in enhanced_tables:
                try:
                    self.db_manager.execute_update(table_sql)
                    logger.debug(f"Created enhanced table successfully")
                except Exception as e:
                    logger.warning(f"Enhanced table creation warning: {e}")
                    
        except Exception as e:
            logger.warning(f"Some enhanced tables failed to create: {e}")

    def _create_indexes(self):
        """Create database indexes for performance"""
        try:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_events_date ON events(date)",
                "CREATE INDEX IF NOT EXISTS idx_events_date_start ON events(date_start)",
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)",
                "CREATE INDEX IF NOT EXISTS idx_events_created_by ON events(created_by)",
                "CREATE INDEX IF NOT EXISTS idx_semesters_academic_year ON semesters(academic_year_id)"
            ]

            for index_sql in indexes:
                try:
                    self.db_manager.execute_update(index_sql)
                except Exception as e:
                    logger.debug(f"Index creation note: {e}")
                    
        except Exception as e:
            logger.warning(f"Index creation had issues: {e}")

    def _create_default_data(self):
        """Create default data if database is empty"""
        try:
            # Check if data already exists
            rows = self.db_manager.execute_query("SELECT COUNT(*) as count FROM academic_years")
            if rows and rows[0][0] > 0:
                return

            current_year = datetime.now().year
            academic_year_id = f"{current_year}-{current_year+1}"
            current_time = datetime.now().isoformat()

            # Create default academic year
            self.db_manager.execute_update(
                "INSERT OR IGNORE INTO academic_years (id, start_date, end_date, date_added) VALUES (?, ?, ?, ?)",
                (academic_year_id, f"{current_year}-09-01", f"{current_year+1}-05-31", current_time)
            )

            # Create default semesters
            semester_data = [
                (academic_year_id, "Fall", f"{current_year}-09-01", f"{current_year}-12-20", current_time),
                (academic_year_id, "Spring", f"{current_year+1}-01-15", f"{current_year+1}-05-31", current_time)
            ]
            
            for semester in semester_data:
                try:
                    self.db_manager.execute_update(
                        "INSERT OR IGNORE INTO semesters (academic_year_id, name, start_date, end_date, date_added) VALUES (?, ?, ?, ?, ?)",
                        semester
                    )
                except Exception as e:
                    logger.debug(f"Semester creation note: {e}")

            # Create default categories
            default_categories = [
                ("Academic", "#1E3A8A", "Academic events like lectures, exams"),
                ("Trip", "#15803D", "Educational trips and excursions"),
                ("Holiday", "#7C3AED", "Holidays and breaks"),
                ("Deadline", "#EA580C", "Important deadlines")
            ]
            
            for name, color, description in default_categories:
                try:
                    self.db_manager.execute_update(
                        "INSERT OR IGNORE INTO event_categories (name, color_code, description, date_added) VALUES (?, ?, ?, ?)",
                        (name, color, description, current_time)
                    )
                except Exception as e:
                    logger.debug(f"Category creation note: {e}")
                    
        except Exception as e:
            logger.warning(f"Default data creation had issues: {e}")

    def get_trips_for_calendar_integration(self):
        """Get trips that can be integrated with calendar"""
        try:
            # sqlite3 is imported globally from university_system.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get trips that don't have calendar events yet
            cursor.execute('''
                SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
                FROM trips t
                LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
                WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open', 'confirmed')
                ORDER BY t.start_date
            ''')
            
            trips = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'id': trip[0],
                    'name': trip[1],
                    'destination': trip[2],
                    'start_date': trip[3],
                    'end_date': trip[4],
                    'status': trip[5]
                }
                for trip in trips
            ]
            
        except Exception as e:
            logger.error(f"Error getting trips for calendar integration: {e}")
            return []
    
    def get_calendar_events_for_trip(self, trip_id):
        """Get calendar events linked to a specific trip"""
        try:
            # sqlite3 is imported globally from university_system.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT e.id, e.name, e.date, e.date_start, e.date_end, e.description, e.event_type
                FROM trip_calendar_events tce
                JOIN events e ON tce.event_id = e.id
                WHERE tce.trip_id = ?
                ORDER BY COALESCE(e.date, e.date_start)
            ''', (trip_id,))
            
            events = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'id': event[0],
                    'name': event[1],
                    'date': event[2],
                    'date_start': event[3],
                    'date_end': event[4],
                    'description': event[5],
                    'event_type': event[6]
                }
                for event in events
            ]
            
        except Exception as e:
            logger.error(f"Error getting calendar events for trip: {e}")
            return []
    
    def remove_trip_calendar_link(self, trip_id, event_id):
        """Remove the link between a trip and calendar event"""
        try:
            # sqlite3 is imported globally from university_system.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM trip_calendar_events 
                WHERE trip_id = ? AND event_id = ?
            ''', (trip_id, event_id))
            
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            
            if deleted:
                logger.info(f"Removed link between trip {trip_id} and event {event_id}")
                return {'success': True, 'message': 'Link removed successfully'}
            else:
                return {'success': False, 'message': 'Link not found'}
                
        except Exception as e:
            logger.error(f"Error removing trip-calendar link: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def get_current_user_permissions(self):
        """Get current user's permissions for menu display"""
        try:
            if not self.auth_manager or not self.auth_manager.current_user:
                return set()
            
            # Get permissions from the main auth system
            from university_system.infrastructure.auth.user_authentication import _current_auth_instance
            if _current_auth_instance and _current_auth_instance.current_user:
                user_permissions = _current_auth_instance.current_user.get('permissions', [])
                return set(user_permissions)
            
            return set()
            
        except Exception as e:
            logger.warning(f"Could not get user permissions: {e}")
            return set()
    
    def verify_calendar_database_integrity(self):
        """Verify and repair calendar database integrity"""
        try:
            logger.info("Verifying calendar database integrity...")
            
            # Check for required tables
            required_tables = [
                'academic_years', 'semesters', 'events', 'event_categories'
            ]
            
            missing_tables = []
            for table in required_tables:
                try:
                    self.db_manager.execute_query(f"SELECT COUNT(*) FROM {table} LIMIT 1")
                except Exception:
                    missing_tables.append(table)
            
            if missing_tables:
                logger.warning(f"Missing tables detected: {missing_tables}")
                self._create_minimal_tables()
                logger.info("Created missing tables")
            
            # Check for data consistency
            self._check_data_consistency()
            
            logger.info("Database integrity verification completed")
            return True
            
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False
    
    def _check_data_consistency(self):
        """Check for data consistency issues"""
        try:
            # Check for orphaned events (events without valid academic year context)
            orphaned_events = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM events e
                WHERE e.date_start IS NOT NULL 
                AND NOT EXISTS (
                    SELECT 1 FROM semesters s 
                    WHERE e.date_start BETWEEN s.start_date AND s.end_date
                )
            ''')
            
            if orphaned_events and orphaned_events[0]['count'] > 0:
                logger.warning(f"Found {orphaned_events[0]['count']} orphaned events")
            
            # Check for invalid date ranges
            invalid_ranges = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM events 
                WHERE date_start IS NOT NULL AND date_end IS NOT NULL 
                AND date_start > date_end
            ''')
            
            if invalid_ranges and invalid_ranges[0]['count'] > 0:
                logger.warning(f"Found {invalid_ranges[0]['count']} events with invalid date ranges")
                
        except Exception as e:
            logger.warning(f"Data consistency check had issues: {e}")
    
    def get_system_stats(self):
        """Get system statistics for dashboard"""
        try:
            stats = {}
            
            # Count events by type
            event_counts = self.db_manager.execute_query('''
                SELECT event_type, COUNT(*) as count 
                FROM events 
                GROUP BY event_type
            ''')
            stats['events_by_type'] = {row['event_type']: row['count'] for row in event_counts}
            
            # Count total academic years
            year_count = self.db_manager.execute_query('SELECT COUNT(*) as count FROM academic_years')
            stats['total_academic_years'] = year_count[0]['count'] if year_count else 0
            
            # Count total semesters
            semester_count = self.db_manager.execute_query('SELECT COUNT(*) as count FROM semesters')
            stats['total_semesters'] = semester_count[0]['count'] if semester_count else 0
            
            # Get current academic period
            current_year = self.get_current_academic_year()
            current_semester = self.get_current_semester()
            
            stats['current_academic_year'] = current_year['id'] if current_year else 'None'
            stats['current_semester'] = current_semester['name'] if current_semester else 'None'
            
            # Count upcoming events (next 30 days)
            future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            upcoming_events = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM events 
                WHERE COALESCE(date, date_start) BETWEEN ? AND ?
            ''', (current_date, future_date))
            
            stats['upcoming_events'] = upcoming_events[0]['count'] if upcoming_events else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def cleanup_old_data(self, days_old=365):
        """Clean up old data to maintain database performance"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions for data cleanup")
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime("%Y-%m-%d")
            
            # Clean up old events
            old_events = self.db_manager.execute_update('''
                DELETE FROM events 
                WHERE COALESCE(date, date_end) < ? 
                AND event_type NOT IN ('Holiday', 'Academic')
            ''', (cutoff_date,))
            
            # Clean up old notifications
            old_notifications = self.db_manager.execute_update('''
                DELETE FROM notification_queue 
                WHERE scheduled_time < ? AND status IN ('sent', 'failed')
            ''', (cutoff_date,))
            
            # Clean up old audit logs (keep important ones)
            old_audit = self.db_manager.execute_update('''
                DELETE FROM audit_log 
                WHERE timestamp < ? AND action NOT IN ('DELETE', 'CREATE')
            ''', (cutoff_date,))
            
            logger.info(f"Cleanup completed: {old_events} events, {old_notifications} notifications, {old_audit} audit logs")
            
            return {
                'success': True,
                'cleaned_events': old_events,
                'cleaned_notifications': old_notifications,
                'cleaned_audit_logs': old_audit
            }
            
        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def export_system_configuration(self):
        """Export system configuration for backup/migration"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to export configuration")
        
        try:
            config_data = {
                'academic_years': [],
                'semesters': [],
                'event_categories': [],
                'export_timestamp': datetime.now().isoformat(),
                'system_version': '1.0'
            }
            
            # Export academic years
            years = self.db_manager.execute_query('SELECT * FROM academic_years ORDER BY start_date')
            config_data['academic_years'] = [dict(row) for row in years]
            
            # Export semesters
            semesters = self.db_manager.execute_query('SELECT * FROM semesters ORDER BY academic_year_id, start_date')
            config_data['semesters'] = [dict(row) for row in semesters]
            
            # Export event categories
            categories = self.db_manager.execute_query('SELECT * FROM event_categories ORDER BY name')
            config_data['event_categories'] = [dict(row) for row in categories]
            
            return config_data
            
        except Exception as e:
            logger.error(f"Configuration export failed: {e}")
            raise CalendarError(f"Configuration export failed: {e}")
    
    def import_system_configuration(self, config_data):
        """Import system configuration from backup"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to import configuration")
        
        try:
            imported_counts = {'academic_years': 0, 'semesters': 0, 'event_categories': 0}
            
            with self.db_manager.transaction():
                # Import academic years
                for year_data in config_data.get('academic_years', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO academic_years (id, start_date, end_date, date_added)
                            VALUES (?, ?, ?, ?)
                        ''', (year_data['id'], year_data['start_date'], year_data['end_date'], year_data['date_added']))
                        imported_counts['academic_years'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import academic year {year_data.get('id')}: {e}")
                
                # Import semesters
                for semester_data in config_data.get('semesters', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO semesters (academic_year_id, name, start_date, end_date, date_added)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (semester_data['academic_year_id'], semester_data['name'], 
                             semester_data['start_date'], semester_data['end_date'], semester_data['date_added']))
                        imported_counts['semesters'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import semester {semester_data.get('name')}: {e}")
                
                # Import event categories
                for category_data in config_data.get('event_categories', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO event_categories (name, color_code, description, date_added)
                            VALUES (?, ?, ?, ?)
                        ''', (category_data['name'], category_data.get('color_code'), 
                             category_data.get('description'), category_data['date_added']))
                        imported_counts['event_categories'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import category {category_data.get('name')}: {e}")
            
            logger.info(f"Configuration import completed: {imported_counts}")
            return {'success': True, 'imported': imported_counts}
            
        except Exception as e:
            logger.error(f"Configuration import failed: {e}")
            return {'success': False, 'error': str(e)}
    
    # Trip integration method
    def create_trip_event(self, trip_id, event_details=None):
        """Create a calendar event for a trip"""
        if not self.auth_manager or not self.auth_manager.current_user:
            return {'success': False, 'message': 'Authentication required'}
        
        if not self.auth_manager.check_permission('manage_schedules'):
            return {'success': False, 'message': 'Insufficient permissions'}
        
        try:
            # Get trip details from trip_management
            # sqlite3 is imported globally from university_system.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trips WHERE id = ?', (trip_id,))
            trip = cursor.fetchone()
            
            if not trip:
                conn.close()
                return {'success': False, 'message': 'Trip not found'}
            
            # Create event details
            trip_id_val, trip_name, description, destination, start_date, end_date = trip[:6]
            
            event_name = event_details.get('name', f"Trip: {trip_name}") if event_details else f"Trip: {trip_name}"
            event_description = event_details.get('description', f"Trip to {destination} - {description or 'No description'}") if event_details else f"Trip to {destination}"
            
            # Create the calendar event
            result = self.add_event(
                name=event_name,
                date_start=start_date,
                date_end=end_date,
                description=event_description,
                event_type='Trip'
            )
            
            if result['success']:
                # Link trip to event
                cursor.execute('''
                    INSERT OR IGNORE INTO trip_calendar_events (trip_id, event_id, created_at)
                    VALUES (?, ?, ?)
                ''', (trip_id, result['event_id'], datetime.now().isoformat()))
                conn.commit()
            
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"Error creating trip event: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    # Core event management methods
    def add_event(self, name: str, date: Optional[str] = None, 
                  date_start: Optional[str] = None, date_end: Optional[str] = None,
                  description: Optional[str] = None, event_type: str = 'Academic') -> Dict[str, Any]:
        """Add a new event to the calendar"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add events")

        # Validate inputs
        if not name or not name.strip():
            raise ValidationError("Event name is required")

        if not date and not (date_start and date_end):
            raise ValidationError("Either date or date_start and date_end are required")

        if date and not ValidationUtils.validate_date(date):
            raise ValidationError("Invalid date format. Use YYYY-MM-DD")

        if date_start and not ValidationUtils.validate_date(date_start):
            raise ValidationError("Invalid start date format. Use YYYY-MM-DD")

        if date_end and not ValidationUtils.validate_date(date_end):
            raise ValidationError("Invalid end date format. Use YYYY-MM-DD")

        if date_start and date_end and date_start >= date_end:
            raise ValidationError("End date must be after start date")

        event_id = str(uuid.uuid4())
        current_time = datetime.now().isoformat()
        user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None

        # Sanitize inputs
        name = ValidationUtils.sanitize_string(name, 255)
        description = ValidationUtils.sanitize_string(description or "", 1000)
        event_type = ValidationUtils.sanitize_string(event_type, 50)

        try:
            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO events (id, name, date, date_start, date_end, description, 
                       event_type, date_added, last_modified, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, name, date, date_start, date_end, 
                     description, event_type, current_time, current_time, user_id)
                )
                
                # Log the action
                self.audit_manager.log_change(
                    table_name='events',
                    record_id=event_id,
                    action='CREATE',
                    new_values={'name': name, 'event_type': event_type},
                    user_id=user_id
                )

            logger.info(f"Event '{name}' created with ID {event_id}")
            return {
                'success': True,
                'message': f"Event '{name}' added successfully",
                'event_id': event_id
            }
            
        except Exception as e:
            logger.error(f"Failed to add event: {e}")
            raise DatabaseError(f"Failed to add event: {e}")

    def update_event(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to update events")

        if not ValidationUtils.validate_uuid(event_id):
            raise ValidationError("Invalid event ID format")

        # Get existing event
        rows = self.db_manager.execute_query("SELECT * FROM events WHERE id = ?", (event_id,))
        if not rows:
            raise ValidationError(f"Event with ID {event_id} not found")

        existing_event = dict(rows[0])

        # Validate and sanitize updates
        allowed_fields = {'name', 'date', 'date_start', 'date_end', 'description', 'event_type'}
        invalid_fields = set(updates.keys()) - allowed_fields
        if invalid_fields:
            raise ValidationError(f"Invalid fields: {', '.join(invalid_fields)}")

        sanitized_updates = {}
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                if field in ['date', 'date_start', 'date_end']:
                    if not ValidationUtils.validate_date(str(value)):
                        raise ValidationError(f"Invalid {field} format. Use YYYY-MM-DD")
                    sanitized_updates[field] = str(value)
                elif field in ['name', 'event_type']:
                    sanitized_updates[field] = ValidationUtils.sanitize_string(str(value), 255)
                elif field == 'description':
                    sanitized_updates[field] = ValidationUtils.sanitize_string(str(value), 1000)

        if not sanitized_updates:
            return {'success': True, 'message': 'No changes to apply'}

        try:
            with self.db_manager.transaction():
                # Build update query
                set_clauses = []
                params = []
                
                for field, value in sanitized_updates.items():
                    set_clauses.append(f"{field} = ?")
                    params.append(value)

                set_clauses.append("last_modified = ?")
                params.append(datetime.now().isoformat())
                params.append(event_id)

                query = f"UPDATE events SET {', '.join(set_clauses)} WHERE id = ?"
                self.db_manager.execute_update(query, tuple(params))

                # Log the action
                user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                self.audit_manager.log_change(
                    table_name='events',
                    record_id=event_id,
                    action='UPDATE',
                    old_values={k: existing_event.get(k) for k in sanitized_updates.keys()},
                    new_values=sanitized_updates,
                    user_id=user_id
                )

            logger.info(f"Event {event_id} updated successfully")
            return {'success': True, 'message': 'Event updated successfully'}

        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            raise DatabaseError(f"Failed to update event: {e}")

    def delete_event(self, event_id: str) -> Dict[str, Any]:
        """Delete an event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to delete events")

        if not ValidationUtils.validate_uuid(event_id):
            raise ValidationError("Invalid event ID format")

        # Get existing event for audit log
        rows = self.db_manager.execute_query("SELECT * FROM events WHERE id = ?", (event_id,))
        if not rows:
            raise ValidationError(f"Event with ID {event_id} not found")

        event_data = dict(rows[0])

        try:
            with self.db_manager.transaction():
                # Delete the event (cascade will handle related records)
                rows_affected = self.db_manager.execute_update("DELETE FROM events WHERE id = ?", (event_id,))
                
                if rows_affected > 0:
                    # Log the action
                    user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                    self.audit_manager.log_change(
                        table_name='events',
                        record_id=event_id,
                        action='DELETE',
                        old_values={'name': event_data.get('name'), 'event_type': event_data.get('event_type')},
                        user_id=user_id
                    )

            logger.info(f"Event {event_id} deleted successfully")
            return {'success': True, 'message': 'Event deleted successfully'}

        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            raise DatabaseError(f"Failed to delete event: {e}")

    def get_events_by_date_range(self, start_date: str, end_date: str, 
                                event_type: Optional[str] = None) -> List[Dict]:
        """Get all events within a date range"""
        if not ValidationUtils.validate_date(start_date):
            raise ValidationError("Invalid start date format")
        
        if not ValidationUtils.validate_date(end_date):
            raise ValidationError("Invalid end date format")
        
        if start_date > end_date:
            raise ValidationError("End date must be after start date")

        try:
            query = """
                SELECT * FROM events
                WHERE ((date BETWEEN ? AND ?) 
                OR (date_start <= ? AND date_end >= ?)
                OR (date_start BETWEEN ? AND ?)
                OR (date_end BETWEEN ? AND ?))
            """
            params = [start_date, end_date, end_date, start_date, 
                     start_date, end_date, start_date, end_date]

            if event_type:
                event_type = ValidationUtils.sanitize_string(event_type, 50)
                query += " AND event_type = ?"
                params.append(event_type)

            query += " ORDER BY COALESCE(date, date_start) LIMIT ?"
            params.append(self.config.max_search_results)

            rows = self.db_manager.execute_query(query, tuple(params))
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get events by date range: {e}")
            raise DatabaseError(f"Failed to retrieve events: {e}")

    def view_calendar(self, academic_year: Optional[str] = None, semester: Optional[str] = None) -> Tuple[bool, List[Dict]]:
        """Retrieve the calendar information for an academic year and/or semester"""
        try:
            query = """
                SELECT s.name AS semester_name, s.start_date AS semester_start, s.end_date AS semester_end,
                       e.name AS event_name, e.date, e.date_start, e.date_end, e.description, e.event_type
                FROM semesters s
                LEFT JOIN events e ON (
                    (e.date BETWEEN s.start_date AND s.end_date) OR
                    (e.date_start BETWEEN s.start_date AND s.end_date) OR
                    (e.date_end BETWEEN s.start_date AND s.end_date)
                )
            """
            conditions = []
            params = []
            
            if academic_year:
                academic_year = ValidationUtils.sanitize_string(academic_year, 20)
                conditions.append("s.academic_year_id = ?")
                params.append(academic_year)
            
            if semester:
                semester = ValidationUtils.sanitize_string(semester, 50)
                conditions.append("s.name = ?")
                params.append(semester)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY s.start_date, COALESCE(e.date, e.date_start)"

            rows = self.db_manager.execute_query(query, tuple(params))
            
            if not rows:
                return False, "No calendar data found for the given selection."
            
            result = [dict(row) for row in rows]
            return True, result
            
        except Exception as e:
            logger.error(f"Failed to view calendar: {e}")
            return False, f"Database error: {str(e)}"

    # Calendar sync with security improvements
    def calendar_sync(self, ical_url: str, local_calendar: Optional[str] = None) -> Dict[str, Any]:
        """Sync external iCal feed with security improvements"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to sync calendars")

        if not ICS_AVAILABLE:
            raise CalendarError("ICS library not available. Install with: pip install ics")

        try:
            # Validate URL
            if not ValidationUtils.validate_url(ical_url):
                raise ValidationError("Invalid URL format")

            # Fetch external calendar with timeout
            response = requests.get(ical_url, timeout=30, headers={'User-Agent': 'Academic Calendar Manager'})
            response.raise_for_status()
            
            # Check response size
            if len(response.content) > self.config.max_file_size:
                raise ValidationError("Calendar file too large")
            
            # Parse calendar
            try:
                ext_cal = ICSCalendar(response.text)
            except Exception as e:
                raise ValidationError(f"Invalid iCal format: {e}")

            # Get existing events for conflict detection
            existing_events = self._get_existing_events_index()

            synced = 0
            conflicts = []
            skipped = 0
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                for event in ext_cal.events:
                    try:
                        # Skip holidays/breaks
                        event_name = str(event.name) if hasattr(event, 'name') and event.name else ""
                        if any(keyword in event_name.lower() for keyword in ['holiday', 'break']):
                            skipped += 1
                            continue

                        # Extract event details safely
                        if not hasattr(event, 'begin') or not event.begin:
                            skipped += 1
                            continue
                            
                        start_dt = event.begin.datetime if hasattr(event.begin, 'datetime') else None
                        end_dt = event.end.datetime if hasattr(event, 'end') and hasattr(event.end, 'datetime') else None
                        
                        if not start_dt:
                            skipped += 1
                            continue

                        # Convert to local timezone if needed
                        if hasattr(start_dt, 'tzinfo') and start_dt.tzinfo:
                            start_dt = start_dt.replace(tzinfo=None)
                        if end_dt and hasattr(end_dt, 'tzinfo') and end_dt.tzinfo:
                            end_dt = end_dt.replace(tzinfo=None)

                        # Check for conflicts
                        conflict_events = self._check_event_conflicts(start_dt, end_dt, existing_events)
                        if conflict_events:
                            conflicts.extend([{
                                'external': event_name,
                                'conflicts_with': conflict['name'],
                                'when': start_dt.strftime("%Y-%m-%d")
                            } for conflict in conflict_events])

                        # Generate safe event ID
                        event_uid = getattr(event, 'uid', None)
                        if event_uid:
                            event_id = ValidationUtils.sanitize_string(str(event_uid), 36)
                        else:
                            event_id = str(uuid.uuid4())

                        # Check if event already exists
                        if not self._event_exists(event_id):
                            description = ValidationUtils.sanitize_string(
                                str(event.description) if hasattr(event, 'description') and event.description else "",
                                1000
                            )
                            
                            self.db_manager.execute_update(
                                """INSERT INTO events (id, name, date_start, date_end, description, 
                                   event_type, date_added, last_modified, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (event_id, 
                                 ValidationUtils.sanitize_string(event_name, 255),
                                 start_dt.strftime("%Y-%m-%d"),
                                 end_dt.strftime("%Y-%m-%d") if end_dt else start_dt.strftime("%Y-%m-%d"),
                                 description,
                                 'Academic',
                                 current_time, current_time, user_id)
                            )
                            synced += 1

                    except Exception as e:
                        logger.warning(f"Failed to process event: {e}")
                        skipped += 1
                        continue

            # Get upcoming deadlines
            upcoming_deadlines = self._get_upcoming_deadlines()

            result = {
                'success': True,
                'synced': synced,
                'skipped_holidays': skipped,
                'conflicts': conflicts,
                'upcoming_deadlines': upcoming_deadlines
            }

            logger.info(f"Calendar sync completed: {synced} synced, {skipped} skipped")
            return result

        except requests.RequestException as e:
            logger.error(f"Failed to fetch remote calendar: {e}")
            raise CalendarError(f"Failed to fetch remote calendar: {e}")
        except Exception as e:
            logger.error(f"Calendar sync failed: {e}")
            raise CalendarError(f"Calendar sync failed: {e}")

    def _get_existing_events_index(self) -> List[Dict]:
        """Get index of existing events for conflict detection"""
        query = "SELECT id, name, date, date_start, date_end, event_type FROM events"
        rows = self.db_manager.execute_query(query)
        
        events = []
        for row in rows:
            try:
                start_str = row['date'] or row['date_start']
                end_str = row['date'] or row['date_end']
                
                if start_str:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_str, "%Y-%m-%d") if end_str else start_dt
                    
                    events.append({
                        'id': row['id'],
                        'name': row['name'],
                        'start': start_dt,
                        'end': end_dt,
                        'type': row['event_type']
                    })
            except (ValueError, TypeError):
                continue
        
        return events

    def _check_event_conflicts(self, start_dt: datetime, end_dt: datetime, 
                              existing_events: List[Dict]) -> List[Dict]:
        """Check for scheduling conflicts"""
        conflicts = []
        
        if not end_dt:
            end_dt = start_dt
        
        for event in existing_events:
            if event['type'].lower() in ('assignment', 'exam'):
                # Check for overlap
                if not (end_dt <= event['start'] or start_dt >= event['end']):
                    conflicts.append(event)
        
        return conflicts

    def _event_exists(self, event_id: str) -> bool:
        """Check if event already exists"""
        rows = self.db_manager.execute_query("SELECT 1 FROM events WHERE id = ?", (event_id,))
        return len(rows) > 0

    def _get_upcoming_deadlines(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming assignment deadlines"""
        end_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        query = """
            SELECT name, COALESCE(date, date_start) as due_date 
            FROM events 
            WHERE event_type = 'Assignment' 
            AND COALESCE(date, date_start) BETWEEN ? AND ?
            ORDER BY COALESCE(date, date_start)
        """
        
        rows = self.db_manager.execute_query(query, (current_date, end_date))
        return [{'name': row['name'], 'due': row['due_date']} for row in rows]

    # Academic year and semester management
    def add_academic_year(self, year: str, start_date: str, end_date: str) -> Tuple[bool, str]:
        """Add a new academic year to the calendar"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add academic years")

        try:
            year = ValidationUtils.sanitize_string(year, 20)
            if not isinstance(year, str) or len(year.split('-')) != 2:
                raise ValidationError("Year should be in format 'YYYY-YYYY' (e.g., '2023-2024')")
            
            if not ValidationUtils.validate_date(start_date) or not ValidationUtils.validate_date(end_date):
                raise ValidationError("Invalid date format. Use YYYY-MM-DD.")
            
            if start_date >= end_date:
                raise ValidationError("End date must be after start date")

            # Check if academic year already exists
            existing = self.db_manager.execute_query("SELECT id FROM academic_years WHERE id = ?", (year,))
            if existing:
                return False, f"Academic year {year} already exists"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO academic_years (id, start_date, end_date, date_added)
                       VALUES (?, ?, ?, ?)""",
                    (year, start_date, end_date, datetime.now().isoformat())
                )
                
                # Log the action
                user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                self.audit_manager.log_change(
                    table_name='academic_years',
                    record_id=year,
                    action='CREATE',
                    new_values={'year': year, 'start_date': start_date, 'end_date': end_date},
                    user_id=user_id
                )

            logger.info(f"Academic year {year} added successfully")
            return True, f"Academic year {year} added successfully"

        except Exception as e:
            logger.error(f"Failed to add academic year: {e}")
            raise DatabaseError(f"Database error: {str(e)}")

    def add_semester(self, academic_year: str, semester_name: str, start_date: str, end_date: str) -> Tuple[bool, str]:
        """Add a semester to an academic year"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add semesters")

        try:
            academic_year = ValidationUtils.sanitize_string(academic_year, 20)
            semester_name = ValidationUtils.sanitize_string(semester_name, 50)
            
            if not ValidationUtils.validate_date(start_date) or not ValidationUtils.validate_date(end_date):
                raise ValidationError("Invalid date format. Use YYYY-MM-DD.")
            
            if start_date >= end_date:
                raise ValidationError("End date must be after start date")

            # Check if academic year exists
            year_data = self.db_manager.execute_query(
                "SELECT id, start_date, end_date FROM academic_years WHERE id = ?", (academic_year,)
            )
            if not year_data:
                return False, f"Academic year {academic_year} not found"

            year_info = dict(year_data[0])
            if start_date < year_info['start_date'] or end_date > year_info['end_date']:
                return False, "Semester dates must fall within the academic year"

            # Check if semester already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM semesters WHERE academic_year_id = ? AND name = ?", 
                (academic_year, semester_name)
            )
            if existing:
                return False, f"Semester {semester_name} already exists for academic year {academic_year}"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO semesters (academic_year_id, name, start_date, end_date, date_added)
                       VALUES (?, ?, ?, ?, ?)""",
                    (academic_year, semester_name, start_date, end_date, datetime.now().isoformat())
                )

            logger.info(f"Semester {semester_name} added to academic year {academic_year}")
            return True, f"Semester {semester_name} added successfully to academic year {academic_year}"

        except Exception as e:
            logger.error(f"Failed to add semester: {e}")
            raise DatabaseError(f"Database error: {str(e)}")

    def get_current_academic_year(self) -> Optional[Dict]:
        """Get the current academic year"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        try:
            # First try to find current academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE start_date <= ? AND end_date >= ?", 
                (current_date, current_date)
            )
            if rows:
                return dict(rows[0])
            
            # If not found, look for upcoming academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE start_date > ? ORDER BY start_date ASC LIMIT 1", 
                (current_date,)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'upcoming'
                return result
            
            # If still not found, look for most recent past academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE end_date < ? ORDER BY end_date DESC LIMIT 1", 
                (current_date,)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'past'
                return result
            
            return None

        except Exception as e:
            logger.error(f"Failed to get current academic year: {e}")
            return None

    def get_current_semester(self) -> Optional[Dict]:
        """Get the current semester"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        try:
            current_year = self.get_current_academic_year()
            if not current_year:
                return None

            current_year_id = current_year['id']
            year_status = current_year.get('status')

            if year_status == 'upcoming':
                rows = self.db_manager.execute_query(
                    "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY start_date ASC LIMIT 1", 
                    (current_year_id,)
                )
                if rows:
                    result = dict(rows[0])
                    result['status'] = 'upcoming'
                    return result
            elif year_status == 'past':
                rows = self.db_manager.execute_query(
                    "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY end_date DESC LIMIT 1", 
                    (current_year_id,)
                )
                if rows:
                    result = dict(rows[0])
                    result['status'] = 'past'
                    return result

            # Look for current semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND start_date <= ? AND end_date >= ?", 
                (current_year_id, current_date, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'current'
                return result

            # Look for upcoming semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND start_date > ? ORDER BY start_date ASC LIMIT 1", 
                (current_year_id, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'upcoming'
                return result

            # Look for most recent past semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND end_date < ? ORDER BY end_date DESC LIMIT 1", 
                (current_year_id, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'past'
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to get current semester: {e}")
            return None

    def get_semesters_for_academic_year(self, academic_year_id: str) -> List[Dict]:
        """Get all semesters for a specific academic year"""
        try:
            academic_year_id = ValidationUtils.sanitize_string(academic_year_id, 20)
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY start_date", 
                (academic_year_id,)
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get semesters: {e}")
            return []

    # Export functionality with security improvements
    def export_calendar(self, file_path: str, format_type: str, 
                       academic_year: Optional[str] = None) -> Dict[str, Any]:
        """Export calendar with security validation"""
        if not self.auth_manager.check_permission('export_data'):
            raise PermissionError("Insufficient permissions to export data")

        # Validate file path
        safe_path = ValidationUtils.sanitize_filename(os.path.basename(file_path))
        if not safe_path:
            raise ValidationError("Invalid file name")

        # Validate format
        supported_formats = {'json', 'csv', 'xlsx', 'pdf', 'ics', 'txt'}
        format_type = format_type.lower()
        if format_type not in supported_formats:
            raise ValidationError(f"Unsupported format. Use: {', '.join(supported_formats)}")

        # Get export data
        try:
            export_data = self._get_export_data(academic_year)
            
            if not export_data:
                return {'success': False, 'message': 'No data to export'}

            # Limit export size
            if len(export_data) > self.config.max_export_records:
                raise ValidationError(f"Export too large. Maximum {self.config.max_export_records} records allowed")

            # Export based on format
            export_methods = {
                'json': self._export_json,
                'csv': self._export_csv,
                'xlsx': self._export_excel,
                'pdf': self._export_pdf,
                'ics': self._export_ical,
                'txt': self._export_txt
            }

            export_method = export_methods[format_type]
            success = export_method(export_data, safe_path)

            if success:
                logger.info(f"Calendar exported to {safe_path}")
                return {'success': True, 'message': f'Calendar exported to {safe_path}', 'file_path': safe_path}
            else:
                return {'success': False, 'message': 'Export failed'}

        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise ExportError(f"Export failed: {e}")

    def _get_export_data(self, academic_year: Optional[str] = None) -> List[Dict]:
        """Get formatted data for export"""
        try:
            query = """
                SELECT s.name AS semester_name, s.start_date AS semester_start, 
                       s.end_date AS semester_end, e.name AS event_name, 
                       COALESCE(e.date, e.date_start) as event_date,
                       e.date_end, e.event_type, e.description
                FROM semesters s
                LEFT JOIN events e ON (
                    (e.date BETWEEN s.start_date AND s.end_date) OR
                    (e.date_start BETWEEN s.start_date AND s.end_date) OR
                    (e.date_end BETWEEN s.start_date AND s.end_date)
                )
            """
            params = []

            if academic_year:
                academic_year = ValidationUtils.sanitize_string(academic_year, 20)
                query += " WHERE s.academic_year_id = ?"
                params.append(academic_year)

            query += " ORDER BY s.start_date, event_date"

            rows = self.db_manager.execute_query(query, tuple(params))
            
            export_data = []
            for row in rows:
                if row['event_name']:  # Only include rows with events
                    event_date = row['event_date']
                    if row['date_end'] and row['date_end'] != row['event_date']:
                        event_date += f" to {row['date_end']}"
                    
                    export_data.append({
                        'Academic Year': academic_year or 'All',
                        'Semester': row['semester_name'],
                        'Semester Start': row['semester_start'],
                        'Semester End': row['semester_end'],
                        'Event Name': row['event_name'],
                        'Event Date': event_date,
                        'Event Type': row['event_type'],
                        'Description': row['description'] or ''
                    })

            return export_data

        except Exception as e:
            logger.error(f"Failed to get export data: {e}")
            raise DatabaseError(f"Failed to get export data: {e}")

    def _export_json(self, data: List[Dict], file_path: str) -> bool:
        """Export to JSON format"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False

    def _export_csv(self, data: List[Dict], file_path: str) -> bool:
        """Export to CSV format"""
        try:
            if not data:
                return False
                
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            return True
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False

    def _export_excel(self, data: List[Dict], file_path: str) -> bool:
        """Export to Excel format"""
        if not PANDAS_AVAILABLE:
            logger.error("pandas not available for Excel export")
            return False
            
        try:
            df = pd.DataFrame(data)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Academic Calendar', index=False)
                
                # Auto-adjust column widths
                worksheet = writer.sheets['Academic Calendar']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                    
            return True
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            return False

    def _export_pdf(self, data: List[Dict], file_path: str) -> bool:
        """Export to PDF format"""
        if not REPORTLAB_AVAILABLE:
            logger.error("reportlab not available for PDF export")
            return False
            
        try:
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Add title
            title = Paragraph("Academic Calendar", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Add generation info
            generation_info = Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                styles['Normal']
            )
            story.append(generation_info)
            story.append(Spacer(1, 12))
            
            # Group by semester
            semesters = {}
            for item in data:
                semester = item['Semester']
                if semester not in semesters:
                    semesters[semester] = {
                        'info': {'start': item['Semester Start'], 'end': item['Semester End']},
                        'events': []
                    }
                semesters[semester]['events'].append(item)
            
            # Create tables for each semester
            for semester_name, semester_data in semesters.items():
                # Semester header
                semester_title = Paragraph(f"{semester_name} Semester", styles['Heading2'])
                story.append(semester_title)
                
                period_info = Paragraph(
                    f"Period: {semester_data['info']['start']} to {semester_data['info']['end']}", 
                    styles['Normal']
                )
                story.append(period_info)
                story.append(Spacer(1, 6))
                
                # Events table
                table_data = [['Date', 'Event', 'Type', 'Description']]
                for event in semester_data['events']:
                    description = event['Description'][:50] + ('...' if len(event['Description']) > 50 else '')
                    table_data.append([
                        event['Event Date'],
                        event['Event Name'],
                        event['Event Type'],
                        description
                    ])
                
                table = Table(table_data, colWidths=[100, 200, 80, 150])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                
                story.append(table)
                story.append(Spacer(1, 20))
            
            doc.build(story)
            return True
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return False

    def _export_txt(self, data: List[Dict], file_path: str) -> bool:
        """Export to plain text format"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("ACADEMIC CALENDAR\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n")
                
                current_semester = None
                for item in data:
                    if current_semester != item['Semester']:
                        current_semester = item['Semester']
                        f.write(f"\n{current_semester} SEMESTER\n")
                        f.write(f"Period: {item['Semester Start']} to {item['Semester End']}\n")
                        f.write("-" * 60 + "\n")
                    
                    f.write(f"{item['Event Date']:<20} {item['Event Name']:<30} ({item['Event Type']})\n")
                    if item['Description']:
                        f.write(f"{'':20} {item['Description']}\n")
                
                f.write("\n" + "=" * 80 + "\n")
            
            return True
        except Exception as e:
            logger.error(f"TXT export failed: {e}")
            return False

    def _export_ical(self, data: List[Dict], file_path: str) -> bool:
        """Export to iCal format"""
        try:
            ical_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Academic Calendar Manager//EN",
                "CALSCALE:GREGORIAN"
            ]
            
            for item in data:
                if item['Event Name']:
                    event_id = str(uuid.uuid4())
                    event_lines = [
                        "BEGIN:VEVENT",
                        f"UID:{event_id}@academic-calendar",
                        f"SUMMARY:{item['Event Name']}",
                        f"DESCRIPTION:{item['Description']}",
                        f"CATEGORIES:{item['Event Type']}"
                    ]
                    
                    # Handle date formatting
                    try:
                        if ' to ' in item['Event Date']:
                            start_date, end_date = item['Event Date'].split(' to ')
                            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        else:
                            start_dt = datetime.strptime(item['Event Date'], "%Y-%m-%d")
                            end_dt = start_dt + timedelta(days=1)
                        
                        event_lines.extend([
                            f"DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}",
                            f"DTEND;VALUE=DATE:{end_dt.strftime('%Y%m%d')}",
                            f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}"
                        ])
                    except ValueError:
                        continue
                    
                    event_lines.append("END:VEVENT")
                    ical_lines.extend(event_lines)
            
            ical_lines.append("END:VCALENDAR")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(ical_lines))
            
            return True
        except Exception as e:
            logger.error(f"iCal export failed: {e}")
            return False

    # Safe file operations
    def safe_open_file(self, file_path: str):
        """Safely open a file with security checks"""
        try:
            # Sanitize file path
            safe_path = ValidationUtils.sanitize_filename(os.path.basename(file_path))
            
            # Check file extension
            _, ext = os.path.splitext(safe_path)
            if ext.lower() not in self.config.allowed_file_types:
                raise ValidationError(f"File type {ext} not allowed")
            
            # Check if file exists
            if not os.path.exists(safe_path):
                raise ValidationError(f"File {safe_path} not found")
            
            # Open file with appropriate application
            if platform.system() == "Windows":
                os.startfile(safe_path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", safe_path])
            else:
                subprocess.call(["xdg-open", safe_path])
                
            logger.info(f"Opened file: {safe_path}")
            
        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            raise CalendarError(f"Failed to open file: {e}")

    # Backup and recovery
    def create_backup(self, backup_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a backup of the database"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to create backups")

        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(self.config.backup_directory, f"calendar_backup_{timestamp}.db")
            
            # Ensure backup directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Create backup using SQLite's backup method
            self.db_manager.backup_database(backup_path)
            
            # Verify backup
            if os.path.exists(backup_path):
                file_size = os.path.getsize(backup_path)
                
                # Record backup in history
                with self.db_manager.transaction():
                    backup_id = str(uuid.uuid4())
                    self.db_manager.execute_update(
                        """INSERT INTO backup_history (id, backup_type, file_path, file_size, 
                           backup_time, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (backup_id, "manual", backup_path, file_size,
                         datetime.now().isoformat(), "completed", "Manual backup")
                    )
                
                logger.info(f"Backup created: {backup_path} ({file_size} bytes)")
                return {
                    'success': True,
                    'message': f'Backup created successfully: {backup_path}',
                    'file_path': backup_path,
                    'file_size': file_size
                }
            else:
                return {'success': False, 'message': 'Backup creation failed'}
                
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise CalendarError(f"Backup creation failed: {e}")

    def restore_backup(self, backup_path: str) -> Dict[str, Any]:
        """Restore database from backup"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to restore backups")

        if not os.path.exists(backup_path):
            raise ValidationError(f"Backup file not found: {backup_path}")

        try:
            # Create backup of current database
            current_backup = f"{self.config.db_file}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(self.config.db_file, current_backup)
            
            # Close current connection
            self.db_manager.close()
            
            # Restore from backup
            shutil.copy2(backup_path, self.config.db_file)
            
            # Reconnect to restored database
            self.db_manager = DatabaseManager(self.config.db_file)
            
            logger.info(f"Database restored from {backup_path}")
            return {
                'success': True,
                'message': f'Database restored from {backup_path}. Previous version saved as {current_backup}'
            }
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise CalendarError(f"Restore failed: {e}")

    # Cleanup and maintenance
    def close(self):
        """Clean up resources"""
        if self.db_manager:
            self.db_manager.close()
        if self.auth_manager:
            self.auth_manager.logout()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Simplified Web API (if Flask is available)
class CalendarWebAPI:
    def __init__(self, calendar_manager: AcademicCalendarManager, host: str = 'localhost', port: int = 5000):
        if not FLASK_AVAILABLE:
            raise ImportError("Flask not available for web interface")
        
        self.calendar_manager = calendar_manager
        self.app = Flask(__name__)
        CORS(self.app)
        self.host = host
        self.port = port
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup basic API routes with authentication"""
        
        @self.app.before_request
        def require_auth():
            """Simple authentication check"""
            if request.endpoint and request.endpoint.startswith('api'):
                auth_header = request.headers.get('Authorization')
                if not auth_header or not auth_header.startswith('Bearer '):
                    return jsonify({'error': 'Authentication required'}), 401
        
        @self.app.route('/api/events', methods=['GET'])
        def get_events():
            try:
                start_date = request.args.get('start_date')
                end_date = request.args.get('end_date')
                event_type = request.args.get('event_type')
                
                if not start_date or not end_date:
                    return jsonify({'error': 'start_date and end_date required'}), 400
                
                events = self.calendar_manager.get_events_by_date_range(
                    start_date, end_date, event_type
                )
                
                return jsonify({
                    'success': True,
                    'events': events,
                    'count': len(events)
                })
                
            except ValidationError as e:
                return jsonify({'error': str(e)}), 400
            except Exception as e:
                logger.error(f"API error: {e}")
                return jsonify({'error': 'Internal server error'}), 500
        
        @self.app.route('/api/events', methods=['POST'])
        def create_event():
            try:
                data = request.json
                if not data:
                    return jsonify({'error': 'JSON data required'}), 400
                
                result = self.calendar_manager.add_event(
                    name=data.get('name'),
                    date=data.get('date'),
                    date_start=data.get('date_start'),
                    date_end=data.get('date_end'),
                    description=data.get('description'),
                    event_type=data.get('event_type', 'Academic')
                )
                
                return jsonify(result)
                
            except ValidationError as e:
                return jsonify({'error': str(e)}), 400
            except PermissionError as e:
                return jsonify({'error': str(e)}), 403
            except Exception as e:
                logger.error(f"API error: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        @self.app.route('/api/calendar/view')
        def view_calendar():
            try:
                academic_year = request.args.get('academic_year')
                semester = request.args.get('semester')
                
                success, result = self.calendar_manager.view_calendar(academic_year, semester)
                
                if success:
                    return jsonify({
                        'success': True,
                        'data': result
                    })
                else:
                    return jsonify({'error': result}), 400
                    
            except Exception as e:
                logger.error(f"API error: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        @self.app.route('/')
        def index():
            """Simple API documentation"""
            return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Academic Calendar API</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .endpoint { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                    .method { font-weight: bold; color: #007bff; }
                    .description { margin-top: 10px; color: #666; }
                </style>
            </head>
            <body>
                <h1>Academic Calendar API</h1>
                <p>RESTful API for Academic Calendar Management</p>
                
                <div class="endpoint">
                    <span class="method">GET</span> /api/events
                    <div class="description">
                        Get events with filtering. Parameters: start_date, end_date, event_type (optional)
                    </div>
                </div>
                
                <div class="endpoint">
                    <span class="method">POST</span> /api/events
                    <div class="description">
                        Create a new event. Requires JSON body with name, date/date_start/date_end, description, event_type
                    </div>
                </div>
                
                <div class="endpoint">
                    <span class="method">GET</span> /api/calendar/view
                    <div class="description">
                        Get calendar view. Parameters: academic_year (optional), semester (optional)
                    </div>
                </div>
                
                <h2>Authentication</h2>
                <p>All API endpoints require Bearer token authentication via Authorization header.</p>
            </body>
            </html>
            """)
    
    def run(self, debug: bool = False):
        """Run the web API"""
        self.app.run(host=self.host, port=self.port, debug=debug)

# Factory function for easy setup
def create_calendar_manager(db_file: str = None,
                          config_overrides: Optional[Dict] = None) -> AcademicCalendarManager:
    """Factory function to create a properly configured calendar manager"""
    
    # Create configuration
    config = CalendarConfig()
    if config_overrides:
        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    config.db_file = db_file
    
    # Create and return calendar manager
    return AcademicCalendarManager(config=config)

# Global authentication manager for integration with main system
# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_manager):
    """Set the authentication manager for the calendar system"""
    global auth
    auth = auth_manager
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_manager)

def display_academic_calendar_menu():
    """Display the academic calendar management menu with trip integration"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the academic calendar.")
        return
    
    # Check if user has any calendar-related permissions
    if not (auth.check_permission('manage_schedules') or 
            auth.check_permission('view_own_timetable') or 
            auth.check_permission('export_data')):
        print("You don't have permission to access the academic calendar.")
        return
    
    try:
        # Create calendar manager with authentication
        config = CalendarConfig()
        calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)
        
        # Set auth for trip management if available
        if TRIP_MANAGEMENT_AVAILABLE:
            trip_management.set_auth(auth)
        
        # Create a simple menu interface
        while True:
            print("\nIntegrated Academic Calendar & Trip Management")
            print("=" * 55)
            print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")
            
            options = []
            option_num = 1
            
            # Calendar options
            print(f"\n📅 CALENDAR MANAGEMENT:")
            if auth.check_permission('manage_schedules'):
                print(f"{option_num}. Add Event")
                options.append(('add_event', lambda: handle_add_event(calendar_manager)))
                option_num += 1
                
                print(f"{option_num}. Update Event")
                options.append(('update_event', lambda: handle_update_event(calendar_manager)))
                option_num += 1
                
                print(f"{option_num}. Delete Event")
                options.append(('delete_event', lambda: handle_delete_event(calendar_manager)))
                option_num += 1
            
            print(f"{option_num}. View Calendar")
            options.append(('view_calendar', lambda: handle_view_calendar(calendar_manager)))
            option_num += 1
            
            if auth.check_permission('export_data'):
                print(f"{option_num}. Export Calendar")
                options.append(('export_calendar', lambda: handle_export_calendar(calendar_manager)))
                option_num += 1
            
            # Trip management options (if available)
            if TRIP_MANAGEMENT_AVAILABLE:
                print(f"\n🎒 TRIP MANAGEMENT:")
                
                if auth.check_permission('view_trips'):
                    print(f"{option_num}. View All Trips")
                    options.append(('view_trips', trip_management.view_trips))
                    option_num += 1
                
                if auth.check_permission('create_trips'):
                    print(f"{option_num}. Create New Trip")
                    options.append(('create_trip', trip_management.create_trip))
                    option_num += 1
                
                if auth.check_permission('register_for_trips'):
                    print(f"{option_num}. Register for Trip")
                    options.append(('register_trip', trip_management.register_for_trip))
                    option_num += 1
                
                if auth.check_permission('view_own_trip_registrations'):
                    print(f"{option_num}. View My Trip Registrations")
                    options.append(('view_registrations', trip_management.view_my_trip_registrations))
                    option_num += 1
            
            # Integration options
            if TRIP_MANAGEMENT_AVAILABLE and auth.check_permission('manage_schedules'):
                print(f"\n🔗 INTEGRATION:")
                print(f"{option_num}. Create Calendar Event for Trip")
                options.append(('create_trip_event', lambda: handle_create_trip_event(calendar_manager)))
                option_num += 1
                
                print(f"{option_num}. View Trip-Calendar Links")
                options.append(('view_links', lambda: handle_view_trip_calendar_links()))
                option_num += 1
            
            print(f"\n{option_num}. Return to Main Menu")
            
            choice = input(f"\nSelect option (1-{option_num}): ").strip()
            
            try:
                choice_num = int(choice)
                
                if choice_num == option_num:  # Return to main menu
                    break
                elif 1 <= choice_num <= len(options):
                    selected_option = options[choice_num - 1]
                    action_name, action_func = selected_option
                    try:
                        action_func()
                    except Exception as e:
                        print(f"Error executing {action_name}: {e}")
                        logger.error(f"Error in {action_name}: {e}")
                else:
                    print("Invalid choice. Please try again.")
                    
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                
            if choice_num != option_num:
                input("Press Enter to continue...")
                
    except Exception as e:
        print(f"Error initializing calendar system: {e}")
        input("Press Enter to continue...")

def handle_create_trip_event(calendar_manager):
    """Handle creating a calendar event for a trip"""
    try:
        # Get available trips
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
            FROM trips t
            LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id  
            WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open')
            ORDER BY t.start_date
        ''')
        
        available_trips = cursor.fetchall()
        
        if not available_trips:
            print("No trips available for calendar event creation.")
            conn.close()
            return
        
        print("\nTrips Available for Calendar Event Creation:")
        print("-" * 70)
        for trip in available_trips:
            print(f"{trip[0]}: {trip[1]} to {trip[2]} ({trip[3]} - {trip[4]}) - {trip[5].title()}")
        
        trip_id = int(input("\nEnter Trip ID to create calendar event for: "))
        
        # Find selected trip
        selected_trip = None
        for trip in available_trips:
            if trip[0] == trip_id:
                selected_trip = trip
                break
        
        if not selected_trip:
            print("Invalid trip selection.")
            conn.close()
            return
        
        # Get event customization
        print(f"\nCreating calendar event for: {selected_trip[1]}")
        event_name = input(f"Event name (press Enter for default): ").strip()
        event_description = input("Event description (optional): ").strip()
        
        event_details = {}
        if event_name:
            event_details['name'] = event_name
        if event_description:
            event_details['description'] = event_description
        
        # Create the event
        result = calendar_manager.create_trip_event(trip_id, event_details)
        
        if result['success']:
            print(f"✓ Calendar event created successfully!")
            print(f"Event ID: {result['event_id']}")
        else:
            print(f"✗ Failed to create calendar event: {result['message']}")
        
        conn.close()
        
    except ValueError:
        print("Invalid trip ID.")
    except Exception as e:
        print(f"Error: {e}")

def handle_view_trip_calendar_links():
    """View existing trip-calendar links"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.trip_name, t.destination, t.start_date, t.end_date,
                   e.name as event_name, e.event_type, tce.created_at
            FROM trip_calendar_events tce
            JOIN trips t ON tce.trip_id = t.id
            JOIN events e ON tce.event_id = e.id
            ORDER BY t.start_date
        ''')
        
        links = cursor.fetchall()
        
        if not links:
            print("No trip-calendar links found.")
        else:
            print("\nTrip-Calendar Event Links:")
            print("=" * 80)
            print(f"{'Trip':<25} {'Destination':<15} {'Dates':<20} {'Calendar Event':<15} {'Created':<12}")
            print("-" * 80)
            
            for link in links:
                trip_name, destination, start_date, end_date, event_name, event_type, created_at = link
                dates = f"{start_date} to {end_date}"
                created = created_at[:10]  # Just the date part
                
                print(f"{trip_name[:24]:<25} {destination[:14]:<15} {dates[:19]:<20} {event_name[:14]:<15} {created:<12}")
            
            print("=" * 80)
        
        conn.close()
        
    except Exception as e:
        print(f"Error viewing links: {e}")

def handle_add_event(calendar_manager):
    """Handle adding a new event"""
    print("\nAdd New Event")
    print("-" * 30)
    
    name = input("Event Name: ").strip()
    if not name:
        print("Event name is required.")
        return
    
    print("\nEvent Type:")
    print("1. Single Date")
    print("2. Date Range")
    
    date_type = input("Select type (1-2): ").strip()
    
    date = None
    date_start = None
    date_end = None
    
    if date_type == '1':
        date = input("Event Date (YYYY-MM-DD): ").strip()
    elif date_type == '2':
        date_start = input("Start Date (YYYY-MM-DD): ").strip()
        date_end = input("End Date (YYYY-MM-DD): ").strip()
    else:
        print("Invalid selection.")
        return
    
    description = input("Description (optional): ").strip()
    
    print("\nEvent Types:")
    event_types = ["Academic", "Holiday", "Administrative", "Social", "Sports", "Deadline"]
    for i, et in enumerate(event_types, 1):
        print(f"{i}. {et}")
    
    try:
        type_choice = int(input("Select event type (1-6): "))
        if 1 <= type_choice <= len(event_types):
            event_type = event_types[type_choice - 1]
        else:
            print("Invalid event type selected.")
            return
    except ValueError:
        print("Invalid choice.")
        return
    
    try:
        result = calendar_manager.add_event(name, date, date_start, date_end, description, event_type)
        print(f"\n{result['message']}")
        if result['success']:
            print(f"Event ID: {result['event_id']}")
    except Exception as e:
        print(f"Error creating event: {e}")
    
    input("\nPress Enter to continue...")

def handle_update_event(calendar_manager):
    """Handle updating an event"""
    print("\nUpdate Event")
    print("-" * 30)
    
    event_id = input("Event ID: ").strip()
    if not event_id:
        print("Event ID is required.")
        return
    
    # Get current event details
    try:
        rows = calendar_manager.db_manager.execute_query("SELECT * FROM events WHERE id = ?", (event_id,))
        if not rows:
            print("Event not found.")
            return
        
        current_event = dict(rows[0])
        print(f"\nCurrent Event: {current_event['name']}")
        print(f"Type: {current_event['event_type']}")
        
        # Build the date string separately
        if current_event['date']:
            date_display = current_event['date']
        else:
            date_display = f"{current_event['date_start']} to {current_event['date_end']}"
        print(f"Date: {date_display}")
        print(f"Description: {current_event['description'] or 'None'}")
        
        updates = {}
        
        new_name = input(f"\nNew name (current: {current_event['name']}, press Enter to keep): ").strip()
        if new_name:
            updates['name'] = new_name
        
        new_description = input(f"New description (current: {current_event['description'] or 'None'}, press Enter to keep): ").strip()
        if new_description:
            updates['description'] = new_description
        
        if updates:
            result = calendar_manager.update_event(event_id, updates)
            print(f"\n{result['message']}")
        else:
            print("No updates provided.")
    
    except Exception as e:
        print(f"Error updating event: {e}")
    
    input("\nPress Enter to continue...")

def handle_delete_event(calendar_manager):
    """Handle deleting an event"""
    print("\nDelete Event")
    print("-" * 30)
    
    event_id = input("Event ID: ").strip()
    if not event_id:
        print("Event ID is required.")
        return
    
    try:
        # Get event details for confirmation
        rows = calendar_manager.db_manager.execute_query("SELECT name FROM events WHERE id = ?", (event_id,))
        if not rows:
            print("Event not found.")
            return
        
        event_name = rows[0]['name']
        confirm = input(f"Are you sure you want to delete '{event_name}'? (yes/no): ").lower()
        
        if confirm == 'yes':
            result = calendar_manager.delete_event(event_id)
            print(f"\n{result['message']}")
        else:
            print("Deletion cancelled.")
    
    except Exception as e:
        print(f"Error deleting event: {e}")
    
    input("\nPress Enter to continue...")

def handle_add_academic_year(calendar_manager):
    """Handle adding an academic year"""
    print("\nAdd Academic Year")
    print("-" * 30)
    
    year = input("Academic Year (e.g., 2024-2025): ").strip()
    start_date = input("Start Date (YYYY-MM-DD): ").strip()
    end_date = input("End Date (YYYY-MM-DD): ").strip()
    
    try:
        success, message = calendar_manager.add_academic_year(year, start_date, end_date)
        print(f"\n{message}")
    except Exception as e:
        print(f"Error: {e}")
    
    input("\nPress Enter to continue...")

def handle_add_semester(calendar_manager):
    """Handle adding a semester"""
    print("\nAdd Semester")
    print("-" * 30)
    
    academic_year = input("Academic Year (e.g., 2024-2025): ").strip()
    semester_name = input("Semester Name (e.g., Fall, Spring): ").strip()
    start_date = input("Start Date (YYYY-MM-DD): ").strip()
    end_date = input("End Date (YYYY-MM-DD): ").strip()
    
    try:
        success, message = calendar_manager.add_semester(academic_year, semester_name, start_date, end_date)
        print(f"\n{message}")
    except Exception as e:
        print(f"Error: {e}")
    
    input("\nPress Enter to continue...")

def handle_view_calendar(calendar_manager):
    """Handle viewing calendar"""
    print("\nView Calendar")
    print("-" * 30)
    
    academic_year = input("Academic Year (leave blank for current): ").strip()
    semester = input("Semester (leave blank for all): ").strip()
    
    academic_year = academic_year if academic_year else None
    semester = semester if semester else None
    
    try:
        success, result = calendar_manager.view_calendar(academic_year, semester)
        if success:
            display_calendar_data(result)
        else:
            print(f"Error: {result}")
    except Exception as e:
        print(f"Error viewing calendar: {e}")
    
    input("\nPress Enter to continue...")

def handle_search_events(calendar_manager):
    """Handle searching events"""
    print("\nSearch Events")
    print("-" * 30)
    
    print("1. Search by date range")
    print("2. Advanced search")
    
    try:
        search_choice = int(input("Select search type (1-2): "))
        
        if search_choice == 1:
            start_date = input("Start Date (YYYY-MM-DD): ").strip()
            end_date = input("End Date (YYYY-MM-DD): ").strip()
            event_type = input("Event Type (optional): ").strip()
            
            events = calendar_manager.get_events_by_date_range(start_date, end_date, event_type or None)
            display_events_list(events)
            
        elif search_choice == 2:
            criteria = {}
            
            text = input("Search text (optional): ").strip()
            if text:
                criteria['text'] = text
                
            start_date = input("Start date (YYYY-MM-DD, optional): ").strip()
            if start_date and ValidationUtils.validate_date(start_date):
                criteria['start_date'] = start_date
                
            end_date = input("End date (YYYY-MM-DD, optional): ").strip()
            if end_date and ValidationUtils.validate_date(end_date):
                criteria['end_date'] = end_date
                
            event_type = input("Event type (optional): ").strip()
            if event_type:
                criteria['event_type'] = event_type
                
            success, results = calendar_manager.search.advanced_search(criteria)
            if success:
                display_events_list(results)
            else:
                print(f"Search failed: {results}")
        else:
            print("Invalid choice.")
    
    except ValueError:
        print("Invalid choice.")
    except Exception as e:
        print(f"Search error: {e}")
    
    input("\nPress Enter to continue...")

def handle_export_calendar(calendar_manager):
    """Handle exporting calendar"""
    print("\nExport Calendar")
    print("-" * 30)
    
    print("Available formats:")
    formats = [
        ("JSON", "json"),
        ("CSV", "csv"),
        ("Excel", "xlsx"),
        ("PDF", "pdf"),
        ("iCal", "ics"),
        ("Text", "txt")
    ]
    
    for i, (name, ext) in enumerate(formats, 1):
        print(f"{i}. {name} (.{ext})")
    
    try:
        format_choice = int(input(f"Select format (1-{len(formats)}): "))
        
        if 1 <= format_choice <= len(formats):
            format_name, format_ext = formats[format_choice - 1]
            
            filename = input(f"Filename (without extension): ").strip()
            if not filename:
                filename = f"calendar_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            file_path = f"{filename}.{format_ext}"
            
            academic_year = input("Academic Year (leave blank for all): ").strip()
            academic_year = academic_year if academic_year else None
            
            result = calendar_manager.export_calendar(file_path, format_ext, academic_year)
            print(f"\n{result['message']}")
            
            if result['success']:
                open_file = input("Open the exported file? (y/n): ").lower().strip()
                if open_file == 'y':
                    try:
                        calendar_manager.safe_open_file(result['file_path'])
                    except Exception as e:
                        print(f"Could not open file: {e}")
        else:
            print("Invalid choice.")
    
    except ValueError:
        print("Invalid choice.")
    except Exception as e:
        print(f"Export error: {e}")
    
    input("\nPress Enter to continue...")

def handle_create_recurring_event(calendar_manager):
    """Handle create recurring event option"""
    print("\nCREATE RECURRING EVENT")
    print("-" * 30)
    
    if not DATEUTIL_AVAILABLE:
        print("dateutil library is required for recurring events.")
        return
        
    # Get base event information
    name = input("Event Name: ").strip()
    if not name:
        print("Event name is required.")
        return
        
    date = input("Start Date (YYYY-MM-DD): ").strip()
    if not ValidationUtils.validate_date(date):
        print("Invalid date format.")
        return
        
    description = input("Description: ").strip()
    event_type = input("Event Type (Academic/Holiday/Administrative): ").strip() or "Academic"
    
    # Get recurrence pattern
    print("\nRecurrence Pattern:")
    print("1. Daily")
    print("2. Weekly") 
    print("3. Monthly")
    print("4. Yearly")
    
    try:
        freq_choice = int(input("Select frequency (1-4): "))
        frequencies = {1: 'daily', 2: 'weekly', 3: 'monthly', 4: 'yearly'}
        
        if freq_choice not in frequencies:
            print("Invalid choice.")
            return
            
        frequency = frequencies[freq_choice]
        interval = int(input("Interval (every X periods): ") or "1")
        
        pattern = {
            'frequency': frequency,
            'interval': interval
        }
        
        # End condition
        print("\nEnd Condition:")
        print("1. End date")
        print("2. Number of occurrences")
        
        end_choice = int(input("Select end condition (1-2): "))
        
        if end_choice == 1:
            end_date = input("End Date (YYYY-MM-DD): ").strip()
            if ValidationUtils.validate_date(end_date):
                pattern['end_date'] = end_date
            else:
                print("Invalid end date.")
                return
        elif end_choice == 2:
            count = int(input("Number of occurrences: "))
            if count > 0:
                pattern['occurrence_count'] = min(count, 100)  # Limit for safety
            else:
                print("Invalid count.")
                return
        else:
            print("Invalid choice.")
            return
            
        base_event = {
            'name': name,
            'date': date,
            'description': description,
            'event_type': event_type
        }
        
        success, message = calendar_manager.recurring_events.create_recurring_event(base_event, pattern)
        print(message)
        
    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Error creating recurring event: {e}")
    
    input("\nPress Enter to continue...")

def handle_project_milestones(calendar_manager):
    """Handle project milestones menu"""
    print("\nPROJECT MILESTONES")
    print("-" * 30)
    print("1. Create milestone")
    print("2. Update milestone progress")
    print("3. View graduation requirements")
    print("4. Return to main menu")
    
    choice = input("Select option (1-4): ")
    
    if choice == '1':
        project_name = input("Project Name: ").strip()
        if not project_name:
            print("Project name is required.")
            return
            
        milestone_name = input("Milestone Name: ").strip()
        if not milestone_name:
            print("Milestone name is required.")
            return
            
        due_date = input("Due Date (YYYY-MM-DD): ").strip()
        if not ValidationUtils.validate_date(due_date):
            print("Invalid date format.")
            return
            
        description = input("Description: ").strip()
        
        try:
            success, message = calendar_manager.academic_deadlines.create_project_milestone(
                project_name, milestone_name, due_date, description=description
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")
    
    elif choice == '2':
        milestone_id = input("Milestone ID: ").strip()
        if not milestone_id:
            print("Milestone ID is required.")
            return
            
        try:
            progress = float(input("Completion percentage (0-100): "))
            success, message = calendar_manager.academic_deadlines.update_milestone_progress(
                milestone_id, progress
            )
            print(message)
        except (ValueError, Exception) as e:
            print(f"Error: {e}")
    
    elif choice == '3':
        student_id = input("Student ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            return
            
        try:
            result = calendar_manager.academic_deadlines.track_graduation_requirements(student_id)
            if 'error' in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Student: {result['student_id']}")
                print(f"Total Requirements: {result['total_requirements']}")
                print(f"Completed: {result['completed_requirements']}")
                print(f"Overall Progress: {result['overall_completion_percentage']}%")
                print(f"Graduation Eligible: {result['graduation_eligible']}")
        except Exception as e:
            print(f"Error: {e}")
    
    input("\nPress Enter to continue...")

def handle_event_dependencies(calendar_manager):
    """Handle event dependencies menu"""
    print("\nEVENT DEPENDENCIES")
    print("-" * 30)
    print("1. Add dependency")
    print("2. Create workflow")
    print("3. Calculate automatic deadlines")
    print("4. Return to main menu")
    
    choice = input("Select option (1-4): ")
    
    if choice == '1':
        prerequisite_id = input("Prerequisite Event ID: ").strip()
        dependent_id = input("Dependent Event ID: ").strip()
        dependency_type = input("Dependency Type (blocking/informational): ").strip() or "blocking"
        delay_days = int(input("Delay Days (default 0): ") or "0")
        
        try:
            success, message = calendar_manager.event_dependencies.add_event_dependency(
                prerequisite_id, dependent_id, dependency_type, delay_days
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")
    
    elif choice == '2':
        workflow_name = input("Workflow Name: ").strip()
        description = input("Description: ").strip()
        
        try:
            success, message = calendar_manager.event_dependencies.create_workflow(
                workflow_name, description
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")
    
    elif choice == '3':
        base_event_id = input("Base Event ID: ").strip()
        deadline_rules = [
            {'name': 'Assignment Due', 'days_before': 7, 'event_type': 'Deadline'},
            {'name': 'Study Reminder', 'days_before': 3, 'event_type': 'Reminder'}
        ]
        
        try:
            deadlines = calendar_manager.event_dependencies.calculate_automatic_deadlines(
                base_event_id, deadline_rules
            )
            print(f"Generated {len(deadlines)} automatic deadlines:")
            for deadline in deadlines:
                print(f"- {deadline['name']}: {deadline['date']}")
        except Exception as e:
            print(f"Error: {e}")
    
    input("\nPress Enter to continue...")

def handle_bulk_operations(calendar_manager):
    """Handle bulk operations menu"""
    print("\nBULK OPERATIONS")
    print("-" * 30)
    print("1. Bulk create events")
    print("2. Bulk update events") 
    print("3. Create event template")
    print("4. Return to main menu")
    
    choice = input("Select option (1-4): ")
    
    if choice == '1':
        print("\nBulk Create Events")
        print("Enter events one by one (press Enter with empty name to finish):")
        
        events_data = []
        while True:
            name = input(f"Event {len(events_data) + 1} name (or Enter to finish): ").strip()
            if not name:
                break
                
            date = input("Date (YYYY-MM-DD): ").strip()
            event_type = input("Event type (Academic/Holiday/Administrative): ").strip() or "Academic"
            description = input("Description: ").strip()
            
            events_data.append({
                'name': name,
                'date': date,
                'event_type': event_type,
                'description': description
            })
        
        if events_data:
            try:
                result = calendar_manager.batch_operations.bulk_create_events(events_data)
                print(f"Created {result['created_count']} events successfully")
                if result['failed_count'] > 0:
                    print(f"Failed to create {result['failed_count']} events")
            except Exception as e:
                print(f"Error: {e}")
    
    elif choice == '2':
        event_ids = input("Event IDs (comma-separated): ").strip().split(',')
        event_ids = [eid.strip() for eid in event_ids if eid.strip()]
        
        if not event_ids:
            print("No event IDs provided.")
            return
            
        update_data = {}
        new_type = input("New event type (optional): ").strip()
        if new_type:
            update_data['event_type'] = new_type
            
        new_description = input("New description (optional): ").strip()
        if new_description:
            update_data['description'] = new_description
            
        if update_data:
            try:
                result = calendar_manager.batch_operations.bulk_update_events(event_ids, update_data)
                print(f"Updated {result['updated_count']} events successfully")
                if result['failed_count'] > 0:
                    print(f"Failed to update {result['failed_count']} events")
            except Exception as e:
                print(f"Error: {e}")
    
    elif choice == '3':
        template_name = input("Template Name: ").strip()
        if not template_name:
            print("Template name is required.")
            return
            
        template_data = {
            'event_type': input("Default Event Type: ").strip() or "Academic",
            'description': input("Default Description: ").strip()
        }
        
        try:
            success, message = calendar_manager.batch_operations.create_event_template(
                template_name, template_data
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")
    
    input("\nPress Enter to continue...")

def handle_advanced_reports(calendar_manager):
    """Handle advanced reporting menu"""
    print("\nADVANCED REPORTS")
    print("-" * 30)
    print("1. Attendance report")
    print("2. Resource utilization report")
    print("3. Academic year summary")
    print("4. Return to main menu")
    
    choice = input("Select option (1-4): ")
    
    try:
        if choice == '1':
            course_id = input("Course ID (optional): ").strip() or None
            report = calendar_manager.advanced_reporting.generate_attendance_report(course_id)
            if report['success']:
                print(f"Total Events: {report['total_events']}")
                print(f"Average Attendance: {report['average_attendance']}")
            else:
                print(f"Error: {report['error']}")
                
        elif choice == '2':
            resource_type = input("Resource type (optional): ").strip() or None
            report = calendar_manager.advanced_reporting.generate_utilization_report(resource_type)
            if report['success']:
                print(f"Total Resources: {report['total_resources']}")
                for resource in report['resources'][:5]:  # Show first 5
                    print(f"- {resource['resource_name']}: {resource['utilization_percentage']:.1f}% utilized")
            else:
                print(f"Error: {report['error']}")
                
        elif choice == '3':
            academic_year = input("Academic Year ID: ").strip()
            if academic_year:
                report = calendar_manager.advanced_reporting.generate_academic_year_summary(academic_year)
                if report['success']:
                    print(f"Academic Year: {academic_year}")
                    print(f"Total Events: {report['total_events']}")
                    print("Event Types:")
                    for event_type, count in report['event_statistics'].items():
                        print(f"  {event_type}: {count}")
                else:
                    print(f"Error: {report['error']}")
    except Exception as e:
        print(f"Error generating report: {e}")
    
    input("\nPress Enter to continue...")

def handle_visualizations(calendar_manager):
    """Handle data visualizations menu"""
    print("\nDATA VISUALIZATIONS")
    print("-" * 30)
    print("1. Calendar heatmap")
    print("2. Event distribution chart")
    print("3. Timeline visualization")
    print("4. Conflict visualization")
    print("5. Return to main menu")
    
    choice = input("Select option (1-5): ")
    
    try:
        if choice == '1':
            year = int(input("Year: "))
            output_path = input("Output file path (optional): ").strip() or None
            success, message = calendar_manager.visualizations.create_calendar_heatmap(year, output_path)
            print(message)
            
        elif choice == '2':
            timeframe = input("Timeframe (month/semester/year): ").strip() or "month"
            output_path = input("Output file path (optional): ").strip() or None
            success, message = calendar_manager.visualizations.create_event_distribution_chart(timeframe, output_path)
            print(message)
            
        elif choice == '3':
            academic_year = input("Academic Year ID: ").strip()
            output_path = input("Output file path (optional): ").strip() or None
            success, message = calendar_manager.enhanced_visualizations.create_timeline_visualization(academic_year, output_path)
            print(message)
            
        elif choice == '4':
            start_date = input("Start Date (YYYY-MM-DD): ").strip()
            end_date = input("End Date (YYYY-MM-DD): ").strip()
            output_path = input("Output file path (optional): ").strip() or None
            success, message = calendar_manager.enhanced_visualizations.create_conflict_visualization(
                (start_date, end_date), output_path
            )
            print(message)
            
    except (ValueError, Exception) as e:
        print(f"Error: {e}")
    
    input("\nPress Enter to continue...")

def handle_system_management(calendar_manager):
    """Handle system management menu"""
    print("\nSYSTEM MANAGEMENT")
    print("-" * 30)
    print("1. Create backup")
    print("2. Import holidays")
    print("3. Calendar sync")
    print("4. User timezone settings")
    print("5. Return to main menu")
    
    choice = input("Select option (1-5): ")
    
    try:
        if choice == '1':
            backup_path = input("Backup file path (leave blank for auto): ").strip()
            backup_path = backup_path if backup_path else None
            result = calendar_manager.create_backup(backup_path)
            print(result['message'])
            
        elif choice == '2':
            if not HOLIDAYS_AVAILABLE:
                print("holidays library is required for this feature.")
                return
                
            country_code = input("Country code (e.g., US, UK, CA): ").upper().strip()
            year_str = input("Year: ").strip()
            region = input("Region/State (optional): ").strip()
            
            year = int(year_str)
            region = region if region else None
            
            success, message = calendar_manager.holidays.import_national_holidays(country_code, year, region)
            print(message)
            
        elif choice == '3':
            ical_url = input("iCal URL: ").strip()
            if ical_url:
                result = calendar_manager.calendar_sync(ical_url)
                print(f"Synced: {result['synced']} events")
                print(f"Skipped: {result['skipped_holidays']} holidays")
                if result['conflicts']:
                    print(f"Conflicts: {len(result['conflicts'])}")
            
        elif choice == '4':
            if not TIMEZONE_AVAILABLE:
                print("pytz library is required for timezone features.")
                return
                
            user_id = calendar_manager.auth_manager.current_user['id']
            timezone_name = input("Timezone (e.g., US/Eastern, Europe/London): ").strip()
            
            if timezone_name:
                success, message = calendar_manager.timezone_manager.set_user_timezone(user_id, timezone_name)
                print(message)
                
    except (ValueError, Exception) as e:
        print(f"Error: {e}")
    
    input("\nPress Enter to continue...")

def display_calendar_data(calendar_data):
    """Display calendar data in a formatted way"""
    if not calendar_data:
        print("No calendar data to display.")
        return
    
    print("\nCALENDAR DISPLAY:")
    print("=" * 80)
    
    current_semester = None
    for item in calendar_data:
        if current_semester != item['semester_name']:
            current_semester = item['semester_name']
            print(f"\n{current_semester} SEMESTER")
            print(f"Period: {item['semester_start']} to {item['semester_end']}")
            print("-" * 60)
        
        if item['event_name']:
            if item['date']:
                event_date = item['date']
            else:
                event_date = f"{item['date_start']} to {item['date_end']}"
            
            print(f"{event_date:<20} {item['event_name']:<30} ({item['event_type']})")
            if item['description']:
                print(f"{'':20} {item['description']}")
    
    print("=" * 80)

def display_events_list(events):
    """Display a list of events"""
    if not events:
        print("No events found.")
        return
    
    print(f"\nFOUND {len(events)} EVENTS:")
    print("=" * 100)
    print(f"{'ID':<8} {'Date':<20} {'Event Name':<30} {'Type':<15} {'Description':<25}")
    print("-" * 100)
    
    for event in events:
        event_id = event['id'][:8] + "..." if len(event['id']) > 8 else event['id']
        
        # Build the date string separately
        if event['date']:
            event_date = event['date']
        else:
            event_date = f"{event['date_start']} to {event['date_end']}"
        
        description = (event['description'] or '')[:25]
        if len(event['description'] or '') > 25:
            description += "..."
        
        print(f"{event_id:<8} {event_date:<20} {event['name']:<30} {event['event_type']:<15} {description:<25}")
    
    print("=" * 100)

def ensure_calendar_permissions():
    """Ensure calendar permissions exist in the main auth system"""
    from university_system.infrastructure.auth.user_authentication import UserAuth
    from university_system.infrastructure.shared_context import get_auth

    calendar_permissions = [
        ('manage_schedules', 'Manage Academic Schedules'),
        ('view_own_timetable', 'View Own Academic Timetable'),
        ('manage_academic_calendar', 'Manage Academic Calendar'),
        ('view_academic_calendar', 'View Academic Calendar'),
        ('create_academic_events', 'Create Academic Events'),
        ('update_academic_events', 'Update Academic Events'),
        ('delete_academic_events', 'Delete Academic Events'),
        ('export_calendar_data', 'Export Calendar Data')
    ]

    try:
        # Try to get centralized auth first
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
        conn = sqlite3.connect(auth.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for perm_name, perm_desc in calendar_permissions:
            # Check if permission exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            if not cursor.fetchone():
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
        
        conn.commit()
        conn.close()
        
        # Reinitialize the auth system to pick up new permissions
        auth._init_db()
        
    except Exception as e:
        logger.warning(f"Could not ensure calendar permissions: {e}")

def _verify_required_tables(self):
    """Verify that required tables exist, create missing ones"""
    try:
        required_tables = [
            'academic_years',
            'semesters', 
            'events',
            'event_categories'
        ]
        
        for table in required_tables:
            try:
                # Test if table exists by querying it
                self.db_manager.execute_query(f"SELECT COUNT(*) FROM {table} LIMIT 1")
                logging.debug(f"Table {table} exists")
            except Exception:
                # Table doesn't exist, create it
                logging.info(f"Creating missing table: {table}")
                
                if table == 'academic_years':
                    self.db_manager.execute_update('''
                        CREATE TABLE IF NOT EXISTS academic_years (
                            id TEXT PRIMARY KEY,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            date_added TEXT NOT NULL,
                            CONSTRAINT valid_dates CHECK (start_date < end_date)
                        )
                    ''')
                    
                elif table == 'semesters':
                    self.db_manager.execute_update('''
                        CREATE TABLE IF NOT EXISTS semesters (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            academic_year_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            registration_start TEXT,
                            registration_end TEXT,
                            final_exams_start TEXT,
                            final_exams_end TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (academic_year_id) REFERENCES academic_years (id) ON DELETE CASCADE,
                            UNIQUE(academic_year_id, name),
                            CONSTRAINT valid_semester_dates CHECK (start_date < end_date)
                        )
                    ''')
                    
                elif table == 'events':
                    self.db_manager.execute_update('''
                        CREATE TABLE IF NOT EXISTS events (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            date TEXT,
                            date_start TEXT,
                            date_end TEXT,
                            description TEXT,
                            event_type TEXT DEFAULT 'Academic',
                            date_added TEXT NOT NULL,
                            last_modified TEXT,
                            created_by TEXT,
                            CONSTRAINT valid_event_dates CHECK (
                                (date IS NOT NULL AND date_start IS NULL AND date_end IS NULL) OR
                                (date IS NULL AND date_start IS NOT NULL AND date_end IS NOT NULL AND date_start <= date_end)
                            )
                        )
                    ''')
                    
                elif table == 'event_categories':
                    self.db_manager.execute_update('''
                        CREATE TABLE IF NOT EXISTS event_categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE NOT NULL,
                            color_code TEXT,
                            description TEXT,
                            date_added TEXT NOT NULL
                        )
                    ''')
                
                logging.info(f"Successfully created table: {table}")
        
        logger.info("Required tables verified/created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Table verification failed: {e}")
        raise DatabaseError(f"Table verification failed: {e}")

def fix_calendar_database():
    """Quick fix for calendar database issues"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if there's a conflicting role_permissions table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role_permissions'")
        if cursor.fetchone():
            # Check the schema
            cursor.execute("PRAGMA table_info(role_permissions)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'role' in columns and 'permission' in columns:
                # This is the problematic table from academic calendar
                print("Found conflicting role_permissions table. Renaming it...")
                cursor.execute("ALTER TABLE role_permissions RENAME TO old_role_permissions")
                print("Conflicting table renamed to old_role_permissions")
        
        conn.commit()
        conn.close()
        print("Database fix completed successfully!")
        
    except Exception as e:
        print(f"Database fix failed: {e}")

# Run this once
fix_calendar_database()
