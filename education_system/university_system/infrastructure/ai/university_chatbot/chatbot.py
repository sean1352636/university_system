"""UniversityChatbot: main orchestrator class that composes all sub-modules."""

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths

from education_system.university_system.infrastructure.ai.university_chatbot.fallbacks import (
    LIBRARIES_AVAILABLE,
    Flask,
    TfidfVectorizer,
    pipeline,
)
from education_system.university_system.infrastructure.ai.university_chatbot.models import (
    AuthenticatedSession,
    ConversationContext,
    UserSession,
)
from education_system.university_system.infrastructure.ai.university_chatbot.voice_interface import VoiceInterface
from education_system.university_system.infrastructure.ai.university_chatbot.config import load_config
from education_system.university_system.infrastructure.ai.university_chatbot import nlp_processor
from education_system.university_system.infrastructure.ai.university_chatbot import intent_handlers
from education_system.university_system.infrastructure.ai.university_chatbot import authenticated_handlers
from education_system.university_system.infrastructure.ai.university_chatbot import recommendation_engine
from education_system.university_system.infrastructure.ai.university_chatbot import database_utils
from education_system.university_system.infrastructure.ai.university_chatbot import logging_tracking
from education_system.university_system.infrastructure.ai.university_chatbot import voice_support
from education_system.university_system.infrastructure.ai.university_chatbot import api_routes as api_routes_mod
from education_system.university_system.infrastructure.ai.university_chatbot import background_tasks


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

        # Selection-aware context. The four scheduling GUIs publish
        # academic.selection.changed when the operator clicks a row;
        # we cache the most recent module/course/exam pointer per
        # user (or globally for unauth chats) and surface it in
        # process_message so replies are scoped to what the user is
        # looking at in a sibling window.
        self._selection_module: str | None = None
        self._selection_course: str | None = None
        self._selection_exam_id: int | None = None
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                subscribe, EVENT_SELECTION_CHANGED,
            )

            def _on_selection(**payload):
                if payload.get("module_code"):
                    self._selection_module = payload.get("module_code")
                if payload.get("course_code"):
                    self._selection_course = payload.get("course_code")
                if payload.get("exam_id") is not None:
                    self._selection_exam_id = payload.get("exam_id")

            subscribe(EVENT_SELECTION_CHANGED, _on_selection)
        except Exception:
            pass

        # Cross-domain bus integration (#10): turn events that affect a
        # specific user into queued chatbot messages they'll see on their
        # next chat session. Read-only consumer; never raises.
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                subscribe,
                EVENT_CHARGE_RAISED,
                EVENT_HOLD_CHANGED,
                EVENT_LOAN_CHANGED,
                EVENT_INCIDENT_LOGGED,
                EVENT_DOCUMENT_CHANGED,
            )
            from education_system.university_system.modules.services.chatbot_inbox import (
                queue_message_for,
            )

            def _on_charge(**kw):
                sid = kw.get("student_id")
                if not sid:
                    return
                amt = kw.get("amount") or 0
                desc = kw.get("description") or "charge"
                queue_message_for(
                    sid,
                    f"Heads up — a £{float(amt):.2f} charge was added to "
                    f"your account: {desc}.",
                    source=kw.get("source") or "finance",
                )

            def _on_hold(**kw):
                sid = kw.get("student_id")
                if sid and kw.get("action") == "placed":
                    reason = kw.get("reason") or "finance hold"
                    queue_message_for(
                        sid,
                        f"A finance hold has been placed on your account "
                        f"({reason}). Resolve it to keep enrolling/booking.",
                        source="finance_hold",
                    )

            def _on_loan(**kw):
                uid = kw.get("user_id")
                if uid and kw.get("action") == "overdue_fined":
                    fine = kw.get("fine_amount") or 0
                    queue_message_for(
                        uid,
                        f"Library overdue fine: £{float(fine):.2f}. "
                        f"Return the book to stop further charges.",
                        source="library",
                    )

            def _on_incident(**kw):
                # Notify the reporter that their incident landed.
                sid = kw.get("reporter_id") or kw.get("reported_by")
                if sid:
                    queue_message_for(
                        sid,
                        f"Your {kw.get('domain', 'incident')} report "
                        f"#{kw.get('incident_id')} has been logged. "
                        f"You'll be contacted with follow-up actions.",
                        source="incident",
                    )

            subscribe(EVENT_CHARGE_RAISED, _on_charge)
            subscribe(EVENT_HOLD_CHANGED, _on_hold)
            subscribe(EVENT_LOAN_CHANGED, _on_loan)
            subscribe(EVENT_INCIDENT_LOGGED, _on_incident)

            # Cases (#11): notify the subject when a misconduct or
            # disciplinary case is opened against them. Also extend the
            # message with a Student Union advocacy opt-in line so the
            # student can reply "help" and have us route the request to
            # SU — keeps SU privacy-respecting (they don't see cases
            # until the student opts in).
            self._pending_advocacy: dict[str, dict] = {}
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    EVENT_CASE_OPENED,
                )

                def _on_case(**kw):
                    sid = kw.get("subject_id")
                    if not sid:
                        return
                    queue_message_for(
                        sid,
                        f"A {kw.get('kind') or 'case'} (#"
                        f"{kw.get('case_id')}, {kw.get('severity') or '—'}) "
                        f"has been opened. Check your portal for details "
                        f"and any required response. "
                        f"Student Union advocacy is available — reply "
                        f"'help' to request representation.",
                        source="case",
                    )
                    # Stash the latest case so 'help' knows what to act on.
                    self._pending_advocacy[str(sid)] = {
                        "case_id": kw.get("case_id"),
                        "kind": kw.get("kind") or "disciplinary",
                    }

                subscribe(EVENT_CASE_OPENED, _on_case)
            except Exception:
                pass
            # Document changes don't get a message — chatbot just
            # invalidates its local index. Hook reserved for future RAG.
            subscribe(EVENT_DOCUMENT_CHANGED, lambda **_: None)
        except Exception as exc:
            print(f"Chatbot bus subscribe skipped: {exc}")

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
        # Drain the inbox first (#12) — queued messages from background
        # gates land before the user's reply so they don't get missed.
        inbox_prefix = ""
        try:
            from education_system.university_system.modules.services.chatbot_inbox import (
                pop_messages_for,
            )
            queued = pop_messages_for(user_id, mark_read=True, limit=5)
            if queued:
                lines = [f"• {m['message']}" for m in queued]
                inbox_prefix = (
                    "While you were away, the system noted:\n"
                    + "\n".join(lines) + "\n\n"
                )
        except Exception:
            inbox_prefix = ""

        # Student Union advocacy opt-in: if there's a pending case for
        # this user and they reply with a help-request keyword, route
        # the advocacy request to SU. This is the only path SU sees
        # the case — privacy-respecting by construction.
        try:
            pending = self._pending_advocacy.get(str(user_id))
            if pending and message.strip().lower() in (
                "help", "yes please", "yes", "su help", "request advocacy",
            ):
                from education_system.university_system.modules.services.student_union_bus import (
                    request_advocacy,
                )
                rid = request_advocacy(
                    user_id, pending["case_id"], pending["kind"],
                    notes="Student requested via chatbot",
                )
                self._pending_advocacy.pop(str(user_id), None)
                ack = (
                    f"Routed to Student Union advocacy "
                    f"(request #{rid}). They'll be in touch."
                    if rid else
                    "Could not route the advocacy request. "
                    "Try contacting the SU welfare team directly."
                )
                return inbox_prefix + ack
        except Exception:
            pass

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
            if inbox_prefix:
                response = inbox_prefix + response

            # Selection-aware context badge — show the user which
            # sibling-window selection the chatbot is reading from.
            sel_bits = []
            if self._selection_module:
                sel_bits.append(f"module {self._selection_module}")
            if self._selection_course:
                sel_bits.append(f"course {self._selection_course}")
            if self._selection_exam_id is not None:
                sel_bits.append(f"exam #{self._selection_exam_id}")
            if sel_bits:
                response = f"(in context: {', '.join(sel_bits)})\n" + response

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
        elif intent == "academic_support":
            return self.handle_academic_support_query(nlp_result, context)
        elif intent == "admissions":
            return self.handle_admissions_query(nlp_result, context)
        elif intent == "administrative":
            return self.handle_administrative_query(nlp_result, context)
        elif intent == "wellbeing":
            return self.handle_wellbeing_query(nlp_result, context)
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

    def handle_academic_support_query(self, nlp_result, context):
        return intent_handlers.handle_academic_support_query(self, nlp_result, context)

    def handle_admissions_query(self, nlp_result, context):
        return intent_handlers.handle_admissions_query(self, nlp_result, context)

    def handle_administrative_query(self, nlp_result, context):
        return intent_handlers.handle_administrative_query(self, nlp_result, context)

    def handle_wellbeing_query(self, nlp_result, context):
        return intent_handlers.handle_wellbeing_query(self, nlp_result, context)

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

    def get_fee_balance(self, student_id):
        return database_utils.get_fee_balance(self, student_id)

    def get_transcript_requests(self, student_id):
        return database_utils.get_transcript_requests(self, student_id)

    def get_upcoming_deadlines(self, student_id):
        return database_utils.get_upcoming_deadlines(self, student_id)

    def get_exam_schedule(self, student_id):
        return database_utils.get_exam_schedule(self, student_id)

    def search_library(self, query):
        return database_utils.search_library(self, query)

    def get_academic_calendar(self):
        return database_utils.get_academic_calendar(self)

    def get_application_status(self, identifier):
        return database_utils.get_application_status(self, identifier)

    def search_staff_directory(self, query):
        return database_utils.search_staff_directory(self, query)

    def get_room_bookings(self, student_id):
        return database_utils.get_room_bookings(self, student_id)

    def get_clubs_and_societies(self):
        return database_utils.get_clubs_and_societies(self)

    def get_transport_schedule(self):
        return database_utils.get_transport_schedule(self)

    def get_lost_found_items(self, query=""):
        return database_utils.get_lost_found_items(self, query)

    def get_mental_health_resources(self):
        return database_utils.get_mental_health_resources(self)

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
                "patterns": ["register", "enroll", "sign up", "add course", "drop course",
                             "prerequisite", "waitlist", "availability", "course registration"],
                "responses": ["I'll help you with registration.", "Let me guide you through the registration process."],
                "requires_auth": True,
                "department": "academic"
            },
            "financial": {
                "patterns": ["fee", "tuition", "payment", "scholarship", "financial aid",
                             "balance", "deadline", "invoice", "payment plan", "bursary"],
                "responses": ["I can assist with financial information.", "Let me help with your financial queries."],
                "requires_auth": True,
                "department": "finance"
            },
            "grades": {
                "patterns": ["grade", "gpa", "transcript", "academic record", "marks",
                             "result", "certificate", "enrollment verification"],
                "responses": ["I can help you check your academic performance.", "Let me retrieve your grade information."],
                "requires_auth": True,
                "department": "academic"
            },
            "technical_support": {
                "patterns": ["password", "login", "system", "technical", "computer", "wifi",
                             "sso", "single sign", "portal", "lms", "moodle", "canvas"],
                "responses": ["I can help with technical issues.", "Let me connect you with IT support."],
                "requires_auth": False,
                "department": "it"
            },
            "voice_command": {
                "patterns": ["voice", "speech", "listen", "talk", "speak"],
                "responses": ["I can interact with you using voice commands.", "Voice mode is available for hands-free interaction."],
                "requires_auth": False,
                "department": "general"
            },
            "academic_support": {
                "patterns": ["deadline", "assignment due", "exam schedule", "exam room",
                             "library", "book available", "academic calendar", "holiday",
                             "term dates", "semester", "timetable", "schedule"],
                "responses": ["I can help with academic support.", "Let me look that up for you."],
                "requires_auth": False,
                "department": "academic"
            },
            "admissions": {
                "patterns": ["application", "apply", "admission", "document submission",
                             "scholarship eligibility", "campus tour", "onboarding",
                             "application status", "offer", "acceptance"],
                "responses": ["I can help with admissions queries.", "Let me check that for you."],
                "requires_auth": False,
                "department": "admissions"
            },
            "administrative": {
                "patterns": ["leave of absence", "deferral", "id card", "replacement",
                             "room booking", "facility", "staff directory", "contact",
                             "department", "office hours"],
                "responses": ["I can help with administrative tasks.", "Let me assist with that."],
                "requires_auth": False,
                "department": "administrative"
            },
            "wellbeing": {
                "patterns": ["mental health", "counselling", "counseling", "wellbeing",
                             "welfare", "event", "club", "society", "lost and found",
                             "lost property", "shuttle", "transport", "bus", "campus life"],
                "responses": ["I can help with wellbeing and campus life.", "Let me find that information."],
                "requires_auth": False,
                "department": "wellbeing"
            }
        }

        self.faq_database = self._load_faq_database()

        # Also set the simple knowledge_base dict for compat
        self.knowledge_base = {
            "academic": {
                "courses": "Information about university courses and programs",
                "registration": "Course registration and enrollment procedures",
                "grades": "Academic performance and grading information",
                "requirements": "Degree and graduation requirements",
                "deadlines": "Assignment and exam deadline reminders",
                "exams": "Exam schedules and room locations",
                "calendar": "Academic calendar, holidays, and term dates",
                "library": "Library resource search and book availability",
                "timetable": "Class timetable and schedule lookup"
            },
            "financial": {
                "tuition": "Tuition fees and payment information",
                "scholarships": "Scholarship and financial aid opportunities",
                "billing": "Billing and payment procedures",
                "balance": "Fee balance and payment deadline information",
                "aid_status": "Financial aid application status"
            },
            "administrative": {
                "policies": "University policies and procedures",
                "calendar": "Academic calendar and important dates",
                "contacts": "Department and office contact information",
                "leave": "Leave of absence and deferral guidance",
                "id_card": "ID card replacement requests",
                "room_booking": "Room and facility booking",
                "staff_directory": "Staff directory and department contacts"
            },
            "admissions": {
                "application": "Application status tracking",
                "documents": "Document submission guidance",
                "scholarships": "Scholarship and eligibility information",
                "tours": "Campus tour scheduling"
            },
            "wellbeing": {
                "mental_health": "Mental health resource signposting",
                "events": "Campus event listings and club information",
                "lost_found": "Lost and found reporting",
                "transport": "Shuttle and transport schedule queries"
            }
        }

    def _load_faq_database(self) -> Dict:
        """Load FAQ database from file or create default"""
        faq_path = os.fspath(paths.CHATBOT_DATA_DIR / "faq_database.json")
        default_faq = {
            "academic": {
                "How do I register for courses?": "You can register through the student portal during registration periods. Check course availability, prerequisites, and waitlist status from the registration page.",
                "What are the prerequisites for advanced courses?": "Prerequisites vary by course. Check the course catalog for specific requirements, or ask me about a specific course.",
                "How do I calculate my GPA?": "GPA is calculated by dividing total grade points by total credit hours. I can calculate yours if you ask 'What is my GPA?'",
                "How do I request a transcript?": "You can request an official transcript through the registrar's office or by asking me to submit a transcript request on your behalf.",
                "How do I get an enrollment certificate?": "Enrollment verification certificates can be requested through the registrar. Ask me to start a request.",
                "When are my assignments due?": "I can show your upcoming deadlines. Ask me 'What are my deadlines?' or click the Deadlines quick action.",
                "Where is my exam?": "I can look up your exam schedule and room locations. Ask 'What is my exam schedule?'",
                "What are the term dates?": "The academic calendar with term dates, holidays, and key deadlines is available. Ask me 'Show academic calendar'.",
                "How do I search the library?": "I can search library resources for you. Ask 'Search library for [topic]' or 'Is [book title] available?'",
                "What is my timetable?": "I can show your class schedule. Ask 'Show my timetable' or click the Schedule quick action."
            },
            "financial": {
                "When are tuition payments due?": "Tuition is typically due before the start of each semester. I can show your specific payment deadlines.",
                "How do I apply for financial aid?": "Submit the FAFSA form and university scholarship applications. Ask me about your financial aid status.",
                "What payment methods are accepted?": "We accept credit cards, bank transfers, and payment plans. Contact the finance office for payment plan setup.",
                "What is my fee balance?": "I can check your current fee balance and upcoming payment deadlines. Ask 'What is my balance?'",
                "What is my financial aid status?": "I can check the status of your financial aid applications. Ask 'Check my financial aid'."
            },
            "technical": {
                "How do I reset my password?": "Use the 'Forgot Password' link on the login page or contact IT support.",
                "How do I connect to campus WiFi?": "Connect to 'UniversityWiFi' and use your student credentials.",
                "Where can I download campus software?": "Visit the IT services website for software downloads.",
                "How do I access the LMS?": "Access Moodle/Canvas through the student portal using your SSO credentials. Contact IT if you have access issues.",
                "How does SSO work?": "Single Sign-On lets you access all university systems with one login. Use your university email and password."
            },
            "admissions": {
                "How do I check my application status?": "I can look up your application status. Ask 'What is my application status?' or provide your application reference.",
                "What documents do I need to submit?": "Required documents vary by programme. Generally: transcripts, personal statement, references, and ID. Ask me about a specific programme.",
                "What scholarships are available?": "We offer merit-based, need-based, and subject-specific scholarships. Ask me about eligibility criteria.",
                "How do I book a campus tour?": "Campus tours can be scheduled through admissions. I can help you book one — just ask."
            },
            "administrative": {
                "How do I apply for a leave of absence?": "Submit a leave of absence request through the student office. I can guide you through the process.",
                "How do I request a deferral?": "Deferral requests are handled by the registrar. I can explain the process and requirements.",
                "How do I replace my ID card?": "Report your lost ID and request a replacement through the student services desk. I can start the process.",
                "How do I book a room?": "Rooms and facilities can be booked through the booking system. Ask me 'Book a room' for guidance.",
                "How do I find a staff member?": "I can search the staff directory. Ask 'Find [name]' or 'Contact [department]'."
            },
            "wellbeing": {
                "Where can I get mental health support?": "The university counselling service offers free, confidential support. Call the wellbeing helpline or visit the Student Wellbeing Centre.",
                "What events are happening on campus?": "I can show upcoming campus events. Ask 'Show events' or click the Events quick action.",
                "What clubs and societies are available?": "There are many student clubs and societies. Ask me about a specific interest or say 'Show clubs'.",
                "I lost something on campus": "Report lost items to the lost and found service. I can help you file a report — just describe the item.",
                "What is the shuttle schedule?": "Campus shuttle and transport schedules are available. Ask 'Show transport schedule' for routes and times."
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
            print("• Student Services: courses, grades, GPA, timetable, fee balance, transcripts")
            print("• Academic Support: deadlines, exam schedule, library search, academic calendar")
            print("• Admissions: application status, scholarships, campus tours")
            print("• Admin: leave requests, ID card replacement, room booking, staff directory")
            print("• Wellbeing: mental health resources, clubs, lost & found, transport")
        elif user['role'] in ['staff', 'admin']:
            print("• Student information lookup and management")
            print("• Course and registration management")
            print("• Financial and administrative support")
            print("• Staff directory and room booking")
            print("• Analytics and system information")
        elif user['role'] == 'instructor':
            print("• Course management and student support")
            print("• Grade information and academic records")
            print("• Exam scheduling and room locations")
            print("• Library resources and staff directory")

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
                    print("\n  Student Services:")
                    print("    - Courses, grades, GPA, timetable, fee balance, transcripts")
                    print("  Academic Support:")
                    print("    - Deadlines, exam schedule, library search, academic calendar")
                    print("  Admissions:")
                    print("    - Application status, scholarships, document guidance, campus tours")
                    print("  Administrative:")
                    print("    - Leave of absence, ID card, room booking, staff directory")
                    print("  Wellbeing & Campus Life:")
                    print("    - Mental health, clubs & societies, lost & found, transport")
                    print(f"\n  Your role: {current_user['role']}")
                    print(f"  Available permissions: {len(current_user.get('permissions', []))}")
                    if hasattr(self, 'voice_interface') and getattr(self.voice_interface, 'enabled', False):
                        print("  Voice commands: 'start voice mode', 'test voice'")
                    print("  'exit' to return to main menu")
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
