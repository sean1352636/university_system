"""
Comprehensive tests for file_upload module.

Tests cover:
- secure_filename() sanitization
- SecureFileUpload initialization
- validate_file() with all checks
- save_file() with validation and storage
- delete_file() with path traversal protection
- _detect_mime_type() magic byte detection
- _check_malicious_patterns() content scanning
- Convenience functions: get_upload_handler, validate_upload, save_upload
"""

import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from education_system.university_system.infrastructure.security.file_upload import (
    secure_filename,
    SecureFileUpload,
    get_upload_handler,
    validate_upload,
    save_upload,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def upload_dir(tmp_path):
    """Provide a temporary upload directory."""
    d = tmp_path / "uploads"
    d.mkdir()
    return str(d)


@pytest.fixture
def handler(upload_dir):
    """Create a SecureFileUpload instance with temp directory."""
    return SecureFileUpload(upload_dir=upload_dir)


@pytest.fixture(autouse=True)
def reset_global():
    """Reset the global upload handler singleton."""
    import education_system.university_system.infrastructure.security.file_upload as mod
    mod._upload_handler = None
    yield
    mod._upload_handler = None


# ---------------------------------------------------------------------------
# secure_filename
# ---------------------------------------------------------------------------

class TestSecureFilename:
    def test_normal_filename(self):
        assert secure_filename("report.pdf") == "report.pdf"

    def test_empty_string(self):
        assert secure_filename("") == ""

    def test_removes_path_traversal(self):
        result = secure_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_removes_null_bytes(self):
        result = secure_filename("file\x00.txt")
        assert "\x00" not in result

    def test_removes_special_characters(self):
        result = secure_filename("file<name>with|bad:chars.txt")
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result

    def test_replaces_path_separators(self):
        result = secure_filename("path/to/file.txt")
        assert "/" not in result

    def test_strips_leading_dots(self):
        result = secure_filename(".hidden.txt")
        assert not result.startswith(".")

    def test_limits_length(self):
        long_name = "a" * 300 + ".txt"
        result = secure_filename(long_name)
        assert len(result) <= 200

    def test_collapses_spaces_to_underscore(self):
        result = secure_filename("my   file   name.txt")
        assert "   " not in result
        assert "_" in result

    def test_only_dots_returns_empty(self):
        assert secure_filename("...") == ""

    def test_preserves_extension(self):
        result = secure_filename("report.final.pdf")
        assert result.endswith(".pdf")

    def test_unicode_handling(self):
        result = secure_filename("resume_cafe.pdf")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# SecureFileUpload initialization
# ---------------------------------------------------------------------------

class TestSecureFileUploadInit:
    def test_creates_upload_dir(self, tmp_path):
        d = str(tmp_path / "new_uploads")
        handler = SecureFileUpload(upload_dir=d)
        assert Path(d).exists()

    def test_upload_dir_stored(self, handler, upload_dir):
        assert str(handler.upload_dir) == upload_dir


# ---------------------------------------------------------------------------
# validate_file
# ---------------------------------------------------------------------------

class TestValidateFile:
    def test_valid_pdf_content(self, handler):
        content = b"%PDF-1.4 some pdf content here"
        result = handler.validate_file("report.pdf", content, "documents")
        assert result["valid"] is True
        assert result["safe_filename"] == "report.pdf"
        assert result["mime_type"] == "application/pdf"

    def test_no_filename(self, handler):
        result = handler.validate_file("", b"content", "documents")
        assert result["valid"] is False
        assert "No filename" in result["error"]

    def test_dangerous_extension_blocked(self, handler):
        result = handler.validate_file("script.exe", b"\x00\x00", "documents")
        assert result["valid"] is False
        assert "not allowed" in result["error"]

    def test_php_extension_blocked(self, handler):
        result = handler.validate_file("shell.php", b"data", "documents")
        assert result["valid"] is False

    def test_extension_not_in_category(self, handler):
        # .mp4 not allowed in documents category
        content = b"\x00\x00\x00\x18ftypmp4"
        result = handler.validate_file("video.mp4", content, "documents")
        assert result["valid"] is False
        assert "not allowed" in result["error"]

    def test_file_too_large(self, handler):
        # Create content larger than image limit (10MB)
        big_content = b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)
        result = handler.validate_file("photo.jpg", big_content, "images")
        assert result["valid"] is False
        assert "too large" in result["error"]

    def test_empty_file(self, handler):
        result = handler.validate_file("empty.txt", b"", "documents")
        assert result["valid"] is False
        assert "Empty" in result["error"]

    def test_malicious_php_content(self, handler):
        content = b"%PDF-1.4 <?php system('ls'); ?>"
        result = handler.validate_file("doc.pdf", content, "documents")
        assert result["valid"] is False
        assert "malicious" in result["error"].lower()

    def test_malicious_script_tag(self, handler):
        content = b"%PDF-1.4 <script>alert(1)</script>"
        result = handler.validate_file("doc.pdf", content, "documents")
        assert result["valid"] is False

    def test_unknown_category_defaults_to_documents(self, handler):
        content = b"%PDF-1.4 content"
        result = handler.validate_file("doc.pdf", content, "unknown_category")
        assert result["valid"] is True  # PDF is in documents category

    def test_valid_jpeg(self, handler):
        # JPEG magic bytes + minimal content
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        result = handler.validate_file("photo.jpg", content, "images")
        assert result["valid"] is True
        assert result["mime_type"] == "image/jpeg"

    def test_valid_png(self, handler):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = handler.validate_file("image.png", content, "images")
        assert result["valid"] is True
        assert result["mime_type"] == "image/png"

    def test_valid_gif(self, handler):
        content = b"GIF89a" + b"\x00" * 100
        result = handler.validate_file("anim.gif", content, "images")
        assert result["valid"] is True

    def test_text_file_with_null_bytes(self, handler):
        content = b"normal text\x00hidden content"
        result = handler.validate_file("data.txt", content, "documents")
        assert result["valid"] is False
        assert "malicious" in result["error"].lower()

    def test_sanitized_filename_returned(self, handler):
        content = b"%PDF-1.4 content"
        result = handler.validate_file("my  report (final).pdf", content, "documents")
        assert result["valid"] is True
        safe = result["safe_filename"]
        assert "(" not in safe
        assert ")" not in safe


