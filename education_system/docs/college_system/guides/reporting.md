# Reporting Guide

This guide covers the reports, data dashboard, KPI dashboard, progress dashboard, mobile dashboard, advanced search, surveys, feedback, and data export modules within the Sixth Form College Management System.

## Overview

The reporting suite provides a comprehensive set of tools for generating, visualising, and exporting college data. From structured progress reports to ad-hoc data queries, these modules support evidence-based decision making at all levels of the organisation.

| Module | Purpose |
|--------|---------|
| `reports` | Progress reports with per-student, per-course entries |
| `data_dashboard` | Central data visualisation and summary dashboard |
| `kpi_dashboard` | Key performance indicator tracking and targets |
| `progress_dashboard` | Student progress monitoring and intervention triggers |
| `mobile_dashboard` | Mobile-optimised dashboard views |
| `advanced_search` | Custom search and filtering across all data |
| `surveys` | Survey creation, distribution, and analysis |
| `feedback` | General feedback collection and management |
| `data_export` | Data export jobs, templates, and ILR submissions |


## Progress Reports

The reports module (`ReportsService`) manages formal progress reports that capture teacher assessments for each student across their courses.

### Report Types

| Type | Purpose | Typical Timing |
|------|---------|---------------|
| `interim` | Mid-term progress snapshot | Mid-term |
| `full` | Comprehensive end-of-term report | End of term |
| `final` | End-of-year summative report | End of academic year |

### Creating a Report

1. Navigate to the Reports section.
2. Click "New Report".
3. Enter the report details:
   - **Title** -- Descriptive name (e.g., "Year 12 Interim Report - Autumn 2025").
   - **Report Type** -- Select interim, full, or final.
   - **Academic Year** -- The academic year this report covers.
   - **Term** -- The specific term.
   - **Due Date** -- Deadline for teachers to complete their entries.
   - **Created By** -- Automatically set to the logged-in user.
4. Save the report.

### Adding Report Entries

Each report contains individual entries from teachers for their students. To add an entry:

1. Select the report.
2. Click "Add Entry".
3. Specify the student, course, and teacher.
4. Enter the assessment data:

| Field | Description |
|-------|-------------|
| `current_grade` | The student's current working grade |
| `target_grade` | The student's target or minimum expected grade |
| `effort_grade` | A grade reflecting the student's effort (e.g., 1-4 scale) |
| `attendance_pct` | The student's attendance percentage for this course |
| `comment` | Teacher's written comment on progress |

### Report Status Workflow

Reports progress through the following statuses:

| Status | Meaning |
|--------|---------|
| `draft` | Report is being set up, entries are being added |
| `open` | Report is open for teachers to complete entries |
| `closed` | Entry deadline has passed, report is locked |
| `published` | Report has been published to students and parents |

### Viewing Reports

- **List all reports** -- View all reports, optionally filtered by status.
- **List entries for a report** -- See all entries within a specific report, optionally filtered by student.
- **Student report view** -- See all entries for a specific student within a report, ordered by course name.


## Data Dashboard

The data dashboard module provides a central hub for data visualisation and summary statistics.

### Dashboard Components

- **Enrolment Summary** -- Total students, new enrolments, withdrawals, and active learner count.
- **Attendance Overview** -- College-wide attendance rate, trend graph, and alerts for courses below threshold.
- **Achievement Rates** -- Pass rates, high grade rates, and comparison with national benchmarks.
- **Retention Rates** -- In-year retention and year-on-year comparison.
- **Destination Summary** -- Post-college destination breakdown with NEET risk count.

### Data Refresh

Dashboard data is calculated from live database records. Summary statistics reflect the current state of the system at the time of viewing.


## KPI Dashboard

The KPI dashboard module tracks key performance indicators against defined targets.

### Standard KPIs

