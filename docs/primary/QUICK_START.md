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
cd education-system

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate    # Linux / macOS
# venv\Scripts\activate     # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.lock
pip install -e .
```

Key dependencies include Flask, bcrypt, pyotp, and the standard library modules (tkinter, sqlite3, logging).

### 3. Verify the Installation

```bash
# Check the package is importable
python -c "from education_system.systems.primary.manifest import MANIFEST; print(MANIFEST.display_name)"
```

## Starting the System

### Option A: Launch the GUI

```bash
python -m education_system --primary --gui
```

This opens the tkinter-based desktop application with a scrollable sidebar listing the available modules.

### Option B: Launch the CLI

```bash
python -m education_system --primary --cli
```

The CLI provides a text-based menu interface for headless or remote operation.

### Option C: Universal Login

```bash
python -m education_system
```

The universal login window authenticates against the shared auth system and allows you to select any of the seven Education System platforms you have access to (Nursery, Primary School, Secondary School, Sixth Form College, FE College, Apprenticeships, University).

## First Login

The system uses shared authentication. When started with `EDU_DEV_SEED=true`, it seeds these default accounts. Use them to log in and explore:

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Super Admin | `superadmin` | `SuperAdmin@123` | Access to all 7 systems |
| Administrator | `admin3` | `admin1234` | Primary school admin |
| Staff | `staff3` | `staff1234` | Teacher / staff role |
| Student | `student3` | `student1234` | Pupil-facing features |
| Parent | `parent3` | `parent1234` | Parent portal access |

**Important**: Change these default passwords immediately in a production or shared environment. Passwords must be at least 12 characters and contain uppercase, lowercase, digits, and special characters.

## Quick Tour of Features

The sidebar groups the system's modules into 9 categories:

- **Pupil Management** -- Pupil directory and profiles (IDs prefixed `P`), admissions, year group enrolment, onboarding, bulk operations, and leavers
- **Academic Management** -- Academic year, calendar, year groups, classes, subjects, timetable, attendance register, lesson plans, cover, homework, phonics tracking, reading levels, library, and clubs
- **Assessment & Progress** -- Assessment records (grades BLW, WTS, EXS, GDS), phonics screening, multiplication check, KS1 and KS2 SATs, EYFS profile, target setting, interventions, early warning, observations, and pupil reports
- **Pastoral & Wellbeing** -- Class teachers, behaviour, house points, safeguarding, SEND, pupil premium, accessibility, wellbeing, pupil support, attendance concerns, absence requests, first aid, medical records, emergency contacts, Prevent duty, equality and diversity, complaints, feedback, surveys, school council, breakfast and after-school club, and transport
- **Staff & Communication** -- Staff directory (IDs prefixed `T`), teaching assistants, HR, absence, wellbeing, recruitment, appraisals, CPD, DBS checks, visitors, parent contacts, parents' evenings, newsletters, announcements, notifications, activity feed, email and messaging, letter templates, document hub, and attachments
- **Finance** -- Dinner money, trips and payments, receipts, expense claims, funding, and school census
- **Reports & Analytics** -- Attendance and progress reports, KPI, data and mobile dashboards, audit reports, and data exports
- **Cross-System** -- Student journey, analytics dashboard, cross-system calendar, central admin portal, GDPR compliance, shared documents, pupil self-service, and certificates
- **System** -- Change password, MFA, user accounts, user management, settings, compliance, governance, policies, GDPR, risk management, health and safety, assets, multi-language, to-do, and about

## Common Tasks

### Add a Pupil

1. Log in as `admin3` or a user with pupil management permissions.
2. Navigate to the **Pupils** module in the sidebar.
3. Click **Add Pupil** and fill in the required fields (name, date of birth, year group, class).
4. The system generates a pupil ID automatically (the prefix `P` followed by digits).
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
   - **BLW** -- Working below the expected standard
   - **WTS** -- Working towards the expected standard
   - **EXS** -- Meeting the expected standard
   - **GDS** -- Working at greater depth
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
var/data/primary/primary.db
```

The shared authentication database is at:

```
var/data/platform/db_files/auth.db
```

On first run, each module creates its tables automatically. The default user accounts above are seeded only when `EDU_DEV_SEED=true`.

## Log Files

Application logs are written to the console; the Primary School writes no log file of its own. Console output shows warnings and above. Start with `--verbose` to see info-level messages:

```bash
python -m education_system --primary --gui --verbose
```

## Next Steps

- **[README.md](README.md)** -- Full documentation index
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** -- Solutions to common problems
- **Shared authentication** -- See `src/education_system/platform/identity/auth/` for the unified authentication system
- **Configuration** -- See `src/education_system/platform/identity/auth/defaults.py` for session timeout, lockout, and other settings

---

**Last Updated**: October 2026
