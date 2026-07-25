# Staff Management Guide

This guide covers the staff management modules in the Sixth Form College Management System, including HR records, absence tracking, cover arrangements, CPD, appraisals, lesson observations, onboarding, recruitment, disciplinary processes, and staff wellbeing.

---

## Staff Records and HR

The **staff** and **staff_hr** modules manage staff personnel records and HR compliance data.

### Staff HR Records

Each HR record includes:

| Field                          | Description                                    |
|--------------------------------|------------------------------------------------|
| staff_id                       | Link to the staff member                       |
| contract_type                  | full_time, part_time, fixed_term, casual        |
| contract_start / contract_end  | Contract period dates                          |
| dbs_number                     | DBS certificate number                         |
| dbs_date                       | Date of DBS check                              |
| dbs_status                     | pending, clear, barred                         |
| safeguarding_training_date     | Date of last safeguarding training             |
| safeguarding_training_expiry   | When safeguarding training expires             |
| first_aid_trained              | Whether the staff member holds first aid cert   |
| prevent_trained                | Whether Prevent training is completed          |

### Key Features

- Create and manage HR records for all staff
- Filter records by contract type and DBS status
- Track safeguarding training dates and expiry
- Monitor compliance with statutory training requirements

### HR Compliance Workflow

1. Create an HR record when a new staff member joins
2. Record DBS check details and update status as clearance is received
3. Log safeguarding and Prevent training dates
4. Monitor expiry dates for training renewals
5. Update contract details on renewal or change

---

## Staff Absence

The **staff_absence** module provides comprehensive absence tracking with return-to-work and occupational health support.

### Absence Record Fields

| Field                        | Description                                |
|------------------------------|--------------------------------------------|
| staff_id                     | Staff member who is absent                 |
| start_date / end_date        | Period of absence                          |
| absence_type                 | sickness, personal, compassionate, etc.    |
| days_lost                    | Number of working days lost                |
| reason                       | Reason for absence                         |
| self_certified               | Whether absence is self-certified          |
| fit_note_received            | Whether a GP fit note has been received    |
| fit_note_expiry              | Expiry date of the fit note                |
| return_to_work_done          | Whether RTW interview is completed         |
| rtw_date / rtw_notes         | RTW interview date and notes               |
| occupational_health_referral | Whether referred to occupational health    |
| trigger_point_reached        | Whether an absence trigger has been hit    |

### Absence Tracking Workflow

1. Record an absence with start date, type, and reason
2. Update with end date and days lost when the staff member returns
3. Record whether a fit note was received for absences over the self-certification period
4. Conduct and log the return-to-work interview
5. Flag if an absence trigger point has been reached (e.g., Bradford Factor)
6. Refer to occupational health if appropriate

### Searching and Filtering

Absences can be filtered by:
- Staff member
- Absence type
- Status
- Free-text search across name, reason, and notes

---

## Cover Arrangements

The **cover** module manages teaching cover when staff are absent.

### Creating Cover

Each cover arrangement records:
- The absent staff member
- The covering staff member (if assigned)
- The timetable slot being covered
- Cover date, reason, and notes
- Who arranged the cover

### Cover Workflow

1. When a staff absence is recorded, identify affected timetable slots
2. Create a cover arrangement for each slot that needs covering
3. Assign a covering teacher or mark as requiring supply cover
4. Update the arrangement status as it progresses (pending, confirmed, completed)
5. Filter arrangements by date, status, or staff member

---

## Continuing Professional Development (CPD)

The **cpd** module tracks professional development activities for all staff.

### CPD Record Fields

| Field          | Description                                |
|----------------|--------------------------------------------|
| staff_id       | Staff member completing the CPD            |
| title          | Title of the CPD activity                  |
| provider       | Training provider or organisation          |
| cpd_type       | Type: course, conference, mentoring, etc.  |
| hours          | Number of CPD hours completed              |
| certification  | Any certification obtained                 |
| expiry_date    | Expiry date if certification time-limited  |
| evidence       | Evidence of completion                     |
| reflection     | Staff member's reflection on learning      |
| status         | planned, in_progress, completed            |