| KPI | Description | Typical Target |
|-----|-------------|----------------|
| Overall attendance | Percentage of sessions attended | 90%+ |
| Retention rate | Percentage of students completing their programme | 95%+ |
| Achievement rate | Percentage of students achieving their qualification | 85%+ |
| High grades | Percentage of students achieving high grades (A*-B / Distinction) | Varies by subject |
| English and Maths | Percentage of condition-of-funding students achieving grade 4+ | 60%+ |
| Destination rate | Percentage of leavers with confirmed positive destinations | 95%+ |
| Value-added | College-wide value-added score | Positive |

### Setting Targets

1. Define KPI targets at the start of each academic year.
2. Set targets at college, department, and course level.
3. Configure RAG (Red, Amber, Green) thresholds for each KPI.
4. Review KPI performance against targets at regular intervals.

### RAG Rating

| Rating | Meaning |
|--------|---------|
| Green | On or above target |
| Amber | Within tolerance but below target |
| Red | Significantly below target, intervention required |


## Progress Dashboard

The progress dashboard module focuses on individual student progress monitoring.

### Features

- **Progress Tracker** -- View each student's current grades against their target grades across all courses.
- **Below-Target Alerts** -- Automatically flag students who are performing below their minimum expected grades.
- **Attendance Correlation** -- Display attendance data alongside progress data to identify patterns.
- **Intervention Log** -- Record and track interventions for students causing concern.
- **Trend Charts** -- Visualise student progress over time using data from successive progress reports.

### Early Warning Integration

The progress dashboard links to the early warning module to provide automated alerts when students meet defined concern criteria, such as:

- Attendance dropping below 85%.
- Two or more subjects below target grade.
- Missed assignment deadlines.
- Behaviour concerns logged.


## Mobile Dashboard

The mobile dashboard module provides optimised dashboard views for mobile devices, enabling staff to access key data on the move.

### Mobile Views

- Quick attendance overview for today's sessions.
- Unread notification count and recent alerts.
- Student lookup with summary profile information.
- KPI summary with RAG ratings.


## Advanced Search

The advanced search module provides flexible querying across all college data.

### Search Capabilities

- **Student Search** -- Find students by name, student ID, course, tutor group, or any combination of filters.
- **Course Search** -- Search courses by code, title, department, or teacher.
- **Cross-Module Search** -- Query data spanning multiple modules (e.g., students with attendance below 80% who are also flagged for NEET risk).

### Building a Search

1. Select the data area to search (students, courses, staff, etc.).
2. Add filter conditions (e.g., attendance rate less than 85%).
3. Choose which fields to display in the results.
4. Run the search and review results.
5. Optionally save the search as a template for future use.
6. Export results in CSV or other formats.


## Surveys

The surveys module (`SurveyService`) supports the creation, distribution, and analysis of surveys for students, staff, and other stakeholders.

### Creating a Survey

1. Navigate to the Surveys section.
2. Click "New Survey".
3. Enter the survey details:

| Field | Description |
|-------|-------------|
| `title` | Survey title (required) |
| `created_by` | Creator's user ID (required) |
| `survey_type` | Type of survey (e.g., student satisfaction, course evaluation, staff feedback) |
| `is_anonymous` | Whether responses are anonymous |
| `target_role` | Which user roles can respond (e.g., student, staff, all) |
| `open_date` | Date the survey becomes available |
| `close_date` | Date the survey closes |
| `status` | Current status (draft, open, closed) |

### Survey Lifecycle

1. **Draft** -- Create the survey and add questions. The survey is not visible to respondents.
2. **Open** -- Publish the survey. Targeted users can now submit responses.
3. **Closed** -- Close the survey. No further responses are accepted. Results can be analysed.

### Survey Types

| Type | Typical Use |
|------|------------|
| Student satisfaction | Annual or termly student experience survey |
| Course evaluation | End-of-course feedback from students |
| Staff feedback | Staff satisfaction and engagement surveys |
| Teaching quality | Student feedback on teaching and learning |
| Stakeholder | External stakeholder consultation |

### Analysis

- View response counts and completion rates.
- Filter responses by role, course, or department.
- Export survey data for detailed analysis.
- Use survey findings as evidence in the Self-Assessment Report.


