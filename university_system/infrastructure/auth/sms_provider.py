#!/usr/bin/env python3
"""
SMS Provider Integration for OTP Delivery
Supports multiple SMS providers with fallback options
"""

import os
import json
from typing import Dict, Optional
from abc import ABC, abstractmethod
from university_system.modules.shared.constants import paths
from university_system.modules.shared.utils.i18n import get_text, _


class SMSProvider(ABC):
    """Abstract base class for SMS providers"""

    @abstractmethod
    def send_otp(self, phone_number: str, code: str) -> Dict:
        """Send OTP via SMS"""
        pass


class TwilioSMSProvider(SMSProvider):
    """Twilio SMS Provider"""

    def __init__(self, account_sid: str = None, auth_token: str = None, from_number: str = None):
        """Initialize Twilio provider"""
        self.account_sid = account_sid or os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = auth_token or os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = from_number or os.getenv('TWILIO_PHONE_NUMBER')

        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError("Twilio credentials not configured")

    def _normalize_phone(self, phone_number: str) -> str:
        """Normalize phone number to E.164 format (especially for UK +44)"""
        # Remove all non-digit characters except +
        clean = ''.join(c for c in phone_number if c.isdigit() or c == '+')

        # Handle UK numbers
        if clean.startswith('+44'):
            return clean  # Already correct
        elif clean.startswith('44') and len(clean) >= 12:
            return '+' + clean  # Add + prefix
        elif clean.startswith('0') and len(clean) == 11:
            # UK local format (07xxx) -> +44
            return '+44' + clean[1:]
        elif clean.startswith('7') and len(clean) == 10:
            # UK mobile without 0 -> +44
            return '+44' + clean
        # Handle US numbers
        elif clean.startswith('+1'):
            return clean
        elif clean.startswith('1') and len(clean) == 11:
            return '+' + clean
        elif len(clean) == 10:
            return '+1' + clean  # Assume US if 10 digits

        # Default: add + if missing
        if not clean.startswith('+'):
            return '+' + clean
        return clean

    def send_otp(self, phone_number: str, code: str) -> Dict:
        """Send OTP via Twilio"""
        try:
            from twilio.rest import Client

            # Normalize phone number for UK (+44)
            normalized = self._normalize_phone(phone_number)

            client = Client(self.account_sid, self.auth_token)

            message_body = f"Your University System verification code is: {code}\n\nThis code expires in 10 minutes.\nDo not share this code with anyone."

            message = client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=normalized
            )

            return {
                'success': True,
                'provider': 'twilio',
                'message_sid': message.sid,
                'status': message.status
            }

        except ImportError:
            return {
                'success': False,
                'error': 'Twilio library not installed. Run: pip install twilio'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Twilio error: {str(e)}'
            }


class AWS_SNS_Provider(SMSProvider):
    """AWS SNS SMS Provider"""

    def __init__(self, region_name: str = 'us-east-1'):
        """Initialize AWS SNS provider"""
        self.region_name = region_name

    def send_otp(self, phone_number: str, code: str) -> Dict:
        """Send OTP via AWS SNS"""
        try:
            import boto3

            sns = boto3.client('sns', region_name=self.region_name)

            message_body = f"Your University System verification code is: {code}\n\nThis code expires in 10 minutes.\nDo not share this code with anyone."

            response = sns.publish(
                PhoneNumber=phone_number,
                Message=message_body,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )

            return {
                'success': True,
                'provider': 'aws_sns',
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
                'error': f'AWS SNS error: {str(e)}'
            }


