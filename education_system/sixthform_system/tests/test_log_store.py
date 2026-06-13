"""Tests for ``education_system.sixthform_system.core.log_store``."""

from __future__ import annotations

import importlib
import logging
import sqlite3

import pytest


@pytest.fixture
def fresh_log_store(tmp_path, monkeypatch):
    """Point ``log_store`` at a fresh SQLite file and reset module state."""
    from education_system.sixthform_system.core import log_store, paths

    db_path = tmp_path / "logs.db"
    monkeypatch.setattr(paths, "SYSTEM_LOGS_DB", db_path)
    monkeypatch.setattr(log_store, "DB_PATH", db_path)
    monkeypatch.setattr(log_store, "_DB_READY", False)
    monkeypatch.setattr(log_store, "_INSTALLED", False)

    # Strip any handlers added by a previous test so install() is fresh.
    target = logging.getLogger("test.sixthform.logstore")
    for h in list(target.handlers):
        target.removeHandler(h)
    yield log_store
    for h in list(target.handlers):
        target.removeHandler(h)


def test_init_db_creates_schema_and_is_idempotent(fresh_log_store):
    fresh_log_store.init_db()
    fresh_log_store.init_db()  # second call is a no-op
    with sqlite3.connect(str(fresh_log_store.DB_PATH)) as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='system_logs'")
        assert cur.fetchone() is not None


def test_count_logs_empty(fresh_log_store):
    assert fresh_log_store.count_logs() == 0


def test_install_attaches_handler_once(fresh_log_store):
    logger = "test.sixthform.logstore"
    h1 = fresh_log_store.install(logger_name=logger)
    h2 = fresh_log_store.install(logger_name=logger)
    assert h1 is h2
    assert fresh_log_store.is_installed() is True
    target = logging.getLogger(logger)
    sqlite_handlers = [
        h for h in target.handlers
        if isinstance(h, fresh_log_store.SqliteLogHandler)
    ]
    assert len(sqlite_handlers) == 1


def test_emit_records_basic_log(fresh_log_store):
    logger_name = "test.sixthform.logstore"
    fresh_log_store.install(logger_name=logger_name, level=logging.DEBUG)
    log = logging.getLogger(logger_name)
    log.info("hello world")

    rows = fresh_log_store.list_logs()
    assert len(rows) == 1
    row = rows[0]
    assert row.level == "INFO"
    assert row.level_no == logging.INFO
    assert row.logger_name == logger_name
    assert row.message == "hello world"
    assert row.student_id is None
    assert row.exc_text is None


def test_emit_extracts_student_id_from_message(fresh_log_store):
    logger_name = "test.sixthform.logstore"
    fresh_log_store.install(logger_name=logger_name)
    log = logging.getLogger(logger_name)
    log.info("updated record for C1234567 today")
    rows = fresh_log_store.list_logs()
    assert rows[0].student_id == "C1234567"


def test_emit_prefers_explicit_student_id(fresh_log_store):
    logger_name = "test.sixthform.logstore"
    fresh_log_store.install(logger_name=logger_name)
    log = logging.getLogger(logger_name)
    log.info(
        "C9999999 appears in the message",
        extra={"student_id": "C0000001"},
    )
    rows = fresh_log_store.list_logs()
    assert rows[0].student_id == "C0000001"


def test_emit_does_not_pick_up_unrelated_c_prefixed_strings(fresh_log_store):
    logger_name = "test.sixthform.logstore"
    fresh_log_store.install(logger_name=logger_name)
    log = logging.getLogger(logger_name)
    log.info("CONFIG=ok C123 short and CABCDEFG letters")
    rows = fresh_log_store.list_logs()
    assert rows[0].student_id is None


def test_emit_captures_exception_traceback(fresh_log_store):
    logger_name = "test.sixthform.logstore"
    fresh_log_store.install(logger_name=logger_name)
    log = logging.getLogger(logger_name)
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("something broke")
    rows = fresh_log_store.list_logs()
    assert rows[0].level == "ERROR"
    assert rows[0].exc_text and "ValueError: boom" in rows[0].exc_text


def test_emit_swallows_database_errors(fresh_log_store, monkeypatch):
    """If the DB cannot be opened the handler must not raise."""
    logger_name = "test.sixthform.logstore"
    handler = fresh_log_store.install(logger_name=logger_name)
    # Point DB_PATH at a directory so ``sqlite3.connect`` raises.
    monkeypatch.setattr(fresh_log_store, "DB_PATH", fresh_log_store.DB_PATH.parent)
    monkeypatch.setattr(fresh_log_store, "_DB_READY", False)
    rec = logging.LogRecord(
        logger_name, logging.INFO, __file__, 1, "msg", None, None)
    # Must not raise.
    handler.emit(rec)


