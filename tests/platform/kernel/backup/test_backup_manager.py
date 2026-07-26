"""Tests for backup_manager (backup, restore, verify, list, cleanup)."""

import os
import sqlite3
import time
import pytest


@pytest.fixture
def source_db(tmp_path):
    """Create a test SQLite DB with a table and sample data."""
    db_path = str(tmp_path / "source.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, grade TEXT)")
    conn.execute("INSERT INTO students VALUES (1, 'Alice', 'A')")
    conn.execute("INSERT INTO students VALUES (2, 'Bob', 'B')")
    conn.execute("INSERT INTO students VALUES (3, 'Charlie', 'C')")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def backup_dir(tmp_path):
    d = str(tmp_path / "backups")
    os.makedirs(d)
    return d


class TestBackup:
    def test_backup_compressed(self, source_db, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup
        path = backup(source_db, backup_dir, compress=True)
        assert os.path.exists(path)
        assert path.endswith(".db.gz")

    def test_backup_uncompressed(self, source_db, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup
        path = backup(source_db, backup_dir, compress=False)
        assert os.path.exists(path)
        assert path.endswith(".db")
        assert not path.endswith(".gz")

    def test_backup_with_label(self, source_db, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup
        path = backup(source_db, backup_dir, compress=False, label="nightly")
        assert "_nightly_" in os.path.basename(path)

    def test_backup_creates_metadata(self, source_db, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup
        path = backup(source_db, backup_dir)
        meta_path = path + ".meta.json"
        assert os.path.exists(meta_path)

    def test_backup_missing_db_raises(self, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup
        with pytest.raises(FileNotFoundError):
            backup("/nonexistent/path.db", backup_dir)


class TestVerify:
    def test_verify_valid_backup(self, source_db, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup, verify_backup
        path = backup(source_db, backup_dir)
        result = verify_backup(path)
        assert result["valid"] is True
        assert result["expected"] == result["actual"]

    def test_verify_no_metadata(self, tmp_path):
        from education_system.platform.kernel.backup.backup_manager import verify_backup
        fake = str(tmp_path / "fake.db")
        with open(fake, "wb") as f:
            f.write(b"data")
        result = verify_backup(fake)
        assert result["valid"] is False


class TestRestore:
    def test_roundtrip_compressed(self, source_db, backup_dir, tmp_path):
        from education_system.platform.kernel.backup.backup_manager import backup, restore
        bk_path = backup(source_db, backup_dir, compress=True)
        restore_path = str(tmp_path / "restored.db")
        restore(bk_path, restore_path)
        conn = sqlite3.connect(restore_path)
        rows = conn.execute("SELECT * FROM students ORDER BY id").fetchall()
        conn.close()
        assert len(rows) == 3
        assert rows[0] == (1, "Alice", "A")
        assert rows[2] == (3, "Charlie", "C")

    def test_roundtrip_uncompressed(self, source_db, backup_dir, tmp_path):
        from education_system.platform.kernel.backup.backup_manager import backup, restore
        bk_path = backup(source_db, backup_dir, compress=False)
        restore_path = str(tmp_path / "restored.db")
        restore(bk_path, restore_path)
        conn = sqlite3.connect(restore_path)
        rows = conn.execute("SELECT name FROM students WHERE id = 2").fetchall()
        conn.close()
        assert rows[0][0] == "Bob"

    def test_restore_creates_pre_restore_copy(self, source_db, backup_dir, tmp_path):
        from education_system.platform.kernel.backup.backup_manager import backup, restore
        bk_path = backup(source_db, backup_dir, compress=False)
        target = str(tmp_path / "existing.db")
        # Create an existing file at the target
        with open(target, "w") as f:
            f.write("old")
        restore(bk_path, target)
        assert os.path.exists(target + ".pre_restore")


class TestListBackups:
    def test_list_backups(self, source_db, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup, list_backups
        backup(source_db, backup_dir, compress=True, label="a")
        backup(source_db, backup_dir, compress=False, label="b")
        backups = list_backups(backup_dir)
        assert len(backups) == 2
        assert all("filename" in b for b in backups)

    def test_list_empty_dir(self, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import list_backups
        assert list_backups(backup_dir) == []

    def test_list_nonexistent_dir(self):
        from education_system.platform.kernel.backup.backup_manager import list_backups
        assert list_backups("/nonexistent/dir") == []


class TestCleanup:
    def test_cleanup_old_backups(self, source_db, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup, cleanup_old_backups
        path = backup(source_db, backup_dir, compress=False)
        # Set mtime to 60 days ago
        old_time = time.time() - (60 * 86400)
        os.utime(path, (old_time, old_time))
        meta = path + ".meta.json"
        if os.path.exists(meta):
            os.utime(meta, (old_time, old_time))
        removed = cleanup_old_backups(backup_dir, retention_days=30)
        assert removed >= 1

    def test_cleanup_keeps_recent(self, source_db, backup_dir):
        from education_system.platform.kernel.backup.backup_manager import backup, cleanup_old_backups
        backup(source_db, backup_dir, compress=False)
        removed = cleanup_old_backups(backup_dir, retention_days=30)
        assert removed == 0
