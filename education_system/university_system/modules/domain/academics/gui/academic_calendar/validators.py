import os
import re
import uuid
from datetime import datetime
from urllib.parse import urlparse
from typing import Tuple, Optional, List

def validate_date(date_string: str, format: str = "%Y-%m-%d") -> Tuple[bool, Optional[datetime]]:
    """
    Validate date string and convert to datetime.
    Delegates to centralized validator.

    Args:
        date_string: Date string to validate
        format: Expected date format (default: YYYY-MM-DD)

    Returns:
        Tuple[bool, Optional[datetime]]: (is_valid, datetime_object or None)
    """
    from education_system.university_system.modules.shared.utils.input_validation import parse_date_safe
    return parse_date_safe(date_string, format)


def validate_datetime(datetime_string: str, format: str = "%Y-%m-%d %H:%M:%S") -> Tuple[bool, Optional[datetime]]:
    """
    Validate datetime string and convert to datetime object.
    Delegates to centralized validator.

    Args:
        datetime_string: Datetime string to validate
        format: Expected datetime format (default: YYYY-MM-DD HH:MM:SS)

    Returns:
        Tuple[bool, Optional[datetime]]: (is_valid, datetime_object or None)
    """
    from education_system.university_system.modules.shared.utils.input_validation import parse_datetime_safe
    return parse_datetime_safe(datetime_string, format)


def validate_email(email: str) -> bool:
    """
    Validate email address format.
    Delegates to centralized validator.

    Args:
        email: Email address to validate

    Returns:
        bool: True if valid email format, False otherwise
    """
    from education_system.university_system.modules.shared.utils.input_validation import is_valid_email
    return is_valid_email(email)


def validate_uuid(uuid_string: str) -> bool:
    """
    Validate UUID string format

    Supports UUID versions 1, 3, 4, and 5.

    Args:
        uuid_string: UUID string to validate

    Returns:
        bool: True if valid UUID format, False otherwise

    Example:
        if validate_uuid("550e8400-e29b-41d4-a716-446655440000"):
            print("Valid UUID")
    """
    if not uuid_string or not isinstance(uuid_string, str):
        return False

    try:
        uuid_obj = uuid.UUID(uuid_string.strip())
        return str(uuid_obj) == uuid_string.strip().lower()
    except (ValueError, AttributeError):
        return False


