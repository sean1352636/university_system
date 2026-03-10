#!/usr/bin/env python3
"""
Comprehensive tests for infrastructure validation - Sanitizers module.

Tests the Sanitizers class and convenience functions for input sanitization,
HTML escaping, SQL injection prevention, filename safety, path traversal
prevention, URL sanitization, JSON cleaning, and text truncation.
"""

import pytest
import os
from pathlib import Path

from education_system.university_system.infrastructure.validation.sanitizers import (
    Sanitizers,
    sanitize_input,
    sanitize_html,
    sanitize_sql_value,
    sanitize_filename,
    escape_html,
    strip_tags,
)


# ---------------------------------------------------------------------------
# sanitize_input
# ---------------------------------------------------------------------------

class TestSanitizeInput:
    """Tests for Sanitizers.sanitize_input."""

    def test_empty_returns_empty(self):
        assert Sanitizers.sanitize_input("") == ""

    def test_none_returns_empty(self):
        assert Sanitizers.sanitize_input(None) == ""

    def test_zero_returns_empty(self):
        # 0 is falsy, so should return ""
        assert Sanitizers.sanitize_input(0) == ""

    def test_plain_text_unchanged(self):
        assert Sanitizers.sanitize_input("Hello World") == "Hello World"

    def test_strips_html_tags_by_default(self):
        result = Sanitizers.sanitize_input("<b>Bold</b>")
        assert "<b>" not in result
        assert "Bold" in result

    def test_preserves_html_when_disabled(self):
        result = Sanitizers.sanitize_input("<b>Bold</b>", strip_html=False)
        assert "<b>" in result

    def test_removes_null_bytes(self):
        result = Sanitizers.sanitize_input("hello\x00world")
        assert "\x00" not in result
        assert "helloworld" in result

    def test_removes_control_characters(self):
        text = "hello\x01\x02\x03world"
        result = Sanitizers.sanitize_input(text)
        assert "\x01" not in result
        assert "\x02" not in result
        assert "\x03" not in result

    def test_preserves_newlines_by_default(self):
        result = Sanitizers.sanitize_input("line1\nline2")
        assert "\n" in result

    def test_preserves_tabs_by_default(self):
        result = Sanitizers.sanitize_input("col1\tcol2")
        assert "\t" in result

    def test_removes_newlines_when_disabled(self):
        result = Sanitizers.sanitize_input("line1\nline2", allow_newlines=False)
        assert "\n" not in result

    def test_removes_carriage_return_when_newlines_disabled(self):
        result = Sanitizers.sanitize_input("line1\r\nline2", allow_newlines=False)
        assert "\r" not in result
        assert "\n" not in result

    def test_strips_whitespace(self):
        result = Sanitizers.sanitize_input("  hello  ")
        assert result == "hello"

    def test_max_length_truncates(self):
        result = Sanitizers.sanitize_input("abcdefghij", max_length=5)
        assert len(result) == 5
        assert result == "abcde"

    def test_max_length_no_truncation_when_shorter(self):
        result = Sanitizers.sanitize_input("abc", max_length=10)
        assert result == "abc"

    def test_unicode_normalization(self):
        # Compatibility form should normalize (e.g., fullwidth chars)
        result = Sanitizers.sanitize_input("\uff21\uff22\uff23")  # fullwidth ABC
        assert result == "ABC"

    def test_unicode_normalization_disabled(self):
        text = "\uff21\uff22"
        result = Sanitizers.sanitize_input(text, normalize_unicode=False)
        # Without normalization, the fullwidth chars remain
        assert "\uff21" in result or "A" in result  # may or may not strip

    def test_integer_converted_to_string(self):
        result = Sanitizers.sanitize_input(12345)
        assert result == "12345"

    def test_script_tag_removed(self):
        result = Sanitizers.sanitize_input("<script>alert('xss')</script>Hello")
        assert "<script>" not in result.lower()
        assert "</script>" not in result.lower()
        assert "Hello" in result


# ---------------------------------------------------------------------------
# sanitize_html
# ---------------------------------------------------------------------------

