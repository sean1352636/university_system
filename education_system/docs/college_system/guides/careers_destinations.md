# Careers and Destinations Guide

This guide covers the careers, destinations, apprenticeships, T-Level, UCAS, value-added, alumni, and functional skills modules within the Sixth Form College Management System.

## Overview

The careers and destinations framework supports students throughout their college journey, from initial careers guidance through to tracking their post-college outcomes. These modules work together to meet the Gatsby Benchmarks for careers guidance and DfE destination reporting requirements.

| Module | Purpose |
|--------|---------|
| `careers` | Careers activities, encounters, and work experience management |
| `destinations` | Post-college destination tracking and NEET risk assessment |
| `apprenticeships` | Apprenticeship opportunity management and applications |
| `tlevel` | T-Level industry placement coordination |
| `ucas` | UCAS application tracking and management |
| `value_added` | Value-added scoring and progress measurement |
| `alumni` | Alumni network and graduate tracking |
| `functional_skills` | English and Maths functional skills tracking |


## Careers Module

The careers module (`CareersService`) manages three core areas: careers activities, UCAS records, and work experience placements.

### Careers Activities

Careers activities record all careers-related encounters and events for each student, supporting Gatsby Benchmark compliance.

**Creating a careers activity:**

1. Navigate to the Careers section.
2. Click "New Activity".
3. Enter the activity details:

| Field | Description |
|-------|-------------|
| `student_id` | The student who participated |
| `activity_type` | Type of activity (default: `encounter`) |
| `description` | Description of the activity |
| `activity_date` | Date of the activity (defaults to today) |
| `gatsby_benchmark` | Which Gatsby Benchmark this activity supports (1-8) |
| `provider` | External provider or organisation involved |
| `duration_minutes` | Duration of the activity in minutes |
| `recorded_by` | Staff member who recorded the activity |

**Gatsby Benchmarks reference:**

| Benchmark | Description |
|-----------|-------------|
| 1 | A stable careers programme |
| 2 | Learning from career and labour market information |
| 3 | Addressing the needs of each student |
| 4 | Linking curriculum learning to careers |
| 5 | Encounters with employers and employees |
| 6 | Experiences of workplaces |
| 7 | Encounters with further and higher education |
| 8 | Personal guidance |

Activities can be listed and filtered by student or activity type, making it straightforward to generate evidence for Gatsby Benchmark compliance reports.

### UCAS Application Management

The UCAS tracking feature manages the full university application cycle for students applying through UCAS.

**Creating a UCAS record:**

1. Select the student.
2. Enter their UCAS ID (when assigned).
3. Set initial statuses for the personal statement and reference.
4. Record predicted grades and university choices.

**UCAS record fields:**

| Field | Description | Statuses |
|-------|-------------|----------|
| `ucas_id` | UCAS personal ID number | -- |
| `personal_statement_status` | Progress on personal statement | `not_started`, `drafting`, `reviewed`, `submitted` |
| `reference_status` | Progress on academic reference | `not_started`, `drafting`, `reviewed`, `submitted` |
| `predicted_grades` | Predicted exam grades | Free text |
| `choices` | University/course choices | Free text |
| `application_status` | Overall application status | `in_progress`, `submitted`, `offers_received`, `firm_accepted` |
| `firm_choice` | Student's firm (first) choice | Free text |
| `insurance_choice` | Student's insurance (backup) choice | Free text |

**UCAS workflow:**

1. Create UCAS records for all Year 13 students intending to apply.
2. Track personal statement drafting progress through review cycles.
3. Monitor reference writing and submission status.
4. Record predicted grades from subject teachers.
5. Update choices as students make their selections.
6. Track application status through to offers, firm, and insurance decisions.

UCAS records can be listed with a filter by application status, allowing staff to quickly identify students at each stage of the process.

### Work Experience

The work experience feature manages placements, including employer details, safeguarding checks, and evaluation.

**Setting up a work experience placement:**

1. Select the student.
2. Enter employer details:
   - Employer name (required).
   - Employer contact person.
   - Placement address.
3. Set the placement period (start and end dates) and hours per week.
4. Describe the student's role.
5. Complete compliance checks:

| Check | Description |
|-------|-------------|
| `dbs_checked` | Employer DBS verification confirmed |
| `risk_assessment` | Workplace risk assessment completed |
| `insurance_confirmed` | Employer liability insurance verified |

6. Set the initial status to `planned`.

**Placement statuses:**

| Status | Meaning |
|--------|---------|
| `planned` | Placement is set up but has not started |
| `in_progress` | Student is currently on placement |
| `completed` | Placement has finished |
| `cancelled` | Placement was cancelled |

After completion, both student and employer evaluations can be recorded against the placement record.


## Destinations Module

The destinations module (`DestinationService`) tracks where students go after leaving college, with a particular focus on identifying and supporting students at risk of becoming NEET (Not in Education, Employment, or Training).

### Recording Destinations

For each student, create a destination record specifying:

