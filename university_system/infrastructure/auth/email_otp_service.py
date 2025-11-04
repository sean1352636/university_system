#!/usr/bin/env python3
"""
Email OTP Service for Multi-Factor Authentication
Supports multiple email providers with templates
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from abc import ABC, abstractmethod


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
        self.smtp_server = smtp_server or os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))
        self.username = username or os.getenv('SMTP_USERNAME')
        self.password = password or os.getenv('SMTP_PASSWORD')
        self.from_email = from_email or os.getenv('SMTP_FROM_EMAIL', self.username)
        self.from_name = from_name or os.getenv('SMTP_FROM_NAME', 'University System')

        if not all([self.smtp_server, self.username, self.password]):
            raise ValueError("SMTP credentials not configured")

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
        """Create plain text email body"""
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
        """Create HTML email body"""
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
            <h1>🔐 University System</h1>
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
                <strong>⚠️ Security Notice:</strong> If you did not request this code, please ignore this email or contact support immediately.
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
        self.log_file = log_file or '/tmp/email_otp_log.txt'

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

    def __init__(self, primary_provider: str = 'mock', fallback_provider: str = None):
        """
        Initialize Email OTP service with providers

        Args:
            primary_provider: Primary provider to use ('smtp', 'aws_ses', 'mock')
            fallback_provider: Fallback provider if primary fails
        """
        self.primary = self._create_provider(primary_provider)
        self.fallback = self._create_provider(fallback_provider) if fallback_provider else None

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
                print(f"Unknown provider: {provider_name}, using mock")
                return MockEmailProvider()
        except Exception as e:
            print(f"Failed to create {provider_name} provider: {e}, using mock")
            return MockEmailProvider()

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
        # Validate email
        if not to_email or '@' not in to_email:
            return {'success': False, 'error': 'Invalid email address'}

        # Try primary provider
        result = self.primary.send_otp(to_email, code, username)

        if result['success']:
            return result

        # Try fallback if primary failed
        if self.fallback:
            print(f"Primary provider failed, trying fallback...")
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
    config_file = os.path.join(
        os.path.dirname(__file__),
        '../../config/email_config.json'
    )

    # Try to load from config file
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load email config: {e}")

    # Default configuration
    return {
        'primary_provider': os.getenv('EMAIL_PRIMARY_PROVIDER', 'mock'),
        'fallback_provider': os.getenv('EMAIL_FALLBACK_PROVIDER', None)
    }


# Default service instance
_default_service = None


def get_email_service() -> EmailOTPService:
    """Get or create default email service instance"""
    global _default_service

    if _default_service is None:
        config = load_email_config()
        _default_service = EmailOTPService(
            primary_provider=config.get('primary_provider', 'mock'),
            fallback_provider=config.get('fallback_provider')
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
