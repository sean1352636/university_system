# Student Life Domain Guide

**Secondary School Management System**
Last Updated: March 2026

---

## Overview

The Student Life domain covers 9 modules supporting the wider student experience beyond the classroom: extra-curricular activities, welfare, transport, careers, and library services. All data is stored in `secondary_school.db`.

---

## Clubs

Manage extra-curricular clubs and activities.

- Create clubs with name, description, day/time, location, and staff lead
- Categorise: sport, music, drama, academic, creative, STEM, community
- Student enrollment with capacity limits
- Track attendance at club sessions
- Termly or annual club schedules
- Waiting lists for oversubscribed clubs
- Generate participation reports (useful for references and UCAS)
- Publish club listings for students and parents

| Field | Description |
|---|---|
| Club Name | e.g. Football, Chess, Drama, Coding |
| Day / Time | Scheduled session (e.g. Tuesday 3:30-4:30) |
| Location | Room or facility |
| Lead Staff | Staff member responsible (STF ID) |
| Capacity | Maximum number of students |
| Year Groups | Eligible year groups (7-11 or subset) |

## Meals

Manage school meals, free school meals eligibility, and dietary needs.

- Record Free School Meal (FSM) eligibility per student
- Track FSM Ever 6 status (eligible in past 6 years) for Pupil Premium
- Log dietary requirements: vegetarian, vegan, halal, kosher, allergies
- Record allergy details with severity level and action plan
- Daily meal choice recording (if applicable)
- Meal account balances and top-up tracking
- Generate FSM reports for census returns
- Catering reports: meal uptake by year group

| Dietary Flag | Description |
|---|---|
| FSM | Currently eligible for free school meals |
| FSM Ever 6 | Eligible at any point in last 6 years |
| Allergy | Specific food allergy (with details) |
| Medical Diet | Diet required for medical reasons |
| Religious/Cultural | Halal, kosher, vegetarian by belief |

## Transport

Manage school transport routes and student travel.

- Define bus routes with stops, times, and operator details
- Assign students to routes based on home address
- Track bus pass allocation and validity
- Record transport mode per student: school bus, public transport, walk, cycle, car
- Manage transport applications and eligibility (distance-based)
- Absent student lists sent to transport team daily
- Emergency contact details accessible for transport staff
- Generate route lists with student names and pickup points

## Trips

Plan and manage educational visits with risk assessments and consent.

- Create trip records: destination, date, educational purpose, year groups
- Risk assessment completion and approval workflow
- Staff-to-student ratio tracking
- Consent form management: issue, track, and record parental consent
- Payment tracking: trip cost, deposits, instalments, balance
- Medical information export for trip leaders (allergies, medications)
- Emergency contact lists for off-site activities
- Post-trip evaluation logging
- Insurance and provider documentation

| Trip Status | Description |
|---|---|
| Draft | Being planned, not yet approved |
| Pending Approval | Risk assessment submitted for review |
| Approved | Approved by SLT, consent forms issued |
| Open | Accepting consent and payments |
| Closed | All places filled or deadline passed |
| Completed | Trip has taken place |
| Cancelled | Trip cancelled (refund process triggered) |

## Careers

Support careers education, information, advice, and guidance (CEIAG).

- Record careers interviews and guidance sessions per student
- Track work experience placements: employer, dates, role, risk assessment
- Log careers events: assemblies, employer visits, careers fairs
- Post-16 destination tracking: sixth form, college, apprenticeship
- Gatsby Benchmark self-assessment tools
- Record student career aspirations and interests
- Link to option choices (Year 9) and subject pathways
- Provider access: manage visits from post-16 providers (Baker Clause compliance)
- Generate CEIAG reports for governors and Ofsted

## Library

Manage the school library catalogue and loan system.

- Catalogue books with ISBN, title, author, category, and location
- Barcode/ID-based loan system linked to student SEC IDs
- Track loans, returns, due dates, and overdue items
- Reservation system for popular titles
- Fine tracking for lost or damaged books
- Reading lists by year group or subject
- Stock reports: total holdings, loans per term, popular titles
- Weeding and stock-take tools
- Student reading history (viewable by student and librarian)

| Loan Rule | Value |
|---|---|
| Loan period | 14 days (default) |
| Max loans | 3 books per student |
| Renewal | 1 renewal allowed |
| Overdue alert | Notification at 1 day overdue |

## Medical

Record student medical conditions, medications, and first aid.

- Log medical conditions per student: asthma, epilepsy, diabetes, allergies
- Record medications held in school: name, dosage, administration times, storage
- Individual Healthcare Plans (IHPs) for students with significant conditions
- First aid log: date, time, student, injury/illness, treatment, staff administering
- Notify parents of first aid incidents
- Track recurring medical visits for patterns
- Emergency action plans for anaphylaxis, seizures, etc.
- Export medical information for trips and off-site activities
- Medication consent forms and administration records

## Form Groups

Manage form/tutor group assignments and registration.

- Assign students to form groups (e.g. 7A, 7B, 8C)
- Assign form tutors (staff members) to each form group
- Morning registration linked to Attendance module
- Form group student lists with key information flags (SEN, PP, medical)
- Transfer students between form groups
- Form group history tracking
- Year group overview: all form groups within a year
- Pastoral data summary per form group for tutor reference

| Field | Description |
|---|---|
| Form Group | e.g. 7A, 9C, 11B |
| Form Tutor | Assigned staff member (STF ID) |
| Year Group | 7, 8, 9, 10, or 11 |
| Student Count | Number of students in group |
| Room | Base room for registration |

## Consent

Track parental consent across multiple categories.

- Manage consent types: photos, trips, medical treatment, data sharing, online platforms
- Issue consent requests to parents (linked to student records)
- Record consent responses: granted, refused, not yet responded
- Consent validity periods and renewal tracking
- Bulk consent collection for start-of-year permissions
- Override and withdrawal: parents can update consent at any time
- Reports showing consent status by type, year group, or individual
- Link to Trips module for trip-specific consent
- GDPR compliance: data processing consent documentation

| Consent Type | Description | Frequency |
|---|---|---|
| Photographs | Use in school publications, website, social media | Annual |
| Trips (blanket) | General permission for local educational visits | Annual |
| Trip (specific) | Individual trip consent | Per trip |
| Medical Treatment | Permission for emergency first aid | Annual |
| Online Platforms | Access to learning platforms | Annual |
| Data Sharing | Sharing data with external agencies | As needed |

---

## Access by Role

| Module | Admin | Teacher | Student |
|---|---|---|---|
| Clubs | Full CRUD | Manage own clubs | View and join |
| Meals | Full CRUD | View FSM flags | View own |
| Transport | Full CRUD | View routes | View own route |
| Trips | Full CRUD | Manage own trips | View and sign up |
| Careers | Full CRUD | Log guidance | View own record |
| Library | Full CRUD | View catalogue | Borrow and view |
| Medical | Full CRUD | View flags for own pupils | View own |
| Form Groups | Full CRUD | View own tutor group | View own |
| Consent | Full CRUD | View status | No access |

---

*Secondary School Management System -- Student Life Domain Guide*
