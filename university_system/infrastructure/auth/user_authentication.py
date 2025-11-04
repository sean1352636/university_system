from typing import Optional, Dict, List, Any, Union, Tuple
import json
import traceback
import logging
from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import hashlib
import secrets
import re
import os
import time
from datetime import datetime, timedelta
import pyotp
import qrcode
import io
import base64
import contextlib
import threading
import logging
import traceback
from pathlib import Path
from university_system.infrastructure.database.db import get_connection
import sys
from pathlib import Path
from university_system.modules.shared.constants import paths

# Import custom exceptions
from university_system.infrastructure.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    SessionExpiredError,
    PermissionDeniedError,
    MFARequiredError,
    ValidationError,
    InvalidInputError,
    DatabaseError,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Import centralized activity logger
try:
    from university_system.modules.shared.utils.activity_logger import (
        set_user, log_login, log_logout, log_activity, log_access
    )
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

class MinimalVoiceInterface:
    """Minimal voice interface placeholder"""
    def __init__(self):
        self.enabled = False
    
    def initialize(self):
        return False
    
    def cleanup(self):
        """Cleanup voice interface resources"""
        self.enabled = False
        # Minimal cleanup - no resources to release in minimal implementation

# Chatbot integration - Corrected version
CHATBOT_AVAILABLE = False
UniversityChatbot = None

try:
    from university_system.utils.ai.university_chatbot import UniversityChatbot
    CHATBOT_AVAILABLE = True
    logger.info("Chatbot module imported successfully")
except ImportError as e:
    logger.warning(f"Failed to import UniversityChatbot: {e}")
    logger.info("Creating minimal chatbot implementation as a fallback")
    
    # Define a minimal chatbot class as a fallback
    class UniversityChatbot:
        def __init__(self):
            logger.debug("Minimal fallback chatbot initialized")
        def process_message(self, message, user_id, session_id=None, is_voice=False, **kwargs):
            return "I am a minimal chatbot fallback. Please check the 'src.infrastructure.university_chatbot' import path."

if not CHATBOT_AVAILABLE or UniversityChatbot is None:
    logger.warning("Chatbot module could not be imported, using fallback implementation")
    
    class UniversityChatbot:
        def __init__(self, db_path=None, config_path=None):
            """Complete minimal chatbot with all required attributes"""
            try:
                # Core attributes
                default_db = os.fspath(paths.DEFAULT_DB_PATH)
                default_config = os.fspath(paths.CHATBOT_CONFIG_PATH)
                self.db_path = os.fspath(db_path) if db_path else default_db
                if config_path:
                    candidate = Path(config_path)
                    self.config_path = os.fspath(candidate if candidate.is_absolute() else paths.CHATBOT_CONFIG_PATH.parent / candidate)
                else:
                    self.config_path = default_config
                self.auth_system = None
                self.conversation_history = {}
                self.enabled = True
                
                # Load configuration
                self.config = self.load_config()
                
                # Initialize ALL expected attributes to prevent AttributeError
                self.app = None  # Flask app (not used in minimal version)
                self.voice_interface = None  # Voice interface (not used in minimal)
                self.nlp = None
                self.intent_classifier = None
                self.sentiment_analyzer = None
                self.qa_pipeline = None
                self.vectorizer = None
                self.intents = {}
                self.faq_database = {}
                self.authenticated_sessions = {}
                self.conversation_contexts = {}
                self.log_dir = os.fspath(paths.LOG_DIR)
                self.upload_dir = os.fspath(paths.CHATBOT_UPLOAD_DIR)
                self.models_dir = os.fspath(paths.CHATBOT_MODELS_DIR)
                
                # Create directories if they don't exist
                self._ensure_directories()

                logger.debug("Minimal chatbot initialized with all attributes")

            except Exception as e:
                logger.error(f"Error in minimal chatbot init: {e}")
                self._set_emergency_defaults()

        def _set_emergency_defaults(self):
            """Set absolute minimum defaults if initialization fails"""
            self.db_path = os.fspath(paths.DEFAULT_DB_PATH)
            self.config_path = os.fspath(paths.CHATBOT_CONFIG_PATH)
            self.auth_system = None
            self.conversation_history = {}
            self.enabled = True
            self.config = {"max_message_length": 500}
            self.app = None
            self.voice_interface = None
            logger.warning("Emergency defaults set for minimal chatbot")
        
        def _ensure_directories(self):
            """Create necessary directories"""
            try:
                import os
                for directory in [
                    getattr(self, 'log_dir', os.fspath(paths.LOG_DIR)),
                    getattr(self, 'upload_dir', os.fspath(paths.CHATBOT_UPLOAD_DIR)),
                    getattr(self, 'models_dir', os.fspath(paths.CHATBOT_MODELS_DIR)),
                ]:
                    if directory:
                        os.makedirs(directory, exist_ok=True)
            except Exception as e:
                logger.error(f"Directory creation failed: {e}")
        
        def load_config(self):
            """Load configuration with comprehensive error handling"""
            import json
            import os
            
            default_config = {
                "max_message_length": 500,
                "session_timeout": 1800,
                "enable_logging": True,
                "response_delay": 0.5,
                "voice": {"enabled": False},
                "features": {"voice_enabled": False, "analytics_enabled": False},
                "database": {"host": "localhost"},
                "security": {"session_timeout": 3600}
            }
            
            try:
                if os.path.exists(self.config_path):
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        file_config = json.load(f)
                    # Merge configs
                    merged_config = default_config.copy()
                    merged_config.update(file_config)
                    return merged_config
                else:
                    return default_config
            except Exception as e:
                logger.error(f"Config loading failed: {e}")
                return default_config

        def set_auth_system(self, auth_system):
            """Set authentication system"""
            try:
                self.auth_system = auth_system
                logger.info("Authentication system integrated with minimal chatbot")
            except Exception as e:
                logger.error(f"Auth system integration failed: {e}")
        
        def process_message(self, message, user_id, session_id=None, is_voice=False):
            """Process messages with enhanced error handling"""
            try:
                if not message or not message.strip():
                    return "Please provide a message."
                
                # Limit message length
                max_length = self.config.get("max_message_length", 500)
                if len(message) > max_length:
                    message = message[:max_length]
                
                message_lower = message.lower()
                
                # Get user context
                role = "guest"
                permissions = []
                username = user_id
                
                try:
                    if (self.auth_system and 
                        hasattr(self.auth_system, 'current_user') and 
                        self.auth_system.current_user):
                        role = self.auth_system.current_user.get('role', 'guest')
                        permissions = self.auth_system.current_user.get('permissions', [])
                        username = self.auth_system.current_user.get('username', user_id)
                except Exception:
                    pass  # Use defaults if auth fails
                
                # Generate response
                response = self._generate_response(message_lower, role, permissions, username)
                
                # Track conversation
                self._track_conversation(user_id, message, response, session_id, is_voice)
                
                return response

            except Exception as e:
                logger.error(f"Message processing error: {e}")
                return "I apologize, but I encountered an error. Please try again."
        
        def _generate_response(self, message_lower, role, permissions, username):
            """Generate contextual responses based on user role"""
            # Personal greeting
            if any(word in message_lower for word in ['hello', 'hi', 'hey', 'good morning']):
                if role == 'student':
                    return f"Hello {username}! I'm here to help with your academic needs. What can I assist you with today?"
                elif role == 'staff':
                    return f"Hello {username}! I can help with student information and administrative tasks."
                elif role == 'admin':
                    return f"Hello {username}! I have full access to help with system functions."
                else:
                    return "Hello! I'm the University Chatbot. How can I help you today?"
            
            # Course information
            elif any(word in message_lower for word in ['course', 'class', 'program', 'module', 'subject']):
                if role == 'student':
                    return "I can help you find course information, check prerequisites, and guide you through registration. What specific course or program interests you?"
                elif role in ['staff', 'admin']:
                    return "I can assist with course management, enrollment tracking, and academic planning. What course information do you need?"
                else:
                    return "I can provide general course information. For enrollment details, please contact the registrar's office."
            
            # Grades and academic records
            elif any(word in message_lower for word in ['grade', 'gpa', 'transcript', 'academic record', 'marks']):
                if 'view_own_grades' in permissions or role in ['staff', 'admin']:
                    return "I can help with grade information. For official transcripts, check your student portal or contact the registrar's office."
                else:
                    return "For grade information, please log into your student portal or contact the registrar's office."
            
            # Financial information
            elif any(word in message_lower for word in ['fee', 'tuition', 'payment', 'financial', 'money', 'cost']):
                if 'view_own_finances' in permissions or role in ['staff', 'admin']:
                    return "I can help with financial information including tuition, fees, and payment options. Check your student account for specific details."
                else:
                    return "For financial information, please visit the bursar's office or log into your student account."
            
            # Registration
            elif any(word in message_lower for word in ['register', 'enroll', 'sign up', 'add course', 'drop course']):
                if role == 'student':
                    return "I can guide you through registration. Use the student portal during registration periods. Need help with course selection?"
                elif role in ['staff', 'admin']:
                    return "I can help with student registration management and enrollment processes."
                else:
                    return "For registration, please contact the registrar's office or check the academic calendar."
            
            # Schedule and timetable
            elif any(word in message_lower for word in ['schedule', 'timetable', 'calendar', 'when', 'time']):
                return "For schedule information, check your student portal or the university's academic calendar website."
            
            # Library services
            elif any(word in message_lower for word in ['library', 'book', 'borrow', 'reserve']):
                return "For library services including book search, reservations, and hours, visit the library website or contact library services."
            
            # Technical support
            elif any(word in message_lower for word in ['password', 'login', 'technical', 'computer', 'wifi', 'email']):
                return "For technical support including password resets and IT issues, contact the IT helpdesk or visit the IT services website."
            
            # Help and support
            elif any(word in message_lower for word in ['help', 'support', 'assist', 'what can you do']):
                features = self._get_role_features(role)
                return f"I'm here to help! Available services:\n" + "\n".join(features)
            
            # Campus and location
            elif any(word in message_lower for word in ['campus', 'location', 'where', 'map', 'building']):
                return "For campus maps and building locations, check the university website or visit the information desk."
            
            # Emergency or urgent
            elif any(word in message_lower for word in ['emergency', 'urgent', 'help me', 'problem']):
                return "For emergencies, call campus security immediately. For urgent academic issues, contact your advisor or the dean's office."
            
            # Default response
            else:
                if role == 'guest':
                    return "I'm here to help with university questions. Try asking about courses, grades, registration, or fees. For personalized help, please log in."
                else:
                    return f"I'm here to help with university questions. As a {role}, you can ask about courses, grades, registration, financial information, or general policies. What would you like to know?"
        
        def _get_role_features(self, role):
            """Get available features based on user role"""
            if role == 'student':
                return [
                    "• Course information and prerequisites",
                    "• Registration assistance", 
                    "• Grade and transcript inquiries",
                    "• Financial aid and payment information",
                    "• Campus resources and services"
                ]
            elif role == 'staff':
                return [
                    "• Student information lookup",
                    "• Course and enrollment management",
                    "• Administrative procedures",
                    "• Report generation",
                    "• System information"
                ]
            elif role == 'admin':
                return [
                    "• Full system access",
                    "• User and role management", 
                    "• System configuration",
                    "• Comprehensive reporting",
                    "• Database operations"
                ]
            else:
                return [
                    "• General university information",
                    "• Course catalogs",
                    "• Contact information",
                    "• Campus resources"
                ]
        
        def _track_conversation(self, user_id, message, response, session_id, is_voice):
            """Track conversations with comprehensive logging"""
            try:
                from datetime import datetime
                
                if user_id not in self.conversation_history:
                    self.conversation_history[user_id] = []
                
                conversation_entry = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'session_id': session_id,
                    'message': message,
                    'response': response,
                    'type': 'voice' if is_voice else 'text',
                    'message_length': len(message),
                    'response_length': len(response)
                }
                
                self.conversation_history[user_id].append(conversation_entry)
                
                # Maintain conversation history limit
                max_history = 50
                if len(self.conversation_history[user_id]) > max_history:
                    self.conversation_history[user_id] = self.conversation_history[user_id][-max_history:]
                
                # Log to auth system if available
                self._log_to_auth_system(user_id, message, response)

            except Exception as e:
                logger.error(f"Conversation tracking error: {e}")

        def _log_to_auth_system(self, user_id, message, response):
            """Log conversation to auth system"""
            try:
                if (self.auth_system and
                    hasattr(self.auth_system, '_log_activity') and
                    self.auth_system.current_user):

                    truncated_msg = message[:50] + ('...' if len(message) > 50 else '')
                    truncated_resp = response[:50] + ('...' if len(response) > 50 else '')

                    self.auth_system._log_activity(
                        user_id,
                        'Chatbot interaction',
                        f"Q: {truncated_msg} A: {truncated_resp}",
                        self.auth_system.current_user.get('id')
                    )
            except Exception as e:
                logger.error(f"Auth logging error: {e}")
        
        def run_authenticated_console_interface(self):
            """Enhanced console interface with better error handling"""
            print("University Chatbot (Minimal Mode)")
            print("=" * 40)
            
            # Validate authentication
            if not self.auth_system:
                print("Error: No authentication system available.")
                return
            
            if not hasattr(self.auth_system, 'current_user') or not self.auth_system.current_user:
                print("Error: No authenticated user found.")
                return
            
            # Check session validity
            if hasattr(self.auth_system, 'check_session'):
                if not self.auth_system.check_session():
                    print("Error: Your session has expired.")
                    return
            
            user = self.auth_system.current_user
            print(f"Welcome {user['username']}! You are logged in as {user['role']}.")
            
            # Check permissions
            if 'access_chatbot' not in user.get('permissions', []):
                print("You don't have permission to access the chatbot.")
                return
            
            # Show help information
            print(f"\nAvailable features for {user['role']}:")
            features = self._get_role_features(user['role'])
            for feature in features:
                print(feature)
            
            print("\nType 'exit' to return, 'help' for commands, or start asking questions!")
            
            session_id = f"{user['username']}_{int(datetime.now().timestamp())}"
            
            # Main chat loop
            while True:
                try:
                    # Check session periodically
                    if (hasattr(self.auth_system, 'check_session') and 
                        not self.auth_system.check_session()):
                        print("\nYour session has expired.")
                        break
                    
                    user_input = input(f"\n{user['username']}: ")
                    
                    # Handle commands
                    if user_input.lower() in ['exit', 'quit', 'back', 'logout']:
                        print("Returning to main menu...")
                        break
                    
                    if user_input.lower() == 'help':
                        print("\nAvailable commands:")
                        print("- Ask about courses, registration, grades, fees")
                        print("- Request information based on your role")
                        print(f"- Your role: {user['role']}")
                        print("- Type 'exit' to return to main menu")
                        continue
                    
                    if user_input.lower() == 'history':
                        history = self.get_conversation_history(user['username'], 5)
                        if history:
                            print("\nRecent conversations:")
                            for i, conv in enumerate(history, 1):
                                print(f"{i}. {conv['timestamp']}: {conv['message'][:30]}...")
                        else:
                            print("No conversation history found.")
                        continue
                    
                    if not user_input.strip():
                        print("Please enter a message, 'help' for commands, or 'exit' to return.")
                        continue
                    
                    # Process message
                    response = self.process_message(user_input, user['username'], session_id)
                    print(f"Chatbot: {response}")
                    
                except KeyboardInterrupt:
                    print("\n\nInterrupted. Returning to main menu...")
                    break
                except EOFError:
                    print("\nSession ended. Returning to main menu...")
                    break
                except Exception as e:
                    logger.error(f"Chat error: {e}")
                    print("Please try again or type 'exit' to return.")

            print(f"Chatbot session ended for {user['username']}. Thank you!")

        def get_conversation_history(self, username, limit=10):
            """Get conversation history with error handling"""
            try:
                return self.conversation_history.get(username, [])[-limit:]
            except Exception as e:
                logger.error(f"History retrieval error: {e}")
                return []
        
        # Additional methods that might be expected by the auth system
        def run_web_server(self, host='0.0.0.0', port=5000):
            """Stub for web server (not implemented in minimal version)"""
            print("Web server not available in minimal chatbot mode.")
            print(f"To enable web server, please install the full chatbot module.")
            return False
        
        def setup_api_routes(self):
            """Stub for API routes (not implemented in minimal version)"""
            print("API routes not available in minimal chatbot mode.")
            return None
        
        def run_console_interface(self):
            """Basic console interface without authentication"""
            print("University Chatbot (Basic Mode)")
            print("=" * 35)
            
            user_id = input("Enter your ID: ") or "guest"
            print(f"Welcome {user_id}! Type 'exit' to quit.")
            
            while True:
                try:
                    user_input = input(f"\n{user_id}: ")
                    
                    if user_input.lower() in ['exit', 'quit']:
                        print("Goodbye!")
                        break
                    
                    if not user_input.strip():
                        print("Please enter a message.")
                        continue
                    
                    response = self.process_message(user_input, user_id)
                    print(f"Chatbot: {response}")
                    
                except KeyboardInterrupt:
                    print("\nGoodbye!")
                    break
        
        def run(self):
            """Main run method"""
            if (self.auth_system and 
                hasattr(self.auth_system, 'current_user') and 
                self.auth_system.current_user):
                self.run_authenticated_console_interface()
            else:
                self.run_console_interface()

    CHATBOT_AVAILABLE = True  # Mark as available
    
    logger.info("Complete minimal chatbot implementation created")

# Global variable to store the current auth instance
_current_auth_instance = None

def get_current_user():
    """Get the current logged-in user information"""
    if _current_auth_instance and _current_auth_instance.current_user:
        return _current_auth_instance.current_user
    return None

def set_auth_instance(auth_instance):
    """Set the global auth instance"""
    global _current_auth_instance
    _current_auth_instance = auth_instance

# Constants
ROLES = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records'
}

# Updated Permission sets for different roles with AI detector permissions
PERMISSIONS = {
    'admin': [
        'create_student', 'view_any_student', 'update_any_student', 'delete_any_student',
        'view_own_record', 'update_own_profile',
        'manage_modules', 'view_assigned_modules',
        'manage_users', 'manage_roles',
        'manage_schedules', 'view_own_timetable', 'export_data',
        'manage_academic_calendar', 'view_academic_calendar',
        'view_reports', 'generate_reports', 'view_analytics',
        'backup_restore', 'system_config', 'view_logs',
        'export_data', 'import_data', 'export_module_data',
        'manage_grades', 'view_own_grades', 'manage_module_grades',
        'manage_attendance', 'view_own_attendance', 'manage_module_attendance',
        'manage_schedules', 'view_own_timetable', 'send_emails', 'batch_operations',
        'delete_any_permit', 'delete_own_permit', 'view_own_permit', 'update_own_permit',
        'update_violation', 'delete_violation', 'view_parking_lots', 'manage_parking_lots',
        'generate_reports', 'manage_books', 'manage_loans', 'view_books', 'checkout_books', 'view_loans',
        'manage_parking', 'create_permit', 'view_any_permit', 'update_any_permit',
        'delete_any_permit', 'register_vehicle', 'view_any_vehicle', 'update_any_vehicle',
        'delete_any_vehicle', 'record_violation', 'view_any_violation', 'update_violation',
        'delete_violation', 'manage_parking_lots', 'view_parking_lots',
        'view_own_permit', 'update_own_permit', 'register_own_vehicle', 'view_own_vehicle',
        'update_own_vehicle', 'view_own_violation',
        'manage_finances', 'view_financial_reports', 'export_financial_data', 'record_payments',
        'view_own_finances',
        'manage_alumni', 'view_alumni', 'view_own_alumni_profile', 'manage_events',
        'view_events', 'make_donation', 'view_own_donations', 'manage_mentorships',
        'view_menu', 'place_own_order', 'manage_menu', 'create_order',
        'view_internships', 'manage_internships', 'apply_for_internship', 'view_own_applications',
        'view_own_health_record', 'view_any_health_record', 'manage_health_records',
        'schedule_health_appointment', 'view_own_appointments', 'manage_health_appointments',
        'view_own_vaccinations', 'manage_vaccinations', 'view_health_advisories',
        'issue_health_advisories', 'view_health_resources', 'manage_courses', 'view_courses',
        'manage_accommodations', 'view_accommodations', 'approve_accommodations',
        # AI Detector permissions for admin (full access)
        'access_ai_detector', 'analyze_submissions', 'view_own_ai_results', 
        'view_any_ai_results', 'manage_ai_whitelist', 'configure_ai_detector', 
        'view_ai_statistics',
        # Plagiarism permissions for admin
        'check_plagiarism', 'manage_plagiarism_system', 'submit_document', 
        'check_plagiarism_any_course', 'access_plagiarism_menu',
        'manage_trips', 'create_trips', 'view_trips', 'register_for_trips',
        'view_own_trip_registrations', 'cancel_trip_registration',
        'manage_trip_participants', 'view_trip_reports', 'manage_trip_expenses',
        'approve_trip_registrations'
    ],
    'staff': [
        'create_student', 'view_any_student', 'update_any_student',
        'manage_modules', 'view_assigned_modules',
        'view_reports', 'generate_reports', 'view_analytics',
        'export_data', 'export_module_data', 'view_assignments',
        'manage_assignments', 'grade_assignments', 
        'view_all_submissions', 'export_submission_data',
        'manage_grades', 'manage_attendance', 'manage_schedules',
        'send_emails', 'manage_courses', 'view_courses',
        'view_books', 'checkout_books', 'view_loans',
        'manage_schedules', 'view_own_timetable', 'export_data',
        'manage_academic_calendar', 'view_academic_calendar',
        'create_permit', 'view_any_permit', 'update_any_permit',
        'register_vehicle', 'view_any_vehicle', 'record_violation',
        'view_any_violation', 'view_parking_lots',
        'record_payments', 'view_financial_reports',
        'view_alumni', 'manage_events', 'view_events',
        'view_menu', 'place_own_order',
        'view_internships', 'manage_internships',
        'view_health_resources', 'view_health_advisories',
        'view_accommodations', 
        'access_ai_detector', 'analyze_submissions', 
        'view_any_ai_results', 'view_ai_statistics',
        'check_plagiarism', 'submit_document', 'access_plagiarism_menu',
        'create_trips', 'view_trips', 'manage_trip_participants',
        'view_trip_reports', 'manage_trip_expenses', 'approve_trip_registrations',
    ],
    'student': [
        'view_own_record', 'update_own_profile',
        'view_own_grades', 'view_own_attendance', 'view_own_timetable', 'view_assigned_modules',
        'view_books', 'checkout_books', 'view_loans','view_courses',
        'view_own_permit', 'update_own_permit', 'register_own_vehicle', 'view_own_vehicle',
        'update_own_vehicle', 'view_own_violation',
        'view_own_finances', 'view_assignments', 'submit_assignment', 'view_own_submissions',
        'view_own_alumni_profile', 'view_events', 'make_donation', 'view_own_donations',
        'view_menu', 'place_own_order', 'view_own_timetable', 'view_academic_calendar',
        'view_internships', 'apply_for_internship', 'view_own_applications',
        'view_own_health_record', 'schedule_health_appointment', 'view_own_appointments',
        'view_own_vaccinations', 'view_health_advisories', 'view_health_resources',
        'send_emails', 'view_messages', 'send_messages', 'view_announcements',             
        'access_communication_dashboard', 'use_chat_rooms', 'manage_notification_preferences',
        'access_ai_detector', 'analyze_submissions', 'view_own_ai_results',
        'submit_document', 'access_plagiarism_menu',
        'view_trips', 'register_for_trips', 'view_own_trip_registrations',
        'cancel_trip_registration'
    ],
    'instructor': [
        'view_assigned_modules', 'manage_module_grades', 'view_module_students',
        'manage_module_attendance', 'export_module_data',
        'send_emails', 'view_assignments', 'manage_assignments',
        'grade_assignments', 'view_all_submissions', 'export_submission_data',
        'view_own_timetable', 'manage_schedules',
        'view_own_timetable', 'manage_schedules', 'view_academic_calendar',
        'view_books', 'view_health_resources', 'view_menu',
        'access_ai_detector', 'analyze_submissions', 
        'view_any_ai_results', 'view_ai_statistics',
        'check_plagiarism', 'submit_document', 'access_plagiarism_menu',
        'view_trips', 'register_for_trips', 'view_own_trip_registrations',
        'cancel_trip_registration'
    ],
    'parent': [
        'view_child_records', 'view_academic_calendar', 'view_child_grades', 
        'view_child_attendance', 'view_teacher_reports', 'message_teachers',
        'view_child_timetable', 'view_child_assignments', 'set_notification_preferences',
        'update_contact_info', 'view_school_calendar', 'report_absence', 'access_parent_dashboard'
    ]
}

# Missing function definitions for user_authentication.py

def initialize_complete_system():
    """Initialize the complete system with chatbot integration"""
    print("=== INITIALIZING COMPLETE UNIVERSITY SYSTEM ===")
    
    try:
        # Initialize authentication
        print("1. Initializing authentication system...")
        auth = UserAuth()
        
        # Setup chatbot permissions
        print("2. Setting up chatbot permissions...")
        auth.setup_chatbot_permissions()
        
        # Initialize chatbot integration
        print("3. Initializing chatbot integration...")
        auth.initialize_chatbot_integration()
        
        # Test the integration
        print("4. Testing integration...")
        if CHATBOT_AVAILABLE:
            print("✓ Chatbot integration available")
        else:
            logger.warning("Chatbot integration not available")
        
        print("5. System initialization completed!")
        print("\nAvailable features:")
        print("- User authentication and authorization")
        print("- Role-based access control")
        print("- University chatbot with voice support")
        print("- Integrated conversation logging")
        print("- Analytics and reporting")
        
        return auth
        
    except Exception as e:
        print(f"❌ System initialization failed: {e}")
        return None

