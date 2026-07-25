# Admissions Guide

This guide covers the admissions module in the Sixth Form College Management System, including the application process, induction management, withdrawal tracking, and links to the UCAS module for university applications.

---

## Overview

The **admissions** module manages the full student lifecycle from initial application through to enrollment and, where necessary, withdrawal. It provides tracking at each stage so that admissions staff can monitor pipeline volumes, follow up with applicants, and ensure a smooth transition into college life.

---

## Application Process

### Creating an Application

Each application captures the following information:

| Field              | Description                                        |
|--------------------|----------------------------------------------------|
| applicant_name     | Full name of the applicant                         |
| date_of_birth      | Date of birth                                      |
| email              | Contact email address                              |
| phone              | Contact phone number                               |
| course_preferences | Preferred courses or subjects (free text)          |
| previous_school    | Name of the applicant's current or previous school |
| gcse_results       | GCSE grades or predicted grades                    |
| personal_statement | Personal statement from the applicant              |

### Application Workflow

1. **Application received** -- An applicant submits their details. The system creates a record with status "submitted" and records the application timestamp.

2. **Initial review** -- Admissions staff review the application, checking course preferences against entry requirements and GCSE results.

3. **Status update** -- Update the application status with optional notes at each stage. Typical status progression:

| Status       | Description                                         |
|--------------|-----------------------------------------------------|
| submitted    | Application received, awaiting review               |
| under_review | Being assessed by admissions team                   |
| interview    | Applicant invited for interview                     |
| offered      | Conditional or unconditional offer made             |
| accepted     | Applicant has accepted the offer                    |
| rejected     | Application unsuccessful                           |
| withdrawn    | Applicant has withdrawn their application           |

4. **Offer management** -- Once reviewed, offers are made. Offers may be conditional (pending GCSE results) or unconditional.

5. **Acceptance and enrollment** -- When an applicant accepts their offer, they transition to the enrollment process. A student record is created in the students module, and course enrollments are set up.

### Filtering and Reporting

- List applications filtered by status to monitor pipeline stages
- View total applications by status for admissions reporting
- Track application volumes over time using the `applied_at` timestamp
- Set limits on returned results for large cohorts

---

## Induction Management

Once a student has accepted their offer and is enrolled, the induction process ensures all required information and documentation is collected.

### Induction Records

| Field              | Description                                   |
|--------------------|-----------------------------------------------|
| student_id         | Link to the enrolled student record           |
| emergency_contact  | Emergency contact details                     |
| medical_info       | Relevant medical information                  |
| consent_form       | Whether consent form is signed                |
| learning_agreement | Whether learning agreement is signed          |
| photo_id           | Whether photo ID has been provided            |
| ict_acceptable_use | Whether ICT acceptable use policy is signed   |
| status             | pending, in_progress, completed               |

### Induction Workflow

1. **Create induction** -- When a student is enrolled, create an induction record with their emergency contact and medical information.

2. **Collect documentation** -- Update the induction record as each document is received:
   - Consent form
   - Learning agreement
   - Photo ID
   - ICT acceptable use policy

3. **Complete induction** -- Once all required items are collected, update the status to "completed".

4. **Monitor progress** -- List inductions filtered by status to identify students with incomplete documentation. Follow up before the term start date.

### Induction Checklist

A typical induction checklist includes:

- Emergency contact details confirmed
- Medical information recorded
- Consent forms signed by parent/guardian (if under 18)
- Learning agreement signed
- Photo ID provided for student card
- ICT acceptable use policy signed
- College tour completed
- Timetable issued
- Bursary application submitted (if applicable)

---

## Withdrawal Management

The admissions module also handles student withdrawals throughout the academic year.

### Withdrawal Records

| Field            | Description                                    |
|------------------|------------------------------------------------|
| student_id       | The withdrawing student                        |
| reason           | Reason for withdrawal                          |
| withdrawal_date  | Date of withdrawal (defaults to today)         |
| destination      | Where the student is going next                |
| destination_type | Type of destination (other college, employment) |
| exit_interview   | Whether an exit interview was conducted        |
| notes            | Additional notes                               |

### Withdrawal Workflow

1. **Record withdrawal** -- Create a withdrawal record with the reason and date.

2. **Exit interview** -- Conduct an exit interview where possible and record whether it took place.

3. **Destination tracking** -- Record where the student is going (another college, employment, NEET, etc.) for destination reporting.

4. **Update student status** -- The student's status in the students module should be updated to "withdrawn".

5. **Reporting** -- List withdrawals to analyse retention rates and common reasons for leaving.

---

## Integration with Student Records

The admissions module connects to the broader system at several points:

- **Application to enrollment**: When an applicant accepts their offer, a student record is created with the information from their application (name, date of birth, email, phone).
- **Course enrollment**: Course preferences from the application inform which courses the student is enrolled in, handled by the enrollment module.
- **Induction to student profile**: Induction data (emergency contacts, medical information) enriches the student profile.
- **Withdrawal to student status**: Withdrawal records trigger a status update on the student record.

---

## UCAS Applications

The **ucas** module manages university applications for Year 13 students applying through UCAS.

### UCAS Application Records

| Field                      | Description                                  |
|----------------------------|----------------------------------------------|
| student_id                 | Student making the application               |
| academic_year              | Academic year of application                 |
| ucas_id                    | Student's UCAS personal ID                   |
| personal_statement_status  | Status of personal statement preparation     |
| reference_status           | Status of the college reference              |
| predicted_tariff           | Predicted UCAS tariff points                 |
| application_status         | draft, in_progress, submitted, etc.          |
| submitted_at               | Timestamp of UCAS submission                 |

### University Choices

Each application can have multiple university choices:

| Field           | Description                              |
|-----------------|------------------------------------------|
| university_name | Name of the university                   |
| course_title    | Title of the course applied to           |
| ucas_code       | UCAS course code                         |
| choice_number   | Choice ranking (1-5)                     |

### UCAS Workflow

1. **Create application** -- Set up a UCAS application for a Year 13 student with their academic year and UCAS ID.

2. **Personal statement** -- Track the status of the student's personal statement preparation.

3. **Reference** -- Monitor the progress of the college reference, typically written by the student's tutor.

4. **Predicted grades** -- The grades module provides predicted grades, and the grade service calculates predicted UCAS tariff points.

5. **Add choices** -- Record the student's university choices with course details and UCAS codes.

6. **Submit** -- Mark the application as submitted with a timestamp.

7. **Track outcomes** -- Update application and choice statuses as offers and decisions are received.

### Integration with Grades

The UCAS module works closely with the grades module:
- Predicted grades recorded via `record_predicted_grade` are used for UCAS applications
- `calculate_ucas_points` provides the predicted tariff total
- Transcripts can be generated for reference writing

---

## Admissions Reporting

Key reports available through the admissions system:

| Report                    | Description                                         |
|---------------------------|-----------------------------------------------------|
| Application pipeline      | Count of applications by status                     |
| Conversion rate           | Percentage of offers accepted                       |
| Induction completion      | Students with incomplete induction documentation    |
| Withdrawal analysis       | Withdrawals by reason and destination type          |
| UCAS submission tracker   | Year 13 students and their UCAS application status  |
| Destination data          | Where withdrawn students and leavers have gone      |
