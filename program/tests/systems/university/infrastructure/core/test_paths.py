"""Tests for university_system.core.paths."""
from pathlib import Path
from unittest.mock import patch

from education_system.systems.university.infrastructure import paths


class TestStructuralPaths:
    def test_project_root_is_path(self):
        assert isinstance(paths.PROJECT_ROOT, Path)
        assert paths.PROJECT_ROOT.is_absolute()

    def test_aliases_consistent(self):
        assert paths.BASE_DIR == paths.PROJECT_ROOT
        assert paths.UNIVERSITY_SYSTEM_DIR == paths.PROJECT_ROOT
        assert paths.REPO_ROOT == paths.PROJECT_ROOT

    def test_data_under_project_root(self):
        assert paths.DATA_DIR.parent == paths.PROJECT_ROOT
        assert paths.DB_DIR.parent == paths.DATA_DIR
        assert paths.CONFIG_DIR.parent == paths.DATA_DIR

    def test_db_path_under_db_dir(self):
        assert paths.DEFAULT_DB_PATH.parent == paths.DB_DIR
        assert paths.DEFAULT_DB_PATH.name == "student_records.db"

    def test_log_dir_under_project_root(self):
        assert paths.LOG_DIR.parent == paths.PROJECT_ROOT

    def test_backup_subdirs_under_backup(self):
        for sub in (paths.BACKUP_DATABASE_DIR, paths.BACKUP_FILES_DIR,
                    paths.BACKUP_FINANCE_DIR, paths.BACKUP_LIBRARY_DIR):
            assert sub.parent == paths.BACKUP_DIR

    def test_exports_subdirs_under_exports(self):
        for sub in (paths.EXPORTS_PDF_DIR, paths.EXPORTS_TICKETS_DIR,
                    paths.EXPORTS_REPORTS_DIR):
            assert sub.parent == paths.EXPORTS_DIR

    def test_db_backups_alias(self):
        assert paths.DB_BACKUPS_DIR == paths.BACKUP_DATABASE_DIR

    def test_uploads_alias(self):
        assert paths.UPLOADS_DIR == paths.UPLOAD_DIR


class TestEnsureDirectories:
    def test_calls_ensure_for_each_dir(self):
        with patch.object(paths, "_ensure") as mock_ensure:
            paths.ensure_directories()
        # Sanity: many directories ensured
        assert mock_ensure.call_count > 20
        # Spot-check a few representative dirs are covered
        called = {call.args[0] for call in mock_ensure.call_args_list}
        assert paths.DATA_DIR in called
        assert paths.LOG_DIR in called
        assert paths.CONFIG_DIR in called


class TestExports:
    def test_all_lists_main_constants(self):
        for key in ("PROJECT_ROOT", "DATA_DIR", "LOG_DIR", "CONFIG_DIR",
                    "DEFAULT_DB_PATH", "ensure_directories"):
            assert key in paths.__all__


class TestEnsureHelper:
    def test_creates_directory(self, tmp_path):
        target = tmp_path / "nested" / "deep"
        result = paths._ensure(target)
        assert result == target
        assert target.is_dir()

    def test_idempotent(self, tmp_path):
        target = tmp_path / "x"
        paths._ensure(target)
        paths._ensure(target)  # must not raise
