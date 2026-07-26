"""Shared analytics data models used across all education systems."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ReportFormat(Enum):
    """Output formats for generated reports."""

    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class ReportFrequency(Enum):
    """How often a scheduled report runs."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    ON_DEMAND = "on_demand"


@dataclass
class MetricSnapshot:
    """A point-in-time measurement of a single metric."""

    name: str
    value: float
    category: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportResult:
    """Container returned by ReportService.generate()."""

    title: str
    system_key: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    sections: Dict[str, Any] = field(default_factory=dict)
    metrics: List[MetricSnapshot] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the report to a plain dictionary."""
        return {
            "title": self.title,
            "system_key": self.system_key,
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start,
            "period_end": self.period_end,
            "sections": self.sections,
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "category": m.category,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in self.metrics
            ],
        }
