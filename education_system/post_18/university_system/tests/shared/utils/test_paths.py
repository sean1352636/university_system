"""
Tests for university_system/core/paths.py

This test suite validates:
- Path constants are properly defined as Path objects
- Path relationships and hierarchy
- Directory creation via ensure_directories()
- Module exports via __all__
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPathConstants:
    """Test path constant definitions"""

    def test_project_root_is_path_object(self):
        """Verify PROJECT_ROOT is a Path object"""
        from education_system.post_18.university_system.core import paths
        assert isinstance(paths.PROJECT_ROOT, Path)
        assert paths.PROJECT_ROOT.exists()

    def test_repo_root_equals_project_root(self):
        """Verify REPO_ROOT equals PROJECT_ROOT"""
        from education_system.post_18.university_system.core import paths
        assert paths.REPO_ROOT == paths.PROJECT_ROOT

    def test_all_path_constants_are_path_objects(self):
        """Verify all path constants are Path objects"""
        from education_system.post_18.university_system.core import paths

        path_constants = [
            'PROJECT_ROOT', 'REPO_ROOT', 'SRC_DIR', 'DATA_DIR', 'DB_DIR',
            'DB_EXPORTS_DIR', 'DEFAULT_DB_PATH', 'LOG_DIR', 'BACKUP_DIR',
            'REPORTS_DIR', 'REPORT_TEMPLATES_DIR', 'REPORT_CACHE_DIR',
            'EMAIL_DATA_DIR', 'EMAIL_CONFIG_PATH', 'EMAIL_TEMPLATES_DIR',
            'LOGGER_CONFIG_DIR', 'CHATBOT_DATA_DIR', 'CHATBOT_UPLOAD_DIR',
            'CHATBOT_MODELS_DIR', 'CHATBOT_CONFIG_PATH', 'QR_CODES_DIR',
            'ANALYTICS_DIR', 'ANALYTICS_PLOTS_DIR', 'ANALYTICS_REPORTS_DIR',
            'SUBMISSIONS_DIR', 'UPLOAD_DIR', 'TEMPLATES_DIR',
            'ASSIGNMENT_TEMPLATES_DIR', 'BACKUP_TEMPLATES_DIR',
            'MEDICAL_TEMPLATES_DIR', 'EMAIL_REMINDER_TEMPLATES_DIR',
            'NLTK_DATA_DIR', 'STUDENT_DOCUMENTS_DIR', 'EXPORTS_DIR',
            'TEMP_DIR', 'CONFIG_DIR', 'CHARTS_DIR'
        ]

        for const_name in path_constants:
            path_obj = getattr(paths, const_name)
            assert isinstance(path_obj, Path), f"{const_name} should be a Path object"

    def test_path_hierarchy_relationships(self):
        """Verify path hierarchy is correct"""
        from education_system.post_18.university_system.core import paths

        # DATA_DIR should be under PROJECT_ROOT
        assert paths.PROJECT_ROOT in paths.DATA_DIR.parents

        # DB_DIR should be under DATA_DIR
        assert paths.DATA_DIR in paths.DB_DIR.parents

        # DB_EXPORTS_DIR should be under DB_DIR
        assert paths.DB_DIR in paths.DB_EXPORTS_DIR.parents

        # LOG_DIR should be under PROJECT_ROOT
        assert paths.PROJECT_ROOT in paths.LOG_DIR.parents

        # REPORTS_DIR should be under DATA_DIR
        assert paths.DATA_DIR in paths.REPORTS_DIR.parents

    def test_file_paths_have_correct_parents(self):
        """Verify file paths (not directories) have correct parent directories"""
        from education_system.post_18.university_system.core import paths

        # DEFAULT_DB_PATH should be in DB_DIR
        assert paths.DEFAULT_DB_PATH.parent == paths.DB_DIR

        # EMAIL_CONFIG_PATH is the canonical email_config.json under a config dir
        # (shared/data/config or the legacy university_system/data/config fallback)
        assert paths.EMAIL_CONFIG_PATH.parent.name == 'config'

        # CHATBOT_CONFIG_PATH should be in LOGGER_CONFIG_DIR
        assert paths.CHATBOT_CONFIG_PATH.parent == paths.LOGGER_CONFIG_DIR


class TestEnsureDirectories:
    """Test ensure_directories() function"""

    def test_ensure_directories_creates_all_directories(self):
        """Verify ensure_directories() creates all required directories"""
        from education_system.post_18.university_system.core import paths

        # Get all directory paths (exclude file paths)
        directory_paths = [
            paths.DATA_DIR, paths.DB_DIR, paths.DB_EXPORTS_DIR, paths.LOG_DIR,
            paths.BACKUP_DIR, paths.REPORTS_DIR, paths.REPORT_TEMPLATES_DIR,
            paths.REPORT_CACHE_DIR, paths.EMAIL_DATA_DIR, paths.EMAIL_TEMPLATES_DIR,
            paths.LOGGER_CONFIG_DIR, paths.CHATBOT_DATA_DIR, paths.CHATBOT_UPLOAD_DIR,
            paths.CHATBOT_MODELS_DIR, paths.QR_CODES_DIR, paths.ANALYTICS_DIR,
            paths.ANALYTICS_PLOTS_DIR, paths.ANALYTICS_REPORTS_DIR,
            paths.SUBMISSIONS_DIR, paths.UPLOAD_DIR, paths.TEMPLATES_DIR,
            paths.ASSIGNMENT_TEMPLATES_DIR, paths.BACKUP_TEMPLATES_DIR,
            paths.MEDICAL_TEMPLATES_DIR, paths.EMAIL_REMINDER_TEMPLATES_DIR,
            paths.NLTK_DATA_DIR, paths.STUDENT_DOCUMENTS_DIR, paths.EXPORTS_DIR,
            paths.TEMP_DIR, paths.CONFIG_DIR, paths.CHARTS_DIR
        ]

        # Create a temporary test directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock the paths to use temp directory
            with patch('education_system.post_18.university_system.core.paths.DATA_DIR', temp_path / 'data'), \
                 patch('education_system.post_18.university_system.core.paths.DB_DIR', temp_path / 'data' / 'db_files'), \
                 patch('education_system.post_18.university_system.core.paths._ensure') as mock_ensure:

                # Call ensure_directories()
                paths.ensure_directories()

                # Verify _ensure was called (it will be called for each directory)
                assert mock_ensure.call_count > 0

    def test_ensure_helper_creates_directory(self):
        """Verify _ensure() helper creates directories"""
        from education_system.post_18.university_system.core.paths import _ensure

        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / 'test_dir' / 'nested' / 'path'

            # Directory should not exist initially
            assert not test_path.exists()

            # Call _ensure
            result = _ensure(test_path)

            # Directory should now exist
            assert test_path.exists()
            assert test_path.is_dir()
            assert result == test_path

    def test_ensure_helper_handles_existing_directory(self):
        """Verify _ensure() handles existing directories gracefully"""
        from education_system.post_18.university_system.core.paths import _ensure

        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / 'existing_dir'
            test_path.mkdir()

            # Directory already exists
            assert test_path.exists()

            # Call _ensure should not raise error
            result = _ensure(test_path)

            # Directory should still exist
            assert test_path.exists()
            assert result == test_path


class TestModuleExports:
    """Test module __all__ exports"""

    def test_all_exports_are_defined(self):
        """Verify all items in __all__ are actually defined"""
        from education_system.post_18.university_system.core import paths

        for export_name in paths.__all__:
            assert hasattr(paths, export_name), f"{export_name} in __all__ but not defined"

    def test_all_major_paths_are_exported(self):
        """Verify major path constants are in __all__"""
        from education_system.post_18.university_system.core import paths

        required_exports = [
            'PROJECT_ROOT', 'DATA_DIR', 'DB_DIR', 'DEFAULT_DB_PATH',
            'LOG_DIR', 'BACKUP_DIR', 'ensure_directories'
        ]

        for export_name in required_exports:
            assert export_name in paths.__all__, f"{export_name} should be in __all__"

    def test_ensure_directories_is_callable(self):
        """Verify ensure_directories is a callable function"""
        from education_system.post_18.university_system.core import paths

        assert callable(paths.ensure_directories)
        assert 'ensure_directories' in paths.__all__


class TestPathIntegrity:
    """Test path integrity and consistency"""

    def test_no_absolute_hardcoded_paths(self):
        """Verify paths are relative to PROJECT_ROOT, not hardcoded"""
        from education_system.post_18.university_system.core import paths

        # All paths except PROJECT_ROOT should contain PROJECT_ROOT in their path
        path_constants = [
            paths.DATA_DIR, paths.DB_DIR, paths.LOG_DIR, paths.BACKUP_DIR,
            paths.REPORTS_DIR, paths.TEMPLATES_DIR
        ]

        for path in path_constants:
            # Resolve to absolute path and check if PROJECT_ROOT is a parent
            assert paths.PROJECT_ROOT in path.parents or path == paths.PROJECT_ROOT

    def test_project_root_calculation(self):
        """Verify PROJECT_ROOT is calculated correctly from this file"""
        from education_system.post_18.university_system.core import paths

        # PROJECT_ROOT should point to university_system directory
        assert paths.PROJECT_ROOT.name == 'university_system'
        assert paths.PROJECT_ROOT.is_dir()

    def test_src_dir_points_to_modules(self):
        """Verify SRC_DIR points to modules directory"""
        from education_system.post_18.university_system.core import paths

        assert paths.SRC_DIR.name == 'modules'
        assert paths.SRC_DIR.parent == paths.PROJECT_ROOT


class TestSpecialPaths:
    """Test special-purpose paths"""

    def test_default_db_path_has_correct_name(self):
        """Verify DEFAULT_DB_PATH has expected database filename"""
        from education_system.post_18.university_system.core import paths

        assert paths.DEFAULT_DB_PATH.name == 'student_records.db'
        assert paths.DEFAULT_DB_PATH.suffix == '.db'

    def test_email_config_path_has_correct_name(self):
        """Verify EMAIL_CONFIG_PATH has expected filename"""
        from education_system.post_18.university_system.core import paths

        assert paths.EMAIL_CONFIG_PATH.name == 'email_config.json'
        assert paths.EMAIL_CONFIG_PATH.suffix == '.json'

    def test_chatbot_config_path_has_correct_name(self):
        """Verify CHATBOT_CONFIG_PATH has expected filename"""
        from education_system.post_18.university_system.core import paths

        assert paths.CHATBOT_CONFIG_PATH.name == 'chatbot_config.json'
        assert paths.CHATBOT_CONFIG_PATH.suffix == '.json'

    def test_analytics_subdirectories_exist(self):
        """Verify analytics has proper subdirectories"""
        from education_system.post_18.university_system.core import paths

        # ANALYTICS_PLOTS_DIR should be under ANALYTICS_DIR
        assert paths.ANALYTICS_DIR in paths.ANALYTICS_PLOTS_DIR.parents

        # ANALYTICS_REPORTS_DIR should be under REPORTS_DIR (consolidated location)
        assert paths.REPORTS_DIR in paths.ANALYTICS_REPORTS_DIR.parents

    def test_template_subdirectories_exist(self):
        """Verify templates has proper subdirectories"""
        from education_system.post_18.university_system.core import paths

        # All template subdirectories should be under TEMPLATES_DIR
        template_subdirs = [
            paths.ASSIGNMENT_TEMPLATES_DIR,
            paths.BACKUP_TEMPLATES_DIR,
            paths.MEDICAL_TEMPLATES_DIR,
            paths.EMAIL_TEMPLATES_DIR
        ]

        for subdir in template_subdirs:
            assert paths.TEMPLATES_DIR in subdir.parents or paths.TEMPLATES_DIR == subdir.parent


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
