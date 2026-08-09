"""
Database Query Performance Monitoring for the University System.

Provides slow query detection, query performance logging, and analytics
to help identify and optimize problematic database queries.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
query_logger = logging.getLogger('query_performance')


@dataclass
class QueryMetrics:
    """Metrics for a single query execution."""
    query: str
    duration_ms: float
    timestamp: datetime
    rows_affected: int = 0
    was_slow: bool = False
    params_hash: Optional[str] = None


@dataclass
class QueryStats:
    """Aggregated statistics for a query pattern."""
    query_pattern: str
    total_executions: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0.0
    slow_count: int = 0
    last_execution: Optional[datetime] = None
    execution_times: List[float] = field(default_factory=list)

    @property
    def avg_time_ms(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_time_ms / self.total_executions

    @property
    def slow_percentage(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return (self.slow_count / self.total_executions) * 100


class QueryTimer:
    """
    Context manager for timing database queries.

    Example:
        >>> with QueryTimer("SELECT * FROM students WHERE id = ?") as timer:
        ...     cursor.execute(query, params)
        ...     result = cursor.fetchall()
        >>> print(f"Query took {timer.elapsed_ms:.2f}ms")
    """

    SLOW_QUERY_THRESHOLD_MS = 100  # Default threshold

    def __init__(
        self,
        query: str,
        threshold_ms: Optional[float] = None,
        log_slow: bool = True,
        monitor: Optional['QueryMonitor'] = None
    ):
        """
        Initialize query timer.

        Args:
            query: The SQL query being timed
            threshold_ms: Custom slow query threshold (uses default if None)
            log_slow: Whether to log slow queries
            monitor: QueryMonitor instance to record metrics
        """
        self.query = query
        self.threshold_ms = threshold_ms or self.SLOW_QUERY_THRESHOLD_MS
        self.log_slow = log_slow
        self.monitor = monitor
        self.start_time: Optional[float] = None
        self.elapsed_ms: float = 0.0
        self.is_slow: bool = False

    def __enter__(self) -> 'QueryTimer':
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.start_time is not None:
            self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
            self.is_slow = self.elapsed_ms > self.threshold_ms

            if self.is_slow and self.log_slow:
                # Truncate query for logging
                query_preview = self.query[:200] + "..." if len(self.query) > 200 else self.query
                query_logger.warning(
                    f"Slow query ({self.elapsed_ms:.2f}ms, threshold: {self.threshold_ms}ms): "
                    f"{query_preview}"
                )

            if self.monitor:
                self.monitor.record_query(
                    query=self.query,
                    duration_ms=self.elapsed_ms,
                    was_slow=self.is_slow
                )

        return False  # Don't suppress exceptions


class QueryMonitor:
    """
    Thread-safe query performance monitor with statistics and slow query detection.

    Example:
        >>> monitor = QueryMonitor(slow_threshold_ms=100)
        >>>
        >>> # Record a query
        >>> monitor.record_query("SELECT * FROM students", 50.0)
        >>>
        >>> # Get statistics
        >>> stats = monitor.get_stats()
        >>> print(f"Total queries: {stats['total_queries']}")
        >>>
        >>> # Get slow queries
        >>> slow = monitor.get_slow_queries()
    """

    def __init__(
        self,
        slow_threshold_ms: float = 100.0,
        max_history: int = 10000,
        stats_retention_hours: int = 24
    ):
        """
        Initialize query monitor.

        Args:
            slow_threshold_ms: Threshold for slow query detection
            max_history: Maximum number of query metrics to retain
            stats_retention_hours: How long to keep detailed stats
        """
        self.slow_threshold_ms = slow_threshold_ms
        self.max_history = max_history
        self.stats_retention_hours = stats_retention_hours

        self._history: List[QueryMetrics] = []
        self._query_stats: Dict[str, QueryStats] = defaultdict(
            lambda: QueryStats(query_pattern="")
        )
        self._lock = threading.RLock()

        # Counters
        self._total_queries = 0
        self._slow_queries = 0
        self._total_time_ms = 0.0

        logger.info(f"QueryMonitor initialized with slow_threshold={slow_threshold_ms}ms")

    def _normalize_query(self, query: str) -> str:
        """
        Normalize a query for aggregation (remove specific values).

        This helps group similar queries together for statistics.
        """
        import re

        # Replace multiple spaces/newlines with single space
        normalized = ' '.join(query.split())

        # Replace specific values with placeholders for pattern matching
        # Numbers
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        # Quoted strings
        normalized = re.sub(r"'[^']*'", '?', normalized)
        normalized = re.sub(r'"[^"]*"', '?', normalized)
        # Parameter placeholders (already normalized)
        normalized = re.sub(r'\?+', '?', normalized)

        return normalized

    def record_query(
        self,
        query: str,
        duration_ms: float,
        rows_affected: int = 0,
        was_slow: Optional[bool] = None
    ) -> None:
        """
        Record a query execution.

        Args:
            query: The SQL query executed
            duration_ms: Query duration in milliseconds
            rows_affected: Number of rows affected
            was_slow: Override slow detection (auto-detect if None)
        """
        if was_slow is None:
            was_slow = duration_ms > self.slow_threshold_ms

        metric = QueryMetrics(
            query=query,
            duration_ms=duration_ms,
            timestamp=datetime.now(),
            rows_affected=rows_affected,
            was_slow=was_slow
        )

        with self._lock:
            # Update counters
            self._total_queries += 1
            self._total_time_ms += duration_ms
            if was_slow:
                self._slow_queries += 1

            # Add to history (with limit)
            self._history.append(metric)
            if len(self._history) > self.max_history:
                self._history = self._history[-self.max_history:]

            # Update query pattern stats
            pattern = self._normalize_query(query)
            stats = self._query_stats[pattern]
            stats.query_pattern = pattern
            stats.total_executions += 1
            stats.total_time_ms += duration_ms
            stats.min_time_ms = min(stats.min_time_ms, duration_ms)
            stats.max_time_ms = max(stats.max_time_ms, duration_ms)
            stats.last_execution = datetime.now()
            if was_slow:
                stats.slow_count += 1

            # Keep recent execution times for percentile calculations
            stats.execution_times.append(duration_ms)
            if len(stats.execution_times) > 100:
                stats.execution_times = stats.execution_times[-100:]

    def get_slow_queries(
        self,
        limit: int = 50,
        since: Optional[datetime] = None
    ) -> List[QueryMetrics]:
        """
        Get recent slow queries.

        Args:
            limit: Maximum number of queries to return
            since: Only return queries after this time

        Returns:
            List of slow QueryMetrics
        """
        with self._lock:
            slow = [m for m in self._history if m.was_slow]
            if since:
                slow = [m for m in slow if m.timestamp > since]
            return sorted(slow, key=lambda x: x.duration_ms, reverse=True)[:limit]

    def get_query_stats(self, top_n: int = 20) -> List[QueryStats]:
        """
        Get statistics for top queries by total time.

        Args:
            top_n: Number of query patterns to return

        Returns:
            List of QueryStats sorted by total time
        """
        with self._lock:
            stats = list(self._query_stats.values())
            return sorted(stats, key=lambda x: x.total_time_ms, reverse=True)[:top_n]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get overall query monitoring statistics.

        Returns:
            Dictionary with monitoring statistics
        """
        with self._lock:
            avg_time = self._total_time_ms / self._total_queries if self._total_queries > 0 else 0

            return {
                'total_queries': self._total_queries,
                'slow_queries': self._slow_queries,
                'slow_percentage': (self._slow_queries / self._total_queries * 100) if self._total_queries > 0 else 0,
                'total_time_ms': self._total_time_ms,
                'avg_time_ms': avg_time,
                'unique_query_patterns': len(self._query_stats),
                'history_size': len(self._history),
                'slow_threshold_ms': self.slow_threshold_ms,
            }

    def get_percentile(self, percentile: float = 95.0) -> float:
        """
        Get the query time at a given percentile.

        Args:
            percentile: Percentile to calculate (0-100)

        Returns:
            Query time in ms at the given percentile
        """
        with self._lock:
            if not self._history:
                return 0.0

            times = sorted([m.duration_ms for m in self._history])
            index = int(len(times) * percentile / 100)
            return times[min(index, len(times) - 1)]

    def reset(self) -> None:
        """Reset all monitoring data."""
        with self._lock:
            self._history.clear()
            self._query_stats.clear()
            self._total_queries = 0
            self._slow_queries = 0
            self._total_time_ms = 0.0
            logger.info("QueryMonitor reset")

    @contextmanager
    def time_query(self, query: str, threshold_ms: Optional[float] = None):
        """
        Context manager for timing a query.

        Args:
            query: The SQL query
            threshold_ms: Custom slow threshold

        Yields:
            QueryTimer instance

        Example:
            >>> with monitor.time_query("SELECT * FROM students") as timer:
            ...     cursor.execute(query)
            ...     results = cursor.fetchall()
        """
        timer = QueryTimer(
            query=query,
            threshold_ms=threshold_ms or self.slow_threshold_ms,
            log_slow=True,
            monitor=self
        )
        with timer:
            yield timer


