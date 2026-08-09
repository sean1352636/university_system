"""
Analytics Data Models

Data structures for analytics and reporting.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional


class ReportType(Enum):
    """Types of reports"""
    EXECUTIVE_SUMMARY = "executive_summary"
    ENROLLMENT_TRENDS = "enrollment_trends"
    FINANCIAL_SUMMARY = "financial_summary"
    ACADEMIC_PERFORMANCE = "academic_performance"
    RETENTION_ANALYSIS = "retention_analysis"
    STUDENT_SUCCESS = "student_success"
    COURSE_EFFECTIVENESS = "course_effectiveness"
    DEPARTMENT_METRICS = "department_metrics"
    CUSTOM = "custom"


class ReportFrequency(Enum):
    """Report generation frequency"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    ON_DEMAND = "on_demand"


class ReportFormat(Enum):
    """Report output formats"""
    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class AnalyticsMetric(Enum):
    """Analytics metrics"""
    ENROLLMENT_RATE = "enrollment_rate"
    RETENTION_RATE = "retention_rate"
    GRADUATION_RATE = "graduation_rate"
    GPA_AVERAGE = "gpa_average"
    ATTENDANCE_RATE = "attendance_rate"
    COURSE_COMPLETION_RATE = "course_completion_rate"
    STUDENT_SATISFACTION = "student_satisfaction"
    REVENUE = "revenue"
    COST_PER_STUDENT = "cost_per_student"
    FACULTY_STUDENT_RATIO = "faculty_student_ratio"


@dataclass
class PredictionResult:
    """Result from predictive model"""
    student_id: str
    prediction_type: str  # 'retention', 'performance', 'graduation'
    probability: float
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    contributing_factors: Dict[str, float] = field(default_factory=dict)
    recommended_actions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    predicted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DashboardWidget:
    """Dashboard widget configuration"""
    widget_id: str
    widget_type: str  # 'chart', 'metric', 'table', 'gauge'
    title: str
    data_source: str
    configuration: Dict[str, Any] = field(default_factory=dict)
    refresh_interval: int = 300  # seconds
    position: Dict[str, int] = field(default_factory=dict)  # x, y, width, height


@dataclass
class ScheduledReport:
    """Scheduled report configuration"""
    report_id: Optional[int] = None
    report_type: str = ""
    frequency: str = ""
    recipients: List[str] = field(default_factory=list)
    format: str = "pdf"
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_generated: Optional[datetime] = None
    next_generation: Optional[datetime] = None


@dataclass
class AnalyticsSnapshot:
    """Point-in-time analytics snapshot"""
    snapshot_id: Optional[int] = None
    snapshot_date: datetime = field(default_factory=datetime.utcnow)
    total_students: int = 0
    active_enrollments: int = 0
    average_gpa: float = 0.0
    retention_rate: float = 0.0
    graduation_rate: float = 0.0
    total_revenue: float = 0.0
    total_expenses: float = 0.0
    faculty_count: int = 0
    course_count: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    'ReportType',
    'ReportFrequency',
    'ReportFormat',
    'AnalyticsMetric',
    'PredictionResult',
    'DashboardWidget',
    'ScheduledReport',
    'AnalyticsSnapshot',
]
