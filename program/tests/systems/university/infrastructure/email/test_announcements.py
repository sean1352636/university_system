"""
Comprehensive test suite for email/announcements.py
Tests announcement management, batch sending, permissions, and user interactions
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from education_system.systems.university.infrastructure.email import announcements


class TestSendBatchAnnouncement:
    """Test suite for send_batch_announcement() function"""

    def test_send_batch_announcement_all_students(self):
        """Test sending batch announcement to all students"""
        mock_students = [
            ('S001', 'student1@test.com', 'Mr', 'John', 'A', 'Doe'),
            ('S002', 'student2@test.com', 'Ms', 'Jane', None, 'Smith')
        ]

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('education_system.systems.university.infrastructure.email.announcements.send_bulk') as mock_send_bulk:

            mock_db.return_value = mock_students
            mock_send_bulk.return_value = {'success': 2, 'failure': 0, 'total': 2}

            success, failure, total = announcements.send_batch_announcement(
                'Test Announcement',
                'This is a test message',
                None
            )

            assert success == 2
            assert failure == 0
            assert total == 2

            # Verify send_bulk was called
            assert mock_send_bulk.called
            args, kwargs = mock_send_bulk.call_args
            recipients = args[0]
            template_name = args[1]
            template_vars_list = args[2]

            assert len(recipients) == 2
            assert 'student1@test.com' in recipients
            assert 'student2@test.com' in recipients
            assert template_name == 'general_announcement'
            assert len(template_vars_list) == 2

    def test_send_batch_announcement_filter_by_course(self):
        """Test sending batch announcement filtered by course"""
        mock_students = [
            ('S001', 'student1@test.com', 'Mr', 'John', 'A', 'Doe')
        ]

        filter_criteria = {'course': 'Computer Science'}

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('education_system.systems.university.infrastructure.email.announcements.send_bulk') as mock_send_bulk:

            mock_db.return_value = mock_students
            mock_send_bulk.return_value = {'success': 1, 'failure': 0, 'total': 1}

            success, failure, total = announcements.send_batch_announcement(
                'Course Announcement',
                'CS course update',
                filter_criteria
            )

            assert success == 1
            assert total == 1

            # Verify the database query included course filter
            assert mock_db.called

    def test_send_batch_announcement_filter_by_registration_year(self):
        """Test sending batch announcement filtered by registration year"""
        mock_students = [
            ('S001', 'student1@test.com', 'Mr', 'John', 'A', 'Doe')
        ]

        filter_criteria = {'registration_year': 2023}

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('education_system.systems.university.infrastructure.email.announcements.send_bulk') as mock_send_bulk:

            mock_db.return_value = mock_students
            mock_send_bulk.return_value = {'success': 1, 'failure': 0, 'total': 1}

            success, failure, total = announcements.send_batch_announcement(
                'Year Announcement',
                '2023 student update',
                filter_criteria
            )

            assert success == 1
            assert total == 1

    def test_send_batch_announcement_filter_by_module_code(self):
        """Test sending batch announcement filtered by module code"""
        mock_students = [
            ('S001', 'student1@test.com', 'Mr', 'John', 'A', 'Doe')
        ]

        filter_criteria = {'module_code': 'CS101'}

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('education_system.systems.university.infrastructure.email.announcements.send_bulk') as mock_send_bulk:

            mock_db.return_value = mock_students
            mock_send_bulk.return_value = {'success': 1, 'failure': 0, 'total': 1}

            success, failure, total = announcements.send_batch_announcement(
                'Module Announcement',
                'CS101 update',
                filter_criteria
            )

            assert success == 1

    def test_send_batch_announcement_no_students(self):
        """Test sending batch announcement when no students match criteria"""
        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('education_system.systems.university.infrastructure.email.announcements.send_bulk') as mock_send_bulk:

            mock_db.return_value = []
            mock_send_bulk.return_value = {'success': 0, 'failure': 0, 'total': 0}

            success, failure, total = announcements.send_batch_announcement(
                'Test',
                'Body',
                None
            )

            assert success == 0
            assert total == 0

    def test_send_batch_announcement_handles_none_middle_name(self):
        """Test sending batch announcement handles None middle name correctly"""
        mock_students = [
            ('S001', 'student1@test.com', 'Mr', 'John', None, 'Doe')
        ]

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('education_system.systems.university.infrastructure.email.announcements.send_bulk') as mock_send_bulk:

            mock_db.return_value = mock_students
            mock_send_bulk.return_value = {'success': 1, 'failure': 0, 'total': 1}

            success, failure, total = announcements.send_batch_announcement(
                'Test',
                'Body',
                None
            )

            # Verify template vars list has empty string for middle name
            args, kwargs = mock_send_bulk.call_args
            template_vars_list = args[2]
            assert template_vars_list[0]['middle_name'] == ''

    def test_send_batch_announcement_database_error(self):
        """Test sending batch announcement handles database errors"""
        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            success, failure, total = announcements.send_batch_announcement(
                'Test',
                'Body',
                None
            )

            # Should return (0, 0, 0) on error
            assert success == 0
            assert failure == 0
            assert total == 0

    def test_send_batch_announcement_partial_failure(self):
        """Test sending batch announcement with partial failures"""
        mock_students = [
            ('S001', 'student1@test.com', 'Mr', 'John', 'A', 'Doe'),
            ('S002', 'student2@test.com', 'Ms', 'Jane', None, 'Smith')
        ]

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('education_system.systems.university.infrastructure.email.announcements.send_bulk') as mock_send_bulk:

            mock_db.return_value = mock_students
            mock_send_bulk.return_value = {'success': 1, 'failure': 1, 'total': 2}

            success, failure, total = announcements.send_batch_announcement(
                'Test',
                'Body',
                None
            )

            assert success == 1
            assert failure == 1
            assert total == 2


class TestDisplayAnnouncementsMenu:
    """Test suite for display_announcements_menu() function"""

    def test_display_announcements_menu_view_active_announcements(self):
        """Test viewing active announcements"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'student', 'username': 'testuser', 'id': 1}
        mock_dashboard.get_announcements.return_value = {
            'announcements': [
                {
                    'title': 'Test Announcement',
                    'creator': 'admin',
                    'created_at': '2024-01-01 10:00:00',
                    'is_urgent': False,
                    'is_viewed': True
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['1', '4']), \
             patch('builtins.print') as mock_print:

            announcements.display_announcements_menu(mock_dashboard)

            # Verify get_announcements was called
            assert mock_dashboard.get_announcements.called

    def test_display_announcements_menu_no_announcements(self):
        """Test viewing when no announcements exist"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'student', 'username': 'testuser', 'id': 1}
        mock_dashboard.get_announcements.return_value = {
            'announcements': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }

        with patch('builtins.input', side_effect=['1', '4']), \
             patch('builtins.print') as mock_print:

            announcements.display_announcements_menu(mock_dashboard)

            # Should display "No active announcements" message
            calls = [str(call) for call in mock_print.call_args_list]
            assert any('No active announcements' in str(call) for call in calls)

    def test_display_announcements_menu_create_announcement_permission_denied(self):
        """Test creating announcement without permission"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'student', 'username': 'testuser', 'id': 1}

        with patch('builtins.input', side_effect=['2', '4']), \
             patch('builtins.print') as mock_print:

            announcements.display_announcements_menu(mock_dashboard)

            # Should display permission denied message
            calls = [str(call) for call in mock_print.call_args_list]
            assert any("don't have permission" in str(call) for call in calls)

    def test_display_announcements_menu_create_announcement_success(self):
        """Test creating announcement with proper permissions"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'admin', 'username': 'admin', 'id': 1}
        mock_dashboard.create_announcement.return_value = True

        with patch('builtins.input', side_effect=[
            '2',  # Create new announcement
            'Test Title',  # Title
            'Test line 1',  # Body line 1
            'END',  # End body
            '1',  # All users
            'n',  # Not urgent
            '',  # Start date (empty = now)
            '',  # End date (empty = no end)
            '4'  # Exit
        ]), patch('builtins.print'):

            announcements.display_announcements_menu(mock_dashboard)

            # Verify create_announcement was called
            assert mock_dashboard.create_announcement.called

    def test_display_announcements_menu_create_announcement_empty_title(self):
        """Test creating announcement with empty title"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'admin', 'username': 'admin', 'id': 1}

        with patch('builtins.input', side_effect=[
            '2',  # Create new announcement
            '',  # Empty title
            '4'  # Exit
        ]), patch('builtins.print') as mock_print:

            announcements.display_announcements_menu(mock_dashboard)

            # Should display "Title cannot be empty" message
            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Title cannot be empty' in str(call) for call in calls)

    def test_display_announcements_menu_create_announcement_empty_content(self):
        """Test creating announcement with empty content"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'staff', 'username': 'staff', 'id': 1}

        with patch('builtins.input', side_effect=[
            '2',  # Create new announcement
            'Test Title',  # Title
            'END',  # Empty body
            '4'  # Exit
        ]), patch('builtins.print') as mock_print:

            announcements.display_announcements_menu(mock_dashboard)

            # Should display "Content cannot be empty" message
            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Content cannot be empty' in str(call) for call in calls)

    def test_display_announcements_menu_create_announcement_target_audiences(self):
        """Test creating announcement with different target audiences"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'instructor', 'username': 'instructor', 'id': 1}
        mock_dashboard.create_announcement.return_value = True

        # Test all audience options
        audience_choices = ['1', '2', '3', '4']
        expected_audiences = ['all', 'students', 'staff', 'instructors']

        for choice, expected in zip(audience_choices, expected_audiences):
            with patch('builtins.input', side_effect=[
                '2',  # Create new announcement
                'Test Title',
                'Test body',
                'END',
                choice,  # Audience choice
                'n',  # Not urgent
                '',  # Start date
                '',  # End date
                '4'  # Exit
            ]), patch('builtins.print'):

                announcements.display_announcements_menu(mock_dashboard)

                # Verify the correct audience was passed
                args, kwargs = mock_dashboard.create_announcement.call_args
                assert args[2] == expected

    def test_display_announcements_menu_create_announcement_invalid_date_format(self):
        """Test creating announcement with invalid date format"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'admin', 'username': 'admin', 'id': 1}
        mock_dashboard.create_announcement.return_value = True

        with patch('builtins.input', side_effect=[
            '2',  # Create new announcement
            'Test Title',
            'Test body',
            'END',
            '1',  # All users
            'y',  # Urgent
            'invalid-date',  # Invalid start date
            'also-invalid',  # Invalid end date
            '4'  # Exit
        ]), patch('builtins.print') as mock_print:

            announcements.display_announcements_menu(mock_dashboard)

            # Should handle invalid dates gracefully
            assert mock_dashboard.create_announcement.called

    def test_display_announcements_menu_update_announcement_no_permission(self):
        """Test updating announcement without permission"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'student', 'username': 'student', 'id': 1}

        with patch('builtins.input', side_effect=['3', '4']), \
             patch('builtins.print') as mock_print:

            announcements.display_announcements_menu(mock_dashboard)

            # Should display permission denied message
            calls = [str(call) for call in mock_print.call_args_list]
            assert any("don't have permission" in str(call) for call in calls)

    def test_display_announcements_menu_update_announcement_no_announcements(self):
        """Test updating when user has no announcements"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'admin', 'username': 'admin', 'id': 1}

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('builtins.input', side_effect=['3', '4']), \
             patch('builtins.print') as mock_print:

            mock_db.return_value = []

            announcements.display_announcements_menu(mock_dashboard)

            # Should display "no announcements" message
            calls = [str(call) for call in mock_print.call_args_list]
            assert any("haven't created any announcements" in str(call) for call in calls)

    def test_display_announcements_menu_update_announcement_title(self):
        """Test updating announcement title"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'admin', 'username': 'admin', 'id': 1}
        mock_dashboard._log_communication_action = Mock()

        mock_announcement = (1, 'Old Title', 'Content', 'all', 0, '2024-01-01 10:00:00', None, 1)

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db, \
             patch('builtins.input', side_effect=[
                 '3',  # Update announcement
                 '1',  # Select announcement ID
                 '1',  # Update title
                 'New Title',  # New title
                 'y',  # Confirm
                 '4'  # Exit
             ]), \
             patch('builtins.print'):

            # First call returns list of announcements, second returns selected announcement
            # Third call executes the update
            mock_db.side_effect = [
                [mock_announcement],  # get_user_announcements
                mock_announcement,  # get_announcement
                True  # update_announcement
            ]

            announcements.display_announcements_menu(mock_dashboard)

            # Verify update was attempted
            assert mock_db.call_count == 3

    def test_display_announcements_menu_invalid_choice(self):
        """Test handling invalid menu choice"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'student', 'username': 'testuser', 'id': 1}

        with patch('builtins.input', side_effect=['99', '4']), \
             patch('builtins.print') as mock_print:

            announcements.display_announcements_menu(mock_dashboard)

            # Should display invalid choice message (may be translated)
            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Invalid choice' in str(call) or 'invalid_choice' in str(call).lower() or '無効' in str(call) for call in calls)


class TestCreateAnnouncementSafe:
    """Test suite for create_announcement_safe() function"""

    def test_create_announcement_safe_success(self):
        """Test successful announcement creation"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'admin',
            'username': 'admin'
        }
        mock_dashboard._log_communication_action = Mock()

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db:
            mock_db.return_value = 123  # Announcement ID

            result = announcements.create_announcement_safe(
                mock_dashboard,
                'Test Title',
                'Test Content',
                'all',
                0,
                '2024-01-01 10:00:00',
                '2024-12-31 23:59:59'
            )

            assert result == 123
            assert mock_db.called

    def test_create_announcement_safe_not_logged_in(self):
        """Test creating announcement when not logged in"""
        mock_dashboard = Mock()
        mock_dashboard.auth = None

        result = announcements.create_announcement_safe(
            mock_dashboard,
            'Test Title',
            'Test Content',
            'all'
        )

        assert result is False

    def test_create_announcement_safe_permission_denied(self):
        """Test creating announcement without proper role"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'student',
            'username': 'student'
        }

        result = announcements.create_announcement_safe(
            mock_dashboard,
            'Test Title',
            'Test Content',
            'all'
        )

        assert result is False

    def test_create_announcement_safe_missing_title(self):
        """Test creating announcement with missing title"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'admin',
            'username': 'admin'
        }

        result = announcements.create_announcement_safe(
            mock_dashboard,
            '',
            'Test Content',
            'all'
        )

        assert result is False

    def test_create_announcement_safe_missing_content(self):
        """Test creating announcement with missing content"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'staff',
            'username': 'staff'
        }

        result = announcements.create_announcement_safe(
            mock_dashboard,
            'Test Title',
            '',
            'all'
        )

        assert result is False

    def test_create_announcement_safe_missing_target_audience(self):
        """Test creating announcement with missing target audience"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'instructor',
            'username': 'instructor'
        }

        result = announcements.create_announcement_safe(
            mock_dashboard,
            'Test Title',
            'Test Content',
            None
        )

        assert result is False

    def test_create_announcement_safe_invalid_start_date_format(self):
        """Test creating announcement with invalid start date"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'admin',
            'username': 'admin'
        }

        result = announcements.create_announcement_safe(
            mock_dashboard,
            'Test Title',
            'Test Content',
            'all',
            0,
            'invalid-date'
        )

        assert result is False

    def test_create_announcement_safe_invalid_end_date_format(self):
        """Test creating announcement with invalid end date"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'admin',
            'username': 'admin'
        }

        result = announcements.create_announcement_safe(
            mock_dashboard,
            'Test Title',
            'Test Content',
            'all',
            0,
            '2024-01-01 10:00:00',
            'invalid-date'
        )

        assert result is False

    def test_create_announcement_safe_default_start_date(self):
        """Test creating announcement with default start date"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'admin',
            'username': 'admin'
        }
        mock_dashboard._log_communication_action = Mock()

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db:
            mock_db.return_value = 123

            result = announcements.create_announcement_safe(
                mock_dashboard,
                'Test Title',
                'Test Content',
                'all',
                0,
                None,
                None
            )

            assert result == 123

    def test_create_announcement_safe_database_error(self):
        """Test creating announcement with database error"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {
            'id': 1,
            'role': 'admin',
            'username': 'admin'
        }

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            result = announcements.create_announcement_safe(
                mock_dashboard,
                'Test Title',
                'Test Content',
                'all'
            )

            assert result is False