class EmailToSMSProvider(SMSProvider):
    """
    Free Email-to-SMS Gateway Provider

    Uses carrier email gateways to send SMS for free via email.
    Requires SMTP to be configured.

    Supported carriers:
    - AT&T: number@txt.att.net
    - T-Mobile: number@tmomail.net
    - Verizon: number@vtext.com
    - Sprint: number@messaging.sprintpcs.com
    - US Cellular: number@email.uscc.net
    - Virgin Mobile: number@vmobl.com
    - Boost Mobile: number@sms.myboostmobile.com
    - Cricket: number@sms.cricketwireless.net
    - Metro PCS: number@mymetropcs.com
    - Google Fi: number@msg.fi.google.com
    """

    # Carrier email gateways (SMS only, not MMS)
    CARRIER_GATEWAYS = {
        'att': 'txt.att.net',
        'tmobile': 'tmomail.net',
        'verizon': 'vtext.com',
        'sprint': 'messaging.sprintpcs.com',
        'uscellular': 'email.uscc.net',
        'virgin': 'vmobl.com',
        'boost': 'sms.myboostmobile.com',
        'cricket': 'sms.cricketwireless.net',
        'metro': 'mymetropcs.com',
        'googlefi': 'msg.fi.google.com',
        # International
        'rogers': 'pcs.rogers.com',  # Canada
        'bell': 'txt.bell.ca',  # Canada
        'telus': 'msg.telus.com',  # Canada
        'vodafone_uk': 'vodafone.net',  # UK (limited)
    }

    def __init__(self, default_carrier: str = None):
        """Initialize Email-to-SMS provider"""
        self.default_carrier = default_carrier

    def send_otp(self, phone_number: str, code: str, carrier: str = None) -> Dict:
        """
        Send OTP via email-to-SMS gateway

        Args:
            phone_number: Phone number (digits only, e.g., '1234567890')
            code: OTP code to send
            carrier: Carrier name (e.g., 'att', 'tmobile', 'verizon')
                    If not provided, uses default_carrier or tries common ones
        """
        try:
            # Import email service
            try:
                from university_system.infrastructure.email.email_service import send_email
                EMAIL_AVAILABLE = True
            except ImportError:
                try:
                    import smtplib
                    from email.mime.text import MIMEText
                    EMAIL_AVAILABLE = 'smtp'
                except ImportError:
                    EMAIL_AVAILABLE = False

            if not EMAIL_AVAILABLE:
                return {
                    'success': False,
                    'error': 'Email service not available for SMS gateway'
                }

            # Clean phone number (remove non-digits except +)
            clean_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')

            # Handle UK numbers (+44)
            if clean_number.startswith('+44'):
                clean_number = clean_number  # Keep as-is for Twilio
            elif clean_number.startswith('44') and len(clean_number) >= 12:
                clean_number = '+' + clean_number  # Add + prefix
            elif clean_number.startswith('0') and len(clean_number) == 11:
                # UK local format (07xxx) -> convert to +44
                clean_number = '+44' + clean_number[1:]
            elif clean_number.startswith('7') and len(clean_number) == 10:
                # UK without leading 0 -> add +44
                clean_number = '+44' + clean_number
            # Handle US numbers
            elif clean_number.startswith('1') and len(clean_number) == 11:
                clean_number = clean_number[1:]  # Remove US country code for gateway

            # Determine carrier
            carrier = carrier or self.default_carrier

            # If no carrier specified, try multiple common ones
            carriers_to_try = [carrier] if carrier else ['att', 'tmobile', 'verizon']

            message = f"Your verification code is: {code}"
            last_error = None

            for carr in carriers_to_try:
                if carr not in self.CARRIER_GATEWAYS:
                    continue

                gateway = self.CARRIER_GATEWAYS[carr]
                sms_email = f"{clean_number}@{gateway}"

                try:
                    if EMAIL_AVAILABLE == 'smtp':
                        # Use direct SMTP
                        success = self._send_via_smtp(sms_email, message)
                    else:
                        # Use email service
                        result = send_email(
                            to_email=sms_email,
                            subject="",  # SMS doesn't need subject
                            body=message
                        )
                        success = result.get('success', False)

                    if success:
                        return {
                            'success': True,
                            'provider': 'email_gateway',
                            'carrier': carr,
                            'message': f'SMS sent via {carr.upper()} email gateway'
                        }
                except Exception as e:
                    last_error = str(e)
                    continue

            return {
                'success': False,
                'error': f'Email-to-SMS failed: {last_error or "Unknown carrier or email error"}'
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Email-to-SMS error: {str(e)}'
            }

    def _send_via_smtp(self, to_email: str, message: str) -> bool:
        """Send via direct SMTP"""
        import smtplib
        from email.mime.text import MIMEText

        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USERNAME', '')
        smtp_pass = os.getenv('SMTP_PASSWORD', '')
        sender = os.getenv('SENDER_EMAIL', smtp_user)

        if not smtp_user or not smtp_pass:
            return False

        msg = MIMEText(message)
        msg['To'] = to_email
        msg['From'] = sender
        msg['Subject'] = ''

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return True

    @classmethod
    def get_supported_carriers(cls) -> Dict[str, str]:
        """Return dict of supported carriers and their gateways"""
        return cls.CARRIER_GATEWAYS.copy()