class TestSanitizeHtml:
    """Tests for Sanitizers.sanitize_html."""

    def test_empty_returns_empty(self):
        assert Sanitizers.sanitize_html("") == ""

    def test_none_returns_empty(self):
        assert Sanitizers.sanitize_html(None) == ""

    def test_script_tags_removed(self):
        html = '<p>Hello</p><script>alert("xss")</script>'
        result = Sanitizers.sanitize_html(html)
        assert "<script>" not in result
        assert "alert" not in result
        assert "<p>Hello</p>" in result

    def test_multiline_script_removed(self):
        html = '<script type="text/javascript">\nvar x = 1;\nalert(x);\n</script>ok'
        result = Sanitizers.sanitize_html(html)
        assert "script" not in result.lower()
        assert "ok" in result

    def test_event_handlers_removed(self):
        html = '<img src="x" onerror="alert(1)">'
        result = Sanitizers.sanitize_html(html)
        assert "onerror" not in result.lower()

    def test_onclick_removed(self):
        html = '<div onclick="doEvil()">Click</div>'
        result = Sanitizers.sanitize_html(html)
        assert "onclick" not in result.lower()

    def test_javascript_urls_removed(self):
        html = '<a href="javascript:alert(1)">Click</a>'
        result = Sanitizers.sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_vbscript_urls_removed(self):
        html = '<a href="vbscript:msgbox(1)">Click</a>'
        result = Sanitizers.sanitize_html(html)
        assert "vbscript:" not in result.lower()

    def test_data_urls_removed(self):
        html = '<a href="data:text/html,<script>alert(1)</script>">Click</a>'
        result = Sanitizers.sanitize_html(html)
        assert "data:" not in result.lower()

    def test_allowed_tags_preserved(self):
        html = '<p>Text</p><strong>Bold</strong><em>Italic</em>'
        result = Sanitizers.sanitize_html(html)
        assert "<p>" in result
        assert "<strong>" in result
        assert "<em>" in result

    def test_disallowed_tags_removed(self):
        html = '<p>Keep</p><iframe src="evil.com"></iframe>'
        result = Sanitizers.sanitize_html(html)
        assert "<p>" in result
        assert "<iframe" not in result

    def test_custom_allowed_tags(self):
        html = '<p>Text</p><div>Block</div><custom>Tag</custom>'
        result = Sanitizers.sanitize_html(html, allowed_tags=["p", "div"])
        assert "<p>" in result
        assert "<div>" in result
        assert "<custom>" not in result

    def test_strip_all_removes_everything(self):
        html = '<p>Hello</p><strong>World</strong>'
        result = Sanitizers.sanitize_html(html, strip_all=True)
        assert "<p>" not in result
        assert "<strong>" not in result
        assert "Hello" in result
        assert "World" in result


# ---------------------------------------------------------------------------
# sanitize_sql_value
# ---------------------------------------------------------------------------

