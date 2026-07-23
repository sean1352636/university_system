"""
Input Sanitizers

Provides sanitization functions to clean and secure user input,
preventing XSS, SQL injection, and other security vulnerabilities.
"""

import re
import html
import html.parser
import io
import unicodedata
from typing import Optional, List, Dict, Any
from pathlib import Path


class _ScriptStripper(html.parser.HTMLParser):
    """HTML parser that removes <script> and <style> elements entirely."""

    _STRIP_TAGS = frozenset(('script', 'style'))

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._out = io.StringIO()
        self._skip_depth = 0
        self._skip_tag: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._STRIP_TAGS:
            if self._skip_depth == 0:
                self._skip_tag = tag.lower()
            self._skip_depth += 1
            return
        if self._skip_depth == 0:
            attr_str = ''.join(f' {k}="{v}"' if v is not None else f' {k}' for k, v in attrs)
            self._out.write(f'<{tag}{attr_str}>')

    def handle_endtag(self, tag):
        if tag.lower() in self._STRIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            if self._skip_depth == 0:
                self._skip_tag = None
            return
        if self._skip_depth == 0:
            self._out.write(f'</{tag}>')

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._out.write(data)

    def handle_entityref(self, name):
        if self._skip_depth == 0:
            self._out.write(f'&{name};')

    def handle_charref(self, name):
        if self._skip_depth == 0:
            self._out.write(f'&#{name};')

    def get_output(self) -> str:
        return self._out.getvalue()


