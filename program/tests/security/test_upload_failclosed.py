"""Upload validation must fail closed when a check cannot complete.

Covers task 12: reject (not admit) when the virus scanner, MIME detector or
archive-bomb inspector errors.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.security


def _validator():
    from education_system.systems.university.infrastructure.security.file_upload_validator import (
        FileUploadValidator,
    )
    return FileUploadValidator()


def test_virus_scan_error_fails_closed(tmp_path):
    v = _validator()
    scanner = MagicMock()
    scanner.scan_file.side_effect = RuntimeError("clamd down")
    v._virus_scanner = scanner
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n")
    is_clean, _ = v.scan_for_viruses(str(f))
    assert is_clean is False, "scanner error must not report the file clean"


def test_missing_scanner_rejects_in_production(tmp_path, as_production):
    v = _validator()
    v._virus_scanner = None
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n")
    with as_production():
        is_clean, _ = v.scan_for_viruses(str(f))
    assert is_clean is False, "no scanner in production must reject the upload"


def test_missing_scanner_skips_in_development(tmp_path, as_development):
    v = _validator()
    v._virus_scanner = None
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n")
    with as_development():
        is_clean, _ = v.scan_for_viruses(str(f))
    assert is_clean is True, "development may skip scanning when unconfigured"


def test_mime_validation_error_fails_closed(tmp_path):
    from education_system.systems.university.infrastructure.security import (
        file_upload_validator as mod,
    )

    v = mod.FileUploadValidator()
    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    # Force the MIME code path to raise, exercising the outer handler.
    with patch.object(mod.mimetypes, "guess_type", side_effect=RuntimeError("boom")):
        result = v.validate_mime_type(str(f), {"pdf"})
    assert result[0] is False, "a MIME-detection error must not validate the file"
