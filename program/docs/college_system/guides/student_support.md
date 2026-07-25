# Student Support Guide

This guide covers the student support and welfare modules in the Sixth Form College Management System, including safeguarding, behaviour management, pastoral care, early warning systems, individual learning plans, wellbeing tracking, counselling, and intervention management.

---

## Student Support Service

The **student_support** module provides a central hub for managing student interventions, risk registers, and support documents.

### Interventions

Interventions track structured support provided to individual students.

| Field             | Description                                   |
|-------------------|-----------------------------------------------|
| student_id        | The student receiving support                 |
| staff_id          | The staff member providing the intervention   |
| intervention_type | Type: academic, pastoral, attendance, etc.    |
| targets           | Agreed targets for the intervention           |
| sessions_planned  | Number of planned support sessions            |
| sessions_attended | Number of sessions actually attended          |
| outcome           | Recorded outcome of the intervention          |
| impact_rating     | Rated as significant, some, or none           |
| status            | Active, completed, or cancelled               |

#### Intervention Workflow

1. Create an intervention specifying the student, staff member, type, and targets
2. Record each session attended using `record_session_attended` (increments count)
3. Update the intervention with outcome and impact rating on completion
4. View the intervention impact report to see effectiveness by type

### Risk Register

The risk register tracks identified risks to student welfare and progress.

- Create risks with type, level (critical, high, medium, low), and mitigations
- Risks are listed ordered by severity (critical first)
- Escalate risks to flag for senior management attention
- Resolve risks with a resolution date
- View a full student risk profile combining risks, interventions, and documents

### Student Documents

Upload and manage supporting documents for student records:
- Document types, titles, and file paths
- Verification workflow with verified-by tracking
- Expiry date monitoring with alerts for documents expiring within a configurable number of days

---

## Safeguarding

The **safeguarding** module manages safeguarding concerns and referrals in compliance with statutory requirements.

### Reporting a Concern

Record a safeguarding concern with:

| Field         | Description                                    |
|---------------|------------------------------------------------|
| student_id    | The student involved                           |
| reported_by   | Staff member raising the concern               |
| category      | Category of concern                            |
| description   | Detailed description of the concern            |
| risk_level    | Risk level: low, medium, high, critical        |
| actions_taken | Initial actions taken                          |

### Safeguarding Workflow

1. Any staff member reports a concern via the system
2. The Designated Safeguarding Lead (DSL) reviews and assigns the concern
3. Update the concern with actions taken, referral agency, and parent notification status
4. Concerns can be marked as confidential to restrict access
5. View all concerns for a specific student to identify patterns

### Concern Statuses

| Status        | Description                             |
|---------------|-----------------------------------------|
| open          | Newly reported, awaiting review         |
| investigating | Under active investigation              |
| referred      | Referred to external agency             |
| resolved      | Concern has been addressed              |
| monitoring    | Ongoing monitoring in place             |

---

## Behaviour Management

The **behaviour** module records behavioural incidents and tracks conduct over time.

### Recording Incidents

Each behaviour record captures:
- Student ID and who recorded it
- Type: concern, positive, incident, or achievement
- Category and description
- Behaviour points (positive or negative)
- Action taken and parent notification status

### Behaviour Workflow

1. Record an incident with type, category, description, and points
2. Assign actions taken (verbal warning, detention, etc.)
3. Update records with parent notification status
4. View a student's full behaviour history
5. Use `count_by_type` to see a breakdown of incident types per student

---

## Pastoral Care

The **pastoral** module manages tutor notes, wellbeing records, and Looked After Children (LAC) records.

### Pastoral Notes

- Add categorised notes about students (academic, welfare, attendance, etc.)
- Mark notes as confidential to restrict visibility
- Set follow-up dates for time-sensitive concerns
- Filter notes by student and category

### Wellbeing Records

Record periodic wellbeing check-ins:
- Wellbeing score (numeric rating)
- Concerns identified
- Actions taken
- Referral to other services if needed

### LAC Records

For Looked After Children, maintain records of:
- Local authority and social worker details
- Care status (in care, previously in care, etc.)
- Personal Education Plan (PEP) dates
- Additional notes and updates

---

## Early Warning System

The **early_warning** module provides automated and manual alerts for students at risk, with configurable rules.

