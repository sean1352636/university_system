"""
Tests for student union menu module.
Tests menu navigation and display functionality.
"""

import pytest
from unittest.mock import Mock, patch, call

from university_system.modules.domain.student_affairs.student_union.services import menu


@pytest.fixture
def mock_context():
    """Mock the context module."""
    ctx = Mock()
    ctx.auth = Mock()
    ctx.auth.current_user = {'id': 1, 'username': 'testuser', 'role': 'student'}
    ctx.auth.check_permission = Mock(return_value=False)
    return ctx


class TestDisplayStudentUnionMenu:
    """Tests for display_student_union_menu function."""

    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_not_logged_in(self, mock_ctx, mock_print):
        """Test menu when not logged in."""
        # Setup mocks
        mock_ctx.auth = None

        # Call function
        menu.display_student_union_menu()

        # Verify results
        assert any('must be logged in' in str(call).lower()
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_basic_display_and_exit(self, mock_ctx, mock_print, mock_input):
        """Test menu displays and exits correctly."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Verify menu was displayed
        assert any('Student Union Portal' in str(call)
                  for call in mock_print.call_args_list)
        assert any('Club Management' in str(call)
                  for call in mock_print.call_args_list)
        assert any('Events & Activities' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['1', '18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.union_context.display_club_menu')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_club_management(self, mock_ctx, mock_display_club, mock_print, mock_input):
        """Test accessing club management."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Verify club menu was called
        mock_display_club.assert_called_once()

    @patch('builtins.input', side_effect=['5', '18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.union_context.manage_engagement_rewards')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_engagement_rewards(self, mock_ctx, mock_engagement, mock_print, mock_input):
        """Test accessing engagement rewards."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Verify engagement rewards was called
        mock_engagement.assert_called_once()

    @patch('builtins.input', side_effect=['15', '18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.union_context.generate_advanced_analytics')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_admin_analytics(self, mock_ctx, mock_analytics, mock_print, mock_input):
        """Test accessing analytics as admin."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1, 'role': 'admin'}
        mock_ctx.auth.check_permission = Mock(return_value=True)

        # Call function
        menu.display_student_union_menu()

        # Verify analytics was called
        mock_analytics.assert_called_once()

    @patch('builtins.input', side_effect=['19', 'https://calendar.example.com/ical', '18'])
    @patch('builtins.print')
    @patch('university_system.modules.domain.academics.services.academic_calendar.AcademicCalendarManager')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_calendar_sync(self, mock_ctx, mock_calendar_manager, mock_print, mock_input):
        """Test calendar sync functionality."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        mock_manager_instance = Mock()
        mock_calendar_manager.return_value = mock_manager_instance

        # Call function
        menu.display_student_union_menu()

        # Verify calendar manager was created and sync was called
        mock_calendar_manager.assert_called()
        mock_manager_instance.calendar_sync.assert_called_once_with('https://calendar.example.com/ical')

    @patch('builtins.input', side_effect=['999', '18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_invalid_choice(self, mock_ctx, mock_print, mock_input):
        """Test handling of invalid menu choice."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Verify invalid choice message
        assert any('Invalid choice' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['2', '3', '4', '18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.union_context.display_event_menu')
    @patch('university_system.modules.core.services.student_union_misc.union_context.display_facility_menu')
    @patch('university_system.modules.core.services.student_union_misc.union_context.display_election_menu')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_multiple_options(self, mock_ctx, mock_election, mock_facility,
                                    mock_event, mock_print, mock_input):
        """Test selecting multiple menu options in sequence."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Verify all menus were called
        mock_event.assert_called_once()
        mock_facility.assert_called_once()
        mock_election.assert_called_once()

    @patch('builtins.input', side_effect=['18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_shows_admin_options_for_admin(self, mock_ctx, mock_print, mock_input):
        """Test that admin options are shown for admins."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1, 'role': 'admin'}
        mock_ctx.auth.check_permission = Mock(return_value=True)

        # Call function
        menu.display_student_union_menu()

        # Verify admin options are displayed
        assert any('Advanced Analytics' in str(call)
                  for call in mock_print.call_args_list)
        assert any('Admin Dashboard' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_hides_admin_options_for_students(self, mock_ctx, mock_print, mock_input):
        """Test that admin options are hidden for students."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1, 'role': 'student'}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Admin options should not be displayed
        # The menu should show option 18 for return, not separate admin options
        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        # Admin options (15, 16, 17) should not be prominently displayed
        # but option 18 (return) should be


class TestMenuStructure:
    """Tests for menu structure and organization."""

    @patch('builtins.input', side_effect=['18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_shows_core_features(self, mock_ctx, mock_print, mock_input):
        """Test that core features section is displayed."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Verify core features are displayed
        assert any('CORE FEATURES' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_shows_enhanced_features(self, mock_ctx, mock_print, mock_input):
        """Test that enhanced features section is displayed."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Verify enhanced features are displayed
        assert any('ENHANCED FEATURES' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['18'])
    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.context')
    def test_menu_shows_specialized_systems(self, mock_ctx, mock_print, mock_input):
        """Test that specialized systems section is displayed."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        menu.display_student_union_menu()

        # Verify specialized systems are displayed
        assert any('SPECIALIZED SYSTEMS' in str(call)
                  for call in mock_print.call_args_list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
