"""Tests for document_manager.backup (BackupMixin)"""
import os
import zipfile
from unittest.mock import patch, MagicMock

import pytest

from education_system.systems.university.infrastructure.utils.document_manager import (
    backup as backup_mod,
)


@pytest.fixture
def patched_paths(tmp_path, monkeypatch):
    """Redirect the paths the backup code actually reads.

    This used to build a MagicMock carrying ``BACKUP_FILES_DIR`` and
    ``DB_PATH`` — the pre-consolidation unprefixed names. The code reads
    ``UNIVERSITY_BACKUP_FILES_DIR`` and ``UNIVERSITY_DEFAULT_DB_PATH``, and a
    MagicMock answers an unset attribute with a *new* auto-created mock rather
    than failing, so the redirect silently missed and backups were written to a
    directory named after the mock's repr.

    Patching the real module instead means a name that stops existing raises
    AttributeError in the fixture rather than being quietly invented.
    """
    from education_system import paths as real_paths

    archives = tmp_path / "backups"
    db = tmp_path / "uni.db"
    db.write_text("dbcontent")

    monkeypatch.setattr(real_paths, "VAR_DIR", tmp_path)
    monkeypatch.setattr(real_paths, "UNIVERSITY_BACKUP_FILES_DIR", archives)
    monkeypatch.setattr(real_paths, "UNIVERSITY_DEFAULT_DB_PATH", db)
    monkeypatch.setattr(real_paths, "MAINTENANCE_BACKUP_DIR", tmp_path / "maintenance")
    monkeypatch.setattr(backup_mod, "paths", real_paths)

    return type("PatchedPaths", (), {"archives": archives, "db": db})


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
    backups = list((patched_paths.archives).glob("*.zip"))
    assert len(backups) == 1


def test_create_full_backup_handles_exception(doc_manager, monkeypatch, capsys):
    fp = MagicMock()
    type(fp).UNIVERSITY_BACKUP_FILES_DIR = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(backup_mod, "paths", fp)
    doc_manager.create_full_backup()
    assert "error" in capsys.readouterr().out.lower()


def test_restore_from_backup_no_dir(doc_manager, monkeypatch, capsys, tmp_path):
    fp = MagicMock(UNIVERSITY_BACKUP_FILES_DIR=tmp_path / "missing")
    monkeypatch.setattr(backup_mod, "paths", fp)
    doc_manager.restore_from_backup()
    assert "No backup directory" in capsys.readouterr().out


def test_restore_from_backup_no_files(doc_manager, patched_paths, capsys):
    patched_paths.archives.mkdir(exist_ok=True)
    doc_manager.restore_from_backup()
    assert "No backup files" in capsys.readouterr().out


def test_restore_from_backup_invalid_selection(doc_manager, patched_paths, feed_input, capsys):
    patched_paths.archives.mkdir(exist_ok=True)
    z = patched_paths.archives / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    feed_input("99")
    doc_manager.restore_from_backup()
    assert "Invalid selection" in capsys.readouterr().out


def test_restore_from_backup_value_error(doc_manager, patched_paths, feed_input, capsys):
    patched_paths.archives.mkdir(exist_ok=True)
    z = patched_paths.archives / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    feed_input("notanumber")
    doc_manager.restore_from_backup()
    assert "Invalid input" in capsys.readouterr().out


def test_restore_from_backup_cancel(doc_manager, patched_paths, feed_input, capsys):
    patched_paths.archives.mkdir(exist_ok=True)
    z = patched_paths.archives / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    feed_input("1", "no")
    doc_manager.restore_from_backup()
    assert "cancelled" in capsys.readouterr().out.lower()


def test_restore_from_backup_confirms_yes(doc_manager, patched_paths, feed_input, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    patched_paths.archives.mkdir(exist_ok=True)
    z = patched_paths.archives / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "hello")
    feed_input("1", "YES")
    doc_manager.restore_from_backup()


def test_view_backup_history_no_dir(doc_manager, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        backup_mod, "paths",
        MagicMock(UNIVERSITY_BACKUP_FILES_DIR=tmp_path / "nope"),
    )
    doc_manager.view_backup_history()
    assert "No backup directory" in capsys.readouterr().out


def test_view_backup_history_no_files(doc_manager, patched_paths, capsys):
    patched_paths.archives.mkdir(exist_ok=True)
    doc_manager.view_backup_history()
    assert "No backup files" in capsys.readouterr().out


def test_view_backup_history_with_files(doc_manager, patched_paths, capsys):
    patched_paths.archives.mkdir(exist_ok=True)
    z = patched_paths.archives / "b.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    doc_manager.view_backup_history()
    assert "BACKUP HISTORY" in capsys.readouterr().out


def test_schedule_automatic_backup_skipped(doc_manager, feed_input, capsys):
    feed_input("n")
    doc_manager.schedule_automatic_backup()
    assert "scheduling" in capsys.readouterr().out.lower()


def test_schedule_automatic_backup_enabled(doc_manager, feed_input, temp_db, capsys):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    feed_input("y")
    doc_manager.schedule_automatic_backup()
    conn = sqlite3.connect(temp_db)
    val = conn.execute(
        "SELECT setting_value FROM system_settings WHERE setting_name = 'auto_backup_enabled'"
    ).fetchone()
    conn.close()
    assert val[0] == "true"


