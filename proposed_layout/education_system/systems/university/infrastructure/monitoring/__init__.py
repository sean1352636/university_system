"""
Monitoring and Observability Infrastructure

Provides application metrics, health checks, and alerting capabilities.
"""

from education_system.systems.university.infrastructure.monitoring.metrics import (
    MetricsCollector,
    get_metrics_collector,
    track_operation,
    record_metric,
)

from education_system.systems.university.infrastructure.monitoring.health_checks import (
    HealthChecker,
    HealthStatus,
    get_health_checker,
    check_system_health,
)

from education_system.systems.university.infrastructure.monitoring.alerts import (
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