def test_emit_retries_on_locked_then_succeeds(fresh_log_store, monkeypatch):
    logger_name = "test.sixthform.logstore"
    handler = fresh_log_store.install(logger_name=logger_name)
    # Make sure init_db has run with the *real* _connect so we can swap
    # _connect for an INSERT-failing variant safely below.
    fresh_log_store.init_db()

    real_connect = fresh_log_store._connect
    calls = {"n": 0}

    class FailingThenWorkingConn:
        def __init__(self, real):
            self._real = real
        def __enter__(self):
            self._real.__enter__()
            return self
        def __exit__(self, *a):
            return self._real.__exit__(*a)
        def execute(self, sql, params=()):
            calls["n"] += 1
            if calls["n"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return self._real.execute(sql, params)
        def executescript(self, sql):
            return self._real.executescript(sql)
        def commit(self):
            return self._real.commit()

    def fake_connect():
        return FailingThenWorkingConn(real_connect())

    monkeypatch.setattr(fresh_log_store, "_connect", fake_connect)
    monkeypatch.setattr(
        fresh_log_store.SqliteLogHandler, "_RETRY_DELAYS", (0.0, 0.0))

    log = logging.getLogger(logger_name)
    log.info("retried message")
    rows = fresh_log_store.list_logs()
    assert any(r.message == "retried message" for r in rows)


def test_emit_reraises_non_locked_operational_error(fresh_log_store, monkeypatch):
    logger_name = "test.sixthform.logstore"
    handler = fresh_log_store.install(logger_name=logger_name)
    fresh_log_store.init_db()

    class BadConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw):
            raise sqlite3.OperationalError("no such table")
        def commit(self): pass

    monkeypatch.setattr(fresh_log_store, "_connect", lambda: BadConn())
    rec = logging.LogRecord(
        logger_name, logging.INFO, __file__, 1, "msg", None, None)
    # ``handleError`` should swallow the re-raised error rather than
    # propagating it.
    handler.emit(rec)


def test_list_logs_filters(fresh_log_store):
    logger_name = "test.sixthform.logstore"
    fresh_log_store.install(logger_name=logger_name)
    log = logging.getLogger(logger_name)
    log.debug("debug-msg")
    log.info("info-msg about C1234567")
    log.warning("warn-msg about C7654321")
    log.error("err-msg")

    assert len(fresh_log_store.list_logs(level="INFO")) == 1
    assert len(fresh_log_store.list_logs(min_level_no=logging.WARNING)) == 2
    assert len(fresh_log_store.list_logs(student_id="C1234567")) == 1
    assert (len(fresh_log_store.list_logs(logger_name_like="sixthform"))
            == 4)
    assert len(fresh_log_store.list_logs(limit=2)) == 2


def test_list_logs_ts_window(fresh_log_store):
    fresh_log_store.init_db()
    with sqlite3.connect(str(fresh_log_store.DB_PATH)) as conn:
        conn.executemany(
            "INSERT INTO system_logs (ts, level, level_no, logger_name, "
            "message) VALUES (?, ?, ?, ?, ?)",
            [
                ("2024-01-01 00:00:00", "INFO", 20, "x", "old"),
                ("2025-06-01 00:00:00", "INFO", 20, "x", "mid"),
                ("2030-01-01 00:00:00", "INFO", 20, "x", "future"),
            ],
        )
        conn.commit()

    rows = fresh_log_store.list_logs(since="2025-01-01")
    msgs = {r.message for r in rows}
    assert "old" not in msgs and "mid" in msgs and "future" in msgs

    rows = fresh_log_store.list_logs(until="2025-12-31")
    msgs = {r.message for r in rows}
    assert "old" in msgs and "mid" in msgs and "future" not in msgs


def test_count_logs_reflects_inserts(fresh_log_store):
    logger_name = "test.sixthform.logstore"
    fresh_log_store.install(logger_name=logger_name)
    log = logging.getLogger(logger_name)
    for i in range(3):
        log.info("entry %d", i)
    assert fresh_log_store.count_logs() == 3


def test_purge_before_removes_older_rows(fresh_log_store):
    fresh_log_store.init_db()
    with sqlite3.connect(str(fresh_log_store.DB_PATH)) as conn:
        conn.executemany(
            "INSERT INTO system_logs (ts, level, level_no, logger_name, "
            "message) VALUES (?, ?, ?, ?, ?)",
            [
                ("2024-01-01 00:00:00", "INFO", 20, "x", "old1"),
                ("2024-06-01 00:00:00", "INFO", 20, "x", "old2"),
                ("2026-01-01 00:00:00", "INFO", 20, "x", "fresh"),
            ],
        )
        conn.commit()

    removed = fresh_log_store.purge_before("2025-01-01")
    assert removed == 2
    rows = fresh_log_store.list_logs()
    assert len(rows) == 1 and rows[0].message == "fresh"
    # Re-running purges nothing.
    assert fresh_log_store.purge_before("2025-01-01") == 0


def test_is_installed_starts_false(fresh_log_store):
    assert fresh_log_store.is_installed() is False
    fresh_log_store.install(logger_name="test.sixthform.logstore")
    assert fresh_log_store.is_installed() is True


def test_logrow_dataclass_fields(fresh_log_store):
    logger_name = "test.sixthform.logstore"
    fresh_log_store.install(logger_name=logger_name)
    logging.getLogger(logger_name).info("one")
    (row,) = fresh_log_store.list_logs()
    for field in (
        "log_id", "ts", "level", "level_no", "logger_name", "module",
        "func_name", "line_no", "message", "student_id", "extra_json",
        "exc_text",
    ):
        assert hasattr(row, field)
