"""
Chatbot Integration Module

This module handles the integration of the University Chatbot with the authentication system.
It provides chatbot initialization, session management, conversation tracking, and analytics.

Functions:
    - initialize_chatbot_integration(): Initialize chatbot integration
    - _create_fallback_chatbot(): Create minimal fallback chatbot
    - setup_chatbot_permissions(): Setup chatbot-specific permissions
    - create_chatbot_session(): Create chatbot session for authenticated users
    - get_chatbot_conversation_history(): Retrieve conversation history
    - generate_chatbot_analytics(): Generate usage analytics
    - launch_chatbot_interface(): Launch chatbot interface
    - display_chatbot_integration_menu(): Display chatbot CLI menu
    - test_chatbot_integration(): Test chatbot integration
    - create_sample_chatbot_data(): Create sample chatbot data
    - process_message(): Process chatbot messages (standalone function)
"""

import logging
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Import optional dependencies
from university_system.infrastructure.auth.optional_dependencies import (
    get_chatbot_class,
    is_chatbot_available,
    OptionalDependencyError,
)

# Check availability
CHATBOT_AVAILABLE = is_chatbot_available()

# Import UniversityChatbot class if available
UniversityChatbot = None
if CHATBOT_AVAILABLE:
    try:
        UniversityChatbot = get_chatbot_class()
        logger.info("Chatbot module is available")
    except (ImportError, OptionalDependencyError, AttributeError) as e:
        logger.warning(f"Failed to get chatbot class: {e}")
        CHATBOT_AVAILABLE = False
else:
    logger.info("Chatbot module not available - feature will be disabled")

