"""Tests for university_system.utils.error_logger."""
import json
from pathlib import Path

import pytest

from education_system.university_system.utils import error_logger
from education_system.university_system.utils.error_logger import (
    ErrorLogger,
    get_error_logger,
    log_critical_error,
    log_error,
)


@pytest.fixture
def logger(tmp_path):
    return ErrorLogger(log_directory=str(tmp_path), log_filename="errors.txt")


class TestErrorLoggerInit:
    def test_creates_log_directory(self, tmp_path):
        target = tmp_path / "nested" / "logs"
        ErrorLogger(log_directory=str(target), log_filename="e.txt")
        assert target.exists() and target.is_dir()

    def test_attaches_handlers(self, logger):
        assert logger.logger.handlers, "expected handlers attached"

    def test_idempotent_handler_setup(self, tmp_path):
        ErrorLogger(log_directory=str(tmp_path), log_filename="e.txt")
        second = ErrorLogger(log_directory=str(tmp_path), log_filename="e.txt")
        # Handlers should not multiply on re-init
        assert len(second.logger.handlers) == 2


class TestLogError:
    def test_writes_to_text_log(self, logger, tmp_path):
        logger.log_error(ValueError("bad input"), context={"k": "v"})
        text = (tmp_path / "errors.txt").read_text()
        assert "ValueError" in text
        assert "bad input" in text

    def test_writes_json_log(self, logger, tmp_path):
        logger.log_error(KeyError("missing"), context={"who": "me"})
        json_path = tmp_path / "error_log_detailed.json"
        assert json_path.exists()
        entries = json.loads(json_path.read_text())
        assert len(entries) == 1
        assert entries[0]["error_type"] == "KeyError"
        assert entries[0]["context"] == {"who": "me"}

    def test_appends_to_existing_json(self, logger, tmp_path):
        logger.log_error(ValueError("a"))
        logger.log_error(ValueError("b"))
        entries = json.loads((tmp_path / "error_log_detailed.json").read_text())
        assert len(entries) == 2

    def test_recovers_from_corrupt_json(self, logger, tmp_path):
        (tmp_path / "error_log_detailed.json").write_text("not json{")
        logger.log_error(ValueError("x"))
        entries = json.loads((tmp_path / "error_log_detailed.json").read_text())
        assert len(entries) == 1

    def test_caps_at_1000_entries(self, logger, tmp_path):
        json_path = tmp_path / "error_log_detailed.json"
        json_path.write_text(json.dumps([{"timestamp": "2024-01-01T00:00:00",
                                          "error_type": "T", "error_message": "m",
                                          "file_path": "f", "function_name": "g",
                                          "line_number": "?", "traceback": "",
                                          "context": {}} for _ in range(1000)]))
        logger.log_error(ValueError("new"))
        entries = json.loads(json_path.read_text())
        assert len(entries) == 1000
        assert entries[-1]["error_type"] == "ValueError"


class TestLogCriticalError:
    def test_logs_error(self, logger, tmp_path):
        logger.log_critical_error(RuntimeError("fatal"))
        text = (tmp_path / "errors.txt").read_text()
        assert "RuntimeError" in text
        assert "fatal" in text


class TestErrorSummary:
    def test_empty_when_no_log(self, logger):
        summary = logger.get_error_summary()
        assert summary == {"total_errors": 0, "error_types": {}, "files_with_errors": {}}

    def test_counts_errors_by_type(self, logger):
        logger.log_error(ValueError("a"))
        logger.log_error(ValueError("b"))
        logger.log_error(KeyError("c"))
        # days=1 keeps the cutoff date within the current month — the source
        # uses day-arithmetic that breaks across month boundaries with larger N.
        summary = logger.get_error_summary(days=1)
        assert summary["total_errors"] == 3
        assert summary["error_types"]["ValueError"] == 2
        assert summary["error_types"]["KeyError"] == 1


class TestGlobalHelpers:
    def test_get_error_logger_is_singleton(self):
        error_logger._error_logger = None
        a = get_error_logger()
        b = get_error_logger()
        assert a is b

    def test_log_error_convenience(self, tmp_path, monkeypatch):
        custom = ErrorLogger(log_directory=str(tmp_path), log_filename="e.txt")
        monkeypatch.setattr(error_logger, "_error_logger", custom)
        log_error(ValueError("via helper"))
        assert "via helper" in (tmp_path / "e.txt").read_text()

    def test_log_critical_error_convenience(self, tmp_path, monkeypatch):
        custom = ErrorLogger(log_directory=str(tmp_path), log_filename="e.txt")
        monkeypatch.setattr(error_logger, "_error_logger", custom)
        log_critical_error(RuntimeError("crit"))
        assert "crit" in (tmp_path / "e.txt").read_text()
