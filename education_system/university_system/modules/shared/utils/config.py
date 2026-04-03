"""Configuration helpers for the email infrastructure package."""

from __future__ import annotations

import json
import ssl
import smtplib
import jsonschema

from education_system.university_system.modules.shared.utils.logs import handle_exception, log_event
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.i18n import get_text


CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "smtp_server": {"type": "string"},
        "smtp_port": {"type": "integer", "minimum": 1, "maximum": 65535},
        "sender_email": {"type": "string", "format": "email"},
        "sender_name": {"type": "string"},
        "use_tls": {"type": "boolean"},
        "use_authentication": {"type": "boolean"},
        "username": {"type": "string"},
        "password": {"type": "string"},
        "email_signature": {"type": "string"},
        "send_delay": {"type": "number", "minimum": 0},
        "max_threads": {"type": "integer", "minimum": 1, "maximum": 20},
        "templates_dir": {"type": "string"},
        "save_password": {"type": "boolean"},
        "database_only_mode": {"type": "boolean"}
    },
    "required": ["smtp_server", "smtp_port", "sender_email", "use_tls"]
}



DEFAULT_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "noreply@university.edu",  # Default sender for database-only mode
    "sender_name": "Teesside University",
    "use_tls": True,
    "use_authentication": True,
    "username": "",      # To be configured by user
    "password": "",      # To be configured by user
    "email_signature": "\n\nRegards,\nTees University",
    "send_delay": 1.0,   # Delay between emails in seconds
    "max_threads": 1,    # Maximum number of concurrent email sending threads
    "templates_dir": str(paths.EMAIL_TEMPLATES_DIR),
    "database_only_mode": True  # NEW: Store emails in database instead of sending
}



config = DEFAULT_CONFIG.copy()


def _config_path():
    return paths.EMAIL_CONFIG_PATH



def validate_email_config(config):
    """Enhanced configuration validation"""
    errors = []

    # Required fields
    required_fields = ['sender_email', 'sender_name']
    for field in required_fields:
        if not config.get(field):
            errors.append(f"Missing required field: {field}")

    # Email format validation
    if config.get('sender_email'):
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, config['sender_email']):
            errors.append("Invalid sender email format")

    # SMTP-specific validation (only if not in database mode)
    if not config.get('database_only_mode', True):
        smtp_required = ['smtp_server', 'smtp_port']
        for field in smtp_required:
            if not config.get(field):
                errors.append(f"SMTP mode requires: {field}")

        # Port validation
        port = config.get('smtp_port')
        if port and (not isinstance(port, int) or port < 1 or port > 65535):
            errors.append("Invalid SMTP port number")

    return errors



@handle_exception
def load_config():
    """Load email configuration from file"""
    global config

    config_path = _config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
            log_event('info', "Email configuration loaded successfully")
        except Exception as e:
            log_event('error', f"Error loading configuration: {e}")
    else:
        log_event('warning', "No email configuration file found. Using defaults.")
        save_config()

    # Force single thread and longer delays to reduce contention
    config['max_threads'] = 1
    config['send_delay'] = max(config.get('send_delay', 2.0), 2.0)

    return config



@handle_exception
def save_config():
    """Save current email configuration to file"""
    try:
        config_path = _config_path()
        from pathlib import Path
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            # Don't save password to file unless explicitly told to
            config_to_save = config.copy()
            if 'save_password' not in config or not config['save_password']:
                config_to_save['password'] = ""

            json.dump(config_to_save, f, indent=4)
        log_event('info', "Email configuration saved successfully")
        return True
    except Exception as e:
        log_event('error', f"Error saving email configuration: {e}")
        return False