### Alert Types and Triggers

Alerts can be created manually or triggered by rules. Each alert includes:

| Field              | Description                                  |
|--------------------|----------------------------------------------|
| student_id         | Student at risk                              |
| alert_type         | Type of warning                              |
| severity           | low, medium, high, critical                  |
| trigger_source     | What triggered the alert                     |
| trigger_detail     | Specific details of the trigger              |
| attendance_pct     | Student's attendance percentage at trigger    |
| grade_trend        | Grade trend direction (declining, stable)     |
| behaviour_count    | Number of behaviour incidents                |
| recommended_action | Suggested intervention                       |
| assigned_to        | Staff member responsible for follow-up       |

### Rules Engine

Define rules that specify:
- Rule type (attendance, grades, behaviour)
- Threshold value and comparison operator (less_than, greater_than, etc.)
- Severity level assigned to triggered alerts
- Auto-assign role for alerts generated by the rule
- Active/inactive toggle

### Alert Resolution Workflow

1. Alert is created (manually or via rule trigger)
2. Staff review the alert and assign it to a responsible person
3. Action is taken and recorded on the alert
4. Alert is resolved with the action taken noted

### Reporting

Statistics include total alerts, active vs resolved counts, breakdown by severity and type, and number of active rules.

---

## Individual Learning Plans (ILP)

The **ilp** module manages personalised learning plans with targets and periodic reviews.

### Creating an ILP

Each plan includes:
- Student ID and academic year
- Plan type (standard, EHCP, enhanced)
- Long-term goal and support needs
- Review frequency (half-termly, termly, etc.)

### Targets

Add specific targets to a plan:
- Subject area and target description
- Current grade and target grade
- Success criteria and evidence
- Status tracking (in progress, completed, not met)

### Reviews

Conduct periodic reviews of the plan:
- Review date, reviewer, and summary
- Student voice (student's own perspective)
- Actions agreed
- Next review date scheduling

### Monitoring

- List all active plans and filter by status
- Identify plans where the next review date has passed using `get_due_reviews`
- Track target completion across all plans

---

## Student Wellbeing

The **student_wellbeing** module provides comprehensive wellbeing tracking through referrals, daily logs, and counselling sessions.

### Wellbeing Referrals

Create referrals when a student needs additional support:
- Concern category and details
- Risk level assessment (low, medium, high, critical)
- Service referred to (internal or external agency)
- Consent tracking and appointment scheduling
- Outcome recording and resolution

### Wellbeing Logs

Record day-to-day wellbeing observations:
- Mood rating (numeric scale)
- Anxiety level and sleep quality
- Notes and follow-up requirements

### Counselling Sessions

Track formal counselling sessions:
- Session date, type, and number in sequence
- Presenting issues and session notes
- Risk assessment at each session
- Next appointment scheduling

### High-Risk Monitoring

The `get_high_risk_students` function returns all open referrals with high or critical risk levels, ordered by severity, for safeguarding and senior leadership review.

### Full Student Wellbeing View

The `get_student_wellbeing` function provides a consolidated view of all referrals, logs, and counselling sessions for a single student with counts and open-referral summaries.

---

## Intervention Tracking

The **intervention_tracking** module manages academic interventions with value-added measurement.

### Key Features

- Track interventions by type and subject area
- Record pre-assessment and post-assessment scores
- Calculate value added from the intervention
- Monitor session completion (total vs completed)
- Impact notes for qualitative assessment

### Intervention Workflow

1. Create an intervention with student, staff member, type, and subject area
2. Set the total sessions planned
3. Record pre-assessment score at the start
4. Update sessions completed as they occur
5. Record post-assessment score and value added on completion
6. Add impact notes summarising the outcome

---

## Helpdesk

The **helpdesk** module provides a student-facing ticket system for raising queries and issues, tracked through to resolution by support staff.

---

## First Aid

The **first_aid** module records first aid incidents including the student involved, nature of the injury or illness, treatment provided, and whether parents were contacted or further medical attention was required.

---

## Student Council and Peer Mentoring

The **student_council** module manages student representative elections and council activities. The **peer_mentoring** module supports structured peer support programmes, matching mentors with mentees and tracking mentoring sessions.