class MockSMSProvider(SMSProvider):
    """Mock SMS Provider for development/testing"""

    def __init__(self, log_file: str = None):
        """Initialize mock provider"""
        self.log_file = log_file or str(paths.TEMP_DIR / 'sms_otp_log.txt')

    def send_otp(self, phone_number: str, code: str) -> Dict:
        """Mock send - logs to file instead of sending SMS"""
        try:
            message = f"[{self._get_timestamp()}] SMS to {phone_number}: Your verification code is {code}\n"

            # Log to file
            with open(self.log_file, 'a') as f:
                f.write(message)

            # Also print to console for development
            print(f"📱 MOCK SMS: {phone_number} -> Code: {code}")

            return {
                'success': True,
                'provider': 'mock',
                'message': 'SMS logged (development mode)',
                'code': code  # Return code for easy testing
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Mock provider error: {str(e)}'
            }

    def _get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class SMSService:
    """
    Main SMS Service with provider management and fallback
    """

    def __init__(self, primary_provider: str = 'mock', fallback_provider: str = None):
        """
        Initialize SMS service with providers

        Args:
            primary_provider: Primary provider to use ('twilio', 'aws_sns', 'mock')
            fallback_provider: Fallback provider if primary fails
        """
        self.primary = self._create_provider(primary_provider)
        self.fallback = self._create_provider(fallback_provider) if fallback_provider else None

    def _create_provider(self, provider_name: str) -> Optional[SMSProvider]:
        """Create provider instance"""
        if not provider_name:
            return None

        provider_name = provider_name.lower()

        try:
            if provider_name == 'twilio':
                return TwilioSMSProvider()
            elif provider_name == 'aws_sns':
                return AWS_SNS_Provider()
            elif provider_name == 'email_gateway':
                return EmailToSMSProvider()
            elif provider_name == 'mock':
                return MockSMSProvider()
            else:
                print(f"Unknown provider: {provider_name}, using mock")
                return MockSMSProvider()
        except Exception as e:
            print(f"Failed to create {provider_name} provider: {e}, using mock")
            return MockSMSProvider()

    def send_otp(self, phone_number: str, code: str) -> Dict:
        """
        Send OTP with automatic fallback

        Args:
            phone_number: Recipient phone number (E.164 format recommended)
            code: OTP code to send

        Returns:
            Dict with success status and details
        """
        # Validate phone number format
        if not phone_number:
            return {'success': False, 'error': 'Phone number is required'}

        # Ensure phone number starts with +
        if not phone_number.startswith('+'):
            # Assume US number if no country code
            phone_number = '+1' + phone_number.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')

        # Try primary provider
        result = self.primary.send_otp(phone_number, code)

        if result['success']:
            return result

        # Try fallback if primary failed
        if self.fallback:
            print(f"Primary provider failed, trying fallback...")
            result = self.fallback.send_otp(phone_number, code)
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
def load_sms_config() -> Dict:
    """Load SMS provider configuration from file or environment"""
    config_file = paths.CONFIG_DIR / 'sms_config.json'

    # Try to load from config file
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load SMS config: {e}")

    # Smart default: Check if Twilio is configured
    twilio_configured = all([
        os.getenv('TWILIO_ACCOUNT_SID'),
        os.getenv('TWILIO_AUTH_TOKEN'),
        os.getenv('TWILIO_PHONE_NUMBER')
    ])

    # Check if SMTP is configured (for email gateway)
    smtp_configured = all([
        os.getenv('SMTP_USERNAME') or os.getenv('SMTP_USER'),
        os.getenv('SMTP_PASSWORD')
    ])

    # Choose best available provider
    if twilio_configured:
        primary = 'twilio'
        fallback = 'email_gateway' if smtp_configured else 'mock'
    elif smtp_configured:
        primary = 'email_gateway'
        fallback = 'mock'
    else:
        primary = os.getenv('SMS_PRIMARY_PROVIDER', 'mock')
        fallback = os.getenv('SMS_FALLBACK_PROVIDER', None)

    return {
        'primary_provider': primary,
        'fallback_provider': fallback
    }


# Default service instance
_default_service = None


def get_sms_service() -> SMSService:
    """Get or create default SMS service instance"""
    global _default_service

    if _default_service is None:
        config = load_sms_config()
        _default_service = SMSService(
            primary_provider=config.get('primary_provider', 'mock'),
            fallback_provider=config.get('fallback_provider')
        )

    return _default_service


def send_otp(phone_number: str, code: str) -> Dict:
    """Convenience function to send OTP"""
    service = get_sms_service()
    return service.send_otp(phone_number, code)


if __name__ == '__main__':
    # Test SMS service
    print("SMS Service Test\n" + "=" * 50)

    service = SMSService(primary_provider='mock')
    print(f"Providers: {service.get_provider_status()}\n")

    # Test send
    result = service.send_otp('+1234567890', '123456')
    print(f"Send result: {json.dumps(result, indent=2)}")

    # Test with different number formats
    test_numbers = [
        '1234567890',
        '(123) 456-7890',
        '+1-123-456-7890'
    ]

    print("\nTesting phone number formats:")
    for num in test_numbers:
        result = service.send_otp(num, '999999')
        print(f"  {num:20} -> {result['success']}")
