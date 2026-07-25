"""Secure logging with HMAC signatures for tamper detection."""

import hashlib
import hmac
import logging
import os
import time


class SecureLogger:
    """Logger that appends HMAC signatures to each log entry."""

    def __init__(self, name, secret_key=None, log_file=None):
        self._secret = (secret_key or os.environ.get("LOG_HMAC_KEY", "default-log-key")).encode()
        self._logger = logging.getLogger(name)
        if log_file:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)

    def _sign(self, message):
        return hmac.new(self._secret, message.encode(), hashlib.sha256).hexdigest()[:16]

    def _log(self, level, message):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry = f"[{timestamp}] [{level}] {message}"
        sig = self._sign(entry)
        self._logger.log(getattr(logging, level), f"{entry} [hmac={sig}]")

    def info(self, message):
        self._log("INFO", message)

    def warning(self, message):
        self._log("WARNING", message)

    def error(self, message):
        self._log("ERROR", message)

    def critical(self, message):
        self._log("CRITICAL", message)


def verify_log_file(filepath, secret_key=None):
    """Verify integrity of a log file. Returns list of tampered line numbers."""
    secret = (secret_key or os.environ.get("LOG_HMAC_KEY", "default-log-key")).encode()
    tampered = []
    with open(filepath) as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip()
            if " [hmac=" not in line:
                continue
            idx = line.rfind(" [hmac=")
            entry = line[:idx]
            sig = line[idx + 7:-1]
            expected = hmac.new(secret, entry.encode(), hashlib.sha256).hexdigest()[:16]
            if not hmac.compare_digest(sig, expected):
                tampered.append(line_num)
    return tampered