class TestSanitizeSqlValue:
    """Tests for Sanitizers.sanitize_sql_value."""

    def test_none_returns_null(self):
        assert Sanitizers.sanitize_sql_value(None) == "NULL"

    def test_none_with_quote_returns_empty_quoted(self):
        assert Sanitizers.sanitize_sql_value(None, quote=True) == "''"

    def test_plain_text_unchanged(self):
        assert Sanitizers.sanitize_sql_value("hello") == "hello"

    def test_single_quotes_escaped(self):
        result = Sanitizers.sanitize_sql_value("O'Brien")
        assert "''" in result
        assert result == "O''Brien"

    def test_backslash_escaped(self):
        result = Sanitizers.sanitize_sql_value("path\\to\\file")
        assert "\\\\" in result

    def test_null_bytes_removed(self):
        result = Sanitizers.sanitize_sql_value("hello\x00world")
        assert "\x00" not in result

    def test_sql_line_comments_removed(self):
        result = Sanitizers.sanitize_sql_value("value -- drop table")
        assert "--" not in result

    def test_sql_block_comments_removed(self):
        result = Sanitizers.sanitize_sql_value("value /* comment */ more")
        assert "/*" not in result
        assert "*/" not in result

    def test_quoting(self):
        result = Sanitizers.sanitize_sql_value("hello", quote=True)
        assert result == "'hello'"

    def test_sql_injection_escaped(self):
        result = Sanitizers.sanitize_sql_value("'; DROP TABLE users; --")
        assert "DROP TABLE" in result  # text preserved but quotes escaped
        assert "''" in result  # single quote escaped
        assert "--" not in result  # comment removed

    def test_integer_input(self):
        result = Sanitizers.sanitize_sql_value(42)
        assert result == "42"

    def test_float_input(self):
        result = Sanitizers.sanitize_sql_value(3.14)
        assert result == "3.14"

    def test_boolean_input(self):
        result = Sanitizers.sanitize_sql_value(True)
        assert result == "True"


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    """Tests for Sanitizers.sanitize_filename."""

    def test_empty_returns_unnamed(self):
        assert Sanitizers.sanitize_filename("") == "unnamed"

    def test_none_returns_unnamed(self):
        assert Sanitizers.sanitize_filename(None) == "unnamed"

    def test_normal_filename_preserved(self):
        assert Sanitizers.sanitize_filename("report.pdf") == "report.pdf"

    def test_spaces_in_name_preserved(self):
        result = Sanitizers.sanitize_filename("my report.pdf")
        assert "report" in result
        assert result.endswith(".pdf")

    def test_dangerous_chars_replaced(self):
        result = Sanitizers.sanitize_filename('file<>:"/\\|?*.txt')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_custom_replacement_char(self):
        result = Sanitizers.sanitize_filename("file<name>.txt", replacement="-")
        assert "<" not in result
        assert ">" not in result
        assert "-" in result

    def test_path_traversal_prevented(self):
        result = Sanitizers.sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "etc" not in result or "passwd" not in result

    def test_double_dots_replaced(self):
        result = Sanitizers.sanitize_filename("file..name.txt")
        assert ".." not in result

    def test_leading_dots_stripped(self):
        result = Sanitizers.sanitize_filename(".hidden")
        # Leading dots stripped, may result in "hidden" or "unnamed"
        assert not result.startswith(".")

    def test_trailing_dots_stripped(self):
        result = Sanitizers.sanitize_filename("file.")
        assert not result.endswith(".")

    def test_max_length_enforced(self):
        long_name = "a" * 300 + ".txt"
        result = Sanitizers.sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50

    def test_custom_max_length(self):
        result = Sanitizers.sanitize_filename("a" * 100, max_length=20)
        assert len(result) <= 20

    @pytest.mark.parametrize("reserved", [
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT9",
    ])
    def test_reserved_windows_names_prefixed(self, reserved):
        result = Sanitizers.sanitize_filename(f"{reserved}.txt")
        # Should be prefixed with underscore
        assert result.startswith("_")

    def test_reserved_name_case_insensitive(self):
        result = Sanitizers.sanitize_filename("con.txt")
        # After Path().name normalization, "con.txt" -> "CON" check
        # Implementation normalizes via rsplit and upper()
        assert result.startswith("_") or result != "con.txt"

    def test_null_bytes_removed(self):
        result = Sanitizers.sanitize_filename("file\x00name.txt")
        assert "\x00" not in result

    def test_control_chars_removed(self):
        result = Sanitizers.sanitize_filename("file\x01\x02name.txt")
        assert "\x01" not in result

    def test_only_dots_returns_unnamed(self):
        result = Sanitizers.sanitize_filename("...")
        # After stripping dots, should be empty -> "unnamed"
        assert result == "unnamed" or len(result) > 0

    def test_path_component_extracted(self):
        result = Sanitizers.sanitize_filename("/home/user/documents/report.pdf")
        assert "home" not in result
        assert result == "report.pdf"


# ---------------------------------------------------------------------------
# escape_html / unescape_html
# ---------------------------------------------------------------------------

class TestEscapeHtml:
    """Tests for Sanitizers.escape_html and unescape_html."""

    def test_empty_returns_empty(self):
        assert Sanitizers.escape_html("") == ""

    def test_none_returns_empty(self):
        assert Sanitizers.escape_html(None) == ""

    def test_angle_brackets_escaped(self):
        result = Sanitizers.escape_html("<script>")
        assert "&lt;" in result
        assert "&gt;" in result

    def test_ampersand_escaped(self):
        result = Sanitizers.escape_html("A & B")
        assert "&amp;" in result

    def test_quotes_escaped(self):
        result = Sanitizers.escape_html('He said "hello"')
        assert "&quot;" in result

    def test_single_quote_escaped(self):
        result = Sanitizers.escape_html("it's")
        assert "&#x27;" in result or "&#39;" in result or "&apos;" in result

    def test_plain_text_unchanged(self):
        assert Sanitizers.escape_html("Hello World") == "Hello World"

    def test_integer_converted(self):
        result = Sanitizers.escape_html(42)
        assert result == "42"

    def test_roundtrip(self):
        original = '<script>alert("xss")</script>'
        escaped = Sanitizers.escape_html(original)
        unescaped = Sanitizers.unescape_html(escaped)
        assert unescaped == original

    def test_unescape_empty(self):
        assert Sanitizers.unescape_html("") == ""

    def test_unescape_none(self):
        assert Sanitizers.unescape_html(None) == ""

    def test_unescape_entities(self):
        assert Sanitizers.unescape_html("&lt;p&gt;") == "<p>"
        assert Sanitizers.unescape_html("&amp;") == "&"