## Feedback

The feedback module (`FeedbackService`) provides a general-purpose feedback collection system, separate from structured surveys.

### Submitting Feedback

1. Navigate to the Feedback section.
2. Click "Submit Feedback".
3. Enter the feedback details:

| Field | Description |
|-------|-------------|
| `title` | Brief summary of the feedback (required) |
| `description` | Detailed feedback text |
| `category` | Category (e.g., facilities, teaching, IT, catering) |
| `is_anonymous` | Whether the submission is anonymous |
| `submitted_by` | User ID of the submitter (if not anonymous) |

### Feedback Management

- **Upvotes** -- Other users can upvote feedback items to indicate agreement.
- **Admin Response** -- Staff can add an official response to feedback items.
- **Status Tracking** -- Feedback progresses through statuses (e.g., new, under review, addressed, closed).
- **Filtering** -- Filter feedback by category, status, or submitter to identify trends.

### Feedback vs. Surveys

| Feature | Feedback | Surveys |
|---------|----------|---------|
| Initiated by | Any user | Staff/admin |
| Structure | Free-form | Structured questions |
| Timing | Continuous | Time-bounded |
| Anonymity | Optional | Optional |
| Analysis | Qualitative | Quantitative and qualitative |


## Data Export

The data export module (`DataExportService`) manages the export of college data for external reporting, ILR submissions, and ad-hoc analysis.

### Export Jobs

An export job represents a single data export operation. Each job tracks the full lifecycle from creation to completion.

**Creating an export job:**

1. Navigate to the Data Export section.
2. Click "New Export".
3. Select the export type (e.g., ILR, student data, attendance, enrolment).
4. Configure parameters:
   - Academic year.
   - Description.
   - Custom parameters (stored as JSON).
5. Create the job.

**Job lifecycle:**

| Status | Description |
|--------|-------------|
| `pending` | Job created, waiting to run |
| `running` | Job is currently executing |
| `completed` | Job finished successfully |
| `failed` | Job encountered an error |

When a job completes, it records:
- The number of records exported.
- The output file path.
- Any validation errors or warnings encountered.
- A validation log for audit purposes.

### Export Templates

Export templates define reusable export configurations, avoiding the need to reconfigure parameters for recurring exports.

**Creating a template:**

1. Give the template a name and export type.
2. Define the field mapping (which database fields map to which output columns).
3. Set filters (which records to include).
4. Save and activate the template.

Templates can be toggled between active and inactive states. Only active templates appear in the template selection list.

### ILR Submissions

The Individualised Learner Record (ILR) is the primary data collection tool for the Education and Skills Funding Agency (ESFA). The data export module supports ILR submissions by:

- Mapping college data fields to ILR field specifications.
- Running validation checks against ILR business rules.
- Generating the export file in the required format.
- Recording submission results including error counts and warnings.

### Export Statistics

The `get_stats` method provides an overview of export activity:

- Total export jobs run.
- Jobs broken down by status (pending, running, completed, failed).
- Jobs broken down by export type.
- Total and active export templates.

### Supported Export Formats

| Format | Use Case |
|--------|----------|
| CSV | General data export, spreadsheet analysis |
| PDF | Formatted reports for printing or sharing |
| Excel | Detailed data analysis with multiple worksheets |
| XML | ILR and other regulatory submissions |


## Best Practices

- Set clear deadlines for progress report completion and follow up with teachers who have outstanding entries.
- Review KPI dashboards weekly during term time to identify emerging concerns early.
- Use the progress dashboard's early warning integration to trigger interventions before issues escalate.
- Run student satisfaction surveys at least once per year and compare results year-on-year.
- Review feedback items regularly and respond promptly to maintain engagement.
- Test ILR export templates against validation rules before the formal submission deadline.
- Save commonly used advanced search queries as templates for efficient repeat use.
- Export data in the most appropriate format for the audience: CSV for data analysts, PDF for management reports, Excel for detailed operational use.
