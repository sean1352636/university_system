"""
Chatbot integration for CLI system.

This module handles the university chatbot integration, conversation management,
and chatbot administration features.
"""

from education_system.systems.university.shell.cli.imports import (
    logging, time, datetime, DB_PATH, _t, logger,
    log_activity
)

from education_system.systems.university.infrastructure.database.db import sqlite3
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
        from education_system.systems.university.shared.ai.chatbot import UniversityChatbot

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

def get_chatbot_instance():
    """The CLI's chatbot, started on first use (``None`` when unavailable)."""
    if chatbot_instance is None:
        initialize_chatbot_integration()
    return chatbot_instance


def display_chatbot_menu() -> None:
    """Display chatbot menu with authentication"""
    global auth, chatbot_instance

    if not auth or not auth.current_user:
        print(_t("cli.chatbot.login_required"))
        return

    if not auth.check_permission('use_chat_rooms'):
        print(_t("cli.chatbot.no_permission"))
        return

    # Initialize chatbot if not already done
    if not chatbot_instance:
        if not initialize_chatbot_integration():
            print(_t("cli.chatbot.not_available"))
            return

    from education_system.systems.university.shell.cli.ai import chatbot_care_menu as care_menu

    while True:
        staff_tools = care_menu.has_staff_role(auth)
        print("\n" + _t("cli.chatbot.title"))
        print(_t("cli.logged_in_as").format(user=auth.current_user['username'], role=auth.current_user['role']))
        print("=" * 50)
        print("1. " + _t("cli.chatbot.start_session"))
        print("2. Quick Actions Menu")
        print("3. " + _t("cli.chatbot.view_history"))
        print("4. Support & privacy (speak to a person, my questions, download / delete)")
        if staff_tools:
            print("5. Chatbot staff tools")
        if auth.check_permission('manage_ai_features'):
            print("6. " + _t("cli.chatbot.administration"))
        print("0. " + _t("common.back"))

        choice = input("\n" + _t("common.enter_choice") + ": ").strip()

        if choice == '1':
            start_chat_session()
        elif choice == '2':
            quick_actions_menu()
        elif choice == '3':
            view_conversation_history()
        elif choice == '4':
            care_menu.self_service_menu(chatbot_instance, auth)
        elif choice == '5' and staff_tools:
            care_menu.staff_menu(auth)
        elif choice == '6' and auth.check_permission('manage_ai_features'):
            chatbot_administration()
        elif choice in ('0', '7'):
            break
        else:
            print(_t("common.invalid_choice"))

def quick_actions_menu():
    """Quick actions menu for common chatbot queries."""
    global auth, chatbot_instance

    if not chatbot_instance:
        print("Chatbot not available.")
        return

    user = auth.current_user
    session_id = f"{user['username']}_{int(time.time())}"

    actions = {
        # Student Services
        '1': ("My Courses", "What courses am I enrolled in?"),
        '2': ("My Grades / GPA", "What is my GPA and recent grades?"),
        '3': ("Timetable / Schedule", "Show my timetable"),
        '4': ("Fee Balance", "What is my fee balance?"),
        '5': ("Financial Aid Status", "What is my financial aid status?"),
        '6': ("Request Transcript", "How do I request a transcript or enrollment certificate?"),
        # Academic Support
        '7': ("Upcoming Deadlines", "What are my upcoming deadlines?"),
        '8': ("Exam Schedule", "What is my exam schedule?"),
        '9': ("Library Search", None),  # special — prompts for query
        '10': ("Academic Calendar", "Show the academic calendar"),
        # Admissions & Admin
        '11': ("Application Status", "What is my application status?"),
        '12': ("Staff Directory Search", None),  # special — prompts for query
        '13': ("Room Booking Info", "How do I book a room?"),
        '14': ("ID Card Replacement", "How do I replace my ID card?"),
        '15': ("Leave of Absence", "How do I apply for a leave of absence?"),
        # Wellbeing & Campus Life
        '16': ("Mental Health Resources", "What mental health support is available?"),
        '17': ("Clubs & Societies", "What clubs and societies are available?"),
        '18': ("Lost & Found", "Show lost and found items"),
        '19': ("Transport Schedule", "What is the shuttle schedule?"),
        '20': ("Campus Events", "What events are happening on campus?"),
    }

    while True:
        print("\nQuick Actions")
        print("=" * 50)
        print("\n  Student Services:")
        for k in ['1', '2', '3', '4', '5', '6']:
            print(f"    {k:>2}. {actions[k][0]}")
        print("\n  Academic Support:")
        for k in ['7', '8', '9', '10']:
            print(f"    {k:>2}. {actions[k][0]}")
        print("\n  Admissions & Admin:")
        for k in ['11', '12', '13', '14', '15']:
            print(f"    {k:>2}. {actions[k][0]}")
        print("\n  Wellbeing & Campus Life:")
        for k in ['16', '17', '18', '19', '20']:
            print(f"    {k:>2}. {actions[k][0]}")
        print("\n    0. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break

        if choice not in actions:
            print("Invalid choice.")
            continue

        label, query = actions[choice]

        # Special cases that need user input
        if choice == '9':
            search_term = input("Enter library search term: ").strip()
            if not search_term:
                print("No search term provided.")
                continue
            query = f"Search library for {search_term}"
        elif choice == '12':
            search_term = input("Enter name or department to search: ").strip()
            if not search_term:
                print("No search term provided.")
                continue
            query = f"Find {search_term} in staff directory"

        print(f"\n--- {label} ---")
        try:
            response = chatbot_instance.process_message(
                query, user['username'], session_id=session_id
            )
            print(f"Chatbot: {response}")
            # The chatbot logs each turn itself (with retention); rate it here.
            from education_system.systems.university.shell.cli.ai import chatbot_care_menu
            chatbot_care_menu.ask_feedback(chatbot_instance, user['username'])
        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")


def start_chat_session():
    """Start interactive chat session"""
    global auth, chatbot_instance

    if not chatbot_instance:
        print(_t("cli.chatbot.not_available"))
        return

    from education_system.systems.university.shell.cli.ai import chatbot_care_menu as care_menu

    user = auth.current_user
    print("\n" + _t("cli.chatbot.session_started"))
    print(_t("cli.chatbot.type_exit"))
    print("Type 'person' to ask a member of staff, 'feedback off' to stop being asked to rate "
          "answers.")
    print("=" * 40)
    care_menu.show_privacy_notice(user['username'])

    session_id = f"{user['username']}_{int(time.time())}"
    rate = True

    while True:
        try:
            user_input = input(f"\n{user['username']}: ")

            if user_input.lower() in ['exit', 'quit', 'bye']:
                print(_t("cli.chatbot.goodbye"))
                break

            if not user_input.strip():
                continue
            if user_input.strip().lower() == 'feedback off':
                rate = False
                print("OK, I won't ask about answers.")
                continue
            if user_input.strip().lower() in ('person', 'speak to a person', 'human'):
                care_menu.speak_to_person(chatbot_instance, user['username'])
                continue

            # The chatbot logs each turn itself (database, with retention).
            response = chatbot_instance.process_message(
                user_input,
                user['username'],
                session_id=session_id
            )

            print(f"Chatbot: {response}")
            if rate:
                care_menu.ask_feedback(chatbot_instance, user['username'])

        except KeyboardInterrupt:
            print("\nChat session ended.")
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"Error: {e}")

