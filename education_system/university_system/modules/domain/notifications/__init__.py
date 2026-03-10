"""
Smart Notifications Hub Module

Unified notification management system for the university platform.

Components:
- services: Core notification service layer
- cli: Command-line interface
- gui: Graphical user interface

Features:
- Multi-channel notifications (academic, social, financial, health, housing, events)
- Priority levels (low, medium, high, urgent)
- Quiet hours scheduling
- Daily digest compilation
- Smart notification bundling
- Multiple delivery methods (push, email, SMS)
- Comprehensive preferences management
"""

from education_system.university_system.modules.domain.notifications.services.notifications_service import (
    NotificationsService,
    NotificationPriority,
    NotificationChannel,
    DeliveryMethod
)

__all__ = [
    'NotificationsService',
    'NotificationPriority',
    'NotificationChannel',
    'DeliveryMethod'
]
