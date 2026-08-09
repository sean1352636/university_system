## Advanced Analytics and Reporting System

Comprehensive analytics platform with predictive capabilities, automated reporting, data warehousing, and real-time dashboards.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Components](#components)
5. [API Reference](#api-reference)
6. [Usage Examples](#usage-examples)
7. [Data Models](#data-models)
8. [Configuration](#configuration)
9. [Dependencies](#dependencies)

---

## Overview

The Analytics and Reporting System provides enterprise-grade analytics capabilities including:

- **Predictive Analytics**: ML-powered student retention and performance prediction
- **Performance Analytics**: GPA trends, course metrics, graduation forecasting
- **Report Generation**: Automated executive dashboards and scheduled reports
- **Data Warehouse**: Star schema with ETL pipelines for BI tool integration
- **Dashboard Service**: Custom dashboards with real-time data visualization

### Use Cases

- **Institutional Research**: Analyze enrollment, retention, and graduation trends
- **Student Success**: Identify at-risk students and provide interventions
- **Executive Leadership**: Comprehensive dashboards for strategic decision-making
- **Academic Planning**: Course and department performance analysis
- **Compliance Reporting**: Automated report generation for regulatory requirements
- **BI Integration**: Export data for Tableau, PowerBI, and Metabase

---

## Features

### Retention Prediction

- ML-based prediction using RandomForestClassifier
- Rule-based fallback when scikit-learn unavailable
- Multi-factor risk assessment (GPA, attendance, failures, enrollment)
- Risk classification (critical, high, medium, low)
- Actionable intervention recommendations
- Student-specific risk scoring
- Retention statistics and trends

### Performance Analytics

- GPA trend analysis (overall and by department)
- Student performance forecasting
- Course performance metrics (success rate, failure rate)
- Department-level performance comparison
- Graduation timeline prediction
- Monthly aggregation and reporting

### Report Generation

- Executive dashboard (enrollment, financial, academic, retention)
- Automated scheduling (daily, weekly, monthly, quarterly, annually)
- Multi-format export (PDF, Excel, CSV, JSON, HTML)
- Email distribution
- Report history and audit trail
- Custom parameters per report

### Data Warehouse

- Star schema design (4 dimensions, 3 fact tables)
- Time dimension with date hierarchy
- Student, Course, and Department dimensions
- Enrollment and Grade fact tables
- ETL pipeline with incremental sync
- BI dataset generation
- Analytics snapshot for daily metrics

### Dashboard Service

- Custom dashboard creation
- Widget library (charts, metrics, tables, gauges)
- Real-time data refresh
- Layout management and persistence
- Dashboard sharing and permissions
- Auto-refresh intervals
- 10+ data sources

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Analytics Layer                          │
├─────────────────────────────────────────────────────────────┤
│  Retention     │  Performance  │  Report     │  Dashboard   │
│  Predictor     │  Analyzer     │  Generator  │  Service     │
├─────────────────────────────────────────────────────────────┤
│                   Data Warehouse Layer                       │
│  ETL Pipeline  │  Star Schema  │  BI Datasets               │
├─────────────────────────────────────────────────────────────┤
│                  Operational Database                        │
│  Students  │  Courses  │  Grades  │  Enrollments            │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Operational Data**: Stored in normalized SQLite database
2. **ETL Process**: Sync operational data to star schema warehouse
3. **Analytics**: Process warehouse data for insights
4. **Reporting**: Generate dashboards and scheduled reports
5. **Delivery**: Export to files or BI tools

---

## Components

### 1. Retention Prediction (`retention_prediction.py`)

Predicts students at risk of dropping out.

**Key Methods:**
- `predict_at_risk_students(threshold, limit)` - Get at-risk students
- `get_student_risk_score(student_id)` - Risk score for specific student
- `get_retention_statistics()` - Overall retention stats

**Risk Factors:**
- GPA < 2.0 (Critical)
- Attendance < 75% (High)
- Failed courses > 2 (High)
- No enrollment (Medium)
- Financial aid issues (Medium)

**Example:**
```python
from university_system.infrastructure.analytics import get_retention_predictor

predictor = get_retention_predictor()
at_risk = predictor.predict_at_risk_students(threshold=0.7, limit=10)

for student in at_risk:
    print(f"{student.student_id}: {student.risk_level} risk ({student.probability:.0%})")
    print(f"  Factors: {student.contributing_factors}")
    print(f"  Actions: {student.recommended_actions}")
```

### 2. Performance Analytics (`performance_analytics.py`)

Analyzes academic performance and forecasts outcomes.

**Key Methods:**
- `analyze_gpa_trends(period_days)` - GPA trends over time
- `predict_student_performance(student_id)` - Performance forecast
- `get_course_performance_metrics(course_id)` - Course metrics
- `get_department_metrics()` - Department comparison
- `predict_graduation_timeline(student_id)` - Graduation prediction

**Example:**
```python
from university_system.infrastructure.analytics import get_performance_analyzer

analyzer = get_performance_analyzer()

# GPA trends
trends = analyzer.analyze_gpa_trends(period_days=365)
print(f"Overall trend: {trends['overall_trend']}")
print(f"Departments: {trends['trends_by_department']}")

# Course performance
metrics = analyzer.get_course_performance_metrics()
for course in metrics['courses']:
    print(f"{course['course_code']}: {course['success_rate']}% success rate")

# Graduation timeline
timeline = analyzer.predict_graduation_timeline("STU001")
print(f"Predicted graduation: {timeline['predicted_graduation_date']}")
print(f"Courses remaining: {timeline['remaining_courses']}")
```

### 3. Report Generator (`report_generator.py`)

Generates and schedules automated reports.

**Key Methods:**
- `generate_executive_dashboard(period)` - Create executive dashboard
- `schedule_report(type, frequency, recipients, format)` - Schedule report
- `get_scheduled_reports()` - List scheduled reports
- `cancel_scheduled_report(report_id)` - Cancel scheduled report
- `export_report(type, format, parameters)` - Export report

**Supported Formats:**
- PDF (requires reportlab)
- Excel (requires openpyxl)
- CSV
- JSON
- HTML

**Example:**
```python
from university_system.infrastructure.analytics import get_report_generator

generator = get_report_generator()

# Generate executive dashboard
dashboard = generator.generate_executive_dashboard(period='monthly')
print(f"Enrollment: {dashboard['enrollment_summary']}")
print(f"Financial: {dashboard['financial_summary']}")
print(f"Academic: {dashboard['academic_summary']}")

# Schedule weekly report
report = generator.schedule_report(
    report_type='executive_summary',
    frequency='weekly',
    recipients=['admin@university.edu', 'president@university.edu'],
    format='pdf',
    parameters={'include_charts': True},
    created_by='admin'
)
print(f"Scheduled report ID: {report.report_id}")
print(f"Next generation: {report.next_generation}")

# Export report
file_path = generator.export_report('executive_summary', 'excel', {})
print(f"Report exported to: {file_path}")
```

### 4. Data Warehouse (`data_warehouse.py`)

Star schema data warehouse with ETL pipelines.

**Schema:**

**Dimensions:**
- `dim_time` - Date hierarchy
- `dim_student` - Student attributes
- `dim_course` - Course details
- `dim_department` - Department info

**Facts:**
- `fact_enrollment` - Student enrollments
- `fact_grade` - Student grades
- `fact_analytics_snapshot` - Daily metrics

**Key Methods:**
- `sync_operational_data(full_sync)` - ETL sync
- `create_analytics_snapshot()` - Daily snapshot
- `get_bi_dataset(dataset_name)` - BI tool datasets

**Available BI Datasets:**
- `enrollment_trends` - Enrollment over time
- `grade_distribution` - Grade distribution analysis
- `department_metrics` - Department comparison

**Example:**
```python
from university_system.infrastructure.analytics import get_data_warehouse

warehouse = get_data_warehouse()

# Sync operational data
stats = warehouse.sync_operational_data(full_sync=False)
print(f"Synced {stats['students_synced']} students")
print(f"Synced {stats['enrollments_synced']} enrollments")

# Create daily snapshot
snapshot = warehouse.create_analytics_snapshot()
print(f"Snapshot ID: {snapshot.snapshot_id}")
print(f"Total students: {snapshot.total_students}")
print(f"Average GPA: {snapshot.average_gpa}")
print(f"Retention rate: {snapshot.retention_rate}%")

# Get BI dataset for Tableau
dataset = warehouse.get_bi_dataset('enrollment_trends')
print(f"Dataset has {len(dataset)} records")
```

### 5. Dashboard Service (`dashboard_service.py`)

Real-time dashboard creation and management.

**Key Methods:**
- `create_dashboard(name, owner_id, shared, ...)` - Create dashboard
- `add_widget(dashboard_id, widget_type, title, data_source, ...)` - Add widget
- `refresh_dashboard_data(dashboard_id)` - Refresh all widgets
- `list_dashboards(user_id, include_shared)` - List dashboards
- `get_dashboard_widgets(dashboard_id)` - Get widgets

**Widget Types:**
- `chart` - Line/bar/pie charts
- `metric` - Single value display
- `table` - Tabular data
- `gauge` - Progress/percentage gauge

**Data Sources:**
- `retention_stats` - Retention statistics
- `at_risk_students` - At-risk student list
- `gpa_trends` - GPA trends chart
- `course_performance` - Course metrics
- `department_metrics` - Department comparison
- `enrollment_trends` - Enrollment over time
- `financial_summary` - Financial metrics
- `student_success` - Success metrics

**Example:**
```python
from university_system.infrastructure.analytics import get_dashboard_service

service = get_dashboard_service()

# Create dashboard
dashboard_id = service.create_dashboard(
    name="Executive Dashboard",
    owner_id="admin",
    description="Comprehensive university metrics",
    shared=True,
    refresh_interval=300  # 5 minutes
)

# Add retention metrics widget
service.add_widget(
    dashboard_id=dashboard_id,
    widget_type='metric',
    title='Retention Rate',
    data_source='retention_stats',
    position_x=0,
    position_y=0,
    width=4,
    height=2
)

# Add at-risk students table
service.add_widget(
    dashboard_id=dashboard_id,
    widget_type='table',
    title='At-Risk Students',
    data_source='at_risk_students',
    configuration={'limit': 10},
    position_x=4,
    position_y=0,
    width=8,
    height=4
)

# Add GPA trends chart
service.add_widget(
    dashboard_id=dashboard_id,
    widget_type='chart',
    title='GPA Trends',
    data_source='gpa_trends',
    configuration={'period_days': 180},
    position_x=0,
    position_y=2,
    width=6,
    height=4
)

# Refresh dashboard data
data = service.refresh_dashboard_data(dashboard_id)
for widget in data['widgets']:
    print(f"Widget: {widget['title']}")
    print(f"  Type: {widget['widget_type']}")
    print(f"  Data: {widget['data']}")
```

---

## API Reference

### REST API Endpoints

All endpoints are prefixed with `/api/v1/analytics`.

#### Retention Prediction

**Get At-Risk Students**
```
GET /retention/at-risk?threshold=0.7&limit=10
```

**Get Student Risk Score**
```
GET /retention/student/{student_id}
```

**Get Retention Statistics**
```
GET /retention/statistics
```

#### Performance Analytics

**Get GPA Trends**
```
GET /performance/gpa-trends?period_days=365
```

**Predict Student Performance**
```
GET /performance/student/{student_id}/predict
```

**Get Course Performance**
```
GET /performance/courses?course_id=CS101
```

**Get Department Metrics**
```
GET /performance/departments
```

**Predict Graduation Timeline**
```
GET /performance/student/{student_id}/graduation
```

#### Report Generation

**Generate Executive Dashboard**
```
GET /reports/executive-dashboard?period=monthly
```

**Schedule Report**
```
POST /reports/schedule
Body: {
  "report_type": "executive_summary",
  "frequency": "weekly",
  "recipients": ["admin@university.edu"],
  "format": "pdf"
}
```

**List Scheduled Reports**
```
GET /reports/scheduled
```

**Cancel Scheduled Report**
```
DELETE /reports/scheduled/{report_id}
```

**Export Report**
```
GET /reports/export/{report_type}?format=pdf
```

#### Data Warehouse

**Sync Operational Data**
```
POST /warehouse/sync
Body: {"full_sync": false}
```

**Create Analytics Snapshot**
```
POST /warehouse/snapshot
```

**Get BI Dataset**
```
GET /warehouse/bi-dataset/{dataset_name}
```

#### Dashboards

**List Dashboards**
```
GET /dashboards?user_id=admin&include_shared=true
```

**Create Dashboard**
```
POST /dashboards
Body: {
  "name": "My Dashboard",
  "owner_id": "admin",
  "shared": true
}
```

**Get Dashboard**
```
GET /dashboards/{dashboard_id}
```

**Update Dashboard**
```
PUT /dashboards/{dashboard_id}
Body: {"name": "Updated Name"}
```

**Delete Dashboard**
```
DELETE /dashboards/{dashboard_id}
```

**Add Widget**
```
POST /dashboards/{dashboard_id}/widgets
Body: {
  "widget_type": "chart",
  "title": "GPA Trends",
  "data_source": "gpa_trends"
}
```

**Get Dashboard Widgets**
```
GET /dashboards/{dashboard_id}/widgets
```

**Refresh Dashboard Data**
```
GET /dashboards/{dashboard_id}/refresh
```

---

## Usage Examples

### Example 1: Identify and Intervene with At-Risk Students

```python
from university_system.infrastructure.analytics import get_retention_predictor

predictor = get_retention_predictor()

# Get high-risk students
at_risk = predictor.predict_at_risk_students(threshold=0.5, limit=20)

for student in at_risk:
    if student.risk_level in ['critical', 'high']:
        print(f"\n🚨 {student.student_id}: {student.risk_level.upper()} RISK")
        print(f"Probability of dropout: {student.probability:.0%}")

        # Analyze factors
        print("Contributing factors:")
        for factor, weight in student.contributing_factors.items():
            print(f"  - {factor}: {weight}")

        # Get recommendations
        print("Recommended interventions:")
        for action in student.recommended_actions:
            print(f"  • {action}")
```

### Example 2: Generate Monthly Executive Report

```python
from university_system.infrastructure.analytics import get_report_generator
from datetime import datetime

generator = get_report_generator()

# Generate dashboard
dashboard = generator.generate_executive_dashboard(period='monthly')

# Create report
report_date = datetime.now().strftime('%Y-%m')
print(f"\n📊 EXECUTIVE DASHBOARD - {report_date}")
print("=" * 60)

print("\n📈 ENROLLMENT SUMMARY")
enrollment = dashboard['enrollment_summary']
print(f"Total Students: {enrollment['total_students']}")
print(f"Active Students: {enrollment['active_students']}")
print(f"New Students: {enrollment['new_students']}")
print(f"Retention Rate: {dashboard['retention_summary']['retention_rate']}%")

print("\n💰 FINANCIAL SUMMARY")
financial = dashboard['financial_summary']
print(f"Total Revenue: ${financial['total_revenue']:,.2f}")
print(f"Tuition Revenue: ${financial['tuition_revenue']:,.2f}")
print(f"Collections: ${financial['total_collections']:,.2f}")

print("\n🎓 ACADEMIC SUMMARY")
academic = dashboard['academic_summary']
print(f"Average GPA: {academic['average_gpa']}")
print(f"Passing Rate: {academic['passing_rate']}%")
print(f"Attendance Rate: {academic['average_attendance']}%")

# Export to PDF
file_path = generator.export_report('executive_summary', 'pdf', {
    'period': 'monthly',
    'include_charts': True
})
print(f"\n📄 Report exported to: {file_path}")
```

### Example 3: Build Custom Analytics Dashboard

```python
from university_system.infrastructure.analytics import get_dashboard_service

service = get_dashboard_service()

# Create dashboard
dashboard_id = service.create_dashboard(
    name="Student Success Dashboard",
    owner_id="dean",
    description="Track student performance and retention",
    shared=True,
    refresh_interval=600  # 10 minutes
)

# Add widgets in grid layout
widgets = [
    # Row 1: Key Metrics
    {
        'widget_type': 'metric',
        'title': 'Overall GPA',
        'data_source': 'student_success',
        'position_x': 0, 'position_y': 0,
        'width': 3, 'height': 2
    },
    {
        'widget_type': 'metric',
        'title': 'Retention Rate',
        'data_source': 'retention_stats',
        'position_x': 3, 'position_y': 0,
        'width': 3, 'height': 2
    },
    {
        'widget_type': 'metric',
        'title': 'Graduation Rate',
        'data_source': 'student_success',
        'position_x': 6, 'position_y': 0,
        'width': 3, 'height': 2
    },
    {
        'widget_type': 'metric',
        'title': 'Attendance',
        'data_source': 'student_success',
        'position_x': 9, 'position_y': 0,
        'width': 3, 'height': 2
    },

    # Row 2: Charts
    {
        'widget_type': 'chart',
        'title': 'GPA Trends by Department',
        'data_source': 'gpa_trends',
        'configuration': {'period_days': 365},
        'position_x': 0, 'position_y': 2,
        'width': 6, 'height': 4
    },
    {
        'widget_type': 'chart',
        'title': 'Enrollment Trends',
        'data_source': 'enrollment_trends',
        'configuration': {'period': 'monthly'},
        'position_x': 6, 'position_y': 2,
        'width': 6, 'height': 4
    },

    # Row 3: Tables
    {
        'widget_type': 'table',
        'title': 'At-Risk Students',
        'data_source': 'at_risk_students',
        'configuration': {'limit': 15},
        'position_x': 0, 'position_y': 6,
        'width': 6, 'height': 5
    },
    {
        'widget_type': 'table',
        'title': 'Top Performing Courses',
        'data_source': 'course_performance',
        'position_x': 6, 'position_y': 6,
        'width': 6, 'height': 5
    },
]

# Add all widgets
for widget in widgets:
    widget_id = service.add_widget(dashboard_id=dashboard_id, **widget)
    print(f"Added widget: {widget['title']} (ID: {widget_id})")

# Refresh and display data
data = service.refresh_dashboard_data(dashboard_id)
print(f"\nDashboard refreshed at: {data['refreshed_at']}")
print(f"Total widgets: {len(data['widgets'])}")
```

### Example 4: Sync Data to BI Tool

```python
from university_system.infrastructure.analytics import get_data_warehouse
import json

warehouse = get_data_warehouse()

# Full sync to refresh warehouse
print("🔄 Syncing operational data to warehouse...")
stats = warehouse.sync_operational_data(full_sync=True)
print(f"✅ Sync complete:")
print(f"   Students: {stats['students_synced']}")
print(f"   Courses: {stats['courses_synced']}")
print(f"   Enrollments: {stats['enrollments_synced']}")
print(f"   Grades: {stats['grades_synced']}")

# Export datasets for Tableau
datasets = {
    'enrollment_trends': warehouse.get_bi_dataset('enrollment_trends'),
    'grade_distribution': warehouse.get_bi_dataset('grade_distribution'),
    'department_metrics': warehouse.get_bi_dataset('department_metrics')
}

# Save to JSON for import
for name, data in datasets.items():
    filename = f"/tmp/{name}.json"
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"📊 Exported {name}: {len(data)} records to {filename}")

print("\n✅ BI datasets ready for Tableau/PowerBI import")
```

---

## Data Models

### PredictionResult

```python
@dataclass
class PredictionResult:
    student_id: str
    prediction_type: str  # 'retention', 'performance', 'graduation'
    probability: float
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    contributing_factors: Dict[str, float]
    recommended_actions: List[str]
    confidence: float
    predicted_at: datetime
```

### ScheduledReport

```python
@dataclass
class ScheduledReport:
    report_id: Optional[int]
    report_type: str
    frequency: str  # 'daily', 'weekly', 'monthly', 'quarterly', 'annually'
    recipients: List[str]
    format: str  # 'pdf', 'excel', 'csv', 'json', 'html'
    parameters: Dict[str, Any]
    enabled: bool
    created_by: str
    created_at: datetime
    last_generated: Optional[datetime]
    next_generation: Optional[datetime]
```

### AnalyticsSnapshot

```python
@dataclass
class AnalyticsSnapshot:
    snapshot_id: Optional[int]
    snapshot_date: datetime
    total_students: int
    active_enrollments: int
    average_gpa: float
    retention_rate: float
    graduation_rate: float
    total_revenue: float
    total_expenses: float
    faculty_count: int
    course_count: int
    metrics: Dict[str, Any]
```

### DashboardWidget

```python
@dataclass
class DashboardWidget:
    widget_id: str
    widget_type: str  # 'chart', 'metric', 'table', 'gauge'
    title: str
    data_source: str
    configuration: Dict[str, Any]
    refresh_interval: int  # seconds
    position: Dict[str, int]  # x, y, width, height
```

---

## Configuration

### Environment Variables

None required. All configuration stored in database.

### Database Tables

Analytics creates the following tables:

**Report Generator:**
- `scheduled_reports` - Scheduled report configurations
- `report_history` - Report generation history

**Dashboard Service:**
- `dashboards` - Dashboard configurations
- `dashboard_widgets` - Widget definitions
- `dashboard_permissions` - Access control

**Data Warehouse:**
- `dim_time` - Time dimension
- `dim_student` - Student dimension
- `dim_course` - Course dimension
- `dim_department` - Department dimension
- `fact_enrollment` - Enrollment facts
- `fact_grade` - Grade facts
- `fact_analytics_snapshot` - Daily snapshots

---

## Dependencies

### Required

- Python 3.8+
- SQLite3 (included with Python)

### Optional

For enhanced features:

```bash
# Machine Learning
pip install pandas numpy scikit-learn

# Report Export
pip install reportlab openpyxl  # PDF and Excel
```

### Graceful Degradation

- **Without ML libraries**: Uses rule-based prediction instead of ML models
- **Without reportlab**: Cannot export PDF reports (other formats work)
- **Without openpyxl**: Cannot export Excel reports (other formats work)

---

## Performance

- **Retention Prediction**: ~100ms for 1000 students
- **GPA Trends**: ~200ms for 12 months of data
- **Executive Dashboard**: ~500ms with all metrics
- **ETL Sync**: ~1-2 seconds for 10,000 records
- **Dashboard Refresh**: ~300ms for 10 widgets

---

## Testing

Run the demo script:

```bash
python examples/analytics_demo.py
```

This demonstrates all features:
1. Retention prediction
2. Performance analytics
3. Report generation
4. Data warehouse operations
5. Dashboard creation and management

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'sklearn'"

ML libraries not installed. Install with:
```bash
pip install pandas numpy scikit-learn
```

Or continue using rule-based prediction (no installation needed).

### "No at-risk students found"

Either:
1. No students in database
2. All students performing well (good news!)
3. Threshold too high - try lower threshold (e.g., 0.3)

### "No trend data available"

Database has insufficient historical data. Add sample data or wait for more data accumulation.

### Dashboard widgets not updating

Check:
1. Dashboard refresh interval setting
2. Data source availability
3. Widget configuration parameters

---

## Best Practices

1. **Schedule ETL during low-traffic periods** (e.g., nightly)
2. **Use incremental sync** for daily updates, full sync weekly
3. **Set appropriate refresh intervals** for dashboards (5-15 minutes)
4. **Export large reports** in CSV/Excel instead of PDF
5. **Use BI datasets** for external visualization tools
6. **Archive old snapshots** periodically to manage storage
7. **Review at-risk predictions** weekly for interventions
8. **Customize report parameters** per stakeholder needs

---

## Support

For issues or questions:
- See examples in `examples/analytics_demo.py`
- Check API documentation at `/docs`
- Review CHANGELOG.md for recent updates
- See parent README_NEW_FEATURES.md for quick start

---

**Version**: 5.7.0
**Last Updated**: 2025-02-01