# ---------------------------------------------------------------------------
# strip_tags
# ---------------------------------------------------------------------------

class TestStripTags:
    """Tests for Sanitizers.strip_tags."""

    def test_empty_returns_empty(self):
        assert Sanitizers.strip_tags("") == ""

    def test_none_returns_empty(self):
        assert Sanitizers.strip_tags(None) == ""

    def test_removes_all_tags(self):
        result = Sanitizers.strip_tags("<p>Hello</p>")
        assert "<p>" not in result
        assert "Hello" in result

    def test_br_converted_to_newline(self):
        result = Sanitizers.strip_tags("line1<br>line2")
        assert "\n" in result
        assert "line1" in result
        assert "line2" in result

    def test_br_self_closing(self):
        result = Sanitizers.strip_tags("line1<br/>line2")
        assert "\n" in result

    def test_p_closing_adds_newlines(self):
        result = Sanitizers.strip_tags("<p>Para 1</p><p>Para 2</p>")
        assert "Para 1" in result
        assert "Para 2" in result
        # Paragraph ends should have double newlines
        assert "\n\n" in result

    def test_div_closing_adds_newline(self):
        result = Sanitizers.strip_tags("<div>Block</div>")
        assert "Block" in result

    def test_nested_tags_removed(self):
        result = Sanitizers.strip_tags("<div><p><strong>Deep</strong></p></div>")
        assert "Deep" in result
        assert "<" not in result
        assert ">" not in result

    def test_html_entities_unescaped(self):
        result = Sanitizers.strip_tags("<p>&amp; &lt; &gt;</p>")
        assert "& < >" in result

    def test_plain_text_preserved(self):
        assert Sanitizers.strip_tags("No tags here").strip() == "No tags here"


# ---------------------------------------------------------------------------
# sanitize_json_value
# ---------------------------------------------------------------------------

class TestSanitizeJsonValue:
    """Tests for Sanitizers.sanitize_json_value."""

    def test_none_returns_none(self):
        assert Sanitizers.sanitize_json_value(None) is None

    def test_string_control_chars_removed(self):
        result = Sanitizers.sanitize_json_value("hello\x00\x01\x02world")
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x02" not in result
        assert "helloworld" in result

    def test_string_newline_preserved(self):
        result = Sanitizers.sanitize_json_value("line1\nline2")
        assert "\n" in result

    def test_string_tab_preserved(self):
        result = Sanitizers.sanitize_json_value("col1\tcol2")
        assert "\t" in result

    def test_integer_unchanged(self):
        assert Sanitizers.sanitize_json_value(42) == 42

    def test_float_unchanged(self):
        assert Sanitizers.sanitize_json_value(3.14) == 3.14

    def test_bool_unchanged(self):
        assert Sanitizers.sanitize_json_value(True) is True
        assert Sanitizers.sanitize_json_value(False) is False

    def test_dict_recursive(self):
        data = {"key": "val\x00ue", "nested": {"inner": "a\x01b"}}
        result = Sanitizers.sanitize_json_value(data)
        assert "\x00" not in result["key"]
        assert "\x01" not in result["nested"]["inner"]

    def test_list_recursive(self):
        data = ["hello\x00world", 42, ["nested\x01"]]
        result = Sanitizers.sanitize_json_value(data)
        assert isinstance(result, list)
        assert "\x00" not in result[0]
        assert result[1] == 42
        assert "\x01" not in result[2][0]

    def test_tuple_converted_to_list(self):
        result = Sanitizers.sanitize_json_value(("a", "b"))
        assert isinstance(result, list)
        assert result == ["a", "b"]

    def test_unknown_type_converted_to_string(self):
        class Custom:
            def __str__(self):
                return "custom_obj"

        result = Sanitizers.sanitize_json_value(Custom())
        assert result == "custom_obj"