class TestMarkAnnouncementViewed:
    """Test suite for mark_announcement_viewed() function"""

    def test_mark_announcement_viewed_success(self):
        """Test successfully marking announcement as viewed"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db:
            mock_db.return_value = True

            result = announcements.mark_announcement_viewed(mock_dashboard, 123)

            assert result is True
            assert mock_db.called

    def test_mark_announcement_viewed_not_logged_in(self):
        """Test marking announcement viewed when not logged in"""
        mock_dashboard = Mock()
        mock_dashboard.auth = None

        result = announcements.mark_announcement_viewed(mock_dashboard, 123)

        assert result is False

    def test_mark_announcement_viewed_already_viewed(self):
        """Test marking announcement as viewed when already viewed"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        def mock_operation(func):
            # Simulate cursor finding existing view record
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)  # Record exists
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation', side_effect=mock_operation):
            result = announcements.mark_announcement_viewed(mock_dashboard, 123)

            assert result is True

    def test_mark_announcement_viewed_database_error(self):
        """Test marking announcement viewed with database error"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            result = announcements.mark_announcement_viewed(mock_dashboard, 123)

            assert result is False


class TestGetAnnouncementById:
    """Test suite for get_announcement_by_id() function"""

    def test_get_announcement_by_id_success(self):
        """Test successfully retrieving announcement by ID"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        mock_row = (
            123,  # id
            1,  # creator_id
            'admin',  # creator_username
            'Test Title',  # title
            'Test Content',  # content
            'all',  # target_audience
            1,  # is_urgent
            '2024-01-01 10:00:00',  # start_date
            None,  # end_date
            '2024-01-01 09:00:00',  # created_at
            '2024-01-01 09:00:00',  # updated_at
            1  # is_active
        )

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = mock_row
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation', side_effect=mock_operation):
            result = announcements.get_announcement_by_id(mock_dashboard, 123)

            assert result is not None
            assert result['id'] == 123
            assert result['title'] == 'Test Title'
            assert result['content'] == 'Test Content'
            assert result['is_urgent'] is True
            assert result['is_active'] is True

    def test_get_announcement_by_id_not_found(self):
        """Test retrieving announcement that doesn't exist"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation', side_effect=mock_operation):
            result = announcements.get_announcement_by_id(mock_dashboard, 999)

            assert result is None

    def test_get_announcement_by_id_not_logged_in(self):
        """Test retrieving announcement when not logged in"""
        mock_dashboard = Mock()
        mock_dashboard.auth = None

        result = announcements.get_announcement_by_id(mock_dashboard, 123)

        assert result is None

    def test_get_announcement_by_id_database_error(self):
        """Test retrieving announcement with database error"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            result = announcements.get_announcement_by_id(mock_dashboard, 123)

            assert result is None


