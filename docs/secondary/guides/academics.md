# Academics Domain Guide

**Secondary School Management System**
Last Updated: March 2026

---

## Overview

The Academics domain covers 12 modules spanning student records, curriculum, assessment, and reporting for Years 7-11 (KS3 and KS4). All modules follow the service-first design pattern and store data in the SQLite database (`secondary_school.db`).

---

## Students

Manage student records with SEC-prefixed identifiers.

| Field | Description |
|---|---|
| Student ID | Auto-generated, SEC0001 onwards |
| Year Group | 7, 8, 9 (KS3) or 10, 11 (KS4) |
| Form Group | Tutor group assignment (e.g. 7A, 10B) |
| Key Stage | KS3 (Years 7-9), KS4 (Years 10-11) |
| Status | Active, Left, Excluded, Transferred |

- Add, edit, and archive student records
- Search by name, ID, year group, or form
- Track student status changes with date stamps
- View a student's full profile: contacts, medical flags, SEN status, Pupil Premium

### Viewing Student Details (Double-Click)

In the GUI, **admin / staff / teacher / instructor** users can
double-click any row in the Students treeview to open a read-only
details window for that student. This mirrors the equivalent feature
in the University System.

The details window has two tabs:

| Tab | Contents |
|---|---|
| Personal | Student ID, names, DOB, address, year/form/key-stage, SEN status, Pupil Premium, status, parent/guardian (name/email/phone), emergency contact, created/updated timestamps |
| Subjects | Subject code, title, teacher, room — for every active enrolment, loaded via `EnrollmentService.get_student_enrollments(pk)` |

Footer buttons: `Close` is always present; `admin` users also see an
`Edit` button that closes the details window and opens the full edit
dialog (the same flow as the toolbar `Edit Selected` button).

Other roles (students, parents) silently no-op on double-click. The
behaviour is implemented in
`secondary_school/modules/domain/academics/students/gui/student_gui.py`
via `_on_double_click_student` and `_show_student_details`.

## Subjects

Define and organise the curriculum by department and key stage.

- Create subjects with name, code, and department
- Assign subjects to KS3, KS4, or both
- Link subjects to exam boards (AQA, Edexcel, OCR) for KS4/GCSE
- Set subject capacity limits per class
- Group subjects by department for reporting (e.g. English, Maths, Science, Humanities)

## Enrollment

Handle subject enrollment, option choices, and class allocation.

- **KS3**: Students follow the core curriculum; enrollment is automatic by year group
- **KS4 Options**: Students select GCSE option subjects (typically in Year 9)
  - Define option blocks and available subjects per block
  - Record student choices and reserve options
  - Validate choices against timetable constraints
- Allocate students to specific teaching groups/classes
- Transfer students between groups mid-year with audit trail

## Grades

Record and track GCSE grades on the 9-1 scale.

| Grade | Meaning |
|---|---|
| 9 | Exceptional performance |
| 7-8 | Well above expected |
| 5-6 | Strong pass / above expected |
| 4 | Standard pass |
| 3 | Below standard pass |
| 1-2 | Low attainment |
| U | Ungraded / unclassified |

- Enter current working grades, predicted grades, and target grades
- Record mock exam results with date and exam series
- Compare actual vs predicted performance
- Bulk grade entry by class or subject
- Grade history maintained per student per subject

## Attendance

Track attendance at session and lesson level.

- **Session registers**: AM (morning) and PM (afternoon) marks
- **Lesson registers**: Per-period attendance linked to timetable
- Standard DfE absence codes: `/` (present AM), `\` (present PM), `N` (unauthorised), `I` (illness), `L` (late), `C` (authorised), `O` (unauthorised absence)
- Persistent absence monitoring: flags students below 90% attendance
- Attendance reports by student, form group, year group, or whole school
- Automated alerts for unexplained absences
- First-day calling support for absent students

## Timetable

Build and manage the school timetable.

- Define periods, break times, and lunch slots per day
- Assign teachers to subjects and classes
- Allocate rooms to lessons
- Clash detection: prevents double-booking of teachers, rooms, or student groups
- View timetable by teacher, class, room, or student
- Support for fortnightly (Week A/B) timetables
- Export timetable views to printable format

## Homework

Set and track homework assignments.

- Create homework tasks linked to subject, class, and teacher
- Set due dates and estimated completion time
- Track completion status: Not Started, In Progress, Submitted, Late, Exempt
- Students and parents can view upcoming and overdue homework
- Teachers can mark homework and add feedback notes
- Filter by class, subject, or date range

## Exams

Manage internal and external examinations.

- Schedule internal exams (mocks, end-of-year) with date, time, and room
- Record exam board entries: AQA, Edexcel, OCR, WJEC
- Manage candidate numbers and UCI codes
- Record and import exam results
- Access arrangements linked from SEND module (extra time, reader, scribe)
- Exam timetable view with clash checking
- Track entry fees and amendments

## Progress

Monitor student progress against targets.

- Set target grades based on KS2 prior attainment or baseline assessments
- Flight paths: visual progress trajectories showing expected grade over time
- RAG (Red/Amber/Green) status per subject based on current grade vs target
- Identify underperformance triggers automatically
- Progress snapshots at defined data collection points (e.g. termly)
- Compare progress across demographic groups (Pupil Premium, SEN, gender)

## Interventions

Plan and track targeted support for underperforming students.

- Create intervention plans linked to specific students and subjects
- Record intervention type: mentoring, small group, 1:1 tuition, catch-up sessions
- Set start/end dates and review milestones
- Track attendance at intervention sessions
- Measure impact: compare grades before, during, and after intervention
- Link to Progress module triggers for automated flagging
- Generate intervention impact reports for SLT

## Reports

Generate report cards and analytical reports.

- **Termly reports**: grades, effort scores, attendance summary, tutor comments
- **Report cards**: printable per-student reports for parents
- **Data analysis**: headline figures by subject, year group, or whole school
- Progress 8 and Attainment 8 estimate calculations
- Export reports to PDF or CSV
- Custom report templates configurable by admin
- Comparative analysis across data collection points

---

## Access by Role

| Module | Admin | Teacher | Student |
|---|---|---|---|
| Students | Full CRUD | View own classes | View own record |
| Subjects | Full CRUD | View all | View enrolled |
| Enrollment | Full CRUD | View own classes | View own |
| Grades | Full CRUD | Edit own classes | View own |
| Attendance | Full CRUD | Mark own classes | View own |
| Timetable | Full CRUD | View/print own | View own |
| Homework | Full CRUD | Set for own classes | View own |
| Exams | Full CRUD | View/enter results | View own |
| Progress | Full CRUD | View own classes | View own |
| Interventions | Full CRUD | Manage own | View own |
| Reports | Full access | Generate for classes | View own |

---

*Secondary School Management System -- Academics Domain Guide*
