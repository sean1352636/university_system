"""Tests for document_manager.backup (BackupMixin)"""
import os
import zipfile
from unittest.mock import patch, MagicMock

import pytest

from education_system.post_18.university_system.modules.shared.utils.document_manager import (
    backup as backup_mod,
)


@pytest.fixture
def patched_paths(tmp_path, monkeypatch):
    fake_paths = MagicMock()
    fake_paths.BACKUP_FILES_DIR = tmp_path / "backups"
    fake_paths.DB_PATH = tmp_path / "uni.db"
    (tmp_path / "uni.db").write_text("dbcontent")
    monkeypatch.setattr(backup_mod, "paths", fake_paths)
    return fake_paths


def test_backup_system_dispatch(doc_manager, feed_input):
    for choice, m in zip("12345",
                         ["create_full_backup", "restore_from_backup",
                          "view_backup_history", "schedule_automatic_backup", None]):
        if m is None:
            feed_input(choice)
            doc_manager.backup_system()
            continue
        with patch.object(doc_manager, m) as p:
            feed_input(choice)
            doc_manager.backup_system()
            p.assert_called_once()


def test_create_full_backup_creates_zip(doc_manager, patched_paths, tmp_path):
    doc_manager.create_full_backup()
    backups = list((patched_paths.BACKUP_FILES_DIR).glob("*.zip"))
    assert len(backups) == 1


def test_create_full_backup_handles_exception(doc_manager, monkeypatch, capsys):
    fp = MagicMock()
    type(fp).BACKUP_FILES_DIR = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(backup_mod, "paths", fp)
    doc_manager.create_full_backup()
    assert "error" in capsys.readouterr().out.lower()


def test_restore_from_backup_no_dir(doc_manager, monkeypatch, capsys, tmp_path):
    fp = MagicMock(BACKUP_FILES_DIR=tmp_path / "missing")
    monkeypatch.setattr(backup_mod, "paths", fp)
    doc_manager.restore_from_backup()
    assert "No backup directory" in capsys.readouterr().out


def test_restore_from_backup_no_files(doc_manager, patched_paths, capsys):
    patched_paths.BACKUP_FILES_DIR.mkdir(exist_ok=True)
    doc_manager.restore_from_backup()
    assert "No backup files" in capsys.readouterr().out


def test_restore_from_backup_invalid_selection(doc_manager, patched_paths, feed_input, capsys):
    patched_paths.BACKUP_FILES_DIR.mkdir(exist_ok=True)
    z = patched_paths.BACKUP_FILES_DIR / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    feed_input("99")
    doc_manager.restore_from_backup()
    assert "Invalid selection" in capsys.readouterr().out


def test_restore_from_backup_value_error(doc_manager, patched_paths, feed_input, capsys):
    patched_paths.BACKUP_FILES_DIR.mkdir(exist_ok=True)
    z = patched_paths.BACKUP_FILES_DIR / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    feed_input("notanumber")
    doc_manager.restore_from_backup()
    assert "Invalid input" in capsys.readouterr().out


def test_restore_from_backup_cancel(doc_manager, patched_paths, feed_input, capsys):
    patched_paths.BACKUP_FILES_DIR.mkdir(exist_ok=True)
    z = patched_paths.BACKUP_FILES_DIR / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    feed_input("1", "no")
    doc_manager.restore_from_backup()
    assert "cancelled" in capsys.readouterr().out.lower()


def test_restore_from_backup_confirms_yes(doc_manager, patched_paths, feed_input, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    patched_paths.BACKUP_FILES_DIR.mkdir(exist_ok=True)
    z = patched_paths.BACKUP_FILES_DIR / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "hello")
    feed_input("1", "YES")
    doc_manager.restore_from_backup()


def test_view_backup_history_no_dir(doc_manager, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(backup_mod, "paths", MagicMock(BACKUP_FILES_DIR=tmp_path / "nope"))
    doc_manager.view_backup_history()
    assert "No backup directory" in capsys.readouterr().out


def test_view_backup_history_no_files(doc_manager, patched_paths, capsys):
    patched_paths.BACKUP_FILES_DIR.mkdir(exist_ok=True)
    doc_manager.view_backup_history()
    assert "No backup files" in capsys.readouterr().out


def test_view_backup_history_with_files(doc_manager, patched_paths, capsys):
    patched_paths.BACKUP_FILES_DIR.mkdir(exist_ok=True)
    z = patched_paths.BACKUP_FILES_DIR / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    doc_manager.view_backup_history()
    assert "BACKUP HISTORY" in capsys.readouterr().out


def test_schedule_automatic_backup_skipped(doc_manager, feed_input, capsys):
    feed_input("n")
    doc_manager.schedule_automatic_backup()
    assert "scheduling" in capsys.readouterr().out.lower()


def test_schedule_automatic_backup_enabled(doc_manager, feed_input, temp_db, capsys):
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    feed_input("y")
    doc_manager.schedule_automatic_backup()
    conn = sqlite3.connect(temp_db)
    val = conn.execute(
        "SELECT setting_value FROM system_settings WHERE setting_name = 'auto_backup_enabled'"
    ).fetchone()
    conn.close()
    assert val[0] == "true"
