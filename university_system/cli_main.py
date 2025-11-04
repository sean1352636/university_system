import sys
import time
import logging
import contextlib
import io
import random
import hashlib
import secrets
from datetime import datetime
import re
import os
import csv
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Import centralized paths early
from university_system.modules.shared.constants import paths

# Database file path - use centralized path configuration
DB_PATH = str(paths.DEFAULT_DB_PATH)
LOG_DIR = str(paths.LOG_DIR)

# Directories are automatically created by paths module via _ensure()

# Configure logging first, before other imports
from university_system.utils.logging.log_config import configure_logging

# Configure logging - use either basicConfig OR configure_logging, not both
logger = configure_logging(name=__name__)

# Import application modules from their package locations.
from university_system.modules.shared.utils.simple_activity_logger import (
    log_dynamic_activity as log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_menu_navigation,
    log_dynamic_activity,
)
from university_system.infrastructure.database.database_utils import cleanup_database_connections
from university_system.modules.domain.academics.services.assignments.assignment_submission import (
    display_assignment_menu,
    init_assignment_system,
    add_assignment_permissions
)

from university_system.infrastructure.auth.user_authentication import (
    display_user_management_menu,
    add_finance_permissions,
    UserAuth,
    display_auth_menu,
    set_auth_instance,
    set_global_auth,
    get_global_auth,
)

# Import MFA (Multi-Factor Authentication) services
try:
    from university_system.infrastructure.auth.mfa_service import (
        MFAService,
        setup_totp,
        verify_totp,
        generate_sms_otp,
        verify_sms_otp
    )
    MFA_AVAILABLE = True
except ImportError as e:
    MFAService = None
    MFA_AVAILABLE = False
    logger.warning(f"MFA services not available: {e}")

try:
    from university_system.infrastructure.auth.mfa_integration import integrate_mfa_with_auth
    MFA_INTEGRATION_AVAILABLE = True
except ImportError:
    MFA_INTEGRATION_AVAILABLE = False

try:
    from university_system.infrastructure.auth.email_otp_service import EmailOTPService
    EMAIL_OTP_AVAILABLE = True
except ImportError:
    EmailOTPService = None
    EMAIL_OTP_AVAILABLE = False

try:
    from university_system.infrastructure.auth.sms_provider import SMSProvider
    SMS_PROVIDER_AVAILABLE = True
except ImportError:
    SMSProvider = None
    SMS_PROVIDER_AVAILABLE = False

# Import security modules
try:
    from university_system.infrastructure.security.session_management import (
        SessionManager,
        SessionInfo,
        create_session,
        validate_session
    )
    SESSION_MANAGEMENT_AVAILABLE = True
except ImportError as e:
    SessionManager = None
    SESSION_MANAGEMENT_AVAILABLE = False
    logger.warning(f"Session management not available: {e}")

try:
    from university_system.infrastructure.security.comprehensive_security import (
        APISecurityManager,
        PasswordSecurityManager,
        SecurityAuditManager,
        DataLossPreventionManager,
        IncidentResponseManager,
        VulnerabilityScanner
    )
    COMPREHENSIVE_SECURITY_AVAILABLE = True
except ImportError as e:
    APISecurityManager = None
    PasswordSecurityManager = None
    SecurityAuditManager = None
    COMPREHENSIVE_SECURITY_AVAILABLE = False
    logger.warning(f"Comprehensive security not available: {e}")

try:
    from university_system.infrastructure.security.data_encryption import (
        EncryptionManager,
        encrypt_sensitive_data,
        decrypt_sensitive_data
    )
    DATA_ENCRYPTION_AVAILABLE = True
except ImportError as e:
    EncryptionManager = None
    DATA_ENCRYPTION_AVAILABLE = False
    logger.warning(f"Data encryption not available: {e}")

try:
    from university_system.infrastructure.security.security_dashboard_cli import display_security_dashboard_menu
    SECURITY_DASHBOARD_CLI_AVAILABLE = True
except ImportError as e:
    display_security_dashboard_menu = None
    SECURITY_DASHBOARD_CLI_AVAILABLE = False
    logger.warning(f"Security Dashboard CLI not available: {e}")

from university_system.modules.domain.student_affairs.student_union.clubs import club_management as su_club
from university_system.modules.domain.student_affairs.student_union.events import event_management as su_event
from university_system.modules.domain.student_affairs.student_union.facilities import facility_management as su_fac
from university_system.modules.domain.student_affairs.student_union.administration import (
    admin_management as su_admin,
    finance_oversight as su_fin,
    miscellaneous as su_misc,
    student_union_core,
)
from university_system.modules.domain.student_affairs.student_union.elections import election_management as su_elec

from university_system.modules.domain.mobility.services.trip_management import (
    display_trip_management_menu,
    init_trip_db,
    setup_trip_permissions,
    set_auth as set_trip_auth,
    integrate_trip_management_with_main,
)
from university_system.modules.domain.housing.services.housing_accommodation import (
    display_housing_accommodation_menu,
    init_housing_db,
    set_auth as set_accommodation_auth,
)
from university_system.utils.ai.ai_detector import AIDetector
from university_system.modules.domain.academics.services.academic_calendar import (
    display_academic_calendar_menu,
    set_auth as set_calendar_auth,
    ensure_calendar_permissions,
)
from university_system.modules.domain.academics.services.course_management import display_course_management_menu
from university_system.utils.logging.log_management import display_log_management_menu
from university_system.modules.domain.academics.services.parent_portal import ParentPortal, integrate_parent_portal_with_main, display_parent_portal_menu, display_parent_portal_enhancement_menu
from university_system.modules.domain.commerce.services.shop_management import (
    init_shop_db,
    setup_shop_permissions,
    display_shop_menu,
    set_auth as set_shop_auth,
    log_activity as shop_log_activity,
    log_create as shop_log_create,
    log_read as shop_log_read,
    log_update as shop_log_update,
    log_delete as shop_log_delete,
)
from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import (
    display_student_union_menu,
    init_student_union_db,
    setup_student_union_permissions,
    set_auth as set_student_union_auth,
)
from university_system.modules.domain.student_affairs.services.helpdesk import display_helpdesk_menu, init_helpdesk_db
from university_system.modules.domain.health.services.health_portal import display_health_portal_menu
from university_system.modules.domain.student_affairs.services.internship_management import (
    display_internship_menu,
    init_internship_db,
    setup_internship_permissions,
    set_auth as set_internship_auth,
)
from university_system.modules.domain.commerce.services.restaurant_management import (
    display_main_menu as display_restaurant_menu,
    init_db as init_restaurant_db,
)
from university_system.modules.domain.student_affairs.services.alumni_management import (
    display_alumni_menu,
    init_alumni_db,
    setup_alumni_permissions,
)
from university_system.modules.domain.student_affairs.services.student_support import display_support_menu
from university_system.modules.domain.finance.core.financial_core import (
    init_enhanced_finance_db as initialize_finance,
    display_enhanced_finance_menu as display_finance_menu,
    assign_fees_to_student,
    record_payment,
    view_student_financial_statement,
    generate_invoice,
    manage_scholarships,
    generate_financial_reports,
    set_finance_auth,
)
from university_system.modules.domain.finance.reporting.financial_reports import display_enhanced_finance_menu as display_finance_reporting_menu
from university_system.modules.domain.mobility.services.parking_management import (
    display_parking_menu,
    init_db as init_parking_db,
)
from university_system.modules.domain.academics.services.library import display_library_menu, init_library_db
from university_system.modules.domain.housing.services.accommodation import (
    display_accommodation_menu,
    set_auth as set_medical_accommodation_auth,
)
from university_system.modules.domain.academics.services.module_scheduling import display_module_scheduling_menu
from university_system.modules.shared.services.analytics.enhanced_reporting import display_enhanced_reporting_menu
from university_system.modules.domain.academics.services.attendance.attendance_tracker import display_attendance_menu
from university_system.infrastructure.email.admin import display_communication_dashboard, CommunicationDashboard, integrate_communication_dashboard_with_main, set_communication_auth
from university_system.infrastructure.email.email_service import (
    send_registration_confirmation,
    send_update_confirmation,
)
from university_system.infrastructure.database.data_backup import (
    display_backup_menu,
    backup_before_operation,
)
from university_system.modules.shared.utils.document_manager import display_document_management_menu
from university_system.modules.domain.academics.grading.grade_tracking import display_enhanced_grade_menu
from university_system.modules.shared.services.analytics.advanced_search import display_enhanced_menu
from university_system.modules.shared.services.analytics.student_analytics import StudentAnalytics
from university_system.modules.shared.utils.batch_operations import BatchOperationManager
from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from university_system.modules.domain.academics.services.attendance.DSstudent import DSStudent
from university_system.modules.domain.academics.services.attendance.CSstudent import CSStudent

# Import module definitions from the refactored modules package
from university_system.modules.domain.academics.services.modules import (
    compulsory_module_1,
    compulsory_module_2,
    optional_module_1,
    optional_module_2,
    optional_module_3,
    optional_module_4,
    CS_optional_module_1,
    CS_optional_module_2,
    CS_optional_module_3,
    CS_optional_module_4,
    DS_optional_module_1,
    DS_optional_module_2,
    DS_optional_module_3,
    DS_optional_module_4,
)

# ============================================================================
# PHASE 4 FEATURE IMPORTS - New Features (October 2025)
# ============================================================================

# Feature 1: Virtual Classroom Integration
from university_system.modules.domain.academics.services.virtual_classroom import (
    VirtualClassroomManager,
    SessionManager,
    ParticipantManager,
    RecordingManager,
    BreakoutRoomManager,
    PollManager,
    ChatManager,
    create_virtual_classroom_tables
)

# Feature 2: Integrated Financial Aid & Scholarship Management
from university_system.modules.domain.finance.services.financial_aid import (
    FinancialAidManager,
    ScholarshipManager,
    create_financial_aid_tables
)

# Feature 3: Unified Communication Hub
from university_system.modules.shared.services.communication import (
    CommunicationManager,
    create_communication_tables
)

# Features 4-8: Database schemas are available in remaining_features_schema.py
# These features have database tables but no CLI/GUI interfaces yet:
# - Mobile App (PWA) Infrastructure
# - Accessibility & Accommodation Tools
# - Parent Portal Enhancement
# - Transportation & Parking Management
# - Blockchain Credentials & Digital Badges
#
# To use these features, import from remaining_features_schema.py and create
# appropriate service managers as needed.

# ============================================================================

# Import advanced feature menu functions from core files
from university_system.modules.domain.academics.services.lms.lms_core import display_lms_menu
from university_system.modules.domain.academics.services.attendance.attendance_tracker import display_attendance_menu as display_advanced_attendance_menu
from university_system.modules.domain.student_affairs.services.mental_health.mental_health_core import display_mental_health_menu
from university_system.modules.domain.student_affairs.services.early_warning.early_warning_core import display_early_warning_menu
from university_system.modules.domain.academics.services.degree_audit.degree_audit_core import display_degree_audit_menu
from university_system.modules.domain.career.services.career_services_core import display_career_services_menu
from university_system.modules.domain.admissions.services.admissions_crm_core import display_admissions_crm_menu
from university_system.modules.shared.services.analytics.analytics_dashboard_core import display_predictive_analytics_menu
from university_system.modules.domain.academics.services.module_scheduling import display_timetable_optimizer_menu
from university_system.modules.domain.campus.services.campus_events_core import display_campus_events_menu
from university_system.modules.domain.student_affairs.services.alumni_management import display_alumni_relations_menu
from university_system.modules.domain.research.services.research_grants_core import display_research_grants_menu
from university_system.modules.domain.facilities.services.facilities_management_core import display_facilities_management_menu
from university_system.modules.domain.academics.services.evaluation.course_evaluation_core import display_course_evaluation_menu
from university_system.modules.domain.academics.grading.predictive_analytics import predictive_analytics_menu
from university_system.modules.shared.services.business_intelligence.bi_reports_core import display_business_intelligence_menu
from university_system.modules.shared.services.ai_features.ai_features_core import display_ai_features_menu
from university_system.modules.shared.services.integrations.integration_marketplace_core import display_integration_marketplace_menu
from university_system.modules.domain.blockchain.services.blockchain_credentials_core import display_blockchain_credentials_menu
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import display_mobile_app_pwa_menu

# ============================================================================

# Global AI detector instance
ai_detector = None

# Global chatbot instance
chatbot_instance = None

def safe_auth_check(auth_obj):
    """Safely check if auth object has required attributes"""
    if not auth_obj:
        return False
    
    # Ensure required attributes exist
    if not hasattr(auth_obj, 'current_user'):
        auth_obj.current_user = None
    
    if not hasattr(auth_obj, 'last_activity'):
        auth_obj.last_activity = None
        
    if not hasattr(auth_obj, 'session_timeout'):
        auth_obj.session_timeout = 30
        
    if not hasattr(auth_obj, 'login_attempts'):
        auth_obj.login_attempts = {}
        
    if not hasattr(auth_obj, 'max_attempts'):
        auth_obj.max_attempts = 5
        
    if not hasattr(auth_obj, 'lockout_time'):
        auth_obj.lockout_time = 15
    
    return True

def initialize_chatbot_integration():
    """Initialize chatbot with authentication integration"""
    global chatbot_instance
    try:
        # Import the chatbot from the ai module
        from university_system.utils.ai.university_chatbot import UniversityChatbot
        
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
    except Exception as e:
        print(f"❌ Chatbot initialization failed: {e}")
        return False

def display_chatbot_menu():
    """Display chatbot menu with authentication"""
    global auth, chatbot_instance
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the chatbot.")
        return
    
    if not auth.check_permission('access_chatbot'):
        print("You don't have permission to access the chatbot.")
        return
    
    # Initialize chatbot if not already done
    if not chatbot_instance:
        if not initialize_chatbot_integration():
            print("Chatbot is not available at this time.")
            return
    
    while True:
        print(f"\nUniversity Chatbot")
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")
        print("=" * 50)
        print("1. Start Chat Session")
        print("2. View Conversation History")
        if auth.check_permission('view_all_conversations'):
            print("3. View All Conversations (Admin)")
        if auth.check_permission('chatbot_admin'):
            print("4. Chatbot Administration")
        print("5. Back to Main Menu")
        
        choice = input("\nEnter your choice: ")
        
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
            print("Invalid choice. Please try again.")

def start_chat_session():
    """Start interactive chat session"""
    global auth, chatbot_instance
    
    if not chatbot_instance:
        print("Chatbot not available.")
        return
    
    user = auth.current_user
    print(f"\nChatbot Session Started")
    print(f"Type 'exit' to end the session")
    print("=" * 40)
    
    session_id = f"{user['username']}_{int(time.time())}"
    
    while True:
        try:
            user_input = input(f"\n{user['username']}: ")
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Chatbot: Goodbye! Have a great day!")
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
        except Exception as e:
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
    except Exception as e:
        logging.error(f"Failed to log conversation: {e}")

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
        
    except Exception as e:
        print(f"Error retrieving conversation history: {e}")

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
    except Exception as e:
        print(f"Error: {e}")

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
    except Exception as e:
        print(f"Error: {e}")

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
        except Exception as e:
            print(f"Error: {e}")

def restart_chatbot():
    """Restart chatbot instance"""
    global chatbot_instance
    chatbot_instance = None
    if initialize_chatbot_integration():
        print("Chatbot restarted successfully.")
    else:
        print("Failed to restart chatbot.")

def integrate_plagiarism_checker_with_main():
    """Initialize and integrate the plagiarism checker with the main system"""
    try:
        # Import and initialize from your plagiarism_main.py
        from university_system.modules.domain.academics.services.assignments.plagiarism_main import PlagiarismChecker
        
        checker = PlagiarismChecker()
        logging.info("Plagiarism checker initialized successfully")
        
        # Add permissions if needed
        try:
            from university_system.infrastructure.auth.user_authentication import add_plagiarism_permissions
            auth_instance = globals().get('auth')
            if auth_instance:
                created_permissions = add_plagiarism_permissions(auth_instance)
                if created_permissions:
                    logging.info(f"Added plagiarism permissions: {', '.join(created_permissions)}")
        except Exception as perm_error:
            logging.warning(f"Could not add plagiarism permissions: {perm_error}")
        
        return True
        
    except ImportError as e:
        logging.warning(f"Plagiarism checker module not available: {e}")
        return True
    except Exception as e:
        logging.warning(f"Plagiarism checker integration failed: {e}")
        return True

def display_plagiarism_checker_menu(auth):
    """Wrapper to call your real plagiarism menu from plagiarism_main.py"""
    try:
        # Import your actual function
        from university_system.modules.domain.academics.services.assignments.plagiarism_main import display_plagiarism_checker_menu as real_menu
        
        # Call your real function
        real_menu(auth)
        
    except ImportError as e:
        print("Plagiarism checker module not found.")
        print("Make sure plagiarism_main.py is in the same directory.")
        input("Press Enter to continue...")
        
    except Exception as e:
        print(f"Error accessing plagiarism checker: {e}")
        input("Press Enter to continue...")
        
def integrate_ai_detector_with_main():
    """Initialize the AI detector system for integration with main menu"""
    global ai_detector
    try:
        # Initialize the AI detector with minimal configuration first
        ai_detector = AIDetector()
        
        # 🔧 CRITICAL FIX: Ensure all required attributes exist
        if not hasattr(ai_detector, 'detection_threshold'):
            ai_detector.detection_threshold = 0.7
            
        if not hasattr(ai_detector, 'style_profiles'):
            ai_detector.style_profiles = {}
            
        if not hasattr(ai_detector, 'detection_methods'):
            ai_detector.detection_methods = {
                'pattern_matching': True,
                'statistical_analysis': True,
                'behavioral_analysis': True,
                'temporal_analysis': True,
                'citation_verification': True
            }
            
        if not hasattr(ai_detector, 'current_user'):
            ai_detector.current_user = None
        
        # Set authentication if available
        global auth
        if auth:
            ai_detector.set_auth(auth)
        
        print("✅ AI detector system initialized successfully!")
        return True
        
    except Exception as e:
        logging.error(f"Failed to initialize AI detector: {e}")
        print(f"⚠️ AI detector initialization failed: {e}")
        
        # Create a minimal fallback AI detector
        try:
            ai_detector = create_minimal_ai_detector()
            print("✅ Minimal AI detector created as fallback")
            return True
        except Exception as fallback_error:
            logging.error(f"Even fallback AI detector failed: {fallback_error}")
            print(f"❌ Complete AI detector failure: {fallback_error}")
            return False

def create_minimal_ai_detector():
    """Create a minimal AI detector that won't crash"""
    class MinimalAIDetector:
        def __init__(self):
            self.detection_threshold = 0.7
            self.style_profiles = {}
            self.detection_methods = {
                'pattern_matching': True,
                'statistical_analysis': True,
                'behavioral_analysis': True,
                'temporal_analysis': True,
                'citation_verification': True
            }
            self.current_user = None
            self.auth = None
        
        def set_auth(self, auth_obj):
            self.auth = auth_obj
            if hasattr(auth_obj, 'current_user'):
                self.current_user = auth_obj.current_user
        
        def get_enhanced_statistics(self):
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'recent_submissions_7_days': 0,
                'high_risk_submissions': 0,
                'detection_threshold': self.detection_threshold,
                'active_style_profiles': len(self.style_profiles),
                'active_detection_methods': len(self.detection_methods),
                'database_status': 'minimal_mode',
                'generated_at': datetime.now().isoformat(),
                'mode': 'minimal_fallback'
            }
        
        def get_statistics(self):
            return self.get_enhanced_statistics()
        
        def list_submissions(self, student_id=None, limit=10, include_text=False):
            """Safe list submissions that handles database errors"""
            try:
                conn = get_db_connection()
                if not conn:
                    return {
                        'submissions': [],
                        'total': 0,
                        'message': 'Database connection failed'
                    }
                
                cursor = conn.cursor()
                
                # Build query with flexible column handling
                try:
                    # First, check what columns actually exist
                    cursor.execute("PRAGMA table_info(ai_detector_submissions)")
                    columns = {row[1]: row[1] for row in cursor.fetchall()}
                    
                    # Build select statement based on available columns
                    select_fields = [
                        'id',
                        'student_id',
                        columns.get('title', columns.get('submission_title', "'Untitled' as title")),
                        'course_code',
                        'assignment_id', 
                        'submission_date',
                        'word_count',
                        'character_count'
                    ]
                    
                    if include_text:
                        select_fields.append('submission_text')
                    
                    query = f'''
                    SELECT {", ".join(select_fields)}
                    FROM ai_detector_submissions s
                    LEFT JOIN ai_detector_results r ON s.id = r.submission_id
                    '''
                    
                    params = []
                    if student_id:
                        query += " WHERE s.student_id = ?"
                        params.append(student_id)
                    
                    query += " ORDER BY s.submission_date DESC LIMIT ?"
                    params.append(limit)
                    
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    
                    submissions = []
                    for row in rows:
                        submission = dict(row) if hasattr(row, 'keys') else {}
                        submissions.append(submission)
                    
                    conn.close()
                    
                    return {
                        'submissions': submissions,
                        'total': len(submissions),
                        'student_filter': student_id,
                        'limit': limit
                    }
                    
                except Exception as query_error:
                    conn.close()
                    return {
                        'submissions': [],
                        'total': 0,
                        'error': f"Query error: {query_error}",
                        'message': 'Database schema issue detected'
                    }
                
            except Exception as e:
                return {
                    'submissions': [],
                    'total': 0,
                    'error': str(e),
                    'message': 'Database access failed'
                }
        
        def analyze_text(self, text, title=None, student_id=None, course_code=None, assignment_id=None):
            """Basic text analysis that always works"""
            import random
            ai_score = random.uniform(0.1, 0.9)  # Random score for demo
            return {
                'submission_id': f"demo_{int(time.time())}",
                'ai_score': ai_score,
                'confidence': 0.5,
                'is_ai_generated': ai_score >= self.detection_threshold,
                'detection_methods': ['basic_pattern_matching'],
                'text_stats': {
                    'word_count': len(text.split()),
                    'char_count': len(text),
                    'sentence_count': len([s for s in text.split('.') if s.strip()]),
                },
                'indicators': [
                    {'name': 'demo_indicator', 'score': ai_score, 'evidence': 'Demo mode active'}
                ],
                'mode': 'minimal_demo'
            }
        
        def get_submission_details(self, submission_id):
            return {'error': 'Not available in minimal mode'}
    
    return MinimalAIDetector()

def display_ai_detector_menu_from_main(auth_obj):
    """Display AI detector menu with comprehensive error handling"""
    global ai_detector
    
    # Check if user is authenticated
    if not auth_obj or not auth_obj.current_user:
        print("You must be logged in to access the AI detector.")
        return
    
    # Initialize AI detector if not already done or if it failed
    if ai_detector is None:
        print("Initializing AI detector...")
        try:
            integrate_ai_detector_with_main()
        except Exception as e:
            print(f"❌ AI detector initialization failed: {e}")
            ai_detector = create_minimal_ai_detector()
            print("✅ Running in minimal mode")
    
    # Double-check that ai_detector has required attributes
    if not hasattr(ai_detector, 'detection_threshold'):
        print("⚠️ AI detector missing critical attributes, recreating...")
        ai_detector = create_minimal_ai_detector()
    
    # Ensure the AI detector has the current auth context
    try:
        ai_detector.set_auth(auth_obj)
    except Exception as e:
        print(f"⚠️ Could not set auth context: {e}")
    
    while True:
        print(f"\nAI Content Detector Menu:")
        print("========================")
        
        # Show current mode
        try:
            stats = ai_detector.get_enhanced_statistics()
            mode = stats.get('mode', 'normal')
            if mode == 'minimal_fallback':
                print("⚠️ Running in MINIMAL MODE - limited functionality")
        except:
            print("⚠️ Status check failed - proceeding with caution")
        
        print("1. Analyze text for AI-generated content")
        print("2. View submission history")
        print("3. View system statistics")
        print("4. Demo AI detector")
        print("5. Return to Main Menu")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        try:
            if choice == '1':
                analyze_text_interface_safe()
            elif choice == '2':
                view_submission_history_safe()
            elif choice == '3':
                view_ai_detector_statistics_safe()
            elif choice == '4':
                run_ai_detector_demo_safe()
            elif choice == '5':
                print("Returning to main menu...")
                break
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Please try again or return to main menu.")