def sanitize_string(input_string: str, max_length: int = 1000,
                   allow_special_chars: bool = True) -> str:
    """
    Sanitize input string to prevent SQL injection and XSS

    Removes potentially dangerous characters and limits length.

    Args:
        input_string: String to sanitize
        max_length: Maximum allowed length
        allow_special_chars: Whether to allow special characters

    Returns:
        str: Sanitized string

    Example:
        safe_input = sanitize_string(user_input, max_length=100)
    """
    if not input_string or not isinstance(input_string, str):
        return ""

    # Limit length
    sanitized = input_string[:max_length]

    # Remove null bytes (common SQL injection technique)
    sanitized = sanitized.replace('\x00', '')

    if not allow_special_chars:
        # Keep only alphanumeric, spaces, and basic punctuation
        sanitized = re.sub(r'[^a-zA-Z0-9\s\.,!?\-_@]', '', sanitized)
    else:
        # Remove potentially dangerous characters for SQL/XSS
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',                 # JavaScript protocol
            r'on\w+\s*=',                  # Event handlers
            r'--',                         # SQL comments
            r'/\*.*?\*/',                  # SQL block comments
        ]
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)

    return sanitized.strip()


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to prevent path traversal attacks

    Removes path separators and limits to valid filename characters.

    Args:
        filename: Filename to sanitize
        max_length: Maximum filename length (default: 255)

    Returns:
        str: Sanitized filename

    Example:
        safe_filename = sanitize_filename("../../etc/passwd")
        # Returns: "etc_passwd"
    """
    if not filename or not isinstance(filename, str):
        return "unnamed_file"

    # Remove path separators and parent directory references
    sanitized = filename.replace('/', '_').replace('\\', '_')
    sanitized = sanitized.replace('..', '')
    sanitized = sanitized.replace('~', '')

    # Keep only safe filename characters
    # Allow: alphanumeric, spaces, dots, dashes, underscores
    sanitized = re.sub(r'[^a-zA-Z0-9\s\.\-_]', '', sanitized)

    # Remove leading/trailing dots and spaces (problematic on Windows)
    sanitized = sanitized.strip('. ')

    # Ensure not empty after sanitization
    if not sanitized:
        sanitized = "unnamed_file"

    # Limit length
    if len(sanitized) > max_length:
        # Preserve extension if present
        name_parts = sanitized.rsplit('.', 1)
        if len(name_parts) == 2:
            name, ext = name_parts
            max_name_length = max_length - len(ext) - 1
            sanitized = f"{name[:max_name_length]}.{ext}"
        else:
            sanitized = sanitized[:max_length]

    return sanitized


def validate_file_path(file_path: str, allowed_directories: Optional[List[str]] = None,
                      allowed_extensions: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate file path for security

    Checks for path traversal, validates against allowed directories,
    and checks file extensions.

    Args:
        file_path: File path to validate
        allowed_directories: List of allowed directory paths (optional)
        allowed_extensions: List of allowed file extensions (optional)

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message or None)

    Example:
        is_valid, error = validate_file_path(
            user_path,
            allowed_directories=['/home/user/uploads'],
            allowed_extensions=['.txt', '.pdf']
        )
        if not is_valid:
            print(f"Invalid path: {error}")
    """
    if not file_path or not isinstance(file_path, str):
        return False, "File path is empty or invalid"

    # Check for path traversal attempts
    normalized_path = os.path.normpath(file_path)
    if '..' in normalized_path or normalized_path.startswith('/..'):
        return False, "Path traversal detected"

    # Convert to absolute path
    try:
        abs_path = os.path.abspath(normalized_path)
    except (ValueError, OSError):
        return False, "Invalid file path"

    # Check against allowed directories
    if allowed_directories:
        allowed = False
        for allowed_dir in allowed_directories:
            allowed_abs = os.path.abspath(allowed_dir)
            if abs_path.startswith(allowed_abs):
                allowed = True
                break

        if not allowed:
            return False, f"File path not in allowed directories"

    # Check file extension
    if allowed_extensions:
        _, ext = os.path.splitext(abs_path)
        if ext.lower() not in [e.lower() for e in allowed_extensions]:
            return False, f"File extension '{ext}' not allowed. Allowed: {', '.join(allowed_extensions)}"

    return True, None


def validate_url(url: str, allowed_schemes: Optional[List[str]] = None,
                require_tld: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate URL format and security

    Checks URL structure, scheme, and optionally validates TLD.

    Args:
        url: URL to validate
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])
        require_tld: Whether to require a valid TLD (default: True)

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message or None)

    Example:
        is_valid, error = validate_url("https://example.com/path")
        if is_valid:
            print("Valid URL")
    """
    if not url or not isinstance(url, str):
        return False, "URL is empty or invalid"

    # Default allowed schemes
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Check scheme
    if not parsed.scheme:
        return False, "URL must include a scheme (e.g., https://)"

    if parsed.scheme.lower() not in [s.lower() for s in allowed_schemes]:
        return False, f"URL scheme '{parsed.scheme}' not allowed. Allowed: {', '.join(allowed_schemes)}"

    # Check netloc (domain)
    if not parsed.netloc:
        return False, "URL must include a domain"

    # Check for valid TLD
    if require_tld:
        domain_parts = parsed.netloc.split('.')
        if len(domain_parts) < 2:
            return False, "URL must include a valid top-level domain"

        tld = domain_parts[-1]
        if not tld or len(tld) < 2:
            return False, "Invalid top-level domain"

    # Check for suspicious patterns
    suspicious_patterns = [
        r'@',  # Credentials in URL
        r'javascript:',  # JavaScript protocol
        r'data:',  # Data protocol (can be used for XSS)
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False, f"URL contains suspicious pattern: {pattern}"

    return True, None


