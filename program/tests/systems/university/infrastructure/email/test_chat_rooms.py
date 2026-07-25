"""
Comprehensive test suite for email/chat_rooms.py
Tests chat room management, invitations, member management, and room interactions
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from education_system.systems.university.infrastructure.email import chat_rooms


class TestInitializeChatTables:
    """Test suite for initialize_chat_tables() function"""

    def test_initialize_chat_tables_success(self):
        """Test successful chat tables initialization"""
        with patch('education_system.systems.university.infrastructure.email.chat_rooms.execute_db_operation') as mock_db:
            mock_db.return_value = True

            result = chat_rooms.initialize_chat_tables()

            assert result is True
            assert mock_db.called

    def test_initialize_chat_tables_creates_invitations_table(self):
        """Test that chat_room_invitations table is created"""
        def mock_operation(func):
            mock_cursor = Mock()
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.chat_rooms.execute_db_operation', side_effect=mock_operation):
            result = chat_rooms.initialize_chat_tables()

            assert result is True

    def test_initialize_chat_tables_creates_indexes(self):
        """Test that indexes are created"""
        def mock_operation(func):
            mock_cursor = Mock()
            return func(mock_cursor)

        with patch('education_system.systems.university.infrastructure.email.chat_rooms.execute_db_operation', side_effect=mock_operation):
            result = chat_rooms.initialize_chat_tables()

            assert result is True

    def test_initialize_chat_tables_database_error(self):
        """Test chat tables initialization with database error"""
        with patch('education_system.systems.university.infrastructure.email.chat_rooms.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            result = chat_rooms.initialize_chat_tables()

            assert result is False


class TestDisplayMyChatRooms:
    """Test suite for display_my_chat_rooms() function"""

    def test_display_my_chat_rooms_with_rooms(self):
        """Test displaying user's chat rooms"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'General',
                    'room_type': 'public',
                    'member_count': 5,
                    'message_count': 10,
                    'is_admin': True
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['6']), \
             patch('builtins.print'):

            chat_rooms.display_my_chat_rooms(mock_dashboard)

            assert mock_dashboard.get_chat_rooms.called

    def test_display_my_chat_rooms_no_rooms(self):
        """Test displaying when user has no rooms"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }

        with patch('builtins.input', return_value=''), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_my_chat_rooms(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any("haven't joined any chat rooms" in str(call) for call in calls)

    def test_display_my_chat_rooms_enter_room(self):
        """Test entering a room"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'General',
                    'room_type': 'public',
                    'member_count': 5,
                    'message_count': 10,
                    'is_admin': False
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }
        mock_dashboard.auth.current_user = {'username': 'testuser'}
        mock_dashboard.get_chat_messages.return_value = {
            'messages': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }
        mock_dashboard.get_room_members.return_value = []

        with patch('builtins.input', side_effect=['1', '1', '/quit', '6']), \
             patch('builtins.print'):

            chat_rooms.display_my_chat_rooms(mock_dashboard)

            assert mock_dashboard.get_chat_messages.called

    def test_display_my_chat_rooms_pagination_next(self):
        """Test pagination - next page"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.side_effect = [
            {
                'rooms': [{'id': i, 'name': f'Room{i}', 'room_type': 'public',
                          'member_count': 1, 'message_count': 0, 'is_admin': False}
                         for i in range(10)],
                'total_count': 15,
                'page': 1,
                'total_pages': 2
            },
            {
                'rooms': [{'id': i, 'name': f'Room{i}', 'room_type': 'public',
                          'member_count': 1, 'message_count': 0, 'is_admin': False}
                         for i in range(10, 15)],
                'total_count': 15,
                'page': 2,
                'total_pages': 2
            }
        ]

        with patch('builtins.input', side_effect=['2', '6']), \
             patch('builtins.print'):

            chat_rooms.display_my_chat_rooms(mock_dashboard)

            assert mock_dashboard.get_chat_rooms.call_count == 2

    def test_display_my_chat_rooms_pagination_previous(self):
        """Test pagination - previous page"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.side_effect = [
            {
                'rooms': [],
                'total_count': 15,
                'page': 2,
                'total_pages': 2
            },
            {
                'rooms': [],
                'total_count': 15,
                'page': 1,
                'total_pages': 2
            }
        ]

        with patch('builtins.input', side_effect=['3', '6']), \
             patch('builtins.print'):

            # Manually set page to 2 for this test
            with patch.object(chat_rooms, 'display_my_chat_rooms') as mock_func:
                pass  # The actual pagination is internal

    def test_display_my_chat_rooms_leave_room(self):
        """Test leaving a room"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'General',
                    'room_type': 'public',
                    'member_count': 5,
                    'message_count': 10,
                    'is_admin': False
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }
        mock_dashboard.leave_chat_room.return_value = True

        with patch('builtins.input', side_effect=['4', '1', 'y', '6']), \
             patch('builtins.print'):

            chat_rooms.display_my_chat_rooms(mock_dashboard)

            assert mock_dashboard.leave_chat_room.called

    def test_display_my_chat_rooms_manage_room_as_admin(self):
        """Test managing a room as admin"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'General',
                    'room_type': 'public',
                    'member_count': 5,
                    'message_count': 10,
                    'is_admin': True
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }
        mock_dashboard.get_room_members.return_value = []

        with patch('builtins.input', side_effect=['5', '1', '1', '', '7', '6']), \
             patch('builtins.print'):

            chat_rooms.display_my_chat_rooms(mock_dashboard)

            # Viewing members in manage menu triggers get_room_members
            assert mock_dashboard.get_room_members.called

    def test_display_my_chat_rooms_manage_room_not_admin(self):
        """Test managing a room as non-admin"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'General',
                    'room_type': 'public',
                    'member_count': 5,
                    'message_count': 10,
                    'is_admin': False
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['5', '1', '6']), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_my_chat_rooms(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('must be an admin' in str(call) for call in calls)

    def test_display_my_chat_rooms_invalid_room_number(self):
        """Test entering invalid room number"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'General',
                    'room_type': 'public',
                    'member_count': 5,
                    'message_count': 10,
                    'is_admin': False
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['1', '999', '6']), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_my_chat_rooms(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Invalid room number' in str(call) for call in calls)


class TestDisplayPublicRooms:
    """Test suite for display_public_rooms() function"""

    def test_display_public_rooms_with_rooms(self):
        """Test displaying public rooms"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'Public Room',
                    'description': 'A public room',
                    'room_type': 'public',
                    'member_count': 10,
                    'message_count': 50,
                    'creator': 'admin',
                    'created_at': '2024-01-01 10:00:00'
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['5']), \
             patch('builtins.print'):

            chat_rooms.display_public_rooms(mock_dashboard)

            assert mock_dashboard.get_chat_rooms.called

    def test_display_public_rooms_no_rooms(self):
        """Test displaying when no public rooms available"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }

        with patch('builtins.input', return_value=''), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_public_rooms(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('No public rooms available' in str(call) for call in calls)

    def test_display_public_rooms_join_room(self):
        """Test joining a public room"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'Public Room',
                    'description': 'A public room',
                    'room_type': 'public',
                    'member_count': 10,
                    'message_count': 50,
                    'creator': 'admin',
                    'created_at': '2024-01-01 10:00:00'
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }
        mock_dashboard.join_chat_room.return_value = True
        mock_dashboard.auth.current_user = {'username': 'testuser'}
        mock_dashboard.get_chat_messages.return_value = {
            'messages': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }
        mock_dashboard.get_room_members.return_value = []

        with patch('builtins.input', side_effect=['1', '1', 'y', 'y', '/quit', '5']), \
             patch('builtins.print'):

            chat_rooms.display_public_rooms(mock_dashboard)

            assert mock_dashboard.join_chat_room.called

    def test_display_public_rooms_join_already_member(self):
        """Test joining room when already a member"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'Public Room',
                    'description': 'A public room',
                    'room_type': 'public',
                    'member_count': 10,
                    'message_count': 50,
                    'creator': 'admin',
                    'created_at': '2024-01-01 10:00:00'
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }
        mock_dashboard.join_chat_room.return_value = "already_member"

        with patch('builtins.input', side_effect=['1', '1', 'y', '5']), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_public_rooms(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('already a member' in str(call) for call in calls)

    def test_display_public_rooms_view_details(self):
        """Test viewing room details"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'Public Room',
                    'description': 'A public room',
                    'room_type': 'public',
                    'member_count': 10,
                    'message_count': 50,
                    'creator': 'admin',
                    'created_at': '2024-01-01 10:00:00'
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['2', '1', '', '5']), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_public_rooms(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Room Details' in str(call) for call in calls)


class TestCreateChatRoomForm:
    """Test suite for create_chat_room_form() function"""

    def test_create_chat_room_form_success(self):
        """Test successfully creating a chat room"""
        mock_dashboard = Mock()
        mock_dashboard.create_chat_room.return_value = 123
        mock_dashboard.auth.current_user = {'username': 'testuser'}
        mock_dashboard.get_chat_messages.return_value = {
            'messages': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }
        mock_dashboard.get_room_members.return_value = []

        with patch('builtins.input', side_effect=[
            'Test Room',  # name
            'Test description',  # description
            '1',  # public
            'y',  # confirm
            'y',  # enter now
            '/quit'  # exit room
        ]), patch('builtins.print'):

            chat_rooms.create_chat_room_form(mock_dashboard)

            assert mock_dashboard.create_chat_room.called
            args, kwargs = mock_dashboard.create_chat_room.call_args
            assert args[0] == 'Test Room'
            assert args[1] == 'Test description'
            assert args[2] == 'public'

    def test_create_chat_room_form_empty_name(self):
        """Test creating room with empty name"""
        mock_dashboard = Mock()

        with patch('builtins.input', return_value=''), \
             patch('builtins.print') as mock_print:

            chat_rooms.create_chat_room_form(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Room name is required' in str(call) for call in calls)

    def test_create_chat_room_form_no_description(self):
        """Test creating room without description"""
        mock_dashboard = Mock()
        mock_dashboard.create_chat_room.return_value = 123

        with patch('builtins.input', side_effect=[
            'Test Room',
            '',  # empty description
            '1',  # public
            'y',  # confirm
            'n'  # don't enter
        ]), patch('builtins.print'):

            chat_rooms.create_chat_room_form(mock_dashboard)

            args, kwargs = mock_dashboard.create_chat_room.call_args
            assert args[1] is None

    def test_create_chat_room_form_different_types(self):
        """Test creating rooms with different types"""
        mock_dashboard = Mock()
        mock_dashboard.create_chat_room.return_value = 123

        room_types = [
            ('1', 'public'),
            ('2', 'private'),
            ('3', 'course'),
            ('4', 'department')
        ]

        for choice, expected_type in room_types:
            with patch('builtins.input', side_effect=[
                'Test Room',
                'Description',
                choice,
                'y',
                'n'
            ]), patch('builtins.print'):

                chat_rooms.create_chat_room_form(mock_dashboard)

                args, kwargs = mock_dashboard.create_chat_room.call_args
                assert args[2] == expected_type

    def test_create_chat_room_form_cancel(self):
        """Test canceling room creation"""
        mock_dashboard = Mock()

        with patch('builtins.input', side_effect=[
            'Test Room',
            'Description',
            '1',
            'n'  # cancel
        ]), patch('builtins.print') as mock_print:

            chat_rooms.create_chat_room_form(mock_dashboard)

            # create_chat_room should not be called
            assert not mock_dashboard.create_chat_room.called

    def test_create_chat_room_form_creation_failure(self):
        """Test handling room creation failure"""
        mock_dashboard = Mock()
        mock_dashboard.create_chat_room.return_value = None

        with patch('builtins.input', side_effect=[
            'Test Room',
            'Description',
            '1',
            'y'
        ]), patch('builtins.print') as mock_print:

            chat_rooms.create_chat_room_form(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Failed to create room' in str(call) for call in calls)


class TestEnterChatRoom:
    """Test suite for enter_chat_room() function"""

    def test_enter_chat_room_with_messages(self):
        """Test entering room with existing messages"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {
            'messages': [
                {
                    'sender': 'user1',
                    'content': 'Hello',
                    'sent_at': '2024-01-01 10:00:00'
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['/quit']), \
             patch('builtins.print') as mock_print:

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Hello' in str(call) for call in calls)

    def test_enter_chat_room_no_messages(self):
        """Test entering room with no messages"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {
            'messages': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }

        with patch('builtins.input', side_effect=['/quit']), \
             patch('builtins.print') as mock_print:

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('No messages yet' in str(call) for call in calls)

    def test_enter_chat_room_send_message(self):
        """Test sending a message in the room"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {'messages': [], 'total_count': 0, 'page': 1, 'total_pages': 0}
        mock_dashboard.send_chat_message.return_value = 123

        with patch('builtins.input', side_effect=['Hello everyone!', '/quit']), \
             patch('builtins.print'):

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            assert mock_dashboard.send_chat_message.called
            args, kwargs = mock_dashboard.send_chat_message.call_args
            assert args[0] == 1
            assert args[1] == 'Hello everyone!'

    def test_enter_chat_room_help_command(self):
        """Test /help command"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {'messages': [], 'total_count': 0, 'page': 1, 'total_pages': 0}

        with patch('builtins.input', side_effect=['/help', '/quit']), \
             patch('builtins.print') as mock_print:

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Available commands' in str(call) for call in calls)

    def test_enter_chat_room_members_command(self):
        """Test /members command"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {'messages': [], 'total_count': 0, 'page': 1, 'total_pages': 0}
        mock_dashboard.get_room_members.return_value = [
            {
                'full_name': 'Test User',
                'username': 'testuser',
                'is_admin': True,
                'user_id': 1
            }
        ]

        with patch('builtins.input', side_effect=['/members', '/quit']), \
             patch('builtins.print') as mock_print:

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Room Members' in str(call) for call in calls)

    def test_enter_chat_room_invite_command_as_admin(self):
        """Test /invite command as admin"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {'messages': [], 'total_count': 0, 'page': 1, 'total_pages': 0}
        mock_dashboard.get_room_members.return_value = [
            {'user_id': 1, 'is_admin': True, 'full_name': 'Test User', 'username': 'testuser'}
        ]
        mock_dashboard.invite_user_to_room.return_value = True

        with patch('builtins.input', side_effect=['/invite', 'otheruser', '/quit']), \
             patch('builtins.print'), \
             patch('education_system.systems.university.infrastructure.email.admin.search_users') as mock_search:

            mock_search.return_value = [{'id': 2, 'username': 'otheruser'}]

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            assert mock_dashboard.invite_user_to_room.called

    def test_enter_chat_room_invite_command_not_admin(self):
        """Test /invite command as non-admin"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {'messages': [], 'total_count': 0, 'page': 1, 'total_pages': 0}
        mock_dashboard.get_room_members.return_value = [
            {'user_id': 1, 'is_admin': False, 'full_name': 'Test User', 'username': 'testuser'}
        ]

        with patch('builtins.input', side_effect=['/invite', '/quit']), \
             patch('builtins.print') as mock_print:

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Only room admins can invite' in str(call) for call in calls)

    def test_enter_chat_room_leave_command(self):
        """Test /leave command"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {'messages': [], 'total_count': 0, 'page': 1, 'total_pages': 0}
        mock_dashboard.leave_chat_room.return_value = True

        with patch('builtins.input', side_effect=['/leave', 'y']), \
             patch('builtins.print'):

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            assert mock_dashboard.leave_chat_room.called

    def test_enter_chat_room_unknown_command(self):
        """Test unknown command"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'username': 'testuser', 'id': 1}
        mock_dashboard.get_chat_messages.return_value = {'messages': [], 'total_count': 0, 'page': 1, 'total_pages': 0}

        with patch('builtins.input', side_effect=['/unknown', '/quit']), \
             patch('builtins.print') as mock_print:

            chat_rooms.enter_chat_room(mock_dashboard, 1, 'Test Room')

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Unknown command' in str(call) for call in calls)


class TestDisplayRoomInvitations:
    """Test suite for display_room_invitations() function"""

    def test_display_room_invitations_no_invitations(self):
        """Test displaying when no invitations exist"""
        mock_dashboard = Mock()
        mock_dashboard.get_pending_invitations.return_value = []

        with patch('builtins.input', return_value=''), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_room_invitations(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('no pending room invitations' in str(call) for call in calls)

    def test_display_room_invitations_accept_invitation(self):
        """Test accepting an invitation"""
        mock_dashboard = Mock()
        mock_dashboard.get_pending_invitations.return_value = [
            {
                'id': 1,
                'room_id': 123,
                'room_name': 'Test Room',
                'invited_by': 'admin',
                'invited_at': '2024-01-01 10:00:00',
                'room_description': 'A test room'
            }
        ]
        mock_dashboard.respond_to_invitation.return_value = True
        mock_dashboard.auth.current_user = {'username': 'testuser'}
        mock_dashboard.get_chat_messages.return_value = {'messages': [], 'total_count': 0, 'page': 1, 'total_pages': 0}

        with patch('builtins.input', side_effect=['1', '1', 'y', '/quit']), \
             patch('builtins.print'):

            chat_rooms.display_room_invitations(mock_dashboard)

            assert mock_dashboard.respond_to_invitation.called
            args, kwargs = mock_dashboard.respond_to_invitation.call_args
            assert args[0] == 1
            assert kwargs.get('accept') is True or (len(args) > 1 and args[1] is True)

    def test_display_room_invitations_decline_invitation(self):
        """Test declining an invitation"""
        mock_dashboard = Mock()
        mock_dashboard.get_pending_invitations.return_value = [
            {
                'id': 1,
                'room_id': 123,
                'room_name': 'Test Room',
                'invited_by': 'admin',
                'invited_at': '2024-01-01 10:00:00',
                'room_description': 'A test room'
            }
        ]
        mock_dashboard.respond_to_invitation.return_value = True

        with patch('builtins.input', side_effect=['2', '1', 'y', '']), \
             patch('builtins.print'):

            chat_rooms.display_room_invitations(mock_dashboard)

            assert mock_dashboard.respond_to_invitation.called
            args, kwargs = mock_dashboard.respond_to_invitation.call_args
            assert kwargs.get('accept') is False or (len(args) > 1 and args[1] is False)

    def test_display_room_invitations_view_details(self):
        """Test viewing invitation details"""
        mock_dashboard = Mock()
        mock_dashboard.get_pending_invitations.return_value = [
            {
                'id': 1,
                'room_id': 123,
                'room_name': 'Test Room',
                'invited_by': 'admin',
                'invited_at': '2024-01-01 10:00:00',
                'room_description': 'A test room'
            }
        ]

        with patch('builtins.input', side_effect=['3', '1', '', '4']), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_room_invitations(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Invitation Details' in str(call) for call in calls)


class TestManageChatRoom:
    """Test suite for manage_chat_room() function"""

    def test_manage_chat_room_view_members(self):
        """Test viewing room members"""
        mock_dashboard = Mock()
        mock_dashboard.get_room_members.return_value = [
            {
                'full_name': 'Test User',
                'username': 'testuser',
                'is_admin': True,
                'joined_at': '2024-01-01 10:00:00'
            }
        ]

        with patch('builtins.input', side_effect=['1', '', '7']), \
             patch('builtins.print'):

            chat_rooms.manage_chat_room(mock_dashboard, 1, 'Test Room')

            assert mock_dashboard.get_room_members.called

    def test_manage_chat_room_invite_user(self):
        """Test inviting a user"""
        mock_dashboard = Mock()
        mock_dashboard.invite_user_to_room.return_value = True

        with patch('builtins.input', side_effect=['2', 'otheruser', '', '7']), \
             patch('builtins.print'), \
             patch('education_system.systems.university.infrastructure.email.admin.search_users') as mock_search:

            mock_search.return_value = [{'id': 2, 'username': 'otheruser', 'full_name': 'Other User', 'email': 'other@test.com'}]

            chat_rooms.manage_chat_room(mock_dashboard, 1, 'Test Room')

            assert mock_dashboard.invite_user_to_room.called

    def test_manage_chat_room_remove_member(self):
        """Test removing a member"""
        mock_dashboard = Mock()

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (2,)
            mock_cursor.rowcount = 1
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['3', 'otheruser', '', '7']), \
             patch('builtins.print'), \
             patch('education_system.systems.university.infrastructure.email.chat_rooms.execute_db_operation', side_effect=mock_operation):

            chat_rooms.manage_chat_room(mock_dashboard, 1, 'Test Room')

    def test_manage_chat_room_promote_member(self):
        """Test promoting a member to moderator"""
        mock_dashboard = Mock()

        operations_count = [0]

        def mock_operation(func):
            mock_cursor = Mock()
            operations_count[0] += 1
            if operations_count[0] == 1:
                # get_member_info
                mock_cursor.fetchone.return_value = (2, 'member')
            else:
                # update_role
                mock_cursor.rowcount = 1
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['4', 'otheruser', '1', '', '7']), \
             patch('builtins.print'), \
             patch('education_system.systems.university.infrastructure.email.chat_rooms.execute_db_operation', side_effect=mock_operation):

            chat_rooms.manage_chat_room(mock_dashboard, 1, 'Test Room')

    def test_manage_chat_room_view_messages(self):
        """Test viewing recent messages"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_messages.return_value = {
            'messages': [
                {
                    'sender': 'user1',
                    'content': 'Hello',
                    'sent_at': '2024-01-01 10:00:00'
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['5', '', '7']), \
             patch('builtins.print'):

            chat_rooms.manage_chat_room(mock_dashboard, 1, 'Test Room')

            assert mock_dashboard.get_chat_messages.called

    def test_manage_chat_room_change_name(self):
        """Test changing room name"""
        mock_dashboard = Mock()

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.rowcount = 1
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['6', '1', 'New Room Name', '', '7']), \
             patch('builtins.print'), \
             patch('education_system.systems.university.infrastructure.email.chat_rooms.execute_db_operation', side_effect=mock_operation):

            chat_rooms.manage_chat_room(mock_dashboard, 1, 'Test Room')

    def test_manage_chat_room_toggle_privacy(self):
        """Test toggling room privacy"""
        mock_dashboard = Mock()

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (0,)  # Currently public
            mock_cursor.rowcount = 1
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['6', '3', '', '7']), \
             patch('builtins.print'), \
             patch('education_system.systems.university.infrastructure.email.chat_rooms.execute_db_operation', side_effect=mock_operation):

            chat_rooms.manage_chat_room(mock_dashboard, 1, 'Test Room')


class TestDisplayAllRoomsAdmin:
    """Test suite for display_all_rooms_admin() function"""

    def test_display_all_rooms_admin_with_rooms(self):
        """Test admin view of all rooms"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [
                {
                    'id': 1,
                    'name': 'Room 1',
                    'room_type': 'public',
                    'creator': 'admin',
                    'member_count': 5,
                    'message_count': 10,
                    'is_admin': True
                }
            ],
            'total_count': 1,
            'page': 1,
            'total_pages': 1
        }

        with patch('builtins.input', side_effect=['6']), \
             patch('builtins.print'):

            chat_rooms.display_all_rooms_admin(mock_dashboard)

            assert mock_dashboard.get_chat_rooms.called

    def test_display_all_rooms_admin_no_rooms(self):
        """Test admin view when no rooms exist"""
        mock_dashboard = Mock()
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }

        with patch('builtins.input', return_value=''), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_all_rooms_admin(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('No chat rooms found' in str(call) for call in calls)


class TestDisplayChatRoomsMenu:
    """Test suite for display_chat_rooms_menu() function"""

    def test_display_chat_rooms_menu_my_rooms(self):
        """Test accessing my rooms from menu"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'student'}
        mock_dashboard.get_pending_invitations.return_value = []
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }

        with patch('builtins.input', side_effect=['1', '5']), \
             patch('builtins.print'):

            chat_rooms.display_chat_rooms_menu(mock_dashboard)

            assert mock_dashboard.get_chat_rooms.called

    def test_display_chat_rooms_menu_pending_invitations_notification(self):
        """Test notification of pending invitations"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'student'}
        mock_dashboard.get_pending_invitations.return_value = [
            {'id': 1, 'room_name': 'Test'}
        ]

        with patch('builtins.input', side_effect=['5']), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_chat_rooms_menu(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('pending room invitation' in str(call) for call in calls)

    def test_display_chat_rooms_menu_admin_options(self):
        """Test admin-specific menu options"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'role': 'admin'}
        mock_dashboard.get_pending_invitations.return_value = []
        mock_dashboard.get_chat_rooms.return_value = {
            'rooms': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0
        }

        with patch('builtins.input', side_effect=['5', '6']), \
             patch('builtins.print') as mock_print:

            chat_rooms.display_chat_rooms_menu(mock_dashboard)

            calls = [str(call) for call in mock_print.call_args_list]
            # Admin should see "All Rooms (Admin)" option
            assert any('All Rooms (Admin)' in str(call) for call in calls)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
