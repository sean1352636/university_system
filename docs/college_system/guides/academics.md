# Academic Features Guide

This guide covers the academic modules in the Sixth Form College Management System, including student records, course management, enrollment, grading, attendance, timetabling, examinations, assignments, and related features.

---

## Student Records

The **students** module manages all student records within the college.

### Key Features

- Auto-generated sequential student IDs with configurable prefix (e.g., STU0001)
- Student profiles with personal details, year group, form group, and form tutor
- Comprehensive profile view including current enrollments and grades
- Search and filter by status, year group, form group, or free-text search
- Full cascade deletion removing enrollments, grades, attendance, submissions, and linked user accounts

### Student Fields

| Field          | Description                          |
|----------------|--------------------------------------|
| student_id     | Auto-generated ID (e.g., STU0001)    |
| first_name     | Student first name                   |
| last_name      | Student last name                    |
| email          | Contact email (validated)            |
| phone          | Contact phone number                 |
| date_of_birth  | Date of birth                        |
| address        | Home address                         |
| year_group     | Year group (defaults to 12)          |
| form_group     | Assigned form group                  |
| form_tutor     | Assigned form tutor                  |
| status         | Active, withdrawn, etc.              |

### Viewing Student Details (Double-Click)

In the GUI, **admin / staff / instructor** users can double-click any
row in the Students treeview to open a read-only details window for
that student. This mirrors the equivalent feature in the University
System and avoids opening the full edit dialog when you only need to
look something up.

The details window has two tabs:

| Tab | Contents |
|---|---|
| Personal | Student ID, names, DOB, contact info (email/phone/address), year/form/tutor, status, created/updated timestamps |
| Enrollments | Course ID, course name, status, and enrolment date for every active enrolment, loaded via `EnrollmentService.list_enrollments(student_pk=...)` |

Footer buttons: `Close` is always present; `admin` users also see an
`Edit` button that closes the details window and opens the full edit
dialog (the same flow as the toolbar `Edit Selected` button).

Other roles (students, parents) silently no-op on double-click — there
is no error popup. The behaviour is implemented in
`college_system/modules/domain/students/gui/student_gui.py` via
`_on_double_click_student` and `_show_student_details`.

---

## Course Management

The **courses** module handles course creation, prerequisites, and roster management.

### Key Features

- Course codes with validation and uniqueness enforcement
- Guided learning hours, capacity, subject area, and qualification type tracking
- Prerequisite management with circular dependency detection
- Enrollment counts and student roster retrieval
- Filtering by subject area, term, qualification type, and status

### Supported Qualification Types

Courses can be categorised by qualification type, defaulting to "A-Level". Common types include A-Level, BTEC, and vocational qualifications.

### Prerequisites Workflow

1. Add a prerequisite linking one course to another
2. The system checks for circular dependencies before saving
3. During enrollment, students must have a passing grade (not U) in all prerequisite courses
4. Prerequisites can be removed at any time

---

## Enrollment

The **enrollment** module manages student course enrollments with automatic waitlist support.

### Enrollment Process

1. Verify the student exists and the course is active
2. Check for duplicate enrollment or existing waitlist entry
3. Validate all prerequisite courses are passed
4. If the course has capacity, enroll the student directly
5. If the course is full, automatically add the student to the waitlist with a position number
6. A notification is sent to the student upon successful enrollment

### Waitlist and Auto-Promotion

When a student drops a course, the system automatically promotes the next student from the waitlist:

1. The dropped student's enrollment status changes to "dropped" with a timestamp
2. The first student on the waitlist is removed and enrolled
3. Remaining waitlist positions are renumbered sequentially

### Enrollment Statuses

| Status    | Description                          |
|-----------|--------------------------------------|
| enrolled  | Currently active in the course       |
| dropped   | Voluntarily dropped with timestamp   |
| waitlisted| On the waitlist pending a place      |

---

## Grade Recording

The **grades** module supports actual grades, predicted grades, and UCAS tariff point calculation.

### Grade Types

- **Actual grades**: Recorded as numeric scores (0-100), automatically converted to letter grades using the system grade scale
- **Predicted grades**: Recorded as letter grades directly, used for UCAS applications and progress monitoring

### Key Features

- Automatic score-to-letter conversion using the configured grade scale
- UCAS tariff point calculation from letter grades
- Full student transcripts with total UCAS points
- Course-level grade statistics (average, min, max, median)
- Grade notifications sent to students automatically

### Grade Recording Workflow

1. Verify the student is enrolled in the course
2. Record the numeric score; the system derives the letter grade
3. If a grade of the same type already exists, it is updated rather than duplicated
4. Students receive a notification with the grade details

### Transcripts

The transcript feature combines all actual grades for a student with UCAS point totals and subject counts.

---

## Attendance Tracking

The **attendance** module manages sessions and per-student attendance records with timetable integration.

### Attendance Statuses

| Status   | Counted as Attended |
|----------|---------------------|
| present  | Yes                 |
| late     | Yes                 |
| absent   | No                  |
| excused  | No                  |

### Session Management

- Create sessions manually for a course and date, or generate them from timetable slots
- Generate registers for an entire day based on the timetable using `generate_registers_for_date`
- Pre-populate sessions with absent marks for all enrolled students, then mark present/late as they arrive

