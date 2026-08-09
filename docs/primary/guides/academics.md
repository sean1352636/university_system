# Primary School — Academics Guide

> Covers 11 modules: Pupils, Subjects, Classes, Assessment, Attendance, Timetable, Homework, SATs, Phonics, Reading Records, Progress

Last Updated: March 2026

---

## Pupils

Manage pupil records with unique **PRI-prefixed IDs** (PRI0001, PRI0002, etc.).

| Field | Description |
|---|---|
| Pupil ID | Auto-generated PRI prefix |
| Name | First name, surname |
| Date of Birth | Used for year group calculation |
| Year Group | Reception, Year 1–6 |
| Key Stage | EYFS (Reception), KS1 (Y1–2), KS2 (Y3–6) |
| Class | Assigned class/form group |
| Parent/Carer | Linked parent contacts |
| Status | Active, Left, Withdrawn |

**Common workflows:**
- **Add a pupil** — Navigate to Pupils tab, click Add, fill in details, assign to year group and class.
- **Transfer year group** — Use the Year Group field to move a pupil at the start of a new academic year. Bulk promotion is available via Settings.
- **View profile** — Click a pupil row to see their full profile including attendance, assessments, and pastoral notes.

### Viewing Pupil Details (Double-Click)

In the GUI, **admin / staff / teacher / instructor** users can
double-click any row in the Pupils treeview to open a read-only details
window for that pupil. This mirrors the equivalent feature in the
University System.

The details window has two tabs:

| Tab | Contents |
|---|---|
| Personal | Pupil ID, names, preferred name, DOB, gender, ethnicity, first language, year/class/key stage, SEN status, EAL/Pupil Premium/Free School Meals/Looked After/Photo Consent flags, status, address, medical notes, dietary requirements, created/updated timestamps |
| Contacts | Parent/Guardian 1 (name/email/phone), Parent/Guardian 2 (name/email/phone), Emergency Contact (name/phone) |

Footer buttons: `Close` is always present; `admin` users also see an
`Edit` button that closes the details window and opens the full edit
dialog (the same flow as the toolbar `Edit Selected` button).

Other roles (parents, students) silently no-op on double-click. The
behaviour is implemented in
`primary_school/modules/domain/academics/pupils/gui/pupil_gui.py`
via `_on_double_click_pupil` and `_show_pupil_details`.

---

## Subjects

Manage curriculum subjects taught across year groups.

Core subjects: **English**, **Maths**, **Science**. Foundation subjects include History, Geography, Art, DT, Music, PE, Computing, RE, PSHE, and MFL (KS2).

- Add or edit subjects and assign them to specific year groups.
- Link subjects to teachers for timetabling.
- Subjects feed into assessment and progress tracking.

---

## Classes

Organise pupils into class/form groups.

- Each class has a **class teacher** and optional teaching assistants.
- Classes are typically named by year group (e.g., "Year 3 Maple").
- Use the class list view to see all pupils in a class at a glance.
- Classes link to timetable, attendance registers, and homework.

---

## Assessment

Record assessments using the four-tier scale aligned to national expectations.

| Level | Meaning |
|---|---|
| **Emerging** | Working towards the expected standard |
| **Developing** | Some elements of the expected standard met |
| **Expected** | Meeting the expected standard for age |
| **Greater Depth** | Exceeding the expected standard |

**How to record assessments:**
1. Select the class and subject.
2. Choose the term (Autumn, Spring, Summer).
3. Enter a level for each pupil.
4. Save — data feeds into progress tracking automatically.

Assessments can be filtered by year group, subject, term, and key stage.

---

## Attendance

Track daily and session-based attendance with statutory absence codes.

| Code | Meaning |
|---|---|
| / | Present (AM) |
| \ | Present (PM) |
| N | Unauthorised absence |
| I | Illness |
| M | Medical appointment |
| H | Authorised holiday |
| C | Other authorised |
| L | Late (before register closes) |
| U | Late (after register closes — unauthorised) |

**Key workflows:**
- **Take register** — Open the class register for AM or PM session. Mark each pupil.
- **Persistent absence** — The system flags pupils below 90% attendance automatically.
- **Reports** — Generate attendance summaries by pupil, class, year group, or whole school.
- **Parental notification** — Absence alerts can trigger notification workflows.

---

## Timetable

Manage weekly timetables for each class.

- Assign subjects to time slots across the week.
- Allocate rooms/spaces (hall, ICT suite, playground).
- Assign teachers and support staff to sessions.
- View timetable by class, teacher, or room.
- Timetable data links to attendance register generation.

---

## Homework

Set and track homework assignments.

- **Set homework** — Select class and subject, enter title, description, and due date.
- **Track completion** — Mark homework as submitted, late, or missing for each pupil.
- **Parent visibility** — Parents can view homework assignments via the parent portal.
- Filter by class, subject, or status (outstanding, overdue, completed).

---

## SATs

Record and analyse Key Stage 1 and Key Stage 2 SATs results.

| SATs | Year Group | Subjects |
|---|---|---|
| KS1 | Year 2 | Reading, Maths, GPS (optional since 2023) |
| KS2 | Year 6 | Reading, Maths, GPS (Grammar, Punctuation & Spelling) |

- Enter **scaled scores** (expected standard: 100+).
- Record teacher assessment judgements alongside test results.
- Compare results against national averages.
- Track trends across cohorts and years.

---

## Phonics

Manage the Year 1 Phonics Screening Check.

- Record individual pupil scores (pass threshold typically 32/40).
- Flag pupils who did not meet the threshold for **resit** in Year 2.
- Track resit results for Year 2 pupils.
- Generate reports by class and year group.
- Link phonics data to reading interventions.

---

## Reading Records

Track individual reading activity and progress.

- **Log reading sessions** — Record date, book title, level, pages read, and comments.
- **Book levels** — Track progression through book bands (Pink, Red, Yellow, Blue, Green, Orange, Turquoise, Purple, Gold, White, Lime).
- **Frequency tracking** — Monitor how often each pupil reads (daily target recommended).
- **Parent entries** — Parents can log home reading via the parent portal.
- Reports highlight pupils who are reading infrequently.

---

## Progress

Monitor pupil progress across subjects and terms.

- View progress grids showing assessment levels across Autumn, Spring, and Summer terms.
- **Expected progress indicators** — The system calculates whether a pupil is on track, above, or below expected progress.
- Filter by year group, class, subject, or pupil.
- Identify pupils requiring intervention based on stalled or declining progress.
- Export progress data for reporting to governors or Ofsted.
- Progress data pulls from Assessment, SATs, and Phonics modules automatically.

---

## Quick Reference

| Module | Access Path | Key Roles |
|---|---|---|
| Pupils | Sidebar → Academics → Pupils | admin, teacher |
| Subjects | Sidebar → Academics → Subjects | admin |
| Classes | Sidebar → Academics → Classes | admin, teacher |
| Assessment | Sidebar → Academics → Assessment | admin, teacher |
| Attendance | Sidebar → Academics → Attendance | admin, teacher |
| Timetable | Sidebar → Academics → Timetable | admin |
| Homework | Sidebar → Academics → Homework | admin, teacher |
| SATs | Sidebar → Academics → SATs | admin, teacher |
| Phonics | Sidebar → Academics → Phonics | admin, teacher |
| Reading Records | Sidebar → Academics → Reading Records | admin, teacher, parent |
| Progress | Sidebar → Academics → Progress | admin, teacher |