def analyze_text_interface_safe():
    """Safe version of text analysis interface"""
    global ai_detector
    
    try:
        print("\nText Analysis for AI Detection")
        print("=" * 40)
        
        # Get basic inputs
        title = input("Enter submission title (optional): ").strip() or "Demo Analysis"
        
        print("\nEnter the text to analyze (press Enter twice to finish):")
        print("-" * 50)
        
        lines = []
        empty_lines = 0
        
        while empty_lines < 2:
            try:
                line = input()
                if line.strip() == "":
                    empty_lines += 1
                else:
                    empty_lines = 0
                lines.append(line)
            except KeyboardInterrupt:
                print("\nAnalysis cancelled.")
                return
        
        # Remove trailing empty lines
        while lines and lines[-1].strip() == "":
            lines.pop()
        
        text = "\n".join(lines)
        
        if not text.strip():
            print("❌ No text provided for analysis.")
            return
        
        print(f"\nAnalyzing {len(text)} characters of text...")
        
        # Analyze the text with error handling
        try:
            result = ai_detector.analyze_text(text=text, title=title)
            display_analysis_results_safe(result)
        except Exception as analysis_error:
            print(f"❌ Analysis failed: {analysis_error}")
            print("The AI detector may not be fully initialized.")
            
    except Exception as e:
        print(f"❌ Interface error: {e}")

def display_analysis_results_safe(result):
    """Safe version of results display"""
    try:
        print("\n" + "=" * 60)
        print("AI DETECTION ANALYSIS RESULTS")
        print("=" * 60)
        
        print(f"Submission ID: {result.get('submission_id', 'N/A')}")
        print(f"AI Score: {result.get('ai_score', 0):.3f} (0.0 = Human, 1.0 = AI)")
        print(f"Confidence Level: {result.get('confidence', 0):.3f}")
        
        is_ai = result.get('is_ai_generated', False)
        status = "🤖 LIKELY AI-GENERATED" if is_ai else "👤 LIKELY HUMAN-WRITTEN"
        print(f"Assessment: {status}")
        
        methods = result.get('detection_methods', [])
        print(f"Detection Methods Used: {', '.join(methods) if methods else 'Unknown'}")
        
        # Show text stats if available
        text_stats = result.get('text_stats', {})
        if text_stats:
            print(f"\nText Statistics:")
            print(f"  Word Count: {text_stats.get('word_count', 'N/A')}")
            print(f"  Character Count: {text_stats.get('char_count', 'N/A')}")
            print(f"  Sentence Count: {text_stats.get('sentence_count', 'N/A')}")
        
        # Show indicators if available
        indicators = result.get('indicators', [])
        if indicators:
            print(f"\nDetected Indicators:")
            for indicator in indicators:
                print(f"  • {indicator.get('name', 'Unknown')}: {indicator.get('score', 0):.3f}")
                evidence = indicator.get('evidence')
                if evidence:
                    print(f"    Evidence: {evidence}")
        
        mode = result.get('mode')
        if mode:
            print(f"\nMode: {mode}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error displaying results: {e}")
        print("Results could not be displayed properly.")
    
    input("\nPress Enter to continue...")

def fix_ai_detector_database_schema():
    """Fix AI detector database schema by creating proper tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("🔧 Fixing AI detector database schema...")
        
        # Create AI detector submissions table with correct column names
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_detector_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            submission_text TEXT NOT NULL,
            title TEXT,
            course_code TEXT,
            assignment_id TEXT,
            submission_date TEXT NOT NULL,
            word_count INTEGER,
            character_count INTEGER,
            institution_id TEXT
        )
        ''')
        
        # Create AI detector results table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_detector_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            ai_score REAL NOT NULL,
            confidence REAL NOT NULL,
            detailed_results TEXT,
            created_at TEXT NOT NULL,
            style_deviation REAL,
            FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
        )
        ''')
        
        # Check if we need to migrate old data or add missing columns
        cursor.execute("PRAGMA table_info(ai_detector_submissions)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # Add missing columns if they don't exist
        required_columns = {
            'title': 'TEXT',
            'course_code': 'TEXT', 
            'assignment_id': 'TEXT',
            'word_count': 'INTEGER',
            'character_count': 'INTEGER',
            'institution_id': 'TEXT'
        }
        
        for column_name, column_def in required_columns.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE ai_detector_submissions ADD COLUMN {column_name} {column_def}')
                    print(f"✅ Added column '{column_name}' to ai_detector_submissions table")
                except Exception as e:
                    print(f"⚠️ Could not add column '{column_name}': {e}")
        
        # Check if we have the wrong column name and need to rename
        if 'submission_title' in existing_columns and 'title' not in existing_columns:
            try:
                # SQLite doesn't support RENAME COLUMN directly in older versions
                # So we'll create a new table and copy data
                cursor.execute('''
                CREATE TABLE ai_detector_submissions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    submission_text TEXT NOT NULL,
                    title TEXT,
                    course_code TEXT,
                    assignment_id TEXT,
                    submission_date TEXT NOT NULL,
                    word_count INTEGER,
                    character_count INTEGER,
                    institution_id TEXT
                )
                ''')
                
                # Copy data from old table to new table
                cursor.execute('''
                INSERT INTO ai_detector_submissions_new 
                (id, student_id, submission_text, title, course_code, assignment_id, 
                 submission_date, word_count, character_count, institution_id)
                SELECT id, student_id, submission_text, submission_title, course_code, assignment_id,
                       submission_date, word_count, character_count, institution_id
                FROM ai_detector_submissions
                ''')
                
                # Drop old table and rename new one
                cursor.execute('DROP TABLE ai_detector_submissions')
                cursor.execute('ALTER TABLE ai_detector_submissions_new RENAME TO ai_detector_submissions')
                
                print("✅ Migrated 'submission_title' column to 'title'")
                
            except Exception as e:
                print(f"⚠️ Could not migrate submission_title column: {e}")
        
        conn.commit()
        conn.close()
        
        print("✅ AI detector database schema fix completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing AI detector database schema: {e}")
        return False
    
def view_submission_history_safe():
    """Safe version of submission history with proper error handling"""
    global ai_detector
    
    try:
        print("\nSubmission History")
        print("=" * 30)
        
        # Try to get submissions with error handling
        try:
            submissions = ai_detector.list_submissions(limit=20)
        except Exception as list_error:
            print(f"❌ Error accessing submission data: {list_error}")
            print("This might be a database schema issue. Attempting to fix...")
            
            # Try to fix the database schema
            if fix_ai_detector_database_schema():
                print("✅ Database schema fixed. Trying again...")
                try:
                    submissions = ai_detector.list_submissions(limit=20)
                except Exception as retry_error:
                    print(f"❌ Still having issues: {retry_error}")
                    submissions = {'submissions': [], 'total': 0, 'error': str(retry_error)}
            else:
                submissions = {'submissions': [], 'total': 0, 'error': 'Database schema fix failed'}
        
        if not submissions.get('submissions'):
            reason = submissions.get('error') or submissions.get('message', 'No submissions found')
            print(f"No submission history available. Reason: {reason}")
        else:
            print(f"Showing {len(submissions['submissions'])} of {submissions['total']} submissions:")
            print()
            
            for submission in submissions['submissions']:
                try:
                    print(f"ID: {submission.get('id', 'N/A')}")
                    
                    # Handle different possible column names
                    title = (submission.get('title') or 
                            submission.get('submission_title') or 
                            'Untitled')
                    print(f"Title: {title}")
                    
                    print(f"Date: {submission.get('submission_date', 'N/A')}")
                    
                    if submission.get('student_id'):
                        print(f"Student ID: {submission['student_id']}")
                    if submission.get('course_code'):
                        print(f"Course: {submission['course_code']}")
                    
                    ai_score = submission.get('ai_score')
                    if ai_score is not None:
                        status = "AI-Generated" if ai_score >= ai_detector.detection_threshold else "Human-Written"
                        print(f"AI Score: {ai_score:.3f} ({status})")
                    
                    print("-" * 40)
                    
                except Exception as display_error:
                    print(f"❌ Error displaying submission: {display_error}")
                    print(f"Raw data: {submission}")
                    print("-" * 40)
        
    except Exception as e:
        print(f"❌ Error viewing history: {e}")
        print("The submission history feature is currently unavailable.")
    
    input("\nPress Enter to continue...")

def display_detailed_submission(submission):
    """Display detailed information about a submission"""
    print("\n" + "=" * 60)
    print("DETAILED SUBMISSION VIEW")
    print("=" * 60)
    
    print(f"Submission ID: {submission['id']}")
    print(f"Title: {submission['submission_title']}")
    print(f"Student ID: {submission.get('student_id', 'N/A')}")
    print(f"Course Code: {submission.get('course_code', 'N/A')}")
    print(f"Assignment ID: {submission.get('assignment_id', 'N/A')}")
    print(f"Submission Date: {submission['submission_date']}")
    print(f"Word Count: {submission['word_count']}")
    print(f"Character Count: {submission['character_count']}")
    
    if submission.get('results'):
        latest_result = submission['results'][0]  # Most recent result
        print(f"\nLatest Analysis:")
        print(f"AI Score: {latest_result['ai_score']:.3f}")
        print(f"Confidence: {latest_result['confidence_level']:.3f}")
        print(f"Detection Method: {latest_result['detection_method']}")
        print(f"Analysis Date: {latest_result['analysis_date']}")
        
        if latest_result.get('indicators_found'):
            print(f"\nIndicators Found:")
            for indicator in latest_result['indicators_found']:
                print(f"  • {indicator.get('name', 'Unknown')}: {indicator.get('score', 0):.3f}")
                if indicator.get('evidence'):
                    print(f"    Evidence: {indicator['evidence']}")
    
    print("=" * 60)
    input("\nPress Enter to continue...")

def view_ai_detector_statistics_safe():
    """Safe version of statistics viewing"""
    global ai_detector
    
    try:
        print("\nAI Detector System Statistics")
        print("=" * 40)
        
        stats = ai_detector.get_enhanced_statistics()
        
        print(f"Detection Threshold: {stats.get('detection_threshold', 'Unknown')}")
        print(f"Total Submissions: {stats.get('total_submissions', 0)}")
        print(f"Unique Students: {stats.get('unique_students', 0)}")
        print(f"Average AI Score: {stats.get('average_ai_score', 0):.3f}")
        print(f"Recent Activity (7 days): {stats.get('recent_submissions_7_days', 0)}")
        print(f"High Risk Submissions: {stats.get('high_risk_submissions', 0)}")
        print(f"Database Status: {stats.get('database_status', 'Unknown')}")
        
        mode = stats.get('mode')
        if mode:
            print(f"Operating Mode: {mode}")
        
        print("=" * 40)
        
    except Exception as e:
        print(f"❌ Error retrieving statistics: {e}")
        print("Statistics are not available at this time.")
    
    input("\nPress Enter to continue...")

def run_ai_detector_demo_safe():
    """Safe version of demo"""
    try:
        print("\nRunning AI Detector Demo...")
        print("=" * 40)
        
        # Simple demo that should always work
        demo_text = "This is a demonstration of the AI content detection system. It analyzes text for patterns that might indicate artificial intelligence generation."
        
        result = ai_detector.analyze_text(
            text=demo_text,
            title="Demo Analysis"
        )
        
        display_analysis_results_safe(result)
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("This indicates the AI detector system needs attention.")
    
    input("\nPress Enter to continue...")
    
def suppress_duplicate_messages():
    """Context manager to suppress repetitive initialization messages"""
    return contextlib.redirect_stdout(io.StringIO())

def fix_accommodation_schema():
    """Fix accommodation database schema during startup"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Fix audit_log table - check if it exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        if not cursor.fetchone():
            # Create audit_log table if it doesn't exist
            cursor.execute('''
                CREATE TABLE audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    accommodation_id INTEGER,
                    details TEXT,
                    ip_address TEXT,
                    timestamp TEXT NOT NULL
                )
            ''')
            print("✅ Created audit_log table with all required columns")
        else:
            # Table exists, add missing columns
            cursor.execute("PRAGMA table_info(audit_log)")
            columns = [row[1] for row in cursor.fetchall()]
            
            missing_columns = {
                'accommodation_id': 'INTEGER',
                'details': 'TEXT', 
                'ip_address': 'TEXT'
            }
            
            for col_name, col_type in missing_columns.items():
                if col_name not in columns:
                    cursor.execute(f'ALTER TABLE audit_log ADD COLUMN {col_name} {col_type}')
                    print(f"✅ Added column '{col_name}' to audit_log table")
        
        # Also ensure accommodations table has all required columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accommodations'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(accommodations)")
            acc_columns = [row[1] for row in cursor.fetchall()]
            
            required_acc_columns = {
                'status': 'TEXT DEFAULT "active"',
                'approved_by': 'TEXT',
                'approval_date': 'TEXT',
                'notes': 'TEXT'
            }
            
            for col_name, col_def in required_acc_columns.items():
                if col_name not in acc_columns:
                    cursor.execute(f'ALTER TABLE accommodations ADD COLUMN {col_name} {col_def}')
                    print(f"✅ Added column '{col_name}' to accommodations table")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Error fixing accommodation schema: {e}")
        print(f"Warning: Could not fix accommodation schema: {e}")
        return False

def get_db_connection(timeout=30.0, max_retries=3):
    """Get a database connection with proper timeout and retry logic"""
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            # Use the configured DB_PATH instead of hardcoded path
            conn = sqlite3.connect(
                DB_PATH,  # This now points to refactored/db_files/student_records.db
                timeout=timeout,
                check_same_thread=False
            )
            # Configure for better concurrency
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")  
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
            conn.execute("PRAGMA cache_size = 10000")
            return conn
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logging.warning(f"Database locked, retrying... (attempt {attempt + 1})")
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue
            else:
                logging.error(f"Database connection error after {attempt + 1} attempts: {e}")
                return None
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            return None
        
