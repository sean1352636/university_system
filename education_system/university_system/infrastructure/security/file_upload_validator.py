"""
File Upload Security Validator

Provides comprehensive file upload validation including:
- File type validation (whitelist and blacklist)
- File size limits
- Virus scanning integration
- Image validation
- Filename sanitization
- MIME type verification
"""

import os
import re
import mimetypes
import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UploadValidationResult:
    """Result of file upload validation"""
    valid: bool
    error: Optional[str] = None
    warnings: List[str] = None
    sanitized_filename: Optional[str] = None
    file_hash: Optional[str] = None
    mime_type: Optional[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class FileUploadValidator:
    """
    Comprehensive file upload validator with security checks.

    Usage:
        validator = FileUploadValidator(
            allowed_extensions=['pdf', 'docx', 'jpg'],
            max_size_mb=10
        )

        result = validator.validate_file(file_path, original_filename)
        if result.valid:
            safe_filename = result.sanitized_filename
        else:
            print(result.error)
    """

    # Dangerous extensions that should never be allowed
    DANGEROUS_EXTENSIONS = {
        'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js', 'jar',
        'ps1', 'msi', 'app', 'deb', 'rpm', 'dmg', 'pkg', 'sh', 'bash',
        'dll', 'sys', 'drv', 'ocx', 'cpl', 'inf', 'reg', 'lnk',
        'wsf', 'wsh', 'hta', 'job', 'vb', 'vbe', 'jse', 'ws', 'wsf'
    }

    # Common document extensions
    DOCUMENT_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'odt', 'ods', 'odp', 'txt', 'rtf', 'csv'
    }

    # Common image extensions
    IMAGE_EXTENSIONS = {
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'ico'
    }

    # Common video extensions
    VIDEO_EXTENSIONS = {
        'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v'
    }

    # Common audio extensions
    AUDIO_EXTENSIONS = {
        'mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma'
    }

    # Archive extensions
    ARCHIVE_EXTENSIONS = {
        'zip', '7z', 'rar', 'tar', 'gz', 'bz2', 'xz'
    }

    def __init__(
        self,
        allowed_extensions: Optional[Set[str]] = None,
        blocked_extensions: Optional[Set[str]] = None,
        max_size_mb: float = 50,
        min_size_bytes: int = 1,
        allow_dangerous: bool = False,
        scan_viruses: bool = False,
        validate_images: bool = True,
        sanitize_filenames: bool = True
    ):
        """
        Initialize file upload validator.

        Args:
            allowed_extensions: Set of allowed file extensions (None = allow all except dangerous)
            blocked_extensions: Set of blocked file extensions
            max_size_mb: Maximum file size in megabytes
            min_size_bytes: Minimum file size in bytes
            allow_dangerous: Whether to allow potentially dangerous extensions
            scan_viruses: Whether to scan files for viruses (requires ClamAV)
            validate_images: Whether to validate image files
            sanitize_filenames: Whether to sanitize filenames
        """
        self.allowed_extensions = set(ext.lower() for ext in (allowed_extensions or set()))
        self.blocked_extensions = set(ext.lower() for ext in (blocked_extensions or set()))
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.min_size_bytes = min_size_bytes
        self.allow_dangerous = allow_dangerous
        self.scan_viruses = scan_viruses
        self.validate_images = validate_images
        self.sanitize_filenames = sanitize_filenames

        # Add dangerous extensions to blocked list if not allowing dangerous files
        if not allow_dangerous:
            self.blocked_extensions.update(self.DANGEROUS_EXTENSIONS)

        # Initialize virus scanner if requested
        self._virus_scanner = None
        if scan_viruses:
            self._init_virus_scanner()

    def _init_virus_scanner(self):
        """Initialize ClamAV virus scanner if available"""
        try:
            import pyclamd
            self._virus_scanner = pyclamd.ClamdUnixSocket()
            # Test connection
            if not self._virus_scanner.ping():
                logger.warning("ClamAV daemon not responding, virus scanning disabled")
                self._virus_scanner = None
            else:
                logger.info("ClamAV virus scanner initialized")
        except ImportError:
            logger.warning("pyclamd not installed, virus scanning disabled")
            self._virus_scanner = None
        except Exception as e:
            logger.warning(f"Failed to initialize virus scanner: {e}")
            self._virus_scanner = None

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent directory traversal and other attacks.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Get just the filename (remove any path)
        filename = os.path.basename(filename)

        # Remove null bytes
        filename = filename.replace('\x00', '')

        # Replace dangerous characters
        # Allow: letters, numbers, dash, underscore, period
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

        # Prevent multiple dots in a row
        filename = re.sub(r'\.{2,}', '.', filename)

        # Prevent leading dots
        filename = filename.lstrip('.')

        # Limit length
        name, ext = os.path.splitext(filename)
        if len(name) > 200:
            name = name[:200]
        filename = name + ext

        # Ensure filename is not empty
        if not filename or filename == '.':
            filename = 'unnamed_file'

        return filename

    def get_file_extension(self, filename: str) -> str:
        """Get lowercase file extension without dot"""
        ext = os.path.splitext(filename)[1].lower()
        return ext.lstrip('.')

    def validate_extension(self, extension: str) -> Tuple[bool, Optional[str]]:
        """
        Validate file extension.

        Returns:
            Tuple of (is_valid, error_message)
        """
        extension = extension.lower()

        # Check if blocked
        if extension in self.blocked_extensions:
            return False, f"File type '{extension}' is not allowed"

        # Check if in allowed list (if whitelist is specified)
        if self.allowed_extensions and extension not in self.allowed_extensions:
            return False, f"File type '{extension}' is not allowed. Allowed types: {', '.join(sorted(self.allowed_extensions))}"

        return True, None

    def validate_size(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate file size.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            size = os.path.getsize(file_path)

            if size < self.min_size_bytes:
                return False, f"File is too small (minimum: {self.min_size_bytes} bytes)"

            if size > self.max_size_bytes:
                max_mb = self.max_size_bytes / (1024 * 1024)
                return False, f"File is too large (maximum: {max_mb:.1f} MB)"

            return True, None

        except OSError as e:
            return False, f"Could not read file size: {e}"

    def calculate_file_hash(self, file_path: str, algorithm: str = 'sha256') -> Optional[str]:
        """
        Calculate file hash for integrity checking.

        Args:
            file_path: Path to file
            algorithm: Hash algorithm (sha256, sha1, md5)

        Returns:
            Hex digest of file hash or None on error
        """
        try:
            hasher = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return None

    def validate_mime_type(self, file_path: str, expected_extensions: Set[str]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate file MIME type matches extension.

        Returns:
            Tuple of (is_valid, error_message, detected_mime_type)
        """
        try:
            # Guess MIME type from file extension
            mime_type, _ = mimetypes.guess_type(file_path)

            if mime_type is None:
                return True, None, None  # Unknown MIME type, can't validate

            # Try to detect actual MIME type from file content if python-magic is available
            try:
                import magic
                detected_mime = magic.from_file(file_path, mime=True)

                # Compare detected MIME with expected
                extension = self.get_file_extension(file_path)
                expected_mime, _ = mimetypes.guess_type(f"file.{extension}")

                if expected_mime and detected_mime:
                    # Get base type (e.g., 'image' from 'image/jpeg')
                    detected_base = detected_mime.split('/')[0]
                    expected_base = expected_mime.split('/')[0]

                    if detected_base != expected_base:
                        return False, f"File content does not match extension (detected: {detected_mime}, expected: {expected_mime})", detected_mime

                return True, None, detected_mime

            except ImportError:
                # python-magic not available, use basic validation
                return True, None, mime_type

        except Exception as e:
            logger.error(f"Error validating MIME type: {e}")
            return True, None, None  # Don't fail validation on error

    def validate_image(self, file_path: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        Validate image file.

        Returns:
            Tuple of (is_valid, error_message, warnings)
        """
        warnings = []

        try:
            from PIL import Image

            try:
                with Image.open(file_path) as img:
                    # Verify image can be loaded
                    img.verify()

                    # Check image size
                    width, height = img.size
                    if width * height > 100_000_000:  # 100 megapixels
                        warnings.append("Image resolution is very large")

                    # Check for EXIF data (may contain sensitive info)
                    if hasattr(img, '_getexif') and img._getexif():
                        warnings.append("Image contains EXIF metadata")

                return True, None, warnings

            except Exception as e:
                return False, f"Invalid or corrupted image file: {e}", warnings

        except ImportError:
            # PIL not available, skip image validation
            return True, None, warnings

    def scan_for_viruses(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Scan file for viruses using ClamAV.

        Returns:
            Tuple of (is_clean, virus_name)
        """
        if not self._virus_scanner:
            return True, None  # Scanner not available, skip check

        try:
            result = self._virus_scanner.scan_file(file_path)

            if result is None:
                # File is clean
                return True, None
            else:
                # Virus detected
                virus_name = result[file_path][1] if file_path in result else "Unknown"
                logger.warning(f"Virus detected in uploaded file: {virus_name}")
                return False, virus_name

        except Exception as e:
            logger.error(f"Error scanning file for viruses: {e}")
            return True, None  # Don't fail validation on scanner error

    def validate_file(
        self,
        file_path: str,
        original_filename: Optional[str] = None
    ) -> UploadValidationResult:
        """
        Perform comprehensive file validation.

        Args:
            file_path: Path to uploaded file
            original_filename: Original filename (if different from file_path)

        Returns:
            UploadValidationResult with validation results
        """
        warnings = []

        # Use original filename if provided, otherwise use file_path
        filename = original_filename or os.path.basename(file_path)

        # Sanitize filename
        sanitized_filename = self.sanitize_filename(filename) if self.sanitize_filenames else filename
        if sanitized_filename != filename:
            warnings.append("Filename was sanitized for security")

        # Get file extension
        extension = self.get_file_extension(sanitized_filename)

        # Validate extension
        ext_valid, ext_error = self.validate_extension(extension)
        if not ext_valid:
            return UploadValidationResult(
                valid=False,
                error=ext_error,
                sanitized_filename=sanitized_filename
            )

        # Validate file size
        size_valid, size_error = self.validate_size(file_path)
        if not size_valid:
            return UploadValidationResult(
                valid=False,
                error=size_error,
                sanitized_filename=sanitized_filename
            )

        # Calculate file hash
        file_hash = self.calculate_file_hash(file_path)

        # Validate MIME type
        mime_valid, mime_error, mime_type = self.validate_mime_type(file_path, {extension})
        if not mime_valid:
            return UploadValidationResult(
                valid=False,
                error=mime_error,
                sanitized_filename=sanitized_filename,
                file_hash=file_hash,
                mime_type=mime_type
            )

        # Validate images if requested
        if self.validate_images and extension in self.IMAGE_EXTENSIONS:
            img_valid, img_error, img_warnings = self.validate_image(file_path)
            if not img_valid:
                return UploadValidationResult(
                    valid=False,
                    error=img_error,
                    sanitized_filename=sanitized_filename,
                    file_hash=file_hash,
                    mime_type=mime_type
                )
            warnings.extend(img_warnings)

        # Scan for viruses if requested
        if self.scan_viruses:
            virus_clean, virus_name = self.scan_for_viruses(file_path)
            if not virus_clean:
                return UploadValidationResult(
                    valid=False,
                    error=f"File contains virus or malware: {virus_name}",
                    sanitized_filename=sanitized_filename,
                    file_hash=file_hash,
                    mime_type=mime_type
                )

        # All validations passed
        return UploadValidationResult(
            valid=True,
            warnings=warnings,
            sanitized_filename=sanitized_filename,
            file_hash=file_hash,
            mime_type=mime_type
        )


# Pre-configured validators for common use cases
document_validator = FileUploadValidator(
    allowed_extensions=FileUploadValidator.DOCUMENT_EXTENSIONS,
    max_size_mb=50
)

image_validator = FileUploadValidator(
    allowed_extensions=FileUploadValidator.IMAGE_EXTENSIONS,
    max_size_mb=10,
    validate_images=True
)

avatar_validator = FileUploadValidator(
    allowed_extensions={'jpg', 'jpeg', 'png', 'gif'},
    max_size_mb=2,
    validate_images=True
)

strict_validator = FileUploadValidator(
    allowed_extensions=FileUploadValidator.DOCUMENT_EXTENSIONS | FileUploadValidator.IMAGE_EXTENSIONS,
    max_size_mb=25,
    scan_viruses=True,
    validate_images=True
)


__all__ = [
    'FileUploadValidator',
    'UploadValidationResult',
    'document_validator',
    'image_validator',
    'avatar_validator',
    'strict_validator',
]
