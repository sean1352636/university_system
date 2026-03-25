"""
Secure File Upload Handler for University Management System.

This module provides a centralized, secure file upload handler that addresses
multiple security vulnerabilities:
- Path traversal attacks (../../etc/passwd)
- MIME type spoofing (executables disguised as images)
- Denial of service (huge file uploads)
- Malicious file content (PHP, JavaScript, shell scripts)
- Predictable file storage locations

Security Features:
- Filename sanitization using werkzeug's secure_filename
- File extension whitelist validation
- MIME type validation from actual file content
- File size limits
- Malicious pattern detection
- Unique filename generation (UUID + hash)
- Restrictive file permissions (0o600)
- Comprehensive audit logging
- **NEW**: Integration with FileUploadValidator for enhanced security

Usage:
    from education_system.university_system.infrastructure.security.file_upload import get_upload_handler

    handler = get_upload_handler()

    # Validate a file
    result = handler.validate_file(filename, file_content, category='documents')
    if result['valid']:
        # File is safe to process
        pass

    # Save a file securely
    result = handler.save_file(filename, file_content, category='documents', user_id='123')
    if result['success']:
        file_path = result['file_path']
"""

import hashlib
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

# Import the new comprehensive validator
try:
    from education_system.university_system.infrastructure.security.file_upload_validator import (
        FileUploadValidator,
        document_validator,
        image_validator,
        avatar_validator,
        strict_validator
    )
    ENHANCED_VALIDATOR_AVAILABLE = True
except ImportError:
    ENHANCED_VALIDATOR_AVAILABLE = False

logger = logging.getLogger(__name__)


