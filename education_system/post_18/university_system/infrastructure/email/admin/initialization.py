"""System initialization, cleanup, auth, and testing utilities."""

from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    datetime,
    config,
    ensure_db_directory,
    execute_db_operation,
    handle_exception,
    initialize_chat_tables,
    initialize_email_db,
    load_config,
    log_event,
    logger,
    render_template,
    save_config,
    save_default_templates,
    send_email,
    send_template_email,
    start_email_workers,
    state,
    LOG_MANAGEMENT_AVAILABLE,
    log_manager,
)
from education_system.post_18.university_system.core.logs import get_log_manager
from education_system.post_18.university_system.infrastructure.email.email_service import (
    email_queue,
    worker_threads,
    stop_email_workers,
)
from education_system.post_18.university_system.infrastructure.email.reports import log_email_metrics


@handle_exception
def integrate_communication_dashboard_with_main():
    """Integrate the communication dashboard with the main system"""
    try:
        # Lazy import to avoid circular dependency
        from education_system.post_18.university_system.infrastructure.email.admin import CommunicationDashboard

        # Initialize database tables
        dashboard = CommunicationDashboard()

        # Load email configuration
        load_config()
        save_default_templates()

        # Initialize email database
        initialize_email_db()

        # Start email workers if configuration is complete and not in database-only mode
        if not config.get('database_only_mode', True):
            if config['sender_email'] and config['smtp_server']:
                start_email_workers()

        # Ensure the scheduler is running for scheduled emails
        if not config.get('database_only_mode', True):
            from education_system.post_18.university_system.infrastructure.email.admin._imports import ensure_scheduler_running
            ensure_scheduler_running()

        # Log the integration
        log_event('info', "Communication Dashboard integrated successfully!")
        return True
    except Exception as e:
        log_event('error', f"Error integrating Communication Dashboard: {e}")
        return False


def set_auth(auth_obj):
    """Set the authentication object for the email module and link to user_authentication"""
    # Use state.set_auth which properly links to user_authentication
    state.set_auth(auth_obj)
    if auth_obj:
        log_event('info', "Email system: Authentication set successfully and linked to user_authentication")
        return True
    return False



def set_communication_auth(auth_obj):
    """Set the authentication object for the communication dashboard module - alias for backward compatibility"""
    return set_auth(auth_obj)



def initialize_integrated_system(auth=None):
    """Initialize both communication and enhanced logging systems"""
    global log_manager

    try:
        # Initialize communication system first
        comm_result = initialize_communication_system()

        # Initialize enhanced logging if available
        log_result = True
        if LOG_MANAGEMENT_AVAILABLE:
            try:
                log_manager = get_log_manager()
                log_event('info', "Enhanced logging system integrated with communication dashboard")
                log_result = True
            except Exception as e:
                log_event('warning', f"Enhanced logging integration failed: {e}")
                log_result = False
        else:
            log_event('info', "Communication system initialized without enhanced logging")

        # Set authentication for both systems
        if auth:
            set_auth(auth)
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                # Both systems will use the same auth and database
                log_event('info', f"Authentication set for integrated system - User: {auth.current_user.get('username', 'Unknown')}")

        return comm_result and log_result

    except Exception as e:
        log_event('error', f"Error initializing integrated system: {e}")
        return False



def cleanup_integrated_system():
    """Clean up resources for both systems before shutting down"""
    try:
        # Clean up communication system
        cleanup_result = cleanup_communication_system()

        # Clean up enhanced logging system if available
        if LOG_MANAGEMENT_AVAILABLE and log_manager:
            try:
                # Stop any scheduled tasks
                if hasattr(log_manager, 'monitor') and log_manager.monitor.running:
                    log_manager.monitor.stop_monitoring()

                log_event('info', "Enhanced logging system cleaned up")
            except Exception as e:
                log_event('warning', f"Error cleaning up enhanced logging: {e}")

        log_event('info', "Integrated communication and logging system shutdown complete")
        return cleanup_result

    except Exception as e:
        log_event('error', f"Error during integrated system cleanup: {e}")
        return False



@handle_exception
def initialize_communication_system():
    """Initialize the entire communication system including chat rooms"""
    # Ensure database directory exists
    ensure_db_directory()

    # Load configuration (which includes database_only_mode setting)
    load_config()

    # Ensure proper email configuration for database-only mode
    if config.get('database_only_mode', True):
        if not config['sender_email']:
            config['sender_email'] = "noreply@university.edu"
            config['sender_name'] = "University System"
            save_config()
            log_event('info', "Configured default sender email for database-only mode")

    # Initialize databases
    initialize_email_db()
    initialize_chat_tables()

    # Only start SMTP workers if not in database-only mode
    if not config.get('database_only_mode', True):
        # Start email workers if configuration is complete
        if config['sender_email'] and config['smtp_server']:
            start_email_workers()

    log_event('info', f"Communication system with chat rooms initialized in {'Database Only' if config.get('database_only_mode', True) else 'SMTP'} mode")
    return True



