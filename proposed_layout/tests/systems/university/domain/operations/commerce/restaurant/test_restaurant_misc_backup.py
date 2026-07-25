"""
Tests for university_system/modules/core/services/restaurant_misc/backup.py
"""
from __future__ import annotations

import os
import shutil
import tempfile
from io import StringIO
from unittest import mock

import pytest

from education_system.systems.university.domain.operations.commerce.services.restaurant.operations import backup


@pytest.fixture
def temp_db_file():
    """Create a temporary database file"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.write(b'test database content')
    temp_file.close()
    yield temp_file.name
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)


@pytest.fixture
def mock_auth():
    """Mock authentication context"""
    auth = mock.MagicMock()
    auth.current_user = {'id': 'USER001', 'username': 'testuser'}
    auth.check_permission.return_value = True
    return auth


class TestSystemBackup:
    """Tests for system_backup function"""

    def test_system_backup_database_only(self):
        """Test system backup with database only option"""
        with mock.patch('builtins.input', return_value='1'):
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.backup_database') as mock_backup_db:
                with mock.patch('sys.stdout', new=StringIO()):
                    backup.system_backup()

                    mock_backup_db.assert_called_once()

    def test_system_backup_full_system(self):
        """Test system backup with full system option"""
        with mock.patch('builtins.input', return_value='2'):
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.backup_full_system') as mock_backup_full:
                with mock.patch('sys.stdout', new=StringIO()):
                    backup.system_backup()

                    mock_backup_full.assert_called_once()

    def test_system_backup_invalid_type(self):
        """Test system backup with invalid backup type"""
        with mock.patch('builtins.input', return_value='invalid'):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                backup.system_backup()

                output = fake_out.getvalue()
                assert 'Invalid backup type' in output

    def test_system_backup_exception(self):
        """Test system backup when exception occurs"""
        with mock.patch('builtins.input', side_effect=Exception("Test error")):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.logging.error') as mock_log:
                    backup.system_backup()

                    output = fake_out.getvalue()
                    assert 'An error occurred' in output
                    mock_log.assert_called_once()


class TestBackupDatabase:
    """Tests for backup_database function"""

    def test_backup_database_success(self, temp_db_file, mock_auth):
        """Test successful database backup"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.DATABASE_FILE', temp_db_file):
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.ctx') as mock_ctx:
                mock_ctx.auth = mock_auth

                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.log_audit_action') as mock_log:
                    with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                        backup.backup_database()

                        output = fake_out.getvalue()
                        assert 'Database backup created' in output
                        assert 'restaurant_db_backup_' in output

                        mock_log.assert_called_once()
                        log_args = mock_log.call_args[0]
                        assert log_args[0] == 'USER001'
                        assert log_args[1] == 'DATABASE_BACKUP'

        # Clean up backup file
        for file in os.listdir('.'):
            if file.startswith('restaurant_db_backup_'):
                os.unlink(file)

    def test_backup_database_file_not_found(self):
        """Test database backup when database file not found"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.DATABASE_FILE', 'nonexistent.db'):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.logging.error') as mock_log:
                    backup.backup_database()

                    output = fake_out.getvalue()
                    assert 'An error occurred' in output
                    mock_log.assert_called_once()

    def test_backup_database_creates_unique_filename(self, temp_db_file, mock_auth):
        """Test that backup creates unique timestamped filename"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.DATABASE_FILE', temp_db_file):
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.ctx') as mock_ctx:
                mock_ctx.auth = mock_auth

                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.log_audit_action'):
                    with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                        backup.backup_database()

                        output = fake_out.getvalue()
                        # Check for timestamp pattern in filename
                        import re
                        assert re.search(r'restaurant_db_backup_\d{8}_\d{6}\.sql', output)

        # Clean up
        for file in os.listdir('.'):
            if file.startswith('restaurant_db_backup_'):
                os.unlink(file)


