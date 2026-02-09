"""
Monitoring and Observability Infrastructure

Provides application metrics, health checks, and alerting capabilities.
"""

from university_system.infrastructure.monitoring.metrics import (
    MetricsCollector,
    get_metrics_collector,
    track_operation,
    record_metric,
)

from university_system.infrastructure.monitoring.health_checks import (
    HealthChecker,
    HealthStatus,
    get_health_checker,
    check_system_health,
)

from university_system.infrastructure.monitoring.alerts import (
    AlertManager,
    AlertLevel,
    get_alert_manager,
    send_alert,
)

__all__ = [
    # Metrics
    'MetricsCollector',
    'get_metrics_collector',
    'track_operation',
    'record_metric',
    # Health Checks
    'HealthChecker',
    'HealthStatus',
    'get_health_checker',
    'check_system_health',
    # Alerts
    'AlertManager',
    'AlertLevel',
    'get_alert_manager',
    'send_alert',
]
