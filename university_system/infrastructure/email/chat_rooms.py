"""Chat room management helpers."""

from __future__ import annotations

from datetime import datetime

from university_system.infrastructure.email.email_db_utilities import execute_db_operation
from university_system.modules.shared.utils.logs import handle_exception, log_event


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
            print("\nYou haven't joined any chat rooms yet.")
            print("Use 'Public Rooms' to find rooms to join or 'Create New Room' to start your own.")
            input("Press Enter to continue...")
            break
        
        print(f"\nMy Chat Rooms ({rooms_data['total_count']} total):")
        print("=" * 80)
        print(f"{'#':<3}{'Room Name':<25}{'Type':<10}{'Members':<10}{'Messages':<10}{'Role':<8}")
        print("-" * 80)
        
        for i, room in enumerate(rooms_data['rooms'], 1):
            role = "Admin" if room['is_admin'] else "Member"
            print(f"{i:<3}{room['name']:<25}{room['room_type']:<10}{room['member_count']:<10}{room['message_count']:<10}{role:<8}")
        
        print(f"\nPage {rooms_data['page']} of {rooms_data['total_pages']}")
        
        print("\nOptions:")
        print("1. Enter a room")
        print("2. Next page") if page < rooms_data['total_pages'] else print("2. (No more pages)")
        print("3. Previous page") if page > 1 else print("3. (First page)")
        print("4. Leave a room")
        print("5. Room management")
        print("6. Back to Chat Rooms Menu")
        
        choice = input("Enter choice: ")
        
        if choice == '1':
            # Enter a room
            try:
                room_num = int(input("Enter room number: "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    enter_chat_room(dashboard, room['id'], room['name'])
                else:
                    print("Invalid room number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '2' and page < rooms_data['total_pages']:
            page += 1
            
        elif choice == '3' and page > 1:
            page -= 1
            
        elif choice == '4':
            # Leave a room
            try:
                room_num = int(input("Enter room number to leave: "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    
                    confirm = input(f"Are you sure you want to leave '{room['name']}'? (y/n): ")
                    if confirm.lower() == 'y':
                        if dashboard.leave_chat_room(room['id']):
                            print(f"✅ Successfully left room '{room['name']}'")
                            # Refresh the page
                            rooms_data = dashboard.get_chat_rooms('joined', page, limit)
                            if page > rooms_data['total_pages'] and rooms_data['total_pages'] > 0:
                                page = rooms_data['total_pages']
                        else:
                            print("❌ Failed to leave room.")
                    else:
                        print("Leave cancelled.")
                else:
                    print("Invalid room number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '5':
            # Room management
            try:
                room_num = int(input("Enter room number to manage: "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    if room['is_admin']:
                        manage_chat_room(dashboard, room['id'], room['name'])
                    else:
                        print("You must be an admin to manage this room.")
                else:
                    print("Invalid room number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")



def display_public_rooms(dashboard):
    """Display public rooms available to join"""
    page = 1
    limit = 10
    
    while True:
        rooms_data = dashboard.get_chat_rooms('public', page, limit)
        
        if rooms_data['total_count'] == 0:
            print("\nNo public rooms available to join.")
            print("All public rooms have already been joined or none exist.")
            input("Press Enter to continue...")
            break
        
        print(f"\nPublic Rooms Available ({rooms_data['total_count']} total):")
        print("=" * 90)
        print(f"{'#':<3}{'Room Name':<25}{'Description':<30}{'Members':<10}{'Creator':<15}")
        print("-" * 90)
        
        for i, room in enumerate(rooms_data['rooms'], 1):
            description = room['description'][:27] + "..." if room['description'] and len(room['description']) > 27 else (room['description'] or "No description")
            print(f"{i:<3}{room['name']:<25}{description:<30}{room['member_count']:<10}{room['creator']:<15}")
        
        print(f"\nPage {rooms_data['page']} of {rooms_data['total_pages']}")
        
        print("\nOptions:")
        print("1. Join a room")
        print("2. View room details")
        print("3. Next page") if page < rooms_data['total_pages'] else print("3. (No more pages)")
        print("4. Previous page") if page > 1 else print("4. (First page)")
        print("5. Back to Chat Rooms Menu")
        
        choice = input("Enter choice: ")
        
        if choice == '1':
            # Join a room
            try:
                room_num = int(input("Enter room number to join: "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    
                    confirm = input(f"Join room '{room['name']}'? (y/n): ")
                    if confirm.lower() == 'y':
                        result = dashboard.join_chat_room(room['id'])
                        if result == True:
                            print(f"✅ Successfully joined room '{room['name']}'!")
                            enter_choice = input("Enter the room now? (y/n): ")
                            if enter_choice.lower() == 'y':
                                enter_chat_room(dashboard, room['id'], room['name'])
                        elif result == "already_member":
                            print("You are already a member of this room.")
                        else:
                            print("❌ Failed to join room.")
                    else:
                        print("Join cancelled.")
                else:
                    print("Invalid room number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '2':
            # View room details
            try:
                room_num = int(input("Enter room number to view details: "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    
                    print(f"\nRoom Details:")
                    print("=" * 50)
                    print(f"Name: {room['name']}")
                    print(f"Type: {room['room_type']}")
                    print(f"Description: {room['description'] or 'No description'}")
                    print(f"Creator: {room['creator']}")
                    print(f"Created: {room['created_at']}")
                    print(f"Members: {room['member_count']}")
                    print(f"Messages: {room['message_count']}")
                    
                    input("\nPress Enter to continue...")
                else:
                    print("Invalid room number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '3' and page < rooms_data['total_pages']:
            page += 1
            
        elif choice == '4' and page > 1:
            page -= 1
            
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")



def create_chat_room_form(dashboard):
    """Form to create a new chat room"""
    print("\nCreate New Chat Room:")
    print("=" * 30)
    
    # Get room details
    name = input("Room Name: ").strip()
    if not name:
        print("Room name is required.")
        return
    
    description = input("Description (optional): ").strip()
    if not description:
        description = None
    
    print("\nRoom Type:")
    print("1. Public (anyone can join)")
    print("2. Private (invitation only)")
    print("3. Course (for course discussions)")
    print("4. Department (for department discussions)")
    
    type_choice = input("Choose type (1-4): ")
    
    type_map = {
        '1': 'public',
        '2': 'private', 
        '3': 'course',
        '4': 'department'
    }
    
    room_type = type_map.get(type_choice, 'public')
    
    # Confirm creation
    print(f"\nRoom Summary:")
    print(f"Name: {name}")
    print(f"Description: {description or 'None'}")
    print(f"Type: {room_type}")
    
    confirm = input("\nCreate this room? (y/n): ")
    if confirm.lower() == 'y':
        room_id = dashboard.create_chat_room(name, description, room_type)
        if room_id:
            print(f"✅ Room '{name}' created successfully!")
            enter_choice = input("Enter the room now? (y/n): ")
            if enter_choice.lower() == 'y':
                enter_chat_room(dashboard, room_id, name)
        else:
            print("❌ Failed to create room.")
    else:
        print("Room creation cancelled.")



def enter_chat_room(dashboard, room_id, room_name):
    """Enter and interact in a chat room"""
    print(f"\n{'='*60}")
    print(f"Entering Chat Room: {room_name}")
    print(f"{'='*60}")
    print("Commands: /help, /members, /invite, /leave, /quit")
    print("Type your message and press Enter to send.")
    print("-" * 60)
    
    # Load recent messages
    messages_data = dashboard.get_chat_messages(room_id, page=1, limit=10)
    
    if messages_data['messages']:
        print("Recent messages:")
        for msg in messages_data['messages']:
            timestamp = msg['sent_at'][:16]  # Remove seconds
            print(f"[{timestamp}] {msg['sender']}: {msg['content']}")
        print("-" * 60)
    else:
        print("No messages yet. Be the first to say something!")
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
                    print("\nAvailable commands:")
                    print("/help - Show this help")
                    print("/members - List room members")
                    print("/invite - Invite a user to the room")
                    print("/leave - Leave this room")
                    print("/quit - Exit the room")
                    print("Type any other text to send a message")
                    
                elif command == 'members':
                    members = dashboard.get_room_members(room_id)
                    if members:
                        print(f"\nRoom Members ({len(members)}):")
                        for member in members:
                            role = " (Admin)" if member['is_admin'] else ""
                            print(f"  • {member['full_name']} (@{member['username']}){role}")
                    else:
                        print("Could not retrieve members list.")
                        
                elif command == 'invite':
                    # Check if user is admin
                    members = dashboard.get_room_members(room_id)
                    current_user_id = dashboard.auth.current_user['id']
                    is_admin = any(m['user_id'] == current_user_id and m['is_admin'] for m in members)
                    
                    if is_admin:
                        username = input("Enter username to invite: ").strip()
                        if username:
                            from .admin import search_users  # Local import to avoid circular dependency

                            # Find user
                            user_list = search_users(dashboard.auth, username)
                            if user_list:
                                user = user_list[0]  # Take first match
                                result = dashboard.invite_user_to_room(room_id, user['id'])
                                if result == True:
                                    print(f"✅ Invitation sent to {username}")
                                elif result == "already_member":
                                    print(f"{username} is already a member")
                                elif result == "already_invited":
                                    print(f"{username} already has a pending invitation")
                                else:
                                    print(f"❌ Failed to invite {username}")
                            else:
                                print(f"User '{username}' not found")
                    else:
                        print("Only room admins can invite users.")
                        
                elif command == 'leave':
                    confirm = input(f"Are you sure you want to leave '{room_name}'? (y/n): ")
                    if confirm.lower() == 'y':
                        if dashboard.leave_chat_room(room_id):
                            print(f"✅ Left room '{room_name}'")
                            break
                        else:
                            print("❌ Failed to leave room")
                    else:
                        print("Leave cancelled.")
                        
                elif command in ['quit', 'exit']:
                    break
                    
                else:
                    print(f"Unknown command: /{command}. Type /help for available commands.")
                    
            else:
                # Send message
                message_id = dashboard.send_chat_message(room_id, message)
                if message_id:
                    # Message sent successfully - it will appear in the next refresh
                    pass
                else:
                    print("❌ Failed to send message")
                    
        except KeyboardInterrupt:
            print("\nExiting chat room...")
            break
        except Exception as e:
            print(f"Error: {e}")



def display_room_invitations(dashboard):
    """Display and manage room invitations"""
    invitations = dashboard.get_pending_invitations()
    
    if not invitations:
        print("\nYou have no pending room invitations.")
        input("Press Enter to continue...")
        return
    
    while True:
        print(f"\nPending Room Invitations ({len(invitations)}):")
        print("=" * 70)
        print(f"{'#':<3}{'Room Name':<25}{'Invited By':<15}{'Date':<20}")
        print("-" * 70)
        
        for i, inv in enumerate(invitations, 1):
            print(f"{i:<3}{inv['room_name']:<25}{inv['invited_by']:<15}{inv['invited_at']:<20}")
        
        print("\nOptions:")
        print("1. Accept invitation")
        print("2. Decline invitation")
        print("3. View invitation details")
        print("4. Back to Chat Rooms Menu")
        
        choice = input("Enter choice: ")
        
        if choice == '1':
            # Accept invitation
            try:
                inv_num = int(input("Enter invitation number to accept: "))
                if 1 <= inv_num <= len(invitations):
                    invitation = invitations[inv_num - 1]
                    
                    if dashboard.respond_to_invitation(invitation['id'], accept=True):
                        print(f"✅ Accepted invitation to '{invitation['room_name']}'!")
                        
                        # Remove from list
                        invitations.pop(inv_num - 1)
                        
                        if not invitations:
                            print("No more pending invitations.")
                            input("Press Enter to continue...")
                            break
                            
                        enter_choice = input("Enter the room now? (y/n): ")
                        if enter_choice.lower() == 'y':
                            enter_chat_room(dashboard, invitation['room_id'], invitation['room_name'])
                    else:
                        print("❌ Failed to accept invitation")
                else:
                    print("Invalid invitation number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '2':
            # Decline invitation
            try:
                inv_num = int(input("Enter invitation number to decline: "))
                if 1 <= inv_num <= len(invitations):
                    invitation = invitations[inv_num - 1]
                    
                    confirm = input(f"Decline invitation to '{invitation['room_name']}'? (y/n): ")
                    if confirm.lower() == 'y':
                        if dashboard.respond_to_invitation(invitation['id'], accept=False):
                            print(f"Declined invitation to '{invitation['room_name']}'")
                            
                            # Remove from list
                            invitations.pop(inv_num - 1)
                            
                            if not invitations:
                                print("No more pending invitations.")
                                input("Press Enter to continue...")
                                break
                        else:
                            print("❌ Failed to decline invitation")
                    else:
                        print("Decline cancelled.")
                else:
                    print("Invalid invitation number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '3':
            # View details
            try:
                inv_num = int(input("Enter invitation number to view: "))
                if 1 <= inv_num <= len(invitations):
                    invitation = invitations[inv_num - 1]
                    
                    print(f"\nInvitation Details:")
                    print("=" * 40)
                    print(f"Room: {invitation['room_name']}")
                    print(f"Description: {invitation['room_description'] or 'No description'}")
                    print(f"Invited by: {invitation['invited_by']}")
                    print(f"Date: {invitation['invited_at']}")
                    
                    input("\nPress Enter to continue...")
                else:
                    print("Invalid invitation number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")



def manage_chat_room(dashboard, room_id, room_name):
    """Manage a chat room (admin functions)"""
    while True:
        print(f"\nManage Room: {room_name}")
        print("=" * 40)
        print("1. View Members")
        print("2. Invite User")
        print("3. Remove Member") 
        print("4. Promote/Demote Member")
        print("5. View Recent Messages")
        print("6. Room Settings")
        print("7. Back")
        
        choice = input("Enter choice: ")
        
        if choice == '1':
            # View members
            members = dashboard.get_room_members(room_id)
            if members:
                print(f"\nRoom Members ({len(members)}):")
                print("=" * 60)
                print(f"{'#':<3}{'Name':<20}{'Username':<15}{'Role':<10}{'Joined':<12}")
                print("-" * 60)
                
                for i, member in enumerate(members, 1):
                    role = "Admin" if member['is_admin'] else "Member"
                    joined_date = member['joined_at'][:10]  # Just the date
                    print(f"{i:<3}{member['full_name']:<20}{member['username']:<15}{role:<10}{joined_date:<12}")
            else:
                print("Could not retrieve members list.")
            
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            # Invite user
            print("\nInvite User to Room:")
            username = input("Enter username to invite: ").strip()
            if username:
                from .admin import search_users  # Local import to avoid circular dependency

                # Search for user
                user_list = search_users(dashboard.auth, username)
                if user_list:
                    if len(user_list) == 1:
                        user = user_list[0]
                    else:
                        print(f"Found {len(user_list)} users:")
                        for i, u in enumerate(user_list[:5], 1):
                            print(f"{i}. {u['full_name']} (@{u['username']}) - {u['email']}")
                        
                        try:
                            choice_num = int(input("Select user number: "))
                            if 1 <= choice_num <= len(user_list):
                                user = user_list[choice_num - 1]
                            else:
                                print("Invalid selection.")
                                continue
                        except ValueError:
                            print("Invalid selection.")
                            continue
                    
                    # Send invitation
                    result = dashboard.invite_user_to_room(room_id, user['id'])
                    if result == True:
                        print(f"✅ Invitation sent to {user['username']}")
                    elif result == "already_member":
                        print(f"{user['username']} is already a member")
                    elif result == "already_invited":
                        print(f"{user['username']} already has a pending invitation")
                    else:
                        print(f"❌ Failed to invite {user['username']}")
                else:
                    print(f"User '{username}' not found")
            
            input("\nPress Enter to continue...")
            
        elif choice == '3':
            # Remove member
            username = input("Enter username to remove: ").strip()
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
                        print(f"✓ {username} removed from room")
                        log_event('info', f"User {username} removed from room {room_id}")
                    else:
                        print(f"❌ Failed to remove {username}")
                else:
                    print(f"User '{username}' not found")

            input("\nPress Enter to continue...")
            
        elif choice == '4':
            # Promote/demote member
            username = input("Enter username to promote/demote: ").strip()
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
                    print(f"\nCurrent role: {current_role}")
                    print("1. Promote to moderator")
                    print("2. Demote to member")
                    role_choice = input("Select option: ").strip()

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
                            print(f"✓ {username} is now a {new_role}")
                            log_event('info', f"User {username} role changed to {new_role} in room {room_id}")
                        else:
                            print(f"❌ Failed to update role")
                    else:
                        print("No change made")
                else:
                    print(f"User '{username}' not found in this room")

            input("\nPress Enter to continue...")
            
        elif choice == '5':
            # View recent messages
            messages_data = dashboard.get_chat_messages(room_id, page=1, limit=20)
            
            if messages_data['messages']:
                print(f"\nRecent Messages ({messages_data['total_count']} total):")
                print("=" * 70)
                
                for msg in messages_data['messages']:
                    timestamp = msg['sent_at'][:16]
                    print(f"[{timestamp}] {msg['sender']}: {msg['content']}")
            else:
                print("No messages in this room yet.")
            
            input("\nPress Enter to continue...")
            
        elif choice == '6':
            # Room settings
            print("\n--- Room Settings ---")
            print("1. Change room name")
            print("2. Change room description")
            print("3. Toggle room privacy")
            print("4. Back")
            settings_choice = input("\nSelect option: ").strip()

            if settings_choice == '1':
                new_name = input("Enter new room name: ").strip()
                if new_name:
                    def update_name(cursor):
                        cursor.execute('UPDATE chat_rooms SET name = ? WHERE id = ?', (new_name, room_id))
                        return cursor.rowcount > 0

                    if execute_db_operation(update_name):
                        print(f"✓ Room name updated to '{new_name}'")
                        log_event('info', f"Room {room_id} name changed to {new_name}")
                    else:
                        print("❌ Failed to update name")

            elif settings_choice == '2':
                new_desc = input("Enter new description: ").strip()
                if new_desc:
                    def update_desc(cursor):
                        cursor.execute('UPDATE chat_rooms SET description = ? WHERE id = ?', (new_desc, room_id))
                        return cursor.rowcount > 0

                    if execute_db_operation(update_desc):
                        print(f"✓ Room description updated")
                        log_event('info', f"Room {room_id} description updated")
                    else:
                        print("❌ Failed to update description")

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
                    status = "private" if new_privacy else "public"
                    print(f"✓ Room is now {status}")
                    log_event('info', f"Room {room_id} privacy changed to {status}")
                else:
                    print("❌ Failed to toggle privacy")

            input("\nPress Enter to continue...")
            
        elif choice == '7':
            break
        else:
            print("Invalid choice. Please try again.")



def display_all_rooms_admin(dashboard):
    """Admin view of all chat rooms"""
    page = 1
    limit = 15
    
    while True:
        rooms_data = dashboard.get_chat_rooms('all', page, limit)
        
        if rooms_data['total_count'] == 0:
            print("\nNo chat rooms found.")
            input("Press Enter to continue...")
            break
        
        print(f"\nAll Chat Rooms - Admin View ({rooms_data['total_count']} total):")
        print("=" * 100)
        print(f"{'#':<3}{'Room Name':<20}{'Type':<10}{'Creator':<15}{'Members':<8}{'Messages':<8}{'Your Role':<10}")
        print("-" * 100)
        
        for i, room in enumerate(rooms_data['rooms'], 1):
            role = "Admin" if room['is_admin'] else ("Member" if room['is_admin'] is not None else "Not Member")
            print(f"{i:<3}{room['name']:<20}{room['room_type']:<10}{room['creator']:<15}{room['member_count']:<8}{room['message_count']:<8}{role:<10}")
        
        print(f"\nPage {rooms_data['page']} of {rooms_data['total_pages']}")
        
        print("\nOptions:")
        print("1. View room details")
        print("2. Join room")
        print("3. Enter room")
        print("4. Next page") if page < rooms_data['total_pages'] else print("4. (No more pages)")
        print("5. Previous page") if page > 1 else print("5. (First page)")
        print("6. Back to Chat Rooms Menu")
        
        choice = input("Enter choice: ")
        
        if choice == '1':
            # View room details
            try:
                room_num = int(input("Enter room number: "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    
                    print(f"\nRoom Details:")
                    print("=" * 50)
                    print(f"ID: {room['id']}")
                    print(f"Name: {room['name']}")
                    print(f"Type: {room['room_type']}")
                    print(f"Description: {room['description'] or 'No description'}")
                    print(f"Creator: {room['creator']}")
                    print(f"Created: {room['created_at']}")
                    print(f"Members: {room['member_count']}")
                    print(f"Messages: {room['message_count']}")
                    print(f"Your Role: {('Admin' if room['is_admin'] else 'Member') if room['is_admin'] is not None else 'Not a member'}")
                    
                    input("\nPress Enter to continue...")
                else:
                    print("Invalid room number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '2':
            # Join room
            try:
                room_num = int(input("Enter room number to join: "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    
                    if room['is_admin'] is not None:
                        print("You are already a member of this room.")
                    else:
                        result = dashboard.join_chat_room(room['id'])
                        if result == True:
                            print(f"✅ Successfully joined room '{room['name']}'!")
                        elif result == "already_member":
                            print("You are already a member of this room.")
                        else:
                            print("❌ Failed to join room.")
                else:
                    print("Invalid room number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '3':
            # Enter room
            try:
                room_num = int(input("Enter room number: "))
                if 1 <= room_num <= len(rooms_data['rooms']):
                    room = rooms_data['rooms'][room_num - 1]
                    
                    if room['is_admin'] is not None:
                        enter_chat_room(dashboard, room['id'], room['name'])
                    else:
                        print("You must be a member to enter this room.")
                else:
                    print("Invalid room number.")
            except ValueError:
                print("Please enter a valid number.")
                
        elif choice == '4' and page < rooms_data['total_pages']:
            page += 1
            
        elif choice == '5' and page > 1:
            page -= 1
            
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")



@handle_exception
def display_chat_rooms_menu(dashboard):
    """Main chat rooms menu"""
    while True:
        print("\nChat Rooms:")
        print("===========")
        
        # Check for pending invitations
        pending_invitations = dashboard.get_pending_invitations()
        if pending_invitations:
            print(f"🔔 You have {len(pending_invitations)} pending room invitation(s)")
        
        print("1. My Chat Rooms")
        print("2. Public Rooms")
        print("3. Create New Room")
        print("4. Room Invitations")
        if dashboard.auth.current_user['role'] == 'admin':
            print("5. All Rooms (Admin)")
            print("6. Back to Communication Dashboard")
        else:
            print("5. Back to Communication Dashboard")
        
        choice = input("Enter your choice: ")
        
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
            print("Invalid choice. Please try again.")