@handle_exception
def validate_config(config_path=None):
    """Validate the email configuration"""
    try:
        if config_path:
            # Load config from file
            with open(config_path, "r") as f:
                cfg = json.load(f)
        else:
            # Use current config
            cfg = config

        # Validate against schema
        jsonschema.validate(instance=cfg, schema=CONFIG_SCHEMA)

        # Skip SMTP validation if in database-only mode
        if cfg.get('database_only_mode', True):
            log_event('info', "Database-only mode enabled - skipping SMTP validation")
            return True

        # Validate SMTP connection if credentials are provided
        if cfg['smtp_server'] and cfg['sender_email']:
            if cfg['use_authentication'] and (not cfg['username'] or not cfg['password']):
                log_event('error', "Authentication enabled but username or password is missing")
                return False

            # Try to connect to SMTP server using centralized system
            try:
                from education_system.university_system.infrastructure.email.smtp import send_email_via_smtp
                from datetime import datetime

                # Test by sending to the sender email as a validation
                current_time = datetime.now().isoformat()
                success = send_email_via_smtp(
                    recipient_email=cfg['sender_email'],
                    subject="SMTP Configuration Test",
                    body="This is a test email to validate SMTP configuration.",
                    cc=None,
                    bcc=None,
                    attachments=None,
                    current_time=current_time
                )

                if success:
                    log_event('info', "SMTP connection test successful")
                    return True
                else:
                    log_event('error', "SMTP connection test failed")
                    return False
            except Exception as e:
                log_event('error', f"SMTP connection test failed: {e}")
                return False

        return True
    except Exception as e:
        log_event('error', f"Config validation error: {e}")
        return False



@handle_exception
def configure_email_settings():
    """Configure email settings interactively"""
    global config

    print("\n" + get_text("config.email_configuration"))
    print("===================")

    # NEW: Database-only mode setting
    print("\n" + get_text("config.email_mode"))
    current_mode = get_text("config.mode_database_only") if config.get('database_only_mode', True) else get_text("config.mode_smtp_sending")
    print(get_text("config.current_mode", mode=current_mode))

    mode_choice = input("Choose mode:\n1. Database Only (emails stored in database)\n2. SMTP Sending (emails actually sent)\nEnter choice (1-2): ")

    if mode_choice == '1':
        config['database_only_mode'] = True
        print(get_text("config.set_database_only_mode"))
    elif mode_choice == '2':
        config['database_only_mode'] = False
        print(get_text("config.set_smtp_sending_mode"))

        # Only configure SMTP settings if not in database-only mode
        print("\n" + get_text("config.smtp_settings"))
        config['smtp_server'] = input(f"SMTP Server [{config['smtp_server']}]: ") or config['smtp_server']

        try:
            port = int(input(f"SMTP Port [{config['smtp_port']}]: ") or config['smtp_port'])
            if 0 < port < 65536:
                config['smtp_port'] = port
            else:
                print(get_text("config.invalid_port_using_previous"))
        except ValueError:
            print(get_text("config.invalid_port_using_previous"))

        use_tls = input(f"Use TLS (y/n) [{('y' if config['use_tls'] else 'n')}]: ") or ('y' if config['use_tls'] else 'n')
        config['use_tls'] = use_tls.lower() == 'y'

        print("\n" + get_text("config.authentication_settings"))
        use_auth = input(f"Use Authentication (y/n) [{('y' if config['use_authentication'] else 'n')}]: ") or ('y' if config['use_authentication'] else 'n')
        config['use_authentication'] = use_auth.lower() == 'y'

        if config['use_authentication']:
            config['username'] = input(f"Username [{config['username']}]: ") or config['username']
            password = input("Password (leave empty to keep current): ")
            if password:
                config['password'] = password

            save_pwd = input("Save password in configuration file? (Not recommended) (y/n): ")
            config['save_password'] = save_pwd.lower() == 'y'
    else:
        print("Invalid choice. Keeping current mode.")

    print("\nSender Information:")
    config['sender_email'] = input(f"Sender Email [{config['sender_email']}]: ") or config['sender_email']
    config['sender_name'] = input(f"Sender Name [{config['sender_name']}]: ") or config['sender_name']

    print("\nEmail Signature:")
    print("Current signature:")
    print(config['email_signature'])
    new_signature = input("New signature (leave empty to keep current):\n")
    if new_signature:
        config['email_signature'] = new_signature

    print("\nAdvanced Settings:")
    try:
        delay = float(input(f"Send Delay (seconds) [{config['send_delay']}]: ") or config['send_delay'])
        if delay >= 0:
            config['send_delay'] = delay
        else:
            print("Invalid delay. Using previous value.")
    except ValueError:
        print("Invalid delay. Using previous value.")

    try:
        threads = int(input(f"Max Threads [{config['max_threads']}]: ") or config['max_threads'])
        if 1 <= threads <= 10:
            config['max_threads'] = threads
        else:
            print("Invalid thread count. Using previous value.")
    except ValueError:
        print("Invalid thread count. Using previous value.")

    # Save configuration
    save_config()

    if not config.get('database_only_mode', True):
        # Validate configuration only if in SMTP mode
        print("\nValidating configuration...")
        if validate_config():
            print("Configuration is valid!")
        else:
            print("Configuration has issues. Please review settings.")

        # Offer to send a test email
        test = input("\nWould you like to send a test email to verify your configuration? (y/n): ")
        if test.lower() == 'y':
            test_recipient = input("Enter test recipient email (leave empty to send to yourself): ")
            test_email_configuration(test_recipient if test_recipient else None)
    else:
        print("\nConfiguration saved! Emails will be stored in database.")



