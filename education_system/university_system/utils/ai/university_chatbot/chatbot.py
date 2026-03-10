"""UniversityChatbot: main orchestrator class that composes all sub-modules."""

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths

from education_system.university_system.utils.ai.university_chatbot.fallbacks import (
    LIBRARIES_AVAILABLE,
    Flask,
    TfidfVectorizer,
    pipeline,
)
from education_system.university_system.utils.ai.university_chatbot.models import (
    AuthenticatedSession,
    ConversationContext,
    UserSession,
)
from education_system.university_system.utils.ai.university_chatbot.voice_interface import VoiceInterface
from education_system.university_system.utils.ai.university_chatbot.config import load_config
from education_system.university_system.utils.ai.university_chatbot import nlp_processor
from education_system.university_system.utils.ai.university_chatbot import intent_handlers
from education_system.university_system.utils.ai.university_chatbot import authenticated_handlers
from education_system.university_system.utils.ai.university_chatbot import recommendation_engine
from education_system.university_system.utils.ai.university_chatbot import database_utils
from education_system.university_system.utils.ai.university_chatbot import logging_tracking
from education_system.university_system.utils.ai.university_chatbot import voice_support
from education_system.university_system.utils.ai.university_chatbot import api_routes as api_routes_mod
from education_system.university_system.utils.ai.university_chatbot import background_tasks


