"""Retention rule for the ``var/backups/maintenance`` tree.

``maintenance_backup_dir()`` had no pruning until 2026-08-23, by which point 31
snapshots of ``student_records.db`` — all holding the same 24 students and
differing only in which views a campaign had added — accounted for 466MB of a
667MB backup tree. These tests pin the rule that replaced that.

Every test redirects :data:`paths.MAINTENANCE_BACKUP_DIR` at ``tmp_path`` first.
The module-level constant is what the prune resolves against, so without that
redirect these would delete real backups.
"""
from __future__ import annotations

import datetime
import os
import time
from pathlib import Path

import pytest

from education_system import paths


@pytest.fixture
def backup_root(tmp_path, monkeypatch):
    """Point the maintenance tree at a temporary directory."""
    monkeypatch.setattr(paths, "MAINTENANCE_BACKUP_DIR", tmp_path)
    return tmp_path


def make_run(root: Path, label: str, name: str, age_days: int = 0) -> Path:
    """Create ``<label>/<name>`` holding a stand-in database file."""
    run = root / label / name
    run.mkdir(parents=True)
    (run / "student_records.db").write_bytes(b"x" * 16)
    if age_days:
        stamp = time.time() - age_days * 86400
        os.utime(run, (stamp, stamp))
    return run