def safe_db_operation_with_retry(operation_func, *args, max_retries=3, **kwargs):
    """
    Safely execute a database operation with retry logic and comprehensive error handling.
    
    Args:
        operation_func: The database operation function to execute
        *args: Arguments to pass to the operation function
        max_retries: Maximum number of retry attempts (default: 3)
        **kwargs: Keyword arguments to pass to the operation function
    
    Returns:
        Result of the operation function, or False if all attempts failed
    """
    retry_delay = 0.1
    last_error = None
    
    for attempt in range(max_retries):
        conn = None
        try:
            # Attempt to get database connection
            conn = get_db_connection(timeout=30.0)
            if not conn:
                last_error = "Failed to establish database connection"
                if attempt < max_retries - 1:
                    logging.warning(f"Database connection failed, retrying in {retry_delay * (2 ** attempt):.2f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                logging.error(f"Database connection failed after {max_retries} attempts")
                return False
            
            # Execute the database operation
            result = operation_func(conn, *args, **kwargs)
            
            # Commit the transaction
            conn.commit()
            
            # Log successful operation if there were previous failures
            if attempt > 0:
                logging.info(f"Database operation succeeded on attempt {attempt + 1}")
            
            return result
            
        except sqlite3.OperationalError as e:
            last_error = e
            
            # Handle rollback for operational errors
            if conn:
                try:
                    conn.rollback()
                    logging.debug("Transaction rolled back successfully")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Unexpected error during rollback: {rollback_error}")
            
            # Check if this is a database lock error that we can retry
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(f"Database locked, retrying in {wait_time:.2f}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                logging.error(f"Database operational error after {attempt + 1} attempts: {e}")
                if attempt >= max_retries - 1:
                    logging.error(f"Database operation failed permanently after {max_retries} attempts")
                    return False
                    
        except sqlite3.IntegrityError as e:
            last_error = e
            
            # Handle rollback for integrity errors
            if conn:
                try:
                    conn.rollback()
                    logging.debug("Transaction rolled back due to integrity constraint")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after integrity error: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Unexpected error during integrity error rollback: {rollback_error}")
            
            # Integrity errors usually shouldn't be retried as they indicate data conflicts
            logging.error(f"Database integrity error (attempt {attempt + 1}): {e}")
            return False
            
        except sqlite3.Error as e:
            last_error = e
            
            # Handle rollback for other SQLite errors
            if conn:
                try:
                    conn.rollback()
                    logging.debug("Transaction rolled back due to SQLite error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after SQLite error: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Unexpected error during SQLite error rollback: {rollback_error}")
            
            logging.error(f"SQLite error (attempt {attempt + 1}): {e}")
            
            # Retry for certain types of SQLite errors
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.info(f"Retrying database operation in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            return False
            
        except Exception as e:
            last_error = e
            
            # Handle rollback for unexpected errors
            if conn:
                try:
                    conn.rollback()
                    logging.debug("Transaction rolled back due to unexpected error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after unexpected error: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Critical: Multiple errors during rollback - original: {e}, rollback: {rollback_error}")
            
            logging.error(f"Unexpected error in database operation (attempt {attempt + 1}): {e}")
            
            # Retry for unexpected errors, but with caution
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.info(f"Retrying after unexpected error in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            return False
            
        finally:
            # Ensure connection is properly closed
            if conn:
                try:
                    conn.close()
                    logging.debug("Database connection closed successfully")
                except sqlite3.Error as close_error:
                    logging.warning(f"Error closing database connection: {close_error}")
                except Exception as close_error:
                    logging.error(f"Unexpected error while closing database connection: {close_error}")
                    # Don't re-raise here as we want to preserve the original error
    
    # If we've exhausted all retries
    if last_error:
        logging.error(f"Database operation failed permanently after {max_retries} attempts. Last error: {last_error}")
    else:
        logging.error(f"Database operation failed permanently after {max_retries} attempts due to unknown error")
    
    return False

# Add this function to fix the missing parent_user_mapping table
def fix_parent_portal_database():
    """Fix missing parent portal database tables"""
    try:
        # Use the student records database for schema corrections
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        
        print("🔧 Fixing parent portal database schema...")
        
        # Create parent_user_mapping table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_user_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            parent_id TEXT UNIQUE,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
        )
        ''')
        
        # Ensure parent_accounts table exists with all required columns
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            address TEXT,
            emergency_contact BOOLEAN DEFAULT 0,
            registration_date TEXT,
            two_factor_enabled BOOLEAN DEFAULT 0,
            two_factor_secret TEXT,
            profile_photo TEXT
        )
        ''')
        
        # Check if parent_accounts table is missing any columns and add them
        cursor.execute("PRAGMA table_info(parent_accounts)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        required_columns = {
            'two_factor_enabled': 'BOOLEAN DEFAULT 0',
            'two_factor_secret': 'TEXT',
            'profile_photo': 'TEXT'
        }
        
        for column_name, column_def in required_columns.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE parent_accounts ADD COLUMN {column_name} {column_def}')
                    print(f"✅ Added column '{column_name}' to parent_accounts table")
                except Exception as e:
                    print(f"⚠️ Could not add column '{column_name}': {e}")
        
        # Create parent_student_relationships table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_student_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT,
            student_id TEXT,
            relationship_type TEXT,
            access_level TEXT DEFAULT 'full',
            date_added TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Create parent_preferences table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT UNIQUE,
            email_notifications BOOLEAN DEFAULT 1,
            sms_notifications BOOLEAN DEFAULT 0,
            grade_alerts BOOLEAN DEFAULT 1,
            attendance_alerts BOOLEAN DEFAULT 1,
            behavior_alerts BOOLEAN DEFAULT 1,
            assignment_alerts BOOLEAN DEFAULT 0,
            weekly_summary BOOLEAN DEFAULT 1,
            notification_timing TEXT DEFAULT '08:00',
            quiet_hours_start TEXT DEFAULT '20:00',
            quiet_hours_end TEXT DEFAULT '07:00',
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
        )
        ''')
        
        # Create other essential parent portal tables
        essential_tables = [
            ('parent_notifications', '''
            CREATE TABLE IF NOT EXISTS parent_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                student_id TEXT,
                notification_type TEXT,
                notification_content TEXT,
                created_date TEXT,
                read_status BOOLEAN DEFAULT 0,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            '''),
            
            ('parent_messages', '''
            CREATE TABLE IF NOT EXISTS parent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                teacher_id INTEGER,
                student_id TEXT,
                message_content TEXT,
                created_date TEXT,
                is_read BOOLEAN DEFAULT 0,
                is_from_parent BOOLEAN DEFAULT 1,
                message_type TEXT DEFAULT 'individual',
                group_id TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (teacher_id) REFERENCES users (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            '''),
            
            ('parent_activity_log', '''
            CREATE TABLE IF NOT EXISTS parent_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                action TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')
        ]
        
        for table_name, create_sql in essential_tables:
            cursor.execute(create_sql)
            print(f"✅ Ensured {table_name} table exists")
        
        conn.commit()
        conn.close()
        
        print("✅ Parent portal database schema fix completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing parent portal database schema: {e}")
        return False

def enhanced_db_operation(operation_func, *args, **kwargs):
    """
    Enhanced wrapper for database operations with better error categorization.
    
    Args:
        operation_func: The database operation function to execute
        *args: Arguments to pass to the operation function
        **kwargs: Keyword arguments to pass to the operation function
    
    Returns:
        Tuple of (success: bool, result: any, error_type: str)
    """
    try:
        result = safe_db_operation_with_retry(operation_func, *args, **kwargs)
        
        if result is False:
            return False, None, "operation_failed"
        
        return True, result, None
        
    except sqlite3.IntegrityError as e:
        logging.error(f"Data integrity violation: {e}")
        return False, None, "integrity_error"
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            logging.error(f"Database access conflict: {e}")
            return False, None, "database_locked"
        else:
            logging.error(f"Database operational issue: {e}")
            return False, None, "operational_error"
            
    except Exception as e:
        logging.error(f"Unexpected error in database operation: {e}")
        return False, None, "unexpected_error"


# Example usage function that demonstrates the improved error handling
def example_create_student_operation(conn, student_data):
    """
    Example database operation that creates a student record.
    This shows how to structure operations for use with the retry function.
    """
    cursor = conn.cursor()
    
    try:
        # Insert student data
        cursor.execute('''
        INSERT INTO students (student_id, email_address, first_name, last_name, course)
        VALUES (?, ?, ?, ?, ?)
        ''', student_data)
        
        logging.info(f"Successfully created student record for ID: {student_data[0]}")
        return True
        
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            logging.warning(f"Student with ID {student_data[0]} already exists")
            raise  # Re-raise to be handled by the retry function
        else:
            logging.error(f"Data integrity issue when creating student: {e}")
            raise
            
    except Exception as e:
        logging.error(f"Error creating student record: {e}")
        raise


# Helper function to use the enhanced operation
def create_student_with_retry(student_data):
    """
    Create a student record with retry logic and enhanced error handling.
    
    Args:
        student_data: Tuple containing student information
    
    Returns:
        Boolean indicating success or failure
    """
    success, result, error_type = enhanced_db_operation(
        example_create_student_operation, 
        student_data
    )
    
    if not success:
        if error_type == "integrity_error":
            print(f"Error: Student with ID {student_data[0]} already exists or data conflicts with existing records.")
        elif error_type == "database_locked":
            print("Error: Database is currently busy. Please try again in a moment.")
        elif error_type == "operational_error":
            print("Error: Database operational issue. Please contact system administrator.")
        else:
            print("Error: An unexpected issue occurred. Please try again or contact support.")
    
    return success

def handle_database_error(operation_name, error):
    """Centralized database error handling"""
    logging.error(f"{operation_name} failed: {error}")
    if "UNIQUE constraint failed" in str(error):
        return "duplicate_entry"
    elif "database is locked" in str(error):
        return "database_locked"
    else:
        return "general_error"

def silent_integrity_check():
    """Perform integrity checks silently during startup"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if users table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            # Users table doesn't exist yet, skip integrity check
            conn.close()
            return True
        
        # Check for and fix duplicate emails silently
        cursor.execute('''
        SELECT email, COUNT(*) as count 
        FROM users 
        GROUP BY email 
        HAVING count > 1
        ''')
        duplicate_emails = cursor.fetchall()
        
        if duplicate_emails:
            conn.close()
            fix_duplicate_emails()
            return silent_integrity_check()  # Re-check after fix
        
        # Check for and fix orphaned users silently
        cursor.execute('''
        SELECT u.id, u.username 
        FROM users u 
        LEFT JOIN user_accounts ua ON u.id = ua.user_id 
        WHERE ua.user_id IS NULL
        ''')
        orphaned_users = cursor.fetchall()
        
        if orphaned_users:
            conn.close()
            # Only try to fix if we have an auth context
            try:
                from university_system.infrastructure.auth.user_authentication import UserAuth
                temp_auth = UserAuth()
                auth = UserAuth()
                if hasattr(temp_auth, 'current_user') and temp_auth.current_user:
                    temp_auth.fix_database_consistency()
                # If no auth context, just log and continue - will be fixed later
            except Exception as e:
                logging.debug(f"Could not fix orphaned users during startup: {e}")
            return True
        
        conn.close()
        return True
        
    except Exception as e:
        logging.debug(f"Silent integrity check info: {e}")  # Changed from warning to debug
        return False

def ensure_default_users_exist_once():
    """
    Ensure default users exist but only create them once per session.
    This is the centralized function for creating default users.
    """
    # Check if we've already created users in this session
    if hasattr(ensure_default_users_exist_once, '_users_created'):
        return True
    
    try:
        conn = get_db_connection(timeout=10.0)
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check and create admin user if needed
        cursor.execute('SELECT id FROM users WHERE username = ? AND email = ?', ('admin', 'admin@university.edu'))
        if not cursor.fetchone():
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                cursor.execute('''
                INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', ('admin', 'System', 'Administrator', 'admin@university.edu', 'admin', None, current_time, current_time))
                print("✅ Default admin user created")
            except sqlite3.IntegrityError as e:
                # Check if it's just a username conflict with different email
                cursor.execute('SELECT email FROM users WHERE username = ?', ('admin',))
                existing_email = cursor.fetchone()
                if existing_email:
                    logging.info(f"Admin user exists with email: {existing_email[0]}")
                    print("ℹ️  Default admin user already exists")
                else:
                    logging.error(f"Error creating admin user: {e}")
        else:
            print("ℹ️  Default admin user already exists")
        
        # Check and create student user if needed
        cursor.execute('SELECT id FROM users WHERE username = ? AND email = ?', ('S12345', 'student@example.com'))
        if not cursor.fetchone():
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                cursor.execute('''
                INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', ('S12345', 'Student', 'User', 'student@example.com', 'student', 'S12345', current_time, current_time))
                print("✅ Default student user created")
            except sqlite3.IntegrityError as e:
                cursor.execute('SELECT email FROM users WHERE username = ?', ('S12345',))
                existing_email = cursor.fetchone()
                if existing_email:
                    logging.info(f"Student user exists with email: {existing_email[0]}")
                    print("ℹ️  Default student user already exists")
                else:
                    logging.error(f"Error creating student user: {e}")
        else:
            print("ℹ️  Default student user already exists")
        
        conn.commit()
        conn.close()
        
        # Mark as completed for this session
        ensure_default_users_exist_once._users_created = True
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Error ensuring default users: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error ensuring default users: {e}")
        return False
    
def create_default_user_if_needed(username, first_name, last_name, email, role, student_id=None):
    """
    Helper function for other modules to create default users safely.
    Returns True if user was created or already exists, False on error.
    """
    try:
        conn = get_db_connection(timeout=10.0)
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return True  # User already exists
        
        # Create the user
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, first_name, last_name, email, role, student_id, current_time, current_time))
        
        conn.commit()
        conn.close()
        print(f"✅ User '{username}' created successfully")
        return True
        
    except sqlite3.IntegrityError as e:
        logging.error(f"Could not create user '{username}': {e}")
        return False
    except Exception as e:
        logging.error(f"Error creating user '{username}': {e}")
        return False

def cleanup_database_on_startup():
    """Clean up any hanging database connections on startup"""
    try:
        import gc
        
        # First, try to checkpoint the WAL file - use correct DB path
        conn = get_db_connection(timeout=5.0)
        if conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        
        # Force garbage collection
        gc.collect()
        
        print("Database cleanup completed successfully.")
        return True
    except Exception as e:
        logging.warning(f"Database cleanup warning: {e}")
        return False
    
def cleanup_database_connections():
    """Function to cleanup database connections - can be called anywhere"""
    cleanup_success = False
    
    try:
        from university_system.infrastructure.database.database_utils import cleanup_database_connections
        cleanup_database_connections()
        cleanup_success = True
        logging.info("Database connections cleaned up successfully")
    except ImportError:
        logging.warning("database_utils module not found, skipping external cleanup")
    except AttributeError:
        logging.warning("cleanup_database_connections function not found in database_utils")
    except Exception as e:
        logging.error(f"Error during database cleanup: {e}")
    
    try:
        # Additional cleanup - force garbage collection
        import gc
        collected = gc.collect()
        logging.debug(f"Garbage collection completed, collected {collected} objects")
        cleanup_success = True
    except ImportError:
        # This should never happen since gc is a built-in module
        logging.error("Failed to import gc module for garbage collection")
    except Exception as e:
        logging.error(f"Error during garbage collection: {e}")
    
    if not cleanup_success:
        logging.warning("Database cleanup completed with some issues")
    
    return cleanup_success

def initialize_security_modules():
    """Initialize security and authentication modules"""
    print("Initializing security modules...")

    # Initialize MFA if available
    if MFA_AVAILABLE:
        try:
            print("  ✓ MFA services loaded")
        except Exception as e:
            logger.warning(f"Failed to initialize MFA: {e}")

    # Initialize Session Management if available
    if SESSION_MANAGEMENT_AVAILABLE:
        try:
            print("  ✓ Session management loaded")
        except Exception as e:
            logger.warning(f"Failed to initialize session management: {e}")

    # Initialize Comprehensive Security if available
    if COMPREHENSIVE_SECURITY_AVAILABLE:
        try:
            print("  ✓ Comprehensive security modules loaded")
        except Exception as e:
            logger.warning(f"Failed to initialize comprehensive security: {e}")

    # Initialize Data Encryption if available
    if DATA_ENCRYPTION_AVAILABLE:
        try:
            print("  ✓ Data encryption services loaded")
        except Exception as e:
            logger.warning(f"Failed to initialize data encryption: {e}")

    # Initialize Email OTP if available
    if EMAIL_OTP_AVAILABLE:
        try:
            print("  ✓ Email OTP services loaded")
        except Exception as e:
            logger.warning(f"Failed to initialize email OTP: {e}")

    # Initialize SMS Provider if available
    if SMS_PROVIDER_AVAILABLE:
        try:
            print("  ✓ SMS provider loaded")
        except Exception as e:
            logger.warning(f"Failed to initialize SMS provider: {e}")

    print("Security modules initialized successfully!")
    return True


def initialize_system():
    """Initialize the system with proper cleanup and integrity checks"""
    print("Initializing Student Record Management System...")

    # Check if system is already initialized to prevent duplicate runs
    if hasattr(initialize_system, '_initialized'):
        print("System already initialized, skipping...")
        return True

    # Cleanup any hanging database connections
    cleanup_database_on_startup()

    # Initialize databases
    if not init_all_databases():
        print("Critical: Failed to initialize databases.")
        return False

    # Initialize security modules
    initialize_security_modules()

    # Mark as initialized
    initialize_system._initialized = True

    # Validate database integrity with admin context
    print("Checking database integrity...")
    validate_database_integrity_with_admin_context()

    print("System initialized successfully!")
    return True

def validate_database_integrity_with_admin_context():
    """
    Validate database integrity with admin permissions during startup
    """
    print("Validating database integrity with admin context...")
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if users table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Users table not created yet, skipping integrity validation.")
            conn.close()
            return True
        
        issues_found = []
        fixes_applied = []
        
        # Check 1: Duplicate emails in users table
        cursor.execute('''
        SELECT email, COUNT(*) as count 
        FROM users 
        GROUP BY email 
        HAVING count > 1
        ''')
        duplicate_emails = cursor.fetchall()
        
        if duplicate_emails:
            issues_found.append(f"Found {len(duplicate_emails)} duplicate email addresses")
            # Auto-fix duplicate emails during startup
            conn.close()
            if fix_duplicate_emails():
                fixes_applied.append("Fixed duplicate emails")
        else:
            conn.close()
        
        # Check 2: Users without corresponding user_accounts
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Check if user_accounts table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_accounts'")
            if cursor.fetchone():
                cursor.execute('''
                SELECT u.id, u.username 
                FROM users u 
                LEFT JOIN user_accounts ua ON u.id = ua.user_id 
                WHERE ua.user_id IS NULL
                ''')
                orphaned_users = cursor.fetchall()
                
                if orphaned_users:
                    issues_found.append(f"Found {len(orphaned_users)} users without accounts")
                    # We'll let the user authentication system handle this later
                    # to avoid permission issues during startup
                    fixes_applied.append("Marked orphaned users for later fixing")
            
            conn.close()
        
        # Report findings
        if issues_found:
            print("Database integrity issues found:")
            for issue in issues_found:
                print(f"  ⚠️  {issue}")
            if fixes_applied:
                print("Fixes applied:")
                for fix in fixes_applied:
                    print(f"  ✅ {fix}")
        else:
            print("✅ Database integrity check passed - no issues found!")
        
        return len(issues_found) == 0
        
    except Exception as e:
        logging.error(f"Error during database integrity validation: {e}")
        return False

def emergency_fix_database():
    """
    Emergency function to fix database issues
    Call this if you're experiencing UNIQUE constraint errors
    """
    print("Emergency Database Fix Utility")
    print("=" * 40)
    
    try:
        # Fix duplicate emails
        print("Step 1: Fixing duplicate email addresses...")
        fix_duplicate_emails()
        
        # Fix orphaned records
        print("\nStep 2: Fixing orphaned user records...")
        from university_system.infrastructure.auth.user_authentication import UserAuth
        auth = UserAuth()
        auth.fix_database_consistency()
        
        # Validate integrity
        print("\nStep 3: Final integrity check...")
        validate_database_integrity()
        
        print("\nEmergency fix completed!")
        return True
        
    except Exception as e:
        logging.error(f"Emergency fix failed: {e}")
        return False

class Student:
    def __init__(self, student_id, email_address, title, first_name, middle_name, last_name, gender, dob, age, course, compulsory_module_1, compulsory_module_2, module1, module2, module3, module4, registration_datetime):
        self.student_id = student_id
        self.email_address = email_address
        self.title = title
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.gender = gender
        self.age = age
        self.dob = dob
        self.course = course
        self.compulsory_module_1 = compulsory_module_1
        self.compulsory_module_2 = compulsory_module_2
        self.module1 = module1
        self.module2 = module2
        self.module3 = module3
        self.module4 = module4
        self.registration_datetime=registration_datetime

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Initialize all the sub-modules that need auth
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
        
    except Exception as e:
        logging.error(f"Error setting up chatbot permissions: {e}")

def init_auth_for_modules():
    global auth
    if auth:
        # Set global auth instance for modules that can read it
        set_auth_instance(auth)
        
        # Configure existing modules with auth
        set_student_union_auth(auth)   # student_union
        set_finance_auth(auth)         # finance
        set_internship_auth(auth)      # internship
        set_accommodation_auth(auth)   # housing accommodation
        # Communication dashboard exposes its auth setter via admin module
        set_communication_auth(auth)
        try:
            from university_system.infrastructure.email import email_service
            import university_system.infrastructure.email.admin as email_admin
            # Mirror worker state into admin module to avoid optional-import NameErrors
            if not hasattr(email_admin, "worker_threads"):
                email_admin.worker_threads = email_service.worker_threads
            if not hasattr(email_admin, "email_queue"):
                email_admin.email_queue = email_service.email_queue
            if not hasattr(email_admin, "stop_email_workers"):
                email_admin.stop_email_workers = email_service.stop_email_workers
        except Exception as email_link_error:
            logging.debug(f"Skipping email worker linkage: {email_link_error}")
        from university_system.modules.domain.commerce.services.restaurant_management import set_auth as set_restaurant_auth
        set_restaurant_auth(auth)
        from university_system.modules.domain.mobility.services.parking_management import set_auth as set_parking_auth
        set_parking_auth(auth)
        from university_system.modules.domain.academics.services.library import set_auth as set_library_auth
        set_library_auth(auth)
        from university_system.modules.domain.student_affairs.services.alumni_management import set_auth as set_alumni_auth
        set_alumni_auth(auth)
        from university_system.modules.domain.student_affairs.services.student_support import set_auth as set_student_support_auth
        set_student_support_auth(auth)
        set_medical_accommodation_auth(auth)   # medical accommodation
        from university_system.modules.domain.commerce.services.shop_management import set_auth as set_shop_auth
        set_trip_auth(auth)
        set_shop_auth(auth)
        set_calendar_auth(auth)        # academic calendar
        setup_chatbot_permissions()
        
        # Wire the Student Union modules that keep their own module-level `auth`
        for m in (su_club, su_event, su_fac, su_admin, su_elec, su_fin, su_misc):
            if hasattr(m, "set_auth"):
                m.set_auth(auth)

        # Ensure calendar permissions exist
        try:
            ensure_calendar_permissions()
        except Exception as e:
            logging.warning(f"Could not ensure calendar permissions: {e}")
            
def init_db():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # IMPORTANT: Disable foreign keys during initial setup to avoid constraint issues
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Create students table first (no dependencies)
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

        # Check if students table has the correct number of columns and add missing ones
        cursor.execute("PRAGMA table_info(students)")
        student_columns = [col[1] for col in cursor.fetchall()]

        # Add missing columns if they don't exist
        if 'status' not in student_columns:
            try:
                cursor.execute('ALTER TABLE students ADD COLUMN status TEXT DEFAULT "Active"')
                print("✓ Added status column to students table")
            except Exception as e:
                print(f"Error adding status column: {e}")

        if 'enrollment_date' not in student_columns:
            try:
                cursor.execute('ALTER TABLE students ADD COLUMN enrollment_date TEXT')
                print("✓ Added enrollment_date column to students table")
            except Exception as e:
                print(f"Error adding enrollment_date column: {e}")

        # Create modules table (no dependencies) 
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            module_code TEXT PRIMARY KEY,
            module_name TEXT,
            module_type TEXT
        )
        ''')

        # Migrate/drop users if old schema detected
        cursor.execute("PRAGMA table_info(users)")
        old_cols = [c[1] for c in cursor.fetchall()]
        if 'username' in old_cols:
            cursor.execute("DROP TABLE IF EXISTS users")

        # Create or alter users table (depends on students)
        cursor.execute("PRAGMA table_info(users)")
        cols = [c[1] for c in cursor.fetchall()]
        if not cols:
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
        else:
            # ensure every new column exists
            required = {
                'first_name': 'TEXT NOT NULL',
                'last_name' : 'TEXT NOT NULL',
                'email'     : 'TEXT UNIQUE NOT NULL',
                'role'      : 'TEXT NOT NULL',
                'student_id': 'TEXT',
                'created_at': 'TEXT NOT NULL',
                'updated_at': 'TEXT NOT NULL'
            }
            for col, definition in required.items():
                if col not in cols:
                    try:
                        cursor.execute(f'ALTER TABLE users ADD COLUMN {col} {definition}')
                        logging.info(f"Added column '{col}' to users table")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            logging.debug(f"Column '{col}' already exists in users table")
                        else:
                            logging.error(f"Failed to add column '{col}' to users table: {e}")
                            # Continue with other columns rather than failing completely
                    except sqlite3.Error as e:
                        logging.error(f"Database error when adding column '{col}': {e}")
                        # Continue with other columns rather than failing completely

        # Create student_grades table (depends on students and modules)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            assessment_name TEXT,
            grade TEXT,
            grade_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Create attendance table (depends on students and modules)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            date TEXT,
            status TEXT,
            reason TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Create student_modules table (depends on students)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_type TEXT,
            module_code TEXT,
            module_name TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # POPULATE MODULES TABLE FIRST (before creating students that reference modules)
        all_modules = [
            (compulsory_module_1['code'], compulsory_module_1['name'], 'compulsory'),
            (compulsory_module_2['code'], compulsory_module_2['name'], 'compulsory'),
            (optional_module_1['code'], optional_module_1['name'], 'optional'),
            (optional_module_2['code'], optional_module_2['name'], 'optional'),
            (optional_module_3['code'], optional_module_3['name'], 'optional'),
            (optional_module_4['code'], optional_module_4['name'], 'optional'),
            (CS_optional_module_1['code'], CS_optional_module_1['name'], 'CS'),
            (CS_optional_module_2['code'], CS_optional_module_2['name'], 'CS'),
            (CS_optional_module_3['code'], CS_optional_module_3['name'], 'CS'),
            (CS_optional_module_4['code'], CS_optional_module_4['name'], 'CS'),
            (DS_optional_module_1['code'], DS_optional_module_1['name'], 'DS'),
            (DS_optional_module_2['code'], DS_optional_module_2['name'], 'DS'),
            (DS_optional_module_3['code'], DS_optional_module_3['name'], 'DS'),
            (DS_optional_module_4['code'], DS_optional_module_4['name'], 'DS')
        ]
        for module_code, module_name, module_type in all_modules:
            cursor.execute('''
            INSERT OR IGNORE INTO modules (module_code, module_name, module_type)
            VALUES (?, ?, ?)
            ''', (module_code, module_name, module_type))

        # ——— PARKING TABLES (these have their own dependencies) ———
        # Create users table dependency first for parking (already created above)
        
        # Vehicles table (depends on users)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id         TEXT PRIMARY KEY,
            license_plate      TEXT NOT NULL,
            make               TEXT,
            model              TEXT,
            year               INTEGER,
            color              TEXT,
            vehicle_type       TEXT,
            owner_id           INTEGER,
            registration_state TEXT,
            FOREIGN KEY (owner_id) REFERENCES users (id)
        )
        ''')

        # Parking lots table (no dependencies)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_lots (
            lot_id            TEXT PRIMARY KEY,
            lot_name          TEXT,
            location          TEXT,
            total_spaces      INTEGER,
            available_spaces  INTEGER,
            zone              TEXT,
            hours_of_operation TEXT
        )
        ''')

        # Parking spaces table (depends on parking_lots)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_spaces (
            space_id         TEXT PRIMARY KEY,
            lot_id           TEXT,
            space_number     TEXT,
            space_type       TEXT,
            occupancy_status TEXT,
            reserved_for     TEXT,
            FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
        )
        ''')

        # Parking permits table (depends on users and vehicles)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_permits (
            permit_id       TEXT PRIMARY KEY,
            id              INTEGER,
            full_name       TEXT,
            email           TEXT,
            zone            TEXT,
            permit_type     TEXT,
            start_date      TEXT,
            end_date        TEXT,
            active_status   TEXT,
            vehicle_id      TEXT,
            issue_date      TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (vehicle_id),
            FOREIGN KEY (id)         REFERENCES users    (id)
        )
        ''')

        # Violations table (depends on vehicles)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_violations (
            violation_id    TEXT PRIMARY KEY,
            vehicle_id      TEXT,
            license_plate   TEXT,
            violation_type  TEXT,
            violation_date  TEXT,
            fine_amount     REAL,
            payment_status  TEXT,
            location        TEXT,
            officer_id      TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (vehicle_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trip_calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            event_type TEXT DEFAULT 'trip_event',
            created_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
            UNIQUE (trip_id, event_id)
        )
        ''')
        
        # Commit table creation before inserting data
        conn.commit()

        # CREATE DEFAULT STUDENT RECORD (ONLY ONCE) - Now safe since modules exist
        # Temporarily disable foreign key checks to avoid module_code issues
        cursor.execute("PRAGMA foreign_keys = OFF")

        cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', ('S12345',))
        if cursor.fetchone()[0] == 0:
            now_dt = datetime.now()
            registration_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')
            dob = datetime(2000, 1, 1)
            age = now_dt.year - dob.year - ((now_dt.month, now_dt.day) < (dob.month, dob.day))
            
            # Create student record
            cursor.execute(
                'INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    'S12345', 'student@example.com', 'Mr', 'Default', 'lucas', 'Student',
                    'male', dob.strftime('%Y-%m-%d'), age, 'CS', registration_time,
                    'Active', registration_time
                )
            )
            
            # Create student modules - now safe since student exists
            module_data = [
                ('S12345', compulsory_module_1['code']),
                ('S12345', compulsory_module_2['code']),
                ('S12345', optional_module_1['code']),
                ('S12345', optional_module_2['code']),
                ('S12345', CS_optional_module_1['code']),
                ('S12345', CS_optional_module_2['code'])
            ]
            cursor.executemany(
                'INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)',
                module_data
            )

            # Re-enable foreign key checks after student modules insertion
            cursor.execute("PRAGMA foreign_keys = ON")

        # Commit all student data before creating users
        conn.commit()
        
        # COMMIT ALL CHANGES AND CLOSE
        conn.commit()
        conn.close()
        
        # CREATE DEFAULT USERS USING CENTRALIZED FUNCTION - Now safe since student exists
        # Call this AFTER closing the connection to avoid lock issues
        ensure_default_users_exist_once()
        
        print("Database initialized successfully!")
        return True

    except sqlite3.Error as e:
        logging.error(f"An error occurred while initializing the database: {e}")
        # Print more detailed error information
        print(f"Database initialization failed: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error during database initialization: {e}")
        print(f"Unexpected error during database initialization: {e}")
        return False

def init_integration_tables():
    """Create tables for system integration - ADD THIS TO main.py"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Create integration tables
        integration_tables = [
            '''CREATE TABLE IF NOT EXISTS attendance_calendar_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_record_id INTEGER,
                event_id TEXT,
                module_code TEXT,
                date TEXT,
                created_at TEXT,
                FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id),
                FOREIGN KEY (event_id) REFERENCES events (id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS system_integration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_system TEXT,
                target_system TEXT,
                operation TEXT,
                status TEXT,
                details TEXT,
                timestamp TEXT
            )'''
        ]
        
        for table_sql in integration_tables:
            cursor.execute(table_sql)
        
        conn.commit()
        conn.close()
        
        print("✅ Integration tables created successfully!")
        return True
        
    except Exception as e:
        logging.error(f"Error creating integration tables: {e}")
        return False

def link_attendance_to_calendar_events():
    """Link attendance records to calendar events - ADD THIS TO main.py"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Link existing attendance to calendar events
        cursor.execute('''
        INSERT OR IGNORE INTO attendance_calendar_links 
        (attendance_record_id, event_id, module_code, date, created_at)
        SELECT ar.id, e.id, ar.module_code, ar.date, datetime('now')
        FROM attendance_records ar
        JOIN events e ON e.name LIKE '%' || ar.module_code || '%' 
        AND e.date = ar.date
        WHERE NOT EXISTS (
            SELECT 1 FROM attendance_calendar_links acl 
            WHERE acl.attendance_record_id = ar.id
        )
        ''')
        
        linked_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"✅ Linked {linked_count} attendance records to calendar events!")
        return True
        
    except Exception as e:
        logging.error(f"Error linking attendance to calendar: {e}")
        return False

def create_integrated_dashboard_data():
    """Create data for integrated dashboard - ADD THIS TO main.py"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        dashboard_data = {
            'upcoming_events': [],
            'attendance_summary': {},
            'recent_activity': []
        }
        
        # Get upcoming events with attendance status
        cursor.execute('''
        SELECT e.id, e.name, e.date, e.event_type,
               COUNT(ar.id) as attendance_count
        FROM events e
        LEFT JOIN attendance_records ar ON e.date = ar.date
        WHERE e.date >= date('now')
        GROUP BY e.id
        ORDER BY e.date
        LIMIT 10
        ''')
        
        events = cursor.fetchall()
        for event in events:
            dashboard_data['upcoming_events'].append({
                'id': event[0],
                'name': event[1],
                'date': event[2],
                'type': event[3],
                'attendance_count': event[4]
            })
        
        # Get attendance summary for current week
        cursor.execute('''
        SELECT module_code, status, COUNT(*) as count
        FROM attendance_records
        WHERE date >= date('now', 'weekday 0', '-7 days')
        AND date < date('now', 'weekday 0')
        GROUP BY module_code, status
        ''')
        
        attendance_data = cursor.fetchall()
        for record in attendance_data:
            module = record[0]
            if module not in dashboard_data['attendance_summary']:
                dashboard_data['attendance_summary'][module] = {}
            dashboard_data['attendance_summary'][module][record[1]] = record[2]
        
        conn.close()
        return dashboard_data
        
    except Exception as e:
        logging.error(f"Error creating dashboard data: {e}")
        return None