# ---------------------------------------------------------------------------
# save_file
# ---------------------------------------------------------------------------

class TestSaveFile:
    def test_save_valid_file(self, handler):
        content = b"%PDF-1.4 pdf content"
        result = handler.save_file("report.pdf", content, "documents", user_id="user1")
        assert result["success"] is True
        assert "file_path" in result
        assert os.path.exists(result["file_path"])
        assert result["original_name"] == "report.pdf"
        assert "file_hash" in result

    def test_save_invalid_file_fails(self, handler):
        result = handler.save_file("script.exe", b"\x00", "documents")
        assert result["success"] is False

    def test_saved_file_has_unique_name(self, handler):
        content = b"%PDF-1.4 content"
        r1 = handler.save_file("doc.pdf", content, "documents")
        r2 = handler.save_file("doc.pdf", content, "documents")
        assert r1["stored_name"] != r2["stored_name"]

    def test_saves_in_category_subdirectory(self, handler, upload_dir):
        content = b"%PDF-1.4 content"
        result = handler.save_file("doc.pdf", content, "documents")
        assert "/documents/" in result["file_path"]

    def test_mime_type_in_result(self, handler):
        content = b"%PDF-1.4 content"
        result = handler.save_file("doc.pdf", content, "documents")
        assert result["mime_type"] == "application/pdf"

    def test_file_size_in_result(self, handler):
        content = b"%PDF-1.4 content"
        result = handler.save_file("doc.pdf", content, "documents")
        assert result["size"] == len(content)


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

class TestDeleteFile:
    def test_delete_existing_file(self, handler):
        content = b"%PDF-1.4 content"
        save_result = handler.save_file("doc.pdf", content, "documents")
        path = save_result["file_path"]

        result = handler.delete_file(path)
        assert result["success"] is True
        assert not os.path.exists(path)

    def test_delete_nonexistent_file(self, handler, upload_dir):
        result = handler.delete_file(os.path.join(upload_dir, "nonexistent.pdf"))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_delete_outside_upload_dir_blocked(self, handler, tmp_path):
        # Create a file outside the upload directory
        outside = tmp_path / "outside.txt"
        outside.write_text("data")

        result = handler.delete_file(str(outside))
        assert result["success"] is False
        assert "Invalid" in result["error"]


# ---------------------------------------------------------------------------
# _detect_mime_type
# ---------------------------------------------------------------------------

