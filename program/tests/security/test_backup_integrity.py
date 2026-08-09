"""Backups must be integrity-protected and restore must refuse tampered data.

Covers tasks 7 and 19.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

pytestmark = pytest.mark.security


def _mod():
    from education_system.platform.kernel.backup import backup_manager
    return backup_manager


def _make_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES ('secret')")
    conn.commit()
    conn.close()


def test_encrypt_without_key_fails_closed(tmp_path, as_production):
    mod = _mod()
    db = tmp_path / "app.db"
    _make_db(db)
    with as_production(BACKUP_ENCRYPTION_KEY=None, ENCRYPTION_KEY=None):
        with pytest.raises(RuntimeError):
            mod.backup(str(db), str(tmp_path / "backups"), encrypt=True)
    # And no plaintext backup was left behind.
    left = list((tmp_path / "backups").glob("*")) if (tmp_path / "backups").exists() else []
    assert not any(p.suffix in (".db", ".gz") for p in left), "plaintext backup leaked on failure"


def test_signed_metadata_and_tamper_detection(tmp_path):
    mod = _mod()
    db = tmp_path / "app.db"
    _make_db(db)
    key = "unit-test-integrity-key"
    os.environ["BACKUP_INTEGRITY_KEY"] = key
    try:
        path = mod.backup(str(db), str(tmp_path / "backups"), compress=False)
        assert mod.verify_backup(path)["valid"] is True
        # Tamper with the backup bytes; verification must now fail.
        with open(path, "ab") as f:
            f.write(b"tampered")
        assert mod.verify_backup(path)["valid"] is False
    finally:
        os.environ.pop("BACKUP_INTEGRITY_KEY", None)


def test_restore_refuses_tampered_backup(tmp_path):
    mod = _mod()
    db = tmp_path / "app.db"
    _make_db(db)
    os.environ["BACKUP_INTEGRITY_KEY"] = "k"
    try:
        path = mod.backup(str(db), str(tmp_path / "backups"), compress=False)
        with open(path, "ab") as f:
            f.write(b"x")
        with pytest.raises(ValueError, match="integrity"):
            mod.restore(path, str(tmp_path / "restored.db"))
    finally:
        os.environ.pop("BACKUP_INTEGRITY_KEY", None)