def display_integrated_system_dashboard():
    """Display integrated system dashboard - ADD THIS TO main.py"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view the dashboard.")
        return
    
    print("\n" + "="*60)
    print("INTEGRATED SYSTEM DASHBOARD")
    print("="*60)
    print(f"User: {auth.current_user['username']} ({auth.current_user['role']})")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get dashboard data
    data = create_integrated_dashboard_data()
    if not data:
        print("Unable to load dashboard data.")
        return
    
    # Display upcoming events
    print(f"\n📅 UPCOMING EVENTS ({len(data['upcoming_events'])})")
    if data['upcoming_events']:
        for event in data['upcoming_events'][:5]:
            attendance_info = f" (📊 {event['attendance_count']} attendance records)" if event['attendance_count'] > 0 else ""
            print(f"   • {event['date']}: {event['name']} [{event['type']}]{attendance_info}")
    else:
        print("   No upcoming events")
    
    # Display attendance summary
    print(f"\n📊 WEEKLY ATTENDANCE SUMMARY")
    if data['attendance_summary']:
        for module, statuses in data['attendance_summary'].items():
            total = sum(statuses.values())
            present = statuses.get('Present', 0) + statuses.get('Late', 0)
            percentage = (present / total * 100) if total > 0 else 0
            print(f"   • {module}: {percentage:.1f}% attendance ({present}/{total})")
    else:
        print("   No attendance data for this week")
    
    print("="*60)
    input("\nPress Enter to continue...")

def ensure_default_users_exist_once():
    """
    Ensure default users exist but only create them once per session.
    This is the centralized function for creating default users with authentication.

    Creates three default accounts:
    - admin / admin123 (Administrator)
    - staff / staff123 (Staff member)
    - student / student123 (Student)
    """
    # Check if we've already created users in this session
    if hasattr(ensure_default_users_exist_once, '_users_created'):
        return True

    try:
        # Get global auth instance or create temporary one
        global auth
        temp_auth = None
        if auth is None:
            temp_auth = UserAuth()
            temp_auth._initialization_mode = True
        else:
            auth._initialization_mode = True

        auth_instance = auth if auth is not None else temp_auth

        conn = get_db_connection(timeout=10.0)
        if not conn:
            return False

        cursor = conn.cursor()

        # Enable foreign keys for this connection
        cursor.execute("PRAGMA foreign_keys = ON")

        # Verify that the student record exists before creating student user
        cursor.execute('SELECT student_id FROM students WHERE student_id = ?', ('S12345',))
        student_exists = cursor.fetchone()

        if not student_exists:
            print("Creating default student record S12345...")
            # Create the student record if it doesn't exist
            now_dt = datetime.now()
            registration_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')
            dob = datetime(2000, 1, 1)
            age = now_dt.year - dob.year - ((now_dt.month, now_dt.day) < (dob.month, dob.day))

            cursor.execute(
                'INSERT OR IGNORE INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    'S12345', 'student@example.com', 'Mr', 'Student', '', 'User',
                    'male', dob.strftime('%Y-%m-%d'), age, 'CS', registration_time,
                    'Active', registration_time
                )
            )
            conn.commit()

        conn.close()

        # Create default admin user with password
        try:
            result = auth_instance.create_user(
                username='admin',
                password='admin123',
                email='admin@university.edu',
                first_name='System',
                last_name='Administrator',
                role='admin',
                student_id=None
            )
            if result:
                print("✅ Default admin user created (username: admin, password: admin123)")
            else:
                print("ℹ️  Default admin user already exists")
        except Exception as e:
            logging.debug(f"Admin user creation: {e}")
            print("ℹ️  Default admin user already exists")

        # Create default staff user with password
        try:
            result = auth_instance.create_user(
                username='staff',
                password='staff123',
                email='staff@university.edu',
                first_name='Staff',
                last_name='Member',
                role='staff',
                student_id=None
            )
            if result:
                print("✅ Default staff user created (username: staff, password: staff123)")
            else:
                print("ℹ️  Default staff user already exists")
        except Exception as e:
            logging.debug(f"Staff user creation: {e}")
            print("ℹ️  Default staff user already exists")

        # Create default student user with password
        try:
            result = auth_instance.create_user(
                username='student',
                password='student123',
                email='student@example.com',
                first_name='Student',
                last_name='User',
                role='student',
                student_id='S12345'
            )
            if result:
                print("✅ Default student user created (username: student, password: student123)")
            else:
                print("ℹ️  Default student user already exists")
        except Exception as e:
            logging.debug(f"Student user creation: {e}")
            print("ℹ️  Default student user already exists")

        # Mark as completed for this session
        ensure_default_users_exist_once._users_created = True
        return True

    except sqlite3.Error as e:
        logging.error(f"Error ensuring default users: {e}")
        print(f"Error creating default users: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error ensuring default users: {e}")
        print(f"Unexpected error creating default users: {e}")
        return False
    
def ensure_user_in_communication_system(username, first_name, last_name, email, role, student_id=None):
    """
    Ensure that a user exists in the users table for communication system integration.
    This function should be called whenever a new user account is created.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if user already exists by username
        cursor.execute('SELECT id, email FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            user_id, existing_email = existing_user
            # User exists, check if we need to update email
            if existing_email != email:
                # Check if the new email is already used by another user
                cursor.execute('SELECT id FROM users WHERE email = ? AND username != ?', (email, username))
                email_conflict = cursor.fetchone()
                
                if email_conflict:
                    print(f"Warning: Email {email} is already in use by another user. Keeping existing email {existing_email} for user {username}.")
                else:
                    # Update the email
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    UPDATE users 
                    SET first_name = ?, last_name = ?, email = ?, role = ?, student_id = ?, updated_at = ?
                    WHERE username = ?
                    ''', (
                        first_name,
                        last_name,
                        email,
                        role,
                        student_id,
                        current_time,
                        username
                    ))
                    conn.commit()
                    print(f"User '{username}' information updated in communication system.")
            else:
                # Email is the same, just update other information
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                UPDATE users 
                SET first_name = ?, last_name = ?, role = ?, student_id = ?, updated_at = ?
                WHERE username = ?
                ''', (
                    first_name,
                    last_name,
                    role,
                    student_id,
                    current_time,
                    username
                ))
                conn.commit()
                print(f"User '{username}' information updated in communication system.")
        else:
            # User doesn't exist, use the centralized creation function
            conn.close()
            return create_default_user_if_needed(username, first_name, last_name, email, role, student_id)
        
        conn.close()
        return True
        
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: users.email" in str(e):
            print(f"Error: Email {email} is already in use. Could not integrate user {username}.")
        elif "UNIQUE constraint failed: users.username" in str(e):
            print(f"Error: Username {username} is already in use. Could not integrate user.")
        else:
            print(f"Database integrity error: {e}")
        return False
    except sqlite3.Error as e:
        logging.error(f"Database error during user integration: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error during user integration: {e}")
        return False

def fix_duplicate_emails():
    """
    Fix duplicate email issues in the users table by making them unique
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Find duplicate emails
        cursor.execute('''
        SELECT email, COUNT(*) as count 
        FROM users 
        GROUP BY email 
        HAVING count > 1
        ''')
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print("No duplicate emails found.")
            conn.close()
            return True
        
        print(f"Found {len(duplicates)} duplicate email(s). Fixing...")
        
        for email, count in duplicates:
            print(f"Fixing duplicate email: {email} (found {count} times)")
            
            # Get all users with this email
            cursor.execute('''
            SELECT id, username, email 
            FROM users 
            WHERE email = ? 
            ORDER BY id
            ''', (email,))
            
            users_with_email = cursor.fetchall()
            
            # Keep the first user with the original email, modify others
            for i, (user_id, username, user_email) in enumerate(users_with_email):
                if i == 0:
                    print(f"  Keeping original email for user {username}")
                    continue
                
                # Generate unique email for subsequent users
                base_email = email.split('@')[0]
                domain = email.split('@')[1]
                new_email = f"{base_email}_{username}@{domain}"
                
                # Make sure this new email is also unique
                counter = 1
                while True:
                    cursor.execute('SELECT id FROM users WHERE email = ?', (new_email,))
                    if not cursor.fetchone():
                        break
                    new_email = f"{base_email}_{username}_{counter}@{domain}"
                    counter += 1
                
                # Update the user's email
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                UPDATE users 
                SET email = ?, updated_at = ? 
                WHERE id = ?
                ''', (new_email, current_time, user_id))
                
                print(f"  Updated user {username} email to: {new_email}")
        
        conn.commit()
        conn.close()
        print("Duplicate email fix completed successfully!")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Database error while fixing duplicate emails: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error while fixing duplicate emails: {e}")
        return False

def validate_database_integrity():
    """
    Validate database integrity and fix common issues
    """
    print("Validating database integrity...")
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        issues_found = []
        fixes_applied = []
        
        # Check 1: Duplicate emails in users table
        cursor.execute('''
        SELECT email, COUNT(*) as count 
        FROM users 
        GROUP BY email 
        HAVING count > 1
        ''')
        duplicate_emails = cursor.fetchall()
        
        if duplicate_emails:
            issues_found.append(f"Found {len(duplicate_emails)} duplicate email addresses")
        
        # Check 2: Duplicate usernames in users table
        cursor.execute('''
        SELECT username, COUNT(*) as count 
        FROM users 
        GROUP BY username 
        HAVING count > 1
        ''')
        duplicate_usernames = cursor.fetchall()
        
        if duplicate_usernames:
            issues_found.append(f"Found {len(duplicate_usernames)} duplicate usernames")
        
        # Check 3: Users without corresponding user_accounts
        cursor.execute('''
        SELECT u.id, u.username 
        FROM users u 
        LEFT JOIN user_accounts ua ON u.id = ua.user_id 
        WHERE ua.user_id IS NULL
        ''')
        orphaned_users = cursor.fetchall()
        
        if orphaned_users:
            issues_found.append(f"Found {len(orphaned_users)} users without accounts")
        
        # Check 4: User accounts without corresponding users
        cursor.execute('''
        SELECT ua.id, ua.username 
        FROM user_accounts ua 
        LEFT JOIN users u ON ua.user_id = u.id 
        WHERE u.id IS NULL
        ''')
        orphaned_accounts = cursor.fetchall()
        
        if orphaned_accounts:
            issues_found.append(f"Found {len(orphaned_accounts)} accounts without user profiles")
        
        conn.close()
        
        # Report findings
        if issues_found:
            print("Database integrity issues found:")
            for issue in issues_found:
                print(f"  - {issue}")
            
            fix_choice = input("\nWould you like to attempt to fix these issues? (y/n): ").lower()
            if fix_choice == 'y':
                # Fix duplicate emails
                if duplicate_emails:
                    if fix_duplicate_emails():
                        fixes_applied.append("Fixed duplicate emails")
                
                # Fix other issues using existing auth methods
                from university_system.infrastructure.auth.user_authentication import UserAuth
                auth = UserAuth()
                if orphaned_users or orphaned_accounts:
                    if auth.fix_database_consistency():
                        fixes_applied.append("Fixed orphaned users/accounts")
                
                if fixes_applied:
                    print("\nFixes applied:")
                    for fix in fixes_applied:
                        print(f"  - {fix}")
                    print("Database integrity validation completed!")
                else:
                    print("No fixes could be applied automatically.")
        else:
            print("Database integrity check passed - no issues found!")
        
        return len(issues_found) == 0
        
    except Exception as e:
        logging.error(f"Error during database integrity validation: {e}")
        return False

def ensure_communication_integration_on_startup():
    """
    Ensure all users are properly integrated with the communication system on startup.
    This function checks for any missing integrations and fixes them automatically.
    """
    try:
        print("Checking communication system integration...")
        
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if users table exists, if not create it
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Users table not found. Creating...")
            cursor.execute('''
            CREATE TABLE users (
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
        
        # Get all students and check if they have user accounts
        cursor.execute('''
        SELECT s.student_id, s.email_address, s.first_name, s.last_name, s.registration_datetime
        FROM students s
        LEFT JOIN users u ON s.student_id = u.student_id
        WHERE u.id IS NULL
        ''')
        
        missing_students = cursor.fetchall()
        
        if missing_students:
            print(f"Found {len(missing_students)} students not integrated with communication system.")
            print("Integrating them now...")
            
            for student in missing_students:
                student_id, email, first_name, last_name, reg_time = student
                
                try:
                    cursor.execute('''
                    INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        student_id,
                        first_name,
                        last_name,
                        email,
                        'student',
                        student_id,
                        reg_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    print(f"  - Integrated student {student_id} ({first_name} {last_name})")
                    
                except sqlite3.IntegrityError as e:
                    print(f"  - Could not integrate student {student_id}: {e}")
        
        # Check for any orphaned user accounts (users without student records for students)
        cursor.execute('''
        SELECT u.username, u.first_name, u.last_name, u.role
        FROM users u
        LEFT JOIN students s ON u.student_id = s.student_id
        WHERE u.role = 'student' AND s.student_id IS NULL
        ''')
        
        orphaned_users = cursor.fetchall()
        if orphaned_users:
            print(f"Warning: Found {len(orphaned_users)} orphaned user accounts:")
            for user in orphaned_users:
                print(f"  - {user[0]} ({user[1]} {user[2]}) - {user[3]}")
        
        conn.commit()
        conn.close()
        
        print("Communication system integration check complete!")
        return True
        
    except Exception as e:
        logging.error(f"Error during communication integration check: {e}")
        return False

def _link_auth_to_student_union(auth):
    """Wire authentication to Student Union modules."""
    try:
        from university_system.modules.domain.student_affairs import student_union
        if hasattr(student_union, 'set_auth_all'):
            student_union.set_auth_all(auth)
        elif hasattr(student_union, 'set_auth'):
            student_union.set_auth(auth)
    except Exception as e:
        print(f"(warning) Could not link auth to Student Union: {e}")

def fix_support_database_schema():
    """
    Fix the support database schema by adding missing columns.
    Call this function before initializing the EnhancedStudentSupport system.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("🔧 Fixing support database schema...")
        
        # Check if support_tickets table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='support_tickets'")
        if not cursor.fetchone():
            print("❌ support_tickets table does not exist. Creating it...")
            cursor.execute('''
            CREATE TABLE support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                user_id INTEGER,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_datetime TEXT NOT NULL,
                last_updated_datetime TEXT,
                assigned_to TEXT,
                escalated_at TEXT,
                resolved_at TEXT,
                closed_at TEXT,
                estimated_resolution TEXT,
                sentiment TEXT DEFAULT 'neutral',
                satisfaction_rating INTEGER,
                tags TEXT,
                parent_ticket_id INTEGER,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
            )
            ''')
            print("✅ Created support_tickets table with all required columns")
        else:
            # Table exists, check and add missing columns
            cursor.execute("PRAGMA table_info(support_tickets)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            # Ensure core columns exist for analytics and SLA tracking
            required_columns = {
                'created_datetime': 'TEXT',
                'last_updated_datetime': 'TEXT',
                'escalated_at': 'TEXT',
                'resolved_at': 'TEXT',
                'closed_at': 'TEXT',
                'estimated_resolution': 'TEXT',
                'sentiment': 'TEXT',
                'satisfaction_rating': 'INTEGER',
                'tags': 'TEXT',
                'parent_ticket_id': 'INTEGER',
                'subject': 'TEXT',
                'message': 'TEXT'
            }

            for column_name, column_def in required_columns.items():
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f'ALTER TABLE support_tickets ADD COLUMN {column_name} {column_def}')
                        print(f"✅ Added column '{column_name}' to support_tickets table")
                    except Exception as e:
                        print(f"⚠️ Could not add column '{column_name}': {e}")

            if 'user_id' not in existing_columns:
                try:
                    cursor.execute('ALTER TABLE support_tickets ADD COLUMN user_id INTEGER')
                    print("✅ Added column 'user_id' to support_tickets table")
                except Exception as e:
                    print(f"⚠️ Could not add column 'user_id': {e}")
        
        # Fix any existing tickets that have NULL created_datetime
        cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE created_datetime IS NULL OR created_datetime = ''")
        null_datetime_count = cursor.fetchone()[0]
        
        if null_datetime_count > 0:
            print(f"🔧 Fixing {null_datetime_count} tickets with missing created_datetime...")
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            UPDATE support_tickets 
            SET created_datetime = ? 
            WHERE created_datetime IS NULL OR created_datetime = ''
            ''', (current_time,))
            print(f"✅ Fixed {null_datetime_count} tickets with missing created_datetime")
        
        # Create other required tables
        required_tables = {
            'system_metrics': '''
            CREATE TABLE IF NOT EXISTS system_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                category TEXT NOT NULL,
                recorded_datetime TEXT NOT NULL,
                metadata TEXT
            )
            ''',
            'escalation_rules': '''
            CREATE TABLE IF NOT EXISTS escalation_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                priority TEXT,
                condition_type TEXT NOT NULL,
                condition_value TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_target TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT NOT NULL,
                created_datetime TEXT NOT NULL
            )
            '''
        }
        
        for table_name, create_sql in required_tables.items():
            cursor.execute(create_sql)
            print(f"✅ Ensured {table_name} table exists")
        
        conn.commit()
        conn.close()
        
        print("✅ Support database schema fix completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing support database schema: {e}")
        return False

def init_all_databases():
    """Initialize all required databases"""
    # Use a module-level flag to prevent multiple initializations
    if hasattr(init_all_databases, '_initialization_complete'):
        print("Databases already initialized, skipping...")
        return True
    
    print("Initializing all databases...")
    
    # Initialize main database first
    if not init_db():
        print("Failed to initialize main database")
        return False

    # Ensure the health portal schema and security tables are ready before features load
    try:
        print("Initializing health portal schema...")
        from university_system.modules.domain.health.portal.health_portal_core import init_enhanced_health_db
        from university_system.modules.domain.health.portal.data_privacy import ensure_security_schema

        init_enhanced_health_db()
        ensure_security_schema()
        print("✅ Health portal schema ready")
    except Exception as e:
        logging.warning(f"Health portal schema initialization encountered an issue: {e}")

    # Ensure academic calendar core tables exist on the shared database (avoids missing table errors)
    conn = None
    try:
        print("Ensuring academic calendar core tables...")
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS event_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color_code TEXT,
                    description TEXT,
                    date_added TEXT NOT NULL
                )
            ''')
            conn.commit()
            print("✅ Academic calendar tables verified")
    except Exception as e:
        logging.warning(f"Failed to ensure academic calendar tables: {e}")
    finally:
        if conn:
            conn.close()

    # Ensure email messaging schema matches admin expectations
    try:
        print("Ensuring messaging/email schema...")
        from university_system.infrastructure.email.email_db_utilities import initialize_email_db
        initialize_email_db()
        print("✅ Messaging tables verified")
    except Exception as e:
        logging.warning(f"Failed to ensure messaging tables: {e}")

    try:
        print("Initializing course management database...")
        from university_system.modules.domain.academics.services.course_management import initialize_enhanced_database
        if initialize_enhanced_database():
            print("✅ Course management database initialized")
        else:
            print("⚠️ Course management database initialization failed")
    except Exception as e:
        logging.warning(f"Failed to initialize course management database: {e}")

    try:
        print("Initializing assignment submission system...")
        if init_assignment_system():
            print("✅ Assignment submission system initialized")
        else:
            print("⚠️ Assignment submission system initialization failed")
    except Exception as e:
        logging.warning(f"Failed to initialize assignment system: {e}")
    
    # FIX THE ACCOMMODATION SCHEMA IMMEDIATELY AFTER MAIN DB INIT
    print("Fixing accommodation database schema...")
    fix_accommodation_schema()

    print("Fixing support database schema...")
    fix_support_database_schema()
    
    # Initialize user authentication database to ensure users table has correct schema
    global auth
    if auth is None:
        auth = UserAuth()
    
    # Wait a moment to ensure the main database is fully initialized
    time.sleep(0.1)
        
    # Ensure communication system integration
    ensure_communication_integration_on_startup()
    
    # Initialize other databases one by one (ONLY ONCE)
    databases = [
        ('parent portal', integrate_parent_portal_with_main),
        ('library', init_library_db),
        ('parking', init_parking_db),
        ('alumni', init_alumni_db),
        ('restaurant', init_restaurant_db),
        ('internship', init_internship_db),
        ('helpdesk', init_helpdesk_db),
        ('student union', init_student_union_db),
        ('finance', initialize_finance),  # Initialize finance here, after DB_PATH is set
        ('housing accommodation', init_housing_db),
        ('university shop', init_shop_db),
        ('trip management', init_trip_db)
    ]

    init_integration_tables()

    for db_name, init_func in databases:
        try:
            print(f"Initializing {db_name} database...")
            init_func()
            time.sleep(0.05)  # Small delay between database initializations
        except Exception as e:
            logging.warning(f"Failed to initialize {db_name} database: {e}")
            # Continue with other databases instead of failing completely

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            intent TEXT,
            confidence REAL,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Chatbot conversations table created")
    except Exception as e:
        logging.error(f"Error creating chatbot table: {e}")

    # Initialize chatbot integration
    try:
        if initialize_chatbot_integration():
            print("✅ Chatbot integration initialized")
        else:
            print("⚠️ Chatbot integration not available")
    except Exception as e:
        logging.error(f"Chatbot integration error: {e}")


    # Initialize communication dashboard (ONLY ONCE)
    try:
        print("Initializing communication dashboard...")
        set_communication_auth(auth)
        integrate_communication_dashboard_with_main()
        time.sleep(0.05)
    except Exception as e:
        logging.warning(f"Failed to initialize communication dashboard: {e}")

    # Initialize AI detector (ONLY ONCE)
    try:
        print("Initializing AI detector...")
        integrate_ai_detector_with_main()
        time.sleep(0.05)
    except Exception as e:
        logging.warning(f"Failed to initialize AI detector: {e}")
    
    # Mark initialization as complete
    init_all_databases._initialization_complete = True
    
    print("All databases initialization completed!")
    return True

def add_communication_dashboard_to_main_menu(auth):
    """Add the communication dashboard to the main menu"""
    # This function can be called from main.py
    try:
        # Initialize the dashboard with the current auth object
        dashboard = CommunicationDashboard(auth=auth)
        
        # Display the dashboard
        display_communication_dashboard(auth)
        return True
    except Exception as e:
        logging.error(f"Error displaying communication dashboard: {e}")
        return False