class TestDeactivateAnnouncement:
    """Test suite for deactivate_announcement() function"""

    def test_deactivate_announcement_success_as_creator(self):
        """Test deactivating announcement as creator"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1, 'role': 'staff'}
        mock_dashboard._log_communication_action = Mock()

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)  # creator_id = 1
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation', side_effect=mock_operation):
            result = announcements.deactivate_announcement(mock_dashboard, 123)

            assert result is True

    def test_deactivate_announcement_success_as_admin(self):
        """Test deactivating announcement as admin"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 2, 'role': 'admin'}
        mock_dashboard._log_communication_action = Mock()

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)  # creator_id = 1 (different from current user)
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation', side_effect=mock_operation):
            result = announcements.deactivate_announcement(mock_dashboard, 123)

            assert result is True

    def test_deactivate_announcement_permission_denied(self):
        """Test deactivating announcement without permission"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 2, 'role': 'student'}

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)  # creator_id = 1
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation', side_effect=mock_operation):
            result = announcements.deactivate_announcement(mock_dashboard, 123)

            assert result is False

    def test_deactivate_announcement_not_found(self):
        """Test deactivating announcement that doesn't exist"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1, 'role': 'admin'}

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation', side_effect=mock_operation):
            result = announcements.deactivate_announcement(mock_dashboard, 999)

            assert result is False

    def test_deactivate_announcement_not_logged_in(self):
        """Test deactivating announcement when not logged in"""
        mock_dashboard = Mock()
        mock_dashboard.auth = None

        result = announcements.deactivate_announcement(mock_dashboard, 123)

        assert result is False

    def test_deactivate_announcement_database_error(self):
        """Test deactivating announcement with database error"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1, 'role': 'admin'}

        with patch('education_system.systems.university.infrastructure.email.announcements.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            result = announcements.deactivate_announcement(mock_dashboard, 123)

            assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