def log_chatbot_conversation(user_id, username, message, response, session_id, intent=None):
    """Log a turn through the chatbot log (database, retention, export,
    erasure). The chatbot already logs what it answers; this is for callers
    outside it."""
    from education_system.systems.university.application.chatbot import (
        knowledge as chatbot_knowledge,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        row_id = chatbot_knowledge.log_turn(conn, username, message, response, intent=intent,
                                            session_id=session_id)
        conn.commit()
        return row_id
    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"Database error logging conversation: {e}")
        return None
    finally:
        conn.close()

def view_conversation_history():
    """The signed-in person's own conversation history (no one reads anyone
    else's conversations here)."""
    from education_system.systems.university.application.chatbot import (
        knowledge as chatbot_knowledge,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection

    user = auth.current_user
    conn = get_connection(row_factory=False)
    try:
        conversations = chatbot_knowledge.history(conn, user['username'], 20)
        conn.commit()
    finally:
        conn.close()

    if not conversations:
        print("No conversation history found.")
        return

    print("\nYour Conversation History:")
    print("=" * 60)
    for i, c in enumerate(conversations, 1):
        message, response = c['message'] or '', c['response'] or ''
        print(f"{i}. [{c['timestamp']}]")
        print(f"   Q: {message[:60]}{'...' if len(message) > 60 else ''}")
        print(f"   A: {response[:60]}{'...' if len(response) > 60 else ''}")
        print()

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
        print("2. Delete Conversations Past Retention")
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
    """Chatbot usage figures (no message content)."""
    from education_system.systems.university.application.chatbot import (
        knowledge as chatbot_knowledge,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        stats = chatbot_knowledge.stats(conn)
        daily = conn.execute(
            "SELECT DATE(timestamp), COUNT(*) FROM chatbot_conversations WHERE timestamp >= "
            "datetime('now', '-7 days') GROUP BY DATE(timestamp) ORDER BY 1").fetchall()
        users = conn.execute("SELECT COUNT(DISTINCT username) FROM chatbot_conversations"
                             ).fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    print("\nChatbot Statistics:")
    print(f"Conversation turns kept: {stats['turns']}")
    print(f"People: {users}")
    print(f"Answered: {stats['answered_pct'] if stats['answered_pct'] is not None else '—'}%")
    print(f"Rated helpful: {stats['helpful_pct'] if stats['helpful_pct'] is not None else '—'}% "
          f"of {stats['ratings']} rating(s)")
    print(f"Open cases: {stats['open_cases']}   Unanswered questions: {stats['open_unanswered']}")
    print("\nDaily Activity (Last 7 days):")
    for day, count in daily:
        print(f"  {day}: {count} turns")


def clear_conversation_history():
    """Delete conversations past the retention period. (This used to delete
    every conversation, including ones a safeguarding case rests on.)"""
    from education_system.systems.university.application.chatbot import (
        knowledge as chatbot_knowledge,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    confirm = input("Delete conversations older than the retention period? (yes/no): ")
    if confirm.lower() != 'yes':
        return
    conn = get_connection(row_factory=False)
    try:
        gone = chatbot_knowledge.purge(conn)
        conn.commit()
        print(f"Deleted {gone} conversation turn(s) past the retention period.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error: {e}")
    finally:
        conn.close()

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
    from education_system.systems.university.shared.ai.chatbot import UniversityChatbot
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