@log_create(module="student_records", description="Creating new student record")
def create_student_record():
    global auth

    # Check for permission
    if not auth or not auth.current_user:
        print("You must be logged in to create student records.")
        return

    if not auth.check_permission('create_student'):
        print("You don't have permission to create student records.")
        return

    # Get student name
    first_name = None
    while not first_name:
        first_name = input("Enter first name: ").strip()
        if not first_name:
            print("Error. Please enter a name.")
    
    middle_name = input("Enter middle name (optional): ").strip()
    
    last_name = None
    while not last_name:
        last_name = input("Enter last name: ").strip()
        if not last_name:
            print("Error. Please enter a name.")

    # Get gender and title
    while True:
        gender = input("Are you 'male', 'female', or 'other'?: ").strip().lower()
        if gender == 'male':
            title = 'Mr'
            break
        elif gender == 'female':
            title = 'Miss'
            break
        elif gender == 'other':
            title = input("Enter title (Mr/Ms/Dr/etc.): ").strip()
            if not title:
                title = ''
            break
        else:
            print("Error. Please enter 'male', 'female', or 'other'.")

    # Get date of birth
    def get_valid_date():
        while True:
            dob_str = input("Enter the date of birth (YYYY-MM-DD): ").strip()
            try:
                return datetime.strptime(dob_str, "%Y-%m-%d")
            except ValueError:
                print("Invalid date. Please enter a valid date in YYYY-MM-DD format.")
    
    dob = get_valid_date()

    # Compute age
    now_dt = datetime.now()
    age = now_dt.year - dob.year - ((now_dt.month, now_dt.day) < (dob.month, dob.day))
    print(f"Your age is {age}.")

    # Randomly choose course
    course = random.choice(['CS', 'DS'])
    print(f"Automatically selected course: {course}")

    # Show compulsory modules
    print("You will be required to study 2 compulsory modules which are:")
    print(f"{compulsory_module_1['code']} - {compulsory_module_1['name']}")
    print(f"{compulsory_module_2['code']} - {compulsory_module_2['name']}")
    input("Press Enter to proceed...")

    # Generate student ID and email
    student_id = random.randint(0, 9999999)
    student_id_str = str(student_id).zfill(7)
    email_address = f"C{student_id_str}@tees.ac.uk"
    print(f"Student ID: {student_id_str}")
    print(f"Email address: {email_address}")
    input("Press Enter to proceed...")

    # Randomly select two optional modules
    modules = {
        '1': optional_module_1,
        '2': optional_module_2,
        '3': optional_module_3,
        '4': optional_module_4,
    }
    opt_keys = random.sample(list(modules.keys()), 2)
    module1, module2 = modules[opt_keys[0]], modules[opt_keys[1]]
    print("Selected optional modules:")
    print(f"{module1['code']} - {module1['name']}")
    print(f"{module2['code']} - {module2['name']}")
    input("Press Enter to proceed...")

    # Randomly select two course-specific modules
    pool = {
        'CS': {'1': CS_optional_module_1, '2': CS_optional_module_2, '3': CS_optional_module_3, '4': CS_optional_module_4},
        'DS': {'1': DS_optional_module_1, '2': DS_optional_module_2, '3': DS_optional_module_3, '4': DS_optional_module_4}
    }[course]
    course_keys = random.sample(list(pool.keys()), 2)
    module3, module4 = pool[course_keys[0]], pool[course_keys[1]]
    print(f"Selected {course}-specific modules:")
    print(f"{module3['code']} - {module3['name']}")
    print(f"{module4['code']} - {module4['name']}")

    # Record registration datetime
    registration_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    print(f"Registration completed on {registration_time}")

    # Add retry logic for database operations
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        conn = None
        try:
            conn = get_db_connection(timeout=30.0)
            if not conn:
                raise sqlite3.Error("Could not connect to database")
                
            cursor = conn.cursor()

            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")

            # Insert into students table with better error handling
            try:
                cursor.execute(
                    'INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        student_id_str,
                        email_address,
                        title,
                        first_name,
                        middle_name,
                        last_name,
                        gender,
                        dob.strftime('%Y-%m-%d'),
                        age,
                        course,
                        registration_time,
                        'Active',  # status
                        registration_time  # enrollment_date
                    )
                )

                # Insert modules
                module_data = [
                    (student_id_str, compulsory_module_1['code']),
                    (student_id_str, compulsory_module_2['code']),
                    (student_id_str, module1['code']),
                    (student_id_str, module2['code']),
                    (student_id_str, module3['code']),
                    (student_id_str, module4['code'])
                ]
                cursor.executemany(
                    'INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)',
                    module_data
                )

                # Re-enable foreign key checks
                cursor.execute("PRAGMA foreign_keys = ON")

                # Commit all student data before creating user
                conn.commit()
                conn.close()
                conn = None  # Mark as closed to avoid double-close
                
                # Add a small delay to ensure the database commit is fully processed
                time.sleep(0.1)
                
                # Success - break out of retry loop
                break
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and retry_count < max_retries - 1:
                    print(f"Database temporarily locked, retrying... (attempt {retry_count + 1})")
                    retry_count += 1
                    time.sleep(1)  # Wait 1 second before retry
                    if conn:
                        try:
                            conn.close()
                        except sqlite3.Error as close_error:
                            logging.debug(f"Error closing connection during retry: {close_error}")
                        except Exception as close_error:
                            logging.warning(f"Unexpected error closing connection during retry: {close_error}")
                        finally:
                            conn = None
                    continue
                else:
                    raise e
                    
        except Exception as e:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error as close_error:
                    logging.debug(f"Error closing connection after exception: {close_error}")
                except Exception as close_error:
                    logging.warning(f"Unexpected error closing connection after exception: {close_error}")
                finally:
                    conn = None
                    
            if retry_count >= max_retries - 1:
                logging.error(f"Failed to create student record after {max_retries} attempts: {e}")
                print(f"Error: Failed to create student record after {max_retries} attempts. Please try again later.")
                return
            retry_count += 1
            time.sleep(1)

    # Add a small delay to ensure the database commit is fully processed
    time.sleep(0.1)

    # Create user account and integrate with communication system
    temp_password = f"{first_name}123456"
    try:
        # Create user account through authentication system
        created = auth.create_user(
            username=student_id_str,
            password=temp_password,
            email=email_address,
            first_name=first_name,
            last_name=last_name,
            role='student',
            student_id=student_id_str,
            password_reset_required=False
        )
        
        if created:
            print("\nUser account created successfully!")
            print(f"  Username: {student_id_str}")
            print(f"  Password: {temp_password}")
            
            # Ensure the user is integrated with the communication system
            ensure_user_in_communication_system(
                username=student_id_str,
                first_name=first_name,
                last_name=last_name,
                email=email_address,
                role='student',
                student_id=student_id_str
            )
            
            print(f"Student '{first_name} {last_name}' can now send and receive messages through the communication system.")
            
            # Send registration confirmation email
            try:
                send_registration_confirmation(student_id_str)
                print("Registration confirmation email has been sent.")
            except Exception as e:
                logging.warning(f"Registration confirmation email could not be sent: {e}")
            
        else:
            print("Failed to create user account. It may already exist.")
            
    except Exception as e:
        logging.error(f"Error creating student user account: {e}")
        print("Warning: Student record created but user account creation failed. Please contact an administrator.")

    print(f"\nStudent record creation complete!")
    print(f"Student ID: {student_id_str}")
    print(f"Email: {email_address}")
    print(f"The student can now log in and use all system features including messaging.")
    input("\nPress Enter to continue...")

