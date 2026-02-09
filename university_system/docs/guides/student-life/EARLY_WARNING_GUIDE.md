# Early Warning System - User Guide

## Overview

The Early Warning System (EWS) proactively identifies students at risk of academic failure through multi-factor risk assessment. By analyzing academic performance, attendance patterns, campus engagement, and financial indicators, the system generates risk scores and recommends targeted interventions. Designed for academic advisors, faculty, and administrators to enable timely support before problems escalate.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Risk Assessment](#risk-assessment)
3. [Risk Score Breakdown](#risk-score-breakdown)
4. [Monitoring Students](#monitoring-students)
5. [Interventions](#interventions)
6. [Alerts & Notifications](#alerts--notifications)
7. [Reporting & Analytics](#reporting--analytics)
8. [Administration](#administration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Early Warning System

**For Academic Advisors:**
1. Navigate to **Student Affairs** → **Early Warning System**
2. Login with staff credentials
3. View your assigned students' risk dashboard

**For Faculty:**
1. Navigate to **Academics** → **Early Warning**
2. View risk indicators for students in your courses

**For Administrators:**
1. Navigate to **Administration** → **Early Warning System**
2. Full access to all risk data, interventions, and reports

### EWS Dashboard

**Dashboard Overview:**
- **At-Risk Students**: Students with elevated risk scores
- **Risk Distribution**: Breakdown by risk level (Critical, High, Medium, Low)
- **Active Interventions**: Current intervention actions in progress
- **Trend Indicators**: Students whose risk is increasing or decreasing
- **Recent Alerts**: Latest automated alerts triggered

---

## Risk Assessment

### How Risk is Calculated

The Early Warning System uses a **weighted multi-factor model** to generate an overall risk score from 0 to 100. Higher scores indicate greater risk.

**Risk Factors and Weights:**

| Factor | Weight | Data Source |
|--------|--------|-------------|
| **Academic Risk** | 40% | GPA, grades from last 3 months |
| **Attendance Risk** | 30% | Attendance percentage, consecutive absences |
| **Engagement Risk** | 20% | Campus activity participation |
| **Financial Risk** | 10% | Outstanding balances, payment issues |

### Risk Levels

| Risk Level | Score Range | Color | Description |
|------------|-----------|-------|-------------|
| **Critical** | 70-100 | Red | Immediate intervention required |
| **High** | 50-69 | Orange | Prompt attention needed |
| **Medium** | 30-49 | Yellow | Monitoring recommended |
| **Low** | 0-29 | Green | No immediate concern |

### Viewing a Student's Risk Score

**Access Risk Profile:**
1. Navigate to **Students** → Search for student
2. Open student's **Risk Profile**
3. View:
   - Overall risk score
   - Individual factor scores
   - Score history over time
   - Risk level classification
   - Recommended interventions

---

## Risk Score Breakdown

### Academic Risk (40% Weight)

**Indicators Monitored:**
- Current GPA and GPA trend
- Grades in individual courses (last 3 months)
- Failed or incomplete courses
- Grade point changes between terms
- Course difficulty level vs. performance

**Risk Triggers:**
- GPA below 2.0
- Failing grade in any course
- Significant GPA decline (0.5+ drop)
- Multiple courses below C grade

### Attendance Risk (30% Weight)

**Indicators Monitored:**
- Overall attendance percentage
- Consecutive absences
- Attendance trends (improving or declining)
- Patterns (missing specific classes, days of week)

**Risk Triggers:**
- Attendance below 75%
- 3+ consecutive absences
- Declining attendance trend over 2+ weeks
- Missing classes in critical courses

### Engagement Risk (20% Weight)

**Indicators Monitored:**
- Campus activity participation
- Club/organization involvement
- Event attendance
- Library usage
- Peer interaction metrics

**Risk Triggers:**
- No campus activities in 30+ days
- Dropped out of clubs or organizations
- Zero event attendance in current term
- Significant decline in engagement from prior term

### Financial Risk (10% Weight)

**Indicators Monitored:**
- Outstanding balance on student account
- Payment plan adherence
- Financial aid status
- Work-study participation

**Risk Triggers:**
- Overdue balance exceeding threshold
- Missed payment plan installments
- Financial aid hold or revocation
- Sudden increase in outstanding balance

---

## Monitoring Students

### Student Watch List

**Managing Your Watch List:**
1. Navigate to **Monitoring** → **Watch List**
2. View students assigned to you or flagged by the system
3. For each student:
   - Current risk level and score
   - Risk trend (increasing, stable, decreasing)
   - Last intervention date
   - Next follow-up date
4. Sort by risk level, score, or last contact date

### Tracking Risk Trends

**Trend Analysis:**
- View risk score history over time
- Identify students with increasing risk trajectories
- Compare risk before and after interventions
- Spot patterns (e.g., risk spikes mid-semester)

### Setting Up Custom Monitoring

**Custom Alerts:**
1. Navigate to **Monitoring** → **Custom Alerts**
2. Define alert criteria:
   - Risk score threshold
   - Specific risk factor changes
   - Student groups (course, major, year)
3. Set notification preferences
4. Save alert configuration

---

## Interventions

### Recommended Interventions

**Based on Risk Level:**

| Risk Level | Recommended Actions |
|------------|-------------------|
| **Critical** | Immediate advisor meeting, success coaching, tutoring referral, financial aid review |
| **High** | Advisor outreach within 48 hours, tutoring referral, study skills workshop |
| **Medium** | Email check-in, academic resource suggestions, mentor connection |
| **Low** | Standard advising, preventive resource sharing |

### Creating an Intervention

**Log an Intervention:**
1. Open student's risk profile
2. Navigate to **Interventions** → **New Intervention**
3. Select intervention type:
   - **Email Alert**: Automated email to student with resources
   - **Advisor Meeting**: Schedule one-on-one advising session
   - **Success Coaching**: Refer to academic success coaching
   - **Tutoring Referral**: Connect with tutoring services
   - **Financial Counseling**: Refer to financial aid office
   - **Mental Health Referral**: Connect with counseling services
   - **Custom**: Define a custom intervention
4. Add notes and expected outcomes
5. Set follow-up date
6. Save intervention

### Tracking Intervention Outcomes

**Monitor Effectiveness:**
1. Open student's intervention history
2. View all past interventions:
   - Date and type
   - Staff member who initiated
   - Notes and outcomes
   - Risk score before and after
3. Update intervention status:
   - **In Progress**: Intervention active
   - **Completed**: Intervention finished
   - **Effective**: Risk decreased after intervention
   - **Ineffective**: Risk unchanged or increased

---

## Alerts & Notifications

### Automated Alerts

**System-Generated Alerts:**
- **New Critical Risk**: Student crosses into critical risk level
- **Risk Increase**: Student's risk score increases by 15+ points
- **Attendance Alert**: Student misses 3+ consecutive classes
- **Academic Alert**: Student receives failing grade
- **Financial Alert**: Account becomes significantly overdue

### Alert Delivery

**Notification Methods:**
- Email notifications to assigned advisor
- Dashboard alerts in the EWS interface
- Optional SMS for critical alerts
- Automated emails to students with support resources

### Managing Alerts

**Alert Actions:**
1. Navigate to **Alerts** → **Active Alerts**
2. View pending alerts
3. For each alert:
   - **Acknowledge**: Mark as seen
   - **Investigate**: Open student profile
   - **Create Intervention**: Start intervention from alert
   - **Dismiss**: Close alert with reason
   - **Escalate**: Forward to supervisor

---

## Reporting & Analytics

### Available Reports

**Standard Reports:**
- **Risk Distribution**: Students by risk level across the institution
- **At-Risk Summary**: Detailed list of high and critical risk students
- **Intervention Report**: All interventions by type, outcome, and period
- **Trend Report**: Risk score changes over a semester
- **Department Report**: Risk levels by academic department
- **Retention Analysis**: Correlation between risk scores and retention

### Generating Reports

**Create a Report:**
1. Navigate to **Reports** → **Generate**
2. Select report type
3. Set parameters:
   - Date range
   - Department or program filter
   - Risk level filter
   - Advisor filter
4. Choose format (PDF, CSV, Excel)
5. Generate and download

### Dashboard Analytics

**Visual Analytics:**
- Risk level distribution pie chart
- Risk score trends line graph
- Intervention effectiveness bar chart
- Department comparison heat map
- Retention prediction dashboard

---

## Administration

### System Configuration

**Configure EWS:**
1. Navigate to **Admin** → **EWS Settings**
2. Adjust parameters:
   - Risk factor weights (must total 100%)
   - Risk level thresholds
   - Alert trigger conditions
   - Data refresh frequency
   - Retention of historical data

### Advisor Assignments

**Managing Assignments:**
- Assign students to advisors for monitoring
- Set advisor caseload limits
- Transfer students between advisors
- View advisor workload distribution

### Data Sources

**Integration Management:**
- Configure connections to academic records system
- Set up attendance data feed
- Link engagement tracking systems
- Connect financial systems
- Set data refresh schedules

---

## Best Practices

1. **Act early** - Intervene at the medium risk level, don't wait for critical
2. **Follow up consistently** - Set and honor follow-up dates for every intervention
3. **Document everything** - Log all interactions and intervention outcomes
4. **Use multiple factors** - Don't rely on a single indicator; review the full profile
5. **Coordinate across departments** - Share information between advisors, faculty, and support services
6. **Review trends, not just snapshots** - A rising score is more concerning than a static one
7. **Respect student privacy** - Share risk information only with those who need to know

---

## Troubleshooting

### Common Issues

**Risk score not updating:**
- Data refreshes on a scheduled basis (check admin settings)
- Recent grades or attendance may not be reflected immediately
- Verify data source connections are active
- Contact IT if data feeds appear stalled

**Student missing from watch list:**
- Check filter settings (risk level, department)
- Verify the student is currently enrolled
- Ensure the student has enough data for risk calculation
- New students may not have sufficient history yet

**Intervention not recording:**
- Ensure all required fields are completed
- Verify you have permission to create interventions
- Check that the student profile is accessible
- Save and verify the intervention appears in history

**Alert not triggering:**
- Review alert configuration thresholds
- Check that the student's data has been updated
- Verify notification email address is correct
- Ensure alerts are not set to dismissed or muted

---

## Contact Information

**Academic Advising Center**
- **Phone**: (555) 123-ADVS
- **Email**: advising@university.edu
- **Location**: Student Success Center, Room 200
- **Hours**: Monday-Friday 8:30 AM - 5 PM

**Student Success Office**
- **Phone**: (555) 123-SUCC
- **Email**: studentsuccess@university.edu

**IT Support (EWS Technical)**
- **Phone**: (555) 123-TECH
- **Email**: ewssupport@university.edu

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/student_affairs/services/early_warning/early_warning_core.py`
**Support**: advising@university.edu | (555) 123-ADVS
