"""MinimalChatbot: lightweight chatbot without full NLP/auth dependencies."""

from datetime import datetime


class MinimalChatbot:
    def __init__(self, db_path=None):
        from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        self.auth_system = None
        self.conversation_history = {}
        self.enabled = True
        print("Minimal chatbot initialized")

    def set_auth_system(self, auth_system):
        """Set authentication system"""
        self.auth_system = auth_system

    def process_message(self, message, user_id, session_id=None, is_voice=False, **kwargs):
        """Process basic messages with conversation tracking"""
        message_lower = message.lower()

        role = "guest"
        if self.auth_system and self.auth_system.current_user:
            role = self.auth_system.current_user.get('role', 'guest')

        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            if role == 'student':
                response = "Hello! I'm the University Chatbot. I can help you with courses, grades, registration, and more."
            elif role in ['staff', 'admin']:
                response = "Hello! I can help you with student management, course administration, and system functions."
            else:
                response = "Hello! I'm the University Chatbot. How can I help you with university information?"

        elif any(word in message_lower for word in ['course', 'class', 'program', 'module']):
            response = "I can help you with course information, enrollment, and academic planning. What specific course information do you need?"

        elif any(word in message_lower for word in ['grade', 'gpa', 'transcript', 'academic record']):
            response = "For grade information and academic records, please check your student portal for official records or contact the registrar's office."

        elif any(word in message_lower for word in ['fee', 'tuition', 'payment', 'financial']):
            response = "I can provide information about tuition fees, payment schedules, and financial aid. For specific account details, please visit the bursar's office."

        elif any(word in message_lower for word in ['register', 'enrollment', 'enroll']):
            response = "I can guide you through the registration process. Registration is typically available through the student portal during designated periods."

        elif any(word in message_lower for word in ['help', 'support']):
            response = "I'm here to help with university-related questions including:\n• Course information and enrollment\n• Academic records and grades\n• Financial information\n• Registration assistance\n• General university policies"

        else:
            response = "I'm here to help with university-related questions. You can ask about courses, grades, fees, registration, or general university information. How can I assist you today?"

        self.track_conversation(user_id, message, response, is_voice, session_id)

        if self.auth_system and hasattr(self.auth_system, '_log_activity'):
            try:
                current_user = self.auth_system.current_user
                user_id_for_log = current_user['id'] if current_user else None
                self.auth_system._log_activity(
                    user_id,
                    'Chatbot interaction',
                    f"Q: {message[:50]}... A: {response[:50]}...",
                    user_id_for_log
                )
            except Exception:
                pass

        return response

    def track_conversation(self, user_id, message, response, is_voice=False, session_id=None):
        """Track conversation in memory with session tracking"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []

        self.conversation_history[user_id].append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'session_id': session_id,
            'message': message,
            'response': response,
            'type': 'voice' if is_voice else 'text'
        })

        if len(self.conversation_history[user_id]) > 50:
            self.conversation_history[user_id] = self.conversation_history[user_id][-50:]

    def run_authenticated_console_interface(self):
        """Run console interface with existing authentication"""
        print("University Chatbot")
        print("=" * 30)

        if not self.auth_system:
            print("Error: No authentication system available.")
            return

        if not self.auth_system.check_session():
            print("Error: Your session has expired. Please log in through the main system.")
            return

        user = self.auth_system.current_user
        if not user:
            print("Error: No authenticated user found.")
            return

        print(f"Welcome {user['username']}! You are logged in as {user['role']}.")

        if 'access_chatbot' not in user.get('permissions', []):
            print("You don't have permission to access the chatbot.")
            return

        print("\nType 'exit' to return to main menu, 'help' for commands.")

        while True:
            try:
                if not self.auth_system.check_session():
                    print("\nYour session has expired.")
                    break

                user_input = input(f"\n{user['username']}: ")

                if user_input.lower() in ['exit', 'quit', 'back']:
                    print("Returning to main menu...")
                    break

                if user_input.lower() == 'help':
                    print("\nAvailable commands:")
                    print("- Ask about courses, registration, grades, fees")
                    print("- 'exit' to return to main menu")
                    continue

                if not user_input.strip():
                    print("Please enter a message.")
                    continue

                try:
                    response = self.process_message(user_input, user['username'])
                    print(f"Chatbot: {response}")

                except Exception as process_error:
                    print(f"Chatbot: I encountered an error: {process_error}")

            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break

            except Exception as e:
                print(f"Error: {e}")
                break

        print(f"Chatbot session ended. Thank you!")

    def get_conversation_history(self, username, limit=10):
        """Get conversation history"""
        return self.conversation_history.get(username, [])[-limit:]