# ---------------------------------------------------------------------------
# Backup / restore round trip
#
# These patch the real ``paths`` module rather than substituting a MagicMock,
# for two reasons: the prefixed constant names are what the code actually reads
# (a MagicMock silently invents an attribute for a name a fixture forgot to
# set), and ``paths.maintenance_backup_dir`` resolves MAINTENANCE_BACKUP_DIR
# from the module global, so it has to be redirected there to stay off the real
# backup tree.
# ---------------------------------------------------------------------------

DB_MEMBER = "data/university/db_files/student_records.db"


@pytest.fixture
def var_tree(tmp_path, monkeypatch):
    """A self-contained ``var/`` tree with a live database in it."""
    from education_system import paths as real_paths

    var = tmp_path / "var"
    db = var / DB_MEMBER
    db.parent.mkdir(parents=True)
    db.write_bytes(b"ORIGINAL DATABASE")
    archives = var / "backups/university/files"
    archives.mkdir(parents=True)

    monkeypatch.setattr(real_paths, "VAR_DIR", var)
    monkeypatch.setattr(real_paths, "UNIVERSITY_BACKUP_FILES_DIR", archives)
    monkeypatch.setattr(real_paths, "UNIVERSITY_DEFAULT_DB_PATH", db)
    monkeypatch.setattr(real_paths, "MAINTENANCE_BACKUP_DIR", var / "backups/maintenance")
    monkeypatch.setattr(backup_mod, "paths", real_paths)

    return type("VarTree", (), {
        "root": var, "db": db, "archives": archives,
        "maintenance": var / "backups/maintenance",
    })


def _only_archive(var_tree):
    archives = list(var_tree.archives.glob("*.zip"))
    assert len(archives) == 1, archives
    return archives[0]


class TestArchiveLayout:
    def test_members_are_stored_relative_to_var_dir(self, doc_manager, var_tree):
        """An absolute path with no arcname would store `home/<user>/...`.

        Such a member is only restorable by extracting at `/`, so the arcname
        is what makes a restore possible at all.
        """
        doc_manager.create_full_backup()

        with zipfile.ZipFile(_only_archive(var_tree)) as archive:
            assert archive.namelist() == [DB_MEMBER]

    def test_no_member_is_an_absolute_path(self, doc_manager, var_tree):
        doc_manager.create_full_backup()

        with zipfile.ZipFile(_only_archive(var_tree)) as archive:
            for name in archive.namelist():
                assert not name.startswith("/")
                assert not name.startswith("home/")


class TestRoundTrip:
    def test_restore_puts_the_database_back_in_place(
        self, doc_manager, var_tree, feed_input
    ):
        doc_manager.create_full_backup()
        var_tree.db.write_bytes(b"CORRUPTED")

        feed_input("1", "YES")
        doc_manager.restore_from_backup()

        assert var_tree.db.read_bytes() == b"ORIGINAL DATABASE"

    def test_restore_keeps_a_copy_of_what_it_replaced(
        self, doc_manager, var_tree, feed_input
    ):
        """The displaced file must survive, so a wrong restore is recoverable."""
        doc_manager.create_full_backup()
        var_tree.db.write_bytes(b"CORRUPTED")

        feed_input("1", "YES")
        doc_manager.restore_from_backup()

        replaced = list(
            (var_tree.maintenance / "document-manager-restore").glob(f"*/{DB_MEMBER}")
        )
        assert len(replaced) == 1
        assert replaced[0].read_bytes() == b"CORRUPTED"

    def test_restore_removes_its_staging_directory(
        self, doc_manager, var_tree, feed_input
    ):
        doc_manager.create_full_backup()

        feed_input("1", "YES")
        doc_manager.restore_from_backup()

        staging = var_tree.root / ".restore-staging"
        assert not staging.exists() or not list(staging.iterdir())

    def test_restore_reports_success(self, doc_manager, var_tree, feed_input, capsys):
        doc_manager.create_full_backup()

        feed_input("1", "YES")
        doc_manager.restore_from_backup()

        assert "restored successfully" in capsys.readouterr().out.lower()


class TestRestoreRejectsUnsafeArchives:
    def test_zip_slip_member_is_refused(
        self, doc_manager, var_tree, feed_input, capsys
    ):
        """A swapped archive must not write outside the restore root."""
        evil = var_tree.archives / "document_manager_backup_20260101_000000.zip"
        with zipfile.ZipFile(evil, "w") as archive:
            archive.writestr("../../escaped.txt", "pwned")

        feed_input("1", "YES")
        doc_manager.restore_from_backup()

        assert "refused" in capsys.readouterr().out.lower()
        assert not (var_tree.root.parent / "escaped.txt").exists()
        assert var_tree.db.read_bytes() == b"ORIGINAL DATABASE"

    def test_refused_archive_leaves_no_staging_behind(
        self, doc_manager, var_tree, feed_input
    ):
        evil = var_tree.archives / "document_manager_backup_20260101_000000.zip"
        with zipfile.ZipFile(evil, "w") as archive:
            archive.writestr("../../escaped.txt", "pwned")

        feed_input("1", "YES")
        doc_manager.restore_from_backup()

        staging = var_tree.root / ".restore-staging"
        assert not staging.exists() or not list(staging.iterdir())
