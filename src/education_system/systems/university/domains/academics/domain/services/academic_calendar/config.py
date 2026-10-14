import os
import re
import uuid
import hashlib
import secrets
from datetime import datetime
from typing import Tuple
from dataclasses import dataclass
from education_system import paths


# Configuration
@dataclass
class CalendarConfig:
    db_file: str = os.fspath(paths.UNIVERSITY_DEFAULT_DB_PATH)
    default_timezone: str = 'UTC'
    max_export_records: int = 10000
    backup_directory: str = os.fspath(paths.UNIVERSITY_BACKUP_CALENDAR_DIR)
    export_directory: str = os.fspath(paths.UNIVERSITY_EXPORTS_DIR)
    # .json is an export format and .png/.html are produced by the chart
    # renderers; without them safe_open_file() refuses to open its own output.
    allowed_file_types: frozenset = frozenset(
        ['.pdf', '.txt', '.csv', '.xlsx', '.ics', '.json', '.png', '.html']
    )
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
    def resolve_safe_path(file_path: str, base_dir: str, create: bool = True,
                          allow_absolute: bool = False) -> str:
        """Resolve *file_path* to an absolute path confined to *base_dir*.

        sanitize_filename() removes every directory component. That blocks
        traversal, but it also throws away the directory the caller asked for,
        so the file silently lands in whatever the process's working directory
        happens to be — and a later "open the file you just wrote" only works
        by accident, from the same directory.

        This keeps the caller's directory when it sits inside *base_dir*, and
        otherwise puts the sanitized filename in *base_dir* itself. Returns ""
        if the filename is unusable, so callers can raise their own error.

        *create* makes the target directory; pass create=False when only
        testing a path (opening an existing file, say) so the check does not
        leave empty directories behind.

        *allow_absolute* honours a fully-qualified path the caller supplied on
        purpose — the desktop export dialog asks the operator where to save,
        and redirecting that into the app's own directory would be its own
        surprise. Relative paths are still confined to *base_dir*, so a
        traversal string can never climb out.
        """
        from pathlib import Path

        if not file_path or not str(file_path).strip():
            return ""

        base = Path(base_dir).expanduser().resolve()

        candidate = Path(file_path).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        candidate = Path(os.path.normpath(candidate))  # collapses any ".."

        name = ValidationUtils.sanitize_filename(candidate.name)
        if not name:
            return ""

        was_absolute = Path(file_path).expanduser().is_absolute()

        target_dir = candidate.parent
        try:
            target_dir.relative_to(base)  # inside the allowed root?
        except ValueError:
            if not (allow_absolute and was_absolute):
                target_dir = base  # outside it — fall back rather than escape

        if create:
            target_dir.mkdir(parents=True, exist_ok=True)
        return str(target_dir / name)

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