class TestDetectMimeType:
    def test_pdf(self, handler):
        assert handler._detect_mime_type(b"%PDF-1.4 content") == "application/pdf"

    def test_jpeg(self, handler):
        assert handler._detect_mime_type(b"\xff\xd8\xff\xe0data") == "image/jpeg"

    def test_png(self, handler):
        assert handler._detect_mime_type(b"\x89PNG\r\n\x1a\ndata") == "image/png"

    def test_gif87(self, handler):
        assert handler._detect_mime_type(b"GIF87adata") == "image/gif"

    def test_gif89(self, handler):
        assert handler._detect_mime_type(b"GIF89adata") == "image/gif"

    def test_zip(self, handler):
        assert handler._detect_mime_type(b"PK\x03\x04data") == "application/zip"

    def test_gzip(self, handler):
        assert handler._detect_mime_type(b"\x1f\x8bdata") == "application/gzip"

    def test_json_content(self, handler):
        mime = handler._detect_mime_type(b'{"key": "value"}')
        assert mime == "application/json"

    def test_csv_content(self, handler):
        mime = handler._detect_mime_type(b"name,age\nAlice,30\nBob,25\n")
        assert mime == "text/csv"

    def test_plain_text(self, handler):
        mime = handler._detect_mime_type(b"Just some plain text here")
        assert mime == "text/plain"

    def test_unknown_binary(self, handler):
        mime = handler._detect_mime_type(b"\x01\x02\x03\x04\x05\x80\x81\x82")
        assert mime == "application/octet-stream"


# ---------------------------------------------------------------------------
# _check_malicious_patterns
# ---------------------------------------------------------------------------

class TestCheckMaliciousPatterns:
    def test_clean_content(self, handler):
        result = handler._check_malicious_patterns(b"normal pdf content", "doc.pdf")
        assert result is None

    def test_php_detected(self, handler):
        result = handler._check_malicious_patterns(b"data <?php echo 'hi'; ?>", "f.pdf")
        assert result is not None
        assert "<?php" in result

    def test_script_tag_detected(self, handler):
        result = handler._check_malicious_patterns(b"<script>alert(1)</script>", "f.pdf")
        assert result is not None

    def test_eval_detected(self, handler):
        result = handler._check_malicious_patterns(b"some eval(payload) here", "f.pdf")
        assert result is not None

    def test_system_call_detected(self, handler):
        result = handler._check_malicious_patterns(b"exec(cmd) here", "f.pdf")
        assert result is not None

    def test_null_byte_in_text_file(self, handler):
        result = handler._check_malicious_patterns(b"text\x00hidden", "data.txt")
        assert result is not None
        assert "Null byte" in result

    def test_null_byte_in_binary_not_flagged(self, handler):
        # Null bytes in non-text files should not trigger
        result = handler._check_malicious_patterns(b"\x00\x01\x02", "image.png")
        assert result is None

    def test_case_insensitive_detection(self, handler):
        result = handler._check_malicious_patterns(b"data <?PHP echo 'hi'; ?>", "f.pdf")
        assert result is not None

    def test_python_os_import(self, handler):
        result = handler._check_malicious_patterns(b"import os", "f.txt")
        assert result is not None

    def test_svg_xss_onerror(self, handler):
        result = handler._check_malicious_patterns(b'<svg onerror="alert(1)">', "f.svg")
        assert result is not None

    def test_svg_foreign_object(self, handler):
        result = handler._check_malicious_patterns(b"<foreignObject>html</foreignObject>", "f.svg")
        assert result is not None


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------

class TestConstants:
    def test_dangerous_extensions_include_common_threats(self):
        dangerous = SecureFileUpload.DANGEROUS_EXTENSIONS
        assert ".exe" in dangerous
        assert ".php" in dangerous
        assert ".sh" in dangerous
        assert ".bat" in dangerous
        assert ".py" in dangerous
        assert ".js" in dangerous
        assert ".ps1" in dangerous

    def test_allowed_extensions_has_categories(self):
        exts = SecureFileUpload.ALLOWED_EXTENSIONS
        assert "documents" in exts
        assert "images" in exts
        assert "archives" in exts
        assert "videos" in exts
        assert "audio" in exts
        assert "data" in exts

    def test_max_file_sizes_per_category(self):
        sizes = SecureFileUpload.MAX_FILE_SIZES
        assert sizes["images"] < sizes["videos"]
        assert sizes["data"] <= sizes["documents"]


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    def test_get_upload_handler_singleton(self):
        h1 = get_upload_handler()
        h2 = get_upload_handler()
        assert h1 is h2
        assert isinstance(h1, SecureFileUpload)

    def test_validate_upload(self):
        with patch(
            "university_system.infrastructure.security.file_upload.get_upload_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_handler.validate_file.return_value = {"valid": True}
            mock_get.return_value = mock_handler

            result = validate_upload("doc.pdf", b"content", "documents")
            assert result["valid"] is True

    def test_save_upload(self):
        with patch(
            "university_system.infrastructure.security.file_upload.get_upload_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_handler.save_file.return_value = {"success": True}
            mock_get.return_value = mock_handler

            result = save_upload("doc.pdf", b"content", "documents", "user1")
            assert result["success"] is True
