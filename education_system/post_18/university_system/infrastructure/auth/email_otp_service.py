#!/usr/bin/env python3
"""
Email OTP Service for Multi-Factor Authentication
Supports multiple email providers with templates
"""

import os
import json
import logging
import smtplib
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, List
from abc import ABC, abstractmethod
from string import Template
from education_system.post_18.university_system.core import paths
from education_system.post_18.university_system.core.i18n import get_text, _
from education_system.post_18.university_system.infrastructure.validation.validators import Validators

# Initialize logger
logger = logging.getLogger(__name__)

class EmailProvider(ABC):
    """Abstract base class for email providers"""

    @abstractmethod
    def send_otp(self, to_email: str, code: str, username: str = None) -> Dict:
        """Send OTP via email"""
        pass

class SMTPEmailProvider(EmailProvider):
    """SMTP Email Provider (supports Gmail, Office365, etc.)"""

    def __init__(self, smtp_server: str = None, smtp_port: int = None,
                 username: str = None, password: str = None,
                 from_email: str = None, from_name: str = None):
        """Initialize SMTP provider"""
        # Try to load from email_config.json first
        config = self._load_email_config()

        self.smtp_server = smtp_server or config.get('smtp_server') or os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = smtp_port or config.get('smtp_port') or int(os.getenv('SMTP_PORT') or 0) or 587
        self.username = username or config.get('smtp_username') or config.get('username') or os.getenv('SMTP_USERNAME')
        self.password = password or config.get('smtp_password') or config.get('password') or os.getenv('SMTP_PASSWORD')
        self.from_email = from_email or config.get('sender_email') or os.getenv('SMTP_FROM_EMAIL') or self.username
        self.from_name = from_name or config.get('sender_name') or os.getenv('SMTP_FROM_NAME', 'University System')

        if not all([self.smtp_server, self.username, self.password]):
            raise ValueError("SMTP credentials not configured")

    def _load_email_config(self) -> dict:
        """Load email configuration from shared config file"""
        try:
            from education_system.shared.email.config import load_email_config
            return load_email_config()
        except ImportError:
            pass
        # Fallback to legacy path
        try:
            config_path = os.path.join(paths.CONFIG_DIR, 'email_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load email config: {e}")
        return {}

    def send_otp(self, to_email: str, code: str, username: str = None) -> Dict:
        """Send OTP via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Your Verification Code - University System'
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email

            # Create HTML and plain text versions
            text_body = self._create_text_body(code, username)
            html_body = self._create_html_body(code, username)

            # Attach both versions
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            return {
                'success': True,
                'provider': 'smtp',
                'message': f'OTP sent to {to_email}'
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'SMTP error: {str(e)}'
            }

    def _create_text_body(self, code: str, username: str = None) -> str:
        """Create plain text email body from template"""
        # Load template from JSON
        template_path = paths.EMAIL_TEMPLATES_DIR / "otp_verification_text.json"

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)

            # Prepare template variables
            greeting = f"Hello {username}," if username else "Hello,"
            template_vars = {
                'greeting': greeting,
                'code': code
            }

            # Render template
            body_template = Template(template_data['body'])
            return body_template.safe_substitute(template_vars)

        except FileNotFoundError:
            logger.warning(
                f"OTP text template not found at {template_path}. Using fallback template."
            )
            greeting = f"Hello {username},\n\n" if username else "Hello,\n\n"
            return f"""{greeting}Your verification code for University System is:

{code}

This code will expire in 10 minutes.

If you did not request this code, please ignore this email or contact support.

For security reasons, never share this code with anyone.

Thank you,
University System Security Team
"""
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in OTP text template at {template_path}: {e}. Using fallback template."
            )
            greeting = f"Hello {username},\n\n" if username else "Hello,\n\n"
            return f"""{greeting}Your verification code for University System is:

{code}

This code will expire in 10 minutes.

If you did not request this code, please ignore this email or contact support.

For security reasons, never share this code with anyone.

Thank you,
University System Security Team
"""
        except Exception as e:
            logger.error(
                f"Unexpected error loading OTP text template from {template_path}: {e}. Using fallback template."
            )
            greeting = f"Hello {username},\n\n" if username else "Hello,\n\n"
            return f"""{greeting}Your verification code for University System is:

{code}

This code will expire in 10 minutes.

If you did not request this code, please ignore this email or contact support.

For security reasons, never share this code with anyone.

Thank you,
University System Security Team
"""

    def _create_html_body(self, code: str, username: str = None) -> str:
        """Create HTML email body from template"""
        # Load template from JSON
        template_path = paths.EMAIL_TEMPLATES_DIR / "otp_verification_html.json"

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)

            # Prepare template variables
            greeting = f"Hello {username}," if username else "Hello,"
            template_vars = {
                'greeting': greeting,
                'code': code
            }

            # Render template
            html_template = Template(template_data['html_body'])
            return html_template.safe_substitute(template_vars)

        except FileNotFoundError:
            logger.warning(
                f"OTP HTML template not found at {template_path}. Using fallback template."
            )
            return self._get_fallback_html_template(code, username)
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in OTP HTML template at {template_path}: {e}. Using fallback template."
            )
            return self._get_fallback_html_template(code, username)
        except Exception as e:
            logger.error(
                f"Unexpected error loading OTP HTML template from {template_path}: {e}. Using fallback template."
            )
            return self._get_fallback_html_template(code, username)

    def _get_fallback_html_template(self, code: str, username: str = None) -> str:
        """Return fallback HTML template when JSON template loading fails."""
        greeting = f"Hello {username}," if username else "Hello,"
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .header {{
            background-color: #0066cc;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: white;
            padding: 30px;
            border-radius: 0 0 5px 5px;
        }}
        .code-box {{
            background-color: #f0f0f0;
            border: 2px solid #0066cc;
            border-radius: 5px;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
        }}
        .code {{
            font-size: 32px;
            font-weight: bold;
            color: #0066cc;
            letter-spacing: 5px;
            font-family: 'Courier New', monospace;
        }}
        .warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 10px;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>University System</h1>
            <p>Security Verification</p>
        </div>
        <div class="content">
            <p>{greeting}</p>
            <p>Your verification code for University System is:</p>

            <div class="code-box">
                <div class="code">{code}</div>
            </div>

            <p><strong>This code will expire in 10 minutes.</strong></p>

            <div class="warning">
                <strong>Security Notice:</strong> If you did not request this code, please ignore this email or contact support immediately.
            </div>

            <p>For security reasons, <strong>never share this code with anyone</strong>, including University System staff.</p>

            <p>Thank you for helping us keep your account secure.</p>

            <p>Best regards,<br>
            University System Security Team</p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""

class AWS_SES_Provider(EmailProvider):
    """AWS SES Email Provider"""

    def __init__(self, region_name: str = 'us-east-1', from_email: str = None):
        """Initialize AWS SES provider"""
        self.region_name = region_name
        self.from_email = from_email or os.getenv('AWS_SES_FROM_EMAIL')

        if not self.from_email:
            raise ValueError("AWS SES from_email not configured")

    def send_otp(self, to_email: str, code: str, username: str = None) -> Dict:
        """Send OTP via AWS SES"""
        try:
            import boto3

            ses = boto3.client('ses', region_name=self.region_name)

            # Create email body
            provider = SMTPEmailProvider()  # Use same template
            html_body = provider._create_html_body(code, username)
            text_body = provider._create_text_body(code, username)

            response = ses.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {
                        'Data': 'Your Verification Code - University System',
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': text_body,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': html_body,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )

            return {
                'success': True,
                'provider': 'aws_ses',
                'message_id': response['MessageId']
            }

        except ImportError:
            return {
                'success': False,
                'error': 'boto3 library not installed. Run: pip install boto3'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'AWS SES error: {str(e)}'
            }

class MockEmailProvider(EmailProvider):
    """Mock Email Provider for development/testing"""

    def __init__(self, log_file: str = None):
        """Initialize mock provider"""
        self.log_file = log_file or str(paths.TEMP_DIR / 'email_otp_log.txt')

    def send_otp(self, to_email: str, code: str, username: str = None) -> Dict:
        """Mock send - logs to file instead of sending email"""
        try:
            from datetime import datetime

            message = f"""
{'=' * 80}
[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]
To: {to_email}
Subject: Your Verification Code - University System

Hello {username or 'User'},

Your verification code is: {code}

This code expires in 10 minutes.
{'=' * 80}
"""

            # Log to file
            with open(self.log_file, 'a') as f:
                f.write(message)

            # Also print to console for development
            print(f"📧 MOCK EMAIL: {to_email} -> Code: {code}")

            return {
                'success': True,
                'provider': 'mock',
                'message': 'Email logged (development mode)',
                'code': code  # Return code for easy testing
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Mock provider error: {str(e)}'
            }

class EmailOTPService:
    """
    Main Email OTP Service with provider management and fallback
    """

    def __init__(self, primary_provider: str = 'smtp', fallback_provider: str = 'mock',
                 smtp_whitelist: list = None):
        """
        Initialize Email OTP service with providers

        Args:
            primary_provider: Primary provider to use ('smtp', 'aws_ses', 'mock')
            fallback_provider: Fallback provider if primary fails
            smtp_whitelist: List of email addresses/domains allowed to receive real emails
                           (e.g., ['user@gmail.com', '@gmail.com'] - exact match or domain)
        """
        self.primary = self._create_provider(primary_provider)
        self.fallback = self._create_provider(fallback_provider) if fallback_provider else None
        self.mock_provider = MockEmailProvider()  # Always have mock available
        self.smtp_whitelist = smtp_whitelist or []

    def _create_provider(self, provider_name: str) -> Optional[EmailProvider]:
        """Create provider instance"""
        if not provider_name:
            return None

        provider_name = provider_name.lower()

        try:
            if provider_name == 'smtp':
                return SMTPEmailProvider()
            elif provider_name == 'aws_ses':
                return AWS_SES_Provider()
            elif provider_name == 'mock':
                return MockEmailProvider()
            else:
                logger.warning("Unknown email provider: %s, using mock", provider_name)
                return MockEmailProvider()
        except Exception as e:
            logger.warning("Failed to create %s email provider: %s, using mock", provider_name, e)
            return MockEmailProvider()

    def _load_whitelist_from_db(self) -> List[str]:
        """Load whitelist from database"""
        try:
            db_path = paths.DEFAULT_DB_PATH
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get active whitelisted emails
            cursor.execute("""
                SELECT email_address FROM email_smtp_whitelist
                WHERE is_active = 1
            """)

            whitelist = [row[0] for row in cursor.fetchall()]
            conn.close()

            logger.debug(f"Loaded {len(whitelist)} emails from database whitelist")
            return whitelist
        except Exception as e:
            logger.warning(f"Failed to load whitelist from database: {e}")
            return []

    def _is_whitelisted(self, email: str) -> bool:
        """Check if email is whitelisted for SMTP sending (checks both config and database)"""
        # Combine config whitelist and database whitelist
        combined_whitelist = list(self.smtp_whitelist)

        # Load from database and add to whitelist
        try:
            db_whitelist = self._load_whitelist_from_db()
            combined_whitelist.extend(db_whitelist)
        except Exception as e:
            logger.warning(f"Error loading database whitelist: {e}")

        if not combined_whitelist:
            # No whitelist = send all via SMTP (backward compatible)
            return True

        email_lower = email.lower()
        for allowed in combined_whitelist:
            allowed_lower = allowed.lower()
            # Exact match or domain match
            if email_lower == allowed_lower or (allowed_lower.startswith('@') and email_lower.endswith(allowed_lower)):
                return True
        return False

    def send_otp(self, to_email: str, code: str, username: str = None) -> Dict:
        """
        Send OTP with automatic fallback

        Args:
            to_email: Recipient email address
            code: OTP code to send
            username: Optional username for personalization

        Returns:
            Dict with success status and details
        """
        # Validate email using centralized validator
        email_validation = Validators.validate_email(to_email)
        if not email_validation.is_valid:
            return {'success': False, 'error': f'Invalid email address: {email_validation.error_message}'}

        # Check if email is whitelisted for SMTP
        if not self._is_whitelisted(to_email):
            # Use mock provider for non-whitelisted emails
            logger.info(f"Email {to_email} not whitelisted, using mock provider")
            return self.mock_provider.send_otp(to_email, code, username)

        # Try primary provider for whitelisted emails
        result = self.primary.send_otp(to_email, code, username)

        if result['success']:
            return result

        # Try fallback if primary failed
        if self.fallback:
            logger.warning("Primary email provider failed, trying fallback")
            result = self.fallback.send_otp(to_email, code, username)
            result['used_fallback'] = True
            return result

        return result

    def get_provider_status(self) -> Dict:
        """Get status of configured providers"""
        return {
            'primary': type(self.primary).__name__ if self.primary else None,
            'fallback': type(self.fallback).__name__ if self.fallback else None
        }

# Configuration loader
def load_email_config() -> Dict:
    """Load email provider configuration from file or environment"""
    config_file = paths.CONFIG_DIR / 'email_config.json'

    # Try to load from config file
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
            # Validate loaded config
            from education_system.post_18.university_system.infrastructure.validation.config_validators import validate_email_config
            result = validate_email_config(file_config)
            if not result.is_valid:
                logger.warning("Email config validation warnings: %s", result.error_message)
            return file_config
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load email config from %s: %s", config_file, e)

    # Default configuration - use SMTP if configured, otherwise mock
    return {
        'primary_provider': os.getenv('EMAIL_PRIMARY_PROVIDER', 'smtp'),
        'fallback_provider': os.getenv('EMAIL_FALLBACK_PROVIDER', 'mock'),
        'smtp_whitelist': []  # Empty = all emails sent via SMTP (backward compatible)
    }

# Default service instance
_default_service = None

def get_email_service() -> EmailOTPService:
    """Get or create default email service instance.

    Note: OTP emails are always sent via SMTP regardless of
    database_only_mode, since users must actually receive MFA codes.
    The rest of the email system respects database_only_mode separately.
    """
    global _default_service

    if _default_service is None:
        config = load_email_config()
        _default_service = EmailOTPService(
            primary_provider=config.get('primary_provider', 'smtp'),
            fallback_provider=config.get('fallback_provider', 'mock'),
            smtp_whitelist=config.get('smtp_whitelist', [])
        )

    return _default_service

def send_otp(to_email: str, code: str, username: str = None) -> Dict:
    """Convenience function to send OTP"""
    service = get_email_service()
    return service.send_otp(to_email, code, username)

if __name__ == '__main__':
    # Test Email service
    print("Email OTP Service Test\n" + "=" * 50)

    service = EmailOTPService(primary_provider='mock')
    print(f"Providers: {service.get_provider_status()}\n")

    # Test send
    result = service.send_otp('user@example.com', '123456', 'John Doe')
    print(f"Send result: {json.dumps(result, indent=2)}")

    # Test with different emails
    test_emails = [
        ('student@university.edu', '111111', 'Jane Student'),
        ('admin@university.edu', '999999', 'Admin User')
    ]

    print("\nTesting multiple emails:")
    for email, code, name in test_emails:
        result = service.send_otp(email, code, name)
        print(f"  {email:30} -> {result['success']}")
