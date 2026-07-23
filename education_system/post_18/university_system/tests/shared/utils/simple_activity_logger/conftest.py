"""Shared fixtures for simple_activity_logger per-file tests."""
from __future__ import annotations

import os
import tempfile
import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3


def _make_log_entry(**overrides):
    from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger.models import LogEntry
    defaults = dict(
        timestamp="2026-05-06 12:00:00.000",
        user_id="u1",
        username="alice",
        role="user",
        action="read",
        module="library",
        details="some detail",
        status="success",
        log_level="INFO",
        session_id="sess",
        ip_address="127.0.0.1",
        user_agent="ua",
        request_size=0,
        response_size=0,
        processing_time=0.0,
        geolocation={},
        security_level="LOW",
        trace_id="trace",
        stack_trace=None,
        metadata=None,
    )
    defaults.update(overrides)
    return LogEntry(**defaults)


@pytest.fixture
def make_log_entry():
    return _make_log_entry


@pytest.fixture
def activity_log_db(tmp_path):
    """Build a tiny sqlite DB with the activity_log schema."""
    db_path = tmp_path / "activity.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            action TEXT,
            details TEXT,
            timestamp TEXT,
            ip_address TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    return str(db_path)
