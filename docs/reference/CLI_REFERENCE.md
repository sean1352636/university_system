# CLI Reference

Complete command-line interface reference for the Education System.

## Launching the System

```bash
python -m education_system                          # Interactive mode selector
python -m education_system --cli --university       # University CLI directly
python -m education_system --gui --college          # Sixth Form College GUI directly
python -m education_system --api                    # REST API server (all systems)
python -m education_system --test --university      # Run university tests
python -m education_system --test-all              # Run all system tests
python -m education_system --seed 50 --college      # Seed the sixth form DB with 50 demo students
```

### Command-Line Arguments

| Flag | Description |
|------|-------------|
| `--cli` | Launch command-line interface |
| `--gui` | Launch graphical interface |
| `--api` | Run unified REST API server |
| `--web` | Open the static HTML web UI in a browser (`--web-port`, `--web-no-browser`) |
| `--test` | Run test suite (requires system flag) |
| `--test-all` | Run tests for all systems |
| `--university` | Select University system |
| `--college` | Select Sixth Form College system (`--sixthform` alias) |
| `--secondary` | Select Secondary School system (`--school` alias) |
| `--primary` | Select Primary School system |
| `--nursery` | Select Nursery / Early Years system |
| `--fecollege` | Select FE College system (`--fe-college` alias) |
| `--apprenticeships` | Select Apprenticeships system (`--apprenticeship` alias) |
| `--seed N` | Seed database with N demo students |

If no flags are provided, an interactive menu is shown.

## Authentication

All CLI and GUI sessions go through shared authentication (`src/education_system/platform/identity/auth/`).

### Login Flow

1. Username and password prompt (3 attempts)
2. MFA challenge if enabled (TOTP or email OTP)
3. Password change if expired (when force-reset is enabled)
4. System selection (if user has access to multiple systems)
5. Superadmin users go directly to the cross-system dashboard

### Default Accounts

Seeded only when `EDU_DEV_SEED=true`. [DEFAULT_ACCOUNTS.md](DEFAULT_ACCOUNTS.md) has the full list.

| Username | Password | Systems | Role |
|----------|----------|---------|------|
| `superadmin` | `SuperAdmin@123` | All 7 | Admin |
| `admin` | `admin123` | University | Admin |
| `staff` | `staff123` | University | Staff |
| `S12345` | `student123` | University | Student |
| `admin1` | `admin1234` | Sixth Form | Admin |
| `staff1` | `staff1234` | Sixth Form | Teacher |
| `student1` | `student1234` | Sixth Form | Student |
| `admin2` | `admin1234` | Secondary | Admin |
| `staff2` | `staff1234` | Secondary | Teacher |
| `student2` | `student1234` | Secondary | Student |
| `admin3` | `admin1234` | Primary | Admin |
| `staff3` | `staff1234` | Primary | Teacher |
| `student3` | `student1234` | Primary | Student |
| `admin4` | `admin1234` | Nursery | Admin |
| `admin5` | `admin1234` | Apprenticeships | Admin |
| `tutor1` | `tutor1234` | Apprenticeships | Staff (tutor) |
| `apprentice1` | `apprentice1234` | Apprenticeships | Apprentice |
| `employer1` | `employer1234` | Apprenticeships | Employer |
| `assessor1` | `assessor1234` | Apprenticeships | End-point assessor |
| `admin6` | `admin1234` | FE College | Admin |
| `lecturer1` | `lecturer1234` | FE College | Teacher |
| `learner1` | `learner1234` | FE College | Student |

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
| Cross-System Calendar | Calendar across systems |
| Inter-System Messaging | Messages between systems |
| Central Admin Portal | Cross-system administration |
| GDPR Compliance | Data retention, erasure requests |
| Shared Documents | Document sharing across systems |
| Student Self-Service | Unified student portal |
| Digital Transcript | Cross-system transcript |
| Apprenticeship Progression | Progression into apprenticeships |

### System

| Option | Description |
|--------|-------------|
| Mobile App (PWA) | Progressive web app management |
| Switch to GUI | Launch the graphical interface |
| Language | Change interface language |
| System Monitoring | Health checks, metrics (admin) |
| Switch System | Jump to any other system the account can access |

## Sixth Form College Menu

Categories (`systems/sixth_form/interfaces/gui/gui_main.py`, mirrored by the CLI): Student Management, Academic Management, Assessment & Grades, UCAS & Careers, Pastoral & Wellbeing, Staff & Communication, Finance & Bursaries, Operations, Reports & Analytics, Cross-System, System

## Secondary School Menu

Adapted for secondary education (Years 7-11):
Pupil Management, Academic Management, Assessment & Grades, Pastoral & Wellbeing, Staff & Communication, Finance, Reports & Analytics, Cross-System, System

## Primary School Menu

Adapted for primary education (Reception-Year 6):
Pupil Management, Academic Management, Assessment & Progress, Pastoral & Wellbeing, Staff & Communication, Finance, Reports & Analytics, Cross-System, System

## Nursery Menu

Children & Admissions, EYFS Learning & Development, Daily Care & Routines, Safeguarding & Welfare, Parents & Communication, Staff & Ratios, Finance, Compliance & Reports, Cross-System, System

## FE College Menu

The menu follows the signed-in user's view:

**Admin:** Overview, People, Curriculum, Money, Communication

**Staff:** Overview, Teaching, Assessment, Learners, Communication

**Student:** Overview, My learning, Me

## Apprenticeships Menu

Each of the five roles has its own menu. See [the Apprenticeships CLI reference](college_and_apprenticeships/cli.md).

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
make ci                  # clean + lint + test-cov + security-scan + supply-chain-check
```
