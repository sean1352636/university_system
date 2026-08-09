# Quick Start Guide

Get the Primary School Management System running in 5 minutes.

## Prerequisites

- **Python 3.11+** (tested on 3.11 and 3.12)
- **pip** (comes with Python)
- A virtual environment is strongly recommended
- **tkinter** (for the GUI; included with most Python distributions)

## Installation

### 1. Clone and Set Up the Virtual Environment

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd education_system

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate    # Linux / macOS
# venv\Scripts\activate     # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies include Flask, bcrypt, pyotp, and the standard library modules (tkinter, sqlite3, logging).

### 3. Verify the Installation

```bash
# Check the package is importable
python -c "from education_system.primary_school import __version__; print(__version__)"
```

## Starting the System

### Option A: Launch the GUI

```bash
python run.py --primary --gui
```

This opens the tkinter-based desktop application with a scrollable sidebar listing all 46 available modules.

### Option B: Launch the CLI

```bash
python run.py --primary --cli
```

The CLI provides a text-based menu interface for headless or remote operation.

### Option C: Universal Login

```bash
python run.py
```

The universal login window authenticates against the shared auth system and allows you to select any of the four Education System platforms (University, College, Secondary School, Primary School).

## First Login

The system uses shared authentication with pre-seeded default accounts. Use these to log in and explore:

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Super Admin | `superadmin` | `SuperAdmin@123` | Access to all 4 systems |
| Administrator | `admin3` | `admin1234` | Primary school admin |
| Staff | `staff3` | `staff1234` | Teacher / staff role |
| Student | `student3` | `student1234` | Pupil-facing features |
| Parent | `parent3` | `parent1234` | Parent portal access |

**Important**: Change these default passwords immediately in a production or shared environment. Passwords must be at least 12 characters and contain uppercase, lowercase, digits, and special characters.

## Quick Tour of Features

The system contains 46 domain modules organized into 7 categories:

### Academics (11 modules)

- **Pupils** -- Pupil records, profiles, and ID management (IDs prefixed `PRI`, e.g., PRI0001)
- **Subjects** -- Subject definitions and curriculum mapping
- **Classes** -- Class group creation and pupil assignment
- **Assessment** -- Assessment recording with levels: Emerging, Developing, Expected, Greater Depth
- **Attendance** -- Daily and session-based attendance registers
- **Timetable** -- Class timetable scheduling and room allocation
- **Homework** -- Homework setting, tracking, and completion
- **SATs** -- Key Stage 1 and Key Stage 2 SATs preparation and results
- **Phonics** -- Year 1 phonics screening check tracking
- **Reading Records** -- Reading log management and reading level tracking
- **Progress** -- Pupil progress tracking across key stages (EYFS, KS1, KS2)

### Pastoral Care (5 modules)

- **Behaviour** -- Behaviour incident logging and management
- **Rewards** -- Reward points, certificates, and recognition
- **Safeguarding** -- Safeguarding concern logging, escalation, and reporting
- **SEND** -- Special educational needs and disabilities tracking and support plans
- **Pastoral** -- Pastoral care records, referrals, and wellbeing notes

### Staff (4 modules)

- **HR** -- Staff records, contracts, and personnel management (IDs prefixed `STF`, e.g., STF0001)
- **CPD** -- Continuing professional development records
- **Cover** -- Cover lesson allocation and tracking
- **Staff Directory** -- Staff contact details and role directory

### Administration (9 modules)

- **Users** -- User account management
- **Settings** -- System configuration and preferences
- **Admissions** -- Admissions application processing and intake management
- **Finance** -- Financial management, budgets, and expenditure tracking
- **Data Export** -- Data export and reporting tools
- **Audit Log** -- System audit trail and activity logging
- **Policies** -- Policy document management and version tracking
- **Documents** -- Document storage and management

### Pupil Life (8 modules)

- **Clubs** -- Extra-curricular club management and attendance
- **Meals** -- School meal management, dietary requirements, and free school meals
- **Transport** -- Pupil transport arrangements and routes
- **Trips** -- School trip planning, risk assessments, and consent
- **Library** -- Library catalogue, loans, returns, and overdue tracking
- **Medical** -- Medical information, allergies, and medication records
- **Class Groups** -- Form group and set management
- **Consent** -- Parental consent tracking for activities and data

### Facilities (4 modules)

- **Room Booking** -- Room and space booking
- **Assets** -- Asset tracking and inventory management
- **Visitors** -- Visitor sign-in, DBS checks, and safeguarding
- **Incidents** -- Incident reporting and follow-up

### Communication (6 modules)

- **Email** -- Email communication to parents and staff
- **Notifications** -- System notifications and alerts
- **Announcements** -- School-wide announcements
- **Calendar** -- School calendar, term dates, and events
- **Parents Evening** -- Parents evening scheduling and booking
- **Communication Log** -- Communication history and audit trail

## Common Tasks

### Add a Pupil

1. Log in as `primary_admin` or a user with pupil management permissions.
2. Navigate to the **Pupils** module in the sidebar.
3. Click **Add Pupil** and fill in the required fields (name, date of birth, year group, class).
4. The system generates a pupil ID automatically (format: `PRI0001`, `PRI0002`, ...).
5. Select the year group: Reception, Year 1, Year 2, Year 3, Year 4, Year 5, or Year 6.
6. Save the record.

### Create a Class

1. Navigate to the **Classes** module.
2. Click **Add Class** and enter the class name, year group, and assigned teacher.
3. Add pupils to the class from the pupil list.
4. Save to make the class available for timetabling and attendance.

### Record an Assessment

1. Navigate to the **Assessment** module.
2. Select the subject and class.
3. For each pupil, record the assessment level:
   - **Emerging** -- Working towards the expected standard
   - **Developing** -- Making progress towards the expected standard
   - **Expected** -- Meeting the expected standard for age
   - **Greater Depth** -- Exceeding the expected standard
4. Add any notes or comments.
5. Save the assessment records.

### Mark Attendance

1. Navigate to the **Attendance** module.
2. Select the class and session (AM or PM).
3. Mark each pupil as present, absent (authorised/unauthorised), or late.
4. Save the register. Absence alerts trigger automatically where configured.

## Database

The system uses SQLite. The database file is located at:

```
primary_school/data/db_files/primary_school.db
```

The shared authentication database is at:

```
education_system/shared/data/db_files/auth.db
```

On first run, the schema is created automatically and default data (including the default user accounts above) is seeded.

## Log Files

Application logs are written to:

```
primary_school/logs/app.log
```

Log output includes timestamps, module names, and severity levels. Console output shows warnings and above; the file captures info-level and above.

## Next Steps

- **[README.md](README.md)** -- Full documentation index
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** -- Solutions to common problems
- **Shared authentication** -- See `education_system/shared/auth/` for the unified authentication system
- **Configuration** -- See `primary_school/core/defaults.py` for session timeout, lockout, and other settings

---

**Last Updated**: March 2026
**Version**: 1.0.0
