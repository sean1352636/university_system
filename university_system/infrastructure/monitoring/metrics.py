"""
Application Metrics Collection

Tracks response times, error rates, active users, and resource utilization.
Compatible with Prometheus/StatsD for external monitoring.
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from functools import wraps
from threading import Lock
import statistics

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and manages application metrics.

    Tracks:
    - Operation response times
    - Error rates
    - Active users
    - Database connection pool stats
    - Cache hit/miss rates
    """

    def __init__(self):
        self._lock = Lock()

        # Counter metrics
        self._counters: Dict[str, int] = defaultdict(int)

        # Gauge metrics (current values)
        self._gauges: Dict[str, float] = {}

        # Histogram metrics (for response times)
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Active operations
        self._active_operations: Dict[str, int] = defaultdict(int)

        # Error tracking
        self._errors: Dict[str, List[Dict]] = defaultdict(list)

    def increment_counter(self, metric: str, value: int = 1):
        """Increment a counter metric"""
        with self._lock:
            self._counters[metric] += value

    def set_gauge(self, metric: str, value: float):
        """Set a gauge metric to a specific value"""
        with self._lock:
            self._gauges[metric] = value

    def record_histogram(self, metric: str, value: float):
        """Record a value in a histogram (for response times)"""
        with self._lock:
            self._histograms[metric].append(value)

    def start_operation(self, operation: str):
        """Mark the start of an operation"""
        with self._lock:
            self._active_operations[operation] += 1

    def end_operation(self, operation: str):
        """Mark the end of an operation"""
        with self._lock:
            if self._active_operations[operation] > 0:
                self._active_operations[operation] -= 1

    def record_error(self, operation: str, error: str, details: Optional[Dict] = None):
        """Record an error occurrence"""
        with self._lock:
            error_data = {
                'timestamp': datetime.now().isoformat(),
                'operation': operation,
                'error': error,
                'details': details or {}
            }
            self._errors[operation].append(error_data)

            # Keep only last 100 errors per operation
            if len(self._errors[operation]) > 100:
                self._errors[operation] = self._errors[operation][-100:]

    def get_counter(self, metric: str) -> int:
        """Get counter value"""
        with self._lock:
            return self._counters.get(metric, 0)

    def get_gauge(self, metric: str) -> Optional[float]:
        """Get gauge value"""
        with self._lock:
            return self._gauges.get(metric)

    def get_histogram_stats(self, metric: str) -> Dict[str, float]:
        """Get histogram statistics (min, max, avg, p50, p95, p99)"""
        with self._lock:
            values = list(self._histograms.get(metric, []))

            if not values:
                return {}

            sorted_values = sorted(values)
            n = len(sorted_values)

            return {
                'count': n,
                'min': min(values),
                'max': max(values),
                'avg': statistics.mean(values),
                'p50': sorted_values[int(n * 0.5)],
                'p95': sorted_values[int(n * 0.95)],
                'p99': sorted_values[int(n * 0.99)],
            }

    def get_active_operations(self) -> Dict[str, int]:
        """Get count of active operations"""
        with self._lock:
            return dict(self._active_operations)

    def get_error_rate(self, operation: str) -> float:
        """Get error rate for an operation (errors per minute)"""
        with self._lock:
            errors = self._errors.get(operation, [])
            if not errors:
                return 0.0

            # Count errors in last minute
            now = datetime.now()
            recent_errors = [
                e for e in errors
                if (now - datetime.fromisoformat(e['timestamp'])).total_seconds() < 60
            ]

            return len(recent_errors)

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary"""
        with self._lock:
            metrics = {
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'histograms': {
                    metric: self.get_histogram_stats(metric)
                    for metric in self._histograms.keys()
                },
                'active_operations': dict(self._active_operations),
                'error_rates': {
                    op: self.get_error_rate(op)
                    for op in self._errors.keys()
                }
            }

        return metrics

    def reset_metrics(self):
        """Reset all metrics (useful for testing)"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._active_operations.clear()
            self._errors.clear()


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    global _metrics_collector

    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()

    return _metrics_collector


def track_operation(operation_name: str):
    """
    Decorator to track operation metrics.

    Tracks:
    - Response time
    - Success/failure count
    - Active operations

    Usage:
        @track_operation('student_enrollment')
        def enroll_student(student_id, course_id):
            # ... operation code
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()

            # Start tracking
            start_time = time.time()
            collector.start_operation(operation_name)
            collector.increment_counter(f'{operation_name}.attempts')

            try:
                result = func(*args, **kwargs)

                # Record success
                elapsed = time.time() - start_time
                collector.record_histogram(f'{operation_name}.response_time', elapsed)
                collector.increment_counter(f'{operation_name}.success')

                return result

            except Exception as e:
                # Record error
                collector.increment_counter(f'{operation_name}.errors')
                collector.record_error(operation_name, str(e), {
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                })
                raise

            finally:
                collector.end_operation(operation_name)

        return wrapper
    return decorator


def record_metric(metric_name: str, value: float, metric_type: str = 'counter'):
    """
    Quick helper to record a metric.

    Args:
        metric_name: Name of the metric
        value: Value to record
        metric_type: Type of metric ('counter', 'gauge', 'histogram')
    """
    collector = get_metrics_collector()

    if metric_type == 'counter':
        collector.increment_counter(metric_name, int(value))
    elif metric_type == 'gauge':
        collector.set_gauge(metric_name, value)
    elif metric_type == 'histogram':
        collector.record_histogram(metric_name, value)
    else:
        logger.warning(f"Unknown metric type: {metric_type}")
