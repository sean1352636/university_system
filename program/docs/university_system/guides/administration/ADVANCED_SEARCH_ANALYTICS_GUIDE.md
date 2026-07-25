# Advanced Search & Analytics Dashboard Guide

This guide covers the search capabilities, analytics dashboards, data visualization, and machine learning features within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Search Features](#search-features)
- [Grade Tracking Analytics](#grade-tracking-analytics)
- [Finance Analytics Dashboard](#finance-analytics-dashboard)
- [Course Analytics](#course-analytics)
- [Library Search](#library-search)
- [Machine Learning Analytics](#machine-learning-analytics)
- [Financial Alert System](#financial-alert-system)
- [Data Visualization](#data-visualization)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The system provides advanced search and analytics capabilities across multiple domains including academics, finance, and library management. Each domain features specialized search interfaces, real-time dashboards, and predictive analytics powered by optional machine learning libraries.

**Key files:**
- Grade Analytics: `modules/domain/academics/gui/grade_tracking/analytics_manager.py`
- Course Analytics: `modules/domain/academics/gui/course_management_gui/analytics/analytics.py`
- Finance Dashboard: `modules/domain/finance/gui/finance_reporting/dashboard_tab.py`
- Finance Analysis: `modules/domain/finance/gui/finance_reporting/analysis_tab.py`
- ML Analytics: `modules/domain/finance/gui/finance_reporting/ml_analytics.py`
- Financial Alerts: `modules/domain/finance/gui/finance_reporting/alerts_monitoring.py`
- Library Search: `modules/domain/academics/gui/library/search.py`
- Course Search: `modules/domain/academics/gui/course_management_gui/search/search.py`

## Search Features

### Multi-Criteria Search

All search interfaces support filtering by multiple criteria simultaneously:

```
┌─────────────────────────────────────────────┐
│              Search Interface                │
├─────────────────────────────────────────────┤
│  Text Fields    │ Dropdowns    │ Date Range │
│  Name/Title     │ Category     │ Start Date │
│  ID/Code        │ Status       │ End Date   │
│  Description    │ Type         │            │
├─────────────────────────────────────────────┤
│  [Search]  [Clear]  [Save Search]           │
├─────────────────────────────────────────────┤
│  Results (sortable, paginated)              │
│  ┌──────┬──────┬──────┬──────┐             │
│  │ Col1 │ Col2 │ Col3 │ Col4 │             │
│  ├──────┼──────┼──────┼──────┤             │
│  │ ...  │ ...  │ ...  │ ...  │             │
│  └──────┴──────┴──────┴──────┘             │
└─────────────────────────────────────────────┘
```

### Search Capabilities

| Feature | Description |
|---------|-------------|
| Multi-field filtering | Search across name, ID, category, status, date range |
| Dynamic SQL building | Parameterized queries prevent SQL injection |
| Result pagination | Page through large result sets |
| Sort by column | Click column headers to sort ascending/descending |
| Search templates | Save and reuse frequent search criteria |
| Advanced dialogs | Pop-up dialogs for complex filter combinations |
| Status filtering | Filter by item status (available, active, archived) |

### Course Catalog Search

Search courses by multiple criteria through the Course Management GUI:

- Course code or name
- Department or instructor
- Credit range
- Schedule/time slot
- Availability status
- Prerequisites

### Library Search

The library search system provides comprehensive book discovery:

- Title, author, ISBN search
- Category and reading level filters
- Availability status (available, checked out, reserved, lost, damaged)
- Publication date range
- QR code generation for results
- Integration with fines and payment system

## Grade Tracking Analytics

The `AnalyticsManager` provides comprehensive academic performance analysis.

### At-Risk Student Identification

```python
# Identifies students performing below thresholds
# Uses GPA, attendance, and assignment completion metrics
analytics.identify_at_risk_students()
```

### Grade Distribution Analysis

Visualizes grade distributions across courses, sections, and semesters:
- Histogram of grade frequencies
- Normal distribution overlay
- Mean, median, and standard deviation statistics
- Letter grade and percentage breakdowns

### Module Performance

Analyzes performance at the module level:
- Average scores per module
- Pass/fail rates
- Comparison across sections
- Trend analysis over semesters

### Course Comparison

Cross-course performance comparison:
- Side-by-side grade distributions
- Normalized performance metrics
- Department-level aggregations

### Performance Trends

Temporal analysis of academic performance:
- Semester-over-semester trends
- Student cohort tracking
- Improvement/decline detection

### Dashboard Tabs

The Grade Tracking analytics interface includes:

| Tab | Content |
|-----|---------|
| Overview | Summary metrics and KPIs |
| Distribution | Grade distribution charts |
| Trends | Performance over time |
| At-Risk | Students needing intervention |
| Comparison | Cross-course analysis |
| Reports | Exportable PDF/CSV reports |

## Finance Analytics Dashboard

### Dashboard Tab

The financial dashboard provides real-time metrics:

| Metric | Description |
|--------|-------------|
| Total Revenue | Aggregate income from all sources |
| Outstanding Payments | Unpaid balances by category |
| Collection Rate | Percentage of fees collected |
| Payment Trends | Daily/weekly/monthly payment patterns |
| Budget Variance | Actual vs. planned spending |
| Department Spending | Per-department expenditure tracking |

### Analysis Tab

Deep financial analysis capabilities:

- Revenue breakdown by source (tuition, fees, grants, donations)
- Year-over-year comparison
- Departmental budget analysis
- Student payment patterns
- Seasonal revenue trends

### Cash Flow Forecasting

```python
# 12-month cash flow prediction with seasonal adjustment
class CashFlowForecaster:
    seasonal_factors = {
        'Jan': 0.95, 'Feb': 0.85, 'Mar': 0.90,
        'Apr': 0.95, 'May': 1.00, 'Jun': 0.70,
        'Jul': 0.65, 'Aug': 1.20, 'Sep': 1.30,
        'Oct': 1.10, 'Nov': 1.05, 'Dec': 0.95
    }
```

The forecaster adjusts predictions based on historical seasonal patterns, with higher factors during enrollment periods (August/September) and lower during summer months.

### Anomaly Detection

```python
class AnomalyDetector:
    # Identifies unusual payment patterns:
    # - Payments significantly above/below average
    # - Unusual timing patterns
    # - Suspicious transaction sequences
```

### Student Lifecycle Analysis

Tracks financial engagement across the student lifecycle:
- Enrollment deposit to graduation
- Payment behavior patterns
- Financial aid utilization
- Tuition payment timing

## Course Analytics

The Course Management analytics module provides:

- Enrollment statistics per course and section
- Seat fill rates and waitlist metrics
- Instructor workload distribution
- Course popularity trends
- Drop/withdrawal rate analysis
- Schedule optimization data

## Library Search

### Advanced Book Search

```python
# Multi-criteria library search
enhanced_search_books(
    title='Introduction to',
    author='Smith',
    category='Computer Science',
    status='available',
    isbn=None,
    date_range=('2020-01-01', '2025-12-31')
)
```

### Search Features

| Feature | Description |
|---------|-------------|
| Full-text search | Search across title, author, description |
| Category filtering | Browse by subject category |
| Status filtering | Available, checked out, reserved, lost, damaged |
| Reading level | Filter by difficulty/level |
| Date range | Publication date filtering |
| QR code | Generate QR codes for search results |
| Save search | Store frequently used search templates |

## Machine Learning Analytics

### Payment Risk Prediction

```python
class PaymentPredictionML:
    # Prepares training data from historical payments
    # Trains classification model
    # Predicts payment risk scores for students
```

Features used for prediction:
- Payment history (on-time vs. late payments)
- Financial aid status
- Enrollment type (full-time vs. part-time)
- Historical payment amounts
- Semester-specific patterns

### Required Libraries

ML analytics gracefully degrade if optional libraries are not installed:

| Library | Purpose | Required |
|---------|---------|----------|
| scikit-learn | ML model training | Optional |
| Matplotlib | Chart generation | Optional |
| Seaborn | Statistical visualization | Optional |
| NumPy | Numerical computation | Optional |
| SciPy | Statistical analysis | Optional |
| Pandas | Data processing | Optional |
| ReportLab | PDF report generation | Optional |

All analytics features fall back to basic statistical calculations if ML libraries are unavailable.

## Financial Alert System

### Alert Types

| Alert | Trigger | Severity |
|-------|---------|----------|
| Low Collection Rate | Collection rate below threshold | High |
| Daily Payment Drop | Significant decrease in daily payments | Medium |
| Large Payment | Payment exceeds defined threshold | Low |
| Budget Overrun | Department exceeds budget allocation | High |
| SLA Breach | Processing time exceeds service agreement | Critical |

### Alert Channels

Alerts are dispatched through multiple channels:
- In-app notification
- Email notification
- Dashboard indicator
- Activity log entry

### Monitoring Dashboard

The alerts monitoring tab provides:
- Active alerts list with severity indicators
- Alert history and resolution tracking
- Threshold configuration
- Alert suppression rules

## Data Visualization

### Chart Types

| Chart | Use Case |
|-------|----------|
| Bar Chart | Grade distributions, category comparisons |
| Line Chart | Trends over time, performance tracking |
| Pie Chart | Revenue breakdown, category proportions |
| Histogram | Score distributions, payment timing |
| Scatter Plot | Correlation analysis, anomaly detection |
| Heatmap | Schedule density, activity patterns |

### Report Generation

Reports can be exported in multiple formats:

| Format | Library | Content |
|--------|---------|---------|
| PDF | ReportLab | Charts, tables, and narrative |
| CSV | Built-in | Raw data for spreadsheet analysis |
| HTML | Built-in | Interactive web-based reports |

### Threading

Analytics dashboards use background threads for data loading to keep the UI responsive:
- Long-running queries execute in worker threads
- Progress indicators show loading status
- Results update the UI on the main thread

## Configuration

### Analytics Dependencies

Install optional analytics libraries for full functionality:

```bash
pip install matplotlib seaborn numpy scipy pandas scikit-learn reportlab
```

### Dashboard Settings

Dashboard refresh intervals and display options are configurable through the Settings tab in each analytics interface.

### Database Indexes

Analytics performance relies on properly indexed tables:
- `module_grades`: indexed on student_id, course_id, timestamp
- `payments`: indexed on student_id, date, status
- `campus_events`: indexed on date, type

## Troubleshooting

### Slow Dashboard Loading

1. Check database indexes are present
2. Reduce the date range for queries
3. Ensure background threading is enabled
4. Consider archiving old data

### Missing Charts

1. Verify Matplotlib is installed: `pip install matplotlib`
2. Check for display issues in headless environments
3. The system falls back to text-based summaries if charting libraries are unavailable

### ML Predictions Unavailable

1. Install scikit-learn: `pip install scikit-learn`
2. Ensure sufficient training data exists (minimum historical records)
3. Check the `ml_analytics.py` log output for model training errors

### Search Returns No Results

1. Verify search criteria are not overly restrictive
2. Check that the database contains data matching the filters
3. Clear all filters and try a broader search
4. Check for typos in text search fields

### Export Failures

1. Verify write permissions on the export directory
2. For PDF exports, ensure ReportLab is installed
3. Check available disk space
4. Review the application logs for specific error messages