def initialize_chatbot_integration(auth_instance):
    """Initialize chatbot integration with comprehensive error handling
    
    Args:
        auth_instance: UserAuth instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    if CHATBOT_AVAILABLE:
        try:
            print("Initializing chatbot integration...")
            auth_instance.chatbot = UniversityChatbot(db_path=auth_instance.db_path)
            
            # Verify the chatbot has required attributes
            required_attrs = ['app', 'config', 'conversation_history', 'auth_system']
            missing_attrs = [attr for attr in required_attrs if not hasattr(auth_instance.chatbot, attr)]
            
            if missing_attrs:
                print(f"⚠️ Chatbot missing attributes: {missing_attrs}")
                # Add missing attributes
                for attr in missing_attrs:
                    setattr(auth_instance.chatbot, attr, None)
            
            auth_instance.chatbot.set_auth_system(auth_instance)
            logger.info("Chatbot integration initialized successfully")
            return True

        except (ImportError, OptionalDependencyError) as e:
            print(f"⚠️ Chatbot module not available: {e}")
            _create_fallback_chatbot(auth_instance)
            return False
        except (AttributeError, TypeError) as e:
            print(f"⚠️ Chatbot integration failed (attribute error): {e}")
            logger.debug(f"Error type: {type(e).__name__}")
            _create_fallback_chatbot(auth_instance)
            return False
        except sqlite3.Error as e:
            print(f"⚠️ Chatbot integration failed (database error): {e}")
            _create_fallback_chatbot(auth_instance)
            return False
    else:
        print("Chatbot module not available")
        auth_instance.chatbot = None
        return False

def _create_fallback_chatbot(auth_instance):
    """Create a minimal fallback chatbot
    
    Args:
        auth_instance: UserAuth instance
    """
    class FallbackChatbot:
        def __init__(self):
            self.enabled = False
        
        def process_message(self, msg, user, session_id=None, voice=False):
            return "Chatbot temporarily unavailable. Please try again later."
        
        def run_authenticated_console_interface(self):
            print("Chatbot is currently unavailable.")
        
        def set_auth_system(self, auth):
            """Set the authentication system reference"""
            self.auth_system = auth
        
        def get_conversation_history(self, user, limit=10):
            return []
    
    auth_instance.chatbot = FallbackChatbot()
    logger.info("Fallback chatbot created")

def setup_chatbot_permissions(auth_instance):
    """Setup chatbot-specific permissions in the database
    
    Args:
        auth_instance: UserAuth instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with auth_instance.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Chatbot permissions
            chatbot_permissions = [
                ('access_chatbot', 'Access University Chatbot'),
                ('chatbot_admin', 'Administer Chatbot System'),
                ('view_all_conversations', 'View All Chatbot Conversations'),
                ('voice_interaction', 'Use Voice Interface with Chatbot')
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
            
            for role_name in role_permissions:
                cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
                role_result = cursor.fetchone()
                if role_result:
                    role_id = role_result[0]
                    
                    for perm_name in role_permissions[role_name]:
                        cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                        perm_result = cursor.fetchone()
                        if perm_result:
                            perm_id = perm_result[0]
                            cursor.execute(
                                'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                (role_id, perm_id)
                            )
            
            conn.commit()
            logger.info("Chatbot permissions configured")
            return True

    except sqlite3.Error as e:
        logger.error(f"Database error setting up chatbot permissions: {e}")
        return False
    except (KeyError, TypeError) as e:
        logger.error(f"Configuration error setting up chatbot permissions: {e}")
        return False

def create_chatbot_session(auth_instance, username: str) -> Optional[str]:
    """Create a chatbot session for authenticated user
    
    Args:
        auth_instance: UserAuth instance
        username: Username to create session for
        
    Returns:
        Optional[str]: Session token if successful, None otherwise
    """
    if not auth_instance.current_user or auth_instance.current_user['username'] != username:
        return None
    
    if not auth_instance.check_permission('access_chatbot'):
        return None
    
    # Generate session token
    import secrets
    session_token = secrets.token_hex(32)
    
    # Log chatbot session creation
    auth_instance._log_activity(username, 'Chatbot session created', f'Token: {session_token[:8]}...', auth_instance.current_user['id'])
    
    return session_token

def get_chatbot_conversation_history(auth_instance, username: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get chatbot conversation history for a user - IMPROVED VERSION
    
    Args:
        auth_instance: UserAuth instance
        username: Username to get history for
        limit: Maximum number of conversations to return
        
    Returns:
        List[Dict[str, Any]]: List of conversation entries
    """
    if not auth_instance.current_user:
        return []
    
    # Check permissions
    can_view = False
    if auth_instance.current_user['username'] == username:
        can_view = True
    elif 'view_all_conversations' in auth_instance.current_user['permissions']:
        can_view = True
    elif 'view_student_conversations' in auth_instance.current_user['permissions']:
        can_view = True
    
    if not can_view:
        return []
    
    conversations = []
    
    # First, try to get from activity_log (most reliable)
    try:
        with auth_instance.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, action, details
                FROM activity_log
                WHERE username = ? AND action = 'Chatbot interaction'
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (username, limit))
            
            for row in cursor.fetchall():
                timestamp, action, details = row
                
                # Extract message and response from details if possible
                message_text = "Chat interaction"
                if details:
                    try:
                        # Try to parse "Q: ... A: ..." format
                        if 'Q:' in details and 'A:' in details:
                            parts = details.split('A:')
                            if len(parts) >= 1:
                                q_part = parts[0].replace('Q:', '').strip()
                                message_text = q_part[:100] + '...' if len(q_part) > 100 else q_part
                        else:
                            message_text = details[:50] + '...' if len(details) > 50 else details
                    except (IndexError, AttributeError, TypeError) as e:
                        logger.warning(f"Failed to parse chat details: {e}")
                        message_text = "Chat interaction"
                
                conversations.append({
                    'timestamp': timestamp,
                    'message': message_text,
                    'details': details or 'Chatbot interaction',
                    'type': 'database'
                })

    except sqlite3.Error as e:
        logger.error(f"Database error getting conversation history: {e}")
    
    # Also get from chatbot's in-memory history if available
    try:
        if hasattr(auth_instance, 'chatbot') and auth_instance.chatbot and hasattr(auth_instance.chatbot, 'conversation_history'):
            user_history = auth_instance.chatbot.conversation_history.get(username, [])
            for conv in user_history:
                conversations.append({
                    'timestamp': conv.get('timestamp', 'Recent'),
                    'message': conv.get('message', 'N/A'),
                    'response': conv.get('response', 'N/A'),
                    'type': 'session'
                })
    except Exception as e:
        logger.error(f"Session history error: {e}")

    # Sort by timestamp and return most recent
    try:
        conversations.sort(key=lambda x: x['timestamp'], reverse=True)
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Failed to sort conversations by timestamp: {e}")
        logger.debug("Returning unsorted conversations")

    return conversations[:limit]

def generate_chatbot_analytics(auth_instance) -> Dict[str, Any]:
    """Generate chatbot usage analytics
    
    Args:
        auth_instance: UserAuth instance
        
    Returns:
        Dict[str, Any]: Analytics data
    """
    if not auth_instance.current_user or 'chatbot_admin' not in auth_instance.current_user['permissions']:
        return {}
    
    try:
        with auth_instance.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total interactions
            cursor.execute('SELECT COUNT(*) FROM chatbot_conversations')
            total_interactions = cursor.fetchone()[0]
            
            # Unique users
            cursor.execute('SELECT COUNT(DISTINCT username) FROM chatbot_conversations')
            unique_users = cursor.fetchone()[0]
            
            # Recent activity (last 7 days)
            cursor.execute('''
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM chatbot_conversations
                WHERE timestamp >= datetime('now', '-7 days')
                GROUP BY DATE(timestamp)
                ORDER BY date
            ''')
            daily_interactions = dict(cursor.fetchall())
            
            return {
                'total_interactions': total_interactions,
                'unique_users': unique_users,
                'daily_interactions': daily_interactions,
                'status': 'active' if CHATBOT_AVAILABLE else 'limited',
                'generated_at': datetime.now().isoformat()
            }

    except sqlite3.Error as e:
        logger.error(f"Database error generating chatbot analytics: {e}")
        return {'error': str(e), 'error_type': 'database'}
    except (KeyError, TypeError) as e:
        logger.error(f"Data error generating chatbot analytics: {e}")
        return {'error': str(e), 'error_type': 'data'}

def launch_chatbot_interface(auth_instance):
    """Launch the chatbot interface for the current user
    
    Args:
        auth_instance: UserAuth instance
    """
    if not auth_instance.current_user:
        print("You must be logged in to access the chatbot.")
        return
    
    if not auth_instance.check_permission('access_chatbot'):
        print("You don't have permission to access the chatbot.")
        return
    
    if not auth_instance.chatbot:
        if not initialize_chatbot_integration(auth_instance):
            print("Chatbot is not available at this time.")
            return
    
    # Ensure chatbot has current auth context
    auth_instance.chatbot.set_auth_system(auth_instance)
    
    # Launch the interface
    auth_instance.chatbot.run_authenticated_console_interface()

def display_chatbot_integration_menu(auth):
    """Display chatbot integration menu
    
    Args:
        auth: UserAuth instance
    """
    while True:
        if not auth.check_session():
            return
        
        user = auth.current_user
        
        # Check if user has chatbot access
        if 'access_chatbot' not in user['permissions']:
            print("You don't have permission to access the chatbot.")
            return
        
        print("\nUniversity Chatbot Integration:")
        print("===============================")
        print(f"Logged in as: {user['username']} ({user['role']})")
        
        if CHATBOT_AVAILABLE:
            print("Status: ✅ Available")
        else:
            print("Status: ⚠️ Limited functionality")
        
        # Build menu based on permissions
        menu_options = []
        menu_options.append("1. Start Chatbot Session")
        menu_options.append("2. View My Conversation History")
        
        option_num = 3
        if 'chatbot_admin' in user['permissions']:
            menu_options.append(f"{option_num}. View Chatbot Analytics")
            analytics_option = option_num
            option_num += 1
        else:
            analytics_option = None
            
        if 'view_all_conversations' in user['permissions']:
            menu_options.append(f"{option_num}. View All User Conversations")
            all_conversations_option = option_num
            option_num += 1
        else:
            all_conversations_option = None
        
        menu_options.append(f"{option_num}. Test Chatbot Integration")
        test_option = option_num
        option_num += 1
        
        menu_options.append(f"{option_num}. Back")
        back_option = option_num
        
        # Display menu
        for option in menu_options:
            print(option)
        
        choice = input(f"\nEnter your choice (1-{back_option}): ")
        
        try:
            choice_num = int(choice)
        except ValueError:
            print("Invalid choice. Please enter a number.")
            continue
        
        if choice == '1':
            # Start chatbot session
            launch_chatbot_interface(auth)
        
        elif choice_num == 2:
            # View conversation history - FIXED VERSION
            try:
                history = get_chatbot_conversation_history(auth, user['username'])
                if history:
                    print(f"\nYour Chatbot Conversation History ({len(history)} interactions):")
                    print("=" * 60)
                    for i, conv in enumerate(history[:10], 1):
                        # Handle different conversation history formats
                        timestamp = conv.get('timestamp', 'Unknown time')
                        
                        # Try to extract message text from different possible structures
                        message_text = None
                        if 'message' in conv:
                            message_text = conv['message']
                        elif 'details' in conv:
                            # Extract from details field (activity log format)
                            details = conv['details']
                            if details and 'Q:' in details:
                                # Extract question from "Q: ... A: ..." format
                                try:
                                    message_text = details.split('Q:')[1].split('A:')[0].strip()
                                except (IndexError, AttributeError) as e:
                                    logger.debug(f"Failed to parse Q/A format: {e}")
                                    message_text = details[:40] if details else "Chat interaction"
                            else:
                                message_text = details[:40] if details else "Chat interaction"
                        else:
                            message_text = "Chat interaction"
                        
                        # Truncate message if too long
                        if message_text and len(message_text) > 40:
                            display_text = message_text[:40] + "..."
                        else:
                            display_text = message_text or "Chat interaction"
                        
                        print(f"{i}. {timestamp} - {display_text}")
                    
                    if len(history) > 10:
                        print(f"... and {len(history) - 10} more interactions")
                else:
                    print("No conversation history found. Start a chatbot session to begin!")
            
            except Exception as e:
                print(f"Error retrieving conversation history: {e}")
                print("No conversation history available at this time.")
        
        elif choice_num == analytics_option and analytics_option:
            # View analytics
            try:
                analytics = generate_chatbot_analytics(auth)
                if analytics and 'error' not in analytics:
                    print("\nChatbot Analytics:")
                    print("=" * 40)
                    print(f"Total Interactions: {analytics.get('total_interactions', 0)}")
                    if 'unique_users' in analytics:
                        print(f"Unique Users: {analytics.get('unique_users', 0)}")
                    if 'interactions_by_role' in analytics:
                        print(f"Interactions by Role: {analytics.get('interactions_by_role', {})}")
                    print(f"Status: {analytics.get('status', 'Active')}")
                    print(f"Generated: {analytics.get('generated_at', 'unknown')}")
                    
                    if analytics.get('daily_interactions'):
                        print("\nDaily Activity:")
                        for date, count in analytics['daily_interactions'].items():
                            print(f"  {date}: {count}")
                else:
                    print("No analytics data available or error occurred.")
            except Exception as e:
                print(f"Error generating analytics: {e}")
        
        elif choice_num == all_conversations_option and all_conversations_option:
            # View all conversations - FIXED VERSION
            print("\nAll User Conversations:")
            print("=" * 50)
            try:
                with auth.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Try to get from activity_log table (more likely to exist)
                    cursor.execute('''
                        SELECT username, COUNT(*) as count, MAX(timestamp) as last_chat
                        FROM activity_log
                        WHERE action = 'Chatbot interaction'
                        GROUP BY username
                        ORDER BY last_chat DESC
                        LIMIT 20
                    ''')
                    
                    all_conversations = cursor.fetchall()
                    if all_conversations:
                        print(f"{'Username':<15} {'Interactions':<12} {'Last Activity':<20}")
                        print("-" * 50)
                        for username, count, last_chat in all_conversations:
                            print(f"{username:<15} {count:<12} {last_chat:<20}")
                    else:
                        print("No conversations found in activity log.")
                        
                        # Try alternative table if it exists
                        try:
                            cursor.execute('''
                                SELECT name FROM sqlite_master 
                                WHERE type='table' AND name='chatbot_conversations'
                            ''')
                            if cursor.fetchone():
                                cursor.execute('''
                                    SELECT username, COUNT(*) as count, MAX(timestamp) as last_chat
                                    FROM chatbot_conversations
                                    GROUP BY username
                                    ORDER BY last_chat DESC
                                    LIMIT 20
                                ''')
                                alt_conversations = cursor.fetchall()
                                if alt_conversations:
                                    print("Found conversations in chatbot_conversations table:")
                                    for username, count, last_chat in alt_conversations:
                                        print(f"{username}: {count} conversations (Last: {last_chat})")
                                else:
                                    print("No conversations found in chatbot_conversations table either.")
                            else:
                                print("No chatbot-specific conversation tables found.")
                        except Exception as alt_e:
                            print(f"Error checking alternative tables: {alt_e}")
                            
            except Exception as e:
                print(f"Error retrieving conversations: {e}")
        
        elif choice_num == test_option:
            # Test integration
            test_chatbot_integration(auth)
        
        elif choice_num == back_option:
            return
        
        else:
            print("Invalid choice. Please try again.")

def process_message(chatbot_instance, message, user_id, is_voice=False):
    """Process a basic message with conversation tracking
    
    This is a standalone function that can be used as a fallback when full
    chatbot functionality is not available.
    
    Args:
        chatbot_instance: Chatbot or fallback instance
        message: User message
        user_id: User identifier
        is_voice: Whether this is a voice message
        
    Returns:
        str: Bot response
    """
    message_lower = message.lower()
    
    # Basic responses (keep existing logic)
    if any(word in message_lower for word in ['hello', 'hi', 'hey']):
        response = "Hello! I'm the University Chatbot. How can I help you today?"
    elif any(word in message_lower for word in ['course', 'class', 'program']):
        response = "I can help you with course information. What specific course or program are you interested in?"
    elif any(word in message_lower for word in ['grade', 'gpa', 'transcript']):
        response = "For grade information, please check your student portal or contact the registrar's office."
    elif any(word in message_lower for word in ['fee', 'tuition', 'payment']):
        response = "For financial information, please visit the bursar's office or check your student account online."
    elif any(word in message_lower for word in ['register', 'enrollment']):
        response = "Registration is available through the student portal during designated periods."
    elif any(word in message_lower for word in ['help', 'support']):
        response = (
            "I'm here to help with university-related questions including:\n"
            "• Course information and enrollment\n"
            "• Academic records and grades\n"
            "• Financial information\n"
            "• Registration assistance\n"
            "• General university policies"
        )
    else:
        response = "I'm here to help with university-related questions. You can ask about courses, grades, fees, or registration."
    
    # ADD CONVERSATION TRACKING HERE:
    # Initialize user history if not exists
    if not hasattr(chatbot_instance, 'conversation_history'):
        chatbot_instance.conversation_history = {}
    
    if user_id not in chatbot_instance.conversation_history:
        chatbot_instance.conversation_history[user_id] = []
    
    # Add this conversation
    chatbot_instance.conversation_history[user_id].append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'message': message,
        'response': response,
        'type': 'voice' if is_voice else 'text'
    })
    
    # Keep only last 50 conversations per user
    if len(chatbot_instance.conversation_history[user_id]) > 50:
        chatbot_instance.conversation_history[user_id] = chatbot_instance.conversation_history[user_id][-50:]

    # Also log to auth system if available
    if hasattr(chatbot_instance, 'auth_system') and chatbot_instance.auth_system and hasattr(chatbot_instance.auth_system, '_log_activity'):
        try:
            chatbot_instance.auth_system._log_activity(
                user_id, 
                'Chatbot interaction',
                f"Q: {message[:50]}... A: {response[:50]}...",
                getattr(chatbot_instance.auth_system.current_user, 'id', None) if chatbot_instance.auth_system.current_user else None
            )
        except Exception as e:
            logger.debug(f"Failed to log chatbot interaction: {e}")
    
    return response

def test_chatbot_integration(auth):
    """Test chatbot integration functionality
    
    Args:
        auth: UserAuth instance
    """
    import sys
    
    print("\nTesting Chatbot Integration:")
    print("=" * 35)
    
    # Test 1: Check if chatbot is available
    if CHATBOT_AVAILABLE:
        print("✓ Chatbot module available")
    else:
        reason = getattr(sys.modules[__name__], "_CHATBOT_IMPORT_ERROR", None)
        print("✗ Chatbot module not available")
        if reason:
            print(f"  ImportError: {reason}")
            print(f"  sys.path[0]: {sys.path[0]}")
        return
    
    # Test 2: Check if chatbot is initialized
    if hasattr(auth, 'chatbot') and auth.chatbot:
        print("✓ Chatbot integration initialized")
    else:
        print("✗ Chatbot integration not initialized")
        print("  Attempting to initialize...")
        if initialize_chatbot_integration(auth):
            print("✓ Chatbot integration initialized successfully")
        else:
            print("✗ Failed to initialize chatbot integration")
            return
    
    # Test 3: Check permissions
    user = auth.current_user
    chatbot_perms = [p for p in user['permissions'] if 'chatbot' in p or p == 'voice_interaction']
    print(f"✓ User has {len(chatbot_perms)} chatbot permissions")
    
    # Test 4: Test session creation
    session_token = create_chatbot_session(auth, user['username'])
    if session_token:
        print("✓ Chatbot session creation successful")
    else:
        print("✗ Chatbot session creation failed")
    
    # Test 5: Test context retrieval
    context = auth.get_user_chatbot_context(user['username'])
    if context:
        print(f"✓ User context retrieved - Role: {context['role']}")
    else:
        print("✗ Failed to retrieve user context")
    
    # Test 6: Test basic chatbot functionality
    if hasattr(auth, 'chatbot') and auth.chatbot:
        try:
            # Test a simple message
            test_message = "Hello, this is a test message"
            if hasattr(auth.chatbot, 'process_message'):
                response = auth.chatbot.process_message(test_message, user['username'])
                if response:
                    print("✓ Basic chatbot message processing works")
                    print(f"  Test response length: {len(response)} characters")
                else:
                    print("✗ Chatbot returned empty response")
            else:
                print("✗ Chatbot missing process_message method")
        except Exception as e:
            print(f"✗ Chatbot functionality test failed: {e}")
    
    print("\nIntegration test completed!")

def create_sample_chatbot_data(auth_instance):
    """Inspect chatbot interaction data stored in the database for validation.
    
    Args:
        auth_instance: UserAuth instance
    """
    import json
    
    try:
        with auth_instance.db_manager.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT username, details, timestamp
                FROM activity_log
                WHERE action = 'Chatbot interaction'
                ORDER BY timestamp DESC
                LIMIT 10
                """
            )
            records = cursor.fetchall()

            if not records:
                print("⚠ No chatbot interactions found in the database.")
                return

            print("✓ Retrieved chatbot interactions from the database:")
            for row in records:
                details = row["details"]
                parsed_details = {}
                if details:
                    try:
                        parsed_details = json.loads(details)
                    except json.JSONDecodeError:
                        parsed_details = {"raw_details": details}

                intent = parsed_details.get("intent") or parsed_details.get("interaction_type")
                message_len = parsed_details.get("message_length")
                response_len = parsed_details.get("response_length")
                summary_parts = [
                    f"user={row['username']}",
                    f"timestamp={row['timestamp']}",
                ]

                if intent:
                    summary_parts.append(f"intent={intent}")
                if message_len is not None:
                    summary_parts.append(f"message_length={message_len}")
                if response_len is not None:
                    summary_parts.append(f"response_length={response_len}")
                if not summary_parts:
                    summary_parts.append(f"details={details}")

                print(f"  • {' | '.join(summary_parts)}")
    except Exception as error:
        print(f"✗ Failed to read chatbot data: {error}")

# Export public functions
__all__ = [
    'initialize_chatbot_integration',
    'setup_chatbot_permissions',
    'create_chatbot_session',
    'get_chatbot_conversation_history',
    'generate_chatbot_analytics',
    'launch_chatbot_interface',
    'display_chatbot_integration_menu',
    'test_chatbot_integration',
    'create_sample_chatbot_data',
    'process_message',
    'CHATBOT_AVAILABLE',
]
