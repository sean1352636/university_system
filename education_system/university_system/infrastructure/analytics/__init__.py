"""
Advanced Analytics and Reporting Infrastructure

Provides comprehensive analytics capabilities including:
- Predictive Analytics (retention, performance forecasting)
- Advanced Reporting (executive dashboards, automated reports)
- Data Warehouse (ETL pipelines, star schema)
- BI Tool Integration (Tableau, PowerBI, Metabase)

Features:
- Student retention prediction
- Academic performance forecasting
- Enrollment trend analysis
- Financial analytics
- Automated report scheduling
- Real-time dashboards
- Data warehouse synchronization
"""

from education_system.university_system.infrastructure.analytics.models import (
    ReportType,
    ReportFrequency,
    ReportFormat,
    AnalyticsMetric,
    PredictionResult,
    DashboardWidget,
)

from education_system.university_system.infrastructure.analytics.retention_prediction import (
    RetentionPredictor,
    get_retention_predictor,
)

from education_system.university_system.infrastructure.analytics.performance_analytics import (
    PerformanceAnalyzer,
    get_performance_analyzer,
)

from education_system.university_system.infrastructure.analytics.report_generator import (
    ReportGenerator,
    get_report_generator,
)

from education_system.university_system.infrastructure.analytics.data_warehouse import (
    DataWarehouse,
    get_data_warehouse,
)

from education_system.university_system.infrastructure.analytics.dashboard_service import (
    DashboardService,
    get_dashboard_service,
)

__all__ = [
    # Models
    'ReportType',
    'ReportFrequency',
    'ReportFormat',
    'AnalyticsMetric',
    'PredictionResult',
    'DashboardWidget',

    # Services
    'RetentionPredictor',
    'PerformanceAnalyzer',
    'ReportGenerator',
    'DataWarehouse',
    'DashboardService',

    # Getters
    'get_retention_predictor',
    'get_performance_analyzer',
    'get_report_generator',
    'get_data_warehouse',
    'get_dashboard_service',
]