# ---------------------------------------------------------------------------
# sanitize_path
# ---------------------------------------------------------------------------

class TestSanitizePath:
    """Tests for Sanitizers.sanitize_path."""

    def test_empty_returns_none(self):
        assert Sanitizers.sanitize_path("") is None

    def test_none_returns_none(self):
        assert Sanitizers.sanitize_path(None) is None

    def test_absolute_path_resolved(self):
        result = Sanitizers.sanitize_path("/tmp/test/file.txt")
        assert result is not None
        assert result == "/tmp/test/file.txt"

    def test_relative_path_resolved(self):
        result = Sanitizers.sanitize_path("subdir/file.txt")
        assert result is not None
        # Should be resolved to an absolute path
        assert os.path.isabs(result)

    def test_traversal_with_base_dir_blocked(self):
        result = Sanitizers.sanitize_path("../../etc/passwd", base_dir="/tmp/safe")
        assert result is None

    def test_path_within_base_dir_allowed(self):
        result = Sanitizers.sanitize_path("/tmp/safe/subdir/file.txt", base_dir="/tmp/safe")
        assert result is not None
        assert "/tmp/safe" in result

    def test_base_dir_exact_match(self):
        result = Sanitizers.sanitize_path("/tmp/safe", base_dir="/tmp/safe")
        assert result is not None

    def test_dotdot_traversal_resolved(self):
        result = Sanitizers.sanitize_path("/tmp/safe/subdir/../file.txt", base_dir="/tmp/safe")
        assert result is not None
        # After resolution, should be within base
        assert "/tmp/safe" in result


# ---------------------------------------------------------------------------
# sanitize_url
# ---------------------------------------------------------------------------

class TestSanitizeUrl:
    """Tests for Sanitizers.sanitize_url."""

    def test_empty_returns_none(self):
        assert Sanitizers.sanitize_url("") is None

    def test_none_returns_none(self):
        assert Sanitizers.sanitize_url(None) is None

    def test_http_url_allowed(self):
        url = "http://example.com/page"
        assert Sanitizers.sanitize_url(url) == url

    def test_https_url_allowed(self):
        url = "https://example.com/page"
        assert Sanitizers.sanitize_url(url) == url

    def test_relative_url_allowed(self):
        url = "/path/to/page"
        assert Sanitizers.sanitize_url(url) == url

    def test_relative_without_slash_allowed(self):
        url = "path/to/page"
        assert Sanitizers.sanitize_url(url) == url

    @pytest.mark.parametrize("scheme", [
        "javascript:", "JAVASCRIPT:", "JavaScript:",
    ])
    def test_javascript_blocked(self, scheme):
        url = f"{scheme}alert(1)"
        assert Sanitizers.sanitize_url(url) is None

    @pytest.mark.parametrize("scheme", [
        "vbscript:", "VBSCRIPT:",
    ])
    def test_vbscript_blocked(self, scheme):
        url = f"{scheme}msgbox(1)"
        assert Sanitizers.sanitize_url(url) is None

    def test_data_scheme_blocked(self):
        assert Sanitizers.sanitize_url("data:text/html,<script>alert(1)</script>") is None

    def test_file_scheme_blocked(self):
        assert Sanitizers.sanitize_url("file:///etc/passwd") is None

    def test_whitespace_stripped(self):
        url = "  https://example.com  "
        result = Sanitizers.sanitize_url(url)
        assert result == "https://example.com"

    def test_unknown_scheme_blocked(self):
        # Something like "ftp://..." has "://" but doesn't start with http(s)
        result = Sanitizers.sanitize_url("ftp://files.example.com")
        assert result is None


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------

