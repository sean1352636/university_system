"""Tests for simple_activity_logger.storage."""
import gzip
import os
import time

import pytest

from education_system.university_system.modules.shared.utils.simple_activity_logger.storage import (
    DatabaseLogger,
    DatabaseManager,
    LogRotationManager,
)
from education_system.university_system.modules.shared.utils.simple_activity_logger.models import LogEntry


def _entry(**o):
    base = dict(
        timestamp="2026-05-28 10:00:00.000",
        user_id="u1", username="alice", role="user",
        action="read", module="m", details="d", status="success",
        log_level="INFO", session_id="s", ip_address="1.1.1.1",
        user_agent="UA", request_size=0, response_size=0,
        processing_time=0.0, geolocation={}, security_level="LOW",
        trace_id="t",
    )
    base.update(o)
    return LogEntry(**base)


class TestLogRotationManager:
    def test_should_rotate_false_when_missing(self, tmp_path):
        mgr = LogRotationManager({"max_file_size": 10})
        assert mgr.should_rotate(str(tmp_path / "nope.log")) is False

    def test_should_rotate_true_when_over_max(self, tmp_path):
        f = tmp_path / "f.log"
        f.write_bytes(b"x" * 200)
        mgr = LogRotationManager({"max_file_size": 100})
        assert mgr.should_rotate(str(f)) is True

    def test_should_rotate_false_when_under_max(self, tmp_path):
        f = tmp_path / "f.log"
        f.write_bytes(b"x" * 50)
        mgr = LogRotationManager({"max_file_size": 100})
        assert mgr.should_rotate(str(f)) is False

    def test_rotate_log_no_compress(self, tmp_path):
        f = tmp_path / "f.log"
        f.write_text("data")
        mgr = LogRotationManager({"compress_old_logs": False})
        mgr.rotate_log(str(f))
        rotated = list(tmp_path.glob("f_*.log"))
        assert len(rotated) == 1
        assert not list(tmp_path.glob("*.gz"))

    def test_rotate_log_with_compress(self, tmp_path):
        f = tmp_path / "f.log"
        f.write_text("hello world")
        mgr = LogRotationManager({"compress_old_logs": True})
        mgr.rotate_log(str(f))
        gzs = list(tmp_path.glob("f_*.log.gz"))
        assert len(gzs) == 1
        assert gzip.decompress(gzs[0].read_bytes()) == b"hello world"

    def test_cleanup_old_logs(self, tmp_path):
        old = tmp_path / "old.log"
        new = tmp_path / "new.log"
        old.write_text("o")
        new.write_text("n")
        # Make `old` ancient
        ancient = time.time() - 86400 * 60
        os.utime(old, (ancient, ancient))
        mgr = LogRotationManager({"retention_days": 30})
        mgr.cleanup_old_logs(str(tmp_path))
        assert not old.exists()
        assert new.exists()

    def test_get_log_files_info_sorted(self, tmp_path):
        (tmp_path / "a.log").write_text("a")
        (tmp_path / "b.log.gz").write_text("b")
        info = LogRotationManager({}).get_log_files_info(str(tmp_path))
        names = {i["name"] for i in info}
        assert names == {"a.log", "b.log.gz"}
        gz_entry = next(i for i in info if i["name"] == "b.log.gz")
        assert gz_entry["compressed"] is True


class TestDatabaseManager:
    def test_execute_update_and_query(self, tmp_path):
        db = str(tmp_path / "x.db")
        m = DatabaseManager(db)
        with m.get_connection() as c:
            c.execute("CREATE TABLE t (id INTEGER, name TEXT)")
            c.commit()
        rows_changed = m.execute_update("INSERT INTO t VALUES (?, ?)", (1, "a"))
        assert rows_changed == 1
        rows = m.execute_query("SELECT * FROM t")
        assert rows == [{"id": 1, "name": "a"}]

    def test_execute_batch(self, tmp_path):
        db = str(tmp_path / "x.db")
        m = DatabaseManager(db)
        with m.get_connection() as c:
            c.execute("CREATE TABLE t (id INTEGER)")
            c.commit()
        m.execute_batch("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
        rows = m.execute_query("SELECT id FROM t ORDER BY id")
        assert [r["id"] for r in rows] == [1, 2, 3]


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "activity.db"
    import sqlite3
    conn = sqlite3.connect(str(p))
    conn.execute("""CREATE TABLE activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, username TEXT, action TEXT,
        details TEXT, timestamp TEXT, ip_address TEXT
    )""")
    conn.commit()
    conn.close()
    return str(p)


class TestDatabaseLogger:
    def test_insert_and_query(self, db_path):
        dl = DatabaseLogger(db_path)
        dl.insert_log(_entry())
        rows = dl.query_logs()
        assert len(rows) == 1
        assert rows[0]["username"] == "alice"

    def test_insert_batch(self, db_path):
        dl = DatabaseLogger(db_path)
        dl.insert_batch_logs([_entry(username="a"), _entry(username="b"), _entry(username="c")])
        assert dl.get_log_count() == 3

    def test_query_with_filter(self, db_path):
        dl = DatabaseLogger(db_path)
        dl.insert_log(_entry(username="alice"))
        dl.insert_log(_entry(username="bob"))
        rows = dl.query_logs({"username": "alice"})
        assert len(rows) == 1

    def test_query_with_list_filter(self, db_path):
        dl = DatabaseLogger(db_path)
        dl.insert_log(_entry(username="alice"))
        dl.insert_log(_entry(username="bob"))
        dl.insert_log(_entry(username="charlie"))
        rows = dl.query_logs({"username": ["alice", "bob"]})
        assert {r["username"] for r in rows} == {"alice", "bob"}

    def test_get_database_stats(self, db_path):
        dl = DatabaseLogger(db_path)
        dl.insert_log(_entry())
        stats = dl.get_database_stats()
        assert stats["total_logs"] == 1
        assert stats["database_size"] > 0

    def test_build_details_packs_metadata(self, db_path):
        dl = DatabaseLogger(db_path)
        e = _entry(metadata={"k": "v"})
        details = dl._build_details(e)
        assert '"metadata"' in details
        assert '"role"' in details

    def test_delete_old_logs(self, db_path):
        dl = DatabaseLogger(db_path)
        dl.insert_log(_entry(timestamp="2000-01-01 00:00:00.000"))
        dl.insert_log(_entry(timestamp="2099-01-01 00:00:00.000"))
        removed = dl.delete_old_logs(days=1)
        assert removed == 1
