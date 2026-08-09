"""In-memory metrics collector with Prometheus exposition format output.

Intentionally dependency-free: no prometheus_client library required.
For production use, replace or wrap with the official client.

Tracked metrics (pre-registered)
---------------------------------
``http_requests_total``            — counter, labelled by method + status
``http_request_duration_seconds``  — histogram buckets for latency
``http_errors_total``              — counter for 4xx/5xx responses
``active_connections``             — gauge (incremented on request, decremented on response)
``db_query_duration_seconds``      — histogram buckets for DB query time
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from typing import Any

__all__ = [
    "MetricsCollector",
    "metrics",  # module-level singleton
]

# Default histogram buckets (seconds)
_DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class MetricsCollector:
    """Thread-safe in-memory metrics store.

    Supports three instrument types:

    Counter
        Monotonically increasing integer.  Use ``increment(name)`` or
        ``increment(name, labels={"method": "GET", "status": "200"})``.

    Gauge
        Integer that can go up or down.  Use ``gauge_set(name, value)``,
        ``gauge_inc(name)``, or ``gauge_dec(name)``.

    Histogram
        Tracks a distribution of float observations (e.g. latencies).
        Use ``observe(name, value)``.  Buckets are fixed at creation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = defaultdict(float)
        # histogram: name → {"buckets": {le: count}, "sum": float, "count": int}
        self._histograms: dict[str, dict[str, Any]] = {}
        self._start_time = time.time()

        # Pre-register histograms with sensible buckets
        self._register_histogram("http_request_duration_seconds", _DEFAULT_BUCKETS)
        self._register_histogram("db_query_duration_seconds", _DEFAULT_BUCKETS)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _register_histogram(self, name: str, buckets: tuple[float, ...]) -> None:
        if name not in self._histograms:
            self._histograms[name] = {
                "buckets": {le: 0 for le in sorted(buckets)},
                "sum": 0.0,
                "count": 0,
            }

    def _label_key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    # ------------------------------------------------------------------
    # Counter
    # ------------------------------------------------------------------

    def increment(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        """Increment a counter by *value* (default 1)."""
        key = self._label_key(name, labels)
        with self._lock:
            self._counters[key] += value

    # ------------------------------------------------------------------
    # Gauge
    # ------------------------------------------------------------------

    def gauge_set(self, name: str, value: float) -> None:
        """Set a gauge to an absolute value."""
        with self._lock:
            self._gauges[name] = value

    def gauge_inc(self, name: str, value: float = 1.0) -> None:
        """Increment a gauge."""
        with self._lock:
            self._gauges[name] += value

    def gauge_dec(self, name: str, value: float = 1.0) -> None:
        """Decrement a gauge."""
        with self._lock:
            self._gauges[name] -= value

    # ------------------------------------------------------------------
    # Histogram
    # ------------------------------------------------------------------

    def observe(self, name: str, value: float, buckets: tuple[float, ...] | None = None) -> None:
        """Record an observation in a histogram.

        If *name* has not been registered yet it is auto-created with
        either the supplied *buckets* or the default set.
        """
        with self._lock:
            if name not in self._histograms:
                self._register_histogram(name, buckets or _DEFAULT_BUCKETS)
            hist = self._histograms[name]
            hist["sum"] += value
            hist["count"] += 1
            for le in hist["buckets"]:
                if value <= le:
                    hist["buckets"][le] += 1

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Return a snapshot of all metrics as a plain dictionary."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: {
                        "buckets": dict(h["buckets"]),
                        "sum": h["sum"],
                        "count": h["count"],
                    }
                    for name, h in self._histograms.items()
                },
                "uptime_seconds": round(time.time() - self._start_time, 1),
            }

    def format_prometheus(self) -> str:
        """Render all metrics in Prometheus exposition format (text/plain; version=0.0.4)."""
        lines: list[str] = []
        snapshot = self.get_metrics()

        # Counters
        for key, value in sorted(snapshot["counters"].items()):
            # key may already contain label braces
            bare_name = key.split("{")[0]
            lines.append(f"# TYPE {bare_name} counter")
            lines.append(f"{key} {value}")

        # Gauges
        for name, value in sorted(snapshot["gauges"].items()):
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        # Histograms
        for name, hist in sorted(snapshot["histograms"].items()):
            lines.append(f"# TYPE {name} histogram")
            for le, count in sorted(hist["buckets"].items()):
                lines.append(f'{name}_bucket{{le="{le}"}} {count}')
            lines.append(f'{name}_bucket{{le="+Inf"}} {hist["count"]}')
            lines.append(f"{name}_sum {hist['sum']}")
            lines.append(f"{name}_count {hist['count']}")

        # Process uptime as an extra gauge
        lines.append("# TYPE process_uptime_seconds gauge")
        lines.append(f"process_uptime_seconds {snapshot['uptime_seconds']}")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Convenience: HTTP tracking helpers
    # ------------------------------------------------------------------

    def record_request(
        self,
        method: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record a completed HTTP request (called by middleware)."""
        labels = {"method": method.upper(), "status": str(status_code)}
        self.increment("http_requests_total", labels=labels)
        self.observe("http_request_duration_seconds", duration_seconds)
        self.gauge_dec("active_connections")
        if status_code >= 400:
            err_labels = {"method": method.upper(), "status": str(status_code)}
            self.increment("http_errors_total", labels=err_labels)


# Module-level singleton — import and use directly in application code
metrics = MetricsCollector()
