"""Tests for shared.security.log_integrity — SecureLogger and verify_log_file."""

import logging

import pytest

from education_system.shared.security.log_integrity import SecureLogger, verify_log_file


@pytest.fixture
def log_file(tmp_path):
    """Return a path for a temporary log file."""
    return str(tmp_path / "secure.log")


SECRET = "test-hmac-secret-key"


def _make_logger(name, log_file):
    """Create a SecureLogger with level set to DEBUG so INFO entries are written."""
    sl = SecureLogger(name, secret_key=SECRET, log_file=log_file)
    sl._logger.setLevel(logging.DEBUG)
    return sl


class TestSecureLogger:
    """Test that SecureLogger writes HMAC-signed entries."""

    def test_info_writes_to_file(self, log_file):
        sl = _make_logger("test.info", log_file)
        sl.info("Test message")
        with open(log_file) as f:
            content = f.read()
        assert "[INFO]" in content
        assert "Test message" in content
        assert "[hmac=" in content

    def test_all_levels(self, log_file):
        sl = _make_logger("test.levels", log_file)
        sl.info("i")
        sl.warning("w")
        sl.error("e")
        sl.critical("c")
        with open(log_file) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 4
        levels_found = {l.split("] [")[1].split("]")[0] for l in lines}
        assert levels_found == {"INFO", "WARNING", "ERROR", "CRITICAL"}


class TestVerifyLogFile:
    """Test verify_log_file detects intact and tampered entries."""

    def test_intact_log_no_tampered(self, log_file):
        sl = _make_logger("test.verify", log_file)
        sl.info("Entry one")
        sl.warning("Entry two")
        sl.error("Entry three")

        tampered = verify_log_file(log_file, secret_key=SECRET)
        assert tampered == []

    def test_tampered_entry_detected(self, log_file):
        sl = _make_logger("test.tamper", log_file)
        sl.info("Original message")
        sl.info("Second message")

        # Tamper with the first line
        with open(log_file) as f:
            lines = f.readlines()

        lines[0] = lines[0].replace("Original message", "ALTERED message")
        with open(log_file, "w") as f:
            f.writelines(lines)

        tampered = verify_log_file(log_file, secret_key=SECRET)
        assert 1 in tampered
        assert 2 not in tampered

    def test_wrong_key_all_tampered(self, log_file):
        sl = _make_logger("test.wrongkey", log_file)
        sl.info("msg1")
        sl.info("msg2")

        tampered = verify_log_file(log_file, secret_key="wrong-key")
        assert len(tampered) == 2

    def test_empty_file(self, tmp_path):
        empty = str(tmp_path / "empty.log")
        with open(empty, "w") as f:
            pass
        assert verify_log_file(empty, secret_key=SECRET) == []
