# CLI Reference

Complete command-line interface reference for the Education System.

## Launching the System

```bash
python run.py                          # Interactive mode selector
python run.py --cli --university       # University CLI directly
python run.py --gui --college          # College GUI directly
python run.py --api                    # REST API server (all systems)
python run.py --test --university      # Run university tests
python run.py --test-all              # Run all system tests
python run.py --seed 50 --college      # Seed college DB with 50 demo students
```

### Command-Line Arguments

| Flag | Description |
|------|-------------|
| `--cli` | Launch command-line interface |
| `--gui` | Launch graphical interface |
| `--api` | Run unified REST API server |
| `--test` | Run test suite (requires system flag) |
| `--test-all` | Run tests for all systems |
| `--university` | Select University system |
| `--college` | Select Sixth Form College system |
| `--school` | Select Secondary School system |
| `--primary` | Select Primary School system |
| `--seed N` | Seed database with N demo students |

If no flags are provided, an interactive menu is shown.

## Authentication

All CLI and GUI sessions go through shared authentication (`shared/auth/`).

### Login Flow

1. Username and password prompt (3 attempts)
2. MFA challenge if enabled (TOTP or email OTP)
3. Password change if expired (when force-reset is enabled)
4. System selection (if user has access to multiple systems)
5. Superadmin users go directly to the cross-system dashboard

### Default Accounts

| Username | Password | Systems | Role |
|----------|----------|---------|------|
| `superadmin` | `SuperAdmin@123` | All 4 | Admin |
| `admin` | `admin123` | University | Admin |
| `staff` | `staff123` | University | Staff |
| `S12345` | `student123` | University | Student |
| `admin1` | `admin1234` | College | Admin |
| `staff1` | `staff1234` | College | Staff |
| `student1` | `student1234` | College | Student |
| `admin2` | `admin1234` | Secondary | Admin |
| `staff2` | `staff1234` | Secondary | Staff |
| `student2` | `student1234` | Secondary | Student |
| `admin3` | `admin1234` | Primary | Admin |
| `staff3` | `staff1234` | Primary | Staff |
| `student3` | `student1234` | Primary | Student |

Parent accounts follow the same pattern (`parent`, `parent1`-`parent3`).

## University CLI Menu Structure

After login the university CLI presents a categorised menu. Options vary by role.

### Academic & Learning

| Option | Description |
|--------|-------------|
| Student Records | Enrollment, records, CRUD operations |
| Course Management | Course catalog, scheduling, prerequisites |
| Academic Calendar | Events, semesters, academic years |
| Grade Tracking | Grades, GPA, transcripts |
| LMS | Learning management system |
| Attendance | QR check-in, analytics, geofencing |
| Timetable | Schedule optimizer |
| Course Evaluation | Student feedback surveys |
| Virtual Classroom | Online sessions, recordings |

### Student Services

| Option | Description |
|--------|-------------|
| Housing | Accommodation applications, room assignments |
| Health Portal | Medical appointments, records |
| Student Union | Elections, clubs, societies |
| Career Services | Job postings, internships |
| Financial Aid | Aid applications, packages |
| Early Warning | At-risk student alerts |
| Support/Helpdesk | Tickets, FAQ, knowledge base |

### Business Operations

| Option | Description |
|--------|-------------|
| Finance | Fees, payments, billing |
| Library | Catalog, loans, reservations |
| Facilities | Room booking, maintenance |
| Transport/Parking | Permits, shuttle schedules |
| Commerce modules | Cafe, grocery, charity shop, and 10+ more |

### Communication & Institutional

| Option | Description |
|--------|-------------|
| Communication Hub | Messages, emails, SMS, newsletters |
| Admissions CRM | Prospect management, applications |
| Alumni Relations | Alumni profiles, events, donations |
| Research/Grants | Project management, publications |
| Campus Events | Event creation, registrations |
| Staff/HR Management | Departments, leave, shifts |

### Technology & Analytics

| Option | Description |
|--------|-------------|
| Admin Tools | User management, batch operations, reporting |
| Security Dashboard | Security metrics, audit logs |
| Data/Documents | Document management, exports |
| AI Features | Chatbot, plagiarism detection, AI detector |
| Business Intelligence | Reports, dashboards |
| Integrations | Third-party service connections |
| Blockchain Credentials | Digital badges, certificates |
| PDF Export | Database and document exports |
| Authentication | User/role management, MFA settings |

### Cross-System Tools (Admin Only)

| Option | Description |
|--------|-------------|
| Analytics Dashboard | Cross-system analytics |
| Outcome Tracking | Student outcome monitoring |
| Bulk Transfer | Transfer students between systems |
| Transfer Documents | Document sharing across systems |
| GDPR Compliance | Data retention, erasure requests |
| Central Admin Portal | Cross-system administration |
| Student Self-Service | Unified student portal |

### System

| Option | Description |
|--------|-------------|
| Mobile App (PWA) | Progressive web app management |
| Switch to GUI | Launch the graphical interface |
| Language | Change interface language |
| System Monitoring | Health checks, metrics (admin) |
| Switch System | Jump to College/School/Primary |

## College CLI Menu

The college CLI organises menus by role:

**Admin/Staff sections:** Teaching & Learning, Students & Pastoral, Attendance & Timetable, Exams & Assessment, Staff & HR, Administration, Finance & Funding, Communication, Facilities, Analytics, Parent & Careers, Student Self-Service, System & Settings, Cross-System Tools

**Student sections:** My Academics, Self-Service & Activities, Communication, Tools & Settings

**Parent sections:** Parent Portal, Messages, Calendar, Parents Evening, Announcements, Feedback

## Secondary School CLI Menu

Similar hierarchical structure adapted for secondary education (Years 7-11):
Academics, Pastoral Care, Attendance, Exams, Staff, Administration, Communication, Facilities, Student Life

## Primary School CLI Menu

Adapted for primary education (Reception-Year 6):
Academics, Safeguarding & Pastoral, Attendance, Assessments, Staff, Administration, Communication, Facilities, Pupil Activities

## Shared CLI Modules

These are available across all systems:

| Module | Description |
|--------|-------------|
| `login_cli.py` | Universal login with MFA support |
| `mfa_cli.py` | TOTP, email OTP, backup codes |
| `security_questions_cli.py` | Setup and verify security questions |
| `superadmin_cli.py` | Cross-system admin dashboard |

## Make Targets

```bash
make test                # All tests (excludes slow/gui)
make test-all            # Including slow tests
make test-university     # University tests only
make test-shared         # Shared module tests
make test-auth           # Auth infrastructure tests
make lint                # Ruff check
make lint-fix            # Ruff auto-fix
make format              # Ruff format
make type-check          # Mypy
make security-scan       # Bandit
make ci                  # clean + lint + test-cov + security-scan
```
