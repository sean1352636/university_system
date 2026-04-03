"""
Chatbot integration for CLI system.

This module handles the university chatbot integration, conversation management,
and chatbot administration features.
"""

from education_system.university_system.modules.shared.cli.imports import (
    logging, time, datetime, DB_PATH, _t, logger,
    log_activity
)

from education_system.university_system.infrastructure.database.db import sqlite3
class ValidationError(Exception):
    pass

class DatabaseError(Exception):
    pass

# Global chatbot instance
chatbot_instance = None
auth = None

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

def initialize_chatbot_integration() -> bool:
    """Initialize chatbot with authentication integration"""
    global chatbot_instance
    try:
        # Import the chatbot from the ai module
        from education_system.university_system.utils.ai.university_chatbot import UniversityChatbot

        # Initialize chatbot with database path
        chatbot_instance = UniversityChatbot(db_path=DB_PATH)

        # Set authentication system
        if auth:
            chatbot_instance.auth_system = auth
            print("✅ Chatbot integrated with authentication system")

        return True
    except ImportError as e:
        print(f"⚠️ Chatbot module not available: {e}")
        return False
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Chatbot initialization failed: {e}")
        return False

def display_chatbot_menu() -> None:
    """Display chatbot menu with authentication"""
    global auth, chatbot_instance

    if not auth or not auth.current_user:
        print(_t("cli.chatbot.login_required"))
        return

    if not auth.check_permission('access_chatbot'):
        print(_t("cli.chatbot.no_permission"))
        return

    # Initialize chatbot if not already done
    if not chatbot_instance:
        if not initialize_chatbot_integration():
            print(_t("cli.chatbot.not_available"))
            return

    while True:
        print(f"\n" + _t("cli.chatbot.title"))
        print(_t("cli.logged_in_as").format(user=auth.current_user['username'], role=auth.current_user['role']))
        print("=" * 50)
        print("1. " + _t("cli.chatbot.start_session"))
        print("2. " + _t("cli.chatbot.view_history"))
        if auth.check_permission('view_all_conversations'):
            print("3. " + _t("cli.chatbot.view_all_admin"))
        if auth.check_permission('chatbot_admin'):
            print("4. " + _t("cli.chatbot.administration"))
        print("5. " + _t("common.back"))

        choice = input("\n" + _t("common.enter_choice") + ": ")

        if choice == '1':
            start_chat_session()
        elif choice == '2':
            view_conversation_history()
        elif choice == '3' and auth.check_permission('view_all_conversations'):
            view_all_conversations()
        elif choice == '4' and auth.check_permission('chatbot_admin'):
            chatbot_administration()
        elif choice == '5':
            break
        else:
            print(_t("common.invalid_choice"))

def start_chat_session():
    """Start interactive chat session"""
    global auth, chatbot_instance

    if not chatbot_instance:
        print(_t("cli.chatbot.not_available"))
        return

    user = auth.current_user
    print(f"\n" + _t("cli.chatbot.session_started"))
    print(_t("cli.chatbot.type_exit"))
    print("=" * 40)

    session_id = f"{user['username']}_{int(time.time())}"

    while True:
        try:
            user_input = input(f"\n{user['username']}: ")

            if user_input.lower() in ['exit', 'quit', 'bye']:
                print(_t("cli.chatbot.goodbye"))
                break

            if not user_input.strip():
                continue

            # Process message through chatbot
            response = chatbot_instance.process_message(
                user_input,
                user['username'],
                session_id=session_id
            )

            print(f"Chatbot: {response}")

            # Log conversation
            log_chatbot_conversation(
                user['id'],
                user['username'],
                user_input,
                response,
                session_id
            )

        except KeyboardInterrupt:
            print("\nChat session ended.")
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"Error: {e}")

def log_chatbot_conversation(user_id, username, message, response, session_id, intent=None):
    """Log chatbot conversation to database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO chatbot_conversations
        (user_id, username, message, response, intent, timestamp, session_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, message, response, intent, timestamp, session_id))

        conn.commit()
        conn.close()
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Database error logging conversation: {e}")

def view_conversation_history():
    """View user's conversation history"""
    global auth

    user = auth.current_user

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get user's conversations
        if auth.check_permission('view_all_conversations'):
            cursor.execute('''
            SELECT username, message, response, timestamp
            FROM chatbot_conversations
            ORDER BY timestamp DESC
            LIMIT 50
            ''')
        else:
            cursor.execute('''
            SELECT username, message, response, timestamp
            FROM chatbot_conversations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 20
            ''', (user['id'],))

        conversations = cursor.fetchall()
        conn.close()

        if not conversations:
            print("No conversation history found.")
            return

        print(f"\nConversation History:")
        print("=" * 60)

        for i, (username, message, response, timestamp) in enumerate(conversations, 1):
            print(f"{i}. [{timestamp}] {username}")
            print(f"   Q: {message[:60]}{'...' if len(message) > 60 else ''}")
            print(f"   A: {response[:60]}{'...' if len(response) > 60 else ''}")
            print()

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Database error retrieving conversation history: {e}")

