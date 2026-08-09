"""
Connection Pool Metrics for the University System.

Provides monitoring and metrics for database connection pool utilization,
helping identify connection issues and optimize pool configuration.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """Snapshot of connection pool metrics."""
    timestamp: datetime = field(default_factory=datetime.now)
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    wait_count: int = 0
    avg_wait_time_ms: float = 0.0
    max_wait_time_ms: float = 0.0
    connections_created: int = 0
    connections_closed: int = 0
    connection_errors: int = 0
    pool_exhausted_count: int = 0


@dataclass
class ConnectionEvent:
    """Record of a connection pool event."""
    timestamp: datetime
    event_type: str  # 'acquire', 'release', 'create', 'close', 'error', 'timeout'
    wait_time_ms: float = 0.0
    connection_id: Optional[int] = None
    details: Optional[str] = None


class PoolMetricsCollector:
    """
    Collects and provides metrics for connection pool monitoring.

    Example:
        >>> collector = PoolMetricsCollector()
        >>>
        >>> # Record events
        >>> collector.record_acquire(wait_time_ms=5.2)
        >>> collector.record_release()
        >>>
        >>> # Get metrics
        >>> metrics = collector.get_metrics()
        >>> print(f"Active connections: {metrics.active_connections}")
    """

    def __init__(
        self,
        pool_max_size: int = 10,
        pool_min_size: int = 2,
        history_size: int = 1000
    ):
        """
        Initialize metrics collector.

        Args:
            pool_max_size: Maximum pool size (for utilization calculations)
            pool_min_size: Minimum pool size
            history_size: Number of events to keep in history
        """
        self.pool_max_size = pool_max_size
        self.pool_min_size = pool_min_size
        self.history_size = history_size

        self._lock = threading.RLock()

        # Current state
        self._active_connections = 0
        self._total_connections = 0
        self._connection_id_counter = 0

        # Counters (cumulative)
        self._total_acquires = 0
        self._total_releases = 0
        self._total_creates = 0
        self._total_closes = 0
        self._total_errors = 0
        self._total_timeouts = 0
        self._pool_exhausted_count = 0

        # Wait time tracking
        self._wait_times: List[float] = []
        self._current_waiters = 0

        # Event history
        self._events: List[ConnectionEvent] = []

        # Time series for metrics over time
        self._metrics_history: List[PoolMetrics] = []
        self._last_snapshot_time = datetime.now()

        logger.info(
            f"PoolMetricsCollector initialized: max_size={pool_max_size}, "
            f"min_size={pool_min_size}"
        )

    def _add_event(self, event: ConnectionEvent) -> None:
        """Add event to history with size limit."""
        self._events.append(event)
        if len(self._events) > self.history_size:
            self._events = self._events[-self.history_size:]

    def record_acquire(
        self,
        wait_time_ms: float = 0.0,
        connection_id: Optional[int] = None
    ) -> None:
        """
        Record a connection acquisition.

        Args:
            wait_time_ms: Time spent waiting for connection
            connection_id: Optional connection identifier
        """
        with self._lock:
            self._active_connections += 1
            self._total_acquires += 1
            self._wait_times.append(wait_time_ms)

            # Keep only recent wait times
            if len(self._wait_times) > 1000:
                self._wait_times = self._wait_times[-1000:]

            self._add_event(ConnectionEvent(
                timestamp=datetime.now(),
                event_type='acquire',
                wait_time_ms=wait_time_ms,
                connection_id=connection_id
            ))

    def record_release(self, connection_id: Optional[int] = None) -> None:
        """
        Record a connection release.

        Args:
            connection_id: Optional connection identifier
        """
        with self._lock:
            self._active_connections = max(0, self._active_connections - 1)
            self._total_releases += 1

            self._add_event(ConnectionEvent(
                timestamp=datetime.now(),
                event_type='release',
                connection_id=connection_id
            ))

    def record_create(self, connection_id: Optional[int] = None) -> int:
        """
        Record a new connection creation.

        Args:
            connection_id: Optional connection identifier

        Returns:
            Assigned connection ID
        """
        with self._lock:
            self._total_connections += 1
            self._total_creates += 1
            self._connection_id_counter += 1
            conn_id = connection_id or self._connection_id_counter

            self._add_event(ConnectionEvent(
                timestamp=datetime.now(),
                event_type='create',
                connection_id=conn_id
            ))

            return conn_id

    def record_close(self, connection_id: Optional[int] = None) -> None:
        """
        Record a connection close.

        Args:
            connection_id: Optional connection identifier
        """
        with self._lock:
            self._total_connections = max(0, self._total_connections - 1)
            self._total_closes += 1

            self._add_event(ConnectionEvent(
                timestamp=datetime.now(),
                event_type='close',
                connection_id=connection_id
            ))

    def record_error(
        self,
        details: Optional[str] = None,
        connection_id: Optional[int] = None
    ) -> None:
        """
        Record a connection error.

        Args:
            details: Error details
            connection_id: Optional connection identifier
        """
        with self._lock:
            self._total_errors += 1

            self._add_event(ConnectionEvent(
                timestamp=datetime.now(),
                event_type='error',
                connection_id=connection_id,
                details=details
            ))

            logger.warning(f"Connection pool error recorded: {details}")

    def record_timeout(self, wait_time_ms: float = 0.0) -> None:
        """
        Record a connection acquisition timeout.

        Args:
            wait_time_ms: Time spent waiting before timeout
        """
        with self._lock:
            self._total_timeouts += 1
            self._pool_exhausted_count += 1

            self._add_event(ConnectionEvent(
                timestamp=datetime.now(),
                event_type='timeout',
                wait_time_ms=wait_time_ms,
                details='Connection pool exhausted'
            ))

            logger.warning(
                f"Connection pool timeout after {wait_time_ms:.2f}ms - "
                f"pool exhausted (count: {self._pool_exhausted_count})"
            )

    def record_waiter_start(self) -> None:
        """Record that a thread started waiting for a connection."""
        with self._lock:
            self._current_waiters += 1

    def record_waiter_end(self) -> None:
        """Record that a thread stopped waiting for a connection."""
        with self._lock:
            self._current_waiters = max(0, self._current_waiters - 1)

    def get_metrics(self) -> PoolMetrics:
        """
        Get current pool metrics snapshot.

        Returns:
            PoolMetrics with current state
        """
        with self._lock:
            avg_wait = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0.0
            max_wait = max(self._wait_times) if self._wait_times else 0.0

            return PoolMetrics(
                timestamp=datetime.now(),
                total_connections=self._total_connections,
                active_connections=self._active_connections,
                idle_connections=max(0, self._total_connections - self._active_connections),
                wait_count=self._current_waiters,
                avg_wait_time_ms=avg_wait,
                max_wait_time_ms=max_wait,
                connections_created=self._total_creates,
                connections_closed=self._total_closes,
                connection_errors=self._total_errors,
                pool_exhausted_count=self._pool_exhausted_count,
            )

    def get_utilization(self) -> float:
        """
        Get current pool utilization percentage.

        Returns:
            Utilization as percentage (0-100)
        """
        with self._lock:
            if self.pool_max_size == 0:
                return 0.0
            return (self._active_connections / self.pool_max_size) * 100

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive pool statistics.

        Returns:
            Dictionary with all statistics
        """
        metrics = self.get_metrics()

        with self._lock:
            # Calculate percentiles for wait times
            p50, p95, p99 = 0.0, 0.0, 0.0
            if self._wait_times:
                sorted_times = sorted(self._wait_times)
                n = len(sorted_times)
                p50 = sorted_times[int(n * 0.50)]
                p95 = sorted_times[int(n * 0.95)]
                p99 = sorted_times[min(int(n * 0.99), n - 1)]

            return {
                'current': {
                    'total_connections': metrics.total_connections,
                    'active_connections': metrics.active_connections,
                    'idle_connections': metrics.idle_connections,
                    'waiting_threads': self._current_waiters,
                    'utilization_percent': self.get_utilization(),
                },
                'cumulative': {
                    'total_acquires': self._total_acquires,
                    'total_releases': self._total_releases,
                    'total_creates': self._total_creates,
                    'total_closes': self._total_closes,
                    'total_errors': self._total_errors,
                    'total_timeouts': self._total_timeouts,
                    'pool_exhausted_count': self._pool_exhausted_count,
                },
                'wait_times': {
                    'avg_ms': metrics.avg_wait_time_ms,
                    'max_ms': metrics.max_wait_time_ms,
                    'p50_ms': p50,
                    'p95_ms': p95,
                    'p99_ms': p99,
                },
                'config': {
                    'max_size': self.pool_max_size,
                    'min_size': self.pool_min_size,
                },
            }

    def get_recent_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[ConnectionEvent]:
        """
        Get recent connection pool events.

        Args:
            event_type: Filter by event type
            limit: Maximum events to return

        Returns:
            List of ConnectionEvent objects
        """
        with self._lock:
            events = self._events
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            return events[-limit:]

    def take_snapshot(self) -> PoolMetrics:
        """
        Take and store a metrics snapshot.

        Returns:
            The captured PoolMetrics
        """
        metrics = self.get_metrics()

        with self._lock:
            self._metrics_history.append(metrics)
            # Keep last 24 hours of hourly snapshots (max 24 entries)
            if len(self._metrics_history) > 1440:  # 24 hours of per-minute snapshots
                self._metrics_history = self._metrics_history[-1440:]
            self._last_snapshot_time = datetime.now()

        return metrics

    def get_metrics_history(
        self,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[PoolMetrics]:
        """
        Get historical metrics snapshots.

        Args:
            since: Only return metrics after this time
            limit: Maximum snapshots to return

        Returns:
            List of PoolMetrics snapshots
        """
        with self._lock:
            history = self._metrics_history
            if since:
                history = [m for m in history if m.timestamp > since]
            return history[-limit:]

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._active_connections = 0
            self._total_connections = 0
            self._total_acquires = 0
            self._total_releases = 0
            self._total_creates = 0
            self._total_closes = 0
            self._total_errors = 0
            self._total_timeouts = 0
            self._pool_exhausted_count = 0
            self._wait_times.clear()
            self._current_waiters = 0
            self._events.clear()
            self._metrics_history.clear()

        logger.info("Pool metrics reset")


# Global metrics collector instance
_pool_metrics: Optional[PoolMetricsCollector] = None
_metrics_lock = threading.Lock()


def get_pool_metrics(
    pool_max_size: int = 10,
    pool_min_size: int = 2
) -> PoolMetricsCollector:
    """
    Get or create the global pool metrics collector.

    Args:
        pool_max_size: Maximum pool size
        pool_min_size: Minimum pool size

    Returns:
        PoolMetricsCollector instance
    """
    global _pool_metrics

    if _pool_metrics is None:
        with _metrics_lock:
            if _pool_metrics is None:
                _pool_metrics = PoolMetricsCollector(
                    pool_max_size=pool_max_size,
                    pool_min_size=pool_min_size
                )

    return _pool_metrics


__all__ = [
    'PoolMetrics',
    'PoolMetricsCollector',
    'ConnectionEvent',
    'get_pool_metrics',
]