@handle_exception
def test_email_configuration(test_recipient=None):
    """Test the email configuration by sending a test email"""
    from education_system.university_system.modules.shared.utils.email_service import send_email  # Local import to avoid circular dependency
    from education_system.university_system.infrastructure.email.template_utils import render_template

    if not config['sender_email']:
        print("Sender email not configured. Please configure email settings first.")
        return False

    # Use sender email as recipient if not specified
    if not test_recipient:
        test_recipient = config['sender_email']

    # Prepare template variables
    template_vars = {
        'mode': 'Database Only' if config.get('database_only_mode', True) else 'SMTP Sending',
        'smtp_server': config['smtp_server'],
        'smtp_port': config['smtp_port'],
        'sender_email': config['sender_email'],
        'tls_enabled': config['use_tls'],
        'authentication_enabled': config['use_authentication'],
        'mode_message': 'This email was stored in the database instead of being sent.' if config.get('database_only_mode', True) else 'If you received this email, your email configuration is working correctly.',
        'signature': config['email_signature']
    }

    try:
        subject, body = render_template('email_system_test', template_vars)
    except Exception as e:
        log_event('error', f"Failed to render email template: {e}")
        # Fallback to hardcoded message if template fails
        subject = "Test Email from Student Records System"
        body = f"""This is a test email sent from the Student Records System.

Configuration:
- Mode: {template_vars['mode']}
- SMTP Server: {template_vars['smtp_server']}
- SMTP Port: {template_vars['smtp_port']}
- Sender: {template_vars['sender_email']}
- TLS Enabled: {template_vars['tls_enabled']}
- Authentication: {template_vars['authentication_enabled']}

{template_vars['mode_message']}
{config['email_signature']}"""

    print(f"Processing test email to {test_recipient}...")
    result = send_email(test_recipient, subject, body)

    if result:
        if config.get('database_only_mode', True):
            print("Test email stored in database successfully!")
        else:
            print("Test email sent successfully!")
    else:
        print("Failed to process test email. Please check your configuration.")

    return result



@handle_exception
def ensure_email_config_for_database_mode():
    """Ensure email configuration is set up properly for database-only mode"""
    global config

    if config.get('database_only_mode', True):
        if not config['sender_email']:
            config['sender_email'] = "noreply@university.edu"
            log_event('info', "Set default sender email for database-only mode")

        if not config['sender_name']:
            config['sender_name'] = "University System"
            log_event('info', "Set default sender name for database-only mode")

    return True
