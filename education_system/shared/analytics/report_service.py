"""System-agnostic report generation service.

Each education system registers its own metric collectors.  The shared
ReportService handles formatting, export, and (optionally) scheduling so
that college, secondary, and primary systems get the same reporting
capabilities the university system already has.

Usage::

    from education_system.shared.analytics import ReportService

    svc = ReportService(system_key="college", db_path=db_path)

    # Register domain-specific collectors
    svc.register_collector("enrollment", my_enrollment_collector)

    # Generate a report that calls all registered collectors
    result = svc.generate(title="Monthly Summary", period="monthly")
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from io import StringIO
from typing import Any, Callable, Dict, List, Optional

from education_system.shared.analytics.models import MetricSnapshot, ReportFormat, ReportResult

logger = logging.getLogger(__name__)

# Type alias: a collector receives (conn, start_date, end_date) and
# returns a dict of section data + optional list of MetricSnapshot.
MetricCollector = Callable[
    [sqlite3.Connection, str, str],
    tuple[Dict[str, Any], List[MetricSnapshot]],
]


class ReportService:
    """Shared report generator that any education system can use.

    Systems plug in domain-specific *collectors* — small functions that
    query a database and return section data.  The service handles the
    boilerplate: date ranges, formatting, JSON/CSV/HTML export.
    """

    def __init__(self, system_key: str, db_path: Optional[str] = None) -> None:
        self.system_key = system_key
        self.db_path = db_path
        self._collectors: Dict[str, MetricCollector] = {}

    # ── Collector registration ─────────────────────────────────────

    def register_collector(self, name: str, fn: MetricCollector) -> None:
        """Register a named metric collector function."""
        self._collectors[name] = fn

    # ── Report generation ──────────────────────────────────────────

    def generate(
        self,
        title: str = "Report",
        period: str = "monthly",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        collectors: Optional[List[str]] = None,
    ) -> ReportResult:
        """Run registered collectors and assemble a report.

        Args:
            title: Human-readable report title.
            period: One of daily/weekly/monthly/quarterly/annually.
            start_date: YYYY-MM-DD (defaults based on *period*).
            end_date: YYYY-MM-DD (defaults to today).
            collectors: Subset of collector names to run; ``None`` = all.

        Returns:
            A :class:`ReportResult` with populated sections and metrics.
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = self._period_start(period, end_date)

        result = ReportResult(
            title=title,
            system_key=self.system_key,
            period_start=start_date,
            period_end=end_date,
        )

        names = collectors if collectors else list(self._collectors)

        conn: Optional[sqlite3.Connection] = None
        if self.db_path:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

        try:
            for name in names:
                fn = self._collectors.get(name)
                if fn is None:
                    logger.warning("Unknown collector %r, skipping", name)
                    continue
                try:
                    section_data, metrics = fn(conn, start_date, end_date)
                    result.sections[name] = section_data
                    result.metrics.extend(metrics)
                except Exception as exc:
                    logger.error("Collector %r failed: %s", name, exc)
                    result.sections[name] = {"error": str(exc)}
        finally:
            if conn:
                conn.close()

        return result

    # ── Export helpers ──────────────────────────────────────────────

    def export(self, report: ReportResult, fmt: ReportFormat = ReportFormat.JSON) -> str:
        """Export a report to the requested format string."""
        data = report.to_dict()

        if fmt == ReportFormat.JSON:
            return json.dumps(data, indent=2, default=str)

        if fmt == ReportFormat.CSV:
            return self._to_csv(data)

        if fmt == ReportFormat.HTML:
            return self._to_html(data)

        return json.dumps(data, indent=2, default=str)

    # ── Private helpers ────────────────────────────────────────────

    @staticmethod
    def _period_start(period: str, end_date: str) -> str:
        """Derive start date from a period name relative to *end_date*."""
        end = datetime.strptime(end_date, "%Y-%m-%d")
        days = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90, "annually": 365}
        delta = days.get(period, 30)
        return (end - timedelta(days=delta)).strftime("%Y-%m-%d")

    @staticmethod
    def _to_csv(data: Dict[str, Any]) -> str:
        """Flatten report sections into CSV rows."""
        buf = StringIO()
        buf.write("section,metric,value\n")
        for section, content in data.get("sections", {}).items():
            if isinstance(content, dict):
                for key, val in content.items():
                    buf.write(f"{section},{key},{val}\n")
        return buf.getvalue()

    @staticmethod
    def _to_html(data: Dict[str, Any]) -> str:
        """Render a minimal HTML report."""
        title = data.get("title", "Report")
        generated = data.get("generated_at", "")
        rows = ""
        for section, content in data.get("sections", {}).items():
            if isinstance(content, dict):
                for key, val in content.items():
                    rows += (
                        f"<tr><td>{section}</td><td>{key}</td><td>{val}</td></tr>\n"
                    )
        return (
            f"<html><head><title>{title}</title>"
            "<style>body{font-family:sans-serif;margin:20px}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left}"
            "th{background:#f5f5f5}</style></head>"
            f"<body><h1>{title}</h1>"
            f"<p>Generated: {generated}</p>"
            "<table><tr><th>Section</th><th>Metric</th><th>Value</th></tr>"
            f"{rows}</table></body></html>"
        )
