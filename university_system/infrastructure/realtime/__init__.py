"""
Real-time collaboration infrastructure for University Management System.

This module provides WebSocket-based real-time features including:
- Live notifications
- Real-time dashboard updates
- Chat support
- Collaborative document editing
- User presence tracking
- Activity streams
"""

from .websocket_manager import (
    WebSocketManager,
    MessageType,
    get_websocket_manager,
)
from .connection_manager import (
    ConnectionManager,
    get_connection_manager,
)
from .notification_service import (
    NotificationService,
    NotificationPriority,
    NotificationCategory,
    get_notification_service,
)
from .presence_manager import (
    PresenceManager,
    UserStatus,
    get_presence_manager,
)
from .chat_service import (
    ChatService,
    ChatRoomType,
    ChatMessageType,
    get_chat_service,
)
from .collaboration_service import (
    CollaborationService,
    DocumentType,
    OperationType,
    get_collaboration_service,
)
from .activity_stream import (
    ActivityStream,
    ActivityType,
    ActivityVisibility,
    get_activity_stream,
)
from .dashboard_service import (
    DashboardService,
    DashboardMetric,
    get_dashboard_service,
)

__all__ = [
    # Core managers
    'WebSocketManager',
    'ConnectionManager',
    'get_websocket_manager',
    'get_connection_manager',

    # Notification service
    'NotificationService',
    'NotificationPriority',
    'NotificationCategory',
    'get_notification_service',

    # Presence service
    'PresenceManager',
    'UserStatus',
    'get_presence_manager',

    # Chat service
    'ChatService',
    'ChatRoomType',
    'ChatMessageType',
    'get_chat_service',

    # Collaboration service
    'CollaborationService',
    'DocumentType',
    'OperationType',
    'get_collaboration_service',

    # Activity stream
    'ActivityStream',
    'ActivityType',
    'ActivityVisibility',
    'get_activity_stream',

    # Dashboard service
    'DashboardService',
    'DashboardMetric',
    'get_dashboard_service',

    # Message types
    'MessageType',
]
