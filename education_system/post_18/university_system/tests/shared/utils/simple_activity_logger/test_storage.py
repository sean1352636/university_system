"""Tests for simple_activity_logger.storage"""
import os
import gzip
import json
import time

from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger.storage import (
    LogRotationManager, DatabaseManager, DatabaseLogger,
)


class TestLogRotationManager:
    def test_should_rotate_false_when_missing(self, tmp_path):
        m = LogRotationManager({"max_file_size": 10})
        assert m.should_rotate(str(tmp_path / "nope.log")) is False

    def test_should_rotate_true_at_size(self, tmp_path):
        f = tmp_path / "a.log"
        f.write_text("x" * 100)
        m = LogRotationManager({"max_file_size": 50})
        assert m.should_rotate(str(f)) is True

    def test_rotate_log_compresses(self, tmp_path):
        f = tmp_path / "a.log"
        f.write_text("hello")
        m = LogRotationManager({"compress_old_logs": True})
        m.rotate_log(str(f))
        gz_files = list(tmp_path.glob("*.gz"))
        assert len(gz_files) == 1
        with gzip.open(gz_files[0], "rb") as fh:
            assert fh.read() == b"hello"

    def test_rotate_without_compress(self, tmp_path):
        f = tmp_path / "a.log"
        f.write_text("hi")
        m = LogRotationManager({"compress_old_logs": False})
        m.rotate_log(str(f))
        rotated = [p for p in tmp_path.glob("*.log") if p.name != "a.log"]
        assert rotated, "expected a rotated .log file"

    def test_rotate_missing_file_returns_path(self, tmp_path):
        path = str(tmp_path / "missing.log")
        m = LogRotationManager({})
        assert m.rotate_log(path) == path

    def test_cleanup_old_logs(self, tmp_path):
        old = tmp_path / "old.log"
        old.write_text("x")
        new = tmp_path / "new.log"
        new.write_text("x")
        os.utime(str(old), (time.time() - 86400 * 60, time.time() - 86400 * 60))
        m = LogRotationManager({"retention_days": 30})
        m.cleanup_old_logs(str(tmp_path))
        assert not old.exists()
        assert new.exists()

    def test_get_log_files_info(self, tmp_path):
        (tmp_path / "a.log").write_text("xx")
        (tmp_path / "b.log.gz").write_text("yy")
        m = LogRotationManager({})
        info = m.get_log_files_info(str(tmp_path))
        names = {i["name"] for i in info}
        assert names == {"a.log", "b.log.gz"}
        compressed = {i["name"]: i["compressed"] for i in info}
        assert compressed["b.log.gz"] is True
        assert compressed["a.log"] is False


class TestDatabaseManager:
    def test_query_update_batch(self, activity_log_db):
        m = DatabaseManager(activity_log_db)
        rows = m.execute_update(
            "INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address) VALUES (?,?,?,?,?,?)",
            ("u", "n", "a", "{}", "2026-05-06 12:00:00", "1.1.1.1"),
        )
        assert rows == 1
        m.execute_batch(
            "INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address) VALUES (?,?,?,?,?,?)",
            [("u2", "n2", "a", "{}", "2026-05-06 12:00:01", "1.1.1.2"),
             ("u3", "n3", "a", "{}", "2026-05-06 12:00:02", "1.1.1.3")],
        )
        results = m.execute_query("SELECT user_id FROM activity_log ORDER BY user_id")
        assert [r["user_id"] for r in results] == ["u", "u2", "u3"]


class TestDatabaseLogger:
    def test_insert_and_query(self, activity_log_db, make_log_entry):
        dl = DatabaseLogger(activity_log_db)
        dl.insert_log(make_log_entry(user_id="u1", action="login"))
        dl.insert_log(make_log_entry(user_id="u2", action="logout"))
        rows = dl.query_logs()
        assert len(rows) == 2
        # details JSON should round-trip
        details = json.loads(rows[0]["details"])
        assert details["module"] == "library"

    def test_insert_batch_logs(self, activity_log_db, make_log_entry):
        dl = DatabaseLogger(activity_log_db)
        dl.insert_batch_logs([make_log_entry(user_id=f"u{i}") for i in range(3)])
        assert dl.get_log_count() == 3

    def test_query_filters(self, activity_log_db, make_log_entry):
        dl = DatabaseLogger(activity_log_db)
        dl.insert_log(make_log_entry(user_id="u1", action="login", timestamp="2026-05-01 10:00:00"))
        dl.insert_log(make_log_entry(user_id="u2", action="logout", timestamp="2026-05-05 10:00:00"))
        # Equality filter
        rows = dl.query_logs({"user_id": "u1"})
        assert len(rows) == 1
        # IN list filter
        rows = dl.query_logs({"action": ["login", "logout"]})
        assert len(rows) == 2
        # Range
        rows = dl.query_logs({"timestamp_from": "2026-05-04 00:00:00"})
        assert len(rows) == 1
        rows = dl.query_logs({"timestamp_to": "2026-05-04 00:00:00"})
        assert len(rows) == 1
        rows = dl.query_logs({"date_from": "2026-05-04", "date_to": "2026-05-10"})
        assert len(rows) == 1

    def test_get_log_count_with_filters(self, activity_log_db, make_log_entry):
        dl = DatabaseLogger(activity_log_db)
        dl.insert_log(make_log_entry(user_id="a"))
        dl.insert_log(make_log_entry(user_id="b"))
        assert dl.get_log_count({"user_id": "a"}) == 1
        assert dl.get_log_count({"user_id": ["a", "b"]}) == 2
        assert dl.get_log_count({"timestamp_from": "1900-01-01"}) == 2

    def test_delete_old_logs(self, activity_log_db, make_log_entry):
        dl = DatabaseLogger(activity_log_db)
        dl.insert_log(make_log_entry(timestamp="2000-01-01 00:00:00"))
        dl.insert_log(make_log_entry(timestamp="2999-01-01 00:00:00"))
        deleted = dl.delete_old_logs(days=1)
        assert deleted == 1
        assert dl.get_log_count() == 1

    def test_get_database_stats(self, activity_log_db, make_log_entry):
        dl = DatabaseLogger(activity_log_db)
        dl.insert_log(make_log_entry())
        stats = dl.get_database_stats()
        assert stats["total_logs"] == 1
        assert stats["database_size"] > 0
        assert "recent_activity" in stats

    def test_database_stats_missing_path(self, activity_log_db, make_log_entry):
        dl = DatabaseLogger(activity_log_db)
        dl.db_path = "/nonexistent/path.db"
        # Should still return a dict; database_size set to 0 on error
        # but get_log_count requires the connection — use real path only
        # Re-point only after counting
        stats = dl.get_database_stats()  # will raise on count via real path
        assert "database_size" in stats

    def test_build_details_with_metadata(self, activity_log_db, make_log_entry):
        dl = DatabaseLogger(activity_log_db)
        entry = make_log_entry(metadata={"x": 1})
        s = dl._build_details(entry)
        parsed = json.loads(s)
        assert parsed["metadata"] == {"x": 1}
        assert parsed["module"] == "library"