class UniversityChatbot:
    def __init__(self, db_path=None, config_path=None):
        # Core initialization
        self.db_path = db_path or os.fspath(paths.DEFAULT_DB_PATH)
        self.config_path = config_path or os.fspath(paths.CHATBOT_DATA_DIR / 'chatbot_config.json')
        self.log_dir = os.fspath(paths.LOG_DIR)
        self.upload_dir = os.fspath(paths.CHATBOT_UPLOAD_DIR)
        self.models_dir = os.fspath(paths.CHATBOT_MODELS_DIR)

        # Authentication system integration
        self.auth_system = None
        self.authenticated_sessions = {}
        self.conversation_contexts = {}
        self.active_sessions = {}

        # Load configuration
        self.config = load_config(self.config_path)

        # Initialize directories
        self.ensure_directories()
        self.active_sessions = {}

        # Initialize voice interface
        self.voice_interface = VoiceInterface()
        self.voice_interface.initialize()

        # Initialize NLP components
        self.init_nlp_components()

        # Knowledge base and patterns
        self.init_knowledge_base()

        # Conversation tracking
        self.conversation_history = {}

        # Flask app for web API
        if LIBRARIES_AVAILABLE['flask']:
            self.app = Flask(__name__)
            try:
                from education_system.university_system.infrastructure.security.flask_security_headers import init_security_headers
                init_security_headers(self.app)
            except ImportError:
                pass
            self.setup_api_routes()

        print("University Chatbot initialized successfully!")

    # -- Auth ---------------------------------------------------------------

    def set_auth_system(self, auth_system):
        """Set the authentication system for integration"""
        self.auth_system = auth_system
        print("✅ Authentication system integrated with chatbot")

    # -- Main message entry point -------------------------------------------

    def process_message(self, message: str, user_id: str, session_id: str | None = None, is_voice: bool = False, **kwargs) -> str:
        """
        Canonical entrypoint. Supports optional session_id.
        If session_id matches an active authenticated session, we process with auth context.
        Otherwise we use/initialize a conversation context keyed by user_id.
        """
        try:
            if session_id and session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                return self.process_message_with_auth(message, session, is_voice=is_voice)

            if user_id not in self.conversation_contexts:
                self.conversation_contexts[user_id] = ConversationContext(
                    conversation_id=session_id or f"{user_id}_{int(time.time())}",
                    user_id=user_id,
                    messages=[],
                    intent_history=[],
                    entities={},
                    session_data={}
                )
            context = self.conversation_contexts[user_id]

            if session_id:
                context.conversation_id = session_id

            nlp_result = self.process_with_nlp(message, context)

            context.messages.append({
                "user_message": message,
                "timestamp": datetime.now().isoformat(),
                "nlp_result": nlp_result,
                "is_voice": is_voice,
                "session_id": session_id
            })

            if nlp_result["intent"]:
                context.intent_history.append(nlp_result["intent"])

            context.entities.update(nlp_result["entities"])

            if nlp_result.get("is_voice_command", False):
                return self.handle_voice_command(message, user_id, context)

            if nlp_result["requires_escalation"]:
                return self.escalate_to_human(message, user_id)

            response = self.generate_response(nlp_result, context)

            self.log_enhanced_conversation(user_id, message, response, nlp_result, session_id)

            return response

        except Exception as e:
            print(f"Message processing error: {e}")
            return "I apologize, but I encountered an error processing your message. Please try again or contact support."

    # -- Delegation to sub-modules ------------------------------------------

    def process_with_nlp(self, text, user_context=None):
        return nlp_processor.process_with_nlp(self, text, user_context)

    def generate_response(self, nlp_result, context):
        intent = nlp_result["intent"]
        if intent == "course_inquiry":
            return self.handle_course_inquiry(nlp_result, context)
        elif intent == "registration":
            return self.handle_registration_query(nlp_result, context)
        elif intent == "financial":
            return self.handle_financial_query(nlp_result, context)
        elif intent == "grades":
            return self.handle_grades_query(nlp_result, context)
        elif intent == "technical_support":
            return self.handle_technical_query(nlp_result, context)
        elif intent == "voice_command":
            return self.handle_voice_command(context.messages[-1]["user_message"], context.user_id, context)
        else:
            return self.handle_general_query(nlp_result, context)

    # Intent handlers
    def handle_course_inquiry(self, nlp_result, context):
        return intent_handlers.handle_course_inquiry(self, nlp_result, context)

    def handle_registration_query(self, nlp_result, context):
        return intent_handlers.handle_registration_query(self, nlp_result, context)

    def handle_financial_query(self, nlp_result, context):
        return intent_handlers.handle_financial_query(self, nlp_result, context)

    def handle_grades_query(self, nlp_result, context):
        return intent_handlers.handle_grades_query(self, nlp_result, context)

    def handle_technical_query(self, nlp_result, context):
        return intent_handlers.handle_technical_query(self, nlp_result, context)

    def handle_general_query(self, nlp_result, context):
        return intent_handlers.handle_general_query(self, nlp_result, context)

    def find_best_faq_match(self, query):
        return intent_handlers.find_best_faq_match(self, query)

    def escalate_to_human(self, message, user_id):
        return intent_handlers.escalate_to_human(self, message, user_id)

    # Authenticated handlers
    def generate_authenticated_response(self, nlp_result, context, session):
        return authenticated_handlers.generate_authenticated_response(self, nlp_result, context, session)

    # Recommendation engine
    def get_course_recommendations(self, student_id, num_recommendations=5):
        return recommendation_engine.get_course_recommendations(self, student_id, num_recommendations)

    def calculate_gpa(self, student_id, semester=None):
        return recommendation_engine.calculate_gpa(self, student_id, semester)

    # Database utils
    def connect_to_db(self):
        return database_utils.connect_to_db(self.db_path)

    def get_student_id_for_user(self, username):
        return database_utils.get_student_id_for_user(self, username)

    def get_student_profile(self, student_id):
        return database_utils.get_student_profile(self, student_id)

    # Logging / tracking
    def get_user_context(self, username):
        return logging_tracking.get_user_context(self, username)

    def generate_contextual_response(self, message, user_context):
        return logging_tracking.generate_contextual_response(self, message, user_context)

    def log_conversation(self, username, message, response, session_id):
        return logging_tracking.log_conversation(self, username, message, response, session_id)

    def track_conversation(self, username, message, response, is_voice=False):
        return logging_tracking.track_conversation(self, username, message, response, is_voice)

    def get_conversation_history(self, username, limit=10):
        return logging_tracking.get_conversation_history(self, username, limit)

    def log_enhanced_conversation(self, user_id, user_message, bot_response, nlp_result, session_id=None):
        return logging_tracking.log_enhanced_conversation(self, user_id, user_message, bot_response, nlp_result, session_id)

    # Voice support
    def process_voice_input(self, duration=5.0):
        return voice_support.process_voice_input(self, duration)

    def start_voice_mode(self, user_id):
        return voice_support.start_voice_mode(self, user_id)

    def text_to_speech(self, text, output_path=None):
        return voice_support.text_to_speech(self, text, output_path)

    def test_voice_interface(self):
        return voice_support.test_voice_interface(self)

    def handle_voice_command(self, message, user_id, context):
        return voice_support.handle_voice_command(self, message, user_id, context)

    # API routes
    def setup_api_routes(self):
        api_routes_mod.setup_api_routes(self)

    # Background tasks / run modes
    def run(self):
        background_tasks.run(self)

    def run_console_interface(self):
        background_tasks.run_console_interface(self)

    def run_web_server(self, host='0.0.0.0', port=5000):
        background_tasks.run_web_server(self, host, port)

    def setup_scheduled_tasks(self):
        background_tasks.setup_scheduled_tasks(self)

    def generate_daily_analytics(self):
        background_tasks.generate_daily_analytics(self)

    def cleanup_old_sessions(self):
        background_tasks.cleanup_old_sessions(self)

    def generate_usage_analytics(self):
        return background_tasks.generate_usage_analytics(self)

    def send_proactive_alerts(self):
        background_tasks.send_proactive_alerts(self)

    # -- Auth / session management (kept inline — small) --------------------

    def validate_chatbot_session(self, session_token: str) -> Optional[AuthenticatedSession]:
        """Validate chatbot session and check permissions"""
        if not session_token or session_token not in self.authenticated_sessions:
            return None

        session = self.authenticated_sessions[session_token]

        if (datetime.now() - session.last_activity).seconds > 1800:
            del self.authenticated_sessions[session_token]
            return None

        session.last_activity = datetime.now()
        return session

    def check_user_permission(self, session_token: str, permission: str) -> bool:
        """Check if authenticated user has specific permission"""
        session = self.validate_chatbot_session(session_token)
        if not session:
            return False
        return permission in session.permissions

    def get_authenticated_user_info(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get information about authenticated user"""
        session = self.validate_chatbot_session(session_token)
        if not session:
            return None

        return {
            "user_id": session.user_id,
            "username": session.username,
            "role": session.role,
            "permissions": session.permissions,
            "login_time": session.login_time.isoformat(),
            "last_activity": session.last_activity.isoformat()
        }

    def process_authenticated_message(self, message: str, session_token: str, is_voice: bool = False) -> str:
        """Process message with authentication context"""
        session = self.validate_chatbot_session(session_token)
        if not session:
            return "Your session has expired. Please log in again to continue using the chatbot."
        return self.process_message_with_auth(message, session, is_voice)

    def process_message_with_auth(self, message: str, session: AuthenticatedSession, is_voice: bool = False) -> str:
        """Enhanced message processing with authentication context"""
        try:
            user_id = session.username

            if user_id not in self.conversation_contexts:
                self.conversation_contexts[user_id] = ConversationContext(
                    conversation_id=f"{user_id}_{int(time.time())}",
                    user_id=user_id,
                    messages=[],
                    intent_history=[],
                    entities={"authenticated_user": session.username, "user_role": session.role},
                    session_data={"permissions": session.permissions}
                )

            context = self.conversation_contexts[user_id]
            context.entities["authenticated_user"] = session.username
            context.entities["user_role"] = session.role
            context.session_data["permissions"] = session.permissions

            nlp_result = self.process_with_nlp(message, context)

            context.messages.append({
                "user_message": message,
                "timestamp": datetime.now().isoformat(),
                "nlp_result": nlp_result,
                "is_voice": is_voice,
                "authenticated": True,
                "user_role": session.role
            })

            if nlp_result["intent"]:
                context.intent_history.append(nlp_result["intent"])

            context.entities.update(nlp_result["entities"])

            if nlp_result.get("is_voice_command", False):
                return self.handle_voice_command(message, user_id, context)

            if nlp_result["requires_escalation"]:
                return self.escalate_to_human(message, user_id)

            response = self.generate_authenticated_response(nlp_result, context, session)

            self.log_enhanced_conversation(session.username, message, response, nlp_result)

            return response

        except Exception as e:
            print(f"Authenticated message processing error: {e}")
            return "I apologize, but I encountered an error processing your message. Please try again."

    def verify_mfa(self, secret: str, code: str) -> bool:
        """Verify MFA code"""
        try:
            import pyotp
            totp = pyotp.TOTP(secret)
            return totp.verify(code)
        except ImportError:
            print("pyotp not available for MFA verification")
            return True

    def validate_session(self, session_token: str) -> Optional[UserSession]:
        """Validate user session"""
        if session_token not in self.active_sessions:
            return None

        session = self.active_sessions[session_token]

        if (datetime.now() - session.last_activity).seconds > self.config["security"]["session_timeout"]:
            del self.active_sessions[session_token]
            return None

        session.last_activity = datetime.now()
        return session

    def get_system_status(self):
        """Get chatbot system status"""
        status = {
            "authenticated": self.auth_system is not None,
            "current_user": None,
            "active_sessions": len(self.conversation_history),
            "total_conversations": 0
        }

        if self.auth_system and self.auth_system.current_user:
            status["current_user"] = self.auth_system.current_user['username']

        for user_history in self.conversation_history.values():
            status["total_conversations"] += len(user_history)

        return status

    # -- Initialization helpers (kept inline) --------------------------------

    def ensure_directories(self):
        """Create necessary directories"""
        for directory in [self.log_dir, self.upload_dir, self.models_dir]:
            os.makedirs(directory, exist_ok=True)

    def init_nlp_components(self):
        """Initialize NLP components with proper error handling"""
        try:
            if LIBRARIES_AVAILABLE['spacy']:
                try:
                    import spacy
                    self.nlp = spacy.load("en_core_web_sm")
                    print("✓ SpaCy NLP model loaded successfully")
                except OSError:
                    print("ℹ️  SpaCy model 'en_core_web_sm' not found - using lightweight fallback")
                    print("   To install: python -m spacy download en_core_web_sm")
                    self.nlp = None
            else:
                self.nlp = None
                print("ℹ️  SpaCy not available - using lightweight fallback NLP")

            if LIBRARIES_AVAILABLE['transformers']:
                try:
                    self.intent_classifier = pipeline(
                        "text-classification",
                        model="distilbert-base-uncased"
                    )
                    self.sentiment_analyzer = pipeline("sentiment-analysis")
                    self.qa_pipeline = pipeline("question-answering")
                    print("✓ Advanced NLP models loaded successfully")
                except Exception as e:
                    print(f"Warning: Advanced NLP model loading failed ({e}), using lightweight fallback")
                    self.intent_classifier = pipeline("text-classification")
                    self.sentiment_analyzer = pipeline("sentiment-analysis")
                    self.qa_pipeline = pipeline("question-answering")
            else:
                self.intent_classifier = pipeline("text-classification")
                self.sentiment_analyzer = pipeline("sentiment-analysis")
                self.qa_pipeline = pipeline("question-answering")

            if LIBRARIES_AVAILABLE['sklearn']:
                self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            else:
                self.vectorizer = TfidfVectorizer()

            print("✓ NLP components initialized successfully")
        except Exception as e:
            print(f"Warning: NLP components initialization failed: {e}")
            self.nlp = None
            self.intent_classifier = pipeline("text-classification")
            self.sentiment_analyzer = pipeline("sentiment-analysis")
            self.qa_pipeline = pipeline("question-answering")
            try:
                self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            except (ValueError, TypeError):
                self.vectorizer = TfidfVectorizer()

    def init_knowledge_base(self):
        """Initialize enhanced knowledge base"""
        self.intents = {
            "course_inquiry": {
                "patterns": ["course", "program", "degree", "study", "major", "curriculum"],
                "responses": ["I can help you with course information.", "Let me find course details for you."],
                "requires_auth": False,
                "department": "academic"
            },
            "registration": {
                "patterns": ["register", "enroll", "sign up", "add course", "drop course"],
                "responses": ["I'll help you with registration.", "Let me guide you through the registration process."],
                "requires_auth": True,
                "department": "academic"
            },
            "financial": {
                "patterns": ["fee", "tuition", "payment", "scholarship", "financial aid"],
                "responses": ["I can assist with financial information.", "Let me help with your financial queries."],
                "requires_auth": True,
                "department": "finance"
            },
            "grades": {
                "patterns": ["grade", "gpa", "transcript", "academic record"],
                "responses": ["I can help you check your academic performance.", "Let me retrieve your grade information."],
                "requires_auth": True,
                "department": "academic"
            },
            "technical_support": {
                "patterns": ["password", "login", "system", "technical", "computer", "wifi"],
                "responses": ["I can help with technical issues.", "Let me connect you with IT support."],
                "requires_auth": False,
                "department": "it"
            },
            "voice_command": {
                "patterns": ["voice", "speech", "listen", "talk", "speak"],
                "responses": ["I can interact with you using voice commands.", "Voice mode is available for hands-free interaction."],
                "requires_auth": False,
                "department": "general"
            }
        }

        self.faq_database = self._load_faq_database()

        # Also set the simple knowledge_base dict for compat
        self.knowledge_base = {
            "academic": {
                "courses": "Information about university courses and programs",
                "registration": "Course registration and enrollment procedures",
                "grades": "Academic performance and grading information",
                "requirements": "Degree and graduation requirements"
            },
            "financial": {
                "tuition": "Tuition fees and payment information",
                "scholarships": "Scholarship and financial aid opportunities",
                "billing": "Billing and payment procedures"
            },
            "administrative": {
                "policies": "University policies and procedures",
                "calendar": "Academic calendar and important dates",
                "contacts": "Department and office contact information"
            }
        }

    def _load_faq_database(self) -> Dict:
        """Load FAQ database from file or create default"""
        faq_path = os.fspath(paths.CHATBOT_DATA_DIR / "faq_database.json")
        default_faq = {
            "academic": {
                "How do I register for courses?": "You can register through the student portal during registration periods.",
                "What are the prerequisites for advanced courses?": "Prerequisites vary by course. Check the course catalog for specific requirements.",
                "How do I calculate my GPA?": "GPA is calculated by dividing total grade points by total credit hours."
            },
            "financial": {
                "When are tuition payments due?": "Tuition is typically due before the start of each semester.",
                "How do I apply for financial aid?": "Submit the FAFSA form and university scholarship applications.",
                "What payment methods are accepted?": "We accept credit cards, bank transfers, and payment plans."
            },
            "technical": {
                "How do I reset my password?": "Use the 'Forgot Password' link on the login page or contact IT support.",
                "How do I connect to campus WiFi?": "Connect to 'UniversityWiFi' and use your student credentials.",
                "Where can I download campus software?": "Visit the IT services website for software downloads."
            },
            "voice": {
                "How do I use voice commands?": "Say 'start voice mode' to begin voice interaction. You can ask questions naturally and I'll respond with voice and text.",
                "What voice commands are available?": "You can ask about courses, grades, registration, and general university information using natural speech.",
                "How do I stop voice mode?": "Say 'stop listening' or 'exit voice mode' to return to text-only interaction."
            }
        }

        if os.path.exists(faq_path):
            with open(faq_path, 'r') as f:
                return json.load(f)
        else:
            with open(faq_path, 'w') as f:
                json.dump(default_faq, f, indent=4)
            return default_faq

    # -- Authenticated console interface ------------------------------------

    def run_authenticated_console_interface(self):
        """Run console interface with existing authentication - NO DOUBLE LOGIN"""
        print("Enhanced University Chatbot")
        print("=" * 30)

        if not self.auth_system:
            print("Error: No authentication system available. Please restart the application.")
            return

        if not self.auth_system.check_session():
            print("Error: Your session has expired or you are not logged in.")
            print("Please log in through the main system first.")
            return

        user = self.auth_system.current_user
        if not user:
            print("Error: No authenticated user found. Please log in through the main system first.")
            return
        print(f"Welcome {user['username']}! You are logged in as {user['role']}.")

        if 'access_chatbot' not in user.get('permissions', []):
            print("You don't have permission to access the chatbot.")
            return

        print(f"\nChatbot Features Available:")
        if user['role'] == 'student':
            print("• Ask about courses and enrollment")
            print("• Check academic information")
            print("• Get help with registration")
            print("• Financial aid information")
        elif user['role'] in ['staff', 'admin']:
            print("• Student information lookup")
            print("• Course management assistance")
            print("• Administrative support")
            print("• System information")
        elif user['role'] == 'instructor':
            print("• Course management")
            print("• Student academic support")
            print("• Grade information")

        print("\nType 'exit' to return to main menu, 'help' for commands.")

        while True:
            try:
                if not self.auth_system.check_session():
                    print("\nYour session has expired. Please log in again through the main system.")
                    break

                current_user = self.auth_system.current_user
                if not current_user:
                    print("\nAuthentication lost. Please log in again through the main system.")
                    break

                user_input = input(f"\n{current_user['username']}: ")

                if user_input.lower() in ['exit', 'quit', 'back', 'logout']:
                    print("Returning to main menu...")
                    break

                if user_input.lower() == 'help':
                    print("\nAvailable commands:")
                    print("- Ask about courses, registration, grades, fees")
                    print("- Request information based on your role permissions")
                    print(f"- Your role: {current_user['role']}")
                    print(f"- Available permissions: {len(current_user.get('permissions', []))}")
                    if hasattr(self, 'voice_interface') and getattr(self.voice_interface, 'enabled', False):
                        print("- Voice commands: 'start voice mode', 'test voice'")
                    print("- 'exit' to return to main menu")
                    continue

                if not user_input.strip():
                    print("Please enter a message or type 'help' for available commands.")
                    continue

                try:
                    response = self.process_message(user_input, current_user['username'])
                    print(f"Chatbot: {response}")

                    if hasattr(self.auth_system, '_log_activity'):
                        self.auth_system._log_activity(
                            current_user['username'],
                            'Chatbot interaction',
                            f"Q: {user_input[:50]}{'...' if len(user_input) > 50 else ''} A: {response[:50]}{'...' if len(response) > 50 else ''}",
                            current_user['id']
                        )

                    if hasattr(self, 'conversation_history'):
                        if current_user['username'] not in self.conversation_history:
                            self.conversation_history[current_user['username']] = []

                        self.conversation_history[current_user['username']].append({
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'message': user_input,
                            'response': response,
                            'role': current_user['role']
                        })

                        if len(self.conversation_history[current_user['username']]) > 50:
                            self.conversation_history[current_user['username']] = self.conversation_history[current_user['username']][-50:]

                except Exception as process_error:
                    print(f"Chatbot: I apologize, but I encountered an error processing your message: {process_error}")
                    print("Please try rephrasing your question or contact support if the issue persists.")

                    if hasattr(self.auth_system, '_log_activity'):
                        self.auth_system._log_activity(
                            current_user['username'],
                            'Chatbot error',
                            f"Error processing: {user_input[:50]} - {str(process_error)[:100]}",
                            current_user['id']
                        )

            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Returning to main menu...")
                break

            except EOFError:
                print("\nEnd of input detected. Returning to main menu...")
                break

            except Exception as e:
                print(f"Unexpected error: {e}")
                print("Returning to main menu...")
                break

        final_user = self.auth_system.current_user
        if final_user:
            print(f"Chatbot session ended for {final_user['username']}. Thank you for using the University Chatbot!")

            if hasattr(self.auth_system, '_log_activity'):
                self.auth_system._log_activity(
                    final_user['username'],
                    'Chatbot session ended',
                    'User exited chatbot interface',
                    final_user['id']
                )
        else:
            print("Chatbot session ended. Thank you for using the University Chatbot!")