class Sanitizers:
    """
    Centralized input sanitization utilities.

    Usage:
        from education_system.post_18.university_system.infrastructure.validation import Sanitizers

        # Basic sanitization
        clean_text = Sanitizers.sanitize_input(user_input)

        # HTML escaping
        safe_html = Sanitizers.escape_html(user_content)

        # SQL value sanitization
        safe_value = Sanitizers.sanitize_sql_value(user_value)

        # Filename sanitization
        safe_filename = Sanitizers.sanitize_filename(uploaded_name)
    """

    # Characters that are potentially dangerous in various contexts
    SQL_DANGEROUS_CHARS = re.compile(r"['\";\\-]")
    HTML_DANGEROUS_CHARS = re.compile(r'[<>&"\']')
    # NOTE: script removal now uses _ScriptStripper HTML parser (not regex)
    # to avoid regex-based tag filter bypasses.
    SCRIPT_PATTERN = None  # deprecated; kept for backward compat
    EVENT_HANDLER_PATTERN = re.compile(r'\s*on\w+\s*=', re.IGNORECASE)

    # Allowed HTML tags for rich text (if needed)
    ALLOWED_HTML_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li', 'a', 'span']

    # Dangerous filename characters
    FILENAME_DANGEROUS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

    # Unicode normalization form
    UNICODE_FORM = 'NFKC'

    @classmethod
    def sanitize_input(
        cls,
        text: str,
        strip_html: bool = True,
        normalize_unicode: bool = True,
        max_length: Optional[int] = None,
        allow_newlines: bool = True
    ) -> str:
        """
        General-purpose input sanitization.

        Args:
            text: Text to sanitize
            strip_html: Remove HTML tags
            normalize_unicode: Normalize unicode characters
            max_length: Maximum length (truncates if exceeded)
            allow_newlines: Whether to preserve newlines

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Convert to string if needed
        text = str(text)

        # Normalize unicode
        if normalize_unicode:
            text = unicodedata.normalize(cls.UNICODE_FORM, text)

        # Strip HTML tags
        if strip_html:
            text = cls.strip_tags(text)

        # Remove null bytes
        text = text.replace('\x00', '')

        # Handle newlines
        if not allow_newlines:
            text = text.replace('\n', ' ').replace('\r', '')

        # Remove control characters (except newlines/tabs if allowed)
        if allow_newlines:
            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        else:
            text = re.sub(r'[\x00-\x1f\x7f]', '', text)

        # Trim whitespace
        text = text.strip()

        # Truncate if needed
        if max_length and len(text) > max_length:
            text = text[:max_length]

        return text

    @classmethod
    def sanitize_html(
        cls,
        html_content: str,
        allowed_tags: List[str] = None,
        strip_all: bool = False
    ) -> str:
        """
        Sanitize HTML content.

        Args:
            html_content: HTML to sanitize
            allowed_tags: List of allowed tag names
            strip_all: If True, remove all tags

        Returns:
            Sanitized HTML
        """
        if not html_content:
            return ""

        allowed_tags = allowed_tags or cls.ALLOWED_HTML_TAGS

        # Remove script/style tags using HTML parser (not regex) to avoid bypasses
        stripper = _ScriptStripper()
        try:
            stripper.feed(html_content)
            result = stripper.get_output()
        except Exception:
            # Fallback: aggressively strip anything that looks like a script tag
            result = re.sub(r'<\s*script\b[^>]*>.*?<\s*/\s*script[^>]*>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
            result = re.sub(r'<\s*script\b[^>]*/?>', '', result, flags=re.IGNORECASE)

        # Remove event handlers
        result = cls.EVENT_HANDLER_PATTERN.sub(' data-removed=', result)

        # Remove javascript: URLs
        result = re.sub(r'javascript:', '', result, flags=re.IGNORECASE)
        result = re.sub(r'vbscript:', '', result, flags=re.IGNORECASE)
        result = re.sub(r'data:', '', result, flags=re.IGNORECASE)

        if strip_all:
            return cls.strip_tags(result)

        # Remove tags not in allowed list
        def replace_tag(match):
            tag = match.group(1).lower().split()[0]
            if tag.lstrip('/') in allowed_tags:
                return match.group(0)
            return ''

        result = re.sub(r'<(/?\w+)[^>]*>', replace_tag, result)

        return result

    @classmethod
    def sanitize_sql_value(cls, value: Any, quote: bool = False) -> str:
        """
        Sanitize a value for use in SQL queries.

        NOTE: This is a secondary defense layer. Always use parameterized
        queries as the primary protection against SQL injection.

        Args:
            value: Value to sanitize
            quote: Whether to wrap in quotes

        Returns:
            Sanitized value
        """
        if value is None:
            return 'NULL' if not quote else "''"

        # Convert to string
        text = str(value)

        # Escape single quotes by doubling them
        text = text.replace("'", "''")

        # Remove other potentially dangerous characters
        text = text.replace('\\', '\\\\')
        text = text.replace('\x00', '')

        # Remove SQL comments
        text = re.sub(r'--.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

        if quote:
            return f"'{text}'"

        return text

    @classmethod
    def sanitize_filename(
        cls,
        filename: str,
        max_length: int = 255,
        replacement: str = '_'
    ) -> str:
        """
        Sanitize a filename to be safe for the filesystem.

        Args:
            filename: Original filename
            max_length: Maximum length
            replacement: Character to replace dangerous chars with

        Returns:
            Safe filename
        """
        if not filename:
            return "unnamed"

        # Normalize unicode
        filename = unicodedata.normalize(cls.UNICODE_FORM, filename)

        # Get just the filename part (remove path)
        filename = Path(filename).name

        # Replace dangerous characters
        filename = cls.FILENAME_DANGEROUS.sub(replacement, filename)

        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')

        # Prevent directory traversal
        filename = filename.replace('..', replacement)

        # Reserved Windows names
        reserved = {'CON', 'PRN', 'AUX', 'NUL',
                   'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
                   'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}

        name_without_ext = filename.rsplit('.', 1)[0].upper()
        if name_without_ext in reserved:
            filename = f"_{filename}"

        # Truncate if too long
        if len(filename) > max_length:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_length = max_length - len(ext) - 1 if ext else max_length
            filename = f"{name[:max_name_length]}.{ext}" if ext else name[:max_length]

        # Ensure we have something
        if not filename:
            return "unnamed"

        return filename

    @classmethod
    def escape_html(cls, text: str) -> str:
        """
        Escape HTML special characters.

        Args:
            text: Text to escape

        Returns:
            HTML-escaped text
        """
        if not text:
            return ""

        return html.escape(str(text), quote=True)

    @classmethod
    def unescape_html(cls, text: str) -> str:
        """
        Unescape HTML entities.

        Args:
            text: Text with HTML entities

        Returns:
            Unescaped text
        """
        if not text:
            return ""

        return html.unescape(str(text))

    @classmethod
    def strip_tags(cls, html_content: str) -> str:
        """
        Remove all HTML tags from content.

        Args:
            html_content: HTML to strip

        Returns:
            Plain text
        """
        if not html_content:
            return ""

        # First, handle common block elements with newlines
        text = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)

        # Remove all tags
        text = re.sub(r'<[^>]+>', '', text)

        # Unescape HTML entities
        text = html.unescape(text)

        # Clean up whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

        return text.strip()

    @classmethod
    def sanitize_json_value(cls, value: Any) -> Any:
        """
        Sanitize a value for JSON encoding.

        Args:
            value: Value to sanitize

        Returns:
            JSON-safe value
        """
        if value is None:
            return None

        if isinstance(value, str):
            # Remove control characters except newlines and tabs
            value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
            return value

        if isinstance(value, (int, float, bool)):
            return value

        if isinstance(value, dict):
            return {k: cls.sanitize_json_value(v) for k, v in value.items()}

        if isinstance(value, (list, tuple)):
            return [cls.sanitize_json_value(v) for v in value]

        return str(value)

    @classmethod
    def sanitize_path(cls, path: str, base_dir: Optional[str] = None) -> Optional[str]:
        """
        Sanitize a file path to prevent directory traversal attacks.

        Args:
            path: Path to sanitize
            base_dir: If provided, ensure path is within this directory

        Returns:
            Safe path or None if invalid
        """
        if not path:
            return None

        # Normalize the path
        path = Path(path).resolve()

        # Check for directory traversal
        if base_dir:
            base = Path(base_dir).resolve()
            try:
                path.relative_to(base)
            except ValueError:
                return None  # Path is outside base directory

        return str(path)

    @classmethod
    def sanitize_url(cls, url: str) -> Optional[str]:
        """
        Sanitize a URL to prevent XSS and open redirect attacks.

        Args:
            url: URL to sanitize

        Returns:
            Safe URL or None if invalid
        """
        if not url:
            return None

        url = url.strip()

        # Check for dangerous schemes
        dangerous_schemes = ['javascript:', 'vbscript:', 'data:', 'file:']
        url_lower = url.lower()
        for scheme in dangerous_schemes:
            if url_lower.startswith(scheme):
                return None

        # Basic URL validation
        if not re.match(r'^https?://', url, re.IGNORECASE):
            # Relative URL - should be safe
            if url.startswith('/') or '://' not in url:
                return url
            return None

        return url

    @classmethod
    def truncate(cls, text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text to a maximum length.

        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add when truncating

        Returns:
            Truncated text
        """
        if not text or len(text) <= max_length:
            return text or ""

        return text[:max_length - len(suffix)] + suffix


# Convenience functions
def sanitize_input(text: str, **kwargs) -> str:
    """Sanitize general text input."""
    return Sanitizers.sanitize_input(text, **kwargs)


def sanitize_html(html_content: str, **kwargs) -> str:
    """Sanitize HTML content."""
    return Sanitizers.sanitize_html(html_content, **kwargs)


def sanitize_sql_value(value: Any, **kwargs) -> str:
    """Sanitize value for SQL (use parameterized queries as primary defense)."""
    return Sanitizers.sanitize_sql_value(value, **kwargs)


def sanitize_filename(filename: str, **kwargs) -> str:
    """Sanitize filename for filesystem."""
    return Sanitizers.sanitize_filename(filename, **kwargs)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return Sanitizers.escape_html(text)


def strip_tags(html_content: str) -> str:
    """Remove all HTML tags."""
    return Sanitizers.strip_tags(html_content)