| Field | Description |
|-------|-------------|
| `student_id` | The student |
| `academic_year` | The academic year this relates to |
| `intended_destination` | What the student plans to do next |
| `destination_type` | Category (e.g., `university`, `apprenticeship`, `employment`, `gap_year`, `unknown`) |
| `institution_name` | Name of the destination institution or employer |
| `course_title` | Course or programme title at the destination |
| `notes` | Additional context |

Destinations progress from intended to confirmed as students receive offers and acceptances.

### NEET Risk Assessment

The system calculates a NEET risk score (0-4) for each student based on multiple factors:

| Factor | Risk Points | Trigger |
|--------|-------------|---------|
| No confirmed destination | +1 | Student has no confirmed next step |
| Withdrawal record | +1 | Student has been withdrawn from a programme |
| Attendance below 85% | +1 | Overall attendance is below the threshold |
| No contact made | +1 | No follow-up contact has been recorded |

**Risk levels:**

| Score | Level |
|-------|-------|
| 0-1 | Low |
| 2 | Medium |
| 3-4 | High |

**Using NEET risk data:**

1. Run the NEET risk calculation for all leavers.
2. Review students flagged as medium or high risk.
3. Assign follow-up actions to careers advisers or tutors.
4. Record contact attempts and outcomes.
5. Update destination records as students confirm their plans.

### Destination Statistics

The `get_destination_stats` method provides an aggregate summary:

- Total destination records.
- Number confirmed vs. unconfirmed.
- Number flagged as NEET risk.
- Breakdown by destination type.

### Pending Follow-ups

Use `get_pending_followups` to list all students where no contact has been made and no destination has been confirmed. This is the primary working list for the careers team during the summer contact period.


## Apprenticeships Module

The apprenticeships module manages apprenticeship opportunities, applications, and placements.

### Key Features

- Record apprenticeship vacancies with employer details, sector, and level.
- Track student applications and interview outcomes.
- Manage apprenticeship start dates and induction requirements.
- Monitor apprenticeship progress and employer feedback.
- Link apprenticeship activity to Gatsby Benchmarks 5 and 6.


## T-Level Industry Placements

The T-Level module manages the mandatory industry placement component of T-Level qualifications.

### Placement Management

T-Level students must complete a minimum of 315 hours of industry placement. The module tracks:

- Placement employer and location details.
- Placement hours completed against the 315-hour target.
- Employer and student feedback.
- Compliance checks (DBS, risk assessment, insurance) -- following the same pattern as work experience.
- Placement quality assessment aligned to T-Level assessment criteria.


## Value-Added Scoring

The value-added module measures student progress against their starting points, providing a key metric for quality assurance and Ofsted evidence.

### How Value-Added Works

1. **Baseline** -- Record each student's starting qualifications (e.g., GCSE grades) at enrolment.
2. **Expected Outcomes** -- Calculate expected outcomes based on national benchmarks and prior attainment data.
3. **Actual Outcomes** -- Record actual achievement at the end of the programme.
4. **Value-Added Score** -- Compare actual outcomes against expected outcomes to calculate the value-added measure.

A positive value-added score indicates that students achieved better than expected; a negative score indicates underperformance relative to starting points.

### Reporting

- View value-added scores by student, course, department, or college-wide.
- Compare against national benchmarks (e.g., ALPS grades for A-Level provision).
- Use trend data over multiple years to identify improving or declining areas.


## Alumni Network

The alumni module maintains records of former students for ongoing engagement and destination tracking.

### Alumni Features

- Record alumni contact details and consent for communications.
- Track alumni career progression and achievements.
- Manage alumni events and networking opportunities.
- Gather alumni testimonials for marketing and recruitment.
- Support longitudinal destination tracking (3-year and 5-year follow-up).


## Functional Skills

The functional skills module tracks English and Maths qualifications for students who have not yet achieved a grade 4 (or equivalent) at GCSE.

### Condition of Funding

Students aged 16-19 who have not achieved a grade 4 in GCSE English and/or Maths are required to continue studying these subjects as a condition of their funding. The functional skills module:

- Identifies students who need to resit or take functional skills qualifications.
- Tracks enrolment on English and Maths courses.
- Records assessment results and progress.
- Links to the compliance module's resit tracking for ESFA reporting.
- Monitors attendance at English and Maths sessions separately from main programme attendance.

### Integration with Compliance

Functional skills data feeds directly into the compliance module's resit tracking, where each resit record can be flagged with `is_condition_of_funding` to ensure accurate ILR returns and funding claims.


## Best Practices

- Record all careers activities promptly to maintain accurate Gatsby Benchmark evidence.
- Begin UCAS tracking in Year 12 to ensure adequate preparation time.
- Run the NEET risk calculation for all Year 13 students from the spring term onwards.
- Follow up with all unconfirmed destinations during the summer and early autumn.
- Complete all work experience and T-Level placement compliance checks before the placement start date.
- Review value-added data at the end of each academic year and incorporate findings into the SAR.
- Keep functional skills records aligned with the compliance module to avoid discrepancies in ILR submissions.