def names(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


def recent_stamp(days_ago: int) -> str:
    """A run name dated *days_ago* days before today.

    Age is read from the name, so a fixture that needs to look recent must be
    *named* recently — setting mtime alone is not enough.
    """
    day = datetime.date.today() - datetime.timedelta(days=days_ago)
    return day.strftime("%Y%m%d") + "_010000"


class TestKeepNewest:
    def test_newest_keep_runs_survive_regardless_of_age(self, backup_root):
        for day in range(1, 6):
            make_run(backup_root, "camp", f"202601{day:02d}_010000", age_days=200)

        removed = paths.prune_maintenance_backups("camp", keep=3)

        assert names(backup_root / "camp") == [
            "20260103_010000",
            "20260104_010000",
            "20260105_010000",
        ]
        assert len(removed) == 2

    def test_keep_larger_than_run_count_removes_nothing(self, backup_root):
        make_run(backup_root, "camp", "20260101_010000", age_days=200)

        assert paths.prune_maintenance_backups("camp", keep=10) == []
        assert names(backup_root / "camp") == ["20260101_010000"]

    def test_returns_the_directories_it_removed(self, backup_root):
        make_run(backup_root, "camp", "20260101_010000", age_days=200)
        make_run(backup_root, "camp", "20260102_010000", age_days=200)

        removed = paths.prune_maintenance_backups("camp", keep=1, max_age_days=0)

        assert [p.name for p in removed] == ["20260101_010000"]
        assert all(not p.exists() for p in removed)


class TestAgeReprieve:
    def test_recent_runs_beyond_keep_are_not_pruned(self, backup_root):
        for days_ago in range(4):
            make_run(backup_root, "recent", recent_stamp(days_ago))

        removed = paths.prune_maintenance_backups("recent", keep=2, max_age_days=30)

        assert removed == []
        assert len(names(backup_root / "recent")) == 4

    def test_max_age_zero_is_a_strict_keep_n(self, backup_root):
        for days_ago in range(4):
            make_run(backup_root, "recent", recent_stamp(days_ago))

        paths.prune_maintenance_backups("recent", keep=2, max_age_days=0)

        assert len(names(backup_root / "recent")) == 2

    def test_age_comes_from_the_name_not_the_mtime(self, backup_root):
        """A freshly touched file must not look recent to the rule.

        mtime shifts whenever a backup is copied or touched; the name records
        when the snapshot was actually taken, so the name wins.
        """
        old = make_run(backup_root, "camp", "20260101_010000")
        now = time.time()
        os.utime(old, (now, now))
        make_run(backup_root, "camp", recent_stamp(0))

        paths.prune_maintenance_backups("camp", keep=1, max_age_days=30)

        assert names(backup_root / "camp") == [recent_stamp(0)]


class TestOnlyDatedRunDirectories:
    def test_loose_files_and_hand_named_dirs_are_never_touched(self, backup_root):
        make_run(backup_root, "mixed", "20260301_010000", age_days=200)
        make_run(backup_root, "mixed", "20260302_010000", age_days=200)
        (backup_root / "mixed" / "loose-copy.db").write_bytes(b"keep me")
        (backup_root / "mixed" / "hand-named").mkdir()

        paths.prune_maintenance_backups("mixed", keep=0, max_age_days=0)

        assert names(backup_root / "mixed") == ["hand-named", "loose-copy.db"]

    def test_dated_name_without_a_time_part_still_sorts(self, backup_root):
        """Real labels include forms like ``20260815_pre_seed``."""
        make_run(backup_root, "odd", "20260401_pre_seed", age_days=200)
        make_run(backup_root, "odd", "20260402_120000", age_days=200)

        paths.prune_maintenance_backups("odd", keep=1, max_age_days=0)

        assert names(backup_root / "odd") == ["20260402_120000"]


class TestGuards:
    def test_exclude_survives_even_at_keep_zero(self, backup_root):
        run = make_run(backup_root, "excl", "20260501_010000", age_days=200)

        paths.prune_maintenance_backups(
            "excl", keep=0, max_age_days=0, exclude=run
        )

        assert run.exists()

    def test_dry_run_reports_without_deleting(self, backup_root):
        make_run(backup_root, "dry", "20260601_010000", age_days=200)
        make_run(backup_root, "dry", "20260602_010000", age_days=200)

        removed = paths.prune_maintenance_backups(
            "dry", keep=1, max_age_days=0, dry_run=True
        )

        assert [p.name for p in removed] == ["20260601_010000"]
        assert len(names(backup_root / "dry")) == 2

    def test_missing_label_is_not_an_error(self, backup_root):
        assert paths.prune_maintenance_backups("never-existed") == []

    @pytest.mark.parametrize(
        "label", ["../../data", "..", ".", "", "a/b", "a\\b", "/etc"]
    )
    def test_label_escaping_the_tree_is_refused(self, backup_root, label):
        with pytest.raises(ValueError, match="escapes the backup tree"):
            paths.prune_maintenance_backups(label)


class TestMaintenanceBackupDir:
    def test_default_call_creates_and_deletes_nothing(self, backup_root):
        """The bare call is a pure path computation.

        Two callers use it only to *locate* a backup, so a lookup must never
        have a filesystem side effect.
        """
        for day in range(1, 5):
            make_run(backup_root, "wired", f"202607{day:02d}_010000", age_days=200)
        before = names(backup_root / "wired")

        target = paths.maintenance_backup_dir("wired", "20260706_010000")

        assert not target.exists()
        assert names(backup_root / "wired") == before

    def test_create_makes_the_directory_and_prunes(self, backup_root):
        for day in range(1, 5):
            make_run(backup_root, "wired", f"202607{day:02d}_010000", age_days=200)

        target = paths.maintenance_backup_dir(
            "wired", "20260705_010000", create=True
        )

        assert target.exists()
        assert names(backup_root / "wired") == [
            "20260703_010000",
            "20260704_010000",
            "20260705_010000",
        ]

    def test_the_run_being_created_is_never_pruned(self, backup_root):
        """Even when the fresh run alone would exceed the retention budget."""
        target = paths.maintenance_backup_dir(
            "fresh", "20260101_010000", create=True
        )

        assert target.exists()

    def test_prune_can_be_forced_off_for_a_created_run(self, backup_root):
        for day in range(1, 5):
            make_run(backup_root, "wired", f"202607{day:02d}_010000", age_days=200)

        paths.maintenance_backup_dir(
            "wired", "20260705_010000", create=True, prune=False
        )

        assert len(names(backup_root / "wired")) == 5

    def test_timestamp_defaults_to_now(self, backup_root):
        target = paths.maintenance_backup_dir("camp")

        assert target.parent == backup_root / "camp"
        assert datetime.datetime.strptime(target.name, "%Y%m%d_%H%M%S")
