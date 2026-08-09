# Staff Management Domain Guide

**Secondary School Management System**
Last Updated: March 2026

---

## Overview

The Staff Management domain covers 4 modules for personnel records, professional development, absence cover, and directory services. Staff IDs use the STF prefix (STF0001 onwards). All data is stored in `secondary_school.db`.

---

## HR (Human Resources)

Manage staff records, contracts, and statutory compliance.

### Staff Records

| Field | Description |
|---|---|
| Staff ID | Auto-generated, STF0001 onwards |
| Role | Teaching, Support, SLT, Admin |
| Department | Linked to subject departments |
| Employment Status | Full-time, Part-time, Temporary, Supply |
| Start Date | Date employment commenced |
| Contract Type | Permanent, Fixed-term, Casual |

- Create and maintain staff personnel files
- Record qualifications, specialism subjects, and teaching responsibilities
- Store emergency contact details
- Track contract start/end dates and renewal reminders
- Manage pay scale references (Main Pay Range, Upper Pay Range, Leadership)

### DBS and Safeguarding Checks

- Record DBS certificate numbers, issue dates, and check levels (Enhanced, Enhanced with Barred List)
- Track DBS update service subscription status
- Flag expiring or missing DBS checks with automated alerts
- Right to work documentation and verification dates

### Single Central Record (SCR)

The SCR is a statutory requirement for all schools. The system maintains:

| Check | Required For | Renewal |
|---|---|---|
| Identity verification | All staff | One-time |
| DBS check | All staff | As required |
| Right to work | All staff | As required |
| Barred list check | All staff | With DBS |
| Qualifications (QTS) | Teaching staff | One-time |
| Prohibition check | Teaching staff | One-time |
| Overseas criminal record | Staff from abroad | One-time |
| Medical fitness | All staff | As required |

- Generate the SCR as a printable report for Ofsted readiness
- Highlight incomplete or missing checks
- Audit trail for all SCR updates

## CPD (Continuing Professional Development)

Track staff training, certifications, and professional growth.

- Log CPD activities: courses, workshops, conferences, in-house training
- Record date, provider, duration (hours), and cost
- Upload certificates and evidence of completion
- Link CPD to performance management objectives
- Track mandatory training completion: safeguarding, first aid, fire safety, prevent
- CPD budget tracking per department or individual
- Generate CPD summary reports for appraisals
- Set reminders for certification renewals (e.g. first aid expires every 3 years)

| Training Type | Frequency | Mandatory |
|---|---|---|
| Safeguarding / Child Protection | Annual | Yes |
| Prevent (counter-terrorism) | Annual | Yes |
| Fire Safety | Annual | Yes |
| First Aid | Every 3 years | Selected staff |
| Data Protection / GDPR | Annual | Yes |
| Subject-specific CPD | Ongoing | No |

## Cover

Manage staff absence and arrange teaching cover.

### Absence Recording

- Record staff absences with reason, start date, and expected return
- Absence categories: illness, personal, bereavement, jury service, training, maternity/paternity
- Track absence patterns and generate summary reports
- Return-to-work meeting logging

### Cover Arrangements

- View the cover timetable: which lessons need cover on a given day
- Assign internal cover from available staff (using free period data from Timetable module)
- Book external supply teachers with contact details and daily rate
- Automatic notification to cover staff
- Track cover costs per absence and per term
- Fair distribution monitoring: ensure cover is spread evenly among staff
- Print daily cover sheet for staff room display

| Cover Type | Description |
|---|---|
| Internal | Existing staff covering during free periods |
| Supply | External supply teacher booked for the day |
| Split | Class split across multiple rooms/teachers |
| Self-cover | Work set by absent teacher, supervised |

## Staff Directory

Searchable directory of all school staff.

- Search by name, department, role, or subject
- View contact details: school email, phone extension
- Department membership and head of department flags
- Qualifications and subject specialisms
- Current timetable summary (teaching load, free periods)
- Photo directory for identification
- Export directory to CSV or PDF
- Filter by employment status (active, on leave, left)

---

## Access by Role

| Module | Admin | Teacher | Student |
|---|---|---|---|
| HR | Full CRUD | View own record | No access |
| CPD | Full CRUD | View/log own CPD | No access |
| Cover | Full CRUD | View own cover | No access |
| Staff Directory | Full access | View all contacts | View names only |

---

## Key Workflows

### New Staff Onboarding
1. Create staff record in HR with personal details and contract
2. Complete SCR checks: DBS, right to work, qualifications, references
3. Add to Staff Directory with department and contact details
4. Schedule mandatory CPD: safeguarding, fire safety, prevent
5. Assign timetable (via Timetable module)

### Staff Departure
1. Record leaving date in HR
2. Archive staff record (retain for statutory period)
3. Reassign classes and responsibilities
4. Update Staff Directory status to "Left"
5. Arrange cover for any remaining timetabled lessons

---

*Secondary School Management System -- Staff Management Domain Guide*