class TestBackupFullSystem:
    """Tests for backup_full_system function"""

    def test_backup_full_system_no_auth(self):
        """Test full system backup when not logged in"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.ctx') as mock_ctx:
            mock_ctx.auth = None

            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                backup.backup_full_system()

                output = fake_out.getvalue()
                assert 'You must be logged in' in output

    def test_backup_full_system_no_permission(self, mock_auth):
        """Test full system backup without permission"""
        mock_auth.check_permission.return_value = False

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.ctx') as mock_ctx:
            mock_ctx.auth = mock_auth

            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                backup.backup_full_system()

                output = fake_out.getvalue()
                assert "You don't have permission" in output

    def test_backup_full_system_success(self, temp_db_file, mock_auth):
        """Test successful full system backup"""
        temp_log_dir = tempfile.mkdtemp()

        try:
            # Create a test log file
            log_file = os.path.join(temp_log_dir, 'test.log')
            with open(log_file, 'w') as f:
                f.write('test log content')

            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.DATABASE_FILE', temp_db_file):
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.get_log_file', return_value=log_file):
                    with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.ctx') as mock_ctx:
                        mock_ctx.auth = mock_auth

                        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.log_audit_action') as mock_log:
                            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                                backup.backup_full_system()

                                output = fake_out.getvalue()
                                assert 'Full system backup completed' in output
                                assert 'Backup location:' in output
                                assert 'Backup size:' in output

                                mock_log.assert_called_once()
                                log_args = mock_log.call_args[0]
                                assert log_args[1] == 'FULL_SYSTEM_BACKUP'

            # Clean up backup directory
            for item in os.listdir('.'):
                if item.startswith('restaurant_backup_'):
                    shutil.rmtree(item, ignore_errors=True)

        finally:
            shutil.rmtree(temp_log_dir, ignore_errors=True)

    def test_backup_full_system_creates_manifest(self, temp_db_file, mock_auth):
        """Test that full system backup creates manifest file"""
        temp_log_dir = tempfile.mkdtemp()

        try:
            log_file = os.path.join(temp_log_dir, 'test.log')
            with open(log_file, 'w') as f:
                f.write('test log')

            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.DATABASE_FILE', temp_db_file):
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.get_log_file', return_value=log_file):
                    with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.ctx') as mock_ctx:
                        mock_ctx.auth = mock_auth

                        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.log_audit_action'):
                            with mock.patch('sys.stdout', new=StringIO()):
                                backup.backup_full_system()

                                # Find backup directory
                                backup_dirs = [d for d in os.listdir('.') if d.startswith('restaurant_backup_')]
                                assert len(backup_dirs) > 0

                                backup_dir = backup_dirs[0]
                                manifest_path = os.path.join(backup_dir, 'backup_manifest.txt')
                                assert os.path.exists(manifest_path)

                                # Read and verify manifest content
                                with open(manifest_path, 'r') as f:
                                    manifest_content = f.read()
                                    assert 'Restaurant Management System Backup' in manifest_content
                                    assert 'testuser' in manifest_content
                                    assert 'Full System' in manifest_content

            # Clean up
            for item in os.listdir('.'):
                if item.startswith('restaurant_backup_'):
                    shutil.rmtree(item, ignore_errors=True)

        finally:
            shutil.rmtree(temp_log_dir, ignore_errors=True)

    def test_backup_full_system_exception(self, mock_auth):
        """Test full system backup when exception occurs"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.ctx') as mock_ctx:
            mock_ctx.auth = mock_auth

            with mock.patch('os.makedirs', side_effect=Exception("Test error")):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.logging.error') as mock_log:
                        backup.backup_full_system()

                        output = fake_out.getvalue()
                        assert 'An error occurred during backup' in output
                        mock_log.assert_called_once()

    def test_backup_full_system_calculates_size(self, temp_db_file, mock_auth):
        """Test that full system backup calculates total size"""
        temp_log_dir = tempfile.mkdtemp()

        try:
            log_file = os.path.join(temp_log_dir, 'test.log')
            with open(log_file, 'w') as f:
                f.write('test log content' * 100)  # Write some content

            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.DATABASE_FILE', temp_db_file):
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.get_log_file', return_value=log_file):
                    with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.ctx') as mock_ctx:
                        mock_ctx.auth = mock_auth

                        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.backup.log_audit_action'):
                            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                                backup.backup_full_system()

                                output = fake_out.getvalue()
                                # Check that size is reported in MB
                                assert 'MB' in output

            # Clean up
            for item in os.listdir('.'):
                if item.startswith('restaurant_backup_'):
                    shutil.rmtree(item, ignore_errors=True)

        finally:
            shutil.rmtree(temp_log_dir, ignore_errors=True)
