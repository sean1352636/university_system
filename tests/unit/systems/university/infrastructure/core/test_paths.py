"""Tests for the university section of ``education_system.paths``."""
from pathlib import Path
from unittest.mock import patch

from education_system import paths


class TestStructuralPaths:
    def test_project_root_is_path(self):
        assert isinstance(paths.UNIVERSITY_PROJECT_ROOT, Path)
        assert paths.UNIVERSITY_PROJECT_ROOT.is_absolute()

    def test_aliases_consistent(self):
        assert paths.UNIVERSITY_BASE_DIR == paths.UNIVERSITY_PROJECT_ROOT
        assert paths.UNIVERSITY_SYSTEM_DIR == paths.UNIVERSITY_PROJECT_ROOT
        # PROGRAM_ROOT is the deprecated alias for src/; the repository root is
        # its parent. They stopped being the same directory when the tree moved
        # from program/ to src/ and var/ was lifted to the repository root.
        assert paths.PROGRAM_ROOT == paths.SRC_ROOT
        assert paths.REPO_ROOT == paths.SRC_ROOT.parent

    def test_data_under_var(self):
        # Runtime state lives under <repo>/var (ADR 0018), not in the package.
        assert paths.UNIVERSITY_DATA_DIR.parent == paths.VAR_DIR / "data"
        assert paths.UNIVERSITY_DB_DIR.parent == paths.UNIVERSITY_DATA_DIR
        assert paths.UNIVERSITY_CONFIG_DIR.parent == paths.UNIVERSITY_DATA_DIR

    def test_db_path_under_db_dir(self):
        assert paths.UNIVERSITY_DEFAULT_DB_PATH.parent == paths.UNIVERSITY_DB_DIR
        assert paths.UNIVERSITY_DEFAULT_DB_PATH.name == "student_records.db"

    def test_log_dir_under_var(self):
        assert paths.UNIVERSITY_LOG_DIR.parent == paths.VAR_DIR / "logs"

    def test_backup_subdirs_under_backup(self):
        for sub in (paths.UNIVERSITY_BACKUP_DATABASE_DIR, paths.UNIVERSITY_BACKUP_FILES_DIR,
                    paths.UNIVERSITY_BACKUP_FINANCE_DIR, paths.UNIVERSITY_BACKUP_LIBRARY_DIR):
            assert sub.parent == paths.UNIVERSITY_BACKUP_DIR

    def test_exports_subdirs_under_exports(self):
        for sub in (paths.UNIVERSITY_EXPORTS_PDF_DIR, paths.UNIVERSITY_EXPORTS_TICKETS_DIR,
                    paths.UNIVERSITY_EXPORTS_REPORTS_DIR):
            assert sub.parent == paths.UNIVERSITY_EXPORTS_DIR

    def test_db_backups_alias(self):
        assert paths.UNIVERSITY_DB_BACKUPS_DIR == paths.UNIVERSITY_BACKUP_DATABASE_DIR

    def test_uploads_alias(self):
        assert paths.UNIVERSITY_UPLOADS_DIR == paths.UNIVERSITY_UPLOAD_DIR


class TestEnsureDirectories:
    def test_calls_ensure_for_each_dir(self):
        with patch.object(paths, "_ensure") as mock_ensure:
            paths.ensure_university_directories()
        # Sanity: many directories ensured
        assert mock_ensure.call_count > 20
        # Spot-check a few representative dirs are covered
        called = {call.args[0] for call in mock_ensure.call_args_list}
        assert paths.UNIVERSITY_DATA_DIR in called
        assert paths.UNIVERSITY_LOG_DIR in called
        assert paths.UNIVERSITY_CONFIG_DIR in called


class TestExports:
    def test_all_lists_main_constants(self):
        for key in ("UNIVERSITY_PROJECT_ROOT", "UNIVERSITY_DATA_DIR",
                    "UNIVERSITY_LOG_DIR", "UNIVERSITY_CONFIG_DIR",
                    "UNIVERSITY_DEFAULT_DB_PATH", "ensure_university_directories"):
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
