"""Central Communication Infrastructure

This package provides unified communication services for the University System.

Services:
- SMS: Central SMS service for notifications (sms_service.py)
- Email: Uses infrastructure.email.email_service
- Templates: Email template management
- Logging: Communication audit trail

For MFA-specific SMS/Email, use infrastructure.auth modules instead.
"""

from university_system.infrastructure.communication.sms_service import (
    SMSService,
    SMSProvider,
    get_sms_service,
    send_sms,
    send_bulk_sms
)

__all__ = [
    'SMSService',
    'SMSProvider',
    'get_sms_service',
    'send_sms',
    'send_bulk_sms'
]