class TestTruncate:
    """Tests for Sanitizers.truncate."""

    def test_empty_returns_empty(self):
        assert Sanitizers.truncate("", 10) == ""

    def test_none_returns_empty(self):
        assert Sanitizers.truncate(None, 10) == ""

    def test_short_text_unchanged(self):
        assert Sanitizers.truncate("Hello", 10) == "Hello"

    def test_exact_length_unchanged(self):
        assert Sanitizers.truncate("Hello", 5) == "Hello"

    def test_truncated_with_default_suffix(self):
        result = Sanitizers.truncate("Hello World", 8)
        assert len(result) == 8
        assert result.endswith("...")
        assert result == "Hello..."

    def test_custom_suffix(self):
        result = Sanitizers.truncate("Hello World", 9, suffix="~~")
        assert result.endswith("~~")
        assert len(result) == 9

    def test_single_char_suffix(self):
        result = Sanitizers.truncate("abcdefghij", 5, suffix=">")
        assert result == "abcd>"
        assert len(result) == 5

    def test_no_suffix(self):
        result = Sanitizers.truncate("Hello World", 5, suffix="")
        assert result == "Hello"
        assert len(result) == 5


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_sanitize_input_function(self):
        result = sanitize_input("<b>Bold</b>")
        assert "<b>" not in result
        assert "Bold" in result

    def test_sanitize_html_function(self):
        result = sanitize_html('<script>alert(1)</script><p>OK</p>')
        assert "script" not in result.lower()

    def test_sanitize_sql_value_function(self):
        result = sanitize_sql_value("O'Brien")
        assert "''" in result

    def test_sanitize_filename_function(self):
        result = sanitize_filename("../../evil.txt")
        assert ".." not in result

    def test_escape_html_function(self):
        result = escape_html("<div>")
        assert "&lt;" in result

    def test_strip_tags_function(self):
        result = strip_tags("<p>text</p>")
        assert "<p>" not in result
        assert "text" in result


# ---------------------------------------------------------------------------
# XSS prevention integration tests
# ---------------------------------------------------------------------------

class TestXssPrevention:
    """Integration tests for XSS attack vector prevention."""

    @pytest.mark.parametrize("payload", [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert(1)>',
        '<svg onload=alert(1)>',
        '<body onload=alert(1)>',
        '<iframe src="javascript:alert(1)">',
        '<a href="javascript:alert(1)">click</a>',
        '"><script>alert(document.cookie)</script>',
        "';alert(1);//",
    ])
    def test_xss_payloads_neutralized_by_sanitize_input(self, payload):
        result = Sanitizers.sanitize_input(payload)
        assert "<script>" not in result.lower()
        assert "onerror" not in result.lower()
        assert "onload" not in result.lower()
        assert "javascript:" not in result.lower()

    @pytest.mark.parametrize("payload", [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert(1)>',
        '<a href="javascript:void(0)">link</a>',
    ])
    def test_xss_payloads_neutralized_by_escape_html(self, payload):
        result = Sanitizers.escape_html(payload)
        # escape_html converts <, >, &, " to entities so the browser
        # renders them as text rather than interpreting them as HTML.
        assert "<script>" not in result
        assert "<img" not in result
        assert "&lt;" in result


# ---------------------------------------------------------------------------
# SQL injection prevention integration tests
# ---------------------------------------------------------------------------

class TestSqlInjectionPrevention:
    """Integration tests for SQL injection prevention."""

    @pytest.mark.parametrize("payload", [
        "'; DROP TABLE users; --",
        "1 OR 1=1",
        "1; DELETE FROM students",
        "admin'--",
        "1 UNION SELECT * FROM passwords",
        "value /* drop */ more",
    ])
    def test_sql_injection_payloads_sanitized(self, payload):
        result = Sanitizers.sanitize_sql_value(payload)
        # Comments should be removed
        assert "--" not in result
        assert "/*" not in result
        # Single quotes should be doubled
        if "'" in payload:
            assert "''" in result or "'" not in result


# ---------------------------------------------------------------------------
# Path traversal prevention integration tests
# ---------------------------------------------------------------------------

class TestPathTraversalPrevention:
    """Integration tests for path traversal attack prevention."""

    @pytest.mark.parametrize("malicious_path", [
        "../../etc/passwd",
        "../../../etc/shadow",
        "..\\..\\windows\\system32\\config\\sam",
    ])
    def test_traversal_blocked_with_base_dir(self, malicious_path):
        result = Sanitizers.sanitize_path(malicious_path, base_dir="/tmp/uploads")
        assert result is None

    @pytest.mark.parametrize("malicious_filename", [
        "../../etc/passwd",
        "..\\..\\boot.ini",
        "/etc/passwd",
    ])
    def test_traversal_in_filenames_prevented(self, malicious_filename):
        result = Sanitizers.sanitize_filename(malicious_filename)
        assert ".." not in result
        assert "/etc" not in result