@handle_exception
def cleanup_communication_system():
    """Clean up resources before shutting down"""
    # Stop email workers
    if worker_threads:
        if email_queue.qsize() > 0:
            log_event('warning', f"Warning: {email_queue.qsize()} emails still in queue and will not be sent.")
        stop_email_workers()

    log_event('info', "Communication system resources cleaned up.")
    return True



@handle_exception
def test_email_system():
    """Test the email system with database storage"""
    logger.info("Testing Email System - Database Storage Mode")
    logger.info("=" * 50)

    # Initialize system
    if initialize_communication_system():
        logger.info("\u2713 Communication system initialized")
    else:
        logger.error("\u2717 Failed to initialize communication system")
        return False

    # Test sending an email
    test_email = "test@example.com"
    test_subject = "Test Email"
    test_body = "This is a test email stored in the database."

    logger.info(f"\nTesting email to {test_email}...")
    if send_email(test_email, test_subject, test_body):
        logger.info("\u2713 Email stored successfully")

        # Log metrics
        log_email_metrics('sent')
        logger.info("\u2713 Metrics logged")

    else:
        logger.error("\u2717 Failed to store email")
        return False

    # Test template email
    logger.info("\nTesting template email...")
    template_vars = {
        'student_id': 'TEST123',
        'title': 'Mr',
        'first_name': 'John',
        'last_name': 'Doe',
        'email_address': test_email,
        'course': 'Computer Science',
        'modules_list': '- CS101: Introduction to Programming\n- CS102: Data Structures'
    }

    if send_template_email('user_management/registration_confirmation', test_email, template_vars):
        logger.info("\u2713 Template email stored successfully")
    else:
        logger.error("\u2717 Failed to store template email")

    logger.info("\n" + "=" * 50)
    logger.info("Email system test completed!")

    return True



def test_communication_dashboard_methods(auth=None):
    """Test if all required methods exist in CommunicationDashboard"""
    # Lazy import to avoid circular dependency
    from education_system.post_18.university_system.infrastructure.email.admin import CommunicationDashboard

    logger.info("Testing CommunicationDashboard methods...")

    # Create dashboard instance
    try:
        dashboard = CommunicationDashboard(auth=auth)
        logger.info("\u2705 CommunicationDashboard created successfully")
    except Exception as e:
        logger.error(f"\u274c Failed to create CommunicationDashboard: {e}")
        return False

    # List of required methods
    required_methods = [
        'send_message',
        'send_message_with_debug',
        'get_inbox',
        'get_sent_messages',
        'read_message',
        'update_message_status',
        'send_email_to_role',
        'compose_email_with_user_selection',
        'display_user_selection_menu',
        'get_notification_preferences',
        'update_notification_preferences',
        'create_announcement',
        'get_announcements'
    ]

    # Test each method
    missing_methods = []
    for method_name in required_methods:
        if hasattr(dashboard, method_name):
            method = getattr(dashboard, method_name)
            if callable(method):
                logger.info(f"\u2705 {method_name} - Found")
            else:
                logger.info(f"\u274c {method_name} - Not callable")
                missing_methods.append(method_name)
        else:
            logger.info(f"\u274c {method_name} - Missing")
            missing_methods.append(method_name)

    if missing_methods:
        logger.info(f"\n\u274c Missing methods: {', '.join(missing_methods)}")
        logger.info("Please add these methods to your CommunicationDashboard class.")
        return False
    else:
        logger.info("\n\u2705 All required methods are present!")
        return True



@handle_exception
def send_system_notification(dashboard, user_id, title, message, notification_type='info'):
    """Send a system notification to a user"""
    if not dashboard.auth or not dashboard.auth.current_user:
        return False

    # For now, we'll implement this as a system message
    system_subject, system_message = render_template("system_notification", {
        "title": title,
        "notification_type": notification_type.upper(),
        "message": message
    })

    # Send as a message from system (admin) user
    def _send_notification(cursor):
        # Get or create system user
        cursor.execute('''
        SELECT id FROM users WHERE role = 'admin' AND username = 'system'
        ''')

        system_user = cursor.fetchone()
        if not system_user:
            # Create system user if it doesn't exist
            cursor.execute('''
            INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('system', 'System', 'User', 'system@university.edu', 'admin',
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            system_user_id = cursor.lastrowid
        else:
            system_user_id = system_user[0]

        # Send the message
        sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO messages (sender_id, recipient_id, subject, content, sent_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (system_user_id, user_id, system_subject, system_message, sent_at))

        return True

    try:
        return execute_db_operation(_send_notification)
    except Exception as e:
        log_event('error', f"Error sending system notification: {e}")
        return False