def init_trip_db():
    """Initialize trip management database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create trips table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            destination TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            max_participants INTEGER,
            cost REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
        
        # Create trip registrations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trip_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            registration_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(trip_id, user_id)
        )
        ''')
        
        # Create trip expenses table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trip_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date TEXT NOT NULL,
            category TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
        
        conn.commit()
        conn.close()
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Error initializing trip database: {e}")
        return False

def setup_trip_permissions():
    """Setup trip management permissions"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Trip permissions
        trip_permissions = [
            ('manage_trips', 'Manage Trip Records'),
            ('create_trips', 'Create New Trips'),
            ('view_trips', 'View Trip Information'),
            ('register_for_trips', 'Register for Trips'),
            ('view_own_trip_registrations', 'View Own Trip Registrations'),
            ('cancel_trip_registration', 'Cancel Trip Registration'),
            ('manage_trip_participants', 'Manage Trip Participants'),
            ('view_trip_reports', 'View Trip Reports'),
            ('manage_trip_expenses', 'Manage Trip Expenses'),
            ('approve_trip_registrations', 'Approve Trip Registrations')
        ]
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for perm_name, perm_desc in trip_permissions:
            cursor.execute(
                'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                (perm_name, perm_desc, timestamp)
            )
        
        # Assign permissions to roles
        role_permissions = {
            'admin': [
                'manage_trips', 'create_trips', 'view_trips', 'register_for_trips',
                'view_own_trip_registrations', 'cancel_trip_registration',
                'manage_trip_participants', 'view_trip_reports', 'manage_trip_expenses',
                'approve_trip_registrations'
            ],
            'staff': [
                'create_trips', 'view_trips', 'manage_trip_participants',
                'view_trip_reports', 'manage_trip_expenses', 'approve_trip_registrations'
            ],
            'instructor': [
                'view_trips', 'register_for_trips', 'view_own_trip_registrations',
                'cancel_trip_registration'
            ],
            'student': [
                'view_trips', 'register_for_trips', 'view_own_trip_registrations',
                'cancel_trip_registration'
            ]
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
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Error setting up trip permissions: {e}")
        return False

def set_trip_auth(auth_instance):
    """Set the authentication instance for trip management"""
    global _trip_auth_instance
    _trip_auth_instance = auth_instance
    logging.info("Trip management authentication configured")

def integrate_trip_management_with_main():
    """Integrate trip management with the main system"""
    try:
        # Initialize trip database
        if not init_trip_db():
            logging.error("Failed to initialize trip database")
            return False
        
        # Setup permissions
        if not setup_trip_permissions():
            logging.error("Failed to setup trip permissions")
            return False
        
        logging.info("Trip management integration completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"Error integrating trip management: {e}")
        return False

# Global variable for trip auth instance
_trip_auth_instance = None

def add_finance_permissions():
    """Add finance-related permissions to the database"""
    auth = UserAuth()
    finance_permissions = [
        ('view_financial_reports', 'View Financial Reports'),
        ('manage_finances', 'Manage Financial Records'),
        ('export_financial_data', 'Export Financial Data'),
        ('record_payments', 'Record Payment Transactions')
    ]
    
    created_permissions = []
    for perm_name, perm_desc in finance_permissions:
        try:
            conn = sqlite3.connect(auth.db_path)
            cursor = conn.cursor()
            
            # Check if permission already exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            if not cursor.fetchone():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                conn.commit()
                created_permissions.append(perm_name)
            
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Error creating permission {perm_name}: {e}")
    
    return created_permissions

def fix_alumni_permissions():
    """Fix alumni permissions for existing database"""
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # All alumni-related permissions that should exist
    all_alumni_permissions = [
        ('manage_alumni', 'Manage Alumni'),
        ('view_alumni', 'View Alumni'),
        ('view_own_alumni_profile', 'View Own Alumni Profile'),
        ('update_own_alumni_profile', 'Update Own Alumni Profile'),
        ('manage_events', 'Manage Events'),
        ('view_events', 'View Events'),
        ('make_donation', 'Make Donation'),
        ('view_own_donations', 'View Own Donations'),
        ('manage_donations', 'Manage Donations'),
        ('manage_mentorships', 'Manage Mentorships'),
        ('view_own_mentorships', 'View Own Mentorships')
    ]
    
    # Create any missing permissions
    for perm_name, perm_desc in all_alumni_permissions:
        cursor.execute(
            'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
            (perm_name, perm_desc, timestamp)
        )
    
    conn.commit()
    print("Created missing alumni permissions")
    
    # Now assign them to the admin role
    cursor.execute('SELECT id FROM roles WHERE role_name = ?', ('admin',))
    admin_role = cursor.fetchone()
    
    if admin_role:
        admin_role_id = admin_role[0]
        
        for perm_name, _ in all_alumni_permissions:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            perm = cursor.fetchone()
            
            if perm:
                perm_id = perm[0]
                cursor.execute(
                    'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                    (admin_role_id, perm_id)
                )
        
        conn.commit()
        print("Assigned alumni permissions to admin role")
    
    # Also assign appropriate permissions to other roles
    role_permissions = {
        'staff': ['view_alumni', 'manage_events', 'view_events'],
        'alumni': ['view_own_alumni_profile', 'update_own_alumni_profile', 'view_events', 
                  'view_own_donations', 'make_donation'],
        'student': ['view_events']
    }
    
    for role_name, permissions in role_permissions.items():
        cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
        role = cursor.fetchone()
        
        if role:
            role_id = role[0]
            
            for perm_name in permissions:
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                perm = cursor.fetchone()
                
                if perm:
                    perm_id = perm[0]
                    cursor.execute(
                        'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                        (role_id, perm_id)
                    )
            
            print(f"Assigned alumni permissions to {role_name} role")
    
    conn.commit()
    conn.close()
    print("\nAlumni permissions have been fixed!")
    print("Please restart your application and try logging in as admin again.")

def get_health_role_permissions():
    """
    Return a dictionary of health-related permissions for different roles.
    This can be used when creating new roles in the system.
    """
    return {
        'admin': [
            'manage_health_records',
            'view_any_health_record',
            'manage_health_appointments',
            'verify_vaccinations',
            'issue_health_advisories',
            'view_health_advisories',
            'view_health_resources'
        ],
        'health_provider': [
            'manage_health_records',
            'view_any_health_record',
            'manage_health_appointments',
            'manage_vaccinations',
            'verify_vaccinations',
            'issue_health_advisories',
            'view_health_advisories',
            'view_health_resources'
        ],
        'staff': [
            'view_health_advisories',
            'view_vaccination_requirements',
            'view_health_resources'
        ],
        'student': [
            'view_own_health_record',
            'schedule_health_appointment',
            'view_own_appointments',
            'cancel_own_appointment',
            'view_own_vaccinations',
            'update_insurance_info',
            'view_health_advisories',
            'view_health_resources'
        ]
    }

def add_calendar_permissions():
    """Add calendar-related permissions to the database"""
    auth = UserAuth()
    calendar_permissions = [
        ('manage_academic_calendar', 'Manage Academic Calendar'),
        ('view_academic_calendar', 'View Academic Calendar'),
        ('create_academic_events', 'Create Academic Events'),
        ('update_academic_events', 'Update Academic Events'),
        ('delete_academic_events', 'Delete Academic Events'),
        ('export_calendar_data', 'Export Calendar Data'),
        ('view_school_calendar', 'View School Calendar')
    ]
    
    try:
        conn = sqlite3.connect(auth.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for perm_name, perm_desc in calendar_permissions:
            # Check if permission already exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            if not cursor.fetchone():
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                print(f"Added permission: {perm_name}")
        
        conn.commit()
        conn.close()
        
        # Now associate these permissions with roles
        auth._init_db()  # This will update role-permission associations
        
        print("Calendar permissions added successfully!")
        
    except sqlite3.Error as e:
        logger.error(f"Error adding calendar permissions: {e}")

def setup_ai_detector_permissions():
    """Setup AI detector permissions in the database"""
    try:
        auth = UserAuth()
        
        # AI detector permissions with descriptions
        ai_permissions = [
            ('access_ai_detector', 'Access AI detector functionality'),
            ('analyze_submissions', 'Analyze submissions for AI-generated content'),
            ('view_own_ai_results', 'View AI detection results for own submissions'),
            ('view_any_ai_results', 'View AI detection results for any submission'),
            ('manage_ai_whitelist', 'Manage AI detector whitelist patterns'),
            ('configure_ai_detector', 'Configure AI detector settings'),
            ('view_ai_statistics', 'View AI detection statistics and reports')
        ]
        
        conn = sqlite3.connect(auth.db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        created_permissions = []
        for perm_name, perm_desc in ai_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                created_permissions.append(perm_name)
        
        # Update role-permission associations for AI permissions
        for role_name, permissions in PERMISSIONS.items():
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if role_result:
                role_id = role_result[0]
                
                for perm_name in permissions:
                    if perm_name in [p[0] for p in ai_permissions]:
                        cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                        perm_result = cursor.fetchone()
                        if perm_result:
                            perm_id = perm_result[0]
                            cursor.execute(
                                'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                                (role_id, perm_id)
                            )
                            if cursor.fetchone()[0] == 0:
                                cursor.execute(
                                    'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                    (role_id, perm_id)
                                )
        
        conn.commit()
        conn.close()
        
        if created_permissions:
            print(f"✅ Created AI permissions: {', '.join(created_permissions)}")
        else:
            logger.info("AI permissions already exist")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Error setting up AI permissions: {e}")
        return False

def verify_ai_detector_setup():
    """Verify that the AI detector is properly set up"""
    try:
        # Check database tables exist
        conn = get_connection()
        cursor = conn.cursor()
        
        required_tables = [
            'ai_detector_submissions',
            'ai_detector_results', 
            'ai_detector_settings',
            'ai_detector_indicators',
            'ai_detector_whitelist'
        ]
        
        missing_tables = []
        for table in required_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cursor.fetchone():
                missing_tables.append(table)
        
        # Check permissions exist
        ai_permissions = [
            'access_ai_detector', 'analyze_submissions', 'view_own_ai_results',
            'view_any_ai_results', 'manage_ai_whitelist', 'configure_ai_detector',
            'view_ai_statistics'
        ]
        
        missing_permissions = []
        for perm in ai_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm,))
            if cursor.fetchone()[0] == 0:
                missing_permissions.append(perm)
        
        conn.close()
        
        if missing_tables or missing_permissions:
            print(f"❌ AI Detector setup incomplete:")
            if missing_tables:
                print(f"   Missing tables: {', '.join(missing_tables)}")
            if missing_permissions:
                print(f"   Missing permissions: {', '.join(missing_permissions)}")
            return False
        else:
            logger.info("AI Detector setup verified")
            return True
            
    except Exception as e:
        print(f"❌ Error verifying AI detector setup: {e}")
        return False

def add_ai_detector_permissions_to_database(auth_instance):
    """Add AI detector permissions to the database during initialization"""
    try:
        conn = sqlite3.connect(auth_instance.db_path)
        cursor = conn.cursor()
        
        # Define AI detector permissions
        ai_permissions = [
            ('access_ai_detector', 'Access AI detector functionality'),
            ('analyze_submissions', 'Analyze submissions for AI-generated content'),
            ('view_own_ai_results', 'View AI detection results for own submissions'),
            ('view_any_ai_results', 'View AI detection results for any submission'),
            ('manage_ai_whitelist', 'Manage AI detector whitelist patterns'),
            ('configure_ai_detector', 'Configure AI detector settings'),
            ('view_ai_statistics', 'View AI detection statistics')
        ]
        
        # Add each permission if it doesn't exist
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for perm_name, perm_desc in ai_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                logging.info(f"Added permission: {perm_name}")
        
        # Associate permissions with roles
        
        # First, get the permission IDs
        perm_ids = {}
        for perm_name, _ in ai_permissions:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            result = cursor.fetchone()
            if result:
                perm_ids[perm_name] = result[0]
        
        # Define role-permission associations
        role_permissions = {
            'admin': [
                'access_ai_detector', 'analyze_submissions', 'view_own_ai_results', 
                'view_any_ai_results', 'manage_ai_whitelist', 'configure_ai_detector', 
                'view_ai_statistics'
            ],
            'staff': [
                'access_ai_detector', 'analyze_submissions', 
                'view_any_ai_results', 'view_ai_statistics'
            ],
            'instructor': [
                'access_ai_detector', 'analyze_submissions', 
                'view_any_ai_results', 'view_ai_statistics'
            ],
            'student': [
                'access_ai_detector', 'analyze_submissions', 'view_own_ai_results'
            ]
        }
        
        # Add role-permission associations
        for role_name, permissions in role_permissions.items():
            # Get role ID
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if not role_result:
                continue
                
            role_id = role_result[0]
            
            # Add permissions to role
            for perm_name in permissions:
                if perm_name in perm_ids:
                    perm_id = perm_ids[perm_name]
                    
                    # Check if association already exists
                    cursor.execute(
                        'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                        (role_id, perm_id)
                    )
                    
                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                            (role_id, perm_id)
                        )
                        logging.info(f"Added permission {perm_name} to role {role_name}")
        
        conn.commit()
        conn.close()
        
        logging.info("AI detector permissions configured successfully")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Database error adding AI permissions: {e}")
        return False
    except Exception as e:
        logging.error(f"Error adding AI permissions: {e}")
        logging.debug(traceback.format_exc())
        return False

def add_plagiarism_permissions(auth_instance=None):
    """Add plagiarism-related permissions to the database"""
    plagiarism_permissions = [
        ('check_plagiarism', 'Check documents for plagiarism'),
        ('manage_plagiarism_system', 'Manage plagiarism checking system settings'),
        ('submit_document', 'Submit documents to the plagiarism repository'),
        ('check_plagiarism_any_course', 'Check plagiarism across all courses'),
        ('access_plagiarism_menu', 'Access the plagiarism checker menu')
    ]
    
    created_permissions = []
    
    try:
        # Use direct database connection to avoid recursion
        # sqlite3 is imported globally from university_system.infrastructure.database.db
        conn = get_connection()
        cursor = conn.cursor()
        
        # Add each permission
        for perm_name, perm_desc in plagiarism_permissions:
            try:
                # Check if permission already exists
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                if not cursor.fetchone():
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                        (perm_name, perm_desc, timestamp)
                    )
                    created_permissions.append(perm_name)
                    logging.info(f"Created permission: {perm_name}")
            except sqlite3.Error as e:
                logging.error(f"Error creating permission {perm_name}: {e}")
        
        # Get permission IDs for role assignments
        permission_ids = {}
        for perm_name in [p[0] for p in plagiarism_permissions]:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            result = cursor.fetchone()
            if result:
                permission_ids[perm_name] = result[0]
        
        # Grant permissions to roles
        role_permissions = {
            'admin': ['check_plagiarism', 'manage_plagiarism_system', 'submit_document', 
                     'check_plagiarism_any_course', 'access_plagiarism_menu'],
            'staff': ['check_plagiarism', 'submit_document', 'access_plagiarism_menu'],
            'instructor': ['check_plagiarism', 'submit_document', 'access_plagiarism_menu'],
            'student': ['submit_document', 'access_plagiarism_menu']
        }
        
        for role, perms in role_permissions.items():
            # Get role ID
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
            role_result = cursor.fetchone()
            if not role_result:
                logging.warning(f"Role '{role}' not found, skipping permission assignment")
                continue
                
            role_id = role_result[0]
            
            # Grant permissions
            for perm in perms:
                if perm in permission_ids:
                    perm_id = permission_ids[perm]
                    
                    # Check if permission is already granted
                    cursor.execute(
                        'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                        (role_id, perm_id)
                    )
                    
                    if cursor.fetchone()[0] == 0:
                        try:
                            cursor.execute(
                                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                (role_id, perm_id)
                            )
                            logging.info(f"Granted permission '{perm}' to role '{role}'")
                        except sqlite3.Error as e:
                            logging.error(f"Error granting {perm} to role {role}: {e}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logging.error(f"Unexpected error adding permissions: {e}")
        # Don't re-raise to avoid breaking initialization
        return []
    
    return created_permissions

class DatabaseConnectionManager:
    """Thread-safe database connection manager to prevent locking issues"""
    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = threading.RLock()
        self.connection_count = 0
        self.max_retries = 3
        self.retry_delay = 0.1
        
    @contextlib.contextmanager
    def get_connection(self):
        """Context manager for database connections with comprehensive error handling"""
        conn = None
        connection_acquired = False
        lock_acquired = False
        
        try:
            # Acquire lock with timeout protection
            lock_acquired = self._lock.acquire(timeout=30.0)
            if not lock_acquired:
                raise DatabaseError(
                    "Failed to acquire database lock within timeout period",
                    code="DB_LOCK_TIMEOUT"
                )
            
            # Track connection attempts for monitoring
            self.connection_count += 1
            connection_id = self.connection_count
            
            # Attempt to establish database connection with retry logic
            conn = self._establish_connection_with_retry(connection_id)
            connection_acquired = True
            
            # Configure connection for optimal performance and concurrency
            self._configure_connection(conn, connection_id)
            
            # Yield the connection to the calling code
            logging.debug(f"Database connection #{connection_id} established successfully")
            yield conn
            
        except sqlite3.OperationalError as e:
            self._handle_operational_error(e, connection_id if 'connection_id' in locals() else 'unknown')
            if conn:
                self._safe_rollback(conn, connection_id if 'connection_id' in locals() else 'unknown')
            raise e
            
        except sqlite3.DatabaseError as e:
            self._handle_database_error(e, connection_id if 'connection_id' in locals() else 'unknown')
            if conn:
                self._safe_rollback(conn, connection_id if 'connection_id' in locals() else 'unknown')
            raise e
            
        except sqlite3.Error as e:
            self._handle_sqlite_error(e, connection_id if 'connection_id' in locals() else 'unknown')
            if conn:
                self._safe_rollback(conn, connection_id if 'connection_id' in locals() else 'unknown')
            raise e
            
        except Exception as e:
            self._handle_unexpected_error(e, connection_id if 'connection_id' in locals() else 'unknown')
            if conn:
                self._safe_rollback(conn, connection_id if 'connection_id' in locals() else 'unknown')
            raise e
            
        finally:
            # Comprehensive cleanup with detailed error handling
            self._cleanup_connection(conn, connection_acquired, lock_acquired, 
                                   connection_id if 'connection_id' in locals() else 'unknown')
    
    def _establish_connection_with_retry(self, connection_id):
        """Establish database connection with retry logic"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                logging.debug(f"Connection #{connection_id} established on attempt {attempt + 1}")
                return conn
                
            except sqlite3.OperationalError as e:
                last_error = e
                if "database is locked" in str(e).lower() and attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(f"Database locked on attempt {attempt + 1}, retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
                    
            except sqlite3.Error as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logging.warning(f"Database error on attempt {attempt + 1}, retrying in {wait_time:.2f}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
        
        # If we get here, all retries failed
        raise last_error or DatabaseError(
            "Failed to establish database connection after all retries",
            code="DB_CONNECTION_FAILED"
        )
    
    def _configure_connection(self, conn, connection_id):
        """Configure database connection for optimal performance"""
        try:
            # Set timeout and concurrency settings
            conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout
            conn.execute("PRAGMA journal_mode = WAL")    # Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA synchronous = NORMAL")  # Balance safety and performance
            conn.execute("PRAGMA foreign_keys = ON")     # Enable foreign key constraints
            conn.execute("PRAGMA temp_store = MEMORY")   # Store temp tables in memory
            conn.execute("PRAGMA cache_size = 10000")    # Increase cache size
            
            logging.debug(f"Connection #{connection_id} configured successfully")
            
        except sqlite3.Error as e:
            logging.warning(f"Failed to configure connection #{connection_id}: {e}")
            # Don't raise here as the connection might still be usable
    
    def _safe_rollback(self, conn, connection_id):
        """Safely rollback transaction with proper error handling"""
        if not conn:
            return
            
        try:
            conn.rollback()
            logging.debug(f"Transaction rolled back successfully for connection #{connection_id}")
            
        except sqlite3.OperationalError as e:
            if "no transaction is active" in str(e).lower():
                logging.debug(f"No active transaction to rollback for connection #{connection_id}")
            else:
                logging.warning(f"Operational error during rollback for connection #{connection_id}: {e}")
                
        except sqlite3.Error as e:
            logging.error(f"Database error during rollback for connection #{connection_id}: {e}")
            
        except Exception as e:
            logging.error(f"Unexpected error during rollback for connection #{connection_id}: {type(e).__name__}: {e}")
    
    def _cleanup_connection(self, conn, connection_acquired, lock_acquired, connection_id):
        """Comprehensive connection cleanup with detailed error handling"""
        cleanup_errors = []
        
        # Close database connection if it was established
        if conn and connection_acquired:
            try:
                # Check if connection is still valid before closing
                conn.execute("SELECT 1")  # Simple query to test connection
                conn.close()
                logging.debug(f"Connection #{connection_id} closed successfully")
                
            except sqlite3.ProgrammingError as e:
                if "cannot operate on a closed database" in str(e).lower():
                    logging.debug(f"Connection #{connection_id} was already closed")
                else:
                    cleanup_errors.append(f"Programming error during close: {e}")
                    logging.warning(f"Programming error closing connection #{connection_id}: {e}")
                    
            except sqlite3.OperationalError as e:
                cleanup_errors.append(f"Operational error during close: {e}")
                logging.warning(f"Operational error closing connection #{connection_id}: {e}")
                
            except sqlite3.Error as e:
                cleanup_errors.append(f"Database error during close: {e}")
                logging.error(f"Database error closing connection #{connection_id}: {e}")
                
            except Exception as e:
                cleanup_errors.append(f"Unexpected error during close: {type(e).__name__}: {e}")
                logging.error(f"Unexpected error closing connection #{connection_id}: {type(e).__name__}: {e}")
        
        # Release the thread lock
        if lock_acquired:
            try:
                self._lock.release()
                logging.debug(f"Lock released successfully for connection #{connection_id}")
                
            except RuntimeError as e:
                cleanup_errors.append(f"Lock release error: {e}")
                logging.error(f"Error releasing lock for connection #{connection_id}: {e}")
                
            except Exception as e:
                cleanup_errors.append(f"Unexpected lock error: {type(e).__name__}: {e}")
                logging.error(f"Unexpected error releasing lock for connection #{connection_id}: {type(e).__name__}: {e}")
        
        # Log cleanup summary if there were any issues
        if cleanup_errors:
            logging.warning(f"Connection #{connection_id} cleanup completed with {len(cleanup_errors)} issues: {'; '.join(cleanup_errors)}")
        else:
            logging.debug(f"Connection #{connection_id} cleanup completed successfully")
    
    def _handle_operational_error(self, error, connection_id):
        """Handle SQLite operational errors with specific categorization"""
        error_msg = str(error).lower()
        
        if "database is locked" in error_msg:
            logging.warning(f"Database lock detected for connection #{connection_id}: {error}")
        elif "disk i/o error" in error_msg:
            logging.error(f"Disk I/O error for connection #{connection_id}: {error}")
        elif "database disk image is malformed" in error_msg:
            logging.critical(f"Database corruption detected for connection #{connection_id}: {error}")
        elif "no such table" in error_msg:
            logging.error(f"Table not found for connection #{connection_id}: {error}")
        elif "permission denied" in error_msg:
            logging.error(f"Permission denied for connection #{connection_id}: {error}")
        else:
            logging.error(f"Operational error for connection #{connection_id}: {error}")
    
    def _handle_database_error(self, error, connection_id):
        """Handle SQLite database errors"""
        logging.error(f"Database error for connection #{connection_id}: {error}")
    
    def _handle_sqlite_error(self, error, connection_id):
        """Handle general SQLite errors"""
        logging.error(f"SQLite error for connection #{connection_id}: {error}")
    
    def _handle_unexpected_error(self, error, connection_id):
        """Handle unexpected non-SQLite errors"""
        logging.error(f"Unexpected error for connection #{connection_id}: {type(error).__name__}: {error}")
    
    def get_connection_stats(self):
        """Get statistics about database connections for monitoring"""
        return {
            'total_connections': self.connection_count,
            'db_path': self.db_path,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'lock_acquired': self._lock._count > 0 if hasattr(self._lock, '_count') else 'unknown'
        }
    
    def test_connection(self):
        """Test database connectivity and return status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return {
                    'status': 'success',
                    'message': 'Database connection test successful',
                    'result': result[0] if result else None
                }
                
        except sqlite3.Error as e:
            return {
                'status': 'error',
                'message': f'Database connection test failed: {e}',
                'error_type': type(e).__name__
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Unexpected error during connection test: {e}',
                'error_type': type(e).__name__
            }

class UserAuth:
    def __init__(self, db_path=None, config_path=None):
        """Initialize UserAuth with proper attribute initialization"""
        try:
            # CRITICAL: Initialize these attributes FIRST
            self.current_user = None
            self.last_activity = None
            self.session_timeout = 30  # minutes
            self.login_attempts = {}
            self.max_attempts = 5
            self.lockout_time = 15  # minutes
            
            # Core initialization
            def _normalise_path(value, default_path: Path) -> str:
                """Resolve *value* to an absolute path rooted in the project.

                Relative paths are interpreted relative to the default path's
                parent so existing call sites that passed filenames continue to
                work while ensuring artefacts land under ``program/data``.
                """
                if value is None:
                    return os.fspath(default_path)

                candidate = Path(value)
                if candidate.is_absolute():
                    return os.fspath(candidate)

                return os.fspath(default_path.parent / candidate)

            self.db_path = _normalise_path(db_path, paths.DEFAULT_DB_PATH)
            self.config_path = _normalise_path(config_path, paths.CHATBOT_CONFIG_PATH)
            self.log_dir = os.fspath(paths.LOG_DIR)
            self.upload_dir = os.fspath(paths.CHATBOT_UPLOAD_DIR)
            self.models_dir = os.fspath(paths.CHATBOT_MODELS_DIR)

            # Authentication system integration
            self.auth_system = None
            self.authenticated_sessions = {}
            self.conversation_contexts = {}
            
            # Initialize database manager
            self.db_manager = DatabaseConnectionManager(self.db_path)
            
            # Load configuration FIRST
            self.config = self.load_config()
            
            # Initialize directories
            self.ensure_directories()

            # Initialize voice interface with error handling
            try:
                if CHATBOT_AVAILABLE:
                    # Try to import the real VoiceInterface
                    from university_system.utils.ai.university_chatbot import VoiceInterface
                    self.voice_interface = VoiceInterface()
                    if hasattr(self.voice_interface, 'initialize'):
                        self.voice_interface.initialize()
                else:
                    self.voice_interface = MinimalVoiceInterface()
            except (ImportError, NameError, AttributeError):
                # Fallback to minimal implementation
                self.voice_interface = MinimalVoiceInterface()
                print("Using minimal voice interface - voice features disabled")
            
            # Additional chatbot attributes
            self.nlp = None
            self.intent_classifier = None
            self.sentiment_analyzer = None
            self.qa_pipeline = None
            self.vectorizer = None
            self.intents = {}
            self.faq_database = {}
            
            # Conversation tracking
            self.conversation_history = {}
            
            # Initialize the database
            self._init_db()
            
            # Set global auth instance
            set_auth_instance(self)
            
            print("UserAuth initialized successfully!")
            
        except Exception as e:
            logger.critical(f"Critical error in UserAuth initialization: {e}")
            # Set minimal safe defaults
            self.current_user = None
            self.last_activity = None
            self.session_timeout = 30
            self.login_attempts = {}
            self.max_attempts = 5
            self.lockout_time = 15
            self.config = {}
            self.conversation_history = {}
            self.auth_system = None
            self.db_path = db_path
            # Still try to initialize database
            try:
                self.db_manager = DatabaseConnectionManager(db_path)
                self._init_db()
            except Exception as db_error:
                logger.error(f"Database initialization also failed: {db_error}")

    def _create_default_student_if_needed(self, cursor, conn):
        """Ensure the students table exists and report if it is empty."""
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
            table_exists = cursor.fetchone() is not None
            if not table_exists:
                logging.warning(
                    "Students table is missing; student-related authentication features may be unavailable."
                )
                return

            cursor.execute('SELECT COUNT(*) FROM students')
            student_count = cursor.fetchone()[0]
            if student_count == 0:
                logging.info(
                    "Students table is present but empty. Import student records to enable student-facing workflows."
                )
        except sqlite3.Error as exc:
            logging.warning(f"Could not inspect students table: {exc}")

    def _create_default_accounts_if_needed(self, cursor, conn, target_usernames: Optional[set[str]] = None):
        """Ensure baseline system accounts exist, creating them when missing."""
        import os
        import secrets
        import string

        def generate_secure_password(length=16):
            """Generate a cryptographically secure random password."""
            alphabet = string.ascii_letters + string.digits + string.punctuation
            return ''.join(secrets.choice(alphabet) for _ in range(length))

        # Get passwords from environment variables or use simple defaults for development
        # SECURITY: In production, ALWAYS set INITIAL_*_PASSWORD environment variables
        admin_password = os.getenv('INITIAL_ADMIN_PASSWORD')
        if not admin_password:
            # Use simple password for development/testing
            admin_password = 'admin123'
            logging.warning(
                "SECURITY WARNING: No INITIAL_ADMIN_PASSWORD environment variable set. "
                f"Using default password 'admin123' for development. "
                f"NEVER use this in production!"
            )
            print("⚠️  Admin account created with password: admin123")

        staff_password = os.getenv('INITIAL_STAFF_PASSWORD')
        if not staff_password:
            # Use simple password for development/testing
            staff_password = 'staff123'
            logging.info("Using default password 'staff123' for staff account (development only)")
            print("⚠️  Staff account created with password: staff123")

        student_password = os.getenv('INITIAL_STUDENT_PASSWORD')
        if not student_password:
            # Use simple password for development/testing
            student_password = 'student123'
            logging.info("Using default password 'student123' for student account (development only)")
            print("⚠️  Student account created with password: student123")

        default_accounts = [
            {
                'username': 'admin',
                'password': admin_password,
                'role': 'admin',
                'email': 'admin@example.com',
                'first_name': 'System',
                'last_name': 'Administrator',
                'student_id': None,
            },
            {
                'username': 'staff',
                'password': staff_password,
                'role': 'staff',
                'email': 'staff@example.com',
                'first_name': 'Staff',
                'last_name': 'User',
                'student_id': None,
            },
            {
                'username': 'student',
                'password': student_password,
                'role': 'student',
                'email': 'student@example.com',
                'first_name': 'Student',
                'last_name': 'User',
                'student_id': None,
            },
        ]

        created_accounts: list[str] = []

        for account in default_accounts:
            if target_usernames and account['username'] not in target_usernames:
                logging.debug(f"Skipping {account['username']} - not in target list")
                continue

            cursor.execute('SELECT id FROM user_accounts WHERE username = ?', (account['username'],))
            existing_account = cursor.fetchone()
            if existing_account:
                logging.debug(f"Account {account['username']} already exists, skipping")
                continue

            logging.info(f"Creating default account: {account['username']}")

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if user already exists by username ONLY (not email)
            # This prevents accidentally reusing a different user's ID if emails happen to match
            cursor.execute(
                'SELECT id, role FROM users WHERE username = ?',
                (account['username'],),
            )
            user_row = cursor.fetchone()

            if user_row:
                # User exists - verify it has the correct role
                user_id, existing_role = user_row
                if existing_role != account['role']:
                    logging.warning(
                        f"User '{account['username']}' exists with role '{existing_role}' "
                        f"but expected '{account['role']}'. Updating role."
                    )
                    try:
                        cursor.execute(
                            'UPDATE users SET role = ?, updated_at = ? WHERE id = ?',
                            (account['role'], timestamp, user_id)
                        )
                    except sqlite3.Error as exc:
                        logging.error(f"Failed to update role for user '{account['username']}': {exc}")
            else:
                try:
                    cursor.execute(
                        '''
                        INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            account['username'],
                            account['first_name'],
                            account['last_name'],
                            account['email'],
                            account['role'],
                            account['student_id'],
                            timestamp,
                            timestamp,
                        ),
                    )
                    user_id = cursor.lastrowid
                    logging.info("Created default user profile for '%s'.", account['username'])
                except sqlite3.Error as exc:
                    logging.error(
                        "Failed to create user profile for default account '%s': %s",
                        account['username'],
                        exc,
                    )
                    conn.rollback()
                    continue

            salt, password_hash = self._hash_password(account['password'])

            try:
                cursor.execute(
                    '''
                    INSERT INTO user_accounts (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                    ''',
                    (
                        account['username'],
                        password_hash,
                        salt,
                        user_id,
                        timestamp,
                        timestamp,
                    ),
                )
                conn.commit()
                created_accounts.append(account['username'])
                logging.info(
                    "Created default %s account '%s'.",
                    account['role'],
                    account['username'],
                )
            except sqlite3.Error as exc:
                conn.rollback()
                logging.error(
                    "Failed to create default account '%s': %s",
                    account['username'],
                    exc,
                )

        if created_accounts:
            print(f"✅ Created default accounts: {', '.join(created_accounts)}")
        else:
            logging.info("Default accounts already present; no action taken.")

    def _ensure_students_table(self, cursor):
        """Guarantee the student catalogue exists for auth relationships"""
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                email_address TEXT,
                title TEXT,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                gender TEXT,
                dob TEXT,
                age INTEGER,
                course TEXT,
                registration_datetime TEXT,
                status TEXT DEFAULT 'Active',
                enrollment_date TEXT
            )
            ''')

            cursor.execute("PRAGMA table_info(students)")
            existing_columns = {column[1] for column in cursor.fetchall()}

            required_columns = {
                'email_address': 'TEXT',
                'title': 'TEXT',
                'first_name': 'TEXT',
                'middle_name': 'TEXT',
                'last_name': 'TEXT',
                'gender': 'TEXT',
                'dob': 'TEXT',
                'age': 'INTEGER',
                'course': 'TEXT',
                'registration_datetime': 'TEXT',
                'status': 'TEXT DEFAULT "Active"',
                'enrollment_date': 'TEXT'
            }

            for column, definition in required_columns.items():
                if column not in existing_columns:
                    try:
                        cursor.execute(f'ALTER TABLE students ADD COLUMN {column} {definition}')
                        logging.info(f"Added missing column '{column}' to students table")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            continue
                        logging.warning(f"Could not add column '{column}' to students table: {e}")
                    except sqlite3.Error as e:
                        logging.warning(f"SQLite error while adding column '{column}': {e}")

        except sqlite3.Error as e:
            logging.error(f"Failed to ensure students table exists: {e}")
            raise

    def _hash_password(self, password, salt=None):
        """
        Hash a password with a salt using PBKDF2.

        Uses 1,000,000 iterations as recommended by OWASP for PBKDF2-SHA256.
        This provides strong protection against brute-force attacks.
        """
        if salt is None:
            salt = secrets.token_hex(16)

        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            1_000_000,  # Increased from 100,000 to 1 million iterations (OWASP recommendation)
            dklen=64
        )

        return salt, key.hex()
    
    def _init_db(self):
        """Initialize database tables needed for authentication"""
        # Use class-level flag to prevent multiple initializations
        if hasattr(UserAuth, '_db_initialized'):
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Ensure the student catalogue exists before creating dependent tables
        self._ensure_students_table(cursor)

        # Create users table for storing user profile information
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            student_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create user_accounts table - for storing authentication data
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            last_login TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            password_reset_required INTEGER DEFAULT 0,
            two_fa_enabled INTEGER DEFAULT 0,
            two_fa_secret TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        ''')

        # Create other tables...
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS two_fa_recovery_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code_hash TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            used_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permission_name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles (id),
            FOREIGN KEY (permission_id) REFERENCES permissions (id),
            UNIQUE(role_id, permission_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            granted INTEGER NOT NULL,
            UNIQUE(user_id, permission_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            attempt_time TEXT NOT NULL,
            ip_address TEXT,
            success INTEGER NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TEXT NOT NULL,
            ip_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        conn.commit()

        # Check if default roles exist, if not create them
        cursor.execute('SELECT COUNT(*) FROM roles')
        role_count = cursor.fetchone()[0]

        if role_count == 0:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Insert default roles
            for role_name, description in ROLES.items():
                cursor.execute(
                    'INSERT INTO roles (role_name, description, created_at, updated_at) VALUES (?, ?, ?, ?)',
                    (role_name, description, timestamp, timestamp)
                )

            conn.commit()

        # Check if permissions exist, if not create them
        cursor.execute('SELECT COUNT(*) FROM permissions')
        permission_count = cursor.fetchone()[0]

        if permission_count == 0:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Gather all unique permissions
            all_permissions = set()
            for perms in PERMISSIONS.values():
                all_permissions.update(perms)

            # Insert permissions
            for perm in all_permissions:
                description = ' '.join(word.capitalize() for word in perm.split('_'))
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm, description, timestamp)
                )

            conn.commit()

            # Now associate permissions with roles
            for role, perms in PERMISSIONS.items():
                cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
                role_result = cursor.fetchone()
                if role_result:
                    role_id = role_result[0]

                    for perm in perms:
                        cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                        perm_result = cursor.fetchone()
                        if perm_result:
                            perm_id = perm_result[0]

                            cursor.execute(
                                'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                                (role_id, perm_id)
                            )
                            if cursor.fetchone()[0] == 0:
                                cursor.execute(
                                    'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                    (role_id, perm_id)
                                )

            conn.commit()
        else:
            # If permissions already exist, ensure all permissions in PERMISSIONS are created
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            all_permissions = set()
            for perms in PERMISSIONS.values():
                all_permissions.update(perms)

            for perm in all_permissions:
                cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm,))
                if cursor.fetchone()[0] == 0:
                    description = ' '.join(word.capitalize() for word in perm.split('_'))
                    cursor.execute(
                        'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                        (perm, description, timestamp)
                    )

            conn.commit()

            # Then ensure all role-permission associations exist
            for role, perms in PERMISSIONS.items():
                cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
                role_result = cursor.fetchone()
                if role_result:
                    role_id = role_result[0]

                    for perm in perms:
                        cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                        perm_result = cursor.fetchone()
                        if perm_result:
                            perm_id = perm_result[0]

                            cursor.execute(
                                'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                                (role_id, perm_id)
                            )
                            if cursor.fetchone()[0] == 0:
                                cursor.execute(
                                    'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                    (role_id, perm_id)
                                )

            conn.commit()

        # Create default student record if needed (improved logic)
        self._create_default_student_if_needed(cursor, conn)
        
        # Create default accounts ONLY if they don't exist (improved logic)
        self._create_default_accounts_if_needed(cursor, conn)
        
        # Close the connection
        conn.close()
        
        # Mark as initialized
        UserAuth._db_initialized = True

    def ensure_directories(self):
        """Create necessary directories"""
        import os
        for directory in [self.log_dir, self.upload_dir, self.models_dir]:
            os.makedirs(directory, exist_ok=True)

    def load_config(self):
        """Load chatbot configuration"""
        default_config = {
            "max_message_length": 500,
            "session_timeout": 1800,
            "enable_logging": True,
            "response_delay": 0.5
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                return {**default_config, **config}
            except Exception as e:
                logging.error(f"Error loading config: {e}")
        
        return default_config
        
        PERMISSIONS = {}

    def initialize_chatbot_integration(self):
        """Initialize chatbot integration with comprehensive error handling"""
        if CHATBOT_AVAILABLE:
            try:
                print("Initializing chatbot integration...")
                self.chatbot = UniversityChatbot(db_path=self.db_path)
                
                # Verify the chatbot has required attributes
                required_attrs = ['app', 'config', 'conversation_history', 'auth_system']
                missing_attrs = [attr for attr in required_attrs if not hasattr(self.chatbot, attr)]
                
                if missing_attrs:
                    print(f"⚠️ Chatbot missing attributes: {missing_attrs}")
                    # Add missing attributes
                    for attr in missing_attrs:
                        setattr(self.chatbot, attr, None)
                
                self.chatbot.set_auth_system(self)
                logger.info("Chatbot integration initialized successfully")
                return True
                
            except Exception as e:
                print(f"⚠️ Chatbot integration failed: {e}")
                logger.debug(f"Error type: {type(e).__name__}")
                
                # Create emergency fallback
                self._create_emergency_chatbot()
                return False
        else:
            print("Chatbot module not available")
            self.chatbot = None
            return False

    def _create_fallback_chatbot(self):
        """Create a minimal fallback chatbot"""
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
        
        self.chatbot = FallbackChatbot()
        logger.info("Fallback chatbot created")
    
    def setup_chatbot_permissions(self):
        """Setup chatbot-specific permissions in the database"""
        try:
            with self.db_manager.get_connection() as conn:
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
                
        except Exception as e:
            logger.error(f"Error setting up chatbot permissions: {e}")
            return False
    
    def create_chatbot_session(self, username: str) -> Optional[str]:
        """Create a chatbot session for authenticated user"""
        if not self.current_user or self.current_user['username'] != username:
            return None
        
        if not self.check_permission('access_chatbot'):
            return None
        
        # Generate session token
        session_token = secrets.token_hex(32)
        
        # Log chatbot session creation
        self._log_activity(username, 'Chatbot session created', f'Token: {session_token[:8]}...', self.current_user['id'])
        
        return session_token

    def get_chatbot_conversation_history(self, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chatbot conversation history for a user - IMPROVED VERSION"""
        if not self.current_user:
            return []
        
        # Check permissions
        can_view = False
        if self.current_user['username'] == username:
            can_view = True
        elif 'view_all_conversations' in self.current_user['permissions']:
            can_view = True
        elif 'view_student_conversations' in self.current_user['permissions']:
            can_view = True
        
        if not can_view:
            return []
        
        conversations = []
        
        # First, try to get from activity_log (most reliable)
        try:
            with self.db_manager.get_connection() as conn:
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
                    
        except Exception as e:
            logger.error(f"Database history error: {e}")
        
        # Also get from chatbot's in-memory history if available
        try:
            if hasattr(self, 'chatbot') and self.chatbot and hasattr(self.chatbot, 'conversation_history'):
                user_history = self.chatbot.conversation_history.get(username, [])
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
            pass  # If sorting fails, return as-is

        return conversations[:limit]

    def generate_chatbot_analytics(self) -> Dict[str, Any]:
        """Generate chatbot usage analytics"""
        if not self.current_user or 'chatbot_admin' not in self.current_user['permissions']:
            return {}
        
        try:
            with self.db_manager.get_connection() as conn:
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
                
        except Exception as e:
            logger.error(f"Error generating chatbot analytics: {e}")
            return {'error': str(e)}

    def launch_chatbot_interface(self):
        """Launch the chatbot interface for the current user"""
        if not self.current_user:
            print("You must be logged in to access the chatbot.")
            return
        
        if not self.check_permission('access_chatbot'):
            print("You don't have permission to access the chatbot.")
            return
        
        if not self.chatbot:
            if not self.initialize_chatbot_integration():
                print("Chatbot is not available at this time.")
                return
        
        # Ensure chatbot has current auth context
        self.chatbot.set_auth_system(self)
        
        # Launch the interface
        self.chatbot.run_authenticated_console_interface()
    
    def log_activity_with_connection(self, conn, username, action, details=None, user_id=None):
        """Log activity using an existing database connection with comprehensive error handling"""
        
        # Input validation and sanitization
        if not conn:
            logging.error("Cannot log activity: database connection is None")
            return {'success': False, 'error': 'no_connection', 'fallback': None}
        
        if not username or not action:
            logging.warning("Activity logging skipped: username and action are required")
            return {'success': False, 'error': 'invalid_input', 'fallback': None}
        
        # Sanitize inputs to prevent issues
        try:
            username = str(username)[:255] if username else 'unknown'
            action = str(action)[:500] if action else 'unknown_action'
            details = str(details)[:1000] if details else None
            user_id = int(user_id) if user_id is not None else None
        except (ValueError, TypeError) as sanitize_error:
            logging.warning(f"Input sanitization warning: {sanitize_error}")
            username = 'sanitization_failed'
            action = 'sanitization_failed'
            details = f"Original error: {sanitize_error}"
            user_id = None
        
        # Prepare log entry
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ip_address = self._get_client_ip() if hasattr(self, '_get_client_ip') else "127.0.0.1"
        
        log_entry = {
            'user_id': user_id,
            'username': username,
            'action': action,
            'details': details,
            'timestamp': timestamp,
            'ip_address': ip_address
        }
        
        # Attempt database logging with the shared connection
        try:
            return self._attempt_shared_connection_logging(conn, log_entry)
            
        except sqlite3.IntegrityError as e:
            return self._handle_shared_connection_integrity_error(e, log_entry)
            
        except sqlite3.OperationalError as e:
            return self._handle_shared_connection_operational_error(e, log_entry)
            
        except sqlite3.DatabaseError as e:
            return self._handle_shared_connection_database_error(e, log_entry)
            
        except sqlite3.Error as e:
            return self._handle_shared_connection_sqlite_error(e, log_entry)
            
        except AttributeError as e:
            return self._handle_shared_connection_attribute_error(e, log_entry)
            
        except ValueError as e:
            return self._handle_shared_connection_value_error(e, log_entry)
            
        except MemoryError as e:
            return self._handle_shared_connection_memory_error(e, log_entry)
            
        except Exception as e:
            return self._handle_shared_connection_unexpected_error(e, log_entry)

    def _attempt_shared_connection_logging(self, conn, log_entry):
        """Attempt to log using the shared database connection"""
        try:
            # Verify connection is still valid
            if not self._validate_shared_connection(conn):
                return {'success': False, 'error': 'invalid_connection', 'fallback': 'file_logged'}
            
            cursor = conn.cursor()
            
            # Verify activity_log table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'")
            if not cursor.fetchone():
                logging.error("Activity log table does not exist in shared connection")
                return self._fallback_shared_connection_logging(log_entry, "table_missing")
            
            # Check table schema compatibility
            cursor.execute("PRAGMA table_info(activity_log)")
            columns = [column[1] for column in cursor.fetchall()]
            required_columns = ['user_id', 'username', 'action', 'details', 'timestamp', 'ip_address']
            
            missing_columns = [col for col in required_columns if col not in columns]
            if missing_columns:
                logging.error(f"Activity log table missing required columns: {missing_columns}")
                return self._fallback_shared_connection_logging(log_entry, f"missing_columns: {missing_columns}")
            
            # Perform the insert (don't commit - let caller handle transaction)
            cursor.execute('''
                INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                log_entry['user_id'],
                log_entry['username'],
                log_entry['action'],
                log_entry['details'],
                log_entry['timestamp'],
                log_entry['ip_address']
            ))
            
            logging.debug(f"Activity logged via shared connection for user: {log_entry['username']}")
            return {'success': True, 'error': None, 'fallback': None, 'method': 'shared_connection'}
            
        except sqlite3.Error as db_error:
            # Re-raise for specific handling by calling methods
            raise db_error
        except Exception as unexpected_error:
            # Re-raise for specific handling by calling methods
            raise unexpected_error

    def _validate_shared_connection(self, conn):
        """Validate that the shared connection is still usable"""
        try:
            # Test with a simple query
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True
            
        except sqlite3.ProgrammingError as e:
            if "cannot operate on a closed database" in str(e).lower():
                logging.warning("Shared database connection is closed")
                return False
            else:
                logging.error(f"Programming error with shared connection: {e}")
                return False
                
        except sqlite3.Error as e:
            logging.warning(f"Shared database connection validation failed: {e}")
            return False
            
        except Exception as e:
            logging.error(f"Unexpected error validating shared connection: {type(e).__name__}: {e}")
            return False

    def _handle_shared_connection_integrity_error(self, error, log_entry):
        """Handle integrity constraint violations in shared connection"""
        error_msg = str(error).lower()
        
        if "foreign key constraint failed" in error_msg:
            logging.warning(f"Foreign key constraint in shared logging for user_id {log_entry['user_id']}: {error}")
            # Try again without user_id to avoid constraint issues
            try:
                log_entry_copy = log_entry.copy()
                log_entry_copy['user_id'] = None
                return self._attempt_shared_connection_logging(None, log_entry_copy)  # Will create new cursor
            except Exception:
                return self._fallback_shared_connection_logging(log_entry, f"foreign_key_retry_failed: {error}")
        
        elif "unique constraint failed" in error_msg:
            logging.debug(f"Duplicate activity log entry for {log_entry['username']} in shared connection")
            # This might be acceptable - treat as success
            return {'success': True, 'error': 'duplicate_entry', 'fallback': None, 'method': 'shared_connection'}
        
        elif "not null constraint failed" in error_msg:
            logging.warning(f"Null constraint violation in shared logging: {error}")
            # Fill required fields with defaults
            log_entry_safe = self._make_log_entry_safe(log_entry)
            try:
                return self._attempt_shared_connection_logging(None, log_entry_safe)
            except Exception:
                return self._fallback_shared_connection_logging(log_entry, f"null_constraint_retry_failed: {error}")
        
        else:
            logging.error(f"Integrity constraint violation in shared logging: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"integrity_error: {error}")

    def _handle_shared_connection_operational_error(self, error, log_entry):
        """Handle operational errors in shared connection logging"""
        error_msg = str(error).lower()
        
        if "database is locked" in error_msg:
            logging.warning(f"Database locked during shared connection logging for {log_entry['username']}: {error}")
            # Don't retry with shared connection - just fallback
            return self._fallback_shared_connection_logging(log_entry, f"shared_db_locked: {error}")
        
        elif "disk i/o error" in error_msg:
            logging.error(f"Disk I/O error in shared connection logging: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"disk_io_error: {error}")
        
        elif "permission denied" in error_msg:
            logging.error(f"Permission denied in shared connection logging: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"permission_denied: {error}")
        
        elif "no such table" in error_msg:
            logging.error(f"Activity log table missing in shared connection: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"table_missing: {error}")
        
        elif "database disk image is malformed" in error_msg:
            logging.critical(f"Database corruption detected in shared connection: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"db_corruption: {error}")
        
        else:
            logging.error(f"Operational error in shared connection logging: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"operational_error: {error}")

    def _handle_shared_connection_database_error(self, error, log_entry):
        """Handle general database errors in shared connection"""
        logging.error(f"Database error in shared connection logging: {error}")
        return self._fallback_shared_connection_logging(log_entry, f"database_error: {error}")

    def _handle_shared_connection_sqlite_error(self, error, log_entry):
        """Handle general SQLite errors in shared connection"""
        logging.error(f"SQLite error in shared connection logging: {error}")
        return self._fallback_shared_connection_logging(log_entry, f"sqlite_error: {error}")

    def _handle_shared_connection_attribute_error(self, error, log_entry):
        """Handle attribute errors (like connection object issues)"""
        error_msg = str(error).lower()
        
        if "cursor" in error_msg:
            logging.error(f"Cursor attribute error in shared connection: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"cursor_error: {error}")
        
        elif "connection" in error_msg:
            logging.error(f"Connection attribute error in shared connection: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"connection_error: {error}")
        
        else:
            logging.error(f"Attribute error in shared connection logging: {error}")
            return self._fallback_shared_connection_logging(log_entry, f"attribute_error: {error}")

    def _handle_shared_connection_value_error(self, error, log_entry):
        """Handle value errors (like data type issues)"""
        logging.warning(f"Value error in shared connection logging: {error}")
        
        # Try to fix data types and retry
        try:
            safe_entry = self._make_log_entry_safe(log_entry)
            return self._attempt_shared_connection_logging(None, safe_entry)
        except Exception:
            return self._fallback_shared_connection_logging(log_entry, f"value_error_retry_failed: {error}")

    def _handle_shared_connection_memory_error(self, error, log_entry):
        """Handle memory errors in shared connection logging"""
        logging.critical(f"Memory error in shared connection logging: {error}")
        
        # Create minimal log entry to reduce memory usage
        minimal_entry = {
            'user_id': None,  # Remove to save memory
            'username': log_entry['username'][:50] if log_entry['username'] else 'unknown',
            'action': log_entry['action'][:50] if log_entry['action'] else 'unknown',
            'details': None,  # Remove details to save memory
            'timestamp': log_entry['timestamp'],
            'ip_address': '127.0.0.1'  # Use default to save memory
        }
        
        return self._fallback_shared_connection_logging(minimal_entry, f"memory_error: {error}")

    def create_chatbot_session(self, username: str) -> Optional[str]:
        """Create a chatbot session for authenticated user"""
        if not self.current_user or self.current_user['username'] != username:
            return None
        
        if not self.check_permission('access_chatbot'):
            return None
        
        # Generate session token
        session_token = secrets.token_hex(32)
        
        # Log chatbot session creation
        self._log_activity(username, 'Chatbot session created', f'Token: {session_token[:8]}...', self.current_user['id'])
        
        return session_token

    def validate_chatbot_session(self, session_token: str, username: str) -> bool:
        """Validate chatbot session token"""
        if not self.current_user or self.current_user['username'] != username:
            return False
        
        if not self.check_permission('access_chatbot'):
            return False
        
        # Simple validation - in production, store and validate actual tokens
        return True

    def _handle_shared_connection_unexpected_error(self, error, log_entry):
        """Handle unexpected errors in shared connection logging"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        logging.error(f"Unexpected error in shared connection logging: {error_type}: {error_msg}")
        
        # Try to determine if this error might interfere with the shared connection
        risky_errors = ['ConnectionError', 'TimeoutError', 'BrokenPipeError', 'OSError']
        
        if error_type in risky_errors:
            logging.warning(f"Potentially risky error detected in shared connection: {error_type}")
        
        return self._fallback_shared_connection_logging(log_entry, f"unexpected_error: {error_type}: {error_msg}")

    def _make_log_entry_safe(self, log_entry):
        """Create a safe version of log entry with proper data types"""
        safe_entry = {}
        
        # Ensure user_id is proper type or None
        try:
            safe_entry['user_id'] = int(log_entry['user_id']) if log_entry.get('user_id') is not None else None
        except (ValueError, TypeError):
            safe_entry['user_id'] = None
        
        # Ensure text fields are strings and not too long
        safe_entry['username'] = str(log_entry.get('username', 'unknown'))[:255]
        safe_entry['action'] = str(log_entry.get('action', 'unknown'))[:500]
        safe_entry['details'] = str(log_entry.get('details', ''))[:1000] if log_entry.get('details') else None
        safe_entry['timestamp'] = str(log_entry.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        safe_entry['ip_address'] = str(log_entry.get('ip_address', '127.0.0.1'))[:45]  # Max IPv6 length
        
        return safe_entry

    def _fallback_shared_connection_logging(self, log_entry, reason):
        """Fallback logging when shared connection fails - must not interfere with main transaction"""
        
        # Since we can't use the shared connection, we need alternative approaches
        # that won't interfere with the main database transaction
        
        fallback_methods = [
            ('file_logging', self._attempt_fallback_file_logging),
            ('memory_buffer', self._attempt_fallback_memory_logging),
            ('system_logging', self._attempt_fallback_system_logging)
        ]
        
        for method_name, method_func in fallback_methods:
            try:
                if method_func(log_entry, reason):
                    return {
                        'success': False, 
                        'error': 'shared_connection_failed', 
                        'fallback': method_name,
                        'reason': reason
                    }
            except Exception as fallback_error:
                logging.debug(f"Fallback method {method_name} failed: {fallback_error}")
                continue
        
        # If all fallbacks fail
        logging.error(f"All fallback methods failed for shared connection logging: {reason}")
        return {
            'success': False, 
            'error': 'all_fallbacks_failed', 
            'fallback': None,
            'reason': reason
        }

    def _attempt_fallback_file_logging(self, log_entry, reason):
        """Attempt to log to file as fallback"""
        try:
            fallback_file = 'shared_connection_fallback.log'
            log_line = f"{log_entry['timestamp']} - {log_entry['username']}: {log_entry['action']} - {log_entry.get('details', 'None')} - Reason: {reason}"
            
            with open(fallback_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
                f.flush()
            
            logging.info(f"Shared connection fallback logged to file for {log_entry['username']}")
            return True
            
        except Exception as file_error:
            logging.debug(f"File fallback logging failed: {file_error}")
            return False

    def _attempt_fallback_memory_logging(self, log_entry, reason):
        """Attempt to log to memory buffer as fallback"""
        try:
            if not hasattr(self, '_shared_connection_fallback_buffer'):
                self._shared_connection_fallback_buffer = []
            
            # Limit buffer size
            if len(self._shared_connection_fallback_buffer) >= 500:
                self._shared_connection_fallback_buffer.pop(0)
            
            buffer_entry = {
                'timestamp': log_entry['timestamp'],
                'username': log_entry['username'],
                'action': log_entry['action'],
                'reason': reason
            }
            
            self._shared_connection_fallback_buffer.append(buffer_entry)
            logging.info(f"Shared connection fallback logged to memory for {log_entry['username']}")
            return True
            
        except Exception as memory_error:
            logging.debug(f"Memory fallback logging failed: {memory_error}")
            return False

    def _attempt_fallback_system_logging(self, log_entry, reason):
        """Log to Python's logging system as last resort"""
        try:
            log_message = f"ACTIVITY_LOG - User: {log_entry['username']}, Action: {log_entry['action']}, Time: {log_entry['timestamp']}, Reason: {reason}"
            logging.warning(log_message)
            return True
            
        except Exception as system_error:
            logging.debug(f"System logging fallback failed: {system_error}")
            return False

    def get_shared_connection_fallback_buffer(self):
        """Retrieve the shared connection fallback buffer for manual processing"""
        return getattr(self, '_shared_connection_fallback_buffer', [])

    def clear_shared_connection_fallback_buffer(self):
        """Clear the shared connection fallback buffer after processing"""
        if hasattr(self, '_shared_connection_fallback_buffer'):
            self._shared_connection_fallback_buffer.clear()
            logging.info("Shared connection fallback buffer cleared")

    def _create_default_student_if_needed(self, cursor, conn):
        """Ensure the students table exists and report if it is empty."""
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
        table_exists = cursor.fetchone() is not None
        if not table_exists:
            logging.warning(
                "Students table is missing; student-related authentication features may be unavailable."
            )
            return

        cursor.execute('SELECT COUNT(*) FROM students')
        student_count = cursor.fetchone()[0]
        if student_count == 0:
            logging.info(
                "Students table is present but empty. Import student records to enable student-facing workflows."
            )

    def _check_role_coverage(self, cursor, conn):
        """Inspect core system accounts and report any missing roles."""
        cursor.execute(
            '''
            SELECT u.role, COUNT(ua.id)
            FROM user_accounts ua
            JOIN users u ON ua.user_id = u.id
            GROUP BY u.role
            '''
        )
        role_counts = {row[0]: row[1] for row in cursor.fetchall()}

        required_roles = {'admin', 'staff', 'student'}
        missing_roles = [role for role in required_roles if role_counts.get(role, 0) == 0]

        if missing_roles:
            logging.warning(
                "No active accounts found for roles: %s. Provision them via the administration tools.",
                ', '.join(sorted(missing_roles)),
            )
        else:
            logging.info("Core role coverage detected: %s", role_counts)

    def ensure_staff_account_exists(self):
        """Report whether staff accounts exist."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT ua.id
                    FROM user_accounts ua
                    WHERE ua.username = ?
                    ''',
                    ('staff',),
                )
                if cursor.fetchone():
                    print("✓ Staff account already exists")
                    return True

                self._create_default_accounts_if_needed(cursor, conn, target_usernames={'staff'})

                cursor.execute(
                    '''
                    SELECT ua.id
                    FROM user_accounts ua
                    WHERE ua.username = ?
                    ''',
                    ('staff',),
                )
                if cursor.fetchone():
                    print("✓ Staff account created successfully (username: staff)")
                    return True

                logging.warning("Staff account could not be created automatically.")
                return False
        except Exception as exc:
            logging.error(f"Error verifying staff account presence: {exc}")
            return False

    def verify_default_accounts(self):
        """Summarise presence of core role accounts."""
        print("\n=== ACCOUNT ROLE SUMMARY ===")
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT u.role, COUNT(ua.id) AS account_count
                FROM user_accounts ua
                JOIN users u ON ua.user_id = u.id
                GROUP BY u.role
                '''
            )
            role_counts = {role: count for role, count in cursor.fetchall()}

            required_roles = ['admin', 'staff', 'student']
            missing_roles = []

            for role in required_roles:
                count = role_counts.get(role, 0)
                if count == 0:
                    print(f"✗ No active accounts found for role '{role}'.")
                    missing_roles.append(role)
                else:
                    print(f"✓ {count} account(s) found for role '{role}'.")

            other_roles = {role: count for role, count in role_counts.items() if role not in required_roles}
            if other_roles:
                print("\nAdditional roles detected:")
                for role, count in sorted(other_roles.items()):
                    print(f"• {role}: {count} account(s)")

            if missing_roles:
                print("\n⚠️  Provision accounts for missing roles using the administration interface.")
                return False

            print("\n✅ Core roles are represented.")
            return True
        except sqlite3.Error as exc:
            print(f"❌ Unable to summarise account roles: {exc}")
            return False
        finally:
            conn.close()

    def setup_default_accounts():
        """Standalone helper to ensure baseline accounts exist."""
        print("=== ACCOUNT SETUP ===")
        try:
            auth = UserAuth()
            with auth.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                auth._create_default_accounts_if_needed(cursor, conn)

            auth.verify_default_accounts()
            print("Setup completed.")
            return True
        except Exception as e:
            print(f"❌ Error ensuring default accounts: {e}")
            return False
    
    def fix_missing_accounts(self):
        """Fix users that exist in users table but not in user_accounts table"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print("Checking for users without accounts...")
            
            # Find users without accounts
            cursor.execute('''
            SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            WHERE ua.user_id IS NULL
            ''')
            
            orphaned_users = cursor.fetchall()
            
            if not orphaned_users:
                print("No orphaned users found.")
                conn.close()
                return True
            
            print(f"Found {len(orphaned_users)} users without accounts. Creating accounts...")

            for user_id, username, email, first_name, last_name, role in orphaned_users:
                password = self._generate_temp_password()
                
                # Create the account
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                salt, password_hash = self._hash_password(password)
                
                cursor.execute('''
                INSERT INTO user_accounts 
                (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (username, password_hash, salt, user_id, timestamp, timestamp))

                identifier = username or email or f"user-{user_id}"
                print(
                    f"Created account for {identifier}. Temporary password generated; user must reset on next login: {password}"
                )
            
            conn.commit()
            conn.close()
            print("All missing accounts created successfully!")
            return True
            
        except Exception as e:
            logging.error(f"Error fixing missing accounts: {e}")
            return False
    
    def _generate_secret(self):
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    def _generate_recovery_codes(self, count=10):
        """Generate recovery codes for 2FA"""
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            codes.append(f"{code[:4]}-{code[4:]}")
        return codes
    
    def _hash_recovery_code(self, code):
        """Hash a recovery code"""
        return hashlib.sha256(code.encode()).hexdigest()
    
    def _validate_username(self, username):
        """Validate username format"""
        if not username:
            return False
        
        if not re.match(r'^[a-zA-Z0-9_-]{3,20}$', username):
            return False
        
        return True
    
    def _validate_password(self, password):
        """Validate password strength"""
        if not password or len(password) < 8:
            return False
        
        if not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
            return False
        
        return True
    
    def _validate_email(self, email):
        """Validate email format"""
        if not email:
            return False
        
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False
        
        return True
    
    def _generate_temp_password(self):
        """Generate a secure temporary password"""
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(12))
    
    def _get_default_password(self, key: str, fallback: str) -> str:
        """Fetch default password overrides from config if present."""
        try:
            defaults = self.config.get('default_accounts', {})
            if isinstance(defaults, dict):
                value = defaults.get(f"{key}_password") or defaults.get(key)
                if value:
                    return str(value)
        except Exception:
            pass
        return fallback

    def _infer_role_for_username(self, username: str) -> str:
        """Best-effort role inference when a user profile is missing."""
        lower = username.lower()
        if 'admin' in lower:
            return 'admin'
        if 'staff' in lower or 'faculty' in lower:
            return 'staff'
        if 'instructor' in lower or 'teacher' in lower:
            return 'instructor'
        return 'student'

    def _derive_name_from_username(self, username: str) -> Tuple[str, str]:
        """Create placeholder names from a username when needed."""
        import re as _re

        tokens = [token for token in _re.split(r'[._\-\s]+', username) if token]
        if len(tokens) >= 2:
            return tokens[0].title(), tokens[-1].title()
        if tokens:
            token = tokens[0].title()
            return token, 'User'
        return 'User', 'Account'

    def enable_two_fa(self, user_id):
        """Enable 2FA for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Generate new secret
            secret = self._generate_secret()
            
            # Update user account
            cursor.execute(
                'UPDATE user_accounts SET two_fa_enabled = 1, two_fa_secret = ? WHERE user_id = ?',
                (secret, user_id)
            )
            
            # Generate recovery codes
            recovery_codes = self._generate_recovery_codes()
            
            # Store hashed recovery codes
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for code in recovery_codes:
                code_hash = self._hash_recovery_code(code)
                cursor.execute(
                    'INSERT INTO two_fa_recovery_codes (user_id, code_hash, created_at) VALUES (?, ?, ?)',
                    (user_id, code_hash, timestamp)
                )
            
            conn.commit()
            
            # Get user info for QR code
            cursor.execute('''
                SELECT ua.username, u.email
                FROM user_accounts ua
                JOIN users u ON ua.user_id = u.id
                WHERE u.id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            username = user_data[0]
            email = user_data[1]
            
            # Generate TOTP URI for QR code
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=email,
                issuer_name='Student Records System'
            )
            
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64 for display
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
            
            conn.close()
            
            return {
                'success': True,
                'secret': secret,
                'qr_code': img_base64,
                'recovery_codes': recovery_codes,
                'message': '2FA has been enabled successfully.'
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return {'success': False, 'message': 'Failed to enable 2FA.'}
    
    def disable_two_fa(self, user_id):
        """Disable 2FA for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update user account
            cursor.execute(
                'UPDATE user_accounts SET two_fa_enabled = 0, two_fa_secret = NULL WHERE user_id = ?',
                (user_id,)
            )
            
            # Remove recovery codes
            cursor.execute('DELETE FROM two_fa_recovery_codes WHERE user_id = ?', (user_id,))
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'message': '2FA has been disabled successfully.'}
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return {'success': False, 'message': 'Failed to disable 2FA.'}
    
    def verify_two_fa_code(self, user_id, code):
        """Verify a 2FA TOTP code"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get user's 2FA secret
            cursor.execute(
                'SELECT two_fa_secret FROM user_accounts WHERE user_id = ? AND two_fa_enabled = 1',
                (user_id,)
            )
            
            result = cursor.fetchone()
            
            if not result or not result[0]:
                conn.close()
                return False
            
            secret = result[0]
            
            # Verify TOTP code
            totp = pyotp.TOTP(secret)
            is_valid = totp.verify(code, valid_window=1)  # Allow 1 step before/after
            
            conn.close()
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying 2FA code: {e}")
            return False
    
    def verify_recovery_code(self, user_id, code):
        """Verify and use a recovery code"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Hash the provided code
            code_hash = self._hash_recovery_code(code)
            
            # Check if code exists and is unused
            cursor.execute(
                'SELECT id FROM two_fa_recovery_codes WHERE user_id = ? AND code_hash = ? AND is_used = 0',
                (user_id, code_hash)
            )
            
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return False
            
            code_id = result[0]
            
            # Mark code as used
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE two_fa_recovery_codes SET is_used = 1, used_at = ? WHERE id = ?',
                (timestamp, code_id)
            )
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying recovery code: {e}")
            return False
    
    def regenerate_recovery_codes(self, user_id):
        """Regenerate recovery codes for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete old recovery codes
            cursor.execute('DELETE FROM two_fa_recovery_codes WHERE user_id = ?', (user_id,))
            
            # Generate new recovery codes
            recovery_codes = self._generate_recovery_codes()
            
            # Store hashed recovery codes
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for code in recovery_codes:
                code_hash = self._hash_recovery_code(code)
                cursor.execute(
                    'INSERT INTO two_fa_recovery_codes (user_id, code_hash, created_at) VALUES (?, ?, ?)',
                    (user_id, code_hash, timestamp)
                )
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'recovery_codes': recovery_codes,
                'message': 'Recovery codes regenerated successfully.'
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return {'success': False, 'message': 'Failed to regenerate recovery codes.'}
    
    def _log_activity(self, username, action, details=None, user_id=None):
        """Log user activity for audit purposes with comprehensive error handling"""
        
        # Input validation and sanitization
        if not username or not action:
            logging.warning("Activity logging skipped: username and action are required")
            return False
        
        # Sanitize inputs to prevent injection attacks
        username = str(username)[:255]  # Limit length
        action = str(action)[:500]      # Limit length
        details = str(details)[:1000] if details else None  # Limit length
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ip_address = self._get_client_ip()  # More sophisticated IP detection
        
        # Track logging attempts for monitoring
        log_entry = {
            'user_id': user_id,
            'username': username,
            'action': action,
            'details': details,
            'timestamp': timestamp,
            'ip_address': ip_address
        }
        
        # Primary database logging attempt
        try:
            return self._attempt_database_logging(log_entry)
            
        except sqlite3.OperationalError as e:
            return self._handle_operational_error(e, log_entry)
            
        except sqlite3.IntegrityError as e:
            return self._handle_integrity_error(e, log_entry)
            
        except sqlite3.DatabaseError as e:
            return self._handle_database_error(e, log_entry)
            
        except sqlite3.Error as e:
            return self._handle_sqlite_error(e, log_entry)
            
        except OSError as e:
            return self._handle_os_error(e, log_entry)
            
        except MemoryError as e:
            return self._handle_memory_error(e, log_entry)
            
        except Exception as e:
            return self._handle_unexpected_error(e, log_entry)

    def _attempt_database_logging(self, log_entry):
        """Attempt to log to the primary database"""
        log_conn = None
        
        try:
            # Establish connection with optimized settings for logging
            log_conn = sqlite3.connect(self.db_path, timeout=5.0)
            log_conn.execute("PRAGMA busy_timeout = 5000")      # 5 second timeout
            log_conn.execute("PRAGMA journal_mode = WAL")       # WAL mode for better concurrency
            log_conn.execute("PRAGMA synchronous = NORMAL")     # Balance safety and speed
            
            cursor = log_conn.cursor()
            
            # Verify table exists before attempting insert
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'")
            if not cursor.fetchone():
                logging.error("Activity log table does not exist - cannot log activity")
                return self._fallback_to_file_logging(log_entry, "Table does not exist")
            
            # Insert the log entry
            cursor.execute('''
                INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                log_entry['user_id'],
                log_entry['username'], 
                log_entry['action'],
                log_entry['details'],
                log_entry['timestamp'],
                log_entry['ip_address']
            ))
            
            log_conn.commit()
            logging.debug(f"Activity logged successfully for user: {log_entry['username']}")
            return True
            
        finally:
            # Ensure connection is properly closed
            if log_conn:
                try:
                    log_conn.close()
                except sqlite3.Error as close_error:
                    logging.warning(f"Error closing log database connection: {close_error}")
                except Exception as close_error:
                    logging.error(f"Unexpected error closing log connection: {type(close_error).__name__}: {close_error}")

    def _handle_operational_error(self, error, log_entry):
        """Handle SQLite operational errors with specific strategies"""
        error_msg = str(error).lower()
        
        if "database is locked" in error_msg:
            logging.warning(f"Database locked during activity logging for {log_entry['username']}")
            return self._retry_database_logging(log_entry, "database_locked")
            
        elif "disk i/o error" in error_msg:
            logging.error(f"Disk I/O error during activity logging: {error}")
            return self._fallback_to_file_logging(log_entry, f"Disk I/O error: {error}")
            
        elif "permission denied" in error_msg:
            logging.error(f"Permission denied for activity logging: {error}")
            return self._fallback_to_file_logging(log_entry, f"Permission denied: {error}")
            
        elif "no such table" in error_msg:
            logging.error(f"Activity log table missing: {error}")
            return self._fallback_to_file_logging(log_entry, f"Table missing: {error}")
            
        elif "database disk image is malformed" in error_msg:
            logging.critical(f"Database corruption detected during activity logging: {error}")
            return self._fallback_to_file_logging(log_entry, f"Database corruption: {error}")
            
        else:
            logging.error(f"Operational error during activity logging: {error}")
            return self._retry_database_logging(log_entry, "operational_error")

    def _handle_integrity_error(self, error, log_entry):
        """Handle database integrity constraint violations"""
        error_msg = str(error).lower()
        
        if "foreign key constraint failed" in error_msg:
            logging.warning(f"Foreign key constraint violation in activity log for user_id {log_entry['user_id']}: {error}")
            # Log without user_id to avoid constraint issues
            log_entry_copy = log_entry.copy()
            log_entry_copy['user_id'] = None
            return self._attempt_database_logging(log_entry_copy)
            
        elif "unique constraint failed" in error_msg:
            logging.debug(f"Duplicate activity log entry detected for {log_entry['username']}")
            # This might be acceptable for some logging scenarios
            return True
            
        else:
            logging.error(f"Integrity constraint violation in activity logging: {error}")
            return self._fallback_to_file_logging(log_entry, f"Integrity error: {error}")

    def _handle_database_error(self, error, log_entry):
        """Handle general database errors"""
        logging.error(f"Database error during activity logging: {error}")
        return self._fallback_to_file_logging(log_entry, f"Database error: {error}")

    def _handle_sqlite_error(self, error, log_entry):
        """Handle general SQLite errors"""
        logging.error(f"SQLite error during activity logging: {error}")
        return self._fallback_to_file_logging(log_entry, f"SQLite error: {error}")

    def _handle_os_error(self, error, log_entry):
        """Handle operating system errors"""
        error_msg = str(error).lower()
        
        if "disk full" in error_msg or "no space left" in error_msg:
            logging.critical(f"Disk space exhausted during activity logging: {error}")
            return self._emergency_memory_logging(log_entry, f"Disk full: {error}")
            
        elif "permission denied" in error_msg:
            logging.error(f"File permission error during activity logging: {error}")
            return self._fallback_to_alternate_location(log_entry, f"Permission error: {error}")
            
        else:
            logging.error(f"OS error during activity logging: {error}")
            return self._fallback_to_file_logging(log_entry, f"OS error: {error}")

    def _handle_memory_error(self, error, log_entry):
        """Handle memory exhaustion errors"""
        logging.critical(f"Memory error during activity logging: {error}")
        # Try to log essential information only
        minimal_entry = {
            'username': log_entry['username'][:50],  # Truncate to essential data
            'action': log_entry['action'][:100],
            'timestamp': log_entry['timestamp']
        }
        return self._emergency_memory_logging(minimal_entry, f"Memory error: {error}")

    def _handle_unexpected_error(self, error, log_entry):
        """Handle unexpected errors with comprehensive fallback"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        logging.error(f"Unexpected error during activity logging: {error_type}: {error_msg}")
        
        # Try to determine if this is a recoverable error
        if any(keyword in error_msg.lower() for keyword in ['timeout', 'temporary', 'retry']):
            return self._retry_database_logging(log_entry, f"unexpected_recoverable: {error_type}")
        else:
            return self._fallback_to_file_logging(log_entry, f"unexpected_error: {error_type}: {error_msg}")

    def _retry_database_logging(self, log_entry, reason):
        """Retry database logging with reduced timeout and fallback"""
        logging.info(f"Retrying activity logging due to: {reason}")
        
        try:
            time.sleep(0.1)  # Brief pause before retry
            
            log_conn = sqlite3.connect(self.db_path, timeout=1.0)
            log_conn.execute("PRAGMA busy_timeout = 1000")  # Reduced timeout for retry
            cursor = log_conn.cursor()
            
            cursor.execute('''
                INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                log_entry['user_id'],
                log_entry['username'],
                log_entry['action'],
                log_entry['details'],
                log_entry['timestamp'],
                log_entry['ip_address']
            ))
            
            log_conn.commit()
            log_conn.close()
            
            logging.debug(f"Activity logging retry successful for {log_entry['username']}")
            return True
            
        except sqlite3.Error as retry_error:
            logging.warning(f"Activity logging retry failed: {retry_error}")
            return self._fallback_to_file_logging(log_entry, f"retry_failed: {retry_error}")
            
        except Exception as retry_error:
            logging.error(f"Unexpected error during activity logging retry: {type(retry_error).__name__}: {retry_error}")
            return self._fallback_to_file_logging(log_entry, f"retry_unexpected: {retry_error}")

    def _fallback_to_file_logging(self, log_entry, reason):
        """Fallback to file-based logging with comprehensive error handling"""
        backup_file = 'activity_backup.log'
        
        try:
            # Ensure backup directory exists
            backup_path = Path(backup_file)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Format log entry for file output
            log_line = self._format_log_entry_for_file(log_entry, reason)
            
            # Attempt to write to backup file with proper encoding
            with open(backup_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
                f.flush()  # Ensure data is written immediately
            
            logging.info(f"Activity logged to backup file for {log_entry['username']} (reason: {reason})")
            return True
            
        except PermissionError as perm_error:
            logging.error(f"Permission denied writing to backup log: {perm_error}")
            return self._fallback_to_alternate_location(log_entry, f"backup_permission: {perm_error}")
            
        except OSError as os_error:
            logging.error(f"OS error writing to backup log: {os_error}")
            return self._emergency_memory_logging(log_entry, f"backup_os_error: {os_error}")
            
        except UnicodeEncodeError as encoding_error:
            logging.warning(f"Encoding error in backup logging: {encoding_error}")
            # Try with ASCII encoding as fallback
            try:
                safe_log_line = self._format_log_entry_for_file(log_entry, reason, safe_encoding=True)
                with open(backup_file, 'a', encoding='ascii', errors='replace') as f:
                    f.write(safe_log_line + '\n')
                    f.flush()
                logging.info(f"Activity logged to backup file with safe encoding for {log_entry['username']}")
                return True
            except Exception as safe_error:
                logging.error(f"Safe encoding backup also failed: {safe_error}")
                return self._emergency_memory_logging(log_entry, f"encoding_fallback_failed: {safe_error}")
                
        except Exception as file_error:
            logging.error(f"Unexpected error in file backup logging: {type(file_error).__name__}: {file_error}")
            return self._emergency_memory_logging(log_entry, f"file_backup_unexpected: {file_error}")

    def _fallback_to_alternate_location(self, log_entry, reason):
        """Try alternative logging locations when primary backup fails"""
        alternate_locations = [
            '/tmp/activity_backup.log',
            str(paths.LOG_DIR / 'activity_backup.log'),
            f'{os.path.expanduser("~")}/activity_backup.log'
        ]
        
        for alt_location in alternate_locations:
            try:
                alt_path = Path(alt_location)
                alt_path.parent.mkdir(parents=True, exist_ok=True)
                
                log_line = self._format_log_entry_for_file(log_entry, reason)
                
                with open(alt_location, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
                    f.flush()
                
                logging.info(f"Activity logged to alternate location {alt_location} for {log_entry['username']}")
                return True
                
            except Exception as alt_error:
                logging.debug(f"Alternate location {alt_location} failed: {alt_error}")
                continue
        
        # If all alternate locations fail
        logging.error(f"All alternate logging locations failed for {log_entry['username']}")
        return self._emergency_memory_logging(log_entry, f"all_alternates_failed: {reason}")

    def _emergency_memory_logging(self, log_entry, reason):
        """Emergency in-memory logging when all file operations fail"""
        try:
            # Store in a class attribute for later retrieval
            if not hasattr(self, '_emergency_log_buffer'):
                self._emergency_log_buffer = []
            
            emergency_entry = {
                'timestamp': log_entry['timestamp'],
                'username': log_entry['username'],
                'action': log_entry['action'],
                'reason': reason
            }
            
            # Limit buffer size to prevent memory issues
            if len(self._emergency_log_buffer) >= 1000:
                self._emergency_log_buffer.pop(0)  # Remove oldest entry
            
            self._emergency_log_buffer.append(emergency_entry)
            
            logging.warning(f"Activity logged to emergency memory buffer for {log_entry['username']} (reason: {reason})")
            return True
            
        except Exception as emergency_error:
            # Absolute last resort - log to Python's logging system only
            logging.critical(f"Emergency memory logging failed for {log_entry['username']}: {emergency_error}")
            logging.critical(f"Lost activity log: {log_entry['username']} performed {log_entry['action']} at {log_entry['timestamp']}")
            return False

    def _format_log_entry_for_file(self, log_entry, reason, safe_encoding=False):
        """Format log entry for file output with optional safe encoding"""
        if safe_encoding:
            # Use safe ASCII characters only
            username = ''.join(c if ord(c) < 128 else '?' for c in log_entry['username'])
            action = ''.join(c if ord(c) < 128 else '?' for c in log_entry['action'])
            details = ''.join(c if ord(c) < 128 else '?' for c in log_entry['details']) if log_entry['details'] else 'None'
        else:
            username = log_entry['username']
            action = log_entry['action']
            details = log_entry['details'] or 'None'
        
        return f"{log_entry['timestamp']} - {username}: {action} - {details} - IP: {log_entry['ip_address']} - Reason: {reason}"

    def _get_client_ip(self):
        """Get client IP address with fallback for different environments"""
        # In a real web application, you would extract this from the request
        # For now, return localhost but make it extensible
        try:
            # This could be extended to get real IP from web frameworks
            # like Flask (request.remote_addr) or Django (request.META['REMOTE_ADDR'])
            return "127.0.0.1"
        except Exception:
            return "unknown"

    def get_emergency_log_buffer(self):
        """Retrieve emergency log buffer for manual processing"""
        return getattr(self, '_emergency_log_buffer', [])

    def clear_emergency_log_buffer(self):
        """Clear the emergency log buffer after processing"""
        if hasattr(self, '_emergency_log_buffer'):
            self._emergency_log_buffer.clear()
            logging.info("Emergency log buffer cleared")

    def _log_login_attempt(self, username, success):
        """Log login attempts for security monitoring"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ip_address = "127.0.0.1"  # In a real system, you would get this from the request
                
                cursor.execute(
                    'INSERT INTO login_attempts (username, attempt_time, ip_address, success) VALUES (?, ?, ?, ?)',
                    (username, timestamp, ip_address, 1 if success else 0)
                )
                
                conn.commit()
        except sqlite3.Error as e:
            # Don't raise exceptions for logging failures
            print(f"Warning: Failed to log login attempt: {e}")
    
    def _increment_login_attempts(self, username):
        """Track failed login attempts"""
        if username in self.login_attempts:
            attempts, _ = self.login_attempts[username]
            self.login_attempts[username] = (attempts + 1, datetime.now())
        else:
            self.login_attempts[username] = (1, datetime.now())
    
    def check_session(self):
        """Check if the current session is valid and not timed out"""
        if not self.current_user:
            return False
        
        if not self.last_activity:
            return False
        
        # Check if session has timed out
        elapsed = (datetime.now() - self.last_activity).total_seconds() / 60
        if elapsed > self.session_timeout:
            print("Your session has timed out due to inactivity. Please log in again.")
            self.logout()
            return False
        
        # Update last activity time
        self.last_activity = datetime.now()
        return True
    
    def check_permission(self, permission, raise_exception=False):
        """
        Check if the current user has a specific permission.

        Args:
            permission: The permission name to check
            raise_exception: If True, raises exception when permission denied.
                           If False, returns False when permission denied (default).

        Returns:
            bool: True if user has permission, False if not (when raise_exception=False)

        Raises:
            SessionExpiredError: If session is invalid or expired (when raise_exception=True)
            PermissionDeniedError: If user lacks the required permission (when raise_exception=True)
        """
        # Check session
        if not self.check_session():
            if raise_exception:
                raise SessionExpiredError(
                    "Your session has expired. Please log in again.",
                    code="SESSION_EXPIRED"
                )
            return False

        # Check permission
        if permission not in self.current_user.get('permissions', []):
            if raise_exception:
                raise PermissionDeniedError(
                    f"You do not have the '{permission}' permission.",
                    code="PERMISSION_DENIED",
                    details={'required_permission': permission, 'user': self.current_user.get('username')}
                )
            return False

        return True

    def has_permission(self, permission):
        """
        Check if the current user has a specific permission without raising exceptions.

        This method is intended for use in conditional statements where you want to
        check permissions without triggering exceptions.

        Args:
            permission: The permission name to check

        Returns:
            bool: True if user has permission and session is valid, False otherwise
        """
        try:
            # Check if user is logged in and session is valid
            if not self.current_user or not self.check_session():
                return False

            # Check if user has the permission
            return permission in self.current_user.get('permissions', [])
        except Exception:
            # If any error occurs, return False
            return False

    def create_user(self, username, password, email, first_name, last_name, role, student_id=None, password_reset_required=False):
        """
        Create a new user with improved duplicate checking.

        Raises:
            InvalidInputError: If username, password, email, or role is invalid
            DatabaseError: If there's a database error during user creation
        """
        # Validate inputs
        if not self._validate_username(username):
            raise InvalidInputError(
                "Invalid username format. Username must be 3-20 characters and contain only letters, numbers, underscores, or hyphens.",
                code="INVALID_USERNAME",
                details={'username': username}
            )

        if not self._validate_password(password):
            raise InvalidInputError(
                "Invalid password. Password must be at least 8 characters long and contain both letters and numbers.",
                code="INVALID_PASSWORD"
            )

        if not self._validate_email(email):
            raise InvalidInputError(
                "Invalid email format.",
                code="INVALID_EMAIL",
                details={'email': email}
            )

        if role not in ROLES:
            raise InvalidInputError(
                f"Invalid role. Valid roles are: {', '.join(ROLES.keys())}",
                code="INVALID_ROLE",
                details={'role': role, 'valid_roles': list(ROLES.keys())}
            )

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check if username already exists in user_accounts
                cursor.execute('SELECT id FROM user_accounts WHERE username = ?', (username,))
                if cursor.fetchone():
                    # Only log if this is not expected (i.e., not during system initialization)
                    if not hasattr(self, '_initialization_mode'):
                        print("Username already exists.")
                    return False

                # Check if email already exists in users table
                cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
                if cursor.fetchone():
                    if not hasattr(self, '_initialization_mode'):
                        print("Email already exists.")
                    return False

                # If this is a student user, validate student_id
                if role == 'student' and student_id:
                    cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                    if not cursor.fetchone():
                        print(f"Student ID {student_id} does not exist in the system.")
                        return False

                # Hash the password
                salt, password_hash = self._hash_password(password)

                # Timestamp
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert the new user
                cursor.execute(
                    '''INSERT INTO users 
                       (username, first_name, last_name, email, role, student_id, created_at, updated_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (username, first_name, last_name, email, role, student_id, timestamp, timestamp)
                )
                user_id = cursor.lastrowid

                # Insert the account
                cursor.execute(
                    '''INSERT INTO user_accounts 
                       (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (username, password_hash, salt, user_id, timestamp, timestamp, 1 if password_reset_required else 0)
                )

                conn.commit()

            # log after connection is closed (only if not in initialization mode)
            if not hasattr(self, '_initialization_mode'):
                self._log_activity('system', f'User created: {username}', f'Role: {role}')
                print(f"User {username} created successfully with role {role}.")
            return True

        except sqlite3.Error as e:
            if not hasattr(self, '_initialization_mode'):
                logger.error(f"Database error: {e}")
            return False
        
    def login(self, username, password):
        """
        Authenticate a user and create a session.

        Args:
            username: The username
            password: The password

        Returns:
            dict or bool: Login result with user info, or dict with 2FA requirement

        Raises:
            InvalidCredentialsError: If credentials are invalid or account is locked
            AuthenticationError: If account is deactivated or other auth errors
            DatabaseError: If database operation fails
        """
        # Check if the user is locked out due to too many failed attempts
        if username in self.login_attempts:
            attempts, last_attempt_time = self.login_attempts[username]
            if attempts >= self.max_attempts:
                elapsed = (datetime.now() - last_attempt_time).total_seconds() / 60
                if elapsed < self.lockout_time:
                    wait_time = int(self.lockout_time - elapsed)
                    raise InvalidCredentialsError(
                        f"Account temporarily locked. Please try again in {wait_time} minutes.",
                        details={
                            'username': username,
                            'locked_until': (last_attempt_time + timedelta(minutes=self.lockout_time)).isoformat(),
                            'wait_minutes': wait_time
                        }
                    )
                else:
                    # Reset attempts if lockout period has passed
                    del self.login_attempts[username]
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # First try with join (ideal case)
                cursor.execute(
                    '''SELECT ua.id, ua.password_hash, ua.salt, ua.user_id, ua.is_active, 
                              ua.password_reset_required, ua.two_fa_enabled, u.role 
                       FROM user_accounts ua
                       JOIN users u ON ua.user_id = u.id
                       WHERE ua.username = ?''',
                    (username,)
                )
                
                user_data = cursor.fetchone()
                
                # If join fails, try without join and use default role
                if not user_data:
                    cursor.execute(
                        '''SELECT id, password_hash, salt, user_id, is_active, 
                                  password_reset_required, two_fa_enabled
                           FROM user_accounts 
                           WHERE username = ?''',
                        (username,)
                    )
                    
                    account_data = cursor.fetchone()
                    
                    if account_data:
                        logging.warning(
                            "User profile missing for account '%s'. Resolve the inconsistency via the administration tools.",
                            username,
                        )
                        (
                            account_id,
                            password_hash,
                            salt,
                            user_id,
                            is_active,
                            password_reset_required,
                            two_fa_enabled,
                        ) = account_data

                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        role_guess = self._infer_role_for_username(username)
                        first_name, last_name = self._derive_name_from_username(username)
                        email = f"{username}@university.local"

                        try:
                            cursor.execute(
                                '''
                                INSERT INTO users (id, username, first_name, last_name, email, role, student_id, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''',
                                (
                                    user_id,
                                    username,
                                    first_name,
                                    last_name,
                                    email,
                                    role_guess,
                                    None,
                                    timestamp,
                                    timestamp,
                                ),
                            )
                            conn.commit()
                            logging.info("Created missing user profile for account '%s'.", username)
                        except sqlite3.IntegrityError as exc:
                            logging.debug(
                                "User profile insertion for '%s' hit integrity constraint: %s",
                                username,
                                exc,
                            )
                        except sqlite3.OperationalError as exc:
                            logging.error(
                                "Operational error while creating user profile for '%s': %s",
                                username,
                                exc,
                            )
                        except sqlite3.Error as exc:
                            logging.error(
                                "Database error while creating user profile for '%s': %s",
                                username,
                                exc,
                            )
                        except Exception as exc:
                            logging.error(
                                "Unexpected error while creating user profile for '%s': %s",
                                username,
                                exc,
                            )

                        cursor.execute(
                            '''SELECT ua.id, ua.password_hash, ua.salt, ua.user_id, ua.is_active,
                                      ua.password_reset_required, ua.two_fa_enabled, u.role
                               FROM user_accounts ua
                               JOIN users u ON ua.user_id = u.id
                               WHERE ua.username = ?''',
                            (username,),
                        )
                        user_data = cursor.fetchone()

                        if not user_data:
                            return False
                
                if not user_data:
                    # Increment failed login attempts
                    self._increment_login_attempts(username)
                    self._log_login_attempt(username, False)

                    # Use centralized activity logger for failed login
                    if ACTIVITY_LOGGER_AVAILABLE:
                        log_login(username, success=False)

                    raise InvalidCredentialsError(
                        "Invalid username or password.",
                        details={'username': username}
                    )

                account_id, password_hash, salt, user_id, is_active, password_reset_required, two_fa_enabled, role = user_data

                # Check if the account is active
                if not is_active:
                    raise AuthenticationError(
                        "This account has been deactivated. Please contact an administrator.",
                        code="ACCOUNT_DEACTIVATED",
                        details={'username': username}
                    )

                # Verify the password
                _, hashed_attempt = self._hash_password(password, salt)

                if hashed_attempt != password_hash:
                    # Increment failed login attempts
                    self._increment_login_attempts(username)
                    self._log_login_attempt(username, False)

                    # Use centralized activity logger for failed login
                    if ACTIVITY_LOGGER_AVAILABLE:
                        log_login(username, success=False)

                    raise InvalidCredentialsError(
                        "Invalid username or password.",
                        details={'username': username}
                    )
                
                # Password is correct, check if 2FA is required
                if two_fa_enabled:
                    return {'success': True, 'requires_2fa': True, 'user_id': user_id, 'username': username}
                
                # Complete login without 2FA
                return self._complete_login(user_id, account_id, username, role, password_reset_required)
                
        except InvalidCredentialsError:
            # Re-raise authentication errors as-is
            raise
        except AuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except sqlite3.Error as e:
            logging.error(f"Database error during login for {username}: {e}")
            logger.error(f"Database error: {e}")
            raise DatabaseError(
                f"Database error during login: {str(e)}",
                code="DB_LOGIN_ERROR",
                details={'username': username}
            ) from e
        except Exception as e:
            logging.error(f"Unexpected error during login for {username}: {type(e).__name__}: {e}")
            raise AuthenticationError(
                "An unexpected error occurred during login. Please try again.",
                code="AUTH_UNEXPECTED_ERROR",
                details={'username': username, 'error_type': type(e).__name__}
            ) from e
    
    def _complete_login(self, user_id, account_id, username, role, password_reset_required):
        """Complete the login process after authentication"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Update last login
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'UPDATE user_accounts SET last_login = ? WHERE id = ?',
                    (timestamp, account_id)
                )
                
                conn.commit()
                
                # Get user permissions
                permissions = self.get_user_permissions(user_id)
                
                # Set current user
                self.current_user = {
                    'id': user_id,
                    'account_id': account_id,
                    'username': username,
                    'role': role,
                    'permissions': permissions,
                    'password_reset_required': password_reset_required
                }
                
                # Update last activity time
                self.last_activity = datetime.now()

                # Log successful login
                self._log_login_attempt(username, True)
                self._log_activity(username, 'User login', None, user_id)

                # Use centralized activity logger
                if ACTIVITY_LOGGER_AVAILABLE:
                    set_user(username)
                    log_login(username, success=True)

                # Reset login attempts
                if username in self.login_attempts:
                    del self.login_attempts[username]

                # Notify if password reset is required
                if password_reset_required:
                    print("You must change your password before continuing.")
                    return 'password_reset_required'

                print(f"Welcome, {username}! You are logged in as {role}.")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
    
    def complete_two_fa_login(self, user_id, username, code):
        """Complete login after 2FA verification"""
        # Verify the 2FA code
        if not self.verify_two_fa_code(user_id, code):
            # Check if it's a recovery code
            if not self.verify_recovery_code(user_id, code):
                print("Invalid 2FA code.")
                return False
        
        # Get full user data
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                '''SELECT ua.id, ua.password_reset_required, u.role
                   FROM user_accounts ua
                   JOIN users u ON ua.user_id = u.id
                   WHERE u.id = ?''',
                (user_id,)
            )
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                return False
            
            account_id, password_reset_required, role = user_data
            
            conn.close()
            
            # Complete the login
            return self._complete_login(user_id, account_id, username, role, password_reset_required)
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
    
    def logout(self):
        """Log out the current user"""
        if not self.current_user:
            print("No user is currently logged in.")
            return

        username = self.current_user.get('username', 'Unknown')
        user_id = self.current_user.get('id', self.current_user.get('user_id'))

        # Log the logout activity
        if user_id:
            self._log_activity(username, 'User logout', None, user_id)

        # Use centralized activity logger
        if ACTIVITY_LOGGER_AVAILABLE:
            log_logout(username)

        # Clear the current user
        self.current_user = None
        self.last_activity = None

        print(f"Goodbye, {username}! You have been logged out.")
    
    def change_password(self, username, current_password, new_password):
        """Change a user's password"""
        if not self._validate_password(new_password):
            print("Invalid new password. Password must be at least 8 characters long and contain a mix of letters, numbers, and special characters.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get user account data
            cursor.execute(
                'SELECT id, user_id, password_hash, salt FROM user_accounts WHERE username = ?',
                (username,)
            )
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                conn.close()
                return False
            
            account_id, user_id, password_hash, salt = user_data
            
            # Verify the current password
            _, hashed_current = self._hash_password(current_password, salt)
            
            if hashed_current != password_hash:
                print("Current password is incorrect.")
                conn.close()
                return False
            
            # Hash the new password
            salt, new_hash = self._hash_password(new_password)
            
            # Update the password
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE user_accounts SET password_hash = ?, salt = ?, updated_at = ?, password_reset_required = 0 WHERE id = ?',
                (new_hash, salt, timestamp, account_id)
            )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(username, 'Password changed', None, user_id)
            
            # Update current user if this is the logged-in user
            if self.current_user and self.current_user['id'] == user_id:
                self.current_user['password_reset_required'] = 0
            
            print("Password changed successfully.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def reset_password(self, username, admin_user_id=None):
        """Reset a user's password to a temporary one (admin function)"""
        if not self.current_user or ('manage_users' not in self.current_user['permissions'] and self.current_user['id'] != admin_user_id):
            print("You don't have permission to reset passwords.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get user account data
            cursor.execute(
                'SELECT id, user_id FROM user_accounts WHERE username = ?',
                (username,)
            )
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                conn.close()
                return False
            
            account_id, user_id = user_data
            
            # Generate a temporary password
            temp_password = self._generate_temp_password()
            
            # Hash the temporary password
            salt, password_hash = self._hash_password(temp_password)
            
            # Update the password
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE user_accounts SET password_hash = ?, salt = ?, updated_at = ?, password_reset_required = 1 WHERE id = ?',
                (password_hash, salt, timestamp, account_id)
            )
            
            conn.commit()
            
            # Log the activity
            admin_username = self.current_user['username'] if self.current_user else "system"
            self._log_activity(admin_username, f'Password reset for user: {username}', None, self.current_user['id'] if self.current_user else None)
            
            print(f"Password for {username} has been reset to: {temp_password}")
            print("User will be required to change password on next login.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def update_user(self, user_id, **kwargs):
        """Update user information"""
        if not self.current_user:
            print("You must be logged in to update user information.")
            return False
        
        # Check if the current user has permission to update users
        if self.current_user['id'] != user_id and 'manage_users' not in self.current_user['permissions']:
            print("You don't have permission to update other users.")
            return False
        
        # Validate inputs
        if 'username' in kwargs and not self._validate_username(kwargs['username']):
            print("Invalid username format.")
            return False
        
        if 'email' in kwargs and not self._validate_email(kwargs['email']):
            print("Invalid email format.")
            return False
        
        if 'role' in kwargs and kwargs['role'] not in ROLES:
            print(f"Invalid role. Valid roles are: {', '.join(ROLES.keys())}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the user exists
            cursor.execute('''
                SELECT u.id, ua.username
                FROM users u
                JOIN user_accounts ua ON u.id = ua.user_id
                WHERE u.id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                conn.close()
                return False
            
            user_id, username = user_data
            
            # Check for uniqueness of username
            if 'username' in kwargs:
                cursor.execute('SELECT id FROM user_accounts WHERE username = ? AND user_id != ?', (kwargs['username'], user_id))
                if cursor.fetchone():
                    print("Username already exists.")
                    conn.close()
                    return False
            
            # Check for uniqueness of email
            if 'email' in kwargs:
                cursor.execute('SELECT id FROM users WHERE email = ? AND id != ?', (kwargs['email'], user_id))
                if cursor.fetchone():
                    print("Email already exists.")
                    conn.close()
                    return False
            
            # Separate user table fields from user_accounts table fields
            user_updates = {}
            account_updates = {}
            
            # Fields for users table
            user_fields = ['first_name', 'last_name', 'email', 'role', 'student_id']
            # Fields for user_accounts table
            account_fields = ['username', 'is_active']
            
            for key, value in kwargs.items():
                if key in user_fields:
                    user_updates[key] = value
                elif key in account_fields:
                    account_updates[key] = value
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Update users table if needed
            if user_updates:
                # Build the update query
                update_fields = []
                update_values = []
                
                for key, value in user_updates.items():
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
                
                # Add updated_at timestamp
                update_fields.append("updated_at = ?")
                update_values.append(timestamp)
                
                # Add user_id to values
                update_values.append(user_id)
                
                # Execute the update
                cursor.execute(
                    f'UPDATE users SET {", ".join(update_fields)} WHERE id = ?',
                    update_values
                )
            
            # Update user_accounts table if needed
            if account_updates:
                # Build the update query
                update_fields = []
                update_values = []
                
                for key, value in account_updates.items():
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
                
                # Add updated_at timestamp
                update_fields.append("updated_at = ?")
                update_values.append(timestamp)
                
                # Add user_id to values
                update_values.append(user_id)
                
                # Execute the update
                cursor.execute(
                    f'UPDATE user_accounts SET {", ".join(update_fields)} WHERE user_id = ?',
                    update_values
                )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'User updated: {username}',
                f'Fields updated: {", ".join(kwargs.keys())}',
                self.current_user['id']
            )
            
            # Update current user information if this is the logged-in user
            if self.current_user and self.current_user['id'] == user_id:
                for key, value in kwargs.items():
                    if key in self.current_user:
                        self.current_user[key] = value
            
            print(f"User {username} updated successfully.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def deactivate_user(self, user_id):
        """Deactivate a user account"""
        if not self.current_user or 'manage_users' not in self.current_user['permissions']:
            print("You don't have permission to deactivate users.")
            return False
        
        # Make sure user isn't deactivating themselves
        if self.current_user['id'] == user_id:
            print("You cannot deactivate your own account.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the user exists
            cursor.execute('''
                SELECT u.id, ua.username, u.role
                FROM users u
                JOIN user_accounts ua ON u.id = ua.user_id
                WHERE u.id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                conn.close()
                return False
            
            user_id, username, role = user_data
            
            # Prevent deactivating the last admin user
            if role == 'admin':
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM users u
                    JOIN user_accounts ua ON u.id = ua.user_id
                    WHERE u.role = ? AND ua.is_active = 1
                ''', ('admin',))
                
                admin_count = cursor.fetchone()[0]
                
                if admin_count <= 1:
                    print("Cannot deactivate the last active admin user.")
                    conn.close()
                    return False
            
            # Deactivate the user account
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE user_accounts SET is_active = 0, updated_at = ? WHERE user_id = ?',
                (timestamp, user_id)
            )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'User deactivated: {username}',
                None,
                self.current_user['id']
            )
            
            print(f"User {username} has been deactivated.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def activate_user(self, user_id):
        """Activate a user account"""
        if not self.current_user or 'manage_users' not in self.current_user['permissions']:
            print("You don't have permission to activate users.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the user exists
            cursor.execute('''
                SELECT ua.username
                FROM user_accounts ua
                WHERE ua.user_id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                conn.close()
                return False
            
            username = user_data[0]
            
            # Activate the user account
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE user_accounts SET is_active = 1, updated_at = ? WHERE user_id = ?',
                (timestamp, user_id)
            )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'User activated: {username}',
                None,
                self.current_user['id']
            )
            
            print(f"User {username} has been activated.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def delete_user(self, user_id):
        """Delete a user from the system"""
        if not self.current_user or 'manage_users' not in self.current_user['permissions']:
            print("You don't have permission to delete users.")
            return False
        
        # Make sure user isn't deleting themselves
        if self.current_user['id'] == user_id:
            print("You cannot delete your own account.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the user exists
            cursor.execute('''
                SELECT u.id, ua.username, u.role
                FROM users u
                JOIN user_accounts ua ON u.id = ua.user_id
                WHERE u.id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                conn.close()
                return False
            
            user_id, username, role = user_data
            
            # Prevent deleting the last admin user
            if role == 'admin':
                cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('admin',))
                admin_count = cursor.fetchone()[0]
                
                if admin_count <= 1:
                    print("Cannot delete the last admin user.")
                    conn.close()
                    return False
            
            # Delete user's 2FA data
            cursor.execute('DELETE FROM two_fa_recovery_codes WHERE user_id = ?', (user_id,))
            
            # Delete user's custom permissions
            cursor.execute('DELETE FROM user_permissions WHERE user_id = ?', (user_id,))
            
            # Delete the user account
            cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
            
            # Delete the user
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'User deleted: {username}',
                None,
                self.current_user['id']
            )
            
            print(f"User {username} has been deleted.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def list_users(self):
        """List all users in the system with better error handling"""
        if not self.current_user or 'manage_users' not in self.current_user['permissions']:
            print("You don't have permission to view all users.")
            return None
        
        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # First try the JOIN query
                cursor.execute('''
                    SELECT u.id, ua.username, u.email, u.first_name, u.last_name, u.role, 
                           ua.is_active, ua.last_login, u.created_at, u.student_id, ua.two_fa_enabled
                    FROM users u
                    JOIN user_accounts ua ON u.id = ua.user_id
                    ORDER BY u.role, ua.username
                ''')
                
                users = [dict(row) for row in cursor.fetchall()]
                
                # Also check for orphaned records
                cursor.execute('''
                    SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                           u.created_at, u.student_id
                    FROM users u
                    LEFT JOIN user_accounts ua ON u.id = ua.user_id
                    WHERE ua.user_id IS NULL
                ''')
                
                orphaned_users = cursor.fetchall()
                
                if orphaned_users:
                    print(f"\nWarning: Found {len(orphaned_users)} orphaned user records (no account):")
                    for user in orphaned_users:
                        print(f"  - User ID {user['id']}: {user['username']} ({user['email']})")
                
                cursor.execute('''
                    SELECT ua.id, ua.username, ua.user_id, ua.is_active, ua.last_login
                    FROM user_accounts ua
                    LEFT JOIN users u ON ua.user_id = u.id
                    WHERE u.id IS NULL
                ''')
                
                orphaned_accounts = cursor.fetchall()
                
                if orphaned_accounts:
                    print(f"\nWarning: Found {len(orphaned_accounts)} orphaned account records (no user profile):")
                    for account in orphaned_accounts:
                        print(f"  - Account ID {account['id']}: {account['username']} (user_id: {account['user_id']})")
                
                return users
                
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
    
    def get_user(self, user_id=None, username=None):
        """Get information about a specific user"""
        if not self.current_user:
            print("You must be logged in to view user information.")
            return None
        
        # Make sure the user has permission to view this user
        if (user_id is not None and user_id != self.current_user['id']) or \
           (username is not None and username != self.current_user['username']):
            if 'manage_users' not in self.current_user['permissions']:
                print("You don't have permission to view other users.")
                return None
        
        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if user_id is not None:
                    # First try the JOIN query
                    cursor.execute('''
                        SELECT u.id, ua.username, u.email, u.first_name, u.last_name, u.role, 
                               ua.is_active, ua.last_login, u.created_at, u.updated_at, u.student_id,
                               ua.two_fa_enabled
                        FROM users u
                        JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.id = ?
                    ''', (user_id,))
                    
                    user = cursor.fetchone()
                    
                    if not user:
                        # If JOIN fails, try to find the user in users table alone
                        cursor.execute('''
                            SELECT id, username, email, first_name, last_name, role, 
                                   created_at, updated_at, student_id
                            FROM users
                            WHERE id = ?
                        ''', (user_id,))
                        
                        user_only = cursor.fetchone()
                        
                        if user_only:
                            print(f"Warning: User {user_id} exists in users table but not in user_accounts table.")
                            print("This indicates a database inconsistency that should be fixed.")
                            return None
                        else:
                            print(f"User with ID {user_id} not found.")
                            return None
                
                elif username is not None:
                    # First try the JOIN query
                    cursor.execute('''
                        SELECT u.id, ua.username, u.email, u.first_name, u.last_name, u.role, 
                               ua.is_active, ua.last_login, u.created_at, u.updated_at, u.student_id,
                               ua.two_fa_enabled
                        FROM users u
                        JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE ua.username = ?
                    ''', (username,))
                    
                    user = cursor.fetchone()
                    
                    if not user:
                        print(f"User '{username}' not found.")
                        return None
                else:
                    print("Either user_id or username must be provided.")
                    return None
                
                if user:
                    # Convert row to dictionary
                    user_dict = dict(user)
                    
                    # Get user permissions
                    user_dict['permissions'] = self.get_user_permissions(user_dict['id'])
                    
                    return user_dict
                else:
                    print("User not found.")
                    return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            print("This might indicate database corruption or schema issues.")
            return None

    def fix_database_consistency(self):
        """Fix database consistency issues between users and user_accounts tables"""
        if not self.current_user or 'manage_users' not in self.current_user['permissions']:
            print("You don't have permission to fix database issues.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print("Checking database consistency...")
            
            # Find orphaned user records (users without accounts)
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role, u.student_id
                FROM users u
                LEFT JOIN user_accounts ua ON u.id = ua.user_id
                WHERE ua.user_id IS NULL
            ''')
            
            orphaned_users = cursor.fetchall()
            
            if orphaned_users:
                print(f"Found {len(orphaned_users)} users without accounts. Creating accounts...")

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                for user in orphaned_users:
                    user_id, username, email, first_name, last_name, role, student_id = user

                    # Check if an account with this username already exists
                    cursor.execute('SELECT id, user_id FROM user_accounts WHERE username = ?', (username,))
                    existing_account = cursor.fetchone()

                    if existing_account:
                        print(f"  - Account for '{username}' already exists, skipping...")
                        continue

                    # Generate a temporary password
                    temp_password = self._generate_temp_password()
                    salt, password_hash = self._hash_password(temp_password)

                    try:
                        cursor.execute('''
                            INSERT INTO user_accounts
                            (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                            VALUES (?, ?, ?, ?, ?, ?, 1)
                        ''', (username, password_hash, salt, user_id, timestamp, timestamp))

                        print(f"  - Created account for {username} (temp password: {temp_password})")
                    except sqlite3.IntegrityError as e:
                        print(f"  - Failed to create account for {username}: {e}")
            
            # Find orphaned account records (accounts without users)
            cursor.execute('''
                SELECT ua.id, ua.username, ua.user_id
                FROM user_accounts ua
                LEFT JOIN users u ON ua.user_id = u.id
                WHERE u.id IS NULL
            ''')

            orphaned_accounts = cursor.fetchall()

            if orphaned_accounts:
                print(f"Found {len(orphaned_accounts)} accounts without user profiles.")
                print("These orphaned accounts will be removed to maintain database integrity...")

                for account in orphaned_accounts:
                    account_id, username, user_id = account

                    # Check if a user with this username already exists
                    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                    existing_user = cursor.fetchone()

                    if existing_user:
                        # User exists, update the account to point to the correct user
                        print(f"  - Updating orphaned account '{username}' to link with existing user")
                        cursor.execute('''
                            UPDATE user_accounts
                            SET user_id = ?
                            WHERE id = ?
                        ''', (existing_user[0], account_id))
                    else:
                        # No matching user exists, delete the orphaned account
                        print(f"  - Deleting orphaned account '{username}' (no matching user found)")
                        cursor.execute('DELETE FROM user_accounts WHERE id = ?', (account_id,))
            
            conn.commit()
            conn.close()
            
            print("Database consistency check completed!")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error while fixing consistency: {e}")
            return False
    
    def get_user_permissions(self, user_id):
        """Get all permissions for a user based on their role and custom permissions"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get user's role
                cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
                user_data = cursor.fetchone()
                
                if not user_data:
                    print("User not found.")
                    return []
                
                role = user_data[0]
                
                # Get role ID
                cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
                role_result = cursor.fetchone()
                if not role_result:
                    return []
                
                role_id = role_result[0]
                
                # Get permissions from role
                cursor.execute('''
                    SELECT p.permission_name
                    FROM permissions p
                    JOIN role_permissions rp ON p.id = rp.permission_id
                    WHERE rp.role_id = ?
                ''', (role_id,))
                
                role_permissions = [row[0] for row in cursor.fetchall()]
                
                # Get custom user permissions
                cursor.execute('''
                    SELECT p.permission_name, up.granted
                    FROM permissions p
                    JOIN user_permissions up ON p.id = up.permission_id
                    WHERE up.user_id = ?
                ''', (user_id,))
                
                custom_permissions = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Combine permissions (custom permissions override role permissions)
                permissions = []
                for perm in role_permissions:
                    if perm in custom_permissions:
                        if custom_permissions[perm]:
                            permissions.append(perm)
                    else:
                        permissions.append(perm)
                
                # Add custom permissions that are granted but not in role
                for perm, granted in custom_permissions.items():
                    if granted and perm not in permissions:
                        permissions.append(perm)
                
                return permissions
                
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return []
    
    def set_user_permission(self, user_id, permission_name, granted=True):
        """Set a custom permission for a user"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to modify user permissions.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the user exists
            cursor.execute('''
                SELECT ua.username
                FROM user_accounts ua
                WHERE ua.user_id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                conn.close()
                return False
            
            username = user_data[0]
            
            # Check if the permission exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
            permission_data = cursor.fetchone()
            
            if not permission_data:
                print(f"Permission '{permission_name}' not found.")
                conn.close()
                return False
            
            permission_id = permission_data[0]
            
            # Check if a custom permission already exists
            cursor.execute(
                'SELECT id FROM user_permissions WHERE user_id = ? AND permission_id = ?',
                (user_id, permission_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing permission
                cursor.execute(
                    'UPDATE user_permissions SET granted = ? WHERE user_id = ? AND permission_id = ?',
                    (1 if granted else 0, user_id, permission_id)
                )
            else:
                # Insert new permission
                cursor.execute(
                    'INSERT INTO user_permissions (user_id, permission_id, granted) VALUES (?, ?, ?)',
                    (user_id, permission_id, 1 if granted else 0)
                )
            
            conn.commit()
            
            # Log the activity
            action = "granted" if granted else "revoked"
            self._log_activity(
                self.current_user['username'],
                f'Permission {action}: {permission_name}',
                f'For user: {username}',
                self.current_user['id']
            )
            
            print(f"Permission '{permission_name}' has been {'granted to' if granted else 'revoked from'} user {username}.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def remove_user_permission(self, user_id, permission_name):
        """Remove a custom permission from a user (revert to role default)"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to modify user permissions.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the user exists
            cursor.execute('''
                SELECT ua.username
                FROM user_accounts ua
                WHERE ua.user_id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                print("User not found.")
                conn.close()
                return False
            
            username = user_data[0]
            
            # Check if the permission exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
            permission_data = cursor.fetchone()
            
            if not permission_data:
                print(f"Permission '{permission_name}' not found.")
                conn.close()
                return False
            
            permission_id = permission_data[0]
            
            # Delete the custom permission
            cursor.execute(
                'DELETE FROM user_permissions WHERE user_id = ? AND permission_id = ?',
                (user_id, permission_id)
            )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'Custom permission removed: {permission_name}',
                f'For user: {username}',
                self.current_user['id']
            )
            
            print(f"Custom permission '{permission_name}' has been removed from user {username}.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def create_role(self, role_name, description, permissions=None):
        """Create a new role with specified permissions"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to create roles.")
            return False
        
        if not role_name or not description:
            print("Role name and description are required.")
            return False
        
        if permissions and not isinstance(permissions, list):
            print("Permissions must be a list.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the role already exists
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            if cursor.fetchone():
                print(f"Role '{role_name}' already exists.")
                conn.close()
                return False
            
            # Create the role
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'INSERT INTO roles (role_name, description, created_at, updated_at) VALUES (?, ?, ?, ?)',
                (role_name, description, timestamp, timestamp)
            )
            
            role_id = cursor.lastrowid
            
            # Add permissions if provided
            if permissions:
                for perm in permissions:
                    # Check if permission exists
                    cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                    perm_data = cursor.fetchone()
                    
                    if perm_data:
                        perm_id = perm_data[0]
                        
                        # Associate permission with role
                        cursor.execute(
                            'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                            (role_id, perm_id)
                        )
                    else:
                        print(f"Warning: Permission '{perm}' does not exist and will be skipped.")
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'Role created: {role_name}',
                f'Permissions: {", ".join(permissions) if permissions else "None"}',
                self.current_user['id']
            )
            
            print(f"Role '{role_name}' created successfully.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def update_role(self, role_id, **kwargs):
        """Update a role's details"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to update roles.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the role exists
            cursor.execute('SELECT role_name FROM roles WHERE id = ?', (role_id,))
            role_data = cursor.fetchone()
            
            if not role_data:
                print("Role not found.")
                conn.close()
                return False
            
            role_name = role_data[0]
            
            # Don't allow updating default roles
            if role_name in ROLES:
                print(f"Cannot update default role '{role_name}'.")
                conn.close()
                return False
            
            # Check for uniqueness of role_name
            if 'role_name' in kwargs:
                cursor.execute('SELECT id FROM roles WHERE role_name = ? AND id != ?', (kwargs['role_name'], role_id))
                if cursor.fetchone():
                    print("Role name already exists.")
                    conn.close()
                    return False
            
            # Build the update query
            update_fields = []
            update_values = []
            
            for key, value in kwargs.items():
                if key not in ['id', 'created_at']:
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
            
            # Add updated_at timestamp
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Add role_id to values
            update_values.append(role_id)
            
            # Execute the update
            cursor.execute(
                f'UPDATE roles SET {", ".join(update_fields)} WHERE id = ?',
                update_values
            )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'Role updated: {role_name}',
                f'Fields updated: {", ".join(kwargs.keys())}',
                self.current_user['id']
            )
            
            print(f"Role '{role_name}' updated successfully.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def delete_role(self, role_id):
        """Delete a role"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to delete roles.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the role exists
            cursor.execute('SELECT role_name FROM roles WHERE id = ?', (role_id,))
            role_data = cursor.fetchone()
            
            if not role_data:
                print("Role not found.")
                conn.close()
                return False
            
            role_name = role_data[0]
            
            # Don't allow deleting default roles
            if role_name in ROLES:
                print(f"Cannot delete default role '{role_name}'.")
                conn.close()
                return False
            
            # Check if any users have this role
            cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', (role_name,))
            user_count = cursor.fetchone()[0]
            
            if user_count > 0:
                print(f"Cannot delete role '{role_name}' because it is assigned to {user_count} user(s).")
                conn.close()
                return False
            
            # Delete role permissions
            cursor.execute('DELETE FROM role_permissions WHERE role_id = ?', (role_id,))
            
            # Delete the role
            cursor.execute('DELETE FROM roles WHERE id = ?', (role_id,))
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'Role deleted: {role_name}',
                None,
                self.current_user['id']
            )
            
            print(f"Role '{role_name}' has been deleted.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def list_roles(self):
        """List all roles in the system"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to view roles.")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, role_name, description, created_at, updated_at
                FROM roles
                ORDER BY role_name
            ''')
            
            roles = [dict(row) for row in cursor.fetchall()]
            
            # For each role, get the permissions
            for role in roles:
                cursor.execute('''
                    SELECT p.permission_name
                    FROM permissions p
                    JOIN role_permissions rp ON p.id = rp.permission_id
                    WHERE rp.role_id = ?
                ''', (role['id'],))
                
                role['permissions'] = [row[0] for row in cursor.fetchall()]
                
                # Count users with this role
                cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', (role['role_name'],))
                role['user_count'] = cursor.fetchone()[0]
            
            conn.close()
            
            return roles
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
    
    def get_role(self, role_id=None, role_name=None):
        """Get information about a specific role"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to view role details.")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            if role_id is not None:
                cursor.execute('''
                    SELECT id, role_name, description, created_at, updated_at
                    FROM roles
                    WHERE id = ?
                ''', (role_id,))
            elif role_name is not None:
                cursor.execute('''
                    SELECT id, role_name, description, created_at, updated_at
                    FROM roles
                    WHERE role_name = ?
                ''', (role_name,))
            else:
                print("Either role_id or role_name must be provided.")
                conn.close()
                return None
            
            role = cursor.fetchone()
            
            if role:
                # Convert row to dictionary
                role_dict = dict(role)
                
                # Get role permissions
                cursor.execute('''
                    SELECT p.permission_name
                    FROM permissions p
                    JOIN role_permissions rp ON p.id = rp.permission_id
                    WHERE rp.role_id = ?
                ''', (role_dict['id'],))
                
                role_dict['permissions'] = [row[0] for row in cursor.fetchall()]
                
                # Count users with this role
                cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', (role_dict['role_name'],))
                role_dict['user_count'] = cursor.fetchone()[0]
                
                return role_dict
            else:
                print("Role not found.")
                return None
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def add_role_permission(self, role_id, permission_name):
        """Add a permission to a role"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to modify role permissions.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the role exists
            cursor.execute('SELECT role_name FROM roles WHERE id = ?', (role_id,))
            role_data = cursor.fetchone()
            
            if not role_data:
                print("Role not found.")
                conn.close()
                return False
            
            role_name = role_data[0]
            
            # Check if the permission exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
            permission_data = cursor.fetchone()
            
            if not permission_data:
                print(f"Permission '{permission_name}' not found.")
                conn.close()
                return False
            
            permission_id = permission_data[0]
            
            # Check if the role already has this permission
            cursor.execute(
                'SELECT id FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                (role_id, permission_id)
            )
            
            if cursor.fetchone():
                print(f"Role '{role_name}' already has permission '{permission_name}'.")
                conn.close()
                return True  # Not an error, just already exists
            
            # Add the permission to the role
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                (role_id, permission_id)
            )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'Permission added to role: {permission_name}',
                f'Role: {role_name}',
                self.current_user['id']
            )
            
            print(f"Permission '{permission_name}' added to role '{role_name}'.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def remove_role_permission(self, role_id, permission_name):
        """Remove a permission from a role"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to modify role permissions.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the role exists
            cursor.execute('SELECT role_name FROM roles WHERE id = ?', (role_id,))
            role_data = cursor.fetchone()
            
            if not role_data:
                print("Role not found.")
                conn.close()
                return False
            
            role_name = role_data[0]
            
            # Check if this is a default role
            if role_name in ROLES:
                print(f"Cannot modify permissions for default role '{role_name}'.")
                conn.close()
                return False
            
            # Check if the permission exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
            permission_data = cursor.fetchone()
            
            if not permission_data:
                print(f"Permission '{permission_name}' not found.")
                conn.close()
                return False
            
            permission_id = permission_data[0]
            
            # Check if the role has this permission
            cursor.execute(
                'SELECT id FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                (role_id, permission_id)
            )
            
            if not cursor.fetchone():
                print(f"Role '{role_name}' does not have permission '{permission_name}'.")
                conn.close()
                return False
            
            # Remove the permission from the role
            cursor.execute(
                'DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                (role_id, permission_id)
            )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'Permission removed from role: {permission_name}',
                f'Role: {role_name}',
                self.current_user['id']
            )
            
            print(f"Permission '{permission_name}' removed from role '{role_name}'.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def list_permissions(self):
        """List all permissions in the system"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to view permissions.")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, permission_name, description, created_at
                FROM permissions
                ORDER BY permission_name
            ''')
            
            permissions = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return permissions
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
    
    def create_permission(self, permission_name, description):
        """Create a new permission"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to create permissions.")
            return False
        
        if not permission_name or not description:
            print("Permission name and description are required.")
            return False
        
        # Validate permission name format (lowercase with underscores)
        if not re.match(r'^[a-z][a-z0-9_]*$', permission_name):            
            print("Invalid permission name. Must start with a letter and contain only lowercase letters, numbers, and underscores.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the permission already exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
            if cursor.fetchone():
                print(f"Permission '{permission_name}' already exists.")
                conn.close()
                return False
            
            # Create the permission
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                (permission_name, description, timestamp)
            )
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'Permission created: {permission_name}',
                None,
                self.current_user['id']
            )
            
            print(f"Permission '{permission_name}' created successfully.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def delete_permission(self, permission_id):
        """Delete a permission"""
        if not self.current_user or 'manage_roles' not in self.current_user['permissions']:
            print("You don't have permission to delete permissions.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the permission exists
            cursor.execute('SELECT permission_name FROM permissions WHERE id = ?', (permission_id,))
            permission_data = cursor.fetchone()
            
            if not permission_data:
                print("Permission not found.")
                conn.close()
                return False
            
            permission_name = permission_data[0]
            
            # Check if this is a built-in permission
            all_default_permissions = set()
            for perms in PERMISSIONS.values():
                all_default_permissions.update(perms)
            
            if permission_name in all_default_permissions:
                print(f"Cannot delete built-in permission '{permission_name}'.")
                conn.close()
                return False
            
            # Check if the permission is used in any roles
            cursor.execute('SELECT COUNT(*) FROM role_permissions WHERE permission_id = ?', (permission_id,))
            role_count = cursor.fetchone()[0]
            
            if role_count > 0:
                print(f"Cannot delete permission '{permission_name}' because it is used by {role_count} role(s).")
                conn.close()
                return False
            
            # Check if the permission is used in any user permissions
            cursor.execute('SELECT COUNT(*) FROM user_permissions WHERE permission_id = ?', (permission_id,))
            user_count = cursor.fetchone()[0]
            
            if user_count > 0:
                print(f"Cannot delete permission '{permission_name}' because it is used by {user_count} user(s).")
                conn.close()
                return False
            
            # Delete the permission
            cursor.execute('DELETE FROM permissions WHERE id = ?', (permission_id,))
            
            conn.commit()
            
            # Log the activity
            self._log_activity(
                self.current_user['username'],
                f'Permission deleted: {permission_name}',
                None,
                self.current_user['id']
            )
            
            print(f"Permission '{permission_name}' has been deleted.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
        finally:
            conn.close()

# Fix for user_authentication.py - display_chatbot_integration_menu function
# Replace the conversation history display section (around line 5498)

def display_chatbot_integration_menu(auth):
    """Display chatbot integration menu"""
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
            auth.launch_chatbot_interface()
        
        elif choice_num == 2:
            # View conversation history - FIXED VERSION
            try:
                history = auth.get_chatbot_conversation_history(user['username'])
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
                analytics = auth.generate_chatbot_analytics()
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
            print("\nTesting Chatbot Integration:")
            print("=" * 35)
            
            if CHATBOT_AVAILABLE:
                print("✅ Chatbot module available")
                
                if hasattr(auth, 'chatbot') and auth.chatbot:
                    print("✅ Chatbot instance created")
                    
                    try:
                        test_response = auth.chatbot.process_message("Hello", user['username'])
                        print(f"✅ Message processing works")
                        print(f"  Test response: {test_response[:80]}...")
                    except Exception as e:
                        print(f"❌ Message processing failed: {e}")
                    
                    print("✅ Integration test completed")
                else:
                    print("❌ Chatbot instance not found")
                    if auth.initialize_chatbot_integration():
                        print("✅ Chatbot initialized successfully")
                    else:
                        print("❌ Failed to initialize chatbot")
            else:
                print("⚠️ Chatbot in limited mode")
        
        elif choice_num == back_option:
            return
        
        else:
            print("Invalid choice. Please try again.")

def process_message(self, message, user_id, is_voice=False):
    """Process a basic message with conversation tracking"""
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
    from datetime import datetime
    
    # Initialize user history if not exists
    if user_id not in self.conversation_history:
        self.conversation_history[user_id] = []
    
    # Add this conversation
    self.conversation_history[user_id].append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'message': message,
        'response': response,
        'type': 'voice' if is_voice else 'text'
    })
    
    # Keep only last 50 conversations per user
    if len(self.conversation_history[user_id]) > 50:
        self.conversation_history[user_id] = self.conversation_history[user_id][-50:]

    # Also log to auth system if available
    if self.auth_system and hasattr(self.auth_system, '_log_activity'):
        try:
            self.auth_system._log_activity(
                user_id, 
                'Chatbot interaction',
                f"Q: {message[:50]}... A: {response[:50]}...",
                getattr(self.auth_system.current_user, 'id', None) if self.auth_system.current_user else None
            )
        except Exception:
            pass  # Don't break if logging fails
    
    return response
            
def test_chatbot_integration(auth):
    """Test chatbot integration functionality"""
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
        if auth.initialize_chatbot_integration():
            print("✓ Chatbot integration initialized successfully")
        else:
            print("✗ Failed to initialize chatbot integration")
            return
    
    # Test 3: Check permissions
    user = auth.current_user
    chatbot_perms = [p for p in user['permissions'] if 'chatbot' in p or p == 'voice_interaction']
    print(f"✓ User has {len(chatbot_perms)} chatbot permissions")
    
    # Test 4: Test session creation
    session_token = auth.create_chatbot_session(user['username'])
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

# Main menu functions
def display_auth_menu():
    """Enhanced authentication menu with chatbot integration"""
    auth = UserAuth()
    
    # Initialize chatbot integration
    if CHATBOT_AVAILABLE:
        auth.initialize_chatbot_integration()
        auth.setup_chatbot_permissions()
    
    while True:
        print("\nEnhanced University System:")
        print("==========================")
        
        if auth.current_user:
            # User is logged in
            user = auth.current_user
            print(f"Logged in as: {user['username']} (Role: {user['role']})")
            
            if user['password_reset_required']:
                # Handle password reset (existing code)
                print("\nYou must change your password before continuing.")
                current_password = input("Enter current password: ")
                
                while True:
                    new_password = input("Enter new password (min 8 chars, mix of letters & numbers): ")
                    confirm_password = input("Confirm new password: ")
                    
                    if new_password != confirm_password:
                        print("Passwords don't match. Try again.")
                        continue
                    
                    if auth.change_password(user['username'], current_password, new_password):
                        break
                    else:
                        retry = input("Do you want to try again? (y/n): ").lower()
                        if retry != 'y':
                            auth.logout()
                            break
                
                continue
            
            print("\n1. User Management")
            print("2. Role Management")
            print("3. My Account")
            if 'access_chatbot' in user['permissions']:
                print("4. University Chatbot")
            print("5. Logout")
            print("6. Return to Main Menu")
            
            max_choice = 6
            choice = input(f"\nEnter your choice (1-{max_choice}): ")
            
            if choice == '1':
                if 'manage_users' in user['permissions']:
                    display_user_management_menu(auth)
                else:
                    print("You don't have permission to access User Management.")
            elif choice == '2':
                if 'manage_roles' in user['permissions']:
                    display_role_management_menu(auth)
                else:
                    print("You don't have permission to access Role Management.")
            elif choice == '3':
                display_my_account_menu(auth)
            elif choice == '4' and 'access_chatbot' in user['permissions']:
                display_chatbot_integration_menu(auth)
            elif choice == '5':
                auth.logout()
            elif choice == '6':
                return auth
            else:
                print("Invalid choice. Please try again.")
                
        else:
            # User is not logged in (existing login code)
            print("Not logged in.")
            print("\n1. Login")
            print("2. Return to Main Menu")
            
            choice = input("\nEnter your choice (1-2): ")
            
            if choice == '1':
                # Login process (existing code)
                username = input("Username: ")
                password = input("Password: ")
                
                result = auth.login(username, password)
                
                if isinstance(result, dict) and result.get('requires_2fa'):
                    # 2FA handling (existing code)
                    print("\n2-Factor Authentication required.")
                    print("Enter your 6-digit verification code from your authenticator app,")
                    print("or use a recovery code.")
                    
                    max_attempts = 3
                    attempts = 0
                    
                    while attempts < max_attempts:
                        code = input("\nEnter verification code: ")
                        code = code.replace('-', '')
                        
                        if auth.complete_two_fa_login(result['user_id'], result['username'], code):
                            break
                        else:
                            attempts += 1
                            remaining = max_attempts - attempts
                            if remaining > 0:
                                print(f"Invalid code. {remaining} attempts remaining.")
                            else:
                                print("Too many failed attempts. Please try logging in again.")
                                break
                
                elif result == 'password_reset_required':
                    continue
                elif not result:
                    retry = input("Do you want to try again? (y/n): ").lower()
                    if retry != 'y':
                        break
            elif choice == '2':
                return None
            else:
                print("Invalid choice. Please try again.")
    
    return auth

def display_user_management_menu(auth):
    """Display the user management menu with enhanced debugging"""
    while True:
        if not auth.check_session() or not auth.check_permission('manage_users'):
            print("You don't have permission to access User Management.")
            return
        
        print("\nUser Management:")
        print("================")
        print("1. List All Users")
        print("2. Create New User")
        print("3. View User Details")
        print("4. Edit User")
        print("5. Reset User Password")
        print("6. Deactivate/Activate User")
        print("7. Delete User")
        print("8. Manage User Permissions")
        print("9. Fix Database Consistency Issues")  # New option
        print("10. Debug User Database")  # New option
        print("11. Back")
        
        choice = input("\nEnter your choice (1-11): ")
        
        if choice == '1':
            # List all users with enhanced information
            users = auth.list_users()
            
            if users:
                print("\nAll Users:")
                print("=" * 100)
                print(f"{'ID':<5} {'Username':<15} {'Name':<25} {'Role':<10} {'Status':<10} {'2FA':<5} {'Last Login':<20}")
                print("-" * 100)
                
                for user in users:
                    full_name = f"{user['first_name']} {user['last_name']}"
                    status = "Active" if user['is_active'] else "Inactive"
                    two_fa = "Yes" if user['two_fa_enabled'] else "No"
                    last_login = user['last_login'] if user['last_login'] else "Never"
                    
                    print(f"{user['id']:<5} {user['username']:<15} {full_name:<25} {user['role']:<10} {status:<10} {two_fa:<5} {last_login:<20}")
                
                print("=" * 100)
        
        elif choice == '2':
            # Create new user
            print("\nCreate New User:")
            username = input("Username: ")
            
            # Check if username is valid
            if not auth._validate_username(username):
                print("Invalid username format. Username must be 3-20 characters and contain only letters, numbers, underscores, or hyphens.")
                continue
            
            # Check if user exists
            conn = sqlite3.connect(auth.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM user_accounts WHERE username = ?', (username,))
            if cursor.fetchone():
                print("Username already exists.")
                conn.close()
                continue
            conn.close()
            
            email = input("Email: ")
            first_name = input("First Name: ")
            last_name = input("Last Name: ")
            
            # Get available roles
            conn = sqlite3.connect(auth.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT role_name FROM roles')
            available_roles = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            print("\nAvailable Roles:")
            for i, role in enumerate(available_roles, 1):
                print(f"{i}. {role}")
            
            while True:
                role_choice = input("Select role (enter number): ")
                try:
                    role_index = int(role_choice) - 1
                    if 0 <= role_index < len(available_roles):
                        role = available_roles[role_index]
                        break
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Please enter a number.")
            
            # If role is student, ask for student_id
            student_id = None
            if role == 'student':
                student_id = input("Student ID (must be an existing student ID): ")
            
            # Generate a random initial password
            import random
            import string
            temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            
            # Create the user
            if auth.create_user(username, temp_password, email, first_name, last_name, role, student_id, True):
                print(f"\nUser created successfully with temporary password: {temp_password}")
                print("User will be required to change password on first login.")
        
        elif choice == '3':
            # View user details with better input handling
            user_input = input("Enter user ID or username to view: ")
            
            user = None
            
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)
            
            if user:
                print("\nUser Details:")
                print("=" * 60)
                print(f"ID: {user['id']}")
                print(f"Username: {user['username']}")
                print(f"Email: {user['email']}")
                print(f"Name: {user['first_name']} {user['last_name']}")
                print(f"Role: {user['role']}")
                print(f"Active: {'Yes' if user['is_active'] else 'No'}")
                print(f"2FA Enabled: {'Yes' if user['two_fa_enabled'] else 'No'}")
                print(f"Student ID: {user['student_id'] or 'N/A'}")
                print(f"Last Login: {user['last_login'] or 'Never'}")
                print(f"Created: {user['created_at']}")
                print(f"Updated: {user['updated_at']}")
                
                print("\nPermissions:")
                for perm in user['permissions']:
                    print(f"- {perm}")
                
                print("=" * 60)
        
        elif choice == '4':
            # Edit User
            user_input = input("Enter user ID or username to edit: ")
            
            user = None
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)
            
            if user:
                print(f"\nEdit User: {user['username']}")
                print("=" * 40)
                print(f"Current Username: {user['username']}")
                print(f"Current Email: {user['email']}")
                print(f"Current First Name: {user['first_name']}")
                print(f"Current Last Name: {user['last_name']}")
                print(f"Current Role: {user['role']}")
                print(f"Current Student ID: {user['student_id'] or 'N/A'}")
                
                print("\nEnter new values (leave blank to keep current):")
                new_username = input("New Username: ")
                new_email = input("New Email: ")
                new_first_name = input("New First Name: ")
                new_last_name = input("New Last Name: ")
                
                # Role selection
                conn = sqlite3.connect(auth.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT role_name FROM roles')
                available_roles = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                print(f"\nCurrent Role: {user['role']}")
                print("Available Roles:")
                for i, role in enumerate(available_roles, 1):
                    print(f"{i}. {role}")
                
                role_choice = input("Select new role (enter number, or leave blank to keep current): ")
                new_role = None
                if role_choice:
                    try:
                        role_index = int(role_choice) - 1
                        if 0 <= role_index < len(available_roles):
                            new_role = available_roles[role_index]
                        else:
                            print("Invalid choice, keeping current role.")
                    except ValueError:
                        print("Invalid input, keeping current role.")
                
                new_student_id = input("New Student ID (leave blank to keep current): ")
                
                # Build update dictionary
                updates = {}
                if new_username:
                    updates['username'] = new_username
                if new_email:
                    updates['email'] = new_email
                if new_first_name:
                    updates['first_name'] = new_first_name
                if new_last_name:
                    updates['last_name'] = new_last_name
                if new_role:
                    updates['role'] = new_role
                if new_student_id:
                    updates['student_id'] = new_student_id
                
                if updates:
                    if auth.update_user(user['id'], **updates):
                        print("User updated successfully.")
                    else:
                        print("Failed to update user.")
                else:
                    print("No changes made.")
            else:
                print("User not found.")
        
        elif choice == '5':
            # Reset User Password
            user_input = input("Enter username to reset password: ")
            
            # Verify user exists
            user = auth.get_user(username=user_input)
            if user:
                confirm = input(f"Are you sure you want to reset password for '{user_input}'? (y/n): ").lower()
                if confirm == 'y':
                    if auth.reset_password(user_input, auth.current_user['id']):
                        print("Password reset successfully. User will receive a temporary password.")
                    else:
                        print("Failed to reset password.")
            else:
                print("User not found.")
        
        elif choice == '6':
            # Deactivate/Activate User
            user_input = input("Enter user ID or username to activate/deactivate: ")
            
            user = None
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)
            
            if user:
                current_status = "Active" if user['is_active'] else "Inactive"
                print(f"\nUser: {user['username']}")
                print(f"Current Status: {current_status}")
                
                if user['is_active']:
                    # User is active, offer to deactivate
                    confirm = input("Do you want to deactivate this user? (y/n): ").lower()
                    if confirm == 'y':
                        if auth.deactivate_user(user['id']):
                            print("User deactivated successfully.")
                        else:
                            print("Failed to deactivate user.")
                else:
                    # User is inactive, offer to activate
                    confirm = input("Do you want to activate this user? (y/n): ").lower()
                    if confirm == 'y':
                        if auth.activate_user(user['id']):
                            print("User activated successfully.")
                        else:
                            print("Failed to activate user.")
            else:
                print("User not found.")
        
        elif choice == '7':
            # Delete User
            user_input = input("Enter user ID or username to delete: ")
            
            user = None
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)
            
            if user:
                print(f"\nUser to delete: {user['username']}")
                print(f"Name: {user['first_name']} {user['last_name']}")
                print(f"Role: {user['role']}")
                print(f"Email: {user['email']}")
                
                # Confirm deletion
                confirm1 = input("\nAre you sure you want to delete this user? This action cannot be undone. (y/n): ").lower()
                if confirm1 == 'y':
                    confirm2 = input("Type 'DELETE' to confirm: ")
                    if confirm2 == 'DELETE':
                        if auth.delete_user(user['id']):
                            print("User deleted successfully.")
                        else:
                            print("Failed to delete user.")
                    else:
                        print("Deletion cancelled.")
                else:
                    print("Deletion cancelled.")
            else:
                print("User not found.")
        
        elif choice == '8':
            # Manage User Permissions
            user_input = input("Enter user ID or username to manage permissions: ")
            
            user = None
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)
            
            if user:
                while True:
                    print(f"\nManage Permissions for: {user['username']}")
                    print("=" * 50)
                    
                    # Get all permissions
                    conn = sqlite3.connect(auth.db_path)
                    cursor = conn.cursor()
                    cursor.execute('SELECT permission_name, description FROM permissions ORDER BY permission_name')
                    all_permissions = cursor.fetchall()
                    conn.close()
                    
                    # Get user's current permissions
                    user_permissions = user['permissions']
                    
                    print(f"Role: {user['role']}")
                    print("Current Permissions:")
                    
                    for i, (perm_name, perm_desc) in enumerate(all_permissions, 1):
                        status = "✓" if perm_name in user_permissions else " "
                        print(f"{i:2}. [{status}] {perm_name} - {perm_desc}")
                    
                    print("\nOptions:")
                    print("1. Grant Permission")
                    print("2. Revoke Permission")
                    print("3. Remove Custom Permission (revert to role default)")
                    print("4. Back")
                    
                    perm_choice = input("\nEnter choice (1-4): ")
                    
                    if perm_choice == '1':
                        # Grant permission
                        perm_number = input("Enter permission number to grant: ")
                        try:
                            perm_index = int(perm_number) - 1
                            if 0 <= perm_index < len(all_permissions):
                                perm_name = all_permissions[perm_index][0]
                                if auth.set_user_permission(user['id'], perm_name, True):
                                    # Refresh user data
                                    user = auth.get_user(user_id=user['id'])
                                    print(f"Permission '{perm_name}' granted successfully.")
                                else:
                                    print("Failed to grant permission.")
                            else:
                                print("Invalid permission number.")
                        except ValueError:
                            print("Please enter a number.")
                    
                    elif perm_choice == '2':
                        # Revoke permission
                        perm_number = input("Enter permission number to revoke: ")
                        try:
                            perm_index = int(perm_number) - 1
                            if 0 <= perm_index < len(all_permissions):
                                perm_name = all_permissions[perm_index][0]
                                if auth.set_user_permission(user['id'], perm_name, False):
                                    # Refresh user data
                                    user = auth.get_user(user_id=user['id'])
                                    print(f"Permission '{perm_name}' revoked successfully.")
                                else:
                                    print("Failed to revoke permission.")
                            else:
                                print("Invalid permission number.")
                        except ValueError:
                            print("Please enter a number.")
                    
                    elif perm_choice == '3':
                        # Remove custom permission
                        perm_number = input("Enter permission number to reset to role default: ")
                        try:
                            perm_index = int(perm_number) - 1
                            if 0 <= perm_index < len(all_permissions):
                                perm_name = all_permissions[perm_index][0]
                                if auth.remove_user_permission(user['id'], perm_name):
                                    # Refresh user data
                                    user = auth.get_user(user_id=user['id'])
                                    print(f"Custom permission '{perm_name}' removed. User now has role default.")
                                else:
                                    print("Failed to remove custom permission.")
                            else:
                                print("Invalid permission number.")
                        except ValueError:
                            print("Please enter a number.")
                    
                    elif perm_choice == '4':
                        break
                    else:
                        print("Invalid choice.")
            else:
                print("User not found.")
        
        elif choice == '9':
            # Fix database consistency issues
            print("\nFix Database Consistency Issues:")
            print("This will attempt to fix orphaned records between users and user_accounts tables.")
            confirm = input("Do you want to proceed? (y/n): ").lower()
            
            if confirm == 'y':
                auth.fix_database_consistency()
        
        elif choice == '10':
            # Debug user database
            print("\nDatabase Debug Information:")
            print("=" * 60)
            
            try:
                conn = sqlite3.connect(auth.db_path)
                cursor = conn.cursor()
                
                # Count records in each table
                cursor.execute('SELECT COUNT(*) FROM users')
                user_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM user_accounts')
                account_count = cursor.fetchone()[0]
                
                print(f"Total users in 'users' table: {user_count}")
                print(f"Total accounts in 'user_accounts' table: {account_count}")
                
                # Check for mismatches
                cursor.execute('''
                    SELECT COUNT(*) FROM users u
                    LEFT JOIN user_accounts ua ON u.id = ua.user_id
                    WHERE ua.user_id IS NULL
                ''')
                orphaned_users = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*) FROM user_accounts ua
                    LEFT JOIN users u ON ua.user_id = u.id
                    WHERE u.id IS NULL
                ''')
                orphaned_accounts = cursor.fetchone()[0]
                
                print(f"Users without accounts: {orphaned_users}")
                print(f"Accounts without users: {orphaned_accounts}")
                
                if orphaned_users > 0 or orphaned_accounts > 0:
                    print("\nWarning: Database inconsistencies detected!")
                    print("Use option 9 to fix these issues.")
                else:
                    print("\nDatabase consistency: OK")
                
                # Show table schemas
                print("\nUsers table schema:")
                cursor.execute("PRAGMA table_info(users)")
                for column in cursor.fetchall():
                    print(f"  {column[1]} ({column[2]})")
                
                print("\nUser_accounts table schema:")
                cursor.execute("PRAGMA table_info(user_accounts)")
                for column in cursor.fetchall():
                    print(f"  {column[1]} ({column[2]})")
                
                conn.close()
                
            except sqlite3.Error as e:
                logger.error(f"Database error: {e}")
            
            print("=" * 60)
        
        elif choice == '11':
            return
        
        else:
            print("Invalid choice. Please try again.")

def display_role_management_menu(auth):
    """Display the role management menu"""
    while True:
        if not auth.check_session() or not auth.check_permission('manage_roles'):
            print("You don't have permission to access Role Management.")
            return
        
        print("\nRole Management:")
        print("===============")
        print("1. List All Roles")
        print("2. Create New Role")
        print("3. View Role Details")
        print("4. Edit Role")
        print("5. Delete Role")
        print("6. Manage Role Permissions")
        print("7. List All Permissions")
        print("8. Create New Permission")
        print("9. Back")
        
        choice = input("\nEnter your choice (1-9): ")
        
        if choice == '1':
            # List all roles
            roles = auth.list_roles()
            
            if roles:
                print("\nAll Roles:")
                print("=" * 70)
                print(f"{'ID':<5} {'Role Name':<15} {'Description':<30} {'Users':<10}")
                print("-" * 70)
                
                for role in roles:
                    print(f"{role['id']:<5} {role['role_name']:<15} {role['description'][:28]:<30} {role['user_count']:<10}")
                
                print("=" * 70)
            
        elif choice == '2':
            # Create new role
            print("\nCreate New Role:")
            role_name = input("Role Name: ")
            description = input("Description: ")
            
            # Get permissions
            conn = sqlite3.connect(auth.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, permission_name, description FROM permissions ORDER BY permission_name')
            all_permissions = cursor.fetchall()
            conn.close()
            
            if all_permissions:
                print("\nSelect permissions (comma-separated numbers, blank for none):")
                for i, perm in enumerate(all_permissions, 1):
                    perm_id, perm_name, perm_desc = perm
                    print(f"{i}. {perm_name} - {perm_desc}")
                
                perm_choices = input("\nPermissions: ")
                
                selected_permissions = []
                if perm_choices:
                    try:
                        indices = [int(idx.strip()) - 1 for idx in perm_choices.split(',')]
                        selected_permissions = [all_permissions[idx][1] for idx in indices if 0 <= idx < len(all_permissions)]
                    except ValueError:
                        print("Invalid input. No permissions will be added.")
                
                auth.create_role(role_name, description, selected_permissions)
            else:
                auth.create_role(role_name, description)
            
        elif choice == '3':
            # View role details
            role_id = input("Enter role ID to view: ")
            
            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)
                
                if role:
                    print("\nRole Details:")
                    print("=" * 60)
                    print(f"ID: {role['id']}")
                    print(f"Name: {role['role_name']}")
                    print(f"Description: {role['description']}")
                    print(f"Created: {role['created_at']}")
                    print(f"Updated: {role['updated_at']}")
                    print(f"Users with this role: {role['user_count']}")
                    
                    print("\nPermissions:")
                    for perm in role['permissions']:
                        print(f"- {perm}")
                    
                    print("=" * 60)
                
            except ValueError:
                print("Invalid role ID. Please enter a number.")
            
        elif choice == '4':
            # Edit role
            role_id = input("Enter role ID to edit: ")
            
            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)
                
                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot edit default role '{role['role_name']}'.")
                        continue
                    
                    print("\nEdit Role:")
                    print(f"Current Name: {role['role_name']}")
                    print(f"Current Description: {role['description']}")
                    
                    print("\nEnter new values (leave blank to keep current):")
                    new_name = input("New Name: ")
                    new_description = input("New Description: ")
                    
                    # Build update dictionary
                    updates = {}
                    if new_name:
                        updates['role_name'] = new_name
                    if new_description:
                        updates['description'] = new_description
                    
                    if updates:
                        auth.update_role(role_id, **updates)
                    else:
                        print("No changes made.")
                
            except ValueError:
                print("Invalid role ID. Please enter a number.")
            
        elif choice == '5':
            # Delete role
            role_id = input("Enter role ID to delete: ")
            
            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)
                
                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot delete default role '{role['role_name']}'.")
                        continue
                    
                    # Check if any users have this role
                    if role['user_count'] > 0:
                        print(f"Cannot delete role '{role['role_name']}' because it is assigned to {role['user_count']} user(s).")
                        continue
                    
                    # Confirm deletion
                    confirm = input(f"Are you sure you want to delete role '{role['role_name']}'? (y/n): ").lower()
                    
                    if confirm == 'y':
                        auth.delete_role(role_id)
                
            except ValueError:
                print("Invalid role ID. Please enter a number.")
            
        elif choice == '6':
            # Manage role permissions
            role_id = input("Enter role ID to manage permissions: ")
            
            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)
                
                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot modify permissions for default role '{role['role_name']}'.")
                        continue
                    
                    while True:
                        print(f"\nPermissions for role '{role['role_name']}':")
                        print("=" * 60)
                        
                        # Get all permissions
                        conn = sqlite3.connect(auth.db_path)
                        cursor = conn.cursor()
                        cursor.execute('SELECT permission_name FROM permissions ORDER BY permission_name')
                        all_permissions = [row[0] for row in cursor.fetchall()]
                        conn.close()
                        
                        # Check which permissions the role has
                        role_permissions = role['permissions']
                        
                        for i, perm in enumerate(all_permissions, 1):
                            status = "✓" if perm in role_permissions else " "
                            print(f"{i:2}. [{status}] {perm}")
                        
                        print("\n1. Add permission")
                        print("2. Remove permission")
                        print("3. Back")
                        
                        perm_choice = input("\nEnter choice (1-3): ")
                        
                        if perm_choice == '1':
                            # Add permission
                            perm_number = input("Enter permission number to add: ")
                            
                            try:
                                perm_index = int(perm_number) - 1
                                if 0 <= perm_index < len(all_permissions):
                                    perm_name = all_permissions[perm_index]
                                    auth.add_role_permission(role_id, perm_name)
                                    # Refresh role data
                                    role = auth.get_role(role_id=role_id)
                                else:
                                    print("Invalid permission number.")
                            except ValueError:
                                print("Please enter a number.")
                                
                        elif perm_choice == '2':
                            # Remove permission
                            perm_number = input("Enter permission number to remove: ")
                            
                            try:
                                perm_index = int(perm_number) - 1
                                if 0 <= perm_index < len(all_permissions):
                                    perm_name = all_permissions[perm_index]
                                    auth.remove_role_permission(role_id, perm_name)
                                    # Refresh role data
                                    role = auth.get_role(role_id=role_id)
                                else:
                                    print("Invalid permission number.")
                            except ValueError:
                                print("Please enter a number.")
                                
                        elif perm_choice == '3':
                            break
                        else:
                            print("Invalid choice.")
                
            except ValueError:
                print("Invalid role ID. Please enter a number.")
            
        elif choice == '7':
            # List all permissions
            permissions = auth.list_permissions()
            
            if permissions:
                print("\nAll Permissions:")
                print("=" * 80)
                print(f"{'ID':<5} {'Permission Name':<30} {'Description':<45}")
                print("-" * 80)
                
                for perm in permissions:
                    print(f"{perm['id']:<5} {perm['permission_name']:<30} {perm['description'][:43]:<45}")
                
                print("=" * 80)
            
        elif choice == '8':
            # Create new permission
            print("\nCreate New Permission:")
            print("Note: Permission names should be lowercase with underscores (e.g., view_reports)")
            permission_name = input("Permission Name: ")
            description = input("Description: ")
            
            auth.create_permission(permission_name, description)
            
        elif choice == '9':
            return
        else:
            print("Invalid choice. Please try again.")

def display_my_account_menu(auth):
    """Display the my account menu"""
    while True:
        if not auth.check_session():
            return
        
        user = auth.current_user
        
        print("\nMy Account:")
        print("===========")
        print(f"Username: {user['username']}")
        print(f"Role: {user['role']}")
        
        print("\n1. Change Password")
        print("2. View My Permissions")
        print("3. 2-Factor Authentication Settings")
        print("4. Back")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == '1':
            # Change password
            print("\nChange Password:")
            current_password = input("Current Password: ")
            new_password = input("New Password (min 8 chars, mix of letters & numbers): ")
            confirm_password = input("Confirm New Password: ")
            
            if new_password != confirm_password:
                print("Passwords don't match.")
                continue
            
            auth.change_password(user['username'], current_password, new_password)
            
        elif choice == '2':
            # View permissions
            print("\nMy Permissions:")
            print("=" * 60)
            
            for perm in user['permissions']:
                print(f"- {perm}")
            
            print("=" * 60)
            
        elif choice == '3':
            # 2FA settings
            user_details = auth.get_user(username=user['username'])
            
            print("\n2-Factor Authentication Settings:")
            print("=================================")
            print(f"2FA Status: {'Enabled' if user_details['two_fa_enabled'] else 'Disabled'}")
            
            if user_details['two_fa_enabled']:
                print("\n1. Disable 2FA")
                print("2. Regenerate Recovery Codes")
                print("3. Back")
                
                twofa_choice = input("\nEnter your choice (1-3): ")
                
                if twofa_choice == '1':
                    # Disable 2FA
                    confirm = input("Are you sure you want to disable 2FA? (y/n): ").lower()
                    if confirm == 'y':
                        result = auth.disable_two_fa(user['id'])
                        if result['success']:
                            print(result['message'])
                        else:
                            print(f"Error: {result['message']}")
                            
                elif twofa_choice == '2':
                    # Regenerate recovery codes
                    confirm = input("Are you sure you want to regenerate recovery codes? Old codes will become invalid. (y/n): ").lower()
                    if confirm == 'y':
                        result = auth.regenerate_recovery_codes(user['id'])
                        if result['success']:
                            print(result['message'])
                            print("\nNew Recovery Codes (save these in a secure place):")
                            for code in result['recovery_codes']:
                                print(code)
                        else:
                            print(f"Error: {result['message']}")
                            
                elif twofa_choice == '3':
                    continue
                else:
                    print("Invalid choice.")
            else:
                print("\n1. Enable 2FA")
                print("2. Back")
                
                twofa_choice = input("\nEnter your choice (1-2): ")
                
                if twofa_choice == '1':
                    # Enable 2FA
                    result = auth.enable_two_fa(user['id'])
                    if result['success']:
                        print(result['message'])
                        print("\nScan this QR code with your authenticator app:")
                        print("(In a real application, this would display the QR code)")
                        print(f"Base64 QR Code: {result['qr_code'][:50]}...")
                        print(f"\nOr manually enter this secret: {result['secret']}")
                        print("\nRecovery Codes (save these in a secure place):")
                        for code in result['recovery_codes']:
                            print(code)
                    else:
                        print(f"Error: {result['message']}")
                        
                elif twofa_choice == '2':
                    continue
                else:
                    print("Invalid choice.")
            
        elif choice == '4':
            return
        else:
            print("Invalid choice. Please try again.")

def test_authentication_fix():
    """Run diagnostics against authentication data without seeding demo users."""
    print("=== AUTHENTICATION DATA CHECK ===")

    auth = UserAuth()

    # Summarise role coverage
    auth.verify_default_accounts()
    auth.ensure_staff_account_exists()

    # Inspect for orphaned records and locked accounts
    with auth.db_manager.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            WHERE ua.user_id IS NULL
            '''
        )
        orphan_count = cursor.fetchone()[0]
        if orphan_count:
            print(f"⚠️  {orphan_count} user record(s) do not have login accounts. Call fix_missing_accounts() if appropriate.")
        else:
            print("✓ All user records have corresponding login accounts.")

        cursor.execute("SELECT COUNT(*) FROM user_accounts WHERE is_active = 0")
        locked_accounts = cursor.fetchone()[0]
        if locked_accounts:
            print(f"⚠️  {locked_accounts} account(s) are marked inactive.")
        else:
            print("✓ No inactive accounts detected.")

def test_authentication_with_ai_detector():
    """Summarise AI detector permissions without relying on seeded accounts."""
    print("=== TESTING AI DETECTOR PERMISSIONS ===")

    try:
        auth = UserAuth()

        ai_permissions = [
            'access_ai_detector',
            'analyze_submissions',
            'view_own_ai_results',
            'view_any_ai_results',
            'manage_ai_whitelist',
            'configure_ai_detector',
            'view_ai_statistics',
        ]

        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT permission_name
                FROM permissions
                WHERE permission_name IN ({})
                '''.format(','.join('?' for _ in ai_permissions)),
                ai_permissions,
            )
            present_perms = {row[0] for row in cursor.fetchall()}
            missing_perms = sorted(set(ai_permissions) - present_perms)

            if missing_perms:
                print(f"❌ Missing AI detector permissions: {', '.join(missing_perms)}")
            else:
                print("✓ All AI detector permissions are registered.")

            cursor.execute(
                '''
                SELECT DISTINCT u.username, u.role
                FROM user_accounts ua
                JOIN users u ON ua.user_id = u.id
                JOIN roles r ON r.role_name = u.role
                JOIN role_permissions rp ON rp.role_id = r.id
                JOIN permissions p ON p.id = rp.permission_id
                WHERE p.permission_name IN ({})
                ORDER BY u.role, u.username
                '''.format(','.join('?' for _ in ai_permissions)),
                ai_permissions,
            )
            rows = cursor.fetchall()

            if rows:
                print("\nUsers currently mapped to AI detector permissions:")
                for username, role in rows:
                    print(f"• {username} ({role})")
            else:
                print("\n⚠️  No user accounts are currently mapped to AI detector permissions.")

            cursor.execute(
                '''
                SELECT r.role_name, COUNT(DISTINCT ua.id) AS account_count
                FROM roles r
                LEFT JOIN users u ON u.role = r.role_name
                LEFT JOIN user_accounts ua ON ua.user_id = u.id
                GROUP BY r.role_name
                ORDER BY r.role_name
                '''
            )
            print("\nRole coverage summary:")
            for role_name, account_count in cursor.fetchall():
                print(f"• {role_name}: {account_count} account(s)")

        print("\n✓ AI detector authentication metadata check completed.")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        traceback.print_exc()

def test_plagiarism_authentication():
    """Summarise plagiarism checker permissions without demo accounts."""
    print("Testing plagiarism checker authentication...")

    auth = UserAuth()

    plagiarism_permissions = [
        'check_plagiarism',
        'manage_plagiarism_system',
        'submit_document',
        'check_plagiarism_any_course',
        'access_plagiarism_menu',
    ]

    with auth.db_manager.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT permission_name
            FROM permissions
            WHERE permission_name IN ({})
            '''.format(','.join('?' for _ in plagiarism_permissions)),
            plagiarism_permissions,
        )
        present = {row[0] for row in cursor.fetchall()}
        missing = sorted(set(plagiarism_permissions) - present)
        if missing:
            print(f"❌ Missing plagiarism permissions: {', '.join(missing)}")
        else:
            print("✓ All plagiarism permissions are registered.")

        cursor.execute(
            '''
            SELECT DISTINCT u.username, u.role
            FROM user_accounts ua
            JOIN users u ON ua.user_id = u.id
            JOIN roles r ON r.role_name = u.role
            JOIN role_permissions rp ON rp.role_id = r.id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE p.permission_name IN ({})
            ORDER BY u.role, u.username
            '''.format(','.join('?' for _ in plagiarism_permissions)),
            plagiarism_permissions,
        )
        mapped_users = cursor.fetchall()

        if mapped_users:
            print("\nUsers with plagiarism permissions:")
            for username, role in mapped_users:
                print(f"• {username} ({role})")
        else:
            print("\n⚠️  No user accounts currently map to plagiarism permissions.")

    print("\nPlagiarism authentication permission check completed!")

def fix_library_permissions():
    """Fix library permissions for existing database"""
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # All library-related permissions that should exist
    all_library_permissions = [
        ('view_books', 'View Books'),
        ('manage_books', 'Manage Books'),
        ('manage_loans', 'Manage Loans'),
        ('checkout_books', 'Checkout Books'),
        ('view_loans', 'View Loans'),
        ('view_reports', 'View Reports'),
        ('generate_reports', 'Generate Reports'),
        ('system_config', 'System Config')
    ]
    
    # Create any missing permissions
    for perm_name, perm_desc in all_library_permissions:
        cursor.execute(
            'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
            (perm_name, perm_desc, timestamp)
        )
    
    conn.commit()
    print("Created missing library permissions")
    
    # Now assign them to the admin role
    cursor.execute('SELECT id FROM roles WHERE role_name = ?', ('admin',))
    admin_role = cursor.fetchone()
    
    if admin_role:
        admin_role_id = admin_role[0]
        
        for perm_name, _ in all_library_permissions:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            perm = cursor.fetchone()
            
            if perm:
                perm_id = perm[0]
                cursor.execute(
                    'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                    (admin_role_id, perm_id)
                )
        
        conn.commit()
        print("Assigned library permissions to admin role")
    
    # Also assign appropriate permissions to other roles
    role_permissions = {
        'staff': ['view_books', 'checkout_books', 'view_loans', 'view_reports', 'generate_reports'],
        'student': ['view_books', 'checkout_books', 'view_loans'],
        'instructor': ['view_books']
    }
    
    for role_name, permissions in role_permissions.items():
        cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
        role = cursor.fetchone()
        
        if role:
            role_id = role[0]
            
            for perm_name in permissions:
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                perm = cursor.fetchone()
                
                if perm:
                    perm_id = perm[0]
                    cursor.execute(
                        'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                        (role_id, perm_id)
                    )
            
            print(f"Assigned library permissions to {role_name} role")
    
    conn.commit()
    conn.close()
    print("\nLibrary permissions have been fixed!")
    print("Please restart your application and try logging in as admin again.")

def simple_login_test(username=None, password=None):
    """Simple inspection helper for account hashes.

    If *username* and *password* are provided the stored hash for that user
    is compared against the supplied password.  Otherwise the function just
    lists accounts found in the database.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=== SIMPLE LOGIN TEST ===")
    
    # Check what's in user_accounts
    cursor.execute("SELECT username, password_hash, salt FROM user_accounts")
    accounts = cursor.fetchall()
    
    print("\nAccounts found:")
    for username, pw_hash, salt in accounts:
        print(f"  Username: {username}")
        print(f"  Password hash: {pw_hash[:50]}...")
        print(f"  Salt: {salt}")
        print()
    
    if username and password:
        import hashlib

        cursor.execute("SELECT salt, password_hash FROM user_accounts WHERE username = ?", (username,))
        result = cursor.fetchone()

        if result:
            salt, stored_hash = result
            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt.encode(),
                1_000_000,  # Must match the hashing function (1 million iterations)
                dklen=64,
            )
            computed_hash = key.hex()

            print(f"\nStored hash:   {stored_hash[:50]}...")
            print(f"Computed hash: {computed_hash[:50]}...")

            if computed_hash == stored_hash:
                print("✓ Password verification successful!")
            else:
                print("✗ Password verification failed!")
        else:
            print(f"No account found for username '{username}'.")
    else:
        print("Provide username and password parameters to verify credentials.")
    
    conn.close()

def test_trip_integration():
    """Test trip management integration"""
    print("Testing trip management integration...")
    
    try:
        # Test database initialization
        if init_trip_db():
            print("✓ Trip database initialized")
        else:
            print("✗ Trip database initialization failed")
            return False
        
        # Test permission setup
        if setup_trip_permissions():
            print("✓ Trip permissions setup completed")
        else:
            print("✗ Trip permissions setup failed")
            return False
        
        # Test auth integration
        if auth:
            set_trip_auth(auth)
            print("✓ Trip auth integration completed")
        
        print("✓ Trip management integration test passed!")
        return True
        
    except Exception as e:
        print(f"✗ Trip integration test failed: {e}")
        logging.error(f"Trip integration test error: {e}")
        return False

def _create_emergency_chatbot(self):
    """Create emergency chatbot when all else fails"""
    class EmergencyChatbot:
        def __init__(self):
            self.app = None
            self.config = {}
            self.conversation_history = {}
            self.auth_system = None
            self.enabled = False
        
        def set_auth_system(self, auth): 
            self.auth_system = auth
        
        def process_message(self, msg, user, session_id=None, voice=False):
            return "Chatbot temporarily unavailable."
        
        def run_authenticated_console_interface(self):
            print("Chatbot is currently unavailable.")
        
        def get_conversation_history(self, user, limit=10):
            return []
        
        def run(self):
            """Run emergency chatbot in console mode"""
            print("Emergency Chatbot - Limited Functionality")
            self.run_console_interface()

        def run_console_interface(self):
            """Emergency console interface"""
            print("Emergency chatbot console. Type 'exit' to quit.")
            while True:
                try:
                    user_input = input("You: ")
                    if user_input.lower() in ['exit', 'quit']:
                        break
                    print("Bot: System is in emergency mode. Limited functionality available.")
                except (KeyboardInterrupt, EOFError):
                    break

        def run_web_server(self, host=None, port=None):
            """Emergency web server not available"""
            print("Web server not available in emergency mode.")
            return False
    
    self.chatbot = EmergencyChatbot()
    print("✅ Emergency chatbot fallback created")

    def get_chatbot_conversation_history(self, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chatbot conversation history for a user - FIXED VERSION"""
        if not self.current_user:
            return []
        
        # Check permissions
        can_view = False
        if self.current_user['username'] == username:
            can_view = True
        elif 'view_all_conversations' in self.current_user['permissions']:
            can_view = True
        elif 'view_student_conversations' in self.current_user['permissions']:
            can_view = True
        
        if not can_view:
            return []
        
        conversations = []
        
        # First, try to get from database
        try:
            with self.db_manager.get_connection() as conn:
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
                    conversations.append({
                        'timestamp': timestamp,
                        'details': details or 'Chatbot interaction',
                        'type': 'database'
                    })
                    
        except Exception as e:
            logger.error(f"Database history error: {e}")
        
        # Also get from chatbot's in-memory history if available
        try:
            if hasattr(self, 'chatbot') and self.chatbot and hasattr(self.chatbot, 'conversation_history'):
                user_history = self.chatbot.conversation_history.get(username, [])
                for conv in user_history:
                    conversations.append({
                        'timestamp': conv.get('timestamp', 'Recent'),
                        'details': f"Q: {conv.get('message', 'N/A')[:30]}... A: {conv.get('response', 'N/A')[:30]}...",
                        'type': 'session'
                    })
        except Exception as e:
            logger.error(f"Session history error: {e}")
        
        # Sort by timestamp and return most recent
        try:
            conversations.sort(key=lambda x: x['timestamp'], reverse=True)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Failed to sort conversations by timestamp: {e}")
            pass  # If sorting fails, return as-is

        return conversations[:limit]

    def generate_chatbot_analytics(self) -> Dict[str, Any]:
        """Generate chatbot usage analytics"""
        if not self.current_user or 'chatbot_analytics' not in self.current_user['permissions']:
            return {}
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total interactions
                cursor.execute('''
                    SELECT COUNT(*) FROM activity_log 
                    WHERE action = 'Chatbot interaction'
                ''')
                total_interactions = cursor.fetchone()[0]
                
                # Interactions by role (simplified)
                cursor.execute('''
                    SELECT u.role, COUNT(*) as count
                    FROM activity_log al
                    JOIN user_accounts ua ON al.username = ua.username
                    JOIN users u ON ua.user_id = u.id
                    WHERE al.action = 'Chatbot interaction'
                    GROUP BY u.role
                ''')
                interactions_by_role = dict(cursor.fetchall())
                
                # Recent activity (last 7 days)
                cursor.execute('''
                    SELECT DATE(timestamp) as date, COUNT(*) as count
                    FROM activity_log
                    WHERE action = 'Chatbot interaction'
                    AND timestamp >= datetime('now', '-7 days')
                    GROUP BY DATE(timestamp)
                    ORDER BY date
                ''')
                daily_interactions = dict(cursor.fetchall())
                
                return {
                    'total_interactions': total_interactions,
                    'interactions_by_role': interactions_by_role,
                    'daily_interactions': daily_interactions,
                    'status': 'active' if CHATBOT_AVAILABLE else 'limited',
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error generating chatbot analytics: {e}")
            return {'error': str(e)}

    def get_chatbot_permissions_for_role(self, role: str) -> list[str]:
        """Get chatbot-specific permissions for a role"""
        chatbot_permissions = {
            'admin': [
                'access_chatbot', 'chatbot_admin', 'view_all_conversations',
                'manage_chatbot_settings', 'chatbot_analytics', 'escalate_conversations'
            ],
            'staff': [
                'access_chatbot', 'view_student_conversations', 'chatbot_reports'
            ],
            'instructor': [
                'access_chatbot', 'view_course_conversations'
            ],
            'student': [
                'access_chatbot', 'voice_interaction'
            ]
        }
        
        return chatbot_permissions.get(role, ['access_chatbot'])

    def setup_chatbot_permissions(self):
        """Setup chatbot-specific permissions in the database"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Chatbot permissions
                chatbot_permissions = [
                    ('access_chatbot', 'Access University Chatbot'),
                    ('chatbot_admin', 'Administer Chatbot System'),
                    ('view_all_conversations', 'View All Chatbot Conversations'),
                    ('view_student_conversations', 'View Student Chatbot Conversations'),
                    ('view_course_conversations', 'View Course-related Conversations'),
                    ('manage_chatbot_settings', 'Manage Chatbot Configuration'),
                    ('chatbot_analytics', 'View Chatbot Analytics'),
                    ('chatbot_reports', 'Generate Chatbot Reports'),
                    ('escalate_conversations', 'Escalate Conversations to Human'),
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
                for role_name in ROLES.keys():
                    role_perms = self.get_chatbot_permissions_for_role(role_name)
                    
                    cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
                    role_result = cursor.fetchone()
                    if role_result:
                        role_id = role_result[0]
                        
                        for perm_name in role_perms:
                            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                            perm_result = cursor.fetchone()
                            if perm_result:
                                perm_id = perm_result[0]
                                cursor.execute(
                                    'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                    (role_id, perm_id)
                                )
                
                conn.commit()
                print("✓ Chatbot permissions configured")
                return True
                
        except Exception as e:
            logger.error(f"Error setting up chatbot permissions: {e}")
            return False

    def create_chatbot_session(self, username: str) -> Optional[str]:
        """Create a chatbot session for authenticated user"""
        if not self.current_user or self.current_user['username'] != username:
            return None
        
        if not self.check_permission('access_chatbot'):
            return None
        
        # Generate session token
        session_token = secrets.token_hex(32)
        
        # Log chatbot session creation
        self._log_activity(username, 'Chatbot session created', f'Token: {session_token[:8]}...', self.current_user['id'])
        
        return session_token

    def validate_chatbot_session(self, session_token: str, username: str) -> bool:
        """Validate chatbot session token"""
        if not self.current_user or self.current_user['username'] != username:
            return False
        
        if not self.check_permission('access_chatbot'):
            return False
        
        # In a production system, you'd store and validate actual session tokens
        # For now, just check if user is authenticated and has permission
        return True

    def get_user_chatbot_context(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user context for chatbot interactions"""
        if not self.current_user or self.current_user['username'] != username:
            return None
        
        user = self.current_user
        
        # Get additional user details
        user_details = self.get_user(username=username)
        if not user_details:
            return None
        
        # Build context
        context = {
            'user_id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'permissions': user['permissions'],
            'full_name': f"{user_details['first_name']} {user_details['last_name']}",
            'email': user_details['email'],
            'student_id': user_details.get('student_id'),
            'chatbot_permissions': [p for p in user['permissions'] if 'chatbot' in p or p in ['voice_interaction']],
            'can_use_voice': 'voice_interaction' in user['permissions'],
            'can_view_analytics': 'chatbot_analytics' in user['permissions'],
            'is_admin': user['role'] == 'admin'
        }
        
        return context

    def log_chatbot_interaction(self, username: str, message: str, response: str, intent: str = None):
        """Log chatbot interactions for audit purposes"""
        if not self.current_user:
            return
        
        details = {
            'message_length': len(message),
            'response_length': len(response),
            'intent': intent,
            'interaction_type': 'chatbot'
        }
        
        self._log_activity(
            username, 
            'Chatbot interaction', 
            json.dumps(details),
            self.current_user['id']
        )

    def generate_chatbot_analytics(self) -> Dict[str, Any]:
        """Generate chatbot usage analytics"""
        if not self.current_user or 'chatbot_analytics' not in self.current_user['permissions']:
            return {}
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total interactions
                cursor.execute('''
                    SELECT COUNT(*) FROM activity_log 
                    WHERE action = 'Chatbot interaction'
                ''')
                total_interactions = cursor.fetchone()[0]
                
                # Interactions by role
                cursor.execute('''
                    SELECT u.role, COUNT(*) as count
                    FROM activity_log al
                    JOIN user_accounts ua ON al.username = ua.username
                    JOIN users u ON ua.user_id = u.id
                    WHERE al.action = 'Chatbot interaction'
                    GROUP BY u.role
                ''')
                interactions_by_role = dict(cursor.fetchall())
                
                # Daily interactions (last 30 days)
                cursor.execute('''
                    SELECT DATE(timestamp) as date, COUNT(*) as count
                    FROM activity_log
                    WHERE action = 'Chatbot interaction'
                    AND timestamp >= datetime('now', '-30 days')
                    GROUP BY DATE(timestamp)
                    ORDER BY date
                ''')
                daily_interactions = dict(cursor.fetchall())
                
                # Most common intents
                cursor.execute('''
                    SELECT details, COUNT(*) as count
                    FROM activity_log
                    WHERE action = 'Chatbot interaction'
                    AND details IS NOT NULL
                    GROUP BY details
                    ORDER BY count DESC
                    LIMIT 10
                ''')
                
                intent_counts = {}
                for row in cursor.fetchall():
                    details, count = row
                    try:
                        details_dict = json.loads(details)
                        intent = details_dict.get('intent', 'unknown')
                        intent_counts[intent] = intent_counts.get(intent, 0) + count
                    except json.JSONDecodeError:
                        continue
                
                return {
                    'total_interactions': total_interactions,
                    'interactions_by_role': interactions_by_role,
                    'daily_interactions': daily_interactions,
                    'common_intents': intent_counts,
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error generating chatbot analytics: {e}")
            return {}

if __name__ == "__main__":
    print("University System with Chatbot Integration")
    print("=" * 50)
    
    # Initialize the complete system
    auth = initialize_complete_system()
    
    if not auth:
        print("❌ Failed to initialize system")
        exit(1)
    
    # Run additional setup and verification
    print("\nRunning setup verification...")
    
    # Summarise account coverage
    print("Summarising account coverage...")
    auth.verify_default_accounts()
    
    # Setup any missing permissions
    try:
        print("Setting up additional permissions...")
        add_finance_permissions()
        add_calendar_permissions()
        setup_ai_detector_permissions()
        add_plagiarism_permissions()
        print("✓ All permissions configured")
    except Exception as e:
        print(f"⚠️ Some permission setup failed: {e}")
    
    # Test integrations
    print("\nTesting system integrations...")

    if CHATBOT_AVAILABLE:
        try:
            auth.initialize_chatbot_integration()
            print("✓ Chatbot integration initialised")
        except Exception as e:
            print(f"⚠️ Chatbot integration issue: {e}")
    else:
        print("⚠️ Chatbot module not available")
    
    print("\n" + "="*50)
    print("SYSTEM READY!")
    print("="*50)
    
    print("\nAvailable Features:")
    print("- User Management & Authentication")
    print("- Role-Based Access Control")
    if CHATBOT_AVAILABLE:
        print("- Integrated University Chatbot")
        print("- Voice Interface Support")
        print("- Conversation Analytics")
    print("- Activity Logging & Audit Trail")
    print("- Permission Management")
    
    # Start the enhanced menu system
    print("\nStarting enhanced authentication menu...")
    try:
        if CHATBOT_AVAILABLE:
            display_auth_menu()
        else:
            display_auth_menu()
    except KeyboardInterrupt:
        print("\n\nSystem shutdown requested.")
    except Exception as e:
        print(f"\nSystem error: {e}")
    finally:
        print("Goodbye!")

# Additional helper functions for the integration

def quick_test_integration():
    """Quick test of the complete integration"""
    print("=== QUICK INTEGRATION TEST ===")
    
    try:
        auth = UserAuth()
        auth.verify_default_accounts()

        if CHATBOT_AVAILABLE:
            try:
                auth.initialize_chatbot_integration()
                print("✓ Chatbot integration initialised")
            except Exception as chatbot_error:
                print(f"⚠️  Chatbot integration reported an issue: {chatbot_error}")
        else:
            print("⚠️  Chatbot module not available")

        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM activity_log")
            activity_entries = cursor.fetchone()[0]
            print(f"✓ Activity log entries: {activity_entries}")

    except Exception as e:
        print(f"✗ Integration test failed: {e}")
    
    print("Test completed!")

def create_sample_chatbot_data():
    """Inspect chatbot interaction data stored in the database for validation."""
    auth = UserAuth()

    try:
        with auth.db_manager.get_connection() as conn:
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


# ============================================================================
# CENTRALIZED AUTH SINGLETON
# ============================================================================
# Global auth instance for centralized authentication management
_global_auth_instance = None

def get_global_auth():
    """
    Get the global centralized auth instance.

    Returns:
        UserAuth: The global auth instance, creating it if it doesn't exist

    Note:
        This ensures all modules use the same auth instance for consistent
        session management across the application.
    """
    global _global_auth_instance
    if _global_auth_instance is None:
        _global_auth_instance = UserAuth()
    return _global_auth_instance

def set_global_auth(auth_instance):
    """
    Set the global auth instance.

    Args:
        auth_instance: UserAuth instance to use as the global auth

    Note:
        This allows cli_main.py or other entry points to set the centralized
        auth instance that all modules will use.
    """
    global _global_auth_instance
    _global_auth_instance = auth_instance

def reset_global_auth():
    """
    Reset the global auth instance (useful for testing or logout).

    Note:
        This will create a new auth instance on the next call to get_global_auth()
    """
    global _global_auth_instance
    _global_auth_instance = None


# Export key functions for use by other modules
__all__ = [
    'UserAuth',
    'display_auth_menu',
    'initialize_complete_system',
    'test_chatbot_integration',
    'quick_test_integration',
    'CHATBOT_AVAILABLE',
    'get_global_auth',
    'set_global_auth',
    'reset_global_auth'
]
