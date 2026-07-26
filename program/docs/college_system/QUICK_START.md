# Quick Start Guide

Get the Sixth Form College Management System running in 5 minutes.

## Prerequisites

- **Python 3.8+** (tested on 3.10 and 3.11)
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

Key dependencies include Flask, Flask-CORS, and the standard library modules (tkinter, sqlite3, logging).

### 3. Verify the Installation

```bash
# Check the package is importable
python -c "from education_system.college_system import __version__; print(__version__)"
# Expected output: 1.0.0
```

## Starting the System

### Option A: Launch the GUI

```bash
python -m education_system.college_system.run
```

This opens the tkinter-based desktop application with a sidebar listing all available modules.

### Option B: Start the API Server

```bash
python -m education_system.college_system.api.api_server
```

The Flask API server starts on `http://127.0.0.1:5000` by default. Configuration is controlled by environment variables or the defaults in `core/defaults.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `COLLEGE_API_HOST` | `127.0.0.1` | API bind address |
| `COLLEGE_API_PORT` | `5000` | API port |
| `COLLEGE_API_DEBUG` | `false` | Flask debug mode |
| `COLLEGE_JWT_SECRET` | `change-me-in-production` | JWT signing secret |
| `COLLEGE_JWT_EXPIRY` | `24` | JWT token lifetime in hours |
| `COLLEGE_SESSION_TIMEOUT` | `30` | Session timeout in minutes |

## First Login

The system uses shared authentication with pre-seeded default accounts:

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Super Admin | `superadmin` | `SuperAdmin@123` | Access to all 4 systems |
| Administrator | `admin1` | `admin1234` | College admin |
| Staff | `staff1` | `staff1234` | College teacher/staff |
| Student | `student1` | `student1234` | Student-facing features |
| Parent | `parent1` | `parent1234` | Parent portal access |

**Important**: Change these default passwords immediately in a production or shared environment. Passwords must be at least 12 characters and contain uppercase, lowercase, digits, and special characters.

## Quick Tour of Features

The system contains over 110 domain modules organized into functional areas:

### Academics and Teaching

- **Students** -- Student records, profiles, and ID management (IDs prefixed `SFC`, e.g., SFC0001)
- **Courses** -- Course creation, prerequisites, and capacity management
- **Enrollment** -- Enrollment processing and withdrawal workflows
- **Grades / Markbook** -- Grade entry, mark schemes, and grade reports
- **Attendance** -- Timetable-linked attendance registers
- **Timetable** -- Room scheduling, clash detection, instructor views
- **Assignments** -- Assignment creation, submission, and marking
- **Exams** -- Exam scheduling and results management
- **Lesson Plans** -- Lesson planning and resource linking
- **Observations** -- Teaching observation records and feedback

### Student Support and Welfare

- **Pastoral** -- Pastoral care records and referrals
- **Safeguarding** -- Safeguarding concern logging and escalation
- **SEND** -- Special educational needs and disabilities tracking
- **Behaviour / Disciplinary** -- Behaviour incidents and disciplinary actions
- **Early Warning** -- At-risk student early warning system
- **Intervention Tracking** -- Targeted intervention management
- **Student Wellbeing** -- Wellbeing monitoring and support
- **ILP** -- Individual learning plans
- **Peer Mentoring** -- Peer mentoring scheme management
- **Counseling / First Aid** -- Health and first aid records

### Further Education Specific

- **Study Programmes** -- Study programme planning and tracking
- **Funding** -- Funding body reporting and eligibility tracking
- **T-Levels** -- T-Level programme management
- **Apprenticeships** -- Apprenticeship tracking and employer links
- **Functional Skills** -- Functional skills (English, maths) tracking
- **UCAS** -- UCAS application management
- **Destinations** -- Post-college destination tracking
- **Bursary** -- Bursary and financial support allocation
- **Enrichment** -- Enrichment activities and participation tracking
- **Value Added** -- Value-added and progress measures

### Staff and HR

- **Staff HR** -- Staff records, contracts, and personnel management
- **Staff Absence** -- Staff absence tracking and cover requests
- **Cover** -- Cover lesson allocation
- **CPD** -- Continuing professional development records
- **Appraisals** -- Staff appraisal and performance review
- **Recruitment** -- Recruitment and vacancy management
- **Onboarding** -- New staff onboarding workflows
- **DBS Checks** -- DBS check tracking and single central record
- **Staff Wellbeing** -- Staff wellbeing initiatives

### Finance and Administration

- **Finance** -- Financial management, budgets, and reporting
- **Expense Claims** -- Expense claim submission and approval
- **Admissions** -- Admissions application processing
- **Data Export** -- Data export and reporting tools
- **Audit Reports** -- System audit trail and reports
- **Policies** -- Policy document management
- **GDPR** -- GDPR compliance tools and data subject requests
- **Bulk Operations** -- Batch data processing
- **User Management** -- User account administration

### Facilities and Resources

- **Assets** -- Asset tracking and inventory
- **Resource Booking** -- Room and resource booking
- **Library** -- Library catalog, loans, and returns
- **Transport** -- Student transport arrangements
- **Lettings** -- Premises lettings management
- **Print Credits** -- Print credit allocation and tracking
- **Health and Safety** -- Health and safety records
- **Risk Management** -- Risk register and assessments
- **Visitors** -- Visitor management and sign-in

### Communication and Engagement

- **Notifications** -- System notifications
- **Messaging** -- Internal messaging
- **Announcements** -- College-wide announcements
- **SMS / Email** -- SMS and email communication
- **Calendar** -- College calendar and events
- **Parent Portal** -- Parent/guardian access portal
- **Parents Evening** -- Parents evening booking
- **Surveys** -- Survey creation and analysis
- **Feedback** -- Feedback collection
- **Letter Templates** -- Letter and mail merge templates

### Governance and Quality

- **Governance** -- Governance board records
- **Compliance** -- Regulatory compliance tracking
- **Quality Assurance** -- Quality assurance processes
- **Self Assessment** -- Self-assessment report (SAR) management
- **Internal Verification** -- Internal verification records
- **Equality and Diversity** -- Equality monitoring and reporting
- **KPI Dashboard** -- Key performance indicator dashboards
- **Prevent Duty** -- Prevent duty compliance

## Common Tasks

### Add a New Student

1. Log in as `admin` or a user with student management permissions.
2. Navigate to the **Students** module in the sidebar.
3. Click **Add Student** and fill in the required fields (name, date of birth, contact details).
4. The system generates a student ID automatically (format: `SFC0001`, `SFC0002`, ...).
5. Save the record.

### Create a Course

1. Navigate to the **Courses** module.
2. Click **Add Course** and enter the course name, code, department, and capacity.
3. Assign an instructor and set the academic year.
4. Save to make the course available for enrollment.

### Process an Enrollment

1. Navigate to the **Enrollment** module.
2. Select a student and choose the course(s) to enroll in.
3. The system validates prerequisites and capacity constraints.
4. Confirm the enrollment. The student now appears on the course register.

### Mark Attendance

1. Navigate to the **Attendance** module.
2. Select the class/session from the timetable-linked register.
3. Mark each student as present, absent, or late.
4. Save the register. Absence alerts trigger automatically where configured.

## Database

The system uses SQLite. The database file is located at:

```
college_system/data/db_files/sixthform.db
```

On first run, the schema is created automatically and default data (including the default user accounts above) is seeded.

## Log Files

Application logs are written to:

```
college_system/logs/app.log
```

Log output includes timestamps, module names, and severity levels. Console output shows warnings and above; the file captures info-level and above.

## Next Steps

- **[README.md](README.md)** -- Full documentation index
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** -- Solutions to common problems
- **Security setup** -- See `docs/college_system/security/` for authentication and MFA configuration
- **API reference** -- See `docs/college_system/infrastructure/` for REST API documentation
- **Developer guide** -- See `docs/college_system/development/` for contributing and module development

---

**Last Updated**: March 2026
**Version**: 1.0.0