### CPD Workflow

1. Record planned CPD activities with title, type, and provider
2. Update with hours completed and evidence on completion
3. Add a personal reflection on the learning outcomes
4. Track certification expiry dates for renewal planning
5. Filter CPD records by staff member, type, and status

---

## Appraisals

The **appraisals** module manages annual staff appraisal cycles.

### Appraisal Records

| Field           | Description                              |
|-----------------|------------------------------------------|
| staff_id        | Staff member being appraised             |
| appraiser_id    | Staff member conducting the appraisal    |
| academic_year   | Academic year of the appraisal           |
| appraisal_type  | Type: annual, mid-year, probation, etc.  |
| overall_rating  | Overall performance rating               |
| status          | scheduled, in_progress, completed        |

### Appraisal Cycle Workflow

1. Schedule appraisals for the academic year, assigning appraisers
2. Conduct the appraisal meeting
3. Record the overall rating and update status to completed
4. Filter and report on appraisal completion rates

---

## Lesson Observations

The **observations** module manages teaching observation records as part of quality assurance.

### Observation Records

| Field                     | Description                                |
|---------------------------|--------------------------------------------|
| teacher_id                | Teacher being observed                     |
| observer_id               | Staff member conducting the observation    |
| scheduled_date            | Date of the observation                    |
| course_id                 | Course being observed                      |
| observation_type          | formal, informal, learning_walk, peer      |
| grade                     | Observation grade                          |
| strengths                 | Identified teaching strengths              |
| areas_for_development     | Areas needing improvement                  |
| action_points             | Agreed action points                       |
| status                    | scheduled, completed, cancelled            |

### Observation Workflow

1. Schedule an observation with the teacher, observer, date, and course
2. Conduct the observation and record strengths and development areas
3. Assign a grade and agree action points with the teacher
4. Update the status to completed
5. Link observation outcomes to CPD planning and appraisals

---

## Recruitment

The **recruitment** module manages the full recruitment lifecycle from vacancy to appointment.

### Job Vacancies

Create vacancies with:
- Job title, department, and description
- Contract type (permanent, fixed-term, etc.) and hours (full-time, part-time)
- Salary range and closing/start dates
- Person specification
- Hiring manager assignment
- Status: draft, published, closed, filled

### Recruitment Workflow

1. Draft a vacancy with job details and person specification
2. Publish the vacancy to make it active
3. Applications are received and tracked through the system
4. Shortlist candidates and schedule interviews
5. Record interview outcomes and make offers
6. Update vacancy status to filled on appointment
7. Transition the successful candidate to the onboarding process

---

## Onboarding

The **onboarding** module manages the induction process for new staff with checklists and probation tracking.

### Onboarding Checklists

Each checklist includes:
- Staff member and start date
- Assigned mentor
- Probation end date and outcome
- Overall status (in_progress, completed)
- Notes

### Onboarding Tasks

Individual tasks within a checklist track specific induction activities (IT setup, safeguarding training, department induction, etc.) with completion status.

### Onboarding Workflow

1. Create an onboarding checklist when a new staff member joins
2. Assign a mentor from existing staff
3. Create tasks for all required induction activities
4. Mark tasks as complete as they are finished
5. Conduct probation reviews at intervals
6. Record probation outcome and complete the checklist

---

## Disciplinary and Appeals

The **disciplinary** module manages formal disciplinary cases for both staff and students.

### Case Management

- Create cases specifying person type (staff or student) and person ID
- Track cases through investigation, hearing, and outcome stages
- Record hearing panels, evidence, and decisions
- Manage appeals against disciplinary outcomes
- Filter cases by status and person type

---

## Staff Wellbeing

The **staff_wellbeing** module supports staff welfare through regular check-ins.

### Wellbeing Check-ins

Record periodic check-ins with:
- Mood rating (numeric scale)
- Workload rating
- Stress level
- Notes and concerns
- Confidential flag to restrict visibility

Check-ins help identify staff who may need additional support, workload adjustments, or referral to occupational health services.
