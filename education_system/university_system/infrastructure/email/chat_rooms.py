"""Chat room management helpers."""

from __future__ import annotations

from datetime import datetime

from education_system.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.university_system.core.logs import handle_exception, log_event
from education_system.university_system.core.i18n import get_text as _t, init_i18n

init_i18n()


@handle_exception
def initialize_chat_tables():
    """Initialize the chat-related database tables if they don't exist"""
    def _init_chat_tables(cursor):
        # Chat room invitations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_room_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            invited_by INTEGER NOT NULL,
            invited_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            responded_at TEXT,
            FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (invited_by) REFERENCES users (id)
        )
        ''')

        # Create index for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_invitation_user ON chat_room_invitations(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_invitation_room ON chat_room_invitations(room_id)')

        return True

    try:
        result = execute_db_operation(_init_chat_tables)
        if result:
            log_event('info', "Chat tables initialized successfully")
        return result
    except Exception as e:
        log_event('error', f"Error initializing chat tables: {e}")
        return False



def display_my_chat_rooms(dashboard):
    """Display user's joined chat rooms"""
    page = 1
    limit = 10

    while True:
        rooms_data = dashboard.get_chat_rooms('joined', page, limit)

        if rooms_data['total_count'] == 0:
            print("\n" + _t("chat_rooms.no_rooms_joined"))
            print(_t("chat_rooms.join_hint"))
            input(_t("common.press_enter"))
            break

        print(f"\n" + _t("chat_rooms.my_rooms_title", count=rooms_data['total_count']))
        print("=" * 80)
        print(f"{'#':<3}{_t('chat_rooms.room_name'):<25}{_t('common.type'):<10}{_t('chat_rooms.members'):<10}{_t('chat_rooms.messages'):<10}{_t('chat_rooms.role'):<8}")
        print("-" * 80)

        for i, room in enumerate(rooms_data['rooms'], 1):
            role = _t("chat_rooms.admin") if room['is_admin'] else _t("chat_rooms.member")
            print(f"{i:<3}{room['name']:<25}{room['room_type']:<10}{room['member_count']:<10}{room['message_count']:<10}{role:<8}")

        print(f"\n" + _t("chat_rooms.page_info", page=rooms_data['page'], total=rooms_data['total_pages']))

        print("\n" + _t("chat_rooms.options") + ":")
        print("1. " + _t("chat_rooms.enter_room"))
        print("2. " + _t("common.next")) if page < rooms_data['total_pages'] else print("2. " + _t("chat_rooms.no_more_pages"))
        print("3. " + _t("common.previous")) if page > 1 else print("3. " + _t("chat_rooms.first_page"))
        print("4. " + _t("chat_rooms.leave_room"))
        print("5. " + _t("chat_rooms.room_management"))
        print("6. " + _t("chat_rooms.back_to_menu"))

        choice = input(_t("chat_rooms.enter_choice") + ": ")

        if choice == '1':
            # Enter a room
            try:
                room_num = int(input(_t("chat_rooms.enter_room_number") + ": "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    enter_chat_room(dashboard, room['id'], room['name'])
                else:
                    print(_t("chat_rooms.invalid_room_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '2' and page < rooms_data['total_pages']:
            page += 1

        elif choice == '3' and page > 1:
            page -= 1

        elif choice == '4':
            # Leave a room
            try:
                room_num = int(input(_t("chat_rooms.enter_room_to_leave") + ": "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]

                    confirm = input(_t("chat_rooms.confirm_leave", name=room['name']) + " (y/n): ")
                    if confirm.lower() == 'y':
                        if dashboard.leave_chat_room(room['id']):
                            print(_t("chat_rooms.left_room_success", name=room['name']))
                            # Refresh the page
                            rooms_data = dashboard.get_chat_rooms('joined', page, limit)
                            if page > rooms_data['total_pages'] and rooms_data['total_pages'] > 0:
                                page = rooms_data['total_pages']
                        else:
                            print(_t("chat_rooms.failed_leave_room"))
                    else:
                        print(_t("chat_rooms.leave_cancelled"))
                else:
                    print(_t("chat_rooms.invalid_room_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '5':
            # Room management
            try:
                room_num = int(input(_t("chat_rooms.enter_room_to_manage") + ": "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    if room['is_admin']:
                        manage_chat_room(dashboard, room['id'], room['name'])
                    else:
                        print(_t("chat_rooms.admin_required"))
                else:
                    print(_t("chat_rooms.invalid_room_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '6':
            break
        else:
            print(_t("common.invalid_choice"))



def display_public_rooms(dashboard):
    """Display public rooms available to join"""
    page = 1
    limit = 10

    while True:
        rooms_data = dashboard.get_chat_rooms('public', page, limit)

        if rooms_data['total_count'] == 0:
            print("\n" + _t("chat_rooms.no_public_rooms"))
            print(_t("chat_rooms.all_rooms_joined"))
            input(_t("common.press_enter"))
            break

        print(f"\n" + _t("chat_rooms.public_rooms_title", count=rooms_data['total_count']))
        print("=" * 90)
        print(f"{'#':<3}{_t('chat_rooms.room_name'):<25}{_t('common.description'):<30}{_t('chat_rooms.members'):<10}{_t('chat_rooms.creator'):<15}")
        print("-" * 90)

        for i, room in enumerate(rooms_data['rooms'], 1):
            description = room['description'][:27] + "..." if room['description'] and len(room['description']) > 27 else (room['description'] or _t("chat_rooms.no_description"))
            print(f"{i:<3}{room['name']:<25}{description:<30}{room['member_count']:<10}{room['creator']:<15}")

        print(f"\n" + _t("chat_rooms.page_info", page=rooms_data['page'], total=rooms_data['total_pages']))

        print("\n" + _t("chat_rooms.options") + ":")
        print("1. " + _t("chat_rooms.join_room"))
        print("2. " + _t("chat_rooms.view_details"))
        print("3. " + _t("common.next")) if page < rooms_data['total_pages'] else print("3. " + _t("chat_rooms.no_more_pages"))
        print("4. " + _t("common.previous")) if page > 1 else print("4. " + _t("chat_rooms.first_page"))
        print("5. " + _t("chat_rooms.back_to_menu"))

        choice = input(_t("chat_rooms.enter_choice") + ": ")

        if choice == '1':
            # Join a room
            try:
                room_num = int(input(_t("chat_rooms.enter_room_to_join") + ": "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]

                    confirm = input(_t("chat_rooms.confirm_join", name=room['name']) + " (y/n): ")
                    if confirm.lower() == 'y':
                        result = dashboard.join_chat_room(room['id'])
                        if result == True:
                            print(_t("chat_rooms.joined_room_success", name=room['name']))
                            enter_choice = input(_t("chat_rooms.enter_now") + " (y/n): ")
                            if enter_choice.lower() == 'y':
                                enter_chat_room(dashboard, room['id'], room['name'])
                        elif result == "already_member":
                            print(_t("chat_rooms.already_member"))
                        else:
                            print(_t("chat_rooms.failed_join_room"))
                    else:
                        print(_t("chat_rooms.join_cancelled"))
                else:
                    print(_t("chat_rooms.invalid_room_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '2':
            # View room details
            try:
                room_num = int(input(_t("chat_rooms.enter_room_to_view") + ": "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]

                    print(f"\n" + _t("chat_rooms.room_details") + ":")
                    print("=" * 50)
                    print(f"{_t('common.name')}: {room['name']}")
                    print(f"{_t('common.type')}: {room['room_type']}")
                    print(f"{_t('common.description')}: {room['description'] or _t('chat_rooms.no_description')}")
                    print(f"{_t('chat_rooms.creator')}: {room['creator']}")
                    print(f"{_t('common.created_at')}: {room['created_at']}")
                    print(f"{_t('chat_rooms.members')}: {room['member_count']}")
                    print(f"{_t('chat_rooms.messages')}: {room['message_count']}")

                    input("\n" + _t("common.press_enter"))
                else:
                    print(_t("chat_rooms.invalid_room_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '3' and page < rooms_data['total_pages']:
            page += 1

        elif choice == '4' and page > 1:
            page -= 1

        elif choice == '5':
            break
        else:
            print(_t("common.invalid_choice"))



def create_chat_room_form(dashboard):
    """Form to create a new chat room"""
    print("\n" + _t("chat_rooms.create_room_title") + ":")
    print("=" * 30)

    # Get room details
    name = input(_t("chat_rooms.room_name") + ": ").strip()
    if not name:
        print(_t("chat_rooms.room_name_required"))
        return

    description = input(_t("chat_rooms.description_optional") + ": ").strip()
    if not description:
        description = None

    print("\n" + _t("chat_rooms.room_type") + ":")
    print("1. " + _t("chat_rooms.type_public"))
    print("2. " + _t("chat_rooms.type_private"))
    print("3. " + _t("chat_rooms.type_course"))
    print("4. " + _t("chat_rooms.type_department"))

    type_choice = input(_t("chat_rooms.choose_type") + " (1-4): ")

    type_map = {
        '1': 'public',
        '2': 'private',
        '3': 'course',
        '4': 'department'
    }

    room_type = type_map.get(type_choice, 'public')

    # Confirm creation
    print(f"\n" + _t("chat_rooms.room_summary") + ":")
    print(f"{_t('common.name')}: {name}")
    print(f"{_t('common.description')}: {description or _t('common.none')}")
    print(f"{_t('common.type')}: {room_type}")

    confirm = input("\n" + _t("chat_rooms.confirm_create") + " (y/n): ")
    if confirm.lower() == 'y':
        room_id = dashboard.create_chat_room(name, description, room_type)
        if room_id:
            print(_t("chat_rooms.room_created_success", name=name))
            enter_choice = input(_t("chat_rooms.enter_now") + " (y/n): ")
            if enter_choice.lower() == 'y':
                enter_chat_room(dashboard, room_id, name)
        else:
            print(_t("chat_rooms.failed_create_room"))
    else:
        print(_t("chat_rooms.create_cancelled"))



def enter_chat_room(dashboard, room_id, room_name):
    """Enter and interact in a chat room"""
    print(f"\n{'='*60}")
    print(_t("chat_rooms.entering_room", name=room_name))
    print(f"{'='*60}")
    print(_t("chat_rooms.commands_hint"))
    print(_t("chat_rooms.type_message_hint"))
    print("-" * 60)

    # Load recent messages
    messages_data = dashboard.get_chat_messages(room_id, page=1, limit=10)

    if messages_data['messages']:
        print(_t("chat_rooms.recent_messages") + ":")
        for msg in messages_data['messages']:
            timestamp = msg['sent_at'][:16]  # Remove seconds
            print(f"[{timestamp}] {msg['sender']}: {msg['content']}")
        print("-" * 60)
    else:
        print(_t("chat_rooms.no_messages_yet"))
        print("-" * 60)

    while True:
        try:
            message = input(f"{dashboard.auth.current_user['username']}: ").strip()

            if not message:
                continue

            if message.startswith('/'):
                # Handle commands
                command = message[1:].lower()

                if command == 'help':
                    print("\n" + _t("chat_rooms.available_commands") + ":")
                    print("/help - " + _t("chat_rooms.cmd_help"))
                    print("/members - " + _t("chat_rooms.cmd_members"))
                    print("/invite - " + _t("chat_rooms.cmd_invite"))
                    print("/leave - " + _t("chat_rooms.cmd_leave"))
                    print("/quit - " + _t("chat_rooms.cmd_quit"))
                    print(_t("chat_rooms.cmd_message_hint"))

                elif command == 'members':
                    members = dashboard.get_room_members(room_id)
                    if members:
                        print(f"\n" + _t("chat_rooms.room_members", count=len(members)) + ":")
                        for member in members:
                            role = " (" + _t("chat_rooms.admin") + ")" if member['is_admin'] else ""
                            print(f"  • {member['full_name']} (@{member['username']}){role}")
                    else:
                        print(_t("chat_rooms.could_not_get_members"))

                elif command == 'invite':
                    # Check if user is admin
                    members = dashboard.get_room_members(room_id)
                    current_user_id = dashboard.auth.current_user['id']
                    is_admin = any(m['user_id'] == current_user_id and m['is_admin'] for m in members)

                    if is_admin:
                        username = input(_t("chat_rooms.enter_username_invite") + ": ").strip()
                        if username:
                            from education_system.university_system.infrastructure.email.admin import search_users  # Local import to avoid circular dependency

                            # Find user
                            user_list = search_users(dashboard.auth, username)
                            if user_list:
                                user = user_list[0]  # Take first match
                                result = dashboard.invite_user_to_room(room_id, user['id'])
                                if result == True:
                                    print(_t("chat_rooms.invitation_sent", username=username))
                                elif result == "already_member":
                                    print(_t("chat_rooms.user_already_member", username=username))
                                elif result == "already_invited":
                                    print(_t("chat_rooms.user_already_invited", username=username))
                                else:
                                    print(_t("chat_rooms.failed_invite", username=username))
                            else:
                                print(_t("chat_rooms.user_not_found", username=username))
                    else:
                        print(_t("chat_rooms.only_admins_invite"))

                elif command == 'leave':
                    confirm = input(_t("chat_rooms.confirm_leave", name=room_name) + " (y/n): ")
                    if confirm.lower() == 'y':
                        if dashboard.leave_chat_room(room_id):
                            print(_t("chat_rooms.left_room_success", name=room_name))
                            break
                        else:
                            print(_t("chat_rooms.failed_leave_room"))
                    else:
                        print(_t("chat_rooms.leave_cancelled"))

                elif command in ['quit', 'exit']:
                    break

                else:
                    print(_t("chat_rooms.unknown_command", command=command))

            else:
                # Send message
                message_id = dashboard.send_chat_message(room_id, message)
                if message_id:
                    # Message sent successfully - it will appear in the next refresh
                    pass
                else:
                    print(_t("chat_rooms.failed_send_message"))

        except KeyboardInterrupt:
            print("\n" + _t("chat_rooms.exiting_room"))
            break
        except Exception as e:
            print(f"{_t('common.error')}: {e}")



def display_room_invitations(dashboard):
    """Display and manage room invitations"""
    invitations = dashboard.get_pending_invitations()

    if not invitations:
        print("\n" + _t("chat_rooms.no_pending_invitations"))
        input(_t("common.press_enter"))
        return

    while True:
        print(f"\n" + _t("chat_rooms.pending_invitations", count=len(invitations)) + ":")
        print("=" * 70)
        print(f"{'#':<3}{_t('chat_rooms.room_name'):<25}{_t('chat_rooms.invited_by'):<15}{_t('common.date'):<20}")
        print("-" * 70)

        for i, inv in enumerate(invitations, 1):
            print(f"{i:<3}{inv['room_name']:<25}{inv['invited_by']:<15}{inv['invited_at']:<20}")

        print("\n" + _t("chat_rooms.options") + ":")
        print("1. " + _t("chat_rooms.accept_invitation"))
        print("2. " + _t("chat_rooms.decline_invitation"))
        print("3. " + _t("chat_rooms.view_invitation_details"))
        print("4. " + _t("chat_rooms.back_to_menu"))

        choice = input(_t("chat_rooms.enter_choice") + ": ")

        if choice == '1':
            # Accept invitation
            try:
                inv_num = int(input(_t("chat_rooms.enter_invitation_accept") + ": "))
                if 1 <= inv_num <= len(invitations):
                    invitation = invitations[inv_num - 1]

                    if dashboard.respond_to_invitation(invitation['id'], accept=True):
                        print(_t("chat_rooms.accepted_invitation", name=invitation['room_name']))

                        # Remove from list
                        invitations.pop(inv_num - 1)

                        if not invitations:
                            print(_t("chat_rooms.no_more_invitations"))
                            input(_t("common.press_enter"))
                            break

                        enter_choice = input(_t("chat_rooms.enter_now") + " (y/n): ")
                        if enter_choice.lower() == 'y':
                            enter_chat_room(dashboard, invitation['room_id'], invitation['room_name'])
                    else:
                        print(_t("chat_rooms.failed_accept_invitation"))
                else:
                    print(_t("chat_rooms.invalid_invitation_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '2':
            # Decline invitation
            try:
                inv_num = int(input(_t("chat_rooms.enter_invitation_decline") + ": "))
                if 1 <= inv_num <= len(invitations):
                    invitation = invitations[inv_num - 1]

                    confirm = input(_t("chat_rooms.confirm_decline", name=invitation['room_name']) + " (y/n): ")
                    if confirm.lower() == 'y':
                        if dashboard.respond_to_invitation(invitation['id'], accept=False):
                            print(_t("chat_rooms.declined_invitation", name=invitation['room_name']))

                            # Remove from list
                            invitations.pop(inv_num - 1)

                            if not invitations:
                                print(_t("chat_rooms.no_more_invitations"))
                                input(_t("common.press_enter"))
                                break
                        else:
                            print(_t("chat_rooms.failed_decline_invitation"))
                    else:
                        print(_t("chat_rooms.decline_cancelled"))
                else:
                    print(_t("chat_rooms.invalid_invitation_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '3':
            # View details
            try:
                inv_num = int(input(_t("chat_rooms.enter_invitation_view") + ": "))
                if 1 <= inv_num <= len(invitations):
                    invitation = invitations[inv_num - 1]

                    print(f"\n" + _t("chat_rooms.invitation_details") + ":")
                    print("=" * 40)
                    print(f"{_t('chat_rooms.room')}: {invitation['room_name']}")
                    print(f"{_t('common.description')}: {invitation['room_description'] or _t('chat_rooms.no_description')}")
                    print(f"{_t('chat_rooms.invited_by')}: {invitation['invited_by']}")
                    print(f"{_t('common.date')}: {invitation['invited_at']}")

                    input("\n" + _t("common.press_enter"))
                else:
                    print(_t("chat_rooms.invalid_invitation_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '4':
            break
        else:
            print(_t("common.invalid_choice"))



def manage_chat_room(dashboard, room_id, room_name):
    """Manage a chat room (admin functions)"""
    while True:
        print(f"\n" + _t("chat_rooms.manage_room", name=room_name))
        print("=" * 40)
        print("1. " + _t("chat_rooms.view_members"))
        print("2. " + _t("chat_rooms.invite_user"))
        print("3. " + _t("chat_rooms.remove_member"))
        print("4. " + _t("chat_rooms.promote_demote"))
        print("5. " + _t("chat_rooms.view_recent_messages"))
        print("6. " + _t("chat_rooms.room_settings"))
        print("7. " + _t("common.back"))

        choice = input(_t("chat_rooms.enter_choice") + ": ")

        if choice == '1':
            # View members
            members = dashboard.get_room_members(room_id)
            if members:
                print(f"\n" + _t("chat_rooms.room_members", count=len(members)) + ":")
                print("=" * 60)
                print(f"{'#':<3}{_t('common.name'):<20}{_t('chat_rooms.username'):<15}{_t('chat_rooms.role'):<10}{_t('chat_rooms.joined'):<12}")
                print("-" * 60)

                for i, member in enumerate(members, 1):
                    role = _t("chat_rooms.admin") if member['is_admin'] else _t("chat_rooms.member")
                    joined_date = member['joined_at'][:10]  # Just the date
                    print(f"{i:<3}{member['full_name']:<20}{member['username']:<15}{role:<10}{joined_date:<12}")
            else:
                print(_t("chat_rooms.could_not_get_members"))

            input("\n" + _t("common.press_enter"))

        elif choice == '2':
            # Invite user
            print("\n" + _t("chat_rooms.invite_user_title") + ":")
            username = input(_t("chat_rooms.enter_username_invite") + ": ").strip()
            if username:
                from education_system.university_system.infrastructure.email.admin import search_users  # Local import to avoid circular dependency

                # Search for user
                user_list = search_users(dashboard.auth, username)
                if user_list:
                    if len(user_list) == 1:
                        user = user_list[0]
                    else:
                        print(_t("chat_rooms.found_users", count=len(user_list)) + ":")
                        for i, u in enumerate(user_list[:5], 1):
                            print(f"{i}. {u['full_name']} (@{u['username']}) - {u['email']}")

                        try:
                            choice_num = int(input(_t("chat_rooms.select_user_number") + ": "))
                            if 1 <= choice_num <= len(user_list):
                                user = user_list[choice_num - 1]
                            else:
                                print(_t("chat_rooms.invalid_selection"))
                                continue
                        except ValueError:
                            print(_t("chat_rooms.invalid_selection"))
                            continue

                    # Send invitation
                    result = dashboard.invite_user_to_room(room_id, user['id'])
                    if result == True:
                        print(_t("chat_rooms.invitation_sent", username=user['username']))
                    elif result == "already_member":
                        print(_t("chat_rooms.user_already_member", username=user['username']))
                    elif result == "already_invited":
                        print(_t("chat_rooms.user_already_invited", username=user['username']))
                    else:
                        print(_t("chat_rooms.failed_invite", username=user['username']))
                else:
                    print(_t("chat_rooms.user_not_found", username=username))

            input("\n" + _t("common.press_enter"))

        elif choice == '3':
            # Remove member
            username = input(_t("chat_rooms.enter_username_remove") + ": ").strip()
            if username:
                # Get user ID
                def get_user_id(cursor):
                    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                    user = cursor.fetchone()
                    return {'id': user[0]} if user else None

                user = execute_db_operation(get_user_id)

                if user:
                    # Remove member from room
                    def remove_member(cursor):
                        cursor.execute('''
                            DELETE FROM chat_room_members
                            WHERE room_id = ? AND user_id = ?
                        ''', (room_id, user['id']))
                        return cursor.rowcount > 0

                    if execute_db_operation(remove_member):
                        print(_t("chat_rooms.member_removed", username=username))
                        log_event('info', f"User {username} removed from room {room_id}")
                    else:
                        print(_t("chat_rooms.failed_remove_member", username=username))
                else:
                    print(_t("chat_rooms.user_not_found", username=username))

            input("\n" + _t("common.press_enter"))

        elif choice == '4':
            # Promote/demote member
            username = input(_t("chat_rooms.enter_username_promote") + ": ").strip()
            if username:
                # Get user ID and current role
                def get_member_info(cursor):
                    cursor.execute('''
                        SELECT u.id, cm.role
                        FROM users u
                        JOIN chat_room_members cm ON u.id = cm.user_id
                        WHERE u.username = ? AND cm.room_id = ?
                    ''', (username, room_id))
                    member = cursor.fetchone()
                    return {'id': member[0], 'role': member[1]} if member else None

                member = execute_db_operation(get_member_info)

                if member:
                    current_role = member['role']
                    print(f"\n" + _t("chat_rooms.current_role", role=current_role))
                    print("1. " + _t("chat_rooms.promote_moderator"))
                    print("2. " + _t("chat_rooms.demote_member"))
                    role_choice = input(_t("chat_rooms.select_option") + ": ").strip()

                    new_role = None
                    if role_choice == '1':
                        new_role = 'moderator'
                    elif role_choice == '2':
                        new_role = 'member'

                    if new_role and new_role != current_role:
                        def update_role(cursor):
                            cursor.execute('''
                                UPDATE chat_room_members
                                SET role = ?
                                WHERE room_id = ? AND user_id = ?
                            ''', (new_role, room_id, member['id']))
                            return cursor.rowcount > 0

                        if execute_db_operation(update_role):
                            print(_t("chat_rooms.role_updated", username=username, role=new_role))
                            log_event('info', f"User {username} role changed to {new_role} in room {room_id}")
                        else:
                            print(_t("chat_rooms.failed_update_role"))
                    else:
                        print(_t("chat_rooms.no_change_made"))
                else:
                    print(_t("chat_rooms.user_not_in_room", username=username))

            input("\n" + _t("common.press_enter"))

        elif choice == '5':
            # View recent messages
            messages_data = dashboard.get_chat_messages(room_id, page=1, limit=20)

            if messages_data['messages']:
                print(f"\n" + _t("chat_rooms.recent_messages_count", count=messages_data['total_count']) + ":")
                print("=" * 70)

                for msg in messages_data['messages']:
                    timestamp = msg['sent_at'][:16]
                    print(f"[{timestamp}] {msg['sender']}: {msg['content']}")
            else:
                print(_t("chat_rooms.no_messages_room"))

            input("\n" + _t("common.press_enter"))

        elif choice == '6':
            # Room settings
            print("\n--- " + _t("chat_rooms.room_settings") + " ---")
            print("1. " + _t("chat_rooms.change_room_name"))
            print("2. " + _t("chat_rooms.change_description"))
            print("3. " + _t("chat_rooms.toggle_privacy"))
            print("4. " + _t("common.back"))
            settings_choice = input("\n" + _t("chat_rooms.select_option") + ": ").strip()

            if settings_choice == '1':
                new_name = input(_t("chat_rooms.enter_new_name") + ": ").strip()
                if new_name:
                    def update_name(cursor):
                        cursor.execute('UPDATE chat_rooms SET name = ? WHERE id = ?', (new_name, room_id))
                        return cursor.rowcount > 0

                    if execute_db_operation(update_name):
                        print(_t("chat_rooms.name_updated", name=new_name))
                        log_event('info', f"Room {room_id} name changed to {new_name}")
                    else:
                        print(_t("chat_rooms.failed_update_name"))

            elif settings_choice == '2':
                new_desc = input(_t("chat_rooms.enter_new_description") + ": ").strip()
                if new_desc:
                    def update_desc(cursor):
                        cursor.execute('UPDATE chat_rooms SET description = ? WHERE id = ?', (new_desc, room_id))
                        return cursor.rowcount > 0

                    if execute_db_operation(update_desc):
                        print(_t("chat_rooms.description_updated"))
                        log_event('info', f"Room {room_id} description updated")
                    else:
                        print(_t("chat_rooms.failed_update_description"))

            elif settings_choice == '3':
                def toggle_privacy(cursor):
                    cursor.execute('SELECT is_private FROM chat_rooms WHERE id = ?', (room_id,))
                    current = cursor.fetchone()
                    if current:
                        new_privacy = 0 if current[0] else 1
                        cursor.execute('UPDATE chat_rooms SET is_private = ? WHERE id = ?', (new_privacy, room_id))
                        return new_privacy
                    return None

                new_privacy = execute_db_operation(toggle_privacy)
                if new_privacy is not None:
                    status = _t("chat_rooms.private") if new_privacy else _t("chat_rooms.public")
                    print(_t("chat_rooms.privacy_updated", status=status))
                    log_event('info', f"Room {room_id} privacy changed to {status}")
                else:
                    print(_t("chat_rooms.failed_toggle_privacy"))

            input("\n" + _t("common.press_enter"))

        elif choice == '7':
            break
        else:
            print(_t("common.invalid_choice"))



def display_all_rooms_admin(dashboard):
    """Admin view of all chat rooms"""
    page = 1
    limit = 15

    while True:
        rooms_data = dashboard.get_chat_rooms('all', page, limit)

        if rooms_data['total_count'] == 0:
            print("\n" + _t("chat_rooms.no_rooms_found"))
            input(_t("common.press_enter"))
            break

        print(f"\n" + _t("chat_rooms.all_rooms_admin", count=rooms_data['total_count']) + ":")
        print("=" * 100)
        print(f"{'#':<3}{_t('chat_rooms.room_name'):<20}{_t('common.type'):<10}{_t('chat_rooms.creator'):<15}{_t('chat_rooms.members'):<8}{_t('chat_rooms.messages'):<8}{_t('chat_rooms.your_role'):<10}")
        print("-" * 100)

        for i, room in enumerate(rooms_data['rooms'], 1):
            role = _t("chat_rooms.admin") if room['is_admin'] else (_t("chat_rooms.member") if room['is_admin'] is not None else _t("chat_rooms.not_member"))
            print(f"{i:<3}{room['name']:<20}{room['room_type']:<10}{room['creator']:<15}{room['member_count']:<8}{room['message_count']:<8}{role:<10}")

        print(f"\n" + _t("chat_rooms.page_info", page=rooms_data['page'], total=rooms_data['total_pages']))

        print("\n" + _t("chat_rooms.options") + ":")
        print("1. " + _t("chat_rooms.view_details"))
        print("2. " + _t("chat_rooms.join_room"))
        print("3. " + _t("chat_rooms.enter_room"))
        print("4. " + _t("common.next")) if page < rooms_data['total_pages'] else print("4. " + _t("chat_rooms.no_more_pages"))
        print("5. " + _t("common.previous")) if page > 1 else print("5. " + _t("chat_rooms.first_page"))
        print("6. " + _t("chat_rooms.back_to_menu"))

        choice = input(_t("chat_rooms.enter_choice") + ": ")

        if choice == '1':
            # View room details
            try:
                room_num = int(input(_t("chat_rooms.enter_room_number") + ": "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]

                    print(f"\n" + _t("chat_rooms.room_details") + ":")
                    print("=" * 50)
                    print(f"{_t('common.id')}: {room['id']}")
                    print(f"{_t('common.name')}: {room['name']}")
                    print(f"{_t('common.type')}: {room['room_type']}")
                    print(f"{_t('common.description')}: {room['description'] or _t('chat_rooms.no_description')}")
                    print(f"{_t('chat_rooms.creator')}: {room['creator']}")
                    print(f"{_t('common.created_at')}: {room['created_at']}")
                    print(f"{_t('chat_rooms.members')}: {room['member_count']}")
                    print(f"{_t('chat_rooms.messages')}: {room['message_count']}")
                    print(f"{_t('chat_rooms.your_role')}: {(_t('chat_rooms.admin') if room['is_admin'] else _t('chat_rooms.member')) if room['is_admin'] is not None else _t('chat_rooms.not_a_member')}")

                    input("\n" + _t("common.press_enter"))
                else:
                    print(_t("chat_rooms.invalid_room_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '2':
            # Join room
            try:
                room_num = int(input(_t("chat_rooms.enter_room_to_join") + ": "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]

                    if room['is_admin'] is not None:
                        print(_t("chat_rooms.already_member"))
                    else:
                        result = dashboard.join_chat_room(room['id'])
                        if result == True:
                            print(_t("chat_rooms.joined_room_success", name=room['name']))
                        elif result == "already_member":
                            print(_t("chat_rooms.already_member"))
                        else:
                            print(_t("chat_rooms.failed_join_room"))
                else:
                    print(_t("chat_rooms.invalid_room_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '3':
            # Enter room
            try:
                room_num = int(input(_t("chat_rooms.enter_room_number") + ": "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]

                    if room['is_admin'] is not None:
                        enter_chat_room(dashboard, room['id'], room['name'])
                    else:
                        print(_t("chat_rooms.must_be_member"))
                else:
                    print(_t("chat_rooms.invalid_room_number"))
            except ValueError:
                print(_t("chat_rooms.enter_valid_number"))

        elif choice == '4' and page < rooms_data['total_pages']:
            page += 1

        elif choice == '5' and page > 1:
            page -= 1

        elif choice == '6':
            break
        else:
            print(_t("common.invalid_choice"))



@handle_exception
def display_chat_rooms_menu(dashboard):
    """Main chat rooms menu"""
    while True:
        print("\n" + _t("chat_rooms.title") + ":")
        print("===========")

        # Check for pending invitations
        pending_invitations = dashboard.get_pending_invitations()
        if pending_invitations:
            print(_t("chat_rooms.pending_invitations_notice", count=len(pending_invitations)))

        print("1. " + _t("chat_rooms.my_chat_rooms"))
        print("2. " + _t("chat_rooms.public_rooms"))
        print("3. " + _t("chat_rooms.create_new_room"))
        print("4. " + _t("chat_rooms.room_invitations"))
        if dashboard.auth.current_user['role'] == 'admin':
            print("5. " + _t("chat_rooms.all_rooms_admin_menu"))
            print("6. " + _t("chat_rooms.back_to_dashboard"))
        else:
            print("5. " + _t("chat_rooms.back_to_dashboard"))

        choice = input(_t("chat_rooms.enter_your_choice") + ": ")

        if choice == '1':
            display_my_chat_rooms(dashboard)
        elif choice == '2':
            display_public_rooms(dashboard)
        elif choice == '3':
            create_chat_room_form(dashboard)
        elif choice == '4':
            display_room_invitations(dashboard)
        elif choice == '5' and dashboard.auth.current_user['role'] == 'admin':
            display_all_rooms_admin(dashboard)
        elif choice == '5' and dashboard.auth.current_user['role'] != 'admin':
            break
        elif choice == '6' and dashboard.auth.current_user['role'] == 'admin':
            break
        else:
            print(_t("common.invalid_choice"))