### Attendance Workflow

1. Generate registers for the day (automatically creates sessions for all timetabled slots)
2. Pre-populate each session with "absent" records for all enrolled students
3. Staff mark students as present, late, or excused during the lesson
4. View attendance summaries per student per course, including attendance rate percentage

### Reporting

- Per-student attendance summary with breakdown by status and attendance rate
- Course-wide attendance reports listing every enrolled student with their rates
- Historical attendance records filterable by course

---

## Timetable Management

The **timetable** module handles scheduling with conflict detection and auto-generation.

### Key Features

- Manual slot creation with day, start time, end time, room, and instructor
- Room and instructor conflict detection before saving
- Student clash detection across enrolled courses
- Per-student, per-course, per-room, and per-instructor timetable views
- Full weekly timetable auto-generation for all active courses

### College Day Structure

| Period   | Time          |
|----------|---------------|
| Period 1 | 09:00 - 10:00 |
| Period 2 | 10:00 - 11:00 |
| Break    | 11:00 - 11:20 |
| Period 3 | 11:20 - 12:20 |
| Lunch    | 12:20 - 13:00 |
| Period 4 | 13:00 - 14:00 |
| Period 5 | 14:00 - 15:00 |

### Auto-Generation

The `generate_full_timetable` function schedules all active courses across the week:

1. Each course is assigned an offset to rotate through different periods across the five-day week (Phase 1: 5 single periods)
2. Teacher offsets are tracked to avoid the same teacher having two courses in the same slot
3. Phase 2 adds two double-lesson extensions per course by adding adjacent periods, giving 7 periods per week total
4. The function returns a summary with slots created, courses scheduled, and any partial or unscheduled courses

---

## Exam Scheduling

The **exams** module manages external exam entries, timetabling, and results.

### Exam Entries

Create entries for students specifying:
- Exam board (e.g., AQA, Pearson, OCR)
- Qualification and unit code
- Exam series (e.g., June 2026)
- Tier and fee information
- Status tracking (planned, entered, completed)

### Exam Timetable

Schedule specific exam sittings with:
- Date, start time, and duration in minutes
- Room allocation and seat number
- Invigilator assignment

### Results Recording

Record external exam results including grade, UMS score, raw mark and max mark, result date, and series.

---

## Assignments and Submissions

The **assignments** module manages coursework with submission tracking, late detection, and grading.

### Assignment Workflow

1. Create an assignment for a course with title, description, due date, and max score
2. Optionally enable late submissions with the `allow_late` flag
3. Students submit their work; the system detects late submissions automatically
4. Staff grade submissions with a score (validated against max score) and optional feedback

### Submission Features

- Late submission detection by comparing submission date to due date
- Enrollment verification before accepting submissions
- View all submissions for an assignment or all submissions by a student
- Grading with score, written feedback, and grader tracking

---

## Academic Year

The **academic_year** module defines academic year periods with start and end dates, current year designation, and status tracking. Multiple years can be stored, and one is marked as current for the active session.

---

## Baseline Assessment

The **baseline_assessment** module records initial assessment data for students on entry and tracks progress checkpoints throughout the year.

### Key Features

- Record baseline scores in English, maths, and ICT
- Filter baselines by academic year and assessment type
- Create progress checkpoints at any point linked to a student and optional course
- View student progress combining baseline data with chronological checkpoints
- Aggregate statistics including average baseline scores

---

## Study Programmes

The **study_programmes** module implements ESFA 16-19 study programme management with condition of funding validation.

### Programme Types

| Type         | Min Planned Hours |
|--------------|-------------------|
| Level 3      | 540               |
| Level 2      | 540               |
| Level 1      | 540               |
| Entry        | 540               |
| Traineeship  | 280               |
| T Level      | 900               |

### Components

Each programme is composed of components: qualification, work experience, enrichment, tutorial, maths/English, and pastoral. Components track planned and delivered hours.

### Validation

The `validate_programme` function checks ESFA condition of funding rules:
- Maths requirement met, exempt, or enrolled
- English requirement met, exempt, or enrolled
- Total planned hours meet the minimum for the programme type
- Work experience completed (required for Level 1-3 and T Level)

### Reporting

- Condition of funding check: lists all active programmes with unmet maths or English requirements
- Funding hours report: summary of planned vs delivered hours per programme
- Statistics including programme type distribution, validity rates, and maths/English met percentages

---

## Tutorial System

The **tutorial** module manages tutor assignments, group tutorial sessions, and individual 1-to-1 meeting records.

### Tutor Assignments

- Assign students to tutors with a tutor group and academic year
- View all students in a tutor group
- End assignments when students leave or change groups

### Tutorial Sessions

- Schedule group tutorial sessions with topic, resources, and notes
- Mark sessions as completed with summary notes
- Filter sessions by tutor, group, and status

### 1-to-1 Records

Record individual meetings between tutors and students with:
- Meeting type, discussion notes, and targets set
- Student concerns and follow-up requirements
- Follow-up tracking with a dedicated view for pending follow-ups

---

## Calendar

The **calendar** module provides event management for academic and college-wide events, supporting scheduling, categorisation, and calendar views across the college.
