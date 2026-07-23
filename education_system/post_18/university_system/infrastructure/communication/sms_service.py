"""Central SMS Service for University System

This module provides centralized SMS functionality for non-MFA use cases.
For MFA OTP delivery, use infrastructure.auth.sms_provider instead.

Supported Providers:
- Twilio (primary)
- AWS SNS (alternative)
- Mock (development/testing)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core import paths

logger = logging.getLogger(__name__)


class SMSProvider(Enum):
    """SMS provider types"""
    TWILIO = "twilio"
    AWS_SNS = "aws_sns"
    MOCK = "mock"


class SMSService:
    """Central SMS service for university communications"""

    def __init__(self, provider: SMSProvider = SMSProvider.MOCK):
        """
        Initialize SMS service with specified provider.

        Args:
            provider: SMS provider to use (default: MOCK for safety)
        """
        self.provider = provider
        self.config = self._load_config()
        self._ensure_sms_log_table()

    def _load_config(self) -> Dict[str, Any]:
        """Load SMS configuration from database or environment"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT provider, config_json
                    FROM sms_config
                    WHERE is_active = 1
                    ORDER BY updated_at DESC
                    LIMIT 1
                """)
                result = cursor.fetchone()

                if result:
                    import json
                    return json.loads(result[1])
        except Exception as e:
            logger.warning(f"Could not load SMS config from database: {e}")

        # Default configuration
        return {
            'twilio': {
                'account_sid': '',
                'auth_token': '',
                'from_number': ''
            },
            'aws_sns': {
                'access_key': '',
                'secret_key': '',
                'region': 'us-east-1'
            }
        }

    def _ensure_sms_log_table(self):
        """Ensure SMS log table exists"""
        try:
            with transaction() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sms_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recipient_phone TEXT NOT NULL,
                        message TEXT NOT NULL,
                        provider TEXT,
                        status TEXT DEFAULT 'sent',
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        student_id TEXT,
                        related_to TEXT,
                        error_message TEXT,
                        message_sid TEXT
                    )
                """)
                logger.info("SMS log table ensured")
        except Exception as e:
            logger.error(f"Error creating sms_log table: {e}")

    def send_sms(
        self,
        phone_number: str,
        message: str,
        student_id: Optional[str] = None,
        related_to: Optional[str] = None
    ) -> bool:
        """
        Send SMS message.

        Args:
            phone_number: Recipient phone number (E.164 format recommended)
            message: SMS message content
            student_id: Student ID for logging
            related_to: What this SMS relates to (e.g., 'calendar_reminder')

        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Validate phone number
        if not phone_number or not isinstance(phone_number, str):
            logger.error("Invalid phone number")
            return False

        # Clean phone number
        phone_number = self._clean_phone_number(phone_number)

        # Validate message
        if not message or len(message) > 1600:  # SMS limit
            logger.error(f"Invalid message length: {len(message) if message else 0}")
            return False

        # Send via appropriate provider
        result = False
        error_message = None
        message_sid = None

        try:
            if self.provider == SMSProvider.TWILIO:
                result, message_sid, error_message = self._send_via_twilio(phone_number, message)
            elif self.provider == SMSProvider.AWS_SNS:
                result, message_sid, error_message = self._send_via_aws_sns(phone_number, message)
            elif self.provider == SMSProvider.MOCK:
                result, message_sid, error_message = self._send_via_mock(phone_number, message)
            else:
                error_message = f"Unknown provider: {self.provider}"
                logger.error(error_message)
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error sending SMS: {e}")

        # Log the SMS
        self._log_sms(
            phone_number,
            message,
            'sent' if result else 'failed',
            student_id,
            related_to,
            error_message,
            message_sid
        )

        return result

    def _send_via_twilio(self, phone_number: str, message: str) -> tuple:
        """Send SMS via Twilio"""
        try:
            from twilio.rest import Client

            account_sid = self.config.get('twilio', {}).get('account_sid')
            auth_token = self.config.get('twilio', {}).get('auth_token')
            from_number = self.config.get('twilio', {}).get('from_number')

            if not all([account_sid, auth_token, from_number]):
                return False, None, "Twilio credentials not configured"

            client = Client(account_sid, auth_token)
            sms = client.messages.create(
                body=message,
                from_=from_number,
                to=phone_number
            )

            logger.info(f"SMS sent via Twilio: {sms.sid}")
            return True, sms.sid, None

        except Exception as e:
            logger.error(f"Twilio error: {e}")
            return False, None, str(e)

    def _send_via_aws_sns(self, phone_number: str, message: str) -> tuple:
        """Send SMS via AWS SNS"""
        try:
            import boto3

            access_key = self.config.get('aws_sns', {}).get('access_key')
            secret_key = self.config.get('aws_sns', {}).get('secret_key')
            region = self.config.get('aws_sns', {}).get('region', 'us-east-1')

            if not all([access_key, secret_key]):
                return False, None, "AWS SNS credentials not configured"

            sns = boto3.client(
                'sns',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )

            response = sns.publish(
                PhoneNumber=phone_number,
                Message=message
            )

            message_id = response.get('MessageId')
            logger.info(f"SMS sent via AWS SNS: {message_id}")
            return True, message_id, None

        except Exception as e:
            logger.error(f"AWS SNS error: {e}")
            return False, None, str(e)

    def _send_via_mock(self, phone_number: str, message: str) -> tuple:
        """Mock SMS sending for development"""
        logger.info(f"[MOCK SMS] To: {phone_number}")
        logger.info(f"[MOCK SMS] Message: {message}")
        print(f"\n{'='*60}")
        print("MOCK SMS SENT")
        print(f"{'='*60}")
        print(f"To: {phone_number}")
        print(f"Message: {message}")
        print(f"{'='*60}\n")
        return True, f"MOCK-{datetime.now().strftime('%Y%m%d%H%M%S')}", None

    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number"""
        # Remove common formatting characters
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

        # Ensure E.164 format for international numbers
        if not cleaned.startswith('+'):
            # Assume UK number if no country code
            if cleaned.startswith('0'):
                cleaned = '+44' + cleaned[1:]
            elif len(cleaned) == 10:
                cleaned = '+44' + cleaned
            else:
                cleaned = '+' + cleaned

        return cleaned

    def _log_sms(
        self,
        phone_number: str,
        message: str,
        status: str,
        student_id: Optional[str],
        related_to: Optional[str],
        error_message: Optional[str],
        message_sid: Optional[str]
    ):
        """Log SMS to database"""
        try:
            with transaction() as conn:
                conn.execute("""
                    INSERT INTO sms_log
                    (recipient_phone, message, provider, status, student_id,
                     related_to, error_message, message_sid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    phone_number,
                    message,
                    self.provider.value,
                    status,
                    student_id,
                    related_to,
                    error_message,
                    message_sid
                ))
                logger.debug(f"SMS logged to database: {phone_number}")
        except Exception as e:
            logger.error(f"Error logging SMS: {e}")

    def send_bulk_sms(
        self,
        recipients: List[str],
        message: str,
        student_ids: Optional[List[str]] = None,
        related_to: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Send SMS to multiple recipients.

        Args:
            recipients: List of phone numbers
            message: SMS message
            student_ids: List of student IDs (optional)
            related_to: What this relates to

        Returns:
            dict: {'sent': count, 'failed': count}
        """
        results = {'sent': 0, 'failed': 0}

        for i, phone in enumerate(recipients):
            student_id = student_ids[i] if student_ids and i < len(student_ids) else None

            if self.send_sms(phone, message, student_id, related_to):
                results['sent'] += 1
            else:
                results['failed'] += 1

        logger.info(f"Bulk SMS results: {results}")
        return results

    def get_sms_log(
        self,
        limit: int = 50,
        student_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve SMS log entries.

        Args:
            limit: Maximum entries to return
            student_id: Filter by student ID
            status: Filter by status ('sent' or 'failed')

        Returns:
            List of SMS log entries
        """
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM sms_log WHERE 1=1"
                params = []

                if student_id:
                    query += " AND student_id = ?"
                    params.append(student_id)

                if status:
                    query += " AND status = ?"
                    params.append(status)

                query += " ORDER BY sent_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)

                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error retrieving SMS log: {e}")
            return []


# Global SMS service instance (using MOCK by default for safety)
_sms_service = None


def get_sms_service(provider: SMSProvider = SMSProvider.MOCK) -> SMSService:
    """
    Get or create global SMS service instance.

    Args:
        provider: SMS provider to use

    Returns:
        SMSService instance
    """
    global _sms_service

    if _sms_service is None:
        _sms_service = SMSService(provider)

    return _sms_service


def send_sms(phone_number: str, message: str, **kwargs) -> bool:
    """
    Convenience function to send SMS via global service.

    Args:
        phone_number: Recipient phone number
        message: SMS message
        **kwargs: Additional arguments (student_id, related_to)

    Returns:
        bool: True if sent successfully
    """
    service = get_sms_service()
    return service.send_sms(phone_number, message, **kwargs)


def send_bulk_sms(recipients: List[str], message: str, **kwargs) -> Dict[str, int]:
    """
    Convenience function for bulk SMS.

    Args:
        recipients: List of phone numbers
        message: SMS message
        **kwargs: Additional arguments

    Returns:
        dict: Send results
    """
    service = get_sms_service()
    return service.send_bulk_sms(recipients, message, **kwargs)