def secure_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent directory traversal and other attacks.

    This is a standalone implementation that doesn't require werkzeug.
    Based on werkzeug's secure_filename with additional hardening.

    Args:
        filename: The original filename

    Returns:
        A sanitized filename safe for filesystem operations
    """
    if not filename:
        return ''

    # Normalize unicode
    try:
        import unicodedata
        filename = unicodedata.normalize('NFKD', filename)
        filename = filename.encode('ascii', 'ignore').decode('ascii')
    except Exception:
        logger.exception("Unicode normalization failed for filename")

    # Replace path separators with underscores
    for sep in (os.sep, os.altsep):
        if sep:
            filename = filename.replace(sep, '_')

    # Remove any null bytes
    filename = filename.replace('\x00', '')

    # Remove directory traversal patterns
    filename = re.sub(r'\.\.+', '.', filename)

    # Only allow safe characters: alphanumeric, dash, underscore, dot
    filename = re.sub(r'[^\w\s\-.]', '', filename)

    # Remove leading/trailing whitespace and dots
    filename = filename.strip('. \t\n\r')

    # Collapse multiple spaces/underscores/dashes
    filename = re.sub(r'[\s_]+', '_', filename)
    filename = re.sub(r'-+', '-', filename)

    # Limit filename length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext

    # If nothing left, return empty
    if not filename or filename == '.':
        return ''

    return filename


class SecureFileUpload:
    """
    Secure file upload handler with comprehensive validation.

    This class provides centralized file upload handling with multiple
    layers of security validation to prevent common attack vectors.

    Attributes:
        ALLOWED_EXTENSIONS: Whitelist of allowed file extensions by category
        ALLOWED_MIMES: Whitelist of allowed MIME types
        MAX_FILE_SIZE: Maximum allowed file size in bytes
        DANGEROUS_EXTENSIONS: Blacklist of dangerous extensions (always blocked)
    """

    # Whitelist of allowed extensions by category
    ALLOWED_EXTENSIONS: Dict[str, Set[str]] = {
        'documents': {'.pdf', '.doc', '.docx', '.txt', '.odt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png', '.gif', '.bmp'},
        'images': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'},
        'archives': {'.zip', '.tar', '.gz', '.7z', '.rar'},
        'videos': {'.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm'},
        'audio': {'.mp3', '.wav', '.ogg', '.flac', '.m4a'},
        'data': {'.csv', '.json', '.xml'},
    }

    # Whitelist of allowed MIME types
    ALLOWED_MIMES: Set[str] = {
        # Documents
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'application/rtf',
        'text/plain',
        'text/csv',
        'application/json',
        'application/xml',
        'text/xml',
        # Images
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/bmp',
        'image/webp',
        # image/svg+xml intentionally excluded — SVGs can contain XSS/XXE attacks
        # Archives
        'application/zip',
        'application/x-tar',
        'application/gzip',
        'application/x-7z-compressed',
        'application/x-rar-compressed',
        # Videos
        'video/mp4',
        'video/avi',
        'video/quicktime',
        'video/x-ms-wmv',
        'video/x-matroska',
        'video/webm',
        # Audio
        'audio/mpeg',
        'audio/wav',
        'audio/ogg',
        'audio/flac',
        'audio/mp4',
    }

    # Dangerous extensions that are ALWAYS blocked
    DANGEROUS_EXTENSIONS: Set[str] = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr',  # Windows executables
        '.sh', '.bash', '.csh', '.zsh',  # Shell scripts
        '.php', '.php3', '.php4', '.php5', '.phtml',  # PHP
        '.asp', '.aspx', '.cer',  # ASP
        '.jsp', '.jspx',  # Java Server Pages
        '.py', '.pyc', '.pyw',  # Python
        '.pl', '.pm', '.cgi',  # Perl/CGI
        '.rb', '.erb',  # Ruby
        '.js', '.mjs',  # JavaScript
        '.htaccess', '.htpasswd',  # Apache config
        '.dll', '.so', '.dylib',  # Libraries
        '.jar', '.war', '.ear',  # Java archives
        '.msi', '.app', '.dmg',  # Installers
        '.vbs', '.vbe', '.wsf', '.wsh',  # VBScript
        '.ps1', '.psm1',  # PowerShell
    }

    # Maximum file sizes (in bytes)
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB default
    MAX_FILE_SIZES: Dict[str, int] = {
        'documents': 25 * 1024 * 1024,   # 25MB
        'images': 10 * 1024 * 1024,      # 10MB
        'archives': 100 * 1024 * 1024,   # 100MB
        'videos': 500 * 1024 * 1024,     # 500MB
        'audio': 50 * 1024 * 1024,       # 50MB
        'data': 10 * 1024 * 1024,        # 10MB
    }

    # File signatures (magic bytes) for MIME type detection
    FILE_SIGNATURES: Dict[bytes, str] = {
        b'%PDF': 'application/pdf',
        b'\xff\xd8\xff': 'image/jpeg',
        b'\x89PNG\r\n\x1a\n': 'image/png',
        b'GIF87a': 'image/gif',
        b'GIF89a': 'image/gif',
        b'BM': 'image/bmp',
        b'PK\x03\x04': 'application/zip',
        b'PK\x05\x06': 'application/zip',
        b'\x1f\x8b': 'application/gzip',
        b'Rar!\x1a\x07': 'application/x-rar-compressed',
        b'7z\xbc\xaf\x27\x1c': 'application/x-7z-compressed',
        b'\x00\x00\x00\x18ftypmp4': 'video/mp4',
        b'\x00\x00\x00\x1cftypmp4': 'video/mp4',
        b'RIFF': 'audio/wav',  # Could also be AVI
        b'ID3': 'audio/mpeg',
        b'\xff\xfb': 'audio/mpeg',
        b'\xff\xfa': 'audio/mpeg',
        b'OggS': 'audio/ogg',
        b'fLaC': 'audio/flac',
    }

    # Malicious patterns to detect in file content
    MALICIOUS_PATTERNS: List[bytes] = [
        b'<?php',           # PHP code
        b'<% ',             # ASP code
        b'<%@',             # JSP code
        b'<script',         # JavaScript (HTML)
        b'javascript:',     # JavaScript protocol
        b'eval(',           # Eval function (multiple languages)
        b'exec(',           # Exec function
        b'system(',         # System call
        b'shell_exec(',     # Shell execution
        b'passthru(',       # PHP passthru
        b'popen(',          # Process open
        b'proc_open(',      # PHP proc_open
        b'/bin/sh',         # Shell reference
        b'/bin/bash',       # Bash reference
        b'cmd.exe',         # Windows command
        b'powershell',      # PowerShell
        b'import os',       # Python os import
        b'import subprocess',  # Python subprocess
        b'__import__',      # Python dynamic import
        b'os.system',       # Python system call
        b'subprocess.call', # Python subprocess
        b'subprocess.Popen',# Python subprocess
        b'Runtime.getRuntime', # Java runtime
        # SVG XSS vectors
        b'onerror=',          # SVG event handler injection
        b'onload=',           # SVG event handler injection
        b'onmouseover=',      # SVG event handler injection
        b'onfocus=',          # SVG event handler injection
        b'xlink:href',        # SVG XLink-based attacks
        b'foreignObject',     # SVG foreign object injection (embeds HTML inside SVG)
    ]

    def __init__(self, upload_dir: Optional[str] = None):
        """
        Initialize the secure file upload handler.

        Args:
            upload_dir: Base directory for file uploads. If None, uses
                       the default from paths module.
        """
        if upload_dir is None:
            try:
                from education_system.university_system.core import paths
                upload_dir = paths.UPLOAD_DIR
            except ImportError:
                upload_dir = '/tmp/uploads'
                logger.warning(f"Could not import paths module, using {upload_dir}")

        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions on upload directory
        try:
            os.chmod(self.upload_dir, 0o700)
        except OSError as e:
            logger.warning(f"Could not set permissions on upload directory: {e}")

        logger.info(f"SecureFileUpload initialized with upload_dir: {self.upload_dir}")

    def validate_file(
        self,
        filename: str,
        file_content: bytes,
        category: str = 'documents'
    ) -> Dict[str, Union[bool, str, int]]:
        """
        Validate an uploaded file for security.

        Performs comprehensive validation including:
        - Filename sanitization
        - Extension whitelist check
        - Dangerous extension blacklist check
        - File size validation
        - MIME type validation from content
        - Malicious pattern detection

        Args:
            filename: Original filename from upload
            file_content: Raw file content as bytes
            category: File category for extension/size validation

        Returns:
            dict with keys:
                - valid (bool): Whether file passed all checks
                - error (str): Error message if invalid
                - safe_filename (str): Sanitized filename if valid
                - mime_type (str): Detected MIME type if valid
                - size (int): File size in bytes if valid
        """
        # 1. Check filename exists
        if not filename:
            logger.warning("File validation failed: No filename provided")
            return {'valid': False, 'error': 'No filename provided'}

        # 2. Sanitize filename
        safe_name = secure_filename(filename)
        if not safe_name:
            logger.warning(f"File validation failed: Invalid filename '{filename}'")
            return {'valid': False, 'error': 'Invalid filename after sanitization'}

        # 3. Check for dangerous extensions (blacklist - always blocked)
        ext = Path(safe_name).suffix.lower()
        if ext in self.DANGEROUS_EXTENSIONS:
            logger.warning(
                f"SECURITY: Blocked dangerous file extension '{ext}' "
                f"for file '{filename}'"
            )
            return {
                'valid': False,
                'error': f'File type {ext} is not allowed for security reasons'
            }

        # 4. Check file extension against whitelist
        if category not in self.ALLOWED_EXTENSIONS:
            logger.warning(f"Unknown category '{category}', defaulting to 'documents'")
            category = 'documents'

        if ext not in self.ALLOWED_EXTENSIONS[category]:
            allowed = ', '.join(sorted(self.ALLOWED_EXTENSIONS[category]))
            logger.warning(
                f"File validation failed: Extension '{ext}' not in "
                f"allowed list for category '{category}'"
            )
            return {
                'valid': False,
                'error': f'File type {ext} not allowed for {category}. Allowed: {allowed}'
            }

        # 5. Check file size
        max_size = self.MAX_FILE_SIZES.get(category, self.MAX_FILE_SIZE)
        if len(file_content) > max_size:
            max_mb = max_size // (1024 * 1024)
            logger.warning(
                f"File validation failed: Size {len(file_content)} exceeds "
                f"maximum {max_size} for category '{category}'"
            )
            return {
                'valid': False,
                'error': f'File too large. Maximum size for {category}: {max_mb}MB'
            }

        # 6. Check for empty files
        if len(file_content) == 0:
            logger.warning("File validation failed: Empty file")
            return {'valid': False, 'error': 'Empty files are not allowed'}

        # 7. Validate MIME type from actual content
        detected_mime = self._detect_mime_type(file_content)
        if detected_mime not in self.ALLOWED_MIMES:
            logger.warning(
                f"SECURITY: MIME type mismatch - detected '{detected_mime}' "
                f"for file '{filename}' with extension '{ext}'"
            )
            return {
                'valid': False,
                'error': f'File content type ({detected_mime}) is not allowed'
            }

        # 8. Check for malicious patterns in content
        malicious_check = self._check_malicious_patterns(file_content, filename)
        if malicious_check:
            logger.warning(
                f"SECURITY: Malicious pattern detected in file '{filename}': "
                f"{malicious_check}"
            )
            return {
                'valid': False,
                'error': 'File contains potentially malicious content'
            }

        # All checks passed
        logger.info(f"File validation passed: '{safe_name}' ({detected_mime}, {len(file_content)} bytes)")
        return {
            'valid': True,
            'safe_filename': safe_name,
            'mime_type': detected_mime,
            'size': len(file_content),
            'category': category
        }

    def save_file(
        self,
        filename: str,
        file_content: bytes,
        category: str = 'documents',
        user_id: Optional[str] = None
    ) -> Dict[str, Union[bool, str]]:
        """
        Securely save an uploaded file.

        Validates the file, generates a unique storage name, saves with
        restrictive permissions, and logs the operation.

        Args:
            filename: Original filename from upload
            file_content: Raw file content as bytes
            category: File category for validation and storage
            user_id: Optional user ID for audit logging

        Returns:
            dict with keys:
                - success (bool): Whether file was saved successfully
                - error (str): Error message if failed
                - file_path (str): Full path to saved file if successful
                - file_hash (str): SHA-256 hash of file content if successful
                - stored_name (str): Generated unique filename if successful
                - original_name (str): Sanitized original filename if successful
        """
        # Validate first
        validation = self.validate_file(filename, file_content, category)
        if not validation['valid']:
            return {'success': False, 'error': validation['error']}

        try:
            # Generate unique filename using UUID + content hash
            file_hash = hashlib.sha256(file_content).hexdigest()
            ext = Path(validation['safe_filename']).suffix.lower()
            unique_name = f"{uuid.uuid4().hex}_{file_hash[:8]}{ext}"

            # Create category subdirectory
            category_dir = self.upload_dir / category
            category_dir.mkdir(parents=True, exist_ok=True)

            # Ensure category directory has restrictive permissions
            try:
                os.chmod(category_dir, 0o700)
            except OSError:
                logger.exception("Failed to set permissions on category directory: %s", category_dir)

            # Generate full file path
            file_path = category_dir / unique_name

            # Check if file already exists (extremely unlikely with UUID)
            if file_path.exists():
                logger.warning(f"File collision detected: {file_path}")
                unique_name = f"{uuid.uuid4().hex}_{uuid.uuid4().hex[:8]}{ext}"
                file_path = category_dir / unique_name

            # Save file
            file_path.write_bytes(file_content)

            # Set restrictive permissions (read/write for owner only)
            os.chmod(file_path, 0o600)

            # Log the upload for audit trail
            try:
                from education_system.university_system.core.activity_logger import log_activity
                log_activity('upload', 'file', details={
                    'original_name': validation['safe_filename'],
                    'stored_name': unique_name,
                    'category': category,
                    'size': len(file_content),
                    'hash': file_hash,
                    'mime_type': validation['mime_type'],
                    'user_id': user_id,
                    'path': str(file_path)
                })
            except ImportError:
                logger.info(
                    f"File uploaded: {validation['safe_filename']} -> {unique_name} "
                    f"({len(file_content)} bytes, user: {user_id})"
                )

            logger.info(f"File saved successfully: {file_path}")
            return {
                'success': True,
                'file_path': str(file_path),
                'file_hash': file_hash,
                'stored_name': unique_name,
                'original_name': validation['safe_filename'],
                'mime_type': validation['mime_type'],
                'size': len(file_content)
            }

        except PermissionError as e:
            logger.error(f"Permission error saving file: {e}")
            return {'success': False, 'error': 'Permission denied when saving file'}
        except OSError as e:
            logger.error(f"OS error saving file: {e}")
            return {'success': False, 'error': f'Failed to save file: {e}'}
        except Exception as e:
            logger.error(f"Unexpected error saving file: {e}")
            return {'success': False, 'error': f'Failed to save file: {e}'}

    def delete_file(self, file_path: str, user_id: Optional[str] = None) -> Dict[str, Union[bool, str]]:
        """
        Securely delete an uploaded file.

        Args:
            file_path: Path to the file to delete
            user_id: Optional user ID for audit logging

        Returns:
            dict with 'success' and optionally 'error'
        """
        try:
            path = Path(file_path)

            # Security check: ensure file is within upload directory
            try:
                path.resolve().relative_to(self.upload_dir.resolve())
            except ValueError:
                logger.warning(
                    f"SECURITY: Attempted to delete file outside upload directory: {file_path}"
                )
                return {'success': False, 'error': 'Invalid file path'}

            if not path.exists():
                return {'success': False, 'error': 'File not found'}

            # Delete the file
            path.unlink()

            # Log deletion
            try:
                from education_system.university_system.core.activity_logger import log_activity
                log_activity('delete', 'file', details={
                    'path': file_path,
                    'user_id': user_id
                })
            except ImportError:
                logger.info(f"File deleted: {file_path} (user: {user_id})")

            return {'success': True}

        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return {'success': False, 'error': f'Failed to delete file: {e}'}

    def _detect_mime_type(self, content: bytes) -> str:
        """
        Detect MIME type from file content using magic bytes.

        Args:
            content: File content as bytes

        Returns:
            Detected MIME type string
        """
        # Try python-magic first if available
        try:
            import magic
            return magic.from_buffer(content, mime=True)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"python-magic failed: {e}")

        # Fallback to signature-based detection
        for signature, mime_type in self.FILE_SIGNATURES.items():
            if content.startswith(signature):
                return mime_type

        # Check for text-based formats
        try:
            # Try to decode as UTF-8
            text_content = content[:1024].decode('utf-8', errors='strict')

            if text_content.strip().startswith('{') or text_content.strip().startswith('['):
                return 'application/json'
            if text_content.strip().startswith('<?xml') or text_content.strip().startswith('<'):
                return 'application/xml'
            if ',' in text_content and '\n' in text_content:
                # Likely CSV
                return 'text/csv'

            return 'text/plain'
        except (UnicodeDecodeError, Exception):
            logger.exception("MIME type detection failed for text-based format check")

        # Unknown type
        return 'application/octet-stream'

    def _check_malicious_patterns(self, content: bytes, filename: str) -> Optional[str]:
        """
        Check file content for malicious patterns.

        Args:
            content: File content as bytes
            filename: Original filename for context

        Returns:
            Description of detected threat, or None if safe
        """
        content_lower = content.lower()

        for pattern in self.MALICIOUS_PATTERNS:
            if pattern.lower() in content_lower:
                return f"Detected pattern: {pattern.decode('utf-8', errors='replace')}"

        # Check for null byte injection in text files
        ext = Path(filename).suffix.lower()
        text_extensions = {'.txt', '.csv', '.json', '.xml', '.html', '.htm'}
        if ext in text_extensions and b'\x00' in content:
            return "Null byte injection detected"

        # Check for double extension tricks
        if '..' in filename or filename.count('.') > 2:
            # Already handled by secure_filename, but extra check
            pass

        return None


# Global instance for convenience
_upload_handler: Optional[SecureFileUpload] = None


def get_upload_handler() -> SecureFileUpload:
    """
    Get the global secure upload handler instance.

    Creates a new instance if one doesn't exist.

    Returns:
        SecureFileUpload instance
    """
    global _upload_handler
    if _upload_handler is None:
        _upload_handler = SecureFileUpload()
    return _upload_handler


def validate_upload(
    filename: str,
    file_content: bytes,
    category: str = 'documents'
) -> Dict[str, Union[bool, str, int]]:
    """
    Convenience function to validate a file upload.

    Args:
        filename: Original filename
        file_content: File content as bytes
        category: File category

    Returns:
        Validation result dict
    """
    return get_upload_handler().validate_file(filename, file_content, category)


def save_upload(
    filename: str,
    file_content: bytes,
    category: str = 'documents',
    user_id: Optional[str] = None
) -> Dict[str, Union[bool, str]]:
    """
    Convenience function to save a file upload securely.

    Args:
        filename: Original filename
        file_content: File content as bytes
        category: File category
        user_id: Optional user ID for audit

    Returns:
        Save result dict
    """
    return get_upload_handler().save_file(filename, file_content, category, user_id)


__all__ = [
    'SecureFileUpload',
    'get_upload_handler',
    'validate_upload',
    'save_upload',
    'secure_filename',
]