@log_read(module="student_records", description="Viewing student records")
def view_student_record():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        print("You must be logged in to view student records.")
        return
    
    # Different behavior based on role/permissions
    if not (auth.has_permission('view_any_student') or auth.has_permission('view_own_record')):
        print("You don't have permission to view student records.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    if auth.has_permission('view_any_student'):
        # Admin or staff - can view any student
        cursor.execute('''
        SELECT * FROM students
        ''')
        
        students = cursor.fetchall()
        
        if not students:
            print("No student records found.")
            conn.close()
            return
        
        for student in students:
            display_student_record(student)
            
    elif auth.has_permission('view_own_record'):
        # Student - can only view their own record
        student_id = None
        
        # Get the student_id associated with this user - updated query for new database structure
        cursor.execute('''
        SELECT student_id FROM users WHERE id = ?
        ''', (auth.current_user['id'],))
        
        result = cursor.fetchone()
        if result and result[0]:
            student_id = result[0]
            
            # Fetch and display just this student's record
            cursor.execute('''
            SELECT * FROM students WHERE student_id = ?
            ''', (student_id,))
            
            student = cursor.fetchone()
            if student:
                display_student_record(student)
            else:
                print("Your student record was not found.")
        else:
            print("No student ID associated with your account.")
    
    conn.close()

@log_update(module="student_records", description="Updating student record")
def update_student_record():
    global auth

    # --- Permission checks ---
    if not auth or not auth.current_user:
        print("You must be logged in to update student records.")
        return

    if not (auth.has_permission('update_any_student') or auth.has_permission('update_own_profile')):
        print("You don't have permission to update student records.")
        return

    # Backup before making changes
    backup_before_operation('update')

    # Use safe database operation with retry logic
    def perform_update_operation(conn):
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- Identify student record ---
        if auth.has_permission('update_any_student'):
            # Admin/staff: pick any student
            while True:
                student_id = input("Enter student ID to update: ").strip()
                if not student_id:
                    print("Error: Student ID is required.")
                    continue

                cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
                student = cursor.fetchone()
                if student:
                    break
                print("Error: Student ID not found.")
        else:
            # Student: only own record - updated query for new database structure
            cursor.execute(
                "SELECT student_id FROM users WHERE id = ?",
                (auth.current_user['id'],)
            )
            row = cursor.fetchone()
            if not row or not row['student_id']:
                print("No student ID linked to your account.")
                return False

            student_id = row['student_id']
            cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
            student = cursor.fetchone()
            if not student:
                print("Your student record was not found.")
                return False

        # --- Select field to update ---
        print("Which field do you want to update?")
        print("1. First Name")
        print("2. Middle Name")
        print("3. Last Name")
        print("4. Gender")
        if auth.has_permission('update_any_student'):
            print("5. Course")
            print("6. Modules")
            max_option = 6
        else:
            max_option = 4

        choice = input(f"Select (1-{max_option}): ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= max_option):
            print("Invalid selection.")
            return False
        field_num = int(choice)

        # Initialize updated_fields dictionary
        updated_fields = {}

        # --- Perform update ---
        if field_num == 1:
            # First Name Update with Password Change
            while True:
                new_first = input("New first name: ").strip()
                if new_first:
                    # Update student record
                    cursor.execute(
                        "UPDATE students SET first_name = ? WHERE student_id = ?",
                        (new_first, student_id)
                    )
                    updated_fields = {"First Name": new_first}
                    
                    # Update password for corresponding user account
                    try:
                        # Find the user account associated with this student
                        cursor.execute("""
                            SELECT ua.id, ua.user_id, ua.username, u.email 
                            FROM user_accounts ua
                            JOIN users u ON ua.user_id = u.id
                            WHERE u.student_id = ?
                        """, (student_id,))
                        
                        user_account = cursor.fetchone()
                        
                        if user_account:
                            account_id, user_id, username, email = user_account
                            
                            # Generate new password: {firstname}123456
                            new_password = f"{new_first.lower()}123456"
                            
                            # Hash the new password using the same method as UserAuth
                            salt = secrets.token_hex(16)
                            key = hashlib.pbkdf2_hmac(
                                'sha256',
                                new_password.encode(),
                                salt.encode(),
                                100000,
                                dklen=64
                            )
                            password_hash = key.hex()
                            
                            # Update the password in user_accounts table
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            cursor.execute("""
                                UPDATE user_accounts 
                                SET password_hash = ?, salt = ?, updated_at = ?, password_reset_required = 0
                                WHERE id = ?
                            """, (password_hash, salt, timestamp, account_id))
                            
                            # Also update the first name in users table to keep it in sync
                            cursor.execute("""
                                UPDATE users 
                                SET first_name = ?, updated_at = ?
                                WHERE id = ?
                            """, (new_first, timestamp, user_id))
                            
                            print(f"✅ Password automatically updated to: {new_password}")
                            print(f"🔐 User '{username}' can now log in with the new password.")
                            
                            # Log the password change activity using the same connection
                            try:
                                log_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                ip_address = "127.0.0.1"  # Default IP
                                current_user_id = auth.current_user['id'] if auth.current_user else None
                                current_username = auth.current_user['username'] if auth.current_user else 'system'
                                
                                cursor.execute("""
                                    INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address) 
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (
                                    current_user_id,
                                    current_username,
                                    f'Password auto-updated for user: {username}',
                                    f'Due to first name change to: {new_first}',
                                    log_timestamp,
                                    ip_address
                                ))
                            except sqlite3.Error as log_error:
                                # Don't fail the update if logging fails
                                print(f"Note: Activity logging failed: {log_error}")
                            
                            updated_fields["Password"] = f"Updated to {new_password}"
                        else:
                            print("⚠️  No user account found for this student. Password not updated.")
                            
                    except sqlite3.Error as e:
                        print(f"⚠️  Error updating password: {e}")
                        # Continue with the student record update even if password update fails
                    
                    break
                print("Error: Name cannot be empty.")

        elif field_num == 2:
            new_middle = input("New middle name: ").strip()
            cursor.execute(
                "UPDATE students SET middle_name = ? WHERE student_id = ?",
                (new_middle, student_id)
            )
            updated_fields = {"Middle Name": new_middle}

        elif field_num == 3:
            while True:
                new_last = input("New last name: ").strip()
                if new_last:
                    cursor.execute(
                        "UPDATE students SET last_name = ? WHERE student_id = ?",
                        (new_last, student_id)
                    )
                    updated_fields = {"Last Name": new_last}
                    
                    # Also update last name in users table to keep it in sync
                    try:
                        cursor.execute("""
                            SELECT u.id FROM users u WHERE u.student_id = ?
                        """, (student_id,))
                        user_record = cursor.fetchone()
                        
                        if user_record:
                            user_id = user_record[0]
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            cursor.execute("""
                                UPDATE users 
                                SET last_name = ?, updated_at = ?
                                WHERE id = ?
                            """, (new_last, timestamp, user_id))
                            print("✅ User profile last name also updated.")
                    except sqlite3.Error as e:
                        print(f"⚠️  Error updating user profile last name: {e}")
                    
                    break
                print("Error: Name cannot be empty.")

        elif field_num == 4:
            while True:
                gender = input("Gender ('male','female','other'): ").strip().lower()
                if gender in ('male', 'female', 'other'):
                    title = {'male': 'Mr', 'female': 'Miss', 'other': ''}[gender]
                    break
                print("Error: Enter 'male', 'female', or 'other'.")

            cursor.execute(
                "UPDATE students SET gender = ?, title = ? WHERE student_id = ?",
                (gender, title, student_id)
            )
            updated_fields = {"Gender": gender, "Title": title}

        elif field_num == 5 and auth.check_permission('update_any_student'):
            # Swap course
            cursor.execute(
                "SELECT course FROM students WHERE student_id = ?",
                (student_id,)
            )
            current = cursor.fetchone()[0]
            new_course = 'DS' if current == 'CS' else 'CS'
            cursor.execute(
                "UPDATE students SET course = ? WHERE student_id = ?",
                (new_course, student_id)
            )

            # Update course-specific modules
            # Get old course to determine which modules to delete
            cursor.execute("SELECT course FROM students WHERE student_id = ?", (student_id,))
            old_course_result = cursor.fetchone()
            old_course = old_course_result[0] if old_course_result else 'CS'

            if old_course == 'CS':
                old_modules = [CS_optional_module_1['code'], CS_optional_module_2['code'],
                              CS_optional_module_3['code'], CS_optional_module_4['code']]
            else:
                old_modules = [DS_optional_module_1['code'], DS_optional_module_2['code'],
                              DS_optional_module_3['code'], DS_optional_module_4['code']]

            # Delete old course-specific modules by their codes
            if old_modules:
                placeholders = ','.join('?' * len(old_modules))
                cursor.execute(
                    f"DELETE FROM student_modules WHERE student_id = ? AND module_code IN ({placeholders})",
                    [student_id] + old_modules
                )

            # Add new course-specific modules
            if new_course == 'CS':
                modules = [CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4]
            else:
                modules = [DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4]

            selected_modules = random.sample(modules, 2)
            for module in selected_modules:
                cursor.execute(
                    "INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)",
                    (student_id, module['code'])
                )
            
            updated_fields = {"Course": new_course}

        elif field_num == 6 and auth.check_permission('update_any_student'):
            sel = input("1. Optional modules  2. Course-specific modules: ").strip()
            if sel == '1':
                modules = [optional_module_1, optional_module_2, optional_module_3, optional_module_4]
                # Get codes of old optional modules to delete
                old_module_codes = [optional_module_1['code'], optional_module_2['code'],
                                   optional_module_3['code'], optional_module_4['code']]
            elif sel == '2':
                cursor.execute("SELECT course FROM students WHERE student_id = ?", (student_id,))
                course = cursor.fetchone()[0]
                if course == 'CS':
                    modules = [CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4]
                    old_module_codes = [CS_optional_module_1['code'], CS_optional_module_2['code'],
                                       CS_optional_module_3['code'], CS_optional_module_4['code']]
                else:
                    modules = [DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4]
                    old_module_codes = [DS_optional_module_1['code'], DS_optional_module_2['code'],
                                       DS_optional_module_3['code'], DS_optional_module_4['code']]
            else:
                print("Invalid choice.")
                return False

            # Delete old modules by their codes
            if old_module_codes:
                placeholders = ','.join('?' * len(old_module_codes))
                cursor.execute(
                    f"DELETE FROM student_modules WHERE student_id = ? AND module_code IN ({placeholders})",
                    [student_id] + old_module_codes
                )

            selected_modules = random.sample(modules, 2)
            for module in selected_modules:
                cursor.execute(
                    "INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)",
                    (student_id, module['code'])
                )
            
            updated_fields = {"Modules": "Updated modules"}

        else:
            print("Invalid option.")
            return False

        # Get updated student record and return the data for display
        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
        updated = cursor.fetchone()
        
        return {
            'success': True,
            'updated_student': updated,
            'updated_fields': updated_fields,
            'student_id': student_id,
            'field_num': field_num
        }

    # Execute the update operation using safe database handling
    try:
        result = safe_db_operation_with_retry(perform_update_operation, max_retries=3)
        
        if not result or not result.get('success'):
            print("Failed to update student record. Please try again.")
            return
        
        # Display the updated record
        display_student_record(result['updated_student'])

        # Send confirmation email with error handling
        try:
            student_email = result['updated_student']['email_address']
            send_update_confirmation(student_email, result['updated_fields'])
        except Exception as e:
            logging.warning(f"Update confirmation email could not be sent ({type(e).__name__})")
        
        print("\nStudent record updated successfully!")
        
        # Display password change summary if first name was updated
        if result['field_num'] == 1:
            print("\n" + "="*50)
            print("🔐 PASSWORD UPDATE SUMMARY")
            print("="*50)
            print(f"Student ID: {result['student_id']}")
            print(f"New First Name: {result['updated_fields'].get('First Name', 'N/A')}")
            if "Password" in result['updated_fields']:
                print(f"New Password: {result['updated_fields']['Password'].replace('Updated to ', '')}")
                print("\n⚠️  IMPORTANT: Please inform the student of their new password!")
            print("="*50)
            
    except Exception as e:
        logging.error(f"Error during student record update: {e}")
        print("An error occurred while updating the student record. Please try again.")
    
@log_delete(module="student_records", description="Deleting student record")
def delete_student_record():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        print("You must be logged in to delete student records.")
        return
    
    if not auth.check_permission('delete_any_student'):
        print("You don't have permission to delete student records.")
        return
    
    backup_before_operation('delete')
    
    def perform_delete_operation(conn):
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ask the user for the student ID to delete
        id_num = input("Enter the ID number of the student to delete: ").strip()
        
        if not id_num:
            print("Error: Student ID cannot be empty.")
            return False
        
        # Check if the student exists
        cursor.execute('SELECT student_id, first_name, last_name FROM students WHERE student_id = ?', (id_num,))
        student = cursor.fetchone()
        
        if not student:
            print("No student records found with that ID.")
            return False
        
        # Display student info and confirm deletion
        print(f"\nStudent to delete:")
        print(f"ID: {student['student_id']}")
        print(f"Name: {student['first_name']} {student['last_name']}")
        
        confirm = input(f"\nAre you sure you want to delete student {id_num}? This will also delete all related records. (y/n): ")
        if confirm.lower() != 'y':
            print("Delete operation cancelled.")
            return False
        
        try:
            # Disable foreign key constraints temporarily for this operation
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            # Delete from all related tables in the correct order
            # Start with tables that reference the student
            
            # Delete student grades
            cursor.execute('DELETE FROM student_grades WHERE student_id = ?', (id_num,))
            print(f"Deleted {cursor.rowcount} grade records.")
            
            # Delete attendance records
            cursor.execute('DELETE FROM attendance WHERE student_id = ?', (id_num,))
            print(f"Deleted {cursor.rowcount} attendance records.")
            
            # Delete student modules
            cursor.execute('DELETE FROM student_modules WHERE student_id = ?', (id_num,))
            print(f"Deleted {cursor.rowcount} module assignments.")
            
            # Delete user account (if exists) - first get the user_id
            cursor.execute('SELECT id FROM users WHERE student_id = ?', (id_num,))
            user_record = cursor.fetchone()
            
            if user_record:
                user_id = user_record['id']
                
                # Delete from user_accounts table
                cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
                print(f"Deleted {cursor.rowcount} user account records.")
                
                # Delete from users table
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                print(f"Deleted {cursor.rowcount} user profile records.")
            
            # Delete any parking permits
            try:
                cursor.execute('DELETE FROM parking_permits WHERE id IN (SELECT id FROM users WHERE student_id = ?)', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} parking permit records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Delete any finance records
            try:
                cursor.execute('DELETE FROM student_fees WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} finance records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Delete any library records
            try:
                cursor.execute('DELETE FROM loans WHERE borrower_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} library loan records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Delete any trip participation records
            try:
                cursor.execute('DELETE FROM trip_participants WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} trip participation records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Delete any assignment submissions
            try:
                cursor.execute('DELETE FROM assignment_submissions WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} assignment submission records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Delete any accommodation requests
            try:
                cursor.execute('DELETE FROM accommodation_requests WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} accommodation request records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Delete any housing accommodation requests
            try:
                cursor.execute('DELETE FROM housing_requests WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} housing request records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Delete any health records
            try:
                cursor.execute('DELETE FROM health_records WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} health records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Delete any internship applications
            try:
                cursor.execute('DELETE FROM internship_applications WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} internship application records.")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            # Finally, delete the main student record
            cursor.execute('DELETE FROM students WHERE student_id = ?', (id_num,))
            if cursor.rowcount > 0:
                print(f"Deleted main student record.")
            else:
                print("Warning: Student record was not found during final deletion.")
                return False
            
            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")
            
            print(f"\nStudent {id_num} and all related records have been successfully deleted.")
            return True
            
        except sqlite3.Error as e:
            # Re-enable foreign keys even if there was an error
            cursor.execute("PRAGMA foreign_keys = ON")
            logging.error(f"Database error during student deletion: {e}")
            print(f"Error during deletion: {e}")
            return False
    
    # Execute the delete operation using safe database handling
    try:
        success = safe_db_operation_with_retry(perform_delete_operation, max_retries=3)
        
        if success:
            print("Student record deletion completed successfully!")
        else:
            print("Failed to delete student record. Please try again.")
            
    except Exception as e:
        logging.error(f"Error during student record deletion: {e}")
        print("An error occurred while deleting the student record. Please try again.")
    
    input("\nPress Enter to continue...")
    
@log_search(module="student_records", description="Searching by first name")
def search_student_by_first_name():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search student records.")
        return
    
    if not auth.check_permission('view_any_student'):
        print("You don't have permission to search student records.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    # Get search term from user
    search_term = input("Enter student's first name: ")

    # Validate search term
    if not search_term:
        print("Error: You must enter a search term.")
        conn.close()
        return
    if not re.match("^[a-zA-Z]+$", search_term):
        print("Error: Search term must contain only letters.")
        conn.close()
        return

    # Search for student records
    cursor.execute('''
    SELECT * FROM students WHERE LOWER(first_name) = LOWER(?)
    ''', (search_term,))
    
    matches = cursor.fetchall()

    # Display search results
    if len(matches) == 0:
        print(f"No records found for search term '{search_term}'.")
    elif len(matches) == 1:
        display_student_record(matches[0])
    else:
        print(f"Multiple records found for search term '{search_term}':")
        for i, match in enumerate(matches):
            print(f"{i+1}.")
            display_student_record(match)
        
        choice = input("Enter the number of the record you want to display: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(matches):
                raise ValueError
            display_student_record(matches[index])
        except (ValueError, IndexError):
            print("Error: Invalid choice.")
    
    conn.close()

@log_search(module="student_records", description="Searching by last name")
def search_student_by_last_name():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search student records.")
        return
    
    if not auth.check_permission('view_any_student'):
        print("You don't have permission to search student records.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    # Get search term from user
    search_term = input("Enter student's last name: ")

    # Validate search term
    if not search_term:
        print("Error: You must enter a search term.")
        conn.close()
        return
    if not re.match("^[a-zA-Z]+$", search_term):
        print("Error: Search term must contain only letters.")
        conn.close()
        return

    # Search for student records
    cursor.execute('''
    SELECT * FROM students WHERE LOWER(last_name) = LOWER(?)
    ''', (search_term,))
    
    matches = cursor.fetchall()

    # Display search results
    if len(matches) == 0:
        print(f"No records found for search term '{search_term}'.")
    elif len(matches) == 1:
        display_student_record(matches[0])
    else:
        print(f"Multiple records found for search term '{search_term}':")
        for i, match in enumerate(matches):
            print(f"{i+1}.")
            display_student_record(match)
        
        choice = input("Enter the number of the record you want to display: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(matches):
                raise ValueError
            display_student_record(matches[index])
        except (ValueError, IndexError):
            print("Error: Invalid choice.")
    
    conn.close()

@log_search(module="student_records", description="Searching by student id")
def search_student_by_student_id():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search student records.")
        return
    
    # Different behavior based on roles/permissions
    if not (auth.check_permission('view_any_student') or auth.check_permission('view_own_record')):
        print("You don't have permission to search student records.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    # For students with view_own_record permission only
    if not auth.check_permission('view_any_student') and auth.check_permission('view_own_record'):
        # Get the student ID associated with this user - updated for new database structure
        cursor.execute('''
        SELECT student_id FROM users WHERE id = ?
        ''', (auth.current_user['id'],))
        
        result = cursor.fetchone()
        if result and result[0]:
            student_id = result[0]
            
            # Fetch and display just this student's record
            cursor.execute('''
            SELECT * FROM students WHERE student_id = ?
            ''', (student_id,))
            
            student = cursor.fetchone()
            if student:
                display_student_record(student)
            else:
                print("Your student record was not found.")
        else:
            print("No student ID associated with your account.")
        
        conn.close()
        return
    
    # For staff/admin with view_any_student permission
    # Get search term from user
    search_term = input("Enter student's ID: ")

    # Validate search term
    if not search_term:
        print("Error: You must enter a search term.")
        conn.close()
        return
    if not re.match("^[0-9]+$", search_term):
        print("Error: Search term must contain only digits.")
        conn.close()
        return

    # Search for student records
    cursor.execute('''
    SELECT * FROM students WHERE student_id = ?
    ''', (search_term,))
    
    match = cursor.fetchone()

    # Display search results
    if not match:
        print(f"No records found for search term '{search_term}'.")
    else:
        display_student_record(match)
    
    conn.close()

@log_search(module="student_records", description="Searching by registration date")
def search_student_by_registration_date():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search student records.")
        return
    
    if not auth.check_permission('view_any_student'):
        print("You don't have permission to search student records.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    # Get search term from user
    search_date = input("Enter date (YYYY-MM-DD): ")

    # Validate search term
    if not search_date or not re.match("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", search_date):
        print("Error: Date must be in the format YYYY-MM-DD.")
        conn.close()
        return

    # Search for student records
    cursor.execute('''
    SELECT * FROM students WHERE registration_datetime LIKE ?
    ''', (f"{search_date}%",))
    
    matches = cursor.fetchall()

    # Display search results
    if len(matches) == 0:
        print(f"No records found for date '{search_date}'.")
    elif len(matches) == 1:
        display_student_record(matches[0])
    else:
        print(f"Multiple records found for date '{search_date}':")
        for i, match in enumerate(matches):
            print(f"{i+1}.")
            display_student_record(match)
        
        choice = input("Enter the number of the record you want to display: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(matches):
                raise ValueError
            display_student_record(matches[index])
        except (ValueError, IndexError):
            print("Error: Invalid choice.")
    
    conn.close()

@log_search(module="student_records", description="Searching by module name")
def search_module_by_module_name():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search module information.")
        return
    
    # Check for appropriate permissions
    if not (auth.check_permission('manage_modules') or 
            auth.check_permission('view_assigned_modules') or 
            auth.check_permission('view_any_student')):
        print("You don't have permission to search module information.")
        return
    
    # First check if the modules table exists - if not, initialize the database
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Check if the modules table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
        if not cursor.fetchone():
            conn.close()
            init_db()  # Initialize the database if it doesn't exist
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
        
        # Ask the user for the name of the module to search for
        module_name = input("Enter the name of the module to search for: ")
        
        # Find the module code that matches the name
        cursor.execute('''
        SELECT module_code, module_name FROM modules
        WHERE LOWER(module_name) LIKE LOWER(?)
        ''', (f"%{module_name}%",))
        
        modules = cursor.fetchall()
        
        if not modules:
            # Try searching in the module dictionary if not found in database
            found_modules = []
            all_modules = [
                compulsory_module_1, compulsory_module_2,
                optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4
            ]
            
            for module in all_modules:
                if module_name.lower() in module['name'].lower():
                    found_modules.append((module['code'], module['name']))
            
            if not found_modules:
                print("No module was found with that name.")
                conn.close()
                return
            else:
                modules = found_modules
        
        # If multiple modules match, let the user choose
        if len(modules) > 1:
            print("Multiple modules found:")
            for i, module in enumerate(modules):
                print(f"{i+1}. {module[0]} - {module[1]}")
            
            choice = input("Enter the number of the module you want to view: ")
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(modules):
                    raise ValueError
                module_code = modules[index][0]
                module_name = modules[index][1]
            except (ValueError, IndexError):
                print("Error: Invalid choice.")
                conn.close()
                return
        else:
            module_code = modules[0][0]
            module_name = modules[0][1]
        
        # Display the data associated with the module
        print(f"\nModule Code: {module_code}")
        print(f"Module Name: {module_name}")
        print("Students taking this module:")
        
        # Find students taking this module
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.middle_name, s.last_name
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ?
        ''', (module_code,))
        
        students = cursor.fetchall()
        
        if not students:
            print("No students are currently taking this module.")
        else:
            for student in students:
                print(f"Student ID: {student[0]}")
                print(f"Name: {student[1]} {student[2]} {student[3]}")
                print("-" * 30)
        
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        print("Initializing database...")
        init_db()
        print("Please try your search again.")

@log_search(module="student_records", description="Searching by module code")
def search_module_by_module_code():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search module information.")
        return
    
    # Check for appropriate permissions
    if not (auth.check_permission('manage_modules') or 
            auth.check_permission('view_assigned_modules') or 
            auth.check_permission('view_any_student')):
        print("You don't have permission to search module information.")
        return
    
    # First check if the modules table exists - if not, initialize the database
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Check if the modules table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
        if not cursor.fetchone():
            conn.close()
            init_db()  # Initialize the database if it doesn't exist
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
        
        # ask the user to input the module code
        module_code = input("Enter the module code: ")
        
        # check if the module code is valid
        cursor.execute('''
        SELECT module_name FROM modules
        WHERE module_code = ?
        ''', (module_code,))
        
        module = cursor.fetchone()
        
        if not module:
            # Try searching in the module dictionary if not found in database
            module_name = None
            all_modules = [
                compulsory_module_1, compulsory_module_2,
                optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4
            ]
            
            for mod in all_modules:
                if mod['code'] == module_code:
                    module_name = mod['name']
                    break
            
            if not module_name:
                print("Invalid module code")
                conn.close()
                return
            else:
                # display module name
                print(f"Module name: {module_name}")
                print("No students are currently taking this module.")
                conn.close()
                return
        
        # display module name
        print(f"Module name: {module[0]}")
        
        # Find students taking this module
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.middle_name, s.last_name
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ?
        ''', (module_code,))
        
        students = cursor.fetchall()
        
        if not students:
            print("No students are currently taking this module.")
        else:
            print("Students taking this module:")
            for student in students:
                print(f"Student ID: {student[0]}")
                print(f"Name: {student[1]} {student[2]} {student[3]}")
                print("-" * 30)
        
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        print("Initializing database...")
        init_db()
        print("Please try your search again.")

def get_file_path(file_format, default_filename):
    """Helper function to get file path from user with error handling"""
    while True:
        location_choice = input(f"Where would you like to save the {file_format} file?\n1. Current directory\n2. Custom path\nEnter your choice (1-2): ")
        
        if location_choice == '1':
            # Use current directory
            return os.path.join(os.getcwd(), default_filename)
        elif location_choice == '2':
            # Custom directory
            while True:
                custom_path = input("Enter the full path (including filename): ")
                directory = os.path.dirname(custom_path)
                
                # Check if directory exists or can be created
                if not directory:  # If no directory specified, use current directory
                    return custom_path
                
                if not os.path.exists(directory):
                    try_create = input(f"Directory {directory} does not exist. Create it? (y/n): ")
                    if try_create.lower() == 'y':
                        try:
                            os.makedirs(directory, exist_ok=True)
                            return custom_path
                        except OSError as e:
                            print(f"Error creating directory: {e}")
                            continue
                    else:
                        continue
                return custom_path
        else:
            print("Invalid choice. Please enter 1 or 2.")

def fetch_student_data(include_modules=True):
    """Helper function to fetch all student data from the database"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        # Fetch all students
        cursor.execute('SELECT * FROM students')
        students = cursor.fetchall()
        
        if include_modules:
            # For each student, fetch their modules
            student_data = []
            for student in students:
                student_id = student[0]
                
                # Fetch modules for this student
                cursor.execute('''
                SELECT m.module_type, sm.module_code, m.module_name
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                WHERE sm.student_id = ?
                ORDER BY m.module_type, sm.module_code
                ''', (student_id,))
                
                modules = cursor.fetchall()
                
                # Combine student info with modules
                student_data.append({
                    'student': student,
                    'modules': modules
                })
                
            conn.close()
            return student_data
        else:
            # Just return the students without modules
            conn.close()
            return students
            
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return []

@log_export(module="export", description="Exporting to CSV")
def export_to_csv():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return
    
    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return
    
    try:
        # Fetch student data
        students = fetch_student_data(include_modules=False)
        
        if not students:
            print("No student records found to export.")
            return
        
        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Get file path from user
        file_path = get_file_path('CSV', default_filename)
        
        # Define CSV headers based on the student table structure
        headers = [
            'Student ID', 'Email Address', 'Title', 'First Name', 'Middle Name', 'Last Name',
            'Gender', 'Date of Birth', 'Age', 'Course', 'Registration Datetime'
        ]
        
        # Write to CSV file
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for student in students:
                writer.writerow(student)
        
        print(f"Student records successfully exported to {file_path}")
        
    except Exception as e:
        logging.error(f"Error exporting to CSV: {e}")

@log_export(module="export", description="Exporting to excel")
def export_to_excel():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return
    
    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return
    
    try:
        # Fetch student data
        students = fetch_student_data(include_modules=True)
        
        if not students:
            print("No student records found to export.")
            return
        
        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # Get file path from user
        file_path = get_file_path('Excel', default_filename)
        
        # Create a pandas Excel writer
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Create student dataframe
            student_rows = []
            for student_data in students:
                student = student_data['student']
                student_rows.append({
                    'Student ID': student[0],
                    'Email Address': student[1],
                    'Title': student[2],
                    'First Name': student[3],
                    'Middle Name': student[4],
                    'Last Name': student[5],
                    'Gender': student[6],
                    'Date of Birth': student[7],
                    'Age': student[8],
                    'Course': student[9],
                    'Registration Datetime': student[10]
                })
            
            # Create student dataframe and write to Excel
            student_df = pd.DataFrame(student_rows)
            student_df.to_excel(writer, sheet_name='Students', index=False)
            
            # Create modules dataframe
            module_rows = []
            for student_data in students:
                student = student_data['student']
                modules = student_data['modules']
                
                for module in modules:
                    module_rows.append({
                        'Student ID': student[0],
                        'Student Name': f"{student[3]} {student[5]}",
                        'Module Type': module[0],
                        'Module Code': module[1],
                        'Module Name': module[2]
                    })
            
            # Create modules dataframe and write to Excel
            module_df = pd.DataFrame(module_rows)
            module_df.to_excel(writer, sheet_name='Modules', index=False)
        
        print(f"Student records successfully exported to {file_path}")
        
    except Exception as e:
        logging.error(f"Error exporting to Excel: {e}")

@log_export(module="export", description="Exporting to pdf")
def export_to_pdf():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return
    
    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return
    
    try:
        # Fetch student data
        students = fetch_student_data(include_modules=True)
        
        if not students:
            print("No student records found to export.")
            return
        
        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Get file path from user
        file_path = get_file_path('PDF', default_filename)
        
        # Create a PDF document
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Add title
        title = Paragraph("Student Records", styles['Title'])
        elements.append(title)
        
        # Process each student
        for student_data in students:
            student = student_data['student']
            modules = student_data['modules']
            
            # Add student information
            elements.append(Paragraph(f"Student ID: {student[0]}", styles['Heading2']))
            
            # Student data table
            student_info = [
                ['Field', 'Value'],
                ['Email', student[1]],
                ['Name', f"{student[2]} {student[3]} {student[4]} {student[5]}"],
                ['Gender', student[6]],
                ['Date of Birth', student[7]],
                ['Age', str(student[8])],
                ['Course', student[9]],
                ['Registration Date', student[10]]
            ]
            
            student_table = Table(student_info, colWidths=[150, 350])
            student_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (1, 0), 12),
                ('BACKGROUND', (0, 1), (1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(student_table)
            elements.append(Paragraph("Modules:", styles['Heading3']))
            
            # Module data table
            module_data = [['Type', 'Code', 'Name']]
            for module in modules:
                module_data.append([module[0], module[1], module[2]])
            
            module_table = Table(module_data, colWidths=[100, 100, 300])
            module_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (2, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (2, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (2, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (2, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(module_table)
            elements.append(Paragraph(" ", styles['Normal']))  # Add some space
        
        # Build the PDF
        doc.build(elements)
        
        print(f"Student records successfully exported to {file_path}")
        
    except Exception as e:
        logging.error(f"Error exporting to PDF: {e}")

@log_export(module="export", description="Exporting to text file")
def export_to_txt():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return
    
    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return
    
    try:
        # Fetch student data
        students = fetch_student_data(include_modules=True)
        
        if not students:
            print("No student records found to export.")
            return
        
        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Get file path from user
        file_path = get_file_path('TXT', default_filename)
        
        # Write to text file
        with open(file_path, 'w') as txtfile:
            txtfile.write("STUDENT RECORDS\n")
            txtfile.write("=" * 60 + "\n\n")
            
            for student_data in students:
                student = student_data['student']
                modules = student_data['modules']
                
                txtfile.write(f"Student ID: {student[0]}\n")
                txtfile.write(f"Email Address: {student[1]}\n")
                txtfile.write(f"Title: {student[2]}\n")
                txtfile.write(f"First Name: {student[3]}\n")
                txtfile.write(f"Middle Name: {student[4]}\n")
                txtfile.write(f"Last Name: {student[5]}\n")
                txtfile.write(f"Gender: {student[6]}\n")
                txtfile.write(f"Date of Birth: {student[7]}\n")
                txtfile.write(f"Age: {student[8]}\n")
                txtfile.write(f"Course: {student[9]}\n")
                txtfile.write(f"Registration Datetime: {student[10]}\n\n")
                
                txtfile.write("Modules:\n")
                txtfile.write("-" * 60 + "\n")
                txtfile.write(f"{'Type':<15} {'Code':<10} {'Name':<35}\n")
                txtfile.write("-" * 60 + "\n")
                
                for module in modules:
                    txtfile.write(f"{module[0]:<15} {module[1]:<10} {module[2]:<35}\n")
                
                txtfile.write("\n" + "=" * 60 + "\n\n")
        
        print(f"Student records successfully exported to {file_path}")
        
    except Exception as e:
        logging.error(f"Error exporting to TXT: {e}")

@log_menu_navigation(description="Displaying export menu")
def display_export_menu():
    """Display the export menu and handle user choices"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to access export functions.")
        return
    
    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export data.")
        return
    
    while True:
        print("\nExport Menu:")
        print("1. Export to CSV")
        print("2. Export to Excel")
        print("3. Export to PDF")
        print("4. Export to TXT")
        print("5. Return to Main Menu")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            export_to_csv()
        elif choice == '2':
            export_to_excel()
        elif choice == '3':
            export_to_pdf()
        elif choice == '4':
            export_to_txt()
        elif choice == '5':
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")

@log_create(module="modules", description="Creating new module")
def create_module():
    """Create a new module in the system"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create modules.")
        return False
    
    if not auth.check_permission('manage_modules'):
        print("You don't have permission to create modules.")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("\nCreate New Module")
        print("=" * 30)
        
        # Get module code
        while True:
            module_code = input("Enter module code (e.g., CS101): ").strip().upper()
            if not module_code:
                print("Error: Module code cannot be empty.")
                continue
            
            # Check if module code already exists
            cursor.execute("SELECT module_code FROM modules WHERE module_code = ?", (module_code,))
            if cursor.fetchone():
                print(f"Error: Module code '{module_code}' already exists.")
                continue
            
            # Validate module code format (letters followed by numbers)
            import re
            if not re.match(r'^[A-Z]{2,4}\d{3,4}$', module_code):
                print("Error: Module code must be 2-4 letters followed by 3-4 digits (e.g., CS101).")
                continue
            
            break
        
        # Get module name
        while True:
            module_name = input("Enter module name: ").strip()
            if not module_name:
                print("Error: Module name cannot be empty.")
                continue
            if len(module_name) < 3:
                print("Error: Module name must be at least 3 characters long.")
                continue
            break
        
        # Get module type
        print("\nModule Types:")
        print("1. Compulsory")
        print("2. Optional")
        print("3. CS (Computer Science specific)")
        print("4. DS (Data Science specific)")
        
        while True:
            type_choice = input("Select module type (1-4): ")
            if type_choice == '1':
                module_type = 'compulsory'
                break
            elif type_choice == '2':
                module_type = 'optional'
                break
            elif type_choice == '3':
                module_type = 'CS'
                break
            elif type_choice == '4':
                module_type = 'DS'
                break
            else:
                print("Invalid choice. Please select 1-4.")
        
        # Insert the module
        cursor.execute('''
        INSERT INTO modules (module_code, module_name, module_type)
        VALUES (?, ?, ?)
        ''', (module_code, module_name, module_type))
        
        conn.commit()
        conn.close()
        
        print(f"\nModule '{module_code} - {module_name}' created successfully!")
        input("\nPress Enter to continue...")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except Exception as e:
        logging.error(f"Error creating module: {e}")
        input("\nPress Enter to continue...")
        return False
    
@log_update(module="modules", description="Editing module")
def edit_module():
    """Edit an existing module"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to edit modules.")
        return False
    
    if not auth.check_permission('manage_modules'):
        print("You don't have permission to edit modules.")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("\nEdit Module")
        print("=" * 30)
        
        # Display all modules
        cursor.execute('''
        SELECT module_code, module_name, module_type 
        FROM modules 
        ORDER BY module_type, module_code
        ''')
        
        modules = cursor.fetchall()
        
        if not modules:
            print("No modules found in the system.")
            conn.close()
            input("\nPress Enter to continue...")
            return False
        
        print("\nExisting Modules:")
        print(f"{'Code':<10} {'Name':<40} {'Type':<15}")
        print("-" * 70)
        
        for module in modules:
            print(f"{module[0]:<10} {module[1]:<40} {module[2]:<15}")
        
        # Get module to edit
        while True:
            module_code = input("\nEnter module code to edit (or 'cancel' to exit): ").strip().upper()
            
            if module_code.lower() == 'cancel':
                print("Edit operation cancelled.")
                conn.close()
                return False
            
            cursor.execute("SELECT * FROM modules WHERE module_code = ?", (module_code,))
            module = cursor.fetchone()
            
            if not module:
                print(f"Error: Module code '{module_code}' not found.")
                continue
            
            break
        
        # Display current module information
        print(f"\nCurrent module information:")
        print(f"Code: {module[0]}")
        print(f"Name: {module[1]}")
        print(f"Type: {module[2]}")
        
        # Choose what to edit
        print("\nWhat would you like to edit?")
        print("1. Module Name")
        print("2. Module Type")
        print("3. Both")
        print("4. Cancel")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == '4':
            print("Edit operation cancelled.")
            conn.close()
            return False
        
        new_name = module[1]  # Keep current name by default
        new_type = module[2]  # Keep current type by default
        
        # Edit module name
        if choice in ['1', '3']:
            while True:
                new_name = input(f"Enter new module name (current: {module[1]}): ").strip()
                if not new_name:
                    print("Error: Module name cannot be empty.")
                    continue
                if len(new_name) < 3:
                    print("Error: Module name must be at least 3 characters long.")
                    continue
                break
        
        # Edit module type
        if choice in ['2', '3']:
            print("\nModule Types:")
            print("1. Compulsory")
            print("2. Optional")
            print("3. CS (Computer Science specific)")
            print("4. DS (Data Science specific)")
            
            while True:
                type_choice = input("Select new module type (1-4): ")
                if type_choice == '1':
                    new_type = 'compulsory'
                    break
                elif type_choice == '2':
                    new_type = 'optional'
                    break
                elif type_choice == '3':
                    new_type = 'CS'
                    break
                elif type_choice == '4':
                    new_type = 'DS'
                    break
                else:
                    print("Invalid choice. Please select 1-4.")
        
        # Update the module
        cursor.execute('''
        UPDATE modules 
        SET module_name = ?, module_type = ?
        WHERE module_code = ?
        ''', (new_name, new_type, module_code))
        
        # Update module name in student_modules table
        if new_name != module[1]:
            cursor.execute('''
            UPDATE student_modules 
            SET module_name = ?
            WHERE module_code = ?
            ''', (new_name, module_code))
        
        conn.commit()
        conn.close()
        
        print(f"\nModule '{module_code}' updated successfully!")
        print(f"New name: {new_name}")
        print(f"New type: {new_type}")
        input("\nPress Enter to continue...")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except Exception as e:
        logging.error(f"Error editing module: {e}")
        input("\nPress Enter to continue...")
        return False

@log_delete(module="modules", description="Deleting module")
def delete_module():
    """Delete a module from the system"""
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to delete modules.")
        return False
    
    if not auth.check_permission('manage_modules'):
        print("You don't have permission to delete modules.")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("\nDelete Module")
        print("=" * 30)
        
        # Display all modules
        cursor.execute('''
        SELECT module_code, module_name, module_type 
        FROM modules 
        ORDER BY module_type, module_code
        ''')
        
        modules = cursor.fetchall()
        
        if not modules:
            print("No modules found in the system.")
            conn.close()
            input("\nPress Enter to continue...")
            return False
        
        print("\nExisting Modules:")
        print(f"{'Code':<10} {'Name':<40} {'Type':<15}")
        print("-" * 70)
        
        for module in modules:
            print(f"{module[0]:<10} {module[1]:<40} {module[2]:<15}")
        
        # Get module to delete
        while True:
            module_code = input("\nEnter module code to delete (or 'cancel' to exit): ").strip().upper()
            
            if module_code.lower() == 'cancel':
                print("Delete operation cancelled.")
                conn.close()
                return False
            
            cursor.execute("SELECT * FROM modules WHERE module_code = ?", (module_code,))
            module = cursor.fetchone()
            
            if not module:
                print(f"Error: Module code '{module_code}' not found.")
                continue
            
            break
        
        # Check if module is assigned to any students
        cursor.execute('''
        SELECT COUNT(*) FROM student_modules WHERE module_code = ?
        ''', (module_code,))
        
        student_count = cursor.fetchone()[0]
        
        if student_count > 0:
            print(f"\nWarning: This module is currently assigned to {student_count} student(s).")
            print("Deleting this module will remove it from all student records.")
        
        # Confirm deletion
        print(f"\nAre you sure you want to delete module '{module_code} - {module[1]}'?")
        confirm = input("Type 'yes' to confirm: ").strip().lower()
        
        if confirm != 'yes':
            print("Delete operation cancelled.")
            conn.close()
            return False
        
        # Delete module from student_modules first (foreign key constraint)
        cursor.execute('''
        DELETE FROM student_modules WHERE module_code = ?
        ''', (module_code,))
        
        # Delete module from modules table
        cursor.execute('''
        DELETE FROM modules WHERE module_code = ?
        ''', (module_code,))
        
        conn.commit()
        conn.close()
        
        print(f"\nModule '{module_code}' deleted successfully!")
        if student_count > 0:
            print(f"Module removed from {student_count} student record(s).")
        input("\nPress Enter to continue...")
        return True
        
    except sqlite3.IntegrityError as e:
        print(f"Cannot delete module: {e}")
        print("This module may be referenced in other tables.")
        input("\nPress Enter to continue...")
        return False
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except Exception as e:
        logging.error(f"Error deleting module: {e}")
        input("\nPress Enter to continue...")
        return False

@log_menu_navigation(description="Displaying module management menu")
def display_module_management_menu():
    global auth
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to access module management.")
        return
    
    if not (auth.check_permission('manage_modules') or auth.check_permission('view_assigned_modules')):
        print("You don't have permission to access module management.")
        return
    
    while True:
        print("\nModule Management Menu:")
        print("=======================")
        
        # Show options based on permissions
        options = []
        option_num = 1
        
        if auth.check_permission('manage_modules'):
            print(f"{option_num}. Create new module")
            options.append('create_module')
            option_num += 1
            
            print(f"{option_num}. Edit module")
            options.append('edit_module')
            option_num += 1
            
            print(f"{option_num}. Delete module")
            options.append('delete_module')
            option_num += 1
        
        print(f"{option_num}. Search module by name")
        options.append('search_module_name')
        option_num += 1
        
        print(f"{option_num}. Search module by code")
        options.append('search_module_code')
        option_num += 1
        
        print(f"{option_num}. Return to Main Menu")
        
        choice = input("Enter your choice: ")
        
        try:
            choice_num = int(choice)
            
            # Handle the choice based on dynamic menu
            if choice_num > 0 and choice_num <= len(options):
                selected_option = options[choice_num - 1]
                
                if selected_option == 'create_module':
                    create_module()
                elif selected_option == 'edit_module':
                    edit_module()
                elif selected_option == 'delete_module':
                    delete_module()
                elif selected_option == 'search_module_name':
                    search_module_by_module_name()
                elif selected_option == 'search_module_code':
                    search_module_by_module_code()
            elif choice_num == option_num:  # Return to Main Menu
                return
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

def launch_chatbot():
    from university_system.utils.ai.university_chatbot import UniversityChatbot
    chatbot = UniversityChatbot()
    chatbot.run()

@log_menu_navigation(description="Displaying student record menu")
def display_student_records_menu():
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access student records.")
        return
    
    while True:
        print("\nStudent Records Menu:")
        print("=====================")
        
        # Show options based on permissions
        option_num = 1
        options = {}
        
        if auth.check_permission('create_student'):
            print(f"{option_num}. Create student record")
            options[str(option_num)] = 'create_student'
            option_num += 1
        
        if auth.check_permission('view_any_student') or auth.check_permission('view_own_record'):
            print(f"{option_num}. View student records")
            options[str(option_num)] = 'view_student'
            option_num += 1
        
        if auth.check_permission('update_any_student') or auth.check_permission('update_own_profile'):
            print(f"{option_num}. Update student record")
            options[str(option_num)] = 'update_student'
            option_num += 1
        
        if auth.check_permission('delete_any_student'):
            print(f"{option_num}. Delete student record")
            options[str(option_num)] = 'delete_student'
            option_num += 1
        
        if auth.check_permission('view_any_student'):
            print(f"{option_num}. Search student by first name")
            options[str(option_num)] = 'search_first_name'
            option_num += 1
            
            print(f"{option_num}. Search student by last name")
            options[str(option_num)] = 'search_last_name'
            option_num += 1
            
            print(f"{option_num}. Search student by ID")
            options[str(option_num)] = 'search_id'
            option_num += 1
            
            print(f"{option_num}. Search student by registration date")
            options[str(option_num)] = 'search_date'
            option_num += 1
        
        print(f"{option_num}. Return to Main Menu")
        
        choice = input("Enter your choice: ")
        
        if choice in options:
            action = options[choice]
            
            if action == 'create_student':
                create_student_record()
            elif action == 'view_student':
                view_student_record()
            elif action == 'update_student':
                update_student_record()
            elif action == 'delete_student':
                delete_student_record()
            elif action == 'search_first_name':
                search_student_by_first_name()
            elif action == 'search_last_name':
                search_student_by_last_name()
            elif action == 'search_id':
                search_student_by_student_id()
            elif action == 'search_date':
                search_student_by_registration_date()
        elif choice == str(option_num):
            return
        else:
            print("Invalid choice or insufficient permissions. Please try again.")

def display_student_record(student):
    """Helper function to display a student record"""
    if not student:
        print("Invalid student record.")
        return
    
    print("\n" + "=" * 40)
    print("Student Record:")
    print("=" * 40)
    print(f"Student ID: {student[0]}")
    print(f"Email: {student[1]}")
    print(f"Title: {student[2]}")
    print(f"First Name: {student[3]}")
    print(f"Middle Name: {student[4]}")
    print(f"Last Name: {student[5]}")
    print(f"Gender: {student[6]}")
    print(f"Date of Birth: {student[7]}")
    print(f"Age: {student[8]}")
    print(f"Course: {student[9]}")
    print(f"Registration Date/Time: {student[10]}")
    
    # Fetch and display modules
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT m.module_type, sm.module_code, m.module_name
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
            ORDER BY m.module_type, sm.module_code
            ''', (student[0],))
            modules = cursor.fetchall()
            
            if modules:
                print("\nModules:")
                print("-" * 40)
                for module in modules:
                    print(f"{module[0]}: {module[1]} - {module[2]}")
            conn.close()
    except sqlite3.Error as e:
        logging.error(f"Error fetching modules: {e}")
    
    print("=" * 40 + "\n")

# Add this to your main menu function
def display_admin_tools_menu():
    """Display admin tools menu for database maintenance"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access admin tools.")
        return
    
    if auth.current_user['role'] != 'admin':
        print("Only administrators can access these tools.")
        return
    
    while True:
        print("\nAdmin Tools:")
        print("============")
        print("1. Validate Database Integrity")
        print("2. Fix Duplicate Emails")
        print("3. Fix Orphaned Records")
        print("4. Emergency Database Fix")
        print("5. View Database Statistics")
        print("6. Back to Main Menu")
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            validate_database_integrity()
        elif choice == '2':
            fix_duplicate_emails()
        elif choice == '3':
            auth.fix_database_consistency()
        elif choice == '4':
            emergency_fix_database()
        elif choice == '5':
            display_database_statistics()
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def display_database_statistics():
    """Display database statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("\nDatabase Statistics:")
        print("=" * 40)
        
        # Count records in main tables
        tables = ['students', 'users', 'user_accounts', 'student_modules', 'modules']
        
        for table in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                print(f"{table.capitalize()}: {count} records")
            except sqlite3.Error:
                print(f"{table.capitalize()}: Table not found")
        
        # Check for duplicates
        print("\nDuplicate Check:")
        cursor.execute('SELECT COUNT(DISTINCT email) as unique_emails, COUNT(*) as total_users FROM users')
        unique_emails, total_users = cursor.fetchone()
        
        if unique_emails != total_users:
            print(f"⚠️  Email duplicates: {total_users - unique_emails} duplicate(s) found")
        else:
            print("✅ No email duplicates found")
        
        cursor.execute('SELECT COUNT(DISTINCT username) as unique_usernames, COUNT(*) as total_users FROM users')
        unique_usernames, total_users = cursor.fetchone()
        
        if unique_usernames != total_users:
            print(f"⚠️  Username duplicates: {total_users - unique_usernames} duplicate(s) found")
        else:
            print("✅ No username duplicates found")
        
        # Check for orphaned records
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
        
        print(f"\nOrphaned Records:")
        print(f"Users without accounts: {orphaned_users}")
        print(f"Accounts without users: {orphaned_accounts}")
        
        conn.close()
        print("=" * 40)
        
    except sqlite3.Error as e:
        logging.error(f"Error retrieving database statistics: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

def create_trip_calendar_event(trip_id, event_details=None):
    """Create a calendar event for a trip"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create trip events.")
        return False
    
    if not auth.check_permission('manage_schedules'):
        print("You don't have permission to create calendar events.")
        return False
    
    try:
        # Get trip details
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM trips WHERE id = ?', (trip_id,))
        trip = cursor.fetchone()
        
        if not trip:
            print("Trip not found.")
            conn.close()
            return False
        
        # Create calendar event using the academic calendar system
        from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager, CalendarConfig
        
        config = CalendarConfig()
        calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)
        
        # Create event details
        event_name = event_details.get('name', f"Trip: {trip[1]}") if event_details else f"Trip: {trip[1]}"
        event_description = event_details.get('description', f"Trip to {trip[3]} - {trip[2] or 'No description'}") if event_details else f"Trip to {trip[3]}"
        
        # Create the calendar event
        result = calendar_manager.add_event(
            name=event_name,
            date_start=trip[4],  # start_date
            date_end=trip[5],    # end_date
            description=event_description,
            event_type='Trip'
        )
        
        if result['success']:
            # Link trip to event
            cursor.execute('''
                INSERT OR IGNORE INTO trip_calendar_events (trip_id, event_id, event_type, created_at)
                VALUES (?, ?, ?, ?)
            ''', (trip_id, result['event_id'], 'trip_event', datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Calendar event created successfully!")
            print(f"Event ID: {result['event_id']}")
            return True
        else:
            print(f"✗ Failed to create calendar event: {result.get('message', 'Unknown error')}")
            conn.close()
            return False
            
    except Exception as e:
        print(f"Error creating trip calendar event: {e}")
        logging.error(f"Error creating trip calendar event: {e}")
        return False

def view_integrated_dashboard():
    """View integrated dashboard showing both calendar and trip data"""
    global auth
    
    # Add this import at the start of the function
    from datetime import datetime, timedelta
    
    if not auth or not auth.current_user:
        print("You must be logged in to view the dashboard.")
        return
        
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("\n" + "="*60)
        print("INTEGRATED ACADEMIC DASHBOARD")
        print("="*60)
        print(f"User: {auth.current_user['username']} ({auth.current_user['role']})")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get upcoming calendar events
        try:
            from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager, CalendarConfig
            config = CalendarConfig()
            calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)
            
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            upcoming_events = calendar_manager.get_events_by_date_range(start_date, end_date)
            
            print(f"\n📅 UPCOMING EVENTS (next 30 days): {len(upcoming_events)}")
            if upcoming_events:
                for event in upcoming_events[:5]:  # Show first 5
                    event_date = event.get('date') or event.get('date_start', 'TBD')
                    print(f"   • {event_date}: {event['name']} ({event['event_type']})")
                if len(upcoming_events) > 5:
                    print(f"   ... and {len(upcoming_events) - 5} more events")
            else:
                print("   No upcoming events")
                
        except Exception as e:
            print(f"\n📅 CALENDAR: Error loading calendar data - {e}")
        
        # Get upcoming trips
        cursor.execute('''
        SELECT t.*, COUNT(tp.id) as participant_count
        FROM trips t
        LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
        WHERE t.start_date >= date('now')
        GROUP BY t.id
        ORDER BY t.start_date
        LIMIT 10
        ''')
        
        upcoming_trips = cursor.fetchall()
        
        print(f"\n🎒 UPCOMING TRIPS: {len(upcoming_trips)}")
        if upcoming_trips:
            for trip in upcoming_trips[:5]:  # Show first 5
                print(f"   • {trip[4]}: {trip[1]} to {trip[3]}")
                print(f"     Participants: {trip[-1]}/{trip[6]} - Status: {trip[8].title()}")
            if len(upcoming_trips) > 5:
                print(f"   ... and {len(upcoming_trips) - 5} more trips")
        else:
            print("   No upcoming trips")
        
        # Get integration statistics
        cursor.execute('SELECT COUNT(*) FROM trip_calendar_events')
        linked_events = cursor.fetchone()[0]
        
        print(f"\n🔗 INTEGRATION STATUS:")
        print(f"   Trip-Calendar links: {linked_events}")
        
        print("="*60)
        conn.close()
        
    except Exception as e:
        print(f"Error loading dashboard: {e}")
        logging.error(f"Error loading integrated dashboard: {e}")

def sync_trips_with_calendar():
    """Sync all trips with calendar events"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to sync trips.")
        return False
    
    if not auth.check_permission('manage_schedules'):
        print("You don't have permission to sync calendar events.")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Get trips without calendar events
        cursor.execute('''
        SELECT t.* FROM trips t
        LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
        WHERE tce.trip_id IS NULL AND t.status IN ('open', 'planning')
        ''')
        
        trips_to_sync = cursor.fetchall()
        
        if not trips_to_sync:
            print("No trips found that need calendar events.")
            conn.close()
            return True
        
        print(f"Found {len(trips_to_sync)} trips to sync with calendar...")
        
        synced_count = 0
        
        for trip in trips_to_sync:
            event_details = {
                'name': f"Trip: {trip[1]}",
                'description': f"Trip to {trip[3]} - {trip[2] or 'No description'}"
            }
            
            if create_trip_calendar_event(trip[0], event_details):
                synced_count += 1
                print(f"  ✅ Synced: {trip[1]}")
            else:
                print(f"  ✗ Failed: {trip[1]}")
        
        conn.close()
        print(f"\nSync completed: {synced_count}/{len(trips_to_sync)} trips synced successfully")
        return True
        
    except Exception as e:
        print(f"Error syncing trips: {e}")
        logging.error(f"Error syncing trips with calendar: {e}")
        return False

def link_trip_to_event_manually():
    """Manually link a trip to a calendar event"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to link trips.")
        return False
    
    if not auth.check_permission('manage_schedules'):
        print("You don't have permission to create calendar events.")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Get trips without calendar events
        cursor.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date
        FROM trips t
        LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
        WHERE tce.trip_id IS NULL
        ORDER BY t.start_date
        ''')
        
        available_trips = cursor.fetchall()
        
        if not available_trips:
            print("No trips available for linking (all may already be linked)")
            conn.close()
            return False
        
        print("\nAvailable Trips for Calendar Event Creation:")
        print("-" * 70)
        for trip in available_trips:
            print(f"{trip[0]}: {trip[1]} to {trip[2]} ({trip[3]} - {trip[4]})")
        
        trip_id = input("\nEnter Trip ID to create calendar event for: ").strip()
        
        try:
            trip_id = int(trip_id)
        except ValueError:
            print("Invalid trip ID.")
            conn.close()
            return False
        
        # Verify trip selection
        selected_trip = None
        for trip in available_trips:
            if trip[0] == trip_id:
                selected_trip = trip
                break
        
        if not selected_trip:
            print("Invalid trip selection.")
            conn.close()
            return False
        
        # Get event details
        print(f"\nCreating calendar event for: {selected_trip[1]}")
        event_name = input(f"Event name (press Enter for default): ").strip()
        description = input("Event description (optional): ").strip()
        
        event_details = {}
        if event_name:
            event_details['name'] = event_name
        if description:
            event_details['description'] = description
        
        conn.close()
        return create_trip_calendar_event(trip_id, event_details)
        
    except Exception as e:
        print(f"Error linking trip: {e}")
        logging.error(f"Error linking trip to event: {e}")
        return False

def view_trip_calendar_links():
    """View existing trip-calendar links"""
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT t.trip_name, t.destination, t.start_date, t.end_date,
               e.name as event_name, e.event_type, tce.created_at
        FROM trip_calendar_events tce
        JOIN trips t ON tce.trip_id = t.id
        JOIN events e ON tce.event_id = e.id
        ORDER BY t.start_date
        ''')
        
        links = cursor.fetchall()
        
        if not links:
            print("No trip-calendar links found.")
        else:
            print("\nTrip-Calendar Event Links:")
            print("=" * 90)
            print(f"{'Trip':<25} {'Destination':<15} {'Dates':<20} {'Calendar Event':<20} {'Created':<12}")
            print("-" * 90)
            
            for link in links:
                trip_name, destination, start_date, end_date, event_name, event_type, created_at = link
                dates = f"{start_date} to {end_date}"
                created = created_at[:10]  # Just the date part
                
                print(f"{trip_name[:24]:<25} {destination[:14]:<15} {dates[:19]:<20} {event_name[:19]:<20} {created:<12}")
            
            print("=" * 90)
        
        conn.close()
        
    except Exception as e:
        print(f"Error viewing links: {e}")
        logging.error(f"Error viewing trip-calendar links: {e}")

@log_menu_navigation(description="Displaying integrated academic menu")
def display_integrated_academic_menu():
    """Display the integrated academic management menu"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the integrated academic system.")
        return
    
    # Check if user has access to either system
    calendar_access = (auth.check_permission('manage_schedules') or 
                      auth.check_permission('view_own_timetable') or 
                      auth.check_permission('export_data'))
    
    trips_access = (auth.check_permission('view_trips') or 
                   auth.check_permission('create_trips') or 
                   auth.check_permission('manage_trips') or 
                   auth.check_permission('register_for_trips'))
    
    if not (calendar_access or trips_access):
        print("You don't have permission to access academic management systems.")
        return
    
    while True:
        print(f"\nIntegrated Academic Management System")
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")
        print("=" * 60)
        
        options = []
        option_num = 1
        
        # Dashboard (available to all users with either system access)
        if calendar_access or trips_access:
            print(f"{option_num}. View Integrated Dashboard")
            options.append(('dashboard', view_integrated_dashboard))
            option_num += 1
        
        # Calendar System
        if calendar_access:
            print(f"{option_num}. Academic Calendar Management")
            options.append(('calendar', display_academic_calendar_menu))
            option_num += 1
        
        # Trip System
        if trips_access:
            print(f"{option_num}. Trip Management")
            options.append(('trips', display_trip_management_menu))
            option_num += 1
        
        # Integration Features (only for users with manage permissions)
        if auth.check_permission('manage_schedules') and trips_access:
            print(f"{option_num}. Create Calendar Event for Trip")
            options.append(('link', link_trip_to_event_manually))
            option_num += 1
            
            print(f"{option_num}. Sync All Trips with Calendar")
            options.append(('sync', sync_trips_with_calendar))
            option_num += 1
            
            print(f"{option_num}. View Trip-Calendar Links")
            options.append(('view_links', view_trip_calendar_links))
            option_num += 1
        
        print(f"{option_num}. Return to Main Menu")
        
        try:
            choice = int(input(f"\nEnter your choice (1-{option_num}): "))
            
            if choice == option_num:  # Return to main menu
                break
            elif 1 <= choice <= len(options):
                action_name, action_func = options[choice - 1]
                try:
                    if action_name in ['sync', 'link']:
                        success = action_func()
                        if success:
                            print("Operation completed successfully!")
                        else:
                            print("Operation failed or was cancelled.")
                    else:
                        action_func()
                except Exception as e:
                    print(f"Error executing {action_name}: {e}")
                    logging.error(f"Error in {action_name}: {e}")
                
                if action_name not in ['calendar', 'trips']:
                    input("\nPress Enter to continue...")
            else:
                print("Invalid choice. Please try again.")
                
        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            logging.error(f"Unexpected error in integrated menu: {e}")

def display_analytics_menu():
    """Display student analytics dashboard"""
    analytics = StudentAnalytics()
    analytics.display_main_menu()

def display_batch_menu():
    """Standalone function to display batch operations menu for import into main.py"""
    batch_manager = BatchOperationManager()
    batch_manager.display_batch_menu()

@log_menu_navigation(description="Displaying main menu")
def display_menu():
    global auth

    # Link auth to Student Union (only if auth exists)
    try:
        _link_auth_to_student_union(auth)
    except NameError:
        # auth not created yet; skip silently or initialize it before calling display_menu
        pass

    # One-time system initialization
    if not getattr(display_menu, "_system_init_complete", False):
        print("Performing one-time system initialization...")

        # Clean up any hanging connections first
        cleanup_database_on_startup()

        # Initialize all databases
        if not init_all_databases():
            print("Failed to initialize databases. Exiting.")
            return

        display_menu._system_init_complete = True
        print("System initialization completed successfully!")
    
    # Initialize authentication system if not already done
    if auth is None:
        try:
            auth = UserAuth()
            # Ensure auth object has all required attributes
            safe_auth_check(auth)
            # Set the global auth instance for other modules
            set_auth_instance(auth)
        except Exception as e:
            print(f"Error initializing authentication: {e}")
            print("Creating minimal auth object...")
            # Create minimal auth object
            class MinimalAuth:
                def __init__(self):
                    self.current_user = None
                    self.last_activity = None
                    self.session_timeout = 30
                    self.login_attempts = {}
                    self.max_attempts = 5
                    self.lockout_time = 15
                    
                def check_session(self):
                    return False
                    
                def check_permission(self, perm):
                    return False
                    
                def logout(self):
                    self.current_user = None
            
            auth = MinimalAuth()
        
        init_auth_for_modules()  # Initialize auth for other modules

    # Setup permissions for various modules (ONLY ONCE)
    if not hasattr(display_menu, '_permissions_setup'):
        try:
            setup_alumni_permissions()
            setup_internship_permissions()
            setup_student_union_permissions(auth)
            add_finance_permissions()
            setup_shop_permissions(auth)
            setup_trip_permissions()  # Add this line

            # Add plagiarism permissions AFTER UserAuth is fully initialized
            try:
                from university_system.infrastructure.auth.user_authentication import add_plagiarism_permissions
                created_permissions = add_plagiarism_permissions(auth)
                if created_permissions:
                    print(f"✅ Added plagiarism permissions: {', '.join(created_permissions)}")
                else:
                    print("✅ Plagiarism permissions already exist")
            except Exception as e:
                logging.warning(f"Could not add plagiarism permissions: {e}")
                
        except Exception as e:
            logging.warning(f"Error setting up permissions: {e}")
        
        # Mark permissions as setup
        display_menu._permissions_setup = True

    # Initialize plagiarism checker integration (ONLY ONCE)
    if not hasattr(display_menu, '_plagiarism_initialized'):
        try:
            integrate_plagiarism_checker_with_main()
            display_menu._plagiarism_initialized = True
            print("✅ Plagiarism checker integration completed")
        except Exception as e:
            logging.warning(f"Failed to initialize plagiarism checker: {e}")
            display_menu._plagiarism_initialized = True
            print("⚠️ Plagiarism checker integration had issues")
    
    # Main application loop
    while True:
        # Check if user is logged in - FIXED VERSION
        if not safe_auth_check(auth) or not auth.current_user:
            # User is not logged in, show authentication menu first
            print("\nPlease log in to access the system.")
            try:
                auth = display_auth_menu()
                if auth is None:
                    # Create a new auth object if none was returned
                    auth = UserAuth()
                    safe_auth_check(auth)
                # Set the global auth instance after login
                set_auth_instance(auth)
                init_auth_for_modules()  # Reinitialize auth for other modules
                # Loop back to check if login was successful
                continue
            except Exception as e:
                print(f"Error in authentication menu: {e}")
                print("Please try again or contact an administrator.")
                break
        
        # User is now logged in, show main menu
        try:
            print(f"\nLogged in as: {auth.current_user['username']} ({auth.current_user['role']})")
        except (AttributeError, TypeError):
            print("\nLogged in (user details unavailable)")

        # NEW CONSOLIDATED MENU STRUCTURE
        print("\n" + "="*60)
        print("          UNIVERSITY MANAGEMENT SYSTEM")
        print("="*60)

        option_map = {}
        option_num = 1

        # 📚 ACADEMIC & LEARNING
        print("\n📚 ACADEMIC & LEARNING")
        print(f"{option_num}. Student Records")
        option_map[str(option_num)] = "student_records"
        option_num += 1

        print(f"{option_num}. Course Management")
        option_map[str(option_num)] = "course_management"
        option_num += 1

        print(f"{option_num}. Academic Calendar")
        option_map[str(option_num)] = "integrated_academic"
        option_num += 1

        print(f"{option_num}. Grade & Performance Tracking")
        option_map[str(option_num)] = "grades"
        option_num += 1

        print(f"{option_num}. LMS (Learning Management System)")
        option_map[str(option_num)] = "lms_system"
        option_num += 1

        print(f"{option_num}. Advanced Attendance System")
        option_map[str(option_num)] = "advanced_attendance"
        option_num += 1

        print(f"{option_num}. Smart Timetable Optimizer")
        option_map[str(option_num)] = "timetable_optimizer"
        option_num += 1

        print(f"{option_num}. Course Evaluation System")
        option_map[str(option_num)] = "course_evaluation"
        option_num += 1

        print(f"{option_num}. Virtual Classroom Platform")
        option_map[str(option_num)] = "virtual_classroom"
        option_num += 1

        print(f"{option_num}. Predictive Analytics & Early Alerts")
        option_map[str(option_num)] = "predictive_analytics"
        option_num += 1

        # 👥 STUDENT SERVICES
        print("\n👥 STUDENT SERVICES")
        print(f"{option_num}. Housing Accommodation Management")
        option_map[str(option_num)] = "housing_accommodations"
        option_num += 1

        print(f"{option_num}. University Health Portal")
        option_map[str(option_num)] = "health_portal"
        option_num += 1

        print(f"{option_num}. Student Union Portal")
        option_map[str(option_num)] = "student_union_portal"
        option_num += 1

        print(f"{option_num}. Career Services Platform")
        option_map[str(option_num)] = "career_services"
        option_num += 1

        print(f"{option_num}. Financial Aid & Scholarships")
        option_map[str(option_num)] = "financial_aid"
        option_num += 1

        print(f"{option_num}. Student Success Early Warning")
        option_map[str(option_num)] = "early_warning_system"
        option_num += 1

        print(f"{option_num}. Student Support & Helpdesk")
        option_map[str(option_num)] = "student_support"
        option_num += 1

        # 💼 BUSINESS OPERATIONS
        print("\n💼 BUSINESS OPERATIONS")
        print(f"{option_num}. Finance Management")
        option_map[str(option_num)] = "finance_management"
        option_num += 1

        print(f"{option_num}. Library Management")
        option_map[str(option_num)] = "library"
        option_num += 1

        print(f"{option_num}. Facilities & Space Management")
        option_map[str(option_num)] = "facilities_management"
        option_num += 1

        print(f"{option_num}. Transportation & Parking Management")
        option_map[str(option_num)] = "transportation_parking"
        option_num += 1

        # 💬 COMMUNICATION & SUPPORT
        print("\n💬 COMMUNICATION & SUPPORT")
        print(f"{option_num}. Unified Communication Hub")
        option_map[str(option_num)] = "communication_hub"
        option_num += 1

        # 🏛️ INSTITUTIONAL
        print("\n🏛️ INSTITUTIONAL")
        print(f"{option_num}. Admissions & Recruitment CRM")
        option_map[str(option_num)] = "admissions_crm"
        option_num += 1

        print(f"{option_num}. Alumni Relations & Engagement")
        option_map[str(option_num)] = "alumni_relations"
        option_num += 1

        print(f"{option_num}. Research & Grants Management")
        option_map[str(option_num)] = "research_grants"
        option_num += 1

        print(f"{option_num}. Campus Events Hub")
        option_map[str(option_num)] = "campus_events"
        option_num += 1

        # 🔧 TECHNOLOGY & ANALYTICS
        print("\n🔧 TECHNOLOGY & ANALYTICS")
        print(f"{option_num}. Administrative Tools")
        option_map[str(option_num)] = "administrative_tools"
        option_num += 1

        print(f"{option_num}. Security & Compliance Dashboard")
        option_map[str(option_num)] = "security_dashboard"
        option_num += 1

        print(f"{option_num}. Data & Document Management")
        option_map[str(option_num)] = "data_document_management"
        option_num += 1

        print(f"{option_num}. AI-Powered Features")
        option_map[str(option_num)] = "ai_features"
        option_num += 1

        print(f"{option_num}. Business Intelligence Reports")
        option_map[str(option_num)] = "business_intelligence"
        option_num += 1

        print(f"{option_num}. Integration Marketplace")
        option_map[str(option_num)] = "integration_marketplace"
        option_num += 1

        print(f"{option_num}. Blockchain Credentials & Digital Badges")
        option_map[str(option_num)] = "blockchain_credentials"
        option_num += 1

        # 📱 INFRASTRUCTURE
        print("\n📱 INFRASTRUCTURE")
        print(f"{option_num}. Mobile App (PWA) Infrastructure")
        option_map[str(option_num)] = "mobile_app_pwa"
        option_num += 1

        # ⚙️ SYSTEM
        print("\n⚙️ SYSTEM")
        print(f"{option_num}. Switch to GUI Interface")
        option_map[str(option_num)] = "switch_to_gui"
        option_num += 1

        print(f"{option_num}. Logout")
        option_map[str(option_num)] = "logout"
        option_num += 1

        print(f"{option_num}. Exit")
        option_map[str(option_num)] = "exit"
        max_option = option_num

        print("="*60)

        # Get user choice
        choice = input("\nEnter your choice: ")

        # Route to appropriate menu
        if choice in option_map:
            option = option_map[choice]

            if option == "student_records":
                display_student_records_menu()
            elif option == "course_management":
                display_course_management_menu(auth)
            elif option == "integrated_academic":
                display_integrated_academic_menu()
            elif option == "grades":
                display_enhanced_grade_menu()
            elif option == "lms_system":
                display_lms_menu(auth)
            elif option == "advanced_attendance":
                display_advanced_attendance_menu()
            elif option == "timetable_optimizer":
                display_timetable_optimizer_menu()
            elif option == "course_evaluation":
                display_course_evaluation_menu(auth)
            elif option == "virtual_classroom":
                display_virtual_classroom_menu(auth)
            elif option == "predictive_analytics":
                predictive_analytics_menu()
            elif option == "housing_accommodations":
                display_housing_accommodation_menu()
            elif option == "health_portal":
                display_health_portal_menu(auth)
            elif option == "student_union_portal":
                display_student_union_menu()
            elif option == "career_services":
                display_career_services_menu(auth)
            elif option == "financial_aid":
                display_financial_aid_menu(auth)
            elif option == "early_warning_system":
                display_early_warning_menu(auth)
            elif option == "student_support":
                display_support_menu()
            elif option == "finance_management":
                display_finance_menu()
            elif option == "library":
                display_library_menu()
            elif option == "facilities_management":
                display_facilities_management_menu(auth)
            elif option == "transportation_parking":
                display_transportation_parking_menu(auth)
            elif option == "communication_hub":
                display_communication_hub_menu(auth)
            elif option == "admissions_crm":
                display_admissions_crm_menu(auth)
            elif option == "alumni_relations":
                display_alumni_relations_menu()
            elif option == "research_grants":
                display_research_grants_menu(auth)
            elif option == "campus_events":
                display_campus_events_menu(auth)
            elif option == "administrative_tools":
                display_administrative_tools_menu(auth)
            elif option == "security_dashboard":
                if SECURITY_DASHBOARD_CLI_AVAILABLE:
                    # Check if user is admin
                    if auth.current_user and auth.current_user.get('role') == 'admin':
                        user_id = auth.current_user.get('id', 1)
                        display_security_dashboard_menu(user_id)
                    else:
                        print("\n❌ Access Denied: Administrator access required for Security Dashboard")
                        input("Press Enter to continue...")
                else:
                    print("\n❌ Security Dashboard is not available")
                    input("Press Enter to continue...")
            elif option == "data_document_management":
                display_data_document_management_menu(auth)
            elif option == "ai_features":
                display_ai_features_menu(auth)
            elif option == "business_intelligence":
                display_business_intelligence_menu(auth)
            elif option == "integration_marketplace":
                display_integration_marketplace_menu(auth)
            elif option == "blockchain_credentials":
                display_blockchain_credentials_menu(auth)
            elif option == "mobile_app_pwa":
                display_mobile_app_pwa_menu(auth)
            elif option == "switch_to_gui":
                switch_to_gui(auth)
            elif option == "logout":
                cleanup_database_connections()
                auth.logout()
            elif option == "exit":
                cleanup_database_connections()
                if auth and auth.current_user:
                    auth.logout()
                print("\nThank you for using the University Management System. Goodbye!")
                return
            else:
                print("Invalid choice. Please try again.")
        else:
            print("Invalid choice. Please try again.")

            
def cleanup_connections():
    """Clean up any hanging database connections."""
    try:
        import gc
        gc.collect()
    except Exception as e:
        logging.error(f"cleanup_connections() failed: {e}")

def display_finance_menu():
    """Display the finance management CLI menu"""
    print("\n" + "="*50)
    print("         FINANCE MANAGEMENT SYSTEM")
    print("="*50)
    print("1. View Financial Reports")
    print("2. Manage Student Fees")
    print("3. Process Payments")
    print("4. Financial Aid Management")
    print("5. Budget Management")
    print("6. Generate Reports")
    print("7. System Settings")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()

            if choice == '1':
                print("\n📊 Financial Reports - Feature not yet implemented in CLI")
                print("Please use the GUI version for full functionality.")
            elif choice == '2':
                print("\n💳 Student Fees Management - Feature not yet implemented in CLI")
                print("Please use the GUI version for full functionality.")
            elif choice == '3':
                print("\n💰 Payment Processing - Feature not yet implemented in CLI")
                print("Please use the GUI version for full functionality.")
            elif choice == '4':
                print("\n🎓 Financial Aid Management - Feature not yet implemented in CLI")
                print("Please use the GUI version for full functionality.")
            elif choice == '5':
                print("\n💼 Budget Management - Feature not yet implemented in CLI")
                print("Please use the GUI version for full functionality.")
            elif choice == '6':
                print("\n📈 Report Generation - Feature not yet implemented in CLI")
                print("Please use the GUI version for full functionality.")
            elif choice == '7':
                print("\n⚙️ System Settings - Feature not yet implemented in CLI")
                print("Please use the GUI version for full functionality.")
            elif choice == '8':
                print("Returning to main menu...")
                break
            else:
                print("❌ Invalid choice. Please enter a number between 1 and 8.")

        except KeyboardInterrupt:
            print("\n\nExiting finance menu...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

def display_virtual_classroom_menu(auth):
    """Display the virtual classroom management CLI menu"""
    print("\n" + "="*50)
    print("      VIRTUAL CLASSROOM MANAGEMENT")
    print("="*50)
    print("1. Create Virtual Classroom")
    print("2. Schedule Virtual Session")
    print("3. Manage Participants")
    print("4. View Recordings")
    print("5. Create Polls/Quizzes")
    print("6. Manage Breakout Rooms")
    print("7. View Chat Messages")
    print("8. Session Analytics")
    print("9. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-9): ").strip()

            if choice == '1':
                # Create Virtual Classroom
                try:
                    session_name = input("Enter session name: ").strip()
                    platform = input("Enter platform (zoom/teams/meet/webrtc): ").strip()
                    meeting_link = input("Enter meeting link: ").strip()

                    classroom_mgr = VirtualClassroomManager()
                    classroom_id = classroom_mgr.create_classroom(
                        session_name=session_name,
                        instructor_id=auth.current_user['user_id'],
                        platform=platform,
                        meeting_link=meeting_link
                    )
                    print(f"✅ Virtual classroom created successfully! Classroom ID: {classroom_id}")
                except Exception as e:
                    print(f"❌ Error creating classroom: {e}")
            elif choice == '2':
                print("\n📅 Schedule Virtual Session - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '3':
                print("\n👥 Manage Participants - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '4':
                print("\n📹 View Recordings - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '5':
                print("\n📊 Create Polls/Quizzes - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '6':
                print("\n🚪 Manage Breakout Rooms - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '7':
                print("\n💬 View Chat Messages - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '8':
                print("\n📈 Session Analytics - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '9':
                print("Returning to main menu...")
                break
            else:
                print("❌ Invalid choice. Please enter a number between 1 and 9.")

        except KeyboardInterrupt:
            print("\n\nExiting virtual classroom menu...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def display_financial_aid_menu(auth):
    """Display the financial aid & scholarships CLI menu"""
    print("\n" + "="*50)
    print("    FINANCIAL AID & SCHOLARSHIP MANAGEMENT")
    print("="*50)
    print("1. View Financial Aid Applications")
    print("2. Submit FAFSA Data")
    print("3. Create Aid Package")
    print("4. Manage Scholarships")
    print("5. Review Scholarship Applications")
    print("6. Award Scholarship")
    print("7. Disbursement Management")
    print("8. Compliance Reports")
    print("9. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-9): ").strip()

            if choice == '1':
                print("\n📋 View Financial Aid Applications - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '2':
                # Submit FAFSA Data
                try:
                    student_id = int(input("Enter student ID: ").strip())
                    academic_year = input("Enter academic year (e.g., 2024-2025): ").strip()
                    efc = float(input("Enter Expected Family Contribution (EFC): ").strip())

                    aid_mgr = FinancialAidManager()
                    from datetime import date
                    aid_mgr.import_fafsa_data(
                        student_id=student_id,
                        academic_year=academic_year,
                        efc=efc,
                        submission_date=date.today()
                    )
                    print(f"✅ FAFSA data imported successfully!")
                except Exception as e:
                    print(f"❌ Error importing FAFSA data: {e}")
            elif choice == '3':
                print("\n💰 Create Aid Package - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '4':
                print("\n🎓 Manage Scholarships - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '5':
                print("\n📝 Review Scholarship Applications - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '6':
                print("\n🏆 Award Scholarship - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '7':
                print("\n💸 Disbursement Management - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '8':
                print("\n📊 Compliance Reports - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '9':
                print("Returning to main menu...")
                break
            else:
                print("❌ Invalid choice. Please enter a number between 1 and 9.")

        except KeyboardInterrupt:
            print("\n\nExiting financial aid menu...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def display_communication_hub_menu(auth):
    """Display the unified communication hub CLI menu with all options"""
    from university_system.infrastructure.email.config import config
    from university_system.modules.shared.utils.logs import LOG_MANAGEMENT_AVAILABLE

    # Initialize dashboard for advanced features
    dashboard = CommunicationDashboard(auth=auth)
    is_admin = auth and auth.current_user and auth.current_user.get('role') == 'admin'

    print("\n" + "="*60)
    print("       UNIFIED COMMUNICATION HUB")
    print("="*60)
    print("\n📧 Quick Actions:")
    print("1. Send Email")
    print("2. Send SMS")
    print("3. Send Push Notification")

    print("\n📢 Announcements & Messages:")
    print("4. Messages Management")
    print("5. Create Announcement")
    print("6. Manage Announcements")
    print("7. Send Batch Announcement")

    print("\n💬 Chat & Communication:")
    print("8. Chat Rooms")
    print("9. Notification Preferences")

    print("\n⚙️ Email System Configuration:")
    print("10. Configure Email Settings")
    print("11. Test Email Configuration")
    print("12. Manage Email Templates")
    print("13. Schedule Emails")
    print("14. View Email Queue Status")
    print("15. View Stored Emails")

    print("\n📊 Reports & Analytics:")
    print("16. Generate Email Reports")
    if LOG_MANAGEMENT_AVAILABLE:
        print("17. Communication Activity Logs")
        if is_admin:
            print("18. Communication Analytics")

    if is_admin:
        print("\n🔧 Administration:")
        print("19. Admin Message Management")

    print("\n↩️ Navigation:")
    if is_admin and LOG_MANAGEMENT_AVAILABLE:
        print("20. Return to Main Menu")
        max_choice = 20
    elif is_admin or LOG_MANAGEMENT_AVAILABLE:
        print("19. Return to Main Menu")
        max_choice = 19
    else:
        print("17. Return to Main Menu")
        max_choice = 17
    print("="*60)

    while True:
        try:
            choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()

            if choice == '1':
                # Send Email
                try:
                    to_address = input("Enter recipient email: ").strip()
                    subject = input("Enter subject: ").strip()
                    body = input("Enter message body: ").strip()

                    comm_mgr = CommunicationManager()
                    email_id = comm_mgr.queue_email(
                        to_address=to_address,
                        subject=subject,
                        body=body,
                        from_user_id=auth.current_user['user_id']
                    )
                    print(f"✅ Email queued successfully! Email ID: {email_id}")
                except Exception as e:
                    print(f"❌ Error queuing email: {e}")
            elif choice == '2':
                # Send SMS
                try:
                    phone_number = input("Enter phone number: ").strip()
                    message = input("Enter message: ").strip()

                    comm_mgr = CommunicationManager()
                    sms_id = comm_mgr.queue_sms(
                        phone_number=phone_number,
                        message=message,
                        from_user_id=auth.current_user['user_id']
                    )
                    print(f"✅ SMS queued successfully! SMS ID: {sms_id}")
                except Exception as e:
                    print(f"❌ Error queuing SMS: {e}")
            elif choice == '3':
                print("\n📱 Send Push Notification - Feature available via GUI")
                print("Please use the GUI version for full functionality.")
            elif choice == '4':
                # Messages Management
                from university_system.infrastructure.email.admin import display_messages_menu
                display_messages_menu(dashboard)
            elif choice == '5':
                # Create Announcement
                try:
                    title = input("Enter announcement title: ").strip()
                    content = input("Enter announcement content: ").strip()
                    target_audience = input("Enter target audience (all/students/faculty/staff): ").strip()

                    comm_mgr = CommunicationManager()
                    announcement_id = comm_mgr.create_announcement(
                        title=title,
                        content=content,
                        target_audience=target_audience,
                        created_by=auth.current_user['user_id']
                    )
                    print(f"✅ Announcement created successfully! Announcement ID: {announcement_id}")
                except Exception as e:
                    print(f"❌ Error creating announcement: {e}")
            elif choice == '6':
                # Manage Announcements
                from university_system.infrastructure.email.admin import display_announcements_menu
                display_announcements_menu(dashboard)
            elif choice == '7':
                # Send Batch Announcement
                from university_system.infrastructure.email.email_service import send_batch_email_form
                send_batch_email_form()
            elif choice == '8':
                # Chat Rooms
                from university_system.infrastructure.email.admin import display_chat_rooms_menu
                display_chat_rooms_menu(dashboard)
            elif choice == '9':
                # Notification Preferences
                from university_system.infrastructure.email.admin import display_preferences_menu
                display_preferences_menu(dashboard)
            elif choice == '10':
                # Configure Email Settings
                from university_system.infrastructure.email.config import configure_email_settings
                configure_email_settings()
            elif choice == '11':
                # Test Email Configuration
                from university_system.infrastructure.email.email_service import send_email
                recipient = input("Enter test recipient email (or press Enter to use your email): ").strip()
                if not recipient and auth.current_user:
                    recipient = auth.current_user.get('email', '')
                if recipient:
                    test_subject = "Test Email from University System"
                    test_body = f"This is a test email sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    if send_email(recipient, test_subject, test_body):
                        print("✅ Test email sent successfully!")
                    else:
                        print("❌ Failed to send test email.")
                else:
                    print("❌ No recipient email provided.")
            elif choice == '12':
                # Manage Email Templates
                from university_system.infrastructure.email.templates import template_management_menu
                template_management_menu()
            elif choice == '13':
                # Schedule Emails
                from university_system.infrastructure.email.email_service import schedule_email_form
                schedule_email_form()
            elif choice == '14':
                # View Email Queue Status
                from university_system.infrastructure.email.email_service import email_queue, get_stored_emails
                if config.get('database_only_mode', True):
                    emails_data = get_stored_emails(limit=1)
                    print(f"\n📊 Stored emails in database: {emails_data['total_count']}")
                    if emails_data['total_count'] > 0:
                        print("Recent stored emails:")
                        recent_emails = get_stored_emails(limit=5)
                        for email in recent_emails['emails']:
                            print(f"  - To: {email['recipient_email']}, Subject: {email['subject'][:50]}...")
                else:
                    queue_size = email_queue.qsize()
                    print(f"\n📊 Current email queue size: {queue_size}")
                input("\nPress Enter to continue...")
            elif choice == '15':
                # View Stored Emails
                from university_system.infrastructure.email.email_service import display_stored_emails_menu
                display_stored_emails_menu()
            elif choice == '16':
                # Generate Email Reports
                from university_system.infrastructure.email.reports import generate_report_form
                generate_report_form()
            elif choice == '17':
                if LOG_MANAGEMENT_AVAILABLE:
                    # Communication Activity Logs
                    from university_system.modules.shared.utils.logs import display_communication_logs_menu
                    display_communication_logs_menu(dashboard)
                elif not is_admin:
                    # Return to main menu (non-admin, no log management)
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            elif choice == '18':
                if is_admin and LOG_MANAGEMENT_AVAILABLE:
                    # Communication Analytics
                    from university_system.modules.shared.utils.logs import display_communication_analytics_menu
                    display_communication_analytics_menu(dashboard)
                else:
                    print("❌ Invalid choice.")
            elif choice == '19':
                if is_admin and not LOG_MANAGEMENT_AVAILABLE:
                    # Admin Message Management (admin without log management)
                    from university_system.infrastructure.email.admin import display_admin_message_management_menu
                    display_admin_message_management_menu(dashboard)
                elif is_admin or LOG_MANAGEMENT_AVAILABLE:
                    # Return to main menu
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            elif choice == '20':
                if is_admin and LOG_MANAGEMENT_AVAILABLE:
                    # Return to main menu (admin with log management)
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            else:
                print(f"❌ Invalid choice. Please enter a number between 1 and {max_choice}.")

        except KeyboardInterrupt:
            print("\n\nExiting communication hub menu...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def display_accessibility_tools_menu(auth):
    """Display the Accessibility & Accommodation Tools CLI menu"""
    print("\n" + "="*50)
    print("  ACCESSIBILITY & ACCOMMODATION TOOLS")
    print("="*50)
    print("1. Manage Accommodation Requests")
    print("2. Accessibility Profiles")
    print("3. Assistive Technology Settings")
    print("4. Document Formats & Conversions")
    print("5. Captioning & Transcripts")
    print("6. Testing Accommodations")
    print("7. Compliance Audits")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n♿ Accessibility feature - Database tables available")
                print("Database tables: accommodation_requests, accommodation_approvals,")
                print("accessibility_profiles, assistive_technology, document_formats,")
                print("captioning_requests, testing_accommodations, accessibility_audits,")
                print("accommodation_documentation")
                print("\nAccess via SQL or create manager following existing patterns.")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def display_transportation_parking_menu(auth):
    """Display the Transportation & Parking Management CLI menu"""
    # Redirect to parking management menu which now includes transportation
    from university_system.modules.domain.mobility.services.parking_management import display_parking_menu
    display_parking_menu()


def switch_to_gui(auth_instance):
    """Switch from CLI to GUI interface without circular imports"""
    try:
        print("\n🔄 Switching to GUI interface...")
        print("Please wait while the GUI loads...")

        # Dynamic import to avoid circular imports
        import importlib
        gui_module = importlib.import_module('university_system.modules.shared.gui.main_gui')

        # Get the current user from the authenticated CLI session
        current_user = auth_instance.current_user if hasattr(auth_instance, 'current_user') else None

        # Use the centralized init_gui function with the logged-in user
        init_gui_func = getattr(gui_module, 'init_gui', None)
        if callable(init_gui_func):
            main_gui = init_gui_func(session_user=current_user)
        else:
            # Fallback to old method if init_gui is not available
            print("⚠️ Warning: Using legacy GUI initialization")
            if hasattr(gui_module, 'auth'):
                gui_module.auth = auth_instance
            safe_auth_check = getattr(gui_module, 'safe_auth_check', None)
            if callable(safe_auth_check):
                safe_auth_check(auth_instance)
            main_gui = gui_module.StudentManagementGUI(auth_instance)

        print("✅ GUI interface loaded successfully!")
        print("You can now close this CLI window if desired.")

        # Start the GUI application loop
        if hasattr(main_gui, 'run') and callable(main_gui.run):
            main_gui.run()
        elif hasattr(main_gui, 'root') and hasattr(main_gui.root, 'mainloop'):
            main_gui.root.mainloop()
        else:
            print("⚠️ Unable to determine GUI main loop entry point. Closing GUI instance.")
            return

    except ImportError as e:
        print(f"❌ Error: Could not import GUI module: {e}")
        print("Please ensure the GUI components are properly installed.")
        input("Press Enter to continue with CLI...")
    except Exception as e:
        print(f"❌ Error switching to GUI: {e}")
        print("Continuing with CLI interface...")
        input("Press Enter to continue...")

def display_administrative_tools_menu(auth):
    """Consolidated administrative tools and analytics menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access administrative tools.")
        return

    while True:
        print("\n" + "="*60)
        print("            ADMINISTRATIVE TOOLS & ANALYTICS")
        print("="*60)
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")

        print("\n👥 User & Access Management:")
        print("1. User Management")

        print("\n📊 Reporting & Analytics:")
        print("2. Enhanced Reporting")
        print("3. Student Analytics Dashboard")
        print("4. Predictive Analytics Dashboard")
        print("5. Business Intelligence Reports")

        print("\n🔧 System Operations:")
        print("6. Batch Operations")
        print("7. Advanced Search and Filtering")

        if auth.current_user['role'] == 'admin':
            print("\n🛠️ Database Administration:")
            print("8. Admin Database Tools")

        print("\n↩️ Navigation:")
        if auth.current_user['role'] == 'admin':
            print("9. Return to Main Menu")
            max_choice = 9
        else:
            print("8. Return to Main Menu")
            max_choice = 8
        print("="*60)

        choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()

        if choice == '1':
            # User Management
            display_user_management_menu(auth)
        elif choice == '2':
            # Enhanced Reporting
            from university_system.modules.shared.services.enhanced_reporting import display_enhanced_reporting_menu
            display_enhanced_reporting_menu()
        elif choice == '3':
            # Student Analytics Dashboard
            display_analytics_menu()
        elif choice == '4':
            # Predictive Analytics Dashboard
            display_predictive_analytics_menu(auth)
        elif choice == '5':
            # Business Intelligence Reports
            display_business_intelligence_menu(auth)
        elif choice == '6':
            # Batch Operations
            display_batch_menu()
        elif choice == '7':
            # Advanced Search
            display_enhanced_menu()
        elif choice == '8':
            if auth.current_user['role'] == 'admin':
                # Admin Database Tools
                display_admin_tools_menu()
            else:
                # Return to main menu (non-admin)
                break
        elif choice == '9' and auth.current_user['role'] == 'admin':
            # Return to main menu (admin)
            break
        else:
            print("Invalid choice. Please try again.")

def display_data_document_management_menu(auth):
    """Consolidated data and document management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access data management.")
        return

    while True:
        print("\n" + "="*60)
        print("        DATA & DOCUMENT MANAGEMENT SYSTEM")
        print("="*60)
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")

        print("\n📄 Document Management:")
        print("1. Document Management System")

        print("\n💾 Data Operations:")
        print("2. Export Options")
        print("3. Data Backup and Restore")

        print("\n↩️ Navigation:")
        print("4. Return to Main Menu")
        print("="*60)

        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == '1':
            # Document Management
            from university_system.modules.shared.utils.document_manager import display_document_management_menu
            display_document_management_menu()
        elif choice == '2':
            # Export Options
            display_export_menu()
        elif choice == '3':
            # Data Backup and Restore
            from university_system.infrastructure.database.data_backup import display_backup_menu
            display_backup_menu()
        elif choice == '4':
            # Return to main menu
            break
        else:
            print("Invalid choice. Please try again.")

def main():
    """Entry point used by both the CLI runner and module execution."""
    # Perform silent integrity check first
    silent_integrity_check()
    fix_parent_portal_database()

    # Initialize system cleanly
    if not initialize_system():
        print("System initialization failed. Exiting.")
        return

    # Initialize auth and start the main menu
    global auth
    auth = UserAuth()
    set_global_auth(auth)  # Set as global auth for all modules
    display_menu()


if __name__ == "__main__":
    main()
