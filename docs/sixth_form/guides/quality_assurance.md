# Quality Assurance Guide

This guide covers the quality assurance, self-assessment, compliance, governance, observations, internal verification, and audit reporting modules within the Sixth Form College Management System.

## Overview

The quality assurance framework in the college system is designed to support Ofsted readiness, continuous improvement, and regulatory compliance. It spans seven interconnected modules that together provide a comprehensive QA infrastructure for further education colleges.

| Module | Purpose |
|--------|---------|
| `quality_assurance` | Central QA coordination, quality improvement plans |
| `self_assessment` | Self-Assessment Report (SAR) creation and management |
| `compliance` | Funding records, resit tracking, destination data compliance |
| `governance` | Governance meeting management and board oversight |
| `observations` | Teaching and learning observation scheduling and grading |
| `internal_verification` | IV sampling plans, assignment verification workflows |
| `audit_reports` | Audit trail generation and compliance reporting |


## Compliance Module

The compliance module (`ComplianceService`) is the most fully developed QA component and manages three critical areas of FE college operations.

### Funding Records

Funding records track the financial basis for each student's enrolment, supporting ILR (Individualised Learner Record) submissions and ESFA compliance.

**Creating a funding record:**

1. Navigate to the Compliance section.
2. Select a student and specify the funding body (e.g., ESFA, local authority).
3. Enter the funding type, ILR reference, programme type, and planned hours.
4. Save the record.

Key fields tracked per funding record:

| Field | Description |
|-------|-------------|
| `funding_body` | The organisation providing funding (e.g., ESFA) |
| `funding_type` | Category of funding (e.g., 16-19 study programme) |
| `ilr_reference` | ILR learner reference number |
| `programme_type` | Programme classification for funding purposes |
| `planned_hours` | Total planned guided learning hours |
| `actual_hours` | Actual hours delivered (updated during the year) |
| `funding_status` | Current status of the funding claim |

Funding records can be filtered by student and updated throughout the academic year as actual hours are recorded.

### Resit Tracking

The resit tracking feature manages GCSE English and Maths resits, which are a condition of funding for many 16-19 learners.

**Workflow for managing resits:**

1. Create a resit record for each student who needs to resit, specifying the subject, original grade, and target grade.
2. Set the `is_condition_of_funding` flag to indicate whether the resit is mandatory for funding compliance.
3. Record the scheduled resit date.
4. After the exam, update the record with the resit grade and change the status accordingly.

Resit records can be filtered by student or by status (e.g., pending, completed, passed, failed) to generate reports for ESFA compliance returns.

### Destination Data

The compliance module also tracks student destinations to meet DfE reporting requirements. Records include destination type, institution name, course title, and confirmation status. This works alongside the dedicated `destinations` module for more detailed destination tracking.


## Quality Assurance Module

The quality assurance module provides the central coordination point for college-wide QA activities.

### Quality Improvement Plans (QIPs)

Quality improvement plans are the primary output of the self-assessment process. A QIP should:

1. Identify specific areas for improvement based on the SAR findings.
2. Set measurable targets with clear deadlines.
3. Assign responsibility to named staff members.
4. Define success criteria and evidence requirements.
5. Include regular review milestones.

### Ofsted Readiness

The QA module supports Ofsted preparation through:

- Aggregated quality metrics across all departments and curriculum areas.
- Links to observation grades, attendance data, and achievement rates.
- Evidence gathering workflows for the Education Inspection Framework (EIF).
- Tracking of previous inspection actions and progress against them.


## Self-Assessment Module

The self-assessment module supports the annual Self-Assessment Report (SAR) cycle, a key requirement for FE colleges.

### SAR Workflow

1. **Initiation** -- Senior leaders set the SAR timeline and assign section leads for each curriculum area and cross-college function.
2. **Data Collection** -- Each area gathers evidence including achievement rates, attendance data, destination outcomes, observation grades, and learner feedback.
3. **Section Drafting** -- Area leads draft their sections, grading against Ofsted criteria (Outstanding, Good, Requires Improvement, Inadequate).
4. **Moderation** -- The quality team reviews all sections for consistency of grading and evidence quality.
5. **Validation** -- The SAR is validated by the senior leadership team and governors.
6. **Publication** -- The final SAR is published and shared with relevant stakeholders.

### Grading Framework

Self-assessment grades align with the Ofsted Common Inspection Framework:

| Grade | Descriptor |
|-------|------------|
| 1 | Outstanding |
| 2 | Good |
| 3 | Requires Improvement |
| 4 | Inadequate |

Each grade must be supported by specific evidence and should reflect the overall quality of provision rather than isolated examples.


## Governance Module

The governance module manages the college's governance structure including board meetings, governor attendance, and decision tracking.

### Meeting Management

- Schedule board meetings, committee meetings, and extraordinary sessions.
- Record attendance of governors at each meeting.
- Attach agendas, minutes, and supporting documents.
- Track actions arising from meetings with assigned owners and deadlines.

### Governor Oversight

Governors can use the system to:

- Review key performance indicators and quality metrics.
- Access SAR summaries and quality improvement plans.
- Monitor compliance status and audit findings.
- Track safeguarding and Prevent duty compliance.


## Observations Module

The observations module manages teaching and learning observations, a core component of the college's quality assurance cycle.

### Observation Types

| Type | Purpose | Frequency |
|------|---------|-----------|
| Formal | Graded observations contributing to SAR evidence | Annually per teacher |
| Developmental | Supportive, non-graded observations for CPD | As needed |
| Peer | Teacher-to-teacher observation for sharing practice | Termly recommended |
| Learning Walk | Short, focused drop-in visits | Regularly throughout year |

### Observation Workflow

1. **Scheduling** -- Observations are scheduled by the quality team, with or without advance notice depending on type.
2. **Pre-observation** -- The observer reviews the session plan, learner profiles, and any relevant context.
3. **Observation** -- The observer records evidence against agreed criteria during the session.
4. **Feedback** -- The observer provides verbal and written feedback, including strengths and areas for development.
5. **Action Planning** -- Where appropriate, an action plan is agreed with specific development targets.
6. **Follow-up** -- Progress against action plans is reviewed at subsequent observations or in one-to-one meetings.


## Internal Verification Module

Internal verification (IV) ensures the accuracy and consistency of assessment decisions across the college.

### IV Process

1. **Sampling Plan** -- The IV lead creates a sampling plan at the start of each academic year, specifying which assignments, assessors, and learner groups will be sampled.
2. **Assignment Verification** -- Before assignments are issued to learners, they are verified to ensure they are fit for purpose, meet the qualification specification, and provide opportunities for learners to achieve at all grade levels.
3. **Assessment Verification** -- A sample of assessed work is second-marked to check that assessment decisions are accurate, consistent, and supported by appropriate feedback.
4. **Feedback to Assessors** -- IV findings are shared with assessors, highlighting good practice and any areas where assessment decisions need to be reconsidered.
5. **Standardisation** -- Regular standardisation meetings are held where assessors discuss and agree on assessment standards.

### IV Documentation

Each IV activity should produce:

- A completed IV record form with the verifier's judgement.
- Notes on the accuracy of assessment decisions.
- Identification of any assessment decisions that need to be amended.
- Action points for the assessor, with follow-up dates.


## Audit Reports Module

The audit reports module generates comprehensive audit trails and compliance reports.

### Available Report Types

- **Funding Audit** -- Cross-references funding records with enrolment and attendance data to identify discrepancies.
- **Compliance Summary** -- Aggregates compliance status across all tracked areas (funding, resits, destinations, safeguarding).
- **Observation Summary** -- Summarises observation grades by department, observation type, and trend over time.
- **IV Completion** -- Tracks IV sampling plan progress and completion rates.
- **Governance Report** -- Summarises governor attendance, meeting frequency, and action completion.

### Generating an Audit Report

1. Select the report type from the audit reports dashboard.
2. Specify the date range and any filters (e.g., department, academic year).
3. Run the report and review the results on screen.
4. Export the report in the required format (CSV, PDF) for external submission or filing.

### Audit Trail

All significant actions within the QA modules are logged automatically, including:

- Record creation and modification timestamps.
- User identification for all changes.
- Status transitions (e.g., funding record status changes, observation grade assignments).

This audit trail supports both internal quality reviews and external inspection evidence requirements.


## Best Practices

- Run compliance checks at the start of each term to identify gaps in funding records and resit registrations.
- Complete the SAR cycle before the end of the autumn term to allow adequate time for QIP development.
- Ensure all observation action plans are followed up within the agreed timeframe.
- Use the IV sampling plan to ensure coverage across all assessors and qualification levels.
- Review audit reports monthly to maintain ongoing Ofsted readiness rather than preparing retrospectively.
