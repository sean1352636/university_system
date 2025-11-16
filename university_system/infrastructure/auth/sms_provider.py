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

    def send_otp(self, phone_number: str, code: str) -> Dict:
        """Send OTP via Twilio"""
        try:
            from twilio.rest import Client

            client = Client(self.account_sid, self.auth_token)

            message_body = f"Your University System verification code is: {code}\n\nThis code expires in 10 minutes.\nDo not share this code with anyone."

            message = client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=phone_number
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

    # Default configuration
    return {
        'primary_provider': os.getenv('SMS_PRIMARY_PROVIDER', 'mock'),
        'fallback_provider': os.getenv('SMS_FALLBACK_PROVIDER', None)
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
