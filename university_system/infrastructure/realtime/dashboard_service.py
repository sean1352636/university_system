"""
Real-Time Dashboard Service

Provides live dashboard updates and metrics streaming.
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime
from enum import Enum
from .websocket_manager import get_websocket_manager, MessageType

logger = logging.getLogger(__name__)


class DashboardMetric(str, Enum):
    """Dashboard metric types"""
    STUDENT_COUNT = "student_count"
    ENROLLMENT_COUNT = "enrollment_count"
    COURSE_COUNT = "course_count"
    ASSIGNMENT_DUE = "assignment_due"
    GRADE_AVERAGE = "grade_average"
    ATTENDANCE_RATE = "attendance_rate"
    PAYMENT_STATUS = "payment_status"
    SYSTEM_HEALTH = "system_health"


class DashboardService:
    """
    Service for real-time dashboard updates.

    Streams live metrics and data updates to dashboard views.
    """

    def __init__(self):
        """Initialize dashboard service"""
        self.ws_manager = get_websocket_manager()

        # Store current metric values
        # metric_name -> value
        self.current_metrics: Dict[str, Any] = {}

        # user_id -> list of subscribed metrics
        self.metric_subscriptions: Dict[str, List[str]] = {}

    async def update_metric(
        self,
        metric: DashboardMetric,
        value: Any,
        metadata: Optional[dict] = None,
        broadcast: bool = True
    ):
        """
        Update a dashboard metric.

        Args:
            metric: Metric identifier
            value: New metric value
            metadata: Additional metadata
            broadcast: Whether to broadcast update to subscribed users
        """
        metric_data = {
            "metric": metric.value,
            "value": value,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        # Store current value
        self.current_metrics[metric.value] = metric_data

        # Broadcast if requested
        if broadcast:
            await self._broadcast_metric_update(metric_data)

        logger.info(f"Dashboard metric updated: {metric.value} = {value}")

    async def update_multiple_metrics(
        self,
        metrics: Dict[DashboardMetric, Any],
        broadcast: bool = True
    ):
        """
        Update multiple metrics at once.

        Args:
            metrics: Dictionary of metric -> value
            broadcast: Whether to broadcast updates
        """
        for metric, value in metrics.items():
            await self.update_metric(metric, value, broadcast=False)

        # Broadcast all updates together if requested
        if broadcast:
            update_data = {
                "type": MessageType.DASHBOARD_UPDATE,
                "update_type": "multiple_metrics",
                "metrics": {
                    metric.value: self.current_metrics.get(metric.value)
                    for metric in metrics.keys()
                },
                "timestamp": datetime.utcnow().isoformat()
            }

            await self._broadcast_to_subscribed_users(update_data)

    async def subscribe_to_metrics(
        self,
        user_id: str,
        metrics: Optional[List[DashboardMetric]] = None
    ):
        """
        Subscribe a user to metric updates.

        Args:
            user_id: User identifier
            metrics: List of metrics to subscribe to (None = all)
        """
        if metrics:
            metric_names = [m.value for m in metrics]
            self.metric_subscriptions[user_id] = metric_names
        else:
            # Subscribe to all metrics
            self.metric_subscriptions[user_id] = [m.value for m in DashboardMetric]

        # Send current values to user
        await self._send_current_metrics(user_id)

        logger.info(f"User {user_id} subscribed to dashboard metrics")

    async def unsubscribe_from_metrics(self, user_id: str):
        """
        Unsubscribe a user from metric updates.

        Args:
            user_id: User identifier
        """
        if user_id in self.metric_subscriptions:
            del self.metric_subscriptions[user_id]

        logger.info(f"User {user_id} unsubscribed from dashboard metrics")

    async def send_dashboard_alert(
        self,
        user_ids: List[str],
        alert_type: str,
        title: str,
        message: str,
        severity: str = "info",
        data: Optional[dict] = None
    ):
        """
        Send an alert to dashboard users.

        Args:
            user_ids: List of user IDs to notify
            alert_type: Type of alert
            title: Alert title
            message: Alert message
            severity: Alert severity (info, warning, error)
            data: Additional data
        """
        alert = {
            "type": MessageType.DASHBOARD_UPDATE,
            "update_type": "alert",
            "alert_type": alert_type,
            "title": title,
            "message": message,
            "severity": severity,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        for user_id in user_ids:
            await self.ws_manager.send_to_user(user_id, alert)

    async def broadcast_system_status(
        self,
        status: str,
        message: Optional[str] = None
    ):
        """
        Broadcast system status update to all dashboard users.

        Args:
            status: System status (operational, degraded, outage)
            message: Optional status message
        """
        status_update = {
            "type": MessageType.DASHBOARD_UPDATE,
            "update_type": "system_status",
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self._broadcast_to_subscribed_users(status_update)

    def get_current_metrics(self, metrics: Optional[List[DashboardMetric]] = None) -> Dict[str, Any]:
        """
        Get current metric values.

        Args:
            metrics: Specific metrics to retrieve (None = all)

        Returns:
            Dictionary of metric values
        """
        if metrics:
            metric_names = [m.value for m in metrics]
            return {
                name: self.current_metrics.get(name)
                for name in metric_names
                if name in self.current_metrics
            }
        else:
            return self.current_metrics.copy()

    async def _broadcast_metric_update(self, metric_data: dict):
        """
        Broadcast metric update to subscribed users.

        Args:
            metric_data: Metric update data
        """
        update_message = {
            "type": MessageType.DASHBOARD_UPDATE,
            "update_type": "metric",
            **metric_data
        }

        await self._broadcast_to_subscribed_users(update_message)

    async def _broadcast_to_subscribed_users(self, message: dict):
        """
        Broadcast message to users subscribed to dashboard updates.

        Args:
            message: Message to broadcast
        """
        metric_name = message.get("metric")

        for user_id, subscribed_metrics in self.metric_subscriptions.items():
            # If specific metric, check subscription
            if metric_name and metric_name not in subscribed_metrics:
                continue

            await self.ws_manager.send_to_user(user_id, message)

    async def _send_current_metrics(self, user_id: str):
        """
        Send current metric values to a user.

        Args:
            user_id: User identifier
        """
        if user_id not in self.metric_subscriptions:
            return

        subscribed_metrics = self.metric_subscriptions[user_id]
        current_values = {
            metric: self.current_metrics.get(metric)
            for metric in subscribed_metrics
            if metric in self.current_metrics
        }

        message = {
            "type": MessageType.DASHBOARD_UPDATE,
            "update_type": "initial_data",
            "metrics": current_values,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.ws_manager.send_to_user(user_id, message)


# Global dashboard service instance
_dashboard_service: Optional[DashboardService] = None


def get_dashboard_service() -> DashboardService:
    """
    Get the global dashboard service instance.

    Returns:
        DashboardService instance
    """
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service
