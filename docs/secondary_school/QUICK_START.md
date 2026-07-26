# Quick Start Guide

Get the Secondary School Management System running in 5 minutes.

## Prerequisites

- **Python 3.11+** (3.11 or later recommended)
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

Key dependencies include Flask, Flask-CORS, bcrypt, pyotp, and the standard library modules (tkinter, sqlite3, logging).

### 3. Verify the Installation

```bash
# Check the package is importable
python -c "import education_system.secondary_school; print('OK')"
```

## Starting the System

### Option A: Launch the GUI

```bash
python run.py --school --gui
```

This opens the tkinter-based desktop application with a scrollable sidebar listing all 51 modules.

### Option B: Launch the CLI

```bash
python run.py --school --cli
```

This starts the command-line interface for headless operation.

### Option C: Universal Login (All Systems)

```bash
python run.py
```

This launches the shared universal login window. After authenticating, select the Secondary School system to enter.

### Configuration Defaults

Key defaults are defined in `secondary_school/core/defaults.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `SESSION_TIMEOUT` | `30` min | Session timeout before automatic logout |
| `MAX_LOGIN_ATTEMPTS` | `5` | Failed attempts before account lockout |
| `API_PORT` | `5001` | API server port |

## First Login

The system uses shared authentication (`shared/auth/`). Default accounts are seeded on first run:

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Super Admin | `superadmin` | `SuperAdmin@123` | All 4 systems |
| Administrator | `admin2` | `admin1234` | Secondary school |
| Staff | `staff2` | `staff1234` | Secondary school |
| Student | `student2` | `student1234` | Secondary school |
| Parent | `parent2` | `parent1234` | Parent portal |

**Important**: Change these default passwords immediately in a production or shared environment. Passwords must be at least 12 characters and contain uppercase, lowercase, digits, and special characters.

## Quick Tour of Features

The system contains 51 domain modules organized into 7 categories:

### Academics (12 modules)

- **Students** -- Student records, profiles, and ID management (IDs prefixed `SEC`, e.g., SEC0001)
- **Subjects** -- Subject creation and management
- **Enrollment** -- Enrollment processing and subject option choices
- **Grades** -- Grade entry and reporting using the GCSE 9-1 scale
- **Attendance** -- Timetable-linked attendance registers
- **Timetable** -- Period scheduling, room allocation, and clash detection
- **Homework** -- Homework setting, submission tracking, and marking
- **Exams** -- Exam scheduling, seating plans, and results management
- **Progress** -- Student progress tracking across key stages (KS3/KS4)
- **Interventions** -- Targeted intervention management for at-risk students
- **Reports** -- Academic report generation and distribution

### Pastoral Care (8 modules)

- **Behaviour** -- Behaviour incident logging and tracking
- **Detentions** -- Detention scheduling and attendance
- **Exclusions** -- Fixed-term and permanent exclusion records
- **Rewards** -- Reward points and achievement tracking
- **Pastoral** -- Pastoral care records, referrals, and notes
- **Safeguarding** -- Safeguarding concern logging and escalation (CPOMS-style)
- **SEND** -- Special educational needs and disabilities tracking, EHCPs, and provision mapping

### Staff (4 modules)

- **HR** -- Staff records, contracts, and personnel management
- **CPD** -- Continuing professional development records and planning
- **Cover** -- Cover lesson allocation and management
- **Staff Directory** -- Staff contact details and department listings

### Admin (9 modules)

- **Users** -- User account administration and role management
- **Settings** -- System configuration and preferences
- **Admissions** -- Admissions application processing and intake management
- **Finance** -- Financial management, budgets, and fee tracking
- **Data Export** -- Data export and reporting tools
- **Audit Log** -- System audit trail and activity records
- **Policies** -- Policy document management and version control
- **Documents** -- Document storage and management

### Student Life (10 modules)

- **Clubs** -- Extra-curricular club management and membership
- **Meals** -- School meals, dietary requirements, and free school meals tracking
- **Transport** -- Student transport arrangements and bus routes
- **Trips** -- Educational visit planning, risk assessments, and consent
- **Careers** -- Careers guidance and work experience tracking
- **Library** -- Library catalogue, loans, and returns
- **Medical** -- Medical records and first aid logging
- **Form Groups** -- Form/tutor group management and registration
- **Consent** -- Parental consent collection and management

### Facilities (6 modules)

- **Room Booking** -- Room and resource booking
- **Assets** -- Asset tracking and inventory management
- **Seating Plans** -- Classroom seating plan creation and management
- **Visitors** -- Visitor management, sign-in, and DBS checks
- **Incidents** -- Health and safety incident recording

### Communication (7 modules)

- **Email** -- Email composition and distribution
- **Notifications** -- System notifications and alerts
- **Announcements** -- School-wide announcements
- **Calendar** -- School calendar, term dates, and events
- **Parents Evening** -- Parents evening booking and scheduling
- **Communication Log** -- Communication audit trail

## Common Tasks

### Add a Student

1. Log in as `school_admin` or a user with student management permissions.
2. Navigate to the **Students** module in the sidebar.
3. Click **Add Student** and fill in the required fields (name, date of birth, year group, form group).
4. The system generates a student ID automatically (format: `SEC0001`, `SEC0002`, ...).
5. Save the record.

### Enroll in Subjects

1. Navigate to the **Enrollment** module.
2. Select a student and choose the subject(s) to enroll in.
3. The system validates prerequisites, capacity, and option block constraints.
4. Confirm the enrollment. The student now appears on the subject register.

### Record Grades (GCSE 9-1 Scale)

1. Navigate to the **Grades** module.
2. Select the subject and assessment period.
3. Enter grades for each student using the 9-1 scale (9 = highest, 1 = lowest).
4. Save. Grade summaries and progress data update automatically.

### Mark Attendance

1. Navigate to the **Attendance** module.
2. Select the class/period from the timetable-linked register.
3. Mark each student as present, absent, late, or authorised/unauthorised absence.
4. Save the register. Absence alerts trigger automatically where configured.

### Log a Behaviour Incident

1. Navigate to the **Behaviour** module.
2. Click **New Incident** and select the student(s) involved.
3. Record the incident type, description, location, and any sanctions applied.
4. Save. The incident appears on the student's behaviour record and triggers any configured alerts.

## Database

The system uses SQLite. The database file is located at:

```
secondary_school/data/db_files/secondary_school.db
```

On first run, the schema is created automatically and default data (including the default user accounts above) is seeded.

## Log Files

Application logs are written to:

```
secondary_school/logs/app.log
```

Log output includes timestamps, module names, and severity levels. Console output shows warnings and above; the file captures info-level and above.

## Next Steps

- **[README.md](README.md)** -- Full documentation index
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** -- Solutions to common problems
- **Security setup** -- See `docs/secondary_school/security/` for authentication and MFA configuration
- **Database reference** -- See `docs/secondary_school/infrastructure/` for schema documentation
- **Developer guide** -- See `docs/secondary_school/development/` for contributing and module development

---

**Last Updated**: March 2026