# Global monitor instance
_query_monitor: Optional[QueryMonitor] = None
_monitor_lock = threading.Lock()


def get_query_monitor(
    slow_threshold_ms: float = 100.0,
    max_history: int = 10000
) -> QueryMonitor:
    """
    Get or create the global query monitor instance.

    Args:
        slow_threshold_ms: Threshold for slow query detection
        max_history: Maximum history size

    Returns:
        QueryMonitor instance
    """
    global _query_monitor

    if _query_monitor is None:
        with _monitor_lock:
            if _query_monitor is None:
                _query_monitor = QueryMonitor(
                    slow_threshold_ms=slow_threshold_ms,
                    max_history=max_history
                )

    return _query_monitor


def time_query(query: str, threshold_ms: Optional[float] = None) -> QueryTimer:
    """
    Create a QueryTimer using the global monitor.

    Args:
        query: The SQL query
        threshold_ms: Custom slow threshold

    Returns:
        QueryTimer instance
    """
    monitor = get_query_monitor()
    return QueryTimer(
        query=query,
        threshold_ms=threshold_ms,
        log_slow=True,
        monitor=monitor
    )


__all__ = [
    'QueryTimer',
    'QueryMonitor',
    'QueryMetrics',
    'QueryStats',
    'get_query_monitor',
    'time_query',
]