def view_all_conversations():
    """View all users' conversations (admin only)"""
    print("\nAll User Conversations:")
    print("=" * 50)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT username, COUNT(*) as conversation_count,
               MAX(timestamp) as last_conversation
        FROM chatbot_conversations
        GROUP BY username
        ORDER BY last_conversation DESC
        ''')

        stats = cursor.fetchall()

        for username, count, last_conv in stats:
            print(f"{username}: {count} conversations (Last: {last_conv})")

        conn.close()
    except (sqlite3.Error, DatabaseError) as e:
        print(f"Database error retrieving conversations: {e}")

def chatbot_administration():
    """Chatbot administration menu"""
    while True:
        print("\nChatbot Administration:")
        print("1. View Usage Statistics")
        print("2. Clear Conversation History")
        print("3. Restart Chatbot")
        print("4. Back")

        choice = input("Enter choice: ")

        if choice == '1':
            show_chatbot_statistics()
        elif choice == '2':
            clear_conversation_history()
        elif choice == '3':
            restart_chatbot()
        elif choice == '4':
            break

def show_chatbot_statistics():
    """Show chatbot usage statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Total conversations
        cursor.execute('SELECT COUNT(*) FROM chatbot_conversations')
        total_conversations = cursor.fetchone()[0]

        # Unique users
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM chatbot_conversations')
        unique_users = cursor.fetchone()[0]

        # Conversations by date (last 7 days)
        cursor.execute('''
        SELECT DATE(timestamp) as date, COUNT(*) as count
        FROM chatbot_conversations
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY DATE(timestamp)
        ORDER BY date
        ''')
        daily_stats = cursor.fetchall()

        print(f"\nChatbot Statistics:")
        print(f"Total Conversations: {total_conversations}")
        print(f"Unique Users: {unique_users}")
        print(f"\nDaily Activity (Last 7 days):")
        for date, count in daily_stats:
            print(f"  {date}: {count} conversations")

        conn.close()
    except (sqlite3.Error, DatabaseError) as e:
        print(f"Database error retrieving statistics: {e}")

def clear_conversation_history():
    """Clear conversation history"""
    confirm = input("Are you sure you want to clear all conversation history? (yes/no): ")
    if confirm.lower() == 'yes':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM chatbot_conversations')
            conn.commit()
            conn.close()
            print("Conversation history cleared.")
        except (sqlite3.Error, DatabaseError) as e:
            print(f"Database error clearing history: {e}")

def restart_chatbot():
    """Restart chatbot instance"""
    global chatbot_instance
    chatbot_instance = None
    if initialize_chatbot_integration():
        print("Chatbot restarted successfully.")
    else:
        print("Failed to restart chatbot.")

def setup_chatbot_permissions():
    """Setup chatbot-specific permissions"""
    global auth
    if not auth:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Chatbot permissions
        chatbot_permissions = [
            ('access_chatbot', 'Access University Chatbot'),
            ('chatbot_admin', 'Administer Chatbot System'),
            ('view_all_conversations', 'View All Chatbot Conversations'),
            ('voice_interaction', 'Use Voice Interface')
        ]

        # Add permissions if they don't exist
        for perm_name, perm_desc in chatbot_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )

        # Assign permissions to roles
        role_permissions = {
            'admin': ['access_chatbot', 'chatbot_admin', 'view_all_conversations', 'voice_interaction'],
            'staff': ['access_chatbot', 'voice_interaction'],
            'instructor': ['access_chatbot', 'voice_interaction'],
            'student': ['access_chatbot', 'voice_interaction'],
            'parent': ['access_chatbot']
        }

        for role_name, permissions in role_permissions.items():
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if role_result:
                role_id = role_result[0]

                for perm_name in permissions:
                    cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                    perm_result = cursor.fetchone()
                    if perm_result:
                        perm_id = perm_result[0]
                        cursor.execute(
                            'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                            (role_id, perm_id)
                        )

        conn.commit()
        conn.close()
        print("✅ Chatbot permissions configured")

    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error setting up chatbot permissions: {e}")

def launch_chatbot():
    from education_system.university_system.utils.ai.university_chatbot import UniversityChatbot
    chatbot = UniversityChatbot()
    chatbot.run()

__all__ = [
    'initialize_chatbot_integration',
    'display_chatbot_menu',
    'start_chat_session',
    'log_chatbot_conversation',
    'view_conversation_history',
    'view_all_conversations',
    'chatbot_administration',
    'show_chatbot_statistics',
    'clear_conversation_history',
    'restart_chatbot',
    'setup_chatbot_permissions',
    'launch_chatbot',
]
