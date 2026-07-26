"""
Unified Communication Hub Module

Provides comprehensive multi-channel communication including:
- Email system (internal and external)
- SMS/text messaging
- Push notifications (mobile and web)
- Announcement broadcasting
- Message templates
- Communication preferences
- Emergency alerts

Manager:
    - CommunicationManager: Unified manager for all communication channels

Example Usage:
    from education_system.systems.university.services.communication import CommunicationManager

    comm_mgr = CommunicationManager()

    # Send email
    comm_mgr.queue_email(
        to_address="student@university.edu",
        subject="Welcome!",
        body="Welcome to the university!"
    )

    # Send SMS
    comm_mgr.queue_sms(
        phone_number="+1234567890",
        message_text="Your class has been cancelled"
    )

    # Create announcement
    comm_mgr.create_announcement(
        title="Campus Closure",
        content="Campus will be closed tomorrow",
        created_by=1,
        priority="high"
    )
"""

from education_system.systems.university.infrastructure.i18n import get_text, _

from education_system.systems.university.services.communication.communication_manager import CommunicationManager
from education_system.systems.university.services.communication.schema import create_communication_tables

__all__ = [
    'CommunicationManager',
    'create_communication_tables'
]
