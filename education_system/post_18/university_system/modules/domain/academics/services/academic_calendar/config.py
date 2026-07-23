import os
import re
import uuid
import hashlib
import secrets
from datetime import datetime
from typing import Tuple
from dataclasses import dataclass
from education_system.post_18.university_system.core import paths


# Configuration
@dataclass
class CalendarConfig:
    db_file: str = os.fspath(paths.DEFAULT_DB_PATH)
    default_timezone: str = 'UTC'
    max_export_records: int = 10000
    backup_directory: str = os.fspath(paths.BACKUP_CALENDAR_DIR)
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
        """Validate datetime format YYYY-MM-DD HH:MM:SS or ISO 8601"""
        if not isinstance(datetime_string, str):
            return False
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                datetime.strptime(datetime_string, fmt)
                return True
            except ValueError:
                continue
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
